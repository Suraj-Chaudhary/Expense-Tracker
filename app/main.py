"""FastAPI application entry point. Run with: uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.routers import auth, budgets, categories, expenses, reports


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)  # creates tables on first run
    yield


app = FastAPI(
    title="Expense Tracker API",
    description="A FastAPI and SQLite based personal finance management system.",
    version="1.0.0",
    lifespan=lifespan,
)

for module in (auth, categories, expenses, budgets, reports):
    app.include_router(module.router)


@app.get("/", tags=["health"])
def root():
    return {"name": "Expense Tracker API", "docs": "/docs", "status": "ok"}
