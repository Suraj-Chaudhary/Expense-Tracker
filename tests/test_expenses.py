from datetime import date, timedelta

from tests.conftest import add_expense, make_category, make_user


def test_add_expense_returns_category_name(client, auth):
    cat = make_category(client, auth, "Food")
    r = add_expense(client, auth, cat, 180.50, description="Lunch")
    assert r.status_code == 201
    body = r.json()
    assert body["amount"] == 180.5 and body["category_name"] == "Food"
    assert body["expense_date"] == str(date.today())


def test_t6_negative_amount_rejected(client, auth):
    cat = make_category(client, auth)
    assert add_expense(client, auth, cat, -5).status_code == 422
    assert add_expense(client, auth, cat, 0).status_code == 422


def test_amount_limits_and_future_date(client, auth):
    cat = make_category(client, auth)
    assert add_expense(client, auth, cat, 1_000_001).status_code == 422
    assert add_expense(client, auth, cat, 10.123).status_code == 422
    tomorrow = date.today() + timedelta(days=1)
    assert add_expense(client, auth, cat, 10, expense_date=tomorrow).status_code == 422


def test_t7_cannot_use_other_users_category(client, auth):
    other = make_user(client, "mallory")
    foreign_cat = make_category(client, other, "Secret")
    assert add_expense(client, auth, foreign_cat, 10).status_code == 404


def test_t8_data_isolation(client, auth):
    cat = make_category(client, auth)
    expense_id = add_expense(client, auth, cat, 50).json()["id"]
    other = make_user(client, "mallory")
    assert client.get(f"/expenses/{expense_id}", headers=other).status_code == 404
    assert client.put(f"/expenses/{expense_id}", json={"amount": 1}, headers=other).status_code == 404
    assert client.delete(f"/expenses/{expense_id}", headers=other).status_code == 404
    assert client.get("/expenses", headers=other).json() == []


def test_t9_filter_by_date_range(client, auth):
    cat = make_category(client, auth)
    for d in ("2026-01-05", "2026-01-15", "2026-02-01"):
        add_expense(client, auth, cat, 10, expense_date=d)
    r = client.get("/expenses", params={"start_date": "2026-01-10", "end_date": "2026-01-31"}, headers=auth)
    assert [e["expense_date"] for e in r.json()] == ["2026-01-15"]


def test_filters_search_amount_pagination(client, auth):
    food, travel = make_category(client, auth, "Food"), make_category(client, auth, "Travel")
    add_expense(client, auth, food, 100, "2026-03-01", "Pizza night")
    add_expense(client, auth, food, 300, "2026-03-02", "Groceries")
    add_expense(client, auth, travel, 500, "2026-03-03", "Metro card")
    assert len(client.get("/expenses", params={"category_id": travel}, headers=auth).json()) == 1
    assert len(client.get("/expenses", params={"min_amount": 200}, headers=auth).json()) == 2
    assert len(client.get("/expenses", params={"max_amount": 200}, headers=auth).json()) == 1
    assert client.get("/expenses", params={"search": "PIZZA"}, headers=auth).json()[0]["description"] == "Pizza night"
    assert client.get("/expenses", params={"search": "%"}, headers=auth).json() == []  # wildcard is escaped
    page = client.get("/expenses", params={"limit": 2, "skip": 1}, headers=auth).json()
    assert [e["expense_date"] for e in page] == ["2026-03-02", "2026-03-01"]  # newest first
    assert client.get("/expenses", params={"limit": 101}, headers=auth).status_code == 422


def test_update_and_delete_expense(client, auth):
    cat = make_category(client, auth)
    eid = add_expense(client, auth, cat, 50, description="old").json()["id"]
    r = client.put(f"/expenses/{eid}", json={"amount": 75, "description": "new"}, headers=auth)
    assert r.status_code == 200 and r.json()["amount"] == 75 and r.json()["description"] == "new"
    assert client.delete(f"/expenses/{eid}", headers=auth).status_code == 204
    assert client.get(f"/expenses/{eid}", headers=auth).status_code == 404


def test_category_crud_and_t14_delete_in_use(client, auth):
    cat = make_category(client, auth, "Food")
    assert client.post("/categories", json={"name": "food"}, headers=auth).status_code == 409  # case-insensitive
    add_expense(client, auth, cat, 10)
    assert client.delete(f"/categories/{cat}", headers=auth).status_code == 409
    empty = make_category(client, auth, "Empty")
    assert client.delete(f"/categories/{empty}", headers=auth).status_code == 204
    assert [c["name"] for c in client.get("/categories", headers=auth).json()] == ["Food"]
