"""Schema for an independent local finance database."""

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProfileInfo(SQLModel, table=True):
    """Display name stored inside each portable profile database."""

    __tablename__ = "profile_info"
    id: int = Field(default=1, primary_key=True)
    name: str


class PaymentMode(SQLModel, table=True):
    __tablename__ = "payment_modes"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)


class Category(SQLModel, table=True):
    __tablename__ = "categories"
    id: int | None = Field(default=None, primary_key=True)
    name: str
    parent_id: int | None = Field(default=None, foreign_key="categories.id")


class Merchant(SQLModel, table=True):
    __tablename__ = "merchants"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    id: int | None = Field(default=None, primary_key=True)
    transaction_type: str  # 'credit' or 'debit'
    payment_mode_id: int | None = Field(default=None, foreign_key="payment_modes.id")
    amount: float
    currency: str = Field(default="INR")
    receiver_id: int | None = Field(default=None, foreign_key="merchants.id")
    category_id: int | None = Field(default=None, foreign_key="categories.id")
    description: str | None = None
    official_txn_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
