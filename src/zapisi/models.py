from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
class PaymentMode(SQLModel, table=True):
    __tablename__ = "payment_modes"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)

class Category(SQLModel, table=True):
    __tablename__ = "categories"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    parent_id: Optional[int] = Field(default=None, foreign_key="categories.id")

class Merchant(SQLModel, table=True):
    __tablename__ = "merchants"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)

class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    transaction_type: str # 'credit' or 'debit'
    payment_mode_id: Optional[int] = Field(default=None, foreign_key="payment_modes.id")
    amount: float
    currency: str = Field(default="INR")
    receiver_id: Optional[int] = Field(default=None, foreign_key="merchants.id")
    category_id: Optional[int] = Field(default=None, foreign_key="categories.id")
    description: Optional[str] = None
    official_txn_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
