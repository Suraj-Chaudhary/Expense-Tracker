"""Report calculations. Aggregation is done inside the database wherever possible."""
import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Budget, Category, Expense

TWO = Decimal("0.01")


def money(value) -> float:
    """Round a Decimal-ish value to 2 places and return a JSON-friendly float."""
    return float(Decimal(value or 0).quantize(TWO, rounding=ROUND_HALF_UP))


def current_month() -> str:
    return date.today().strftime("%Y-%m")


def month_bounds(month: str) -> tuple[date, date]:
    year, mon = int(month[:4]), int(month[5:7])
    return date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])


def shift_month(month: str, delta: int) -> str:
    year, mon = int(month[:4]), int(month[5:7])
    index = year * 12 + (mon - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_total(db: Session, user_id: int, month: str) -> Decimal:
    start, end = month_bounds(month)
    total = db.scalar(
        select(func.sum(Expense.amount)).where(
            Expense.user_id == user_id, Expense.expense_date.between(start, end)
        )
    )
    return Decimal(total or 0)


def monthly_summary(db: Session, user_id: int, month: str) -> dict:
    start, end = month_bounds(month)
    total, count, avg, highest = db.execute(
        select(func.sum(Expense.amount), func.count(Expense.id), func.avg(Expense.amount), func.max(Expense.amount))
        .where(Expense.user_id == user_id, Expense.expense_date.between(start, end))
    ).one()
    if not count:
        return {"month": month, "total": 0.0, "count": 0, "average": 0.0, "highest": 0.0}
    return {
        "month": month,
        "total": money(total),
        "count": count,
        "average": money(avg),
        "highest": money(highest),
    }


def category_breakdown(db: Session, user_id: int, month: str) -> dict:
    start, end = month_bounds(month)
    rows = db.execute(
        select(Category.name, func.sum(Expense.amount).label("spent"))
        .join(Category, Expense.category_id == Category.id)
        .where(Expense.user_id == user_id, Expense.expense_date.between(start, end))
        .group_by(Category.name)
    ).all()
    total = sum((Decimal(r.spent) for r in rows), Decimal(0))
    breakdown = [
        {
            "category": r.name,
            "amount": money(r.spent),
            "percent": float((Decimal(r.spent) / total * 100).quantize(TWO, rounding=ROUND_HALF_UP)),
        }
        for r in rows
    ]
    breakdown.sort(key=lambda item: item["amount"], reverse=True)
    return {"month": month, "total": money(total), "breakdown": breakdown}


def trend(db: Session, user_id: int, months: int) -> dict:
    now = current_month()
    series = []
    for i in range(months - 1, -1, -1):
        month = shift_month(now, -i)
        series.append({"month": month, "total": month_total(db, user_id, month)})
    result = []
    for k, item in enumerate(series):
        change = None
        if k > 0 and series[k - 1]["total"] != 0:
            prev = series[k - 1]["total"]
            change = float(((item["total"] - prev) / prev * 100).quantize(TWO, rounding=ROUND_HALF_UP))
        result.append({"month": item["month"], "total": money(item["total"]), "change_percent": change})
    return {"months": months, "trend": result}


def projection(db: Session, user_id: int, today: date | None = None) -> dict:
    today = today or date.today()
    month = today.strftime("%Y-%m")
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = today.day
    spent = month_total(db, user_id, month)
    daily_avg = spent / days_elapsed
    projected = daily_avg * days_in_month

    budget_total = db.scalar(
        select(func.sum(Budget.limit_amount)).where(Budget.user_id == user_id, Budget.month == month)
    )
    budget_total = Decimal(budget_total) if budget_total is not None else None
    return {
        "month": month,
        "spent": money(spent),
        "daily_average": money(daily_avg),
        "projected_total": money(projected),
        "days_remaining": days_in_month - days_elapsed,
        "budget_total": money(budget_total) if budget_total is not None else None,
        "likely_to_exceed_budget": bool(budget_total is not None and projected > budget_total),
    }
