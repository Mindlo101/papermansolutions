from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.customer import Customer
from ..models.loan import Loan
from ..models.fraud_alert import FraudAlert
from ..models.user import User
from .auth import get_current_user

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Only count active customers (not deleted)
    total_customers = db.query(Customer).filter(Customer.deleted_at.is_(None)).count()
    
    # Only count loans from active customers
    total_loans = db.query(Loan).join(Customer).filter(Customer.deleted_at.is_(None)).count()
    
    # Count APPROVED, DISBURSED, and ACTIVE as "approved" loans - only from active customers
    approved_loans = db.query(Loan).join(Customer).filter(
        Customer.deleted_at.is_(None),
        Loan.status.in_(["APPROVED", "DISBURSED", "ACTIVE"])
    ).count()
    
    pending_loans = db.query(Loan).join(Customer).filter(
        Customer.deleted_at.is_(None),
        Loan.status == "PENDING"
    ).count()
    
    rejected_loans = db.query(Loan).join(Customer).filter(
        Customer.deleted_at.is_(None),
        Loan.status == "REJECTED"
    ).count()
    
    disbursed_loans = db.query(Loan).join(Customer).filter(
        Customer.deleted_at.is_(None),
        Loan.status == "DISBURSED"
    ).count()
    
    completed_loans = db.query(Loan).join(Customer).filter(
        Customer.deleted_at.is_(None),
        Loan.status == "COMPLETED"
    ).count()
    
    defaulted_loans = db.query(Loan).join(Customer).filter(
        Customer.deleted_at.is_(None),
        Loan.status == "DEFAULTED"
    ).count()

    # Get all active customers (not deleted)
    customers = db.query(Customer).filter(Customer.deleted_at.is_(None)).all()
    
    # Get all loans from active customers
    loans = db.query(Loan).join(Customer).filter(Customer.deleted_at.is_(None)).all()

    # Calculate total portfolio value (only from active customers)
    total_portfolio = db.query(Loan).join(Customer).filter(
        Customer.deleted_at.is_(None)
    ).with_entities(Loan.amount).all()
    total_portfolio_value = sum([loan.amount for loan in total_portfolio]) if total_portfolio else 0

    # Recent loans (last 5) from active customers
    recent_loans = db.query(Loan).join(Customer).filter(
        Customer.deleted_at.is_(None)
    ).order_by(Loan.id.desc()).limit(5).all()

    # ============================================
    # FRAUD STATS
    # ============================================
    fraud_alerts = db.query(FraudAlert).all()
    total_fraud_checks = len(fraud_alerts)
    high_risk_checks = len([f for f in fraud_alerts if f.risk_level == "HIGH"])
    medium_risk_checks = len([f for f in fraud_alerts if f.risk_level == "MEDIUM"])
    low_risk_checks = len([f for f in fraud_alerts if f.risk_level == "LOW"])
    overridden_checks = len([f for f in fraud_alerts if f.is_overridden])
    blocked_by_ai = len([f for f in fraud_alerts if f.ai_decision == "BLOCK" and not f.is_overridden])
    
    # Recent fraud alerts (last 5)
    recent_fraud_alerts = db.query(FraudAlert).order_by(FraudAlert.id.desc()).limit(5).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_customers": total_customers,
        "total_loans": total_loans,
        "approved_loans": approved_loans,
        "pending_loans": pending_loans,
        "rejected_loans": rejected_loans,
        "disbursed_loans": disbursed_loans,
        "completed_loans": completed_loans,
        "defaulted_loans": defaulted_loans,
        "total_portfolio_value": total_portfolio_value,
        "customers": customers,
        "loans": loans,
        "recent_loans": recent_loans,
        "user": current_user,
        # Fraud stats
        "total_fraud_checks": total_fraud_checks,
        "high_risk_checks": high_risk_checks,
        "medium_risk_checks": medium_risk_checks,
        "low_risk_checks": low_risk_checks,
        "overridden_checks": overridden_checks,
        "blocked_by_ai": blocked_by_ai,
        "recent_fraud_alerts": recent_fraud_alerts
    })