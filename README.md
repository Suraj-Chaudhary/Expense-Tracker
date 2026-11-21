# Expense Tracker API

A personal finance backend built with **FastAPI + SQLAlchemy + SQLite**, with a **Streamlit** front end.
Register, record expenses under your own categories, set monthly budgets, and get reports: monthly
summary, category breakdown, trends, budget alerts and a month-end spending projection.

## Quick start (Windows)

Open **PowerShell** in the project folder:

```powershell
# 1. virtual environment
python -m venv venv
venv\Scripts\Activate.ps1          # in cmd.exe use: venv\Scripts\activate.bat

# 2. dependencies
pip install -r requirements.txt

# 3. secret key used to sign login tokens (PowerShell syntax; cmd.exe: set SECRET_KEY=...)
$env:SECRET_KEY = "put-a-long-random-string-here"

# 4. (optional) demo user + sample data: login demo / demo12345
python seed_data.py

# 5. start the API  ->  http://127.0.0.1:8000/docs
uvicorn app.main:app --reload
```

In a **second** terminal (activate the venv again) start the UI:

```powershell
streamlit run streamlit_app.py     # opens http://localhost:8501
```

Run the tests: `pytest -v`

> If PowerShell blocks the activate script, run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
>
> Without `SECRET_KEY` the app still runs with an insecure development default and prints a warning.
> Use the same SECRET_KEY each time you start the API, or old login tokens stop working.

## Project layout

```
app/
  main.py          creates the app, creates tables on startup, registers routers
  config.py        settings from environment variables (SECRET_KEY, token expiry, DATABASE_URL)
  database.py      engine, SessionLocal, Base, get_db() dependency (turns on SQLite foreign keys)
  models.py        tables: User, Category, Expense, Budget
  schemas.py       Pydantic request/response models and validation rules
  dependencies.py  get_current_user(): reads the JWT and loads the user
  routers/         auth, categories, expenses, budgets, reports (HTTP layer only)
  services/
    security.py        bcrypt hashing + JWT create/decode
    report_service.py  summary, breakdown, trend, projection
    budget_service.py  budget vs actual, OK / WARNING / EXCEEDED
tests/             pytest suite (in-memory SQLite, no real data touched)
streamlit_app.py   the front end; talks to the API over HTTP only
seed_data.py       creates demo data directly in the database
```

## How it fits together

Layers, each calling only the one below: **Streamlit / Swagger -> routers -> services -> SQLAlchemy -> SQLite.**

A typical request, `POST /expenses`:

1. Client sends JSON and `Authorization: Bearer <token>`.
2. `get_current_user` decodes the JWT and loads the user (bad/expired token -> **401**).
3. Pydantic validates the body (amount > 0, date not in the future ...) -> **422** on failure.
4. The router checks the category belongs to this user -> **404** otherwise.
5. The row is inserted and committed; the response is returned with **201**.

**Data isolation:** every query filters on `user_id`. Asking for someone else's record returns 404,
the same as a missing one, so ids can't be probed.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | 409 if the username exists |
| POST | `/auth/login` | form fields `username`, `password`; returns a JWT |
| GET | `/auth/me` | current user |
| POST/GET | `/categories` | |
| DELETE | `/categories/{id}` | 409 if expenses still use it |
| POST | `/expenses` | |
| GET | `/expenses` | filters: `category_id, start_date, end_date, min_amount, max_amount, search, skip, limit` |
| GET/PUT/DELETE | `/expenses/{id}` | PUT is a partial update |
| PUT | `/budgets` | create or update the limit for category + month |
| GET | `/budgets?month=YYYY-MM` | defaults to the current month |
| GET | `/reports/monthly-summary?month=` | total, count, average, highest |
| GET | `/reports/category-breakdown?month=` | amount and percent per category |
| GET | `/reports/trend?months=6` | totals plus % change (null if previous month is 0) |
| GET | `/reports/budget-status?month=` | OK (<80%), WARNING (80-100%), EXCEEDED (>100%) |
| GET | `/reports/projection` | daily average x days in month, compared with the sum of this month's budgets |

In Swagger (`/docs`), click **Authorize** and log in with username and password to try protected endpoints.

## Key design points

- **Passwords:** bcrypt with a per-user salt. Login gives the same error for an unknown user and a wrong
  password, so valid usernames can't be discovered.
- **JWT:** HS256, expires after 60 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`); stateless, no sessions stored.
- **Money:** `Decimal` / `Numeric(10,2)` instead of floats; JSON responses show numbers.
- **Reports are computed in SQL** (`SUM`, `COUNT`, `AVG`, `MAX`, `GROUP BY`), not by loading rows into Python.
- **Index** on `expenses(user_id, expense_date)` for the common "my expenses in a date range" query.
- **Tests** replace `get_db` with an in-memory database (dependency injection), covering all 14 cases
  from the report plus extras (filters, pagination, partial update, projection worked example).

## Small changes from the original report

| Change | Why |
|---|---|
| `datetime.now(timezone.utc)` instead of `datetime.utcnow` | `utcnow` is deprecated in Python 3.12+ |
| Password max length 72 bytes | bcrypt only uses the first 72 bytes; newer versions reject longer input |
| `amount <= 1,000,000` enforced | the report states this limit but `Numeric(10,2)` alone allows far more |
| Projection compares against the **sum of category budgets** | budgets exist per category only; there is no separate total budget |
| JWT `sub` stored as a string | required by the current PyJWT |
| Category names are unique case-insensitively | avoids "Food" and "food" as separate categories |
| Budget at exactly 100% counts as WARNING | follows the report's table (EXCEEDED is strictly greater than 100) |

## Known limitations

SQLite is single-machine; one currency (INR); manual entry only; the projection assumes even spending
(a big early-month cost inflates it); no password reset or refresh tokens; no user-delete endpoint.

## Ideas for later

Recurring expenses, CSV/PDF export, receipt OCR, shared expenses, income tracking, Alembic migrations and
PostgreSQL, Docker, refresh tokens and rate limiting.
