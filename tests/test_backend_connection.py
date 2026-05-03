import pytest
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)
from database.db import get_db
from werkzeug.security import generate_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_user(name="Test User", email="test@example.com", password="testpass"):
    db = get_db()
    cursor = db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password)),
    )
    user_id = cursor.lastrowid
    db.commit()
    db.close()
    return user_id


def _add_expense(user_id, amount, category, date, description=""):
    db = get_db()
    db.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# get_user_by_id
# ---------------------------------------------------------------------------

class TestGetUserById:
    def test_returns_dict_for_valid_user(self):
        uid = _create_user(name="Alice", email="alice@example.com")
        result = get_user_by_id(uid)
        assert result is not None
        assert result["name"] == "Alice"
        assert result["email"] == "alice@example.com"
        assert "member_since" in result

    def test_member_since_format(self):
        uid = _create_user(name="Bob", email="bob@example.com")
        result = get_user_by_id(uid)
        # Should be "Month YYYY" e.g. "May 2026"
        parts = result["member_since"].split()
        assert len(parts) == 2
        assert parts[1].isdigit()

    def test_returns_none_for_nonexistent_user(self):
        assert get_user_by_id(999999) is None


# ---------------------------------------------------------------------------
# get_summary_stats
# ---------------------------------------------------------------------------

class TestGetSummaryStats:
    def test_correct_stats_with_expenses(self):
        uid = _create_user(name="Carol", email="carol@example.com")
        _add_expense(uid, 1000.0, "Food", "2026-05-01", "Groceries")
        _add_expense(uid, 500.0,  "Food", "2026-05-02", "Lunch")
        _add_expense(uid, 2000.0, "Bills", "2026-05-03", "Rent")

        result = get_summary_stats(uid)

        assert result["transaction_count"] == 3
        assert result["total_spent"] == "₹3,500"
        assert result["top_category"] == "Bills"

    def test_zero_stats_with_no_expenses(self):
        uid = _create_user(name="Dave", email="dave@example.com")
        result = get_summary_stats(uid)

        assert result["transaction_count"] == 0
        assert result["total_spent"] == "₹0"
        assert result["top_category"] == "—"


# ---------------------------------------------------------------------------
# get_recent_transactions
# ---------------------------------------------------------------------------

class TestGetRecentTransactions:
    def test_returns_transactions_newest_first(self):
        uid = _create_user(name="Eve", email="eve@example.com")
        _add_expense(uid, 100.0, "Food",      "2026-05-01", "Older")
        _add_expense(uid, 200.0, "Transport", "2026-05-10", "Newer")

        result = get_recent_transactions(uid)

        assert len(result) == 2
        assert result[0]["description"] == "Newer"
        assert result[1]["description"] == "Older"

    def test_result_has_required_keys(self):
        uid = _create_user(name="Frank", email="frank@example.com")
        _add_expense(uid, 450.0, "Food", "2026-05-01", "Grocery run")

        result = get_recent_transactions(uid)

        assert len(result) == 1
        row = result[0]
        assert "date" in row
        assert "description" in row
        assert "category" in row
        assert "amount" in row

    def test_date_is_formatted(self):
        uid = _create_user(name="Grace", email="grace@example.com")
        _add_expense(uid, 100.0, "Other", "2026-05-01", "Test")

        result = get_recent_transactions(uid)
        assert result[0]["date"] == "May 01, 2026"

    def test_amount_has_rupee_symbol(self):
        uid = _create_user(name="Hank", email="hank@example.com")
        _add_expense(uid, 980.0, "Food", "2026-05-15", "Dinner")

        result = get_recent_transactions(uid)
        assert result[0]["amount"] == "₹980"

    def test_empty_list_for_no_expenses(self):
        uid = _create_user(name="Iris", email="iris@example.com")
        assert get_recent_transactions(uid) == []

    def test_limit_is_respected(self):
        uid = _create_user(name="Jack", email="jack@example.com")
        for i in range(15):
            _add_expense(uid, 10.0, "Other", f"2026-05-{i+1:02d}", f"Expense {i}")

        result = get_recent_transactions(uid, limit=5)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# get_category_breakdown
# ---------------------------------------------------------------------------

class TestGetCategoryBreakdown:
    def test_returns_categories_sorted_by_amount(self):
        uid = _create_user(name="Kate", email="kate@example.com")
        _add_expense(uid, 100.0,  "Food",     "2026-05-01", "")
        _add_expense(uid, 2000.0, "Shopping", "2026-05-02", "")
        _add_expense(uid, 500.0,  "Bills",    "2026-05-03", "")

        result = get_category_breakdown(uid)

        assert result[0]["name"] == "Shopping"
        assert result[1]["name"] == "Bills"
        assert result[2]["name"] == "Food"

    def test_pcts_sum_to_100(self):
        uid = _create_user(name="Leo", email="leo@example.com")
        _add_expense(uid, 333.0, "Food",      "2026-05-01", "")
        _add_expense(uid, 333.0, "Transport", "2026-05-02", "")
        _add_expense(uid, 334.0, "Bills",     "2026-05-03", "")

        result = get_category_breakdown(uid)
        assert sum(c["pct"] for c in result) == 100

    def test_amounts_have_rupee_symbol(self):
        uid = _create_user(name="Mia", email="mia@example.com")
        _add_expense(uid, 2200.0, "Shopping", "2026-05-01", "")

        result = get_category_breakdown(uid)
        assert result[0]["amount"] == "₹2,200"

    def test_empty_list_for_no_expenses(self):
        uid = _create_user(name="Ned", email="ned@example.com")
        assert get_category_breakdown(uid) == []


# ---------------------------------------------------------------------------
# Route: GET /profile
# ---------------------------------------------------------------------------

class TestProfileRoute:
    def test_unauthenticated_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]

    def test_authenticated_returns_200(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Demo User"

        response = client.get("/profile")
        assert response.status_code == 200

    def test_profile_shows_real_user_name(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Demo User"

        response = client.get("/profile")
        assert b"Demo User" in response.data

    def test_profile_shows_real_email(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Demo User"

        response = client.get("/profile")
        assert b"demo@spendly.com" in response.data

    def test_profile_contains_rupee_symbol(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Demo User"

        response = client.get("/profile")
        assert "₹".encode() in response.data

    def test_seed_user_total_spent(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Demo User"

        response = client.get("/profile")
        assert b"6,575" in response.data

    def test_seed_user_transaction_count(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Demo User"

        response = client.get("/profile")
        assert b"8" in response.data

    def test_seed_user_top_category(self, client):
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["user_name"] = "Demo User"

        response = client.get("/profile")
        assert b"Shopping" in response.data
