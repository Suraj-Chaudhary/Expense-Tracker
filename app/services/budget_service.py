"""Budget evaluation: compare spending with the monthly limit of each category."""
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Budget, Category, Expense
from app.services.report_service import TWO, money, month_bounds

WARNING_THRESHOLD = Decimal(80)
EXCEEDED_THRESHOLD = Decimal(100)


def evaluate(spent: Decimal, limit: Decimal) -> tuple[Decimal, str]:
    used_pct = spent / limit * 100
    if used_pct > EXCEEDED_THRESHOLD:
        status = "EXCEEDED"
    elif used_pct >= WARNING_THRESHOLD:
        status = "WARNING"
    else:
        status = "OK"
    return used_pct, status


def budget_status(db: Session, user_id: int, month: str) -> dict:
    start, end = month_bounds(month)
    budgets = db.execute(
        select(Budget, Category.name)
        .join(Category, Budget.category_id == Category.id)
        .where(Budget.user_id == user_id, Budget.month == month)
        .order_by(Category.name)
    ).all()

    items = []
    for budget, category_name in budgets:
        spent = Decimal(
            db.scalar(
                select(func.sum(Expense.amount)).where(
                    Expense.user_id == user_id,
                    Expense.category_id == budget.category_id,
                    Expense.expense_date.between(start, end),
                )
            )
            or 0
        )
        limit = Decimal(budget.limit_amount)
        used_pct, status = evaluate(spent, limit)
        remaining = limit - spent
        items.append(
            {
                "category": category_name,
                "limit": money(limit),
                "spent": money(spent),
                "remaining": money(remaining),
                "excess": money(-remaining) if remaining < 0 else 0.0,
                "used_percent": float(used_pct.quantize(TWO, rounding=ROUND_HALF_UP)),
                "status": status,
            }
        )
    return {"month": month, "budgets": items}
