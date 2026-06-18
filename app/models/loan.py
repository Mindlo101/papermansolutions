from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)

    amount = Column(Float, nullable=False)
    term_months = Column(Integer, nullable=False)
    interest_rate = Column(Float, nullable=False)
    interest_amount = Column(Float, nullable=False)
    total_repayment = Column(Float, nullable=False)
    monthly_installment = Column(Float, nullable=False)

    status = Column(String(20), default="PENDING")
    balance_remaining = Column(Float, default=0.0)

    approval_date = Column(Date, nullable=True)
    disbursement_date = Column(Date, nullable=True)
    next_due_date = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Use string references for relationships
    customer = relationship("Customer", back_populates="loans")
    payments = relationship("Payment", back_populates="loan", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="loan", cascade="all, delete-orphan")