from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Use a persistent path on Railway
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./papermansolutions.db")

# For Railway, use a persistent volume path
if os.getenv("RAILWAY_VOLUME_MOUNT_PATH"):
    db_path = os.path.join(os.getenv("RAILWAY_VOLUME_MOUNT_PATH"), "papermansolutions.db")
    DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()