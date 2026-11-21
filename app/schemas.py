"""Pydantic request / response models."""
from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

# Decimal in, JSON number out (Pydantic would otherwise serialise Decimal as a string).
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
MAX_AMOUNT = 1_000_000  # 10,00,000


# ---------- auth ----------
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, v: str) -> str:
        # bcrypt only uses the first 72 *bytes*, so cap bytes, not characters.
        if len(v.encode("utf-8")) > 72:
            raise ValueError("password must be at most 72 bytes")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- categories ----------
class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be blank")
        return v


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


# ---------- expenses ----------
def _not_in_future(v: date | None) -> date | None:
    if v is not None and v > date.today():
        raise ValueError("expense_date cannot be in the future")
    return v


class ExpenseCreate(BaseModel):
    amount: Money = Field(gt=0, le=MAX_AMOUNT, max_digits=10, decimal_places=2)
    category_id: int
    description: str | None = Field(default=None, max_length=200)
    expense_date: date = Field(default_factory=date.today)

    _check_date = field_validator("expense_date")(_not_in_future)


class ExpenseUpdate(BaseModel):
    """Partial update: only the supplied fields are changed."""
    amount: Money | None = Field(default=None, gt=0, le=MAX_AMOUNT, max_digits=10, decimal_places=2)
    category_id: int | None = None
    description: str | None = Field(default=None, max_length=200)
    expense_date: date | None = None

    _check_date = field_validator("expense_date")(_not_in_future)


class ExpenseOut(BaseModel):
    id: int
    amount: Money
    category_id: int
    category_name: str
    description: str | None
    expense_date: date


# ---------- budgets ----------
class BudgetUpsert(BaseModel):
    category_id: int
    month: str = Field(pattern=MONTH_PATTERN)
    limit_amount: Money = Field(gt=0, le=MAX_AMOUNT, max_digits=10, decimal_places=2)


class BudgetOut(BaseModel):
    id: int
    category_id: int
    category_name: str
    month: str
    limit_amount: Money
