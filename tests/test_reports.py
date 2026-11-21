from datetime import date
from decimal import Decimal

from app.services.report_service import month_bounds, shift_month
from tests.conftest import add_expense, make_category

THIS_MONTH = date.today().strftime("%Y-%m")
FIRST = date.today().replace(day=1)


def test_month_helpers():
    assert month_bounds("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert month_bounds("2028-02")[1] == date(2028, 2, 29)
    assert shift_month("2026-01", -1) == "2025-12"
    assert shift_month("2026-11", 3) == "2027-02"


def test_t10_empty_month_returns_zeros(client, auth):
    r = client.get("/reports/monthly-summary", params={"month": "2020-01"}, headers=auth)
    assert r.status_code == 200
    assert r.json() == {"month": "2020-01", "total": 0.0, "count": 0, "average": 0.0, "highest": 0.0}
    assert client.get("/reports/category-breakdown", params={"month": "2020-01"}, headers=auth).json()["breakdown"] == []


def test_monthly_summary(client, auth):
    cat = make_category(client, auth)
    for amount in (100, 200, 600):
        add_expense(client, auth, cat, amount, "2026-01-10")
    add_expense(client, auth, cat, 999, "2026-02-01")  # other month, must be ignored
    r = client.get("/reports/monthly-summary", params={"month": "2026-01"}, headers=auth).json()
    assert r == {"month": "2026-01", "total": 900.0, "count": 3, "average": 300.0, "highest": 600.0}


def test_invalid_month_format(client, auth):
    assert client.get("/reports/monthly-summary", params={"month": "2026-13"}, headers=auth).status_code == 422
    assert client.get("/reports/monthly-summary", params={"month": "Jan"}, headers=auth).status_code == 422


def test_t11_breakdown_percentages(client, auth):
    food, travel, other = (make_category(client, auth, n) for n in ("Food", "Transport", "Others"))
    add_expense(client, auth, food, 2750, "2026-01-05")
    add_expense(client, auth, travel, 1500, "2026-01-06")
    add_expense(client, auth, other, 970, "2026-01-07")
    r = client.get("/reports/category-breakdown", params={"month": "2026-01"}, headers=auth).json()
    assert r["total"] == 5220.0
    assert [b["category"] for b in r["breakdown"]] == ["Food", "Transport", "Others"]  # sorted desc
    assert abs(sum(b["percent"] for b in r["breakdown"]) - 100) < 0.05


def test_t12_budget_warning_and_boundaries(client, auth):
    cat = make_category(client, auth)
    r = client.put("/budgets", json={"category_id": cat, "month": "2026-01", "limit_amount": 1000}, headers=auth)
    assert r.status_code == 200
    # updating the same category+month replaces, not duplicates
    client.put("/budgets", json={"category_id": cat, "month": "2026-01", "limit_amount": 1000}, headers=auth)
    assert len(client.get("/budgets", params={"month": "2026-01"}, headers=auth).json()) == 1

    def current_status():
        return client.get("/reports/budget-status", params={"month": "2026-01"}, headers=auth).json()["budgets"][0]

    add_expense(client, auth, cat, 790, "2026-01-02")
    assert current_status()["status"] == "OK"
    add_expense(client, auth, cat, 60, "2026-01-03")  # 850 -> 85%
    s = current_status()
    assert s["status"] == "WARNING" and s["used_percent"] == 85.0 and s["remaining"] == 150.0
    add_expense(client, auth, cat, 150, "2026-01-04")  # exactly 100% -> still WARNING per spec
    assert current_status()["status"] == "WARNING"
    add_expense(client, auth, cat, 50, "2026-01-05")  # 1050 -> 105%
    s = current_status()
    assert s["status"] == "EXCEEDED" and s["excess"] == 50.0


def test_budget_requires_own_category(client, auth):
    assert client.put("/budgets", json={"category_id": 999, "month": "2026-01", "limit_amount": 10}, headers=auth).status_code == 404


def test_t13_trend_previous_zero_gives_null(client, auth):
    cat = make_category(client, auth)
    add_expense(client, auth, cat, 400, FIRST)
    r = client.get("/reports/trend", params={"months": 3}, headers=auth).json()["trend"]
    assert [t["month"] for t in r][-1] == THIS_MONTH
    assert r[-1]["total"] == 400.0
    assert r[0]["change_percent"] is None  # first has no predecessor
    assert r[-1]["change_percent"] is None  # previous month total is 0 -> no division error


def test_trend_percentage_change(client, auth):
    cat = make_category(client, auth)
    prev_month = shift_month(THIS_MONTH, -1)
    add_expense(client, auth, cat, 200, f"{prev_month}-15")
    add_expense(client, auth, cat, 300, FIRST)
    r = client.get("/reports/trend", params={"months": 2}, headers=auth).json()["trend"]
    assert r[-1]["change_percent"] == 50.0


def test_projection(client, auth):
    cat = make_category(client, auth)
    add_expense(client, auth, cat, 400, FIRST)
    r = client.get("/reports/projection", headers=auth).json()
    today = date.today()
    assert r["spent"] == 400.0
    assert r["daily_average"] == float(round(Decimal(400) / today.day, 2))
    assert r["budget_total"] is None and r["likely_to_exceed_budget"] is False
    client.put("/budgets", json={"category_id": cat, "month": THIS_MONTH, "limit_amount": 1}, headers=auth)
    assert client.get("/reports/projection", headers=auth).json()["likely_to_exceed_budget"] is True


def test_projection_worked_example_from_report():
    """Rs 4,000 by day 10 of a 30-day month -> projected Rs 12,000."""
    from tests.conftest import TestingSession, engine
    from app.database import Base
    from app.models import Category, Expense, User
    from app.services.report_service import projection

    Base.metadata.create_all(engine)
    db = TestingSession()
    try:
        user = User(username="u", hashed_password="x")
        db.add(user)
        db.flush()
        cat = Category(user_id=user.id, name="Misc")
        db.add(cat)
        db.flush()
        db.add(Expense(user_id=user.id, category_id=cat.id, amount=Decimal(4000), expense_date=date(2026, 6, 5)))
        db.commit()
        r = projection(db, user.id, today=date(2026, 6, 10))
        assert r["daily_average"] == 400.0 and r["projected_total"] == 12000.0 and r["days_remaining"] == 20
    finally:
        db.close()
        Base.metadata.drop_all(engine)
