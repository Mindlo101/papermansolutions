from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CustomerBase(BaseModel):
    first_name: str
    last_name: str
    id_number: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    employer: Optional[str] = None
    monthly_income: Optional[float] = 0.0

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    employer: Optional[str] = None
    monthly_income: Optional[float] = None

class CustomerResponse(CustomerBase):
    id: int
    is_blacklisted: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True