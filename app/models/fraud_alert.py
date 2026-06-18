from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from ..database import Base


class FraudAlert(Base):
    __tablename__ = "fraud_alerts"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=True)
    
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH
    ai_decision = Column(String(20), nullable=False)  # APPROVE, REVIEW, BLOCK
    
    flags = Column(Text, nullable=True)  # JSON string of all fraud flags
    flag_count = Column(Integer, default=0)
    
    # Override tracking
    is_overridden = Column(Boolean, default=False)
    overridden_by = Column(Integer, nullable=True)  # User ID
    override_reason = Column(Text, nullable=True)
    override_at = Column(DateTime(timezone=True), nullable=True)
    
    # Final status after override
    final_status = Column(String(20), nullable=True)  # APPROVED, REJECTED
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    customer = relationship("Customer", foreign_keys=[customer_id])
    loan = relationship("Loan", foreign_keys=[loan_id])