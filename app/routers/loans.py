from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date, timedelta, datetime
from pathlib import Path
import os
import json
from ..database import get_db
from ..models.customer import Customer
from ..models.loan import Loan
from ..models.document import Document
from ..models.user import User
from ..models.fraud_alert import FraudAlert
from .auth import get_current_user
from ..utils.loan_calculator import calculate_loan
from ..utils.pdf_generator import generate_loan_agreement
from ..utils.audit import log_action
from ..utils.fraud_detection import FraudDetector, can_override_ai_decision, get_override_message
from ..config import settings

router = APIRouter(prefix="/loans", tags=["loans"])
templates = Jinja2Templates(directory="app/templates")


def require_role(current_user, allowed_roles):
    if current_user.role not in allowed_roles and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return True


@router.get("/", response_class=HTMLResponse)
def list_loans(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    loans = db.query(Loan).all()
    return templates.TemplateResponse("loans/list.html", {
        "request": request,
        "loans": loans,
        "user": current_user
    })


@router.get("/apply", response_class=HTMLResponse)
def apply_form(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["admin", "manager", "loan_officer"])
    customers = db.query(Customer).filter(Customer.is_blacklisted == False).all()
    return templates.TemplateResponse("loans/apply.html", {
        "request": request,
        "customers": customers,
        "user": current_user
    })


@router.post("/apply")
def create_loan(
    request: Request,
    customer_id: int = Form(...),
    amount: float = Form(...),
    term_months: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["admin", "manager", "loan_officer"])
    
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return RedirectResponse(url="/loans/apply?error=invalid_customer", status_code=303)
    
    if customer.is_blacklisted:
        return RedirectResponse(url="/loans/apply?error=blacklisted", status_code=303)

    active = db.query(Loan).filter(
        Loan.customer_id == customer_id,
        Loan.status.in_(["PENDING", "APPROVED", "DISBURSED", "ACTIVE"])
    ).first()
    if active:
        return RedirectResponse(url="/loans/apply?error=has_active_loan", status_code=303)

    # ============================================
    # AI FRAUD DETECTION
    # ============================================
    fraud_detector = FraudDetector(db)
    fraud_result = fraud_detector.detect_fraud(customer, amount, term_months)
    
    # Calculate loan details first
    calc = calculate_loan(amount, term_months, settings.INTEREST_RATE)
    
    # Create the loan first
    loan = Loan(
        customer_id=customer_id,
        amount=amount,
        term_months=term_months,
        interest_rate=settings.INTEREST_RATE,
        interest_amount=calc["interest_amount"],
        total_repayment=calc["total_repayment"],
        monthly_installment=calc["monthly_installment"],
        status="PENDING",
        balance_remaining=calc["total_repayment"]
    )
    db.add(loan)
    db.commit()
    db.refresh(loan)
    
    # Save fraud alert with loan_id
    fraud_alert = FraudAlert(
        customer_id=customer.id,
        loan_id=loan.id,
        risk_score=fraud_result["risk_score"],
        risk_level=fraud_result["risk_level"],
        ai_decision=fraud_result["ai_decision"],
        flags=json.dumps(fraud_result["flags"]),
        flag_count=fraud_result["flag_count"],
        is_overridden=False,
        final_status=None
    )
    db.add(fraud_alert)
    db.commit()
    db.refresh(fraud_alert)
    
    # Check if AI blocked the loan
    if fraud_result["ai_decision"] == "BLOCK":
        # Only Admin can override HIGH risk loans
        if current_user.role == "admin":
            # Admin can override - show the fraud blocked page with override option
            return templates.TemplateResponse("loans/fraud_blocked.html", {
                "request": request,
                "customer": customer,
                "loan": loan,
                "amount": amount,
                "term_months": term_months,
                "fraud_result": fraud_result,
                "user": current_user,
                "can_override": True
            })
        else:
            # Non-admin users cannot proceed - show blocked page without override
            return templates.TemplateResponse("loans/fraud_blocked.html", {
                "request": request,
                "customer": customer,
                "loan": loan,
                "amount": amount,
                "term_months": term_months,
                "fraud_result": fraud_result,
                "user": current_user,
                "can_override": False
            })
    
    # For MEDIUM risk, warn but allow (Manager can approve)
    if fraud_result["risk_level"] == "MEDIUM" and current_user.role not in ["admin", "manager"]:
        # Loan Officer cannot proceed with medium risk
        return templates.TemplateResponse("loans/fraud_review.html", {
            "request": request,
            "customer": customer,
            "loan": loan,
            "amount": amount,
            "term_months": term_months,
            "fraud_result": fraud_result,
            "user": current_user
        })

    # If we get here, loan is approved by AI (LOW risk or MEDIUM with proper role)
    log_action(db, current_user.id, current_user.username, "CREATE_LOAN", "loans", loan.id, ip_address=request.client.host)
    return RedirectResponse(url="/loans/", status_code=303)


@router.post("/{loan_id}/override-fraud")
def override_fraud(
    loan_id: int,
    request: Request,
    override_reason: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only Admin can override fraud blocks
    require_role(current_user, ["admin"])
    
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(404, "Loan not found")
    
    # Get fraud alert
    fraud_alert = db.query(FraudAlert).filter(FraudAlert.loan_id == loan_id).first()
    if not fraud_alert:
        raise HTTPException(404, "No fraud alert found for this loan")
    
    # Check if already overridden
    if fraud_alert.is_overridden:
        return RedirectResponse(url="/loans/?error=already_overridden", status_code=303)
    
    # Override the fraud decision
    fraud_alert.is_overridden = True
    fraud_alert.overridden_by = current_user.id
    fraud_alert.override_reason = override_reason
    fraud_alert.override_at = datetime.now()
    fraud_alert.final_status = "APPROVED"
    
    # Update loan status to APPROVED
    loan.status = "APPROVED"
    loan.approval_date = date.today()
    
    db.commit()
    
    # Log the override
    log_action(
        db, 
        current_user.id, 
        current_user.username, 
        "ADMIN_OVERRIDE_FRAUD", 
        "loans", 
        loan_id, 
        ip_address=request.client.host,
        old_value=f"AI BLOCKED - Risk Score: {fraud_alert.risk_score}%",
        new_value=f"ADMIN OVERRIDE - Reason: {override_reason}"
    )
    
    print(f"✅ Admin {current_user.username} overrode fraud block on loan {loan_id}")
    print(f"   Reason: {override_reason}")
    
    return RedirectResponse(url="/loans/", status_code=303)


@router.post("/{loan_id}/approve")
def approve_loan(
    loan_id: int, 
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["admin", "manager"])
    
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(404)
    if loan.status != "PENDING":
        return RedirectResponse(url="/loans/", status_code=303)

    # Update loan status
    loan.status = "APPROVED"
    loan.approval_date = date.today()
    db.commit()
    
    print(f"✅ Loan {loan_id} approved, generating PDF...")

    # Generate PDF agreement
    customer = db.query(Customer).filter(Customer.id == loan.customer_id).first()
    doc_id = None
    
    if customer:
        try:
            # Create uploads directory if it doesn't exist
            upload_dir = Path(settings.UPLOAD_DIR)
            upload_dir.mkdir(parents=True, exist_ok=True)
            print(f"📁 Upload directory: {upload_dir}")
            
            # Generate unique filename
            pdf_filename = f"agreement_loan_{loan_id}_{date.today()}.pdf"
            pdf_path = upload_dir / pdf_filename
            print(f"📄 PDF path: {pdf_path}")
            
            # Generate the PDF
            generate_loan_agreement(loan, customer, str(pdf_path))
            print(f"✅ PDF generated successfully!")
            
            # Check if file exists
            if pdf_path.exists():
                print(f"✅ File exists: {pdf_path}")
                print(f"📏 File size: {pdf_path.stat().st_size} bytes")
                
                # Store in documents table
                doc = Document(
                    customer_id=customer.id,
                    loan_id=loan.id,
                    file_name=f"Loan_Agreement_{loan_id}.pdf",
                    file_path=str(pdf_path),
                    file_type="agreement",
                    uploaded_by=current_user.id
                )
                db.add(doc)
                db.commit()
                db.refresh(doc)
                doc_id = doc.id
                print(f"✅ Document stored in database with ID: {doc.id}")
            else:
                print(f"❌ ERROR: PDF file was not created at {pdf_path}")
                
        except Exception as e:
            print(f"❌ PDF generation FAILED with error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"❌ Customer not found for loan {loan_id}")

    log_action(db, current_user.id, current_user.username, "APPROVE_LOAN", "loans", loan_id, ip_address=request.client.host)
    return RedirectResponse(url="/loans/", status_code=303)


@router.post("/{loan_id}/reject")
def reject_loan(
    loan_id: int, 
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["admin", "manager"])
    
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(404)
    if loan.status != "PENDING":
        return RedirectResponse(url="/loans/", status_code=303)
    loan.status = "REJECTED"
    db.commit()
    log_action(db, current_user.id, current_user.username, "REJECT_LOAN", "loans", loan_id, ip_address=request.client.host)
    return RedirectResponse(url="/loans/", status_code=303)


@router.post("/{loan_id}/disburse")
def disburse_loan(
    loan_id: int, 
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["admin", "manager"])
    
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(404)
    if loan.status != "APPROVED":
        return RedirectResponse(url="/loans/", status_code=303)
    loan.status = "DISBURSED"
    loan.disbursement_date = date.today()
    loan.next_due_date = date.today() + timedelta(days=30)
    db.commit()
    log_action(db, current_user.id, current_user.username, "DISBURSE_LOAN", "loans", loan_id, ip_address=request.client.host)
    return RedirectResponse(url="/loans/", status_code=303)