from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Budget, Category, User
from app.schemas import MONTH_PATTERN, BudgetOut, BudgetUpsert
from app.services.report_service import current_month

router = APIRouter(prefix="/budgets", tags=["budgets"])


def to_out(budget: Budget, category_name: str) -> BudgetOut:
    return BudgetOut(
        id=budget.id,
        category_id=budget.category_id,
        category_name=category_name,
        month=budget.month,
        limit_amount=budget.limit_amount,
    )


@router.put("", response_model=BudgetOut)
def upsert_budget(data: BudgetUpsert, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    category = db.scalar(select(Category).where(Category.id == data.category_id, Category.user_id == user.id))
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    budget = db.scalar(
        select(Budget).where(
            Budget.user_id == user.id, Budget.category_id == category.id, Budget.month == data.month
        )
    )
    if budget is None:
        budget = Budget(user_id=user.id, category_id=category.id, month=data.month, limit_amount=data.limit_amount)
        db.add(budget)
    else:
        budget.limit_amount = data.limit_amount
    db.commit()
    db.refresh(budget)
    return to_out(budget, category.name)


@router.get("", response_model=list[BudgetOut])
def list_budgets(
    month: str = Query(default_factory=current_month, pattern=MONTH_PATTERN),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(Budget, Category.name)
        .join(Category, Budget.category_id == Category.id)
        .where(Budget.user_id == user.id, Budget.month == month)
        .order_by(Category.name)
    ).all()
    return [to_out(b, name) for b, name in rows]
