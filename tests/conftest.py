"""Test fixtures: an in-memory SQLite database replaces the real one via dependency override."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


@event.listens_for(engine, "connect")
def _fk_on(dbapi_connection, _record):
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture
def client():
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def make_user(client, username="alice", password="password123") -> dict:
    """Register + log in; returns auth headers."""
    client.post("/auth/register", json={"username": username, "password": password})
    r = client.post("/auth/login", data={"username": username, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_category(client, headers, name="Food") -> int:
    return client.post("/categories", json={"name": name}, headers=headers).json()["id"]


def add_expense(client, headers, category_id, amount=100, expense_date=None, description=None):
    body = {"amount": amount, "category_id": category_id}
    if expense_date:
        body["expense_date"] = str(expense_date)
    if description:
        body["description"] = description
    return client.post("/expenses", json=body, headers=headers)


@pytest.fixture
def auth(client):
    return make_user(client)
