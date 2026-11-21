"""Create a demo user with realistic sample data (no server needed).

Usage:  python seed_data.py
Login:  username 'demo'  /  password 'demo12345'
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Budget, Category, Expense, User
from app.services.report_service import current_month
from app.services.security import hash_password

USERNAME, PASSWORD = "demo", "demo12345"

# category -> (typical min, max, sample descriptions, monthly budget)
CATALOG = {
    "Food": (60, 450, ["Lunch at canteen", "Dinner with friends", "Groceries", "Snacks", "Coffee"], 6000),
    "Transport": (20, 300, ["Metro card recharge", "Auto fare", "Train pass", "Bus ticket"], 2000),
    "Education": (200, 1500, ["Online course", "Books", "Stationery", "Exam fee"], 3000),
    "Entertainment": (100, 700, ["Movie", "OTT subscription", "Game purchase"], 1500),
    "Subscriptions": (99, 499, ["Music plan", "Cloud storage", "Mobile recharge"], 1200),
}


def main() -> None:
    random.seed(42)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == USERNAME)):
            print(f"User '{USERNAME}' already exists - nothing to do.")
            return
        user = User(username=USERNAME, hashed_password=hash_password(PASSWORD))
        db.add(user)
        db.flush()

        categories = {}
        for name in CATALOG:
            categories[name] = Category(user_id=user.id, name=name)
            db.add(categories[name])
        db.flush()

        today = date.today()
        for offset in range(0, 90):  # the last ~3 months
            day = today - timedelta(days=offset)
            for _ in range(random.choice([0, 1, 1, 2])):
                name = random.choices(list(CATALOG), weights=[5, 3, 1, 2, 1])[0]
                low, high, notes, _budget = CATALOG[name]
                db.add(
                    Expense(
                        user_id=user.id,
                        category_id=categories[name].id,
                        amount=Decimal(random.randint(low, high)),
                        description=random.choice(notes),
                        expense_date=day,
                    )
                )

        month = current_month()
        for name, (*_rest, limit) in CATALOG.items():
            db.add(Budget(user_id=user.id, category_id=categories[name].id, month=month, limit_amount=Decimal(limit)))
        db.commit()
        print(f"Created demo user '{USERNAME}' (password '{PASSWORD}') with sample expenses and budgets.")


if __name__ == "__main__":
    main()
