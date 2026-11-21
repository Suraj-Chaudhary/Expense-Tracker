"""Streamlit front end for the Expense Tracker API.

Run the API first (uvicorn app.main:app --reload), then:  streamlit run streamlit_app.py
"""
import os
from datetime import date

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Expense Tracker", page_icon="💸", layout="wide")


# ---------------------------------------------------------------- API helpers
def api(method: str, path: str, **kwargs):
    """Call the backend. Returns (response | None, error message | None)."""
    headers = {}
    if st.session_state.get("token"):
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    try:
        resp = requests.request(method, f"{API_URL}{path}", headers=headers, timeout=10, **kwargs)
    except requests.exceptions.RequestException:
        return None, f"Cannot reach the API at {API_URL}. Is the server running?"
    if resp.status_code == 401 and st.session_state.get("token"):
        st.session_state.pop("token", None)
        st.session_state.pop("username", None)
        return None, "Session expired. Please log in again."
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        if isinstance(detail, list):  # FastAPI validation errors
            detail = "; ".join(f"{'.'.join(map(str, d['loc'][1:]))}: {d['msg']}" for d in detail)
        return None, str(detail)
    return resp, None


def get_json(path: str, **params):
    resp, err = api("GET", path, params=params)
    if err:
        st.error(err)
        return None
    return resp.json()


def inr(value: float) -> str:
    return f"₹{value:,.2f}"


def month_options(n: int = 12) -> list[str]:
    today = date.today()
    out = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def load_categories() -> list[dict]:
    return get_json("/categories") or []


# ---------------------------------------------------------------- auth page
def auth_page():
    st.title("💸 Expense Tracker")
    st.caption("Track spending, set budgets and see where your money goes.")
    login_tab, register_tab = st.tabs(["Log in", "Create account"])

    with login_tab:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", type="primary"):
                resp, err = api("POST", "/auth/login", data={"username": username, "password": password})
                if err:
                    st.error(err)
                else:
                    st.session_state.token = resp.json()["access_token"]
                    st.session_state.username = username
                    st.rerun()

    with register_tab:
        with st.form("register"):
            username = st.text_input("Username (3-50 letters, digits or _)")
            password = st.text_input("Password (8-72 characters)", type="password")
            if st.form_submit_button("Create account"):
                _, err = api("POST", "/auth/register", json={"username": username, "password": password})
                if err:
                    st.error(err)
                else:
                    st.success("Account created. You can now log in.")


# ---------------------------------------------------------------- pages
def dashboard_page():
    st.header("Dashboard")
    month = st.selectbox("Month", month_options())

    summary = get_json("/reports/monthly-summary", month=month)
    if summary:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total spent", inr(summary["total"]))
        c2.metric("Expenses", summary["count"])
        c3.metric("Average", inr(summary["average"]))
        c4.metric("Highest", inr(summary["highest"]))

    left, right = st.columns(2)
    with left:
        st.subheader("By category")
        data = get_json("/reports/category-breakdown", month=month)
        if data and data["breakdown"]:
            df = pd.DataFrame(data["breakdown"]).set_index("category")
            st.bar_chart(df["amount"])
            st.dataframe(df.rename(columns={"amount": "Amount (₹)", "percent": "Share (%)"}), width="stretch")
        else:
            st.info("No expenses in this month.")
    with right:
        st.subheader("Monthly trend")
        months = st.slider("Months", 2, 12, 6)
        data = get_json("/reports/trend", months=months)
        if data:
            df = pd.DataFrame(data["trend"]).set_index("month")
            st.bar_chart(df["total"])
            st.dataframe(
                df.rename(columns={"total": "Total (₹)", "change_percent": "Change (%)"}),
                width="stretch",
            )

    st.subheader("Budget status")
    data = get_json("/reports/budget-status", month=month)
    if data and data["budgets"]:
        icons = {"OK": "🟢", "WARNING": "🟠", "EXCEEDED": "🔴"}
        for b in data["budgets"]:
            st.write(
                f"{icons[b['status']]} **{b['category']}** - {inr(b['spent'])} of {inr(b['limit'])} "
                f"({b['used_percent']}%) · {b['status']}"
            )
            st.progress(min(b["used_percent"] / 100, 1.0))
            if b["status"] == "EXCEEDED":
                st.caption(f"Over budget by {inr(b['excess'])}")
            elif b["status"] == "WARNING":
                st.caption(f"Close to the limit - {inr(b['remaining'])} left")
    else:
        st.info("No budgets set for this month. Add some on the Budgets page.")

    if month == month_options()[0]:
        st.subheader("Month-end projection")
        p = get_json("/reports/projection")
        if p:
            c1, c2, c3 = st.columns(3)
            c1.metric("Spent so far", inr(p["spent"]))
            c2.metric("Daily average", inr(p["daily_average"]))
            c3.metric("Projected total", inr(p["projected_total"]), help=f"{p['days_remaining']} days remaining")
            if p["likely_to_exceed_budget"]:
                st.warning(f"At this pace you will exceed your total budget of {inr(p['budget_total'])}.")
            elif p["budget_total"] is not None:
                st.success(f"On track against your total budget of {inr(p['budget_total'])}.")


def add_expense_page():
    st.header("Add expense")
    categories = load_categories()
    if not categories:
        st.info("Create a category first on the Categories page.")
        return
    names = {c["name"]: c["id"] for c in categories}
    with st.form("add_expense", clear_on_submit=True):
        amount = st.number_input("Amount (₹)", min_value=0.01, max_value=1_000_000.0, value=100.0, step=10.0)
        category = st.selectbox("Category", list(names))
        when = st.date_input("Date", value=date.today(), max_value=date.today())
        description = st.text_input("Description", max_chars=200)
        if st.form_submit_button("Add expense", type="primary"):
            body = {
                "amount": round(amount, 2),
                "category_id": names[category],
                "expense_date": str(when),
                "description": description or None,
            }
            _, err = api("POST", "/expenses", json=body)
            if err:
                st.error(err)
            else:
                st.success("Expense added.")


def expenses_page():
    st.header("Expenses")
    categories = load_categories()
    names = {c["name"]: c["id"] for c in categories}

    with st.expander("Filters", expanded=True):
        c1, c2, c3 = st.columns(3)
        cat = c1.selectbox("Category", ["All"] + list(names))
        use_dates = c2.checkbox("Filter by date range")
        search = c3.text_input("Search description")
        params: dict = {}
        if use_dates:
            d1, d2 = st.columns(2)
            params["start_date"] = str(d1.date_input("From", value=date.today().replace(day=1)))
            params["end_date"] = str(d2.date_input("To", value=date.today()))
        a1, a2, a3 = st.columns(3)
        min_amt = a1.number_input("Min amount", min_value=0.0, value=0.0)
        max_amt = a2.number_input("Max amount (0 = no limit)", min_value=0.0, value=0.0)
        page_size = a3.selectbox("Rows per page", [10, 20, 50, 100], index=1)
    if cat != "All":
        params["category_id"] = names[cat]
    if search:
        params["search"] = search
    if min_amt > 0:
        params["min_amount"] = min_amt
    if max_amt > 0:
        params["max_amount"] = max_amt

    page = st.number_input("Page", min_value=1, value=1, step=1)
    data = get_json("/expenses", skip=(page - 1) * page_size, limit=page_size, **params)
    if data is None:
        return
    if not data:
        st.info("No expenses match.")
        return

    df = pd.DataFrame(data)[["id", "expense_date", "category_name", "amount", "description"]]
    df.columns = ["ID", "Date", "Category", "Amount (₹)", "Description"]
    st.dataframe(df, width="stretch", hide_index=True)

    with st.expander("Delete an expense"):
        eid = st.selectbox("Expense ID", df["ID"].tolist())
        if st.button("Delete", type="primary"):
            _, err = api("DELETE", f"/expenses/{eid}")
            if err:
                st.error(err)
            else:
                st.success(f"Deleted expense {eid}.")
                st.rerun()


def categories_page():
    st.header("Categories")
    with st.form("add_category", clear_on_submit=True):
        name = st.text_input("New category name", max_chars=50)
        if st.form_submit_button("Add category", type="primary"):
            _, err = api("POST", "/categories", json={"name": name})
            if err:
                st.error(err)
            else:
                st.rerun()

    categories = load_categories()
    if not categories:
        st.info("No categories yet.")
        return
    for c in categories:
        col1, col2 = st.columns([4, 1])
        col1.write(c["name"])
        if col2.button("Delete", key=f"del_cat_{c['id']}"):
            _, err = api("DELETE", f"/categories/{c['id']}")
            if err:
                st.error(err)
            else:
                st.rerun()


def budgets_page():
    st.header("Budgets")
    categories = load_categories()
    if not categories:
        st.info("Create a category first on the Categories page.")
        return
    names = {c["name"]: c["id"] for c in categories}
    month = st.selectbox("Month", month_options())

    with st.form("set_budget"):
        category = st.selectbox("Category", list(names))
        limit = st.number_input("Monthly limit (₹)", min_value=1.0, max_value=1_000_000.0, value=1000.0, step=100.0)
        if st.form_submit_button("Save budget", type="primary"):
            body = {"category_id": names[category], "month": month, "limit_amount": round(limit, 2)}
            _, err = api("PUT", "/budgets", json=body)
            if err:
                st.error(err)
            else:
                st.success("Budget saved.")

    budgets = get_json("/budgets", month=month)
    if budgets:
        df = pd.DataFrame(budgets)[["category_name", "limit_amount"]]
        df.columns = ["Category", "Limit (₹)"]
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("No budgets for this month yet.")


PAGES = {
    "Dashboard": dashboard_page,
    "Add expense": add_expense_page,
    "Expenses": expenses_page,
    "Categories": categories_page,
    "Budgets": budgets_page,
}


# ---------------------------------------------------------------- main
if not st.session_state.get("token"):
    auth_page()
else:
    with st.sidebar:
        st.write(f"Logged in as **{st.session_state.get('username', '')}**")
        choice = st.radio("Go to", list(PAGES), label_visibility="collapsed")
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()
    PAGES[choice]()
