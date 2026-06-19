from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    id_number = Column(String(50), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    email = Column(String(100), nullable=True)
    address = Column(String(200), nullable=True)
    employer = Column(String(100), nullable=True)
    monthly_income = Column(Float, default=0.0)
    is_blacklisted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # NEW: Soft delete columns
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, nullable=True)

    # Relationships
    loans = relationship("Loan", back_populates="customer", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="customer", cascade="all, delete-orphan")