from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class PaymentCreate(BaseModel):
    loan_id: int
    amount_paid: float
    payment_date: date
    method: str = "cash"
    reference: Optional[str] = None

class PaymentResponse(BaseModel):
    id: int
    loan_id: int
    amount_paid: float
    payment_date: date
    method: str
    reference: Optional[str]
    remaining_balance_after: float
    created_at: datetime

    class Config:
        from_attributes = True