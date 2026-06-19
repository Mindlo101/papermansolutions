import os
import shutil
from fastapi import APIRouter, Request, Depends, File, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from ..database import get_db
from ..models.document import Document
from ..models.customer import Customer
from ..models.loan import Loan
from ..models.user import User
from .auth import get_current_user
from ..utils.audit import log_action
from ..config import settings

router = APIRouter(prefix="/documents", tags=["documents"])
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def require_role(current_user, allowed_roles):
    if current_user.role not in allowed_roles and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return True


@router.get("/upload", response_class=HTMLResponse)
def upload_form(
    request: Request, 
    customer_id: int = None, 
    loan_id: int = None, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # Admin, manager, and loan officers can upload documents
    require_role(current_user, ["admin", "manager", "loan_officer"])
    
    customers = db.query(Customer).all()
    loans = db.query(Loan).all()
    return templates.TemplateResponse("documents/upload.html", {
        "request": request,
        "customers": customers,
        "loans": loans,
        "selected_customer": customer_id,
        "selected_loan": loan_id,
        "user": current_user
    })


@router.post("/upload")
async def upload_document(
    request: Request,
    customer_id: int = Form(...),
    loan_id: str = Form(""),  # Changed to string to handle empty value
    file_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Admin, manager, and loan officers can upload documents
    require_role(current_user, ["admin", "manager", "loan_officer"])
    
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Customer not found")

    # Convert loan_id to int or None
    loan_id_value = None
    if loan_id and loan_id.strip():
        try:
            loan_id_value = int(loan_id)
        except ValueError:
            loan_id_value = None
    
    # Only validate loan_id if it has a value
    if loan_id_value:
        loan = db.query(Loan).filter(Loan.id == loan_id_value, Loan.customer_id == customer_id).first()
        if not loan:
            raise HTTPException(404, "Loan not found for this customer")

    original_name = file.filename
    safe_name = f"{customer_id}_{file_type}_{original_name}"
    file_path = UPLOAD_DIR / safe_name

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc = Document(
        customer_id=customer_id,
        loan_id=loan_id_value,
        file_name=original_name,
        file_path=str(file_path),
        file_type=file_type,
        uploaded_by=current_user.id
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_action(db, current_user.id, current_user.username, "UPLOAD_DOCUMENT", "documents", doc.id, ip_address=request.client.host)
    return RedirectResponse(url=f"/customers/{customer_id}", status_code=303)


@router.get("/download/{doc_id}")
def download_document(
    doc_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    # All roles can download documents
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not os.path.exists(doc.file_path):
        raise HTTPException(404, "File not found on server")
    return FileResponse(doc.file_path, filename=doc.file_name)