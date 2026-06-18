from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from passlib.context import CryptContext

from .database import Base, engine
from .config import settings
from .routers import (
    auth_router,
    dashboard_router,
    customers_router,
    loans_router,
    payments_router,
    documents_router,
    reports_router,
    users_router
)

# Create database tables
Base.metadata.create_all(bind=engine)

# FastAPI application
app = FastAPI(
    title="PapermanSolutions LMS",
    version="1.0.0"
)

# Password hashing
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto"
)

# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY
)

# Static files
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)

# Include routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(customers_router)
app.include_router(loans_router)
app.include_router(payments_router)
app.include_router(documents_router)
app.include_router(reports_router)
app.include_router(users_router)


# Root route - redirect to login
@app.get("/")
async def root():
    return RedirectResponse(
        url="/auth/login",
        status_code=302
    )


# Startup event - create default admin user if none exists
@app.on_event("startup")
def create_default_user():
    from .database import SessionLocal
    from .models.user import User

    db = SessionLocal()

    try:
        admin = (
            db.query(User)
            .filter(User.username == "admin")
            .first()
        )

        if not admin:
            hashed_password = pwd_context.hash("admin123")

            admin_user = User(
                username="admin",
                hashed_password=hashed_password,
                full_name="System Admin",
                role="admin",
                is_active=True
            )

            db.add(admin_user)
            db.commit()

            print("=" * 50)
            print("✅ Default admin created successfully!")
            print("📋 Username: admin")
            print("🔑 Password: admin123")
            print("=" * 50)
        else:
            print("✅ Admin user already exists")

    except Exception as e:
        print(f"❌ Startup error: {e}")

    finally:
        db.close()