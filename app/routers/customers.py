from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from ..database import get_db
from ..models.customer import Customer
from ..models.loan import Loan
from ..models.user import User
from .auth import get_current_user
from ..utils.audit import log_action

router = APIRouter(prefix="/customers", tags=["customers"])
templates = Jinja2Templates(directory="app/templates")


def require_role(current_user, allowed_roles):
    if current_user.role not in allowed_roles and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return True


@router.get("/", response_class=HTMLResponse)
def list_customers(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Only show active customers (not deleted)
    customers = db.query(Customer).filter(Customer.deleted_at.is_(None)).all()
    
    # Get loan status for each customer to determine delete permissions
    customer_data = []
    for customer in customers:
        loans = db.query(Loan).filter(Loan.customer_id == customer.id).all()
        has_approved = any(l.status == "APPROVED" for l in loans)
        has_disbursed = any(l.status == "DISBURSED" for l in loans)
        has_completed = any(l.status == "COMPLETED" for l in loans)
        has_pending = any(l.status == "PENDING" for l in loans)
        has_rejected = any(l.status == "REJECTED" for l in loans)
        has_defaulted = any(l.status == "DEFAULTED" for l in loans)
        
        customer_data.append({
            "customer": customer,
            "has_approved": has_approved,
            "has_disbursed": has_disbursed,
            "has_completed": has_completed,
            "has_pending": has_pending,
            "has_rejected": has_rejected,
            "has_defaulted": has_defaulted,
            "loan_count": len(loans)
        })
    
    # Count items in recycle bin
    trash_count = db.query(Customer).filter(Customer.deleted_at.isnot(None)).count()
    
    return templates.TemplateResponse("customers/list.html", {
        "request": request,
        "customer_data": customer_data,
        "trash_count": trash_count,
        "user": current_user
    })


@router.get("/trash", response_class=HTMLResponse)
def trash_view(
    request: Request, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Only Admin and Manager can view trash
    require_role(current_user, ["admin", "manager"])
    
    # Get all soft-deleted customers
    deleted_customers = db.query(Customer).filter(Customer.deleted_at.isnot(None)).all()
    
    return templates.TemplateResponse("customers/trash.html", {
        "request": request,
        "deleted_customers": deleted_customers,
        "user": current_user,
        "now": datetime.now()
    })


@router.post("/{customer_id}/restore")
def restore_customer(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only Admin and Manager can restore
    require_role(current_user, ["admin", "manager"])
    
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    
    if customer.deleted_at is None:
        return RedirectResponse(url="/customers/trash?error=already_active", status_code=303)
    
    # Restore the customer
    customer.deleted_at = None
    customer.deleted_by = None
    db.commit()
    
    log_action(db, current_user.id, current_user.username, "RESTORE_CUSTOMER", "customers", customer_id, ip_address=request.client.host)
    return RedirectResponse(url="/customers/trash?success=restored", status_code=303)


@router.post("/trash/empty")
def empty_trash(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only Admin can empty trash
    require_role(current_user, ["admin"])
    
    # Get all deleted customers older than 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)
    old_deleted = db.query(Customer).filter(
        Customer.deleted_at.isnot(None),
        Customer.deleted_at < thirty_days_ago
    ).all()
    
    count = len(old_deleted)
    for customer in old_deleted:
        db.delete(customer)
    db.commit()
    
    log_action(db, current_user.id, current_user.username, "EMPTY_TRASH", "customers", 0, ip_address=request.client.host, old_value=f"Deleted {count} customers")
    return RedirectResponse(url="/customers/trash?success=trash_emptied", status_code=303)


@router.get("/add", response_class=HTMLResponse)
def add_customer_form(
    request: Request, 
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["admin", "manager", "loan_officer"])
    return templates.TemplateResponse("customers/add.html", {
        "request": request, 
        "user": current_user,
        "error": None
    })


@router.post("/add")
def create_customer(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    id_number: str = Form(...),
    phone: str = Form(...),
    email: str = Form(None),
    address: str = Form(None),
    employer: str = Form(None),
    monthly_income: float = Form(0.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["admin", "manager", "loan_officer"])
    
    # Check if ID number already exists (including deleted customers)
    existing = db.query(Customer).filter(
        func.lower(Customer.id_number) == func.lower(id_number)
    ).first()
    
    if existing:
        if existing.deleted_at is not None:
            # Customer is in trash, restore them instead
            existing.deleted_at = None
            existing.deleted_by = None
            # Update details
            existing.first_name = first_name
            existing.last_name = last_name
            existing.phone = phone
            existing.email = email
            existing.address = address
            existing.employer = employer
            existing.monthly_income = monthly_income
            db.commit()
            log_action(db, current_user.id, current_user.username, "RESTORE_CUSTOMER", "customers", existing.id, ip_address=request.client.host)
            return RedirectResponse(url="/customers/", status_code=303)
        else:
            return templates.TemplateResponse("customers/add.html", {
                "request": request,
                "user": current_user,
                "error": f"ID Number '{id_number}' already exists for customer: {existing.first_name} {existing.last_name}",
                "first_name": first_name,
                "last_name": last_name,
                "id_number": id_number,
                "phone": phone,
                "email": email,
                "address": address,
                "employer": employer,
                "monthly_income": monthly_income
            })
    
    customer = Customer(
        first_name=first_name,
        last_name=last_name,
        id_number=id_number,
        phone=phone,
        email=email,
        address=address,
        employer=employer,
        monthly_income=monthly_income
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    log_action(db, current_user.id, current_user.username, "CREATE_CUSTOMER", "customers", customer.id, ip_address=request.client.host)
    return RedirectResponse(url="/customers/", status_code=303)


@router.get("/{customer_id}", response_class=HTMLResponse)
def view_customer(
    request: Request, 
    customer_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.deleted_at.is_(None)).first()
    if not customer:
        raise HTTPException(status_code=404)
    loans = db.query(Loan).filter(Loan.customer_id == customer_id).all()
    return templates.TemplateResponse("customers/details.html", {
        "request": request,
        "customer": customer,
        "loans": loans,
        "user": current_user
    })


@router.get("/{customer_id}/edit", response_class=HTMLResponse)
def edit_customer_form(
    request: Request,
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["admin", "manager", "loan_officer"])
    
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.deleted_at.is_(None)).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    
    return templates.TemplateResponse("customers/edit.html", {
        "request": request,
        "customer": customer,
        "user": current_user,
        "error": None
    })


@router.post("/{customer_id}/edit")
def update_customer(
    request: Request,
    customer_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    id_number: str = Form(...),
    phone: str = Form(...),
    email: str = Form(None),
    address: str = Form(None),
    employer: str = Form(None),
    monthly_income: float = Form(0.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_role(current_user, ["admin", "manager", "loan_officer"])
    
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.deleted_at.is_(None)).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    
    # Check if ID number already exists for a DIFFERENT customer
    existing = db.query(Customer).filter(
        func.lower(Customer.id_number) == func.lower(id_number),
        Customer.id != customer_id
    ).first()
    
    if existing:
        return templates.TemplateResponse("customers/edit.html", {
            "request": request,
            "customer": customer,
            "user": current_user,
            "error": f"ID Number '{id_number}' already exists for customer: {existing.first_name} {existing.last_name}"
        })
    
    # Update customer details
    customer.first_name = first_name
    customer.last_name = last_name
    customer.id_number = id_number
    customer.phone = phone
    customer.email = email
    customer.address = address
    customer.employer = employer
    customer.monthly_income = monthly_income
    
    db.commit()
    
    log_action(db, current_user.id, current_user.username, "UPDATE_CUSTOMER", "customers", customer_id, ip_address=request.client.host)
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@router.post("/{customer_id}/delete")
def delete_customer(
    customer_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.deleted_at.is_(None)).first()
    if not customer:
        raise HTTPException(404, "Customer not found")
    
    # Get all loans for this customer
    loans = db.query(Loan).filter(Loan.customer_id == customer_id).all()
    
    # Check permissions based on role
    can_delete = False
    reason = ""
    
    if current_user.role == "admin":
        can_delete = True
        reason = "Admin override"
        
    elif current_user.role == "manager":
        has_approved = any(l.status == "APPROVED" for l in loans)
        has_disbursed = any(l.status == "DISBURSED" for l in loans)
        has_completed = any(l.status == "COMPLETED" for l in loans)
        has_defaulted = any(l.status == "DEFAULTED" for l in loans)
        
        if has_approved or has_disbursed or has_completed or has_defaulted:
            can_delete = True
            reason = "Customer has approved/disbursed/completed/defaulted loans"
        elif loans:
            return RedirectResponse(
                url=f"/customers/?error=manager_cannot_delete_pending_only",
                status_code=303
            )
        else:
            can_delete = True
            reason = "No loans found"
            
    elif current_user.role == "loan_officer":
        has_approved = any(l.status == "APPROVED" for l in loans)
        has_disbursed = any(l.status == "DISBURSED" for l in loans)
        has_completed = any(l.status == "COMPLETED" for l in loans)
        has_defaulted = any(l.status == "DEFAULTED" for l in loans)
        
        if has_approved or has_disbursed or has_completed or has_defaulted:
            return RedirectResponse(
                url=f"/customers/?error=officer_cannot_delete_approved",
                status_code=303
            )
        else:
            can_delete = True
            reason = "Only pending/rejected loans or no loans"
    
    if not can_delete:
        return RedirectResponse(
            url=f"/customers/?error=permission_denied",
            status_code=303
        )
    
    # Soft delete - move to recycle bin
    customer.deleted_at = datetime.now()
    customer.deleted_by = current_user.id
    db.commit()
    
    log_action(db, current_user.id, current_user.username, "DELETE_CUSTOMER", "customers", customer_id, ip_address=request.client.host, old_value=reason)
    
    return RedirectResponse(url="/customers/?success=customer_deleted", status_code=303)