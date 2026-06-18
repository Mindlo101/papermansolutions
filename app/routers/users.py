from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from ..database import get_db
from ..models.user import User
from .auth import get_current_user
from ..utils.audit import log_action

router = APIRouter(prefix="/users", tags=["users"])
templates = Jinja2Templates(directory="app/templates")
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# Permission check function
def require_role(current_user, allowed_roles):
    if current_user.role not in allowed_roles and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return True


@router.get("/", response_class=HTMLResponse)
def list_users(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Only admin can view users
    require_role(current_user, ["admin"])
    
    users = db.query(User).all()
    return templates.TemplateResponse("users/list.html", {
        "request": request,
        "users": users,
        "user": current_user
    })


@router.get("/create", response_class=HTMLResponse)
def create_user_form(request: Request, current_user: User = Depends(get_current_user)):
    # Only admin can create users
    require_role(current_user, ["admin"])
    return templates.TemplateResponse("users/create.html", {
        "request": request,
        "user": current_user
    })


@router.post("/create")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only admin can create users
    require_role(current_user, ["admin"])
    
    # Check if username already exists
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return templates.TemplateResponse("users/create.html", {
            "request": request,
            "error": "Username already exists",
            "user": current_user
        })
    
    # Create new user
    hashed = hash_password(password)
    new_user = User(
        username=username,
        hashed_password=hashed,
        full_name=full_name,
        role=role,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    
    log_action(db, current_user.id, current_user.username, "CREATE_USER", "users", new_user.id)
    return RedirectResponse(url="/users/", status_code=303)


@router.post("/{user_id}/toggle-status")
def toggle_user_status(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only admin can toggle user status
    require_role(current_user, ["admin"])
    
    if user_id == current_user.id:
        return RedirectResponse(url="/users/?error=cannot_deactivate_self", status_code=303)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    
    user.is_active = not user.is_active
    db.commit()
    
    status = "activated" if user.is_active else "deactivated"
    log_action(db, current_user.id, current_user.username, f"TOGGLE_USER_{status}", "users", user_id)
    return RedirectResponse(url="/users/", status_code=303)


@router.post("/{user_id}/change-role")
def change_user_role(
    user_id: int,
    request: Request,
    new_role: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only admin can change roles
    require_role(current_user, ["admin"])
    
    if user_id == current_user.id:
        return RedirectResponse(url="/users/?error=cannot_change_self_role", status_code=303)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404)
    
    old_role = user.role
    user.role = new_role
    db.commit()
    
    log_action(db, current_user.id, current_user.username, "CHANGE_USER_ROLE", "users", user_id, old_role, new_role)
    return RedirectResponse(url="/users/", status_code=303)


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    request: Request,
    new_password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Only admin can reset passwords
    require_role(current_user, ["admin"])
    
    # Prevent admin from resetting their own password
    if user_id == current_user.id:
        return RedirectResponse(url="/users/?error=cannot_reset_self", status_code=303)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    # Check minimum length
    if len(new_password) < 4:
        return RedirectResponse(url="/users/?error=password_too_short", status_code=303)
    
    # Update password
    user.hashed_password = hash_password(new_password)
    db.commit()
    
    log_action(db, current_user.id, current_user.username, "RESET_USER_PASSWORD", "users", user_id)
    
    return RedirectResponse(url="/users/?success=password_reset", status_code=303)


@router.get("/change-password", response_class=HTMLResponse)
def change_password_form(request: Request, current_user: User = Depends(get_current_user)):
    """Show password change form for current user"""
    return templates.TemplateResponse("users/change_password.html", {
        "request": request,
        "user": current_user,
        "error": None,
        "success": None
    })


@router.post("/change-password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Change password for current user"""
    # Verify current password
    if not pwd_context.verify(current_password, current_user.hashed_password):
        return templates.TemplateResponse("users/change_password.html", {
            "request": request,
            "user": current_user,
            "error": "Current password is incorrect",
            "success": None
        })
    
    # Check if new password matches confirmation
    if new_password != confirm_password:
        return templates.TemplateResponse("users/change_password.html", {
            "request": request,
            "user": current_user,
            "error": "New passwords do not match",
            "success": None
        })
    
    # Check minimum length
    if len(new_password) < 4:
        return templates.TemplateResponse("users/change_password.html", {
            "request": request,
            "user": current_user,
            "error": "Password must be at least 4 characters long",
            "success": None
        })
    
    # Update password
    current_user.hashed_password = pwd_context.hash(new_password)
    db.commit()
    
    log_action(db, current_user.id, current_user.username, "CHANGE_PASSWORD", "users", current_user.id)
    
    return templates.TemplateResponse("users/change_password.html", {
        "request": request,
        "user": current_user,
        "error": None,
        "success": "✅ Password changed successfully!"
    })