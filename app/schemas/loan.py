from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime

class LoanCreate(BaseModel):
    customer_id: int
    amount: float = Field(gt=0)
    term_months: int = Field(gt=0, le=60)

class LoanResponse(BaseModel):
    id: int
    customer_id: int
    amount: float
    term_months: int
    interest_rate: float
    interest_amount: float
    total_repayment: float
    monthly_installment: float
    status: str
    balance_remaining: float
    approval_date: Optional[date] = None
    disbursement_date: Optional[date] = None
    next_due_date: Optional[date] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True