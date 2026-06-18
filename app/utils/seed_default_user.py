from .utils.audit import log_action
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@app.on_event("startup")
def create_default_user():
    from .database import SessionLocal
    from .models.user import User
    db = SessionLocal()
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        hashed = pwd_context.hash("admin123")
        admin_user = User(username="admin", hashed_password=hashed, full_name="System Admin", role="admin")
        db.add(admin_user)
        db.commit()
        print("Default admin created: username=admin, password=admin123")
    db.close()