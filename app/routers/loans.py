from fastapi import APIRouter, Request, Depends, Form, HTTPException, File, UploadFile
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
    customers = db.query(Customer).filter(Customer.is_blacklisted == False, Customer.deleted_at.is_(None)).all()
    return templates.TemplateResponse("loans/apply.html", {
        "request": request,
        "customers": customers,
        "user": current_user,
        "term_months": 1
    })


@router.post("/apply")
async def create_loan(
    request: Request,
    customer_id: int = Form(...),
    amount: float = Form(...),
    term_months: int = Form(1),
    id_copy: UploadFile = File(...),
    proof_income: UploadFile = File(...),
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
    # SAVE UPLOADED DOCUMENTS
    # ============================================
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Save ID Copy
    id_copy_filename = f"{customer_id}_id_copy_{id_copy.filename}"
    id_copy_path = upload_dir / id_copy_filename
    with open(id_copy_path, "wb") as buffer:
        content = await id_copy.read()
        buffer.write(content)
    
    # Save Proof of Income
    proof_filename = f"{customer_id}_proof_income_{proof_income.filename}"
    proof_path = upload_dir / proof_filename
    with open(proof_path, "wb") as buffer:
        content = await proof_income.read()
        buffer.write(content)
    
    # Store ID Copy in documents table
    id_doc = Document(
        customer_id=customer.id,
        loan_id=None,
        file_name=id_copy.filename,
        file_path=str(id_copy_path),
        file_type="id_copy",
        uploaded_by=current_user.id
    )
    db.add(id_doc)
    
    # Store Proof of Income in documents table
    proof_doc = Document(
        customer_id=customer.id,
        loan_id=None,
        file_name=proof_income.filename,
        file_path=str(proof_path),
        file_type="proof_income",
        uploaded_by=current_user.id
    )
    db.add(proof_doc)
    db.commit()

    # ============================================
    # AI FRAUD DETECTION
    # ============================================
    fraud_detector = FraudDetector(db)
    fraud_result = fraud_detector.detect_fraud(customer, amount, term_months)
    
    # Calculate loan details
    calc = calculate_loan(amount, term_months, settings.INTEREST_RATE)
    
    # Create the loan
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
    
    # Update documents with loan_id
    id_doc.loan_id = loan.id
    proof_doc.loan_id = loan.id
    db.commit()
    
    # Check if AI blocked the loan
    if fraud_result["ai_decision"] == "BLOCK":
        if current_user.role == "admin":
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
        return templates.TemplateResponse("loans/fraud_review.html", {
            "request": request,
            "customer": customer,
            "loan": loan,
            "amount": amount,
            "term_months": term_months,
            "fraud_result": fraud_result,
            "user": current_user
        })

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
    require_role(current_user, ["admin"])
    
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(404, "Loan not found")
    
    fraud_alert = db.query(FraudAlert).filter(FraudAlert.loan_id == loan_id).first()
    if not fraud_alert:
        raise HTTPException(404, "No fraud alert found for this loan")
    
    if fraud_alert.is_overridden:
        return RedirectResponse(url="/loans/?error=already_overridden", status_code=303)
    
    fraud_alert.is_overridden = True
    fraud_alert.overridden_by = current_user.id
    fraud_alert.override_reason = override_reason
    fraud_alert.override_at = datetime.now()
    fraud_alert.final_status = "APPROVED"
    
    loan.status = "APPROVED"
    loan.approval_date = date.today()
    
    db.commit()
    
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
    
    return RedirectResponse(url="/loans/", status_code=303)


# ============================================
# LOAN REVIEW ROUTES
# ============================================

@router.get("/{loan_id}/review", response_class=HTMLResponse)
def review_loan(
    loan_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only Admin and Manager can review
    require_role(current_user, ["admin", "manager"])
    
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(404, "Loan not found")
    
    customer = db.query(Customer).filter(Customer.id == loan.customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    
    # Get fraud alert
    fraud_alert = db.query(FraudAlert).filter(FraudAlert.loan_id == loan_id).first()
    
    # Safely parse flags
    flags = []
    if fraud_alert and fraud_alert.flags:
        try:
            flags = json.loads(fraud_alert.flags)
        except (json.JSONDecodeError, TypeError):
            flags = []
    
    fraud_result = {
        "risk_score": fraud_alert.risk_score if fraud_alert else 0,
        "risk_level": fraud_alert.risk_level if fraud_alert else "UNKNOWN",
        "ai_decision": fraud_alert.ai_decision if fraud_alert else "UNKNOWN",
        "flags": flags,
        "flag_count": fraud_alert.flag_count if fraud_alert else 0
    }
    
    # Get loan counts for stats
    total_loans = db.query(Loan).count()
    customer_loan_count = db.query(Loan).filter(Loan.customer_id == customer.id).count()
    active_loan_count = db.query(Loan).filter(
        Loan.customer_id == customer.id,
        Loan.status.in_(["PENDING", "APPROVED", "DISBURSED", "ACTIVE"])
    ).count()
    
    return templates.TemplateResponse("loans/review.html", {
        "request": request,
        "loan": loan,
        "customer": customer,
        "fraud_result": fraud_result,
        "total_loans": total_loans,
        "customer_loan_count": customer_loan_count,
        "active_loan_count": active_loan_count,
        "user": current_user
    })


@router.post("/{loan_id}/review-approve")
def review_approve_loan(
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
    
    # Generate PDF agreement
    customer = db.query(Customer).filter(Customer.id == loan.customer_id).first()
    if customer:
        try:
            upload_dir = Path(settings.UPLOAD_DIR)
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            pdf_filename = f"agreement_loan_{loan_id}_{date.today()}.pdf"
            pdf_path = upload_dir / pdf_filename
            
            generate_loan_agreement(loan, customer, str(pdf_path))
            
            if pdf_path.exists():
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
                print(f"✅ Document stored in database with ID: {doc.id}")
        except Exception as e:
            print(f"❌ PDF generation error: {e}")
    
    log_action(db, current_user.id, current_user.username, "APPROVE_LOAN", "loans", loan_id, ip_address=request.client.host, new_value="Approved from review page")
    return RedirectResponse(url="/loans/", status_code=303)


@router.post("/{loan_id}/review-reject")
def review_reject_loan(
    loan_id: int,
    request: Request,
    rejection_reason: str = Form(None),
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
    
    reason = rejection_reason if rejection_reason else "No reason provided"
    log_action(db, current_user.id, current_user.username, "REJECT_LOAN", "loans", loan_id, ip_address=request.client.host, new_value=f"Rejected from review page. Reason: {reason}")
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

    # ============================================
    # CHECK: Required documents uploaded
    # ============================================
    customer = db.query(Customer).filter(Customer.id == loan.customer_id).first()
    
    # Check if customer has uploaded required documents
    required_docs = ["id_copy", "proof_income"]
    uploaded_docs = db.query(Document).filter(
        Document.customer_id == customer.id,
        Document.file_type.in_(required_docs)
    ).all()
    
    uploaded_types = [doc.file_type for doc in uploaded_docs]
    missing_docs = [doc for doc in required_docs if doc not in uploaded_types]
    
    if missing_docs:
        doc_names = {
            "id_copy": "ID Copy",
            "proof_income": "Proof of Income"
        }
        missing_names = [doc_names.get(doc, doc) for doc in missing_docs]
        missing_message = ", ".join(missing_names)
        
        return templates.TemplateResponse("loans/missing_documents.html", {
            "request": request,
            "loan": loan,
            "customer": customer,
            "missing_docs": missing_docs,
            "missing_message": missing_message,
            "user": current_user
        })

    # Update loan status
    loan.status = "APPROVED"
    loan.approval_date = date.today()
    db.commit()
    
    print(f"✅ Loan {loan_id} approved, generating PDF...")

    # Generate PDF agreement
    doc_id = None
    
    if customer:
        try:
            upload_dir = Path(settings.UPLOAD_DIR)
            upload_dir.mkdir(parents=True, exist_ok=True)
            
            pdf_filename = f"agreement_loan_{loan_id}_{date.today()}.pdf"
            pdf_path = upload_dir / pdf_filename
            
            generate_loan_agreement(loan, customer, str(pdf_path))
            
            if pdf_path.exists():
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