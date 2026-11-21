from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Category, Expense, User
from app.schemas import CategoryCreate, CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    exists = db.scalar(
        select(Category).where(Category.user_id == user.id, func.lower(Category.name) == data.name.lower())
    )
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Category already exists")
    category = Category(user_id=user.id, name=data.name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Category).where(Category.user_id == user.id).order_by(Category.name)).all()


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    category = db.scalar(select(Category).where(Category.id == category_id, Category.user_id == user.id))
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    in_use = db.scalar(select(func.count(Expense.id)).where(Expense.category_id == category.id))
    if in_use:
        raise HTTPException(status.HTTP_409_CONFLICT, "Category still has expenses and cannot be deleted")
    db.delete(category)  # its budgets are removed by the ORM cascade
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
