from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Category, Expense, User
from app.schemas import ExpenseCreate, ExpenseOut, ExpenseUpdate

router = APIRouter(prefix="/expenses", tags=["expenses"])


def to_out(e: Expense) -> ExpenseOut:
    return ExpenseOut(
        id=e.id,
        amount=e.amount,
        category_id=e.category_id,
        category_name=e.category.name,
        description=e.description,
        expense_date=e.expense_date,
    )


def _owned_category(db: Session, user: User, category_id: int) -> Category:
    category = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user.id))
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    return category


def _owned_expense(db: Session, user: User, expense_id: int) -> Expense:
    expense = db.scalar(
        select(Expense)
        .options(joinedload(Expense.category))
        .where(Expense.id == expense_id, Expense.user_id == user.id)
    )
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    return expense


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def add_expense(data: ExpenseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    category = _owned_category(db, user, data.category_id)
    expense = Expense(
        user_id=user.id,
        category_id=category.id,
        amount=data.amount,
        description=data.description,
        expense_date=data.expense_date,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return to_out(expense)


@router.get("", response_model=list[ExpenseOut])
def list_expenses(
    category_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    min_amount: Decimal | None = Query(default=None, ge=0),
    max_amount: Decimal | None = Query(default=None, ge=0),
    search: str | None = Query(default=None, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Expense).options(joinedload(Expense.category)).where(Expense.user_id == user.id)
    if category_id is not None:
        query = query.where(Expense.category_id == category_id)
    if start_date is not None:
        query = query.where(Expense.expense_date >= start_date)
    if end_date is not None:
        query = query.where(Expense.expense_date <= end_date)
    if min_amount is not None:
        query = query.where(Expense.amount >= min_amount)
    if max_amount is not None:
        query = query.where(Expense.amount <= max_amount)
    if search:
        query = query.where(Expense.description.icontains(search, autoescape=True))
    query = query.order_by(Expense.expense_date.desc(), Expense.id.desc()).offset(skip).limit(limit)
    return [to_out(e) for e in db.scalars(query).all()]


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(expense_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return to_out(_owned_expense(db, user, expense_id))


@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int, data: ExpenseUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    expense = _owned_expense(db, user, expense_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("category_id") is not None:
        _owned_category(db, user, changes["category_id"])
    for field, value in changes.items():
        if value is None and field != "description":
            continue  # amount, category and date can't be nulled
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return to_out(expense)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_owned_expense(db, user, expense_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
