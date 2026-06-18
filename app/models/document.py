from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50))
    uploaded_by = Column(Integer)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Use string references to avoid circular import issues
    customer = relationship("Customer", back_populates="documents")
    loan = relationship("Loan", back_populates="documents")