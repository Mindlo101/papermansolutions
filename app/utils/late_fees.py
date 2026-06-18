from datetime import date, timedelta
from sqlalchemy.orm import Session
from ..models.loan import Loan
from ..models.payment import Payment
from ..models.blacklist import Blacklist
from ..models.customer import Customer
from ..config import settings


def calculate_late_fee(overdue_amount: float, days_late: int, penalty_percent_per_week: float = None):
    """
    Calculate late fee based on overdue amount and days late.
    """
    if penalty_percent_per_week is None:
        penalty_percent_per_week = settings.LATE_FEE_PERCENT
    
    if days_late <= 0 or overdue_amount <= 0:
        return 0.0
    
    # Calculate weeks late (ceil)
    weeks_late = (days_late + 6) // 7
    fee = overdue_amount * (penalty_percent_per_week / 100) * weeks_late
    return round(fee, 2)


def apply_late_fees(db: Session):
    """
    Apply late fees to all overdue loans.
    Returns: dict with stats (loans_updated, total_fees_applied)
    """
    today = date.today()
    loans_updated = 0
    total_fees = 0.0
    
    # Find all loans that are ACTIVE or DISBURSED with balance > 0
    overdue_loans = db.query(Loan).filter(
        Loan.status.in_(["ACTIVE", "DISBURSED"]),
        Loan.balance_remaining > 0,
        Loan.next_due_date < today
    ).all()
    
    for loan in overdue_loans:
        days_late = (today - loan.next_due_date).days
        fee = calculate_late_fee(loan.balance_remaining, days_late)
        
        if fee > 0:
            # Add fee to balance
            loan.balance_remaining += fee
            
            # Record the late fee as a negative payment for audit
            payment = Payment(
                loan_id=loan.id,
                amount_paid=0,  # 0 means fee, not actual payment
                payment_date=today,
                method="late_fee",
                reference=f"Late fee: {days_late} days overdue",
                remaining_balance_after=loan.balance_remaining
            )
            db.add(payment)
            
            loans_updated += 1
            total_fees += fee
    
    if loans_updated > 0:
        db.commit()
    
    return {
        "loans_updated": loans_updated,
        "total_fees_applied": round(total_fees, 2)
    }


def mark_defaulted_loans(db: Session, days_to_default: int = 90):
    """
    Mark loans as DEFAULTED if they've been overdue for too long.
    Also blacklists the customer.
    """
    today = date.today()
    cutoff_date = today - timedelta(days=days_to_default)
    
    # Find loans that are ACTIVE or DISBURSED and overdue past cutoff
    defaulted_loans = db.query(Loan).filter(
        Loan.status.in_(["ACTIVE", "DISBURSED"]),
        Loan.balance_remaining > 0,
        Loan.next_due_date < cutoff_date
    ).all()
    
    updated = 0
    blacklisted_count = 0
    
    for loan in defaulted_loans:
        loan.status = "DEFAULTED"
        updated += 1
        
        # Blacklist the customer
        existing_blacklist = db.query(Blacklist).filter(Blacklist.customer_id == loan.customer_id).first()
        if not existing_blacklist:
            blacklist = Blacklist(
                customer_id=loan.customer_id,
                reason=f"Loan #{loan.id} defaulted after {days_to_default} days overdue",
                blacklisted_by=1  # System user
            )
            db.add(blacklist)
            
            # Update customer blacklist flag
            customer = db.query(Customer).filter(Customer.id == loan.customer_id).first()
            if customer:
                customer.is_blacklisted = True
            blacklisted_count += 1
    
    if updated > 0:
        db.commit()
    
    return {
        "loans_defaulted": updated,
        "customers_blacklisted": blacklisted_count
    }