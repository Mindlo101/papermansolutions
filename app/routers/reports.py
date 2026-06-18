from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date, timedelta
from ..database import get_db
from ..models.customer import Customer
from ..models.loan import Loan
from ..models.payment import Payment
from ..models.user import User
from .auth import get_current_user
from ..utils.late_fees import apply_late_fees, mark_defaulted_loans

router = APIRouter(prefix="/reports", tags=["reports"])
templates = Jinja2Templates(directory="app/templates")


def require_role(current_user, allowed_roles):
    if current_user.role not in allowed_roles and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return True


@router.get("/", response_class=HTMLResponse)
def reports_index(
    request: Request, 
    current_user: User = Depends(get_current_user)
):
    # All roles can view reports index
    return templates.TemplateResponse("reports/index.html", {
        "request": request,
        "user": current_user
    })


@router.get("/aging", response_class=HTMLResponse)
def aging_report(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # All roles can view reports
    today = date.today()
    
    # Apply late fees first
    fee_results = apply_late_fees(db)
    
    # Mark defaulted loans (90+ days overdue)
    default_results = mark_defaulted_loans(db)
    if default_results["loans_defaulted"] > 0:
        print(f"✅ Marked {default_results['loans_defaulted']} loans as defaulted")
        print(f"✅ Blacklisted {default_results['customers_blacklisted']} customers")
    
    # Get all loans with balance > 0
    active_loans = db.query(Loan).filter(
        Loan.status.in_(["ACTIVE", "DISBURSED"]),
        Loan.balance_remaining > 0
    ).all()
    
    # Categorize by days overdue
    aging_data = {
        "current": [],
        "days_31_60": [],
        "days_61_90": [],
        "days_90_plus": [],
        "totals": {
            "current": 0,
            "days_31_60": 0,
            "days_61_90": 0,
            "days_90_plus": 0
        }
    }
    
    for loan in active_loans:
        if loan.next_due_date:
            days_late = (today - loan.next_due_date).days
        else:
            days_late = 0
        
        customer = db.query(Customer).filter(Customer.id == loan.customer_id).first()
        customer_name = f"{customer.first_name} {customer.last_name}" if customer else "Unknown"
        
        loan_data = {
            "id": loan.id,
            "customer_id": loan.customer_id,
            "customer_name": customer_name,
            "amount": loan.amount,
            "balance": loan.balance_remaining,
            "next_due_date": loan.next_due_date,
            "days_late": max(0, days_late),
            "status": loan.status
        }
        
        if days_late <= 0:
            aging_data["current"].append(loan_data)
            aging_data["totals"]["current"] += loan.balance_remaining
        elif days_late <= 30:
            aging_data["current"].append(loan_data)
            aging_data["totals"]["current"] += loan.balance_remaining
        elif days_late <= 60:
            aging_data["days_31_60"].append(loan_data)
            aging_data["totals"]["days_31_60"] += loan.balance_remaining
        elif days_late <= 90:
            aging_data["days_61_90"].append(loan_data)
            aging_data["totals"]["days_61_90"] += loan.balance_remaining
        else:
            aging_data["days_90_plus"].append(loan_data)
            aging_data["totals"]["days_90_plus"] += loan.balance_remaining
    
    total_outstanding = sum(aging_data["totals"].values())
    
    return templates.TemplateResponse("reports/aging.html", {
        "request": request,
        "aging_data": aging_data,
        "total_outstanding": total_outstanding,
        "fee_results": fee_results,
        "default_results": default_results,
        "user": current_user
    })


@router.get("/daily-cash", response_class=HTMLResponse)
def daily_cash_report(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # All roles can view reports
    today = date.today()
    
    today_payments = db.query(Payment).filter(
        Payment.payment_date == today,
        Payment.method != "late_fee"
    ).all()
    
    total_collected = sum(payment.amount_paid for payment in today_payments)
    
    fee_payments = db.query(Payment).filter(
        Payment.payment_date == today,
        Payment.method == "late_fee"
    ).all()
    total_fees = len(fee_payments)
    
    return templates.TemplateResponse("reports/daily_cash.html", {
        "request": request,
        "today": today,
        "payments": today_payments,
        "total_collected": total_collected,
        "total_fees": total_fees,
        "user": current_user
    })


@router.get("/loan-register", response_class=HTMLResponse)
def loan_register(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # All roles can view reports
    loans = db.query(Loan).all()
    
    loan_data = []
    for loan in loans:
        customer = db.query(Customer).filter(Customer.id == loan.customer_id).first()
        customer_name = f"{customer.first_name} {customer.last_name}" if customer else "Unknown"
        
        loan_data.append({
            "id": loan.id,
            "customer_id": loan.customer_id,
            "customer_name": customer_name,
            "amount": loan.amount,
            "interest_amount": loan.interest_amount,
            "total_repayment": loan.total_repayment,
            "monthly_installment": loan.monthly_installment,
            "status": loan.status,
            "balance_remaining": loan.balance_remaining,
            "approval_date": loan.approval_date,
            "disbursement_date": loan.disbursement_date,
            "next_due_date": loan.next_due_date,
            "created_at": loan.created_at
        })
    
    total_loans = len(loan_data)
    total_amount = sum(l["amount"] for l in loan_data)
    total_interest = sum(l["interest_amount"] for l in loan_data)
    total_repayment = sum(l["total_repayment"] for l in loan_data)
    total_outstanding = sum(l["balance_remaining"] for l in loan_data)
    
    status_counts = {}
    for loan in loan_data:
        status = loan["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    return templates.TemplateResponse("reports/loan_register.html", {
        "request": request,
        "loans": loan_data,
        "total_loans": total_loans,
        "total_amount": total_amount,
        "total_interest": total_interest,
        "total_repayment": total_repayment,
        "total_outstanding": total_outstanding,
        "status_counts": status_counts,
        "user": current_user
    })