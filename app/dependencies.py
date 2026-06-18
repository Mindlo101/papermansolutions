from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")  # we'll implement later

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    # For now, placeholder – we'll implement JWT or session cookie later
    # For simplicity during first phase, we'll skip auth and assume a default user
    # But we'll still keep the structure.
    return {"id": 1, "username": "admin", "role": "admin"}

def require_role(required_role: str):
    def role_checker(current_user=Depends(get_current_user)):
        if current_user["role"] != required_role and current_user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return role_checker