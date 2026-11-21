from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import MONTH_PATTERN
from app.services import budget_service, report_service

router = APIRouter(prefix="/reports", tags=["reports"])


def month_param(month: str = Query(default_factory=report_service.current_month, pattern=MONTH_PATTERN)) -> str:
    """?month=YYYY-MM, defaulting to the current month."""
    return month


@router.get("/monthly-summary")
def monthly_summary(month: str = Depends(month_param), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return report_service.monthly_summary(db, user.id, month)


@router.get("/category-breakdown")
def category_breakdown(month: str = Depends(month_param), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return report_service.category_breakdown(db, user.id, month)


@router.get("/trend")
def trend(months: int = Query(default=6, ge=2, le=24), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return report_service.trend(db, user.id, months)


@router.get("/budget-status")
def budget_status(month: str = Depends(month_param), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return budget_service.budget_status(db, user.id, month)


@router.get("/projection")
def projection(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return report_service.projection(db, user.id)
