from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..database import get_db
from ..models.loan import Loan
from ..models.payment import Payment
from ..models.user import User
from .auth import get_current_user
from ..utils.audit import log_action

router = APIRouter(prefix="/payments", tags=["payments"])
templates = Jinja2Templates(directory="app/templates")


def require_role(current_user, allowed_roles):
    if current_user.role not in allowed_roles and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return True


@router.get("/record", response_class=HTMLResponse)
def record_payment_form(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Admin, manager, and loan officers can record payments
    require_role(current_user, ["admin", "manager", "loan_officer"])
    
    loans = db.query(Loan).filter(
        Loan.status.in_(["DISBURSED", "ACTIVE"]),
        Loan.balance_remaining > 0
    ).all()
    
    return templates.TemplateResponse("payments/record.html", {
        "request": request,
        "loans": loans,
        "user": current_user
    })


@router.post("/record")
def record_payment(
    request: Request,
    loan_id: int = Form(...),
    amount_paid: float = Form(...),
    payment_date: str = Form(...),
    method: str = Form("cash"),
    reference: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Admin, manager, and loan officers can record payments
    require_role(current_user, ["admin", "manager", "loan_officer"])
    
    pay_date = datetime.strptime(payment_date, "%Y-%m-%d").date()
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(404, "Loan not found")
    
    if loan.balance_remaining <= 0:
        return RedirectResponse(url="/payments/record?error=already_paid", status_code=303)

    new_balance = loan.balance_remaining - amount_paid
    if new_balance < 0:
        new_balance = 0

    payment = Payment(
        loan_id=loan_id,
        amount_paid=amount_paid,
        payment_date=pay_date,
        method=method,
        reference=reference,
        remaining_balance_after=new_balance
    )
    db.add(payment)
    loan.balance_remaining = new_balance

    if new_balance <= 0:
        loan.status = "COMPLETED"
    else:
        if loan.status == "DISBURSED":
            loan.status = "ACTIVE"
        loan.next_due_date = pay_date + timedelta(days=30)

    db.commit()
    log_action(db, current_user.id, current_user.username, "RECORD_PAYMENT", "payments", payment.id, ip_address=request.client.host)
    return RedirectResponse(url="/loans/", status_code=303)