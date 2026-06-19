@router.post("/upload")
async def upload_document(
    request: Request,
    customer_id: int = Form(...),
    loan_id: int = Form(None),  # This should work if empty
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

    # Only validate loan_id if it has a value
    if loan_id and loan_id > 0:
        loan = db.query(Loan).filter(Loan.id == loan_id, Loan.customer_id == customer_id).first()
        if not loan:
            raise HTTPException(404, "Loan not found for this customer")
    else:
        loan_id = None  # Set to None if empty or 0

    original_name = file.filename
    safe_name = f"{customer_id}_{file_type}_{original_name}"
    file_path = UPLOAD_DIR / safe_name

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    doc = Document(
        customer_id=customer_id,
        loan_id=loan_id,
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