"""SQLAlchemy ORM tables: User, Category, Expense, Budget."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    categories: Mapped[list["Category"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    budgets: Mapped[list["Budget"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_category_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))

    owner: Mapped["User"] = relationship(back_populates="categories")
    expenses: Mapped[list["Expense"]] = relationship(back_populates="category")
    budgets: Mapped[list["Budget"]] = relationship(back_populates="category", cascade="all, delete-orphan")


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expenses_user_date", "user_id", "expense_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    expense_date: Mapped[date] = mapped_column(default=date.today, index=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    category: Mapped["Category"] = relationship(back_populates="expenses")
    owner: Mapped["User"] = relationship(back_populates="expenses")


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category_id", "month", name="uq_budget_user_cat_month"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    month: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    owner: Mapped["User"] = relationship(back_populates="budgets")
    category: Mapped["Category"] = relationship(back_populates="budgets")
