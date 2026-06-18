from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base

class Blacklist(Base):
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), unique=True, nullable=False)
    reason = Column(Text)
    blacklisted_by = Column(Integer)
    blacklisted_at = Column(DateTime(timezone=True), server_default=func.now())