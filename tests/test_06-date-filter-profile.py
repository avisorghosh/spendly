"""
tests/test_06-date-filter-profile.py

Tests for Step 06: Date Filter for Profile Page.

Strategy
--------
- Route / integration tests reuse the real seeded DB (via the shared conftest
  client fixture) because the seed data is entirely in May 2026, which makes
  date-range assertions deterministic when we freeze `date.today()` to
  2026-05-04 via unittest.mock.patch.
- Query helper unit tests create their own isolated user so that seed data
  from the demo account never bleeds into assertions about filtered results.
"""

import pytest
from unittest.mock import patch
from datetime import date

from database.queries import (
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)
from database.db import get_db
from werkzeug.security import generate_password_hash

# ---------------------------------------------------------------------------
# Frozen "today" for all tests that touch date-relative logic.
# The seed data spans 2026-05-01 to 2026-05-15.  Freezing at 2026-05-04
# means "This Month" covers only the first four days of May and "Last Month"
# covers April (which has no seed data).
# ---------------------------------------------------------------------------
FROZEN_TODAY = date(2026, 5, 4)
FROZEN_TODAY_ISO = FROZEN_TODAY.isoformat()          # "2026-05-04"
THIS_MONTH_FROM = "2026-05-01"                       # first day of May 2026
THIS_MONTH_TO   = FROZEN_TODAY_ISO                   # "2026-05-04"
LAST_MONTH_FROM = "2026-04-01"
LAST_MONTH_TO   = "2026-04-30"
LAST_3M_FROM    = "2026-02-03"   # FROZEN_TODAY - 90 days
LAST_3M_TO      = FROZEN_TODAY_ISO


# ---------------------------------------------------------------------------
# Helpers for isolated query-unit tests
# ---------------------------------------------------------------------------

def _create_isolated_user(suffix: str) -> int:
    """Insert a fresh user (or reuse one with the same email) for isolated unit tests."""
    db = get_db()
    email = f"isolated_{suffix}@test.com"
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        db.execute("DELETE FROM expenses WHERE user_id = ?", (existing["id"],))
        db.commit()
        db.close()
        return existing["id"]
    cursor = db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (f"Isolated {suffix}", email, generate_password_hash("x")),
    )
    uid = cursor.lastrowid
    db.commit()
    db.close()
    return uid


def _add_expense(user_id: int, amount: float, category: str, iso_date: str, desc: str = "") -> None:
    db = get_db()
    db.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, iso_date, desc),
    )
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Helper: set session so client acts as the seeded demo user (id=1)
# ---------------------------------------------------------------------------

def _login_as_demo(client):
    with client.session_transaction() as sess:
        sess["user_id"]   = 1
        sess["user_name"] = "Demo User"


# ===========================================================================
# AUTH GUARD
# ===========================================================================

class TestAuthGuard:
    def test_unauthenticated_get_profile_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, "Unauthenticated /profile must redirect (302)"
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_unauthenticated_get_profile_with_date_params_redirects_to_login(self, client):
        response = client.get(f"/profile?date_from={THIS_MONTH_FROM}&date_to={THIS_MONTH_TO}")
        assert response.status_code == 302, "Auth guard must apply even when query params are present"
        assert "/login" in response.headers["Location"]


# ===========================================================================
# DEFAULT VIEW — no query params, All Time
# ===========================================================================

class TestDefaultAllTime:
    def test_returns_200(self, client):
        _login_as_demo(client)
        response = client.get("/profile")
        assert response.status_code == 200, "Authenticated /profile must return 200"

    def test_all_eight_seed_transactions_present(self, client):
        """All 8 seed expenses should appear in the unfiltered view."""
        _login_as_demo(client)
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        # The seed data has 8 transactions; the stat value must appear on the page.
        assert "8" in data, "Transaction count of 8 must appear for All Time view"

    def test_full_total_spent_shown(self, client):
        """Seed total = 450+120+1800+600+350+2200+75+980 = 6,575."""
        _login_as_demo(client)
        response = client.get("/profile")
        assert b"6,575" in response.data, "Full seed total ₹6,575 must appear in All Time view"

    def test_top_category_is_shopping(self, client):
        _login_as_demo(client)
        response = client.get("/profile")
        assert b"Shopping" in response.data, "Top category must be Shopping for All Time seed data"

    def test_heading_is_plain_transaction_history(self, client):
        """All Time produces no suffix on the section heading."""
        _login_as_demo(client)
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        assert "Transaction History" in data, "Section heading must contain 'Transaction History'"
        assert "Transaction History —" not in data, (
            "All Time must NOT append a label to the heading"
        )

    def test_all_time_button_is_active(self, client):
        """The 'All Time' button must carry the filter-btn--active class."""
        _login_as_demo(client)
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        # The active button text and class must appear together in the markup.
        assert "filter-btn--active" in data, "Some button must have filter-btn--active class"
        # Verify the active region contains 'All Time'
        active_idx = data.find("filter-btn--active")
        surrounding = data[active_idx: active_idx + 100]
        assert "All Time" in surrounding, (
            "The filter-btn--active element must be the All Time button when no params are given"
        )

    def test_filter_bar_is_present(self, client):
        _login_as_demo(client)
        response = client.get("/profile")
        assert b"filter-bar" in response.data, "Filter bar container must be present in the page"

    def test_four_preset_buttons_present(self, client):
        _login_as_demo(client)
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        for label in ("This Month", "Last Month", "Last 3 Months", "All Time"):
            assert label in data, f"Preset button '{label}' must appear in the filter bar"

    def test_user_info_card_present(self, client):
        _login_as_demo(client)
        response = client.get("/profile")
        assert b"Demo User" in response.data, "User info card must show name"
        assert b"demo@spendly.com" in response.data, "User info card must show email"


# ===========================================================================
# THIS MONTH FILTER  (frozen to 2026-05-04)
# Seed expenses on/before 2026-05-04: 2026-05-01, 2026-05-02, 2026-05-03 → 3 rows
# ===========================================================================

class TestThisMonthFilter:
    def _get(self, client):
        _login_as_demo(client)
        with patch("app.date") as mock_date:
            mock_date.today.return_value = FROZEN_TODAY
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            return client.get(
                f"/profile?date_from={THIS_MONTH_FROM}&date_to={THIS_MONTH_TO}"
            )

    def test_returns_200(self, client):
        response = self._get(client)
        assert response.status_code == 200

    def test_heading_contains_this_month_label(self, client):
        response = self._get(client)
        data = response.data.decode("utf-8")
        assert "Transaction History — This Month" in data, (
            "Heading must append '— This Month' when this-month filter is active"
        )

    def test_this_month_button_is_active(self, client):
        response = self._get(client)
        data = response.data.decode("utf-8")
        active_idx = data.find("filter-btn--active")
        surrounding = data[active_idx: active_idx + 100]
        assert "This Month" in surrounding, (
            "The filter-btn--active element must be 'This Month'"
        )

    def test_only_expenses_up_to_frozen_today_appear(self, client):
        """
        With date_to=2026-05-04 the seed data matching dates are:
        2026-05-01 (Grocery run), 2026-05-02 (Auto rickshaw), 2026-05-03 (Electricity bill).
        The expenses dated 2026-05-05 and later must NOT appear.
        """
        response = self._get(client)
        assert b"Grocery run" in response.data, "2026-05-01 expense must appear"
        assert b"Auto rickshaw" in response.data, "2026-05-02 expense must appear"
        assert b"Electricity bill" in response.data, "2026-05-03 expense must appear"
        assert b"Pharmacy" not in response.data, "2026-05-05 expense must be excluded"
        assert b"Movie tickets" not in response.data, "2026-05-08 expense must be excluded"
        assert b"Restaurant dinner" not in response.data, "2026-05-15 expense must be excluded"

    def test_transaction_count_is_three(self, client):
        response = self._get(client)
        # stat value "3" should appear in the stats row; we verify the total too
        # (450 + 120 + 1800 = 2,370)
        assert b"2,370" in response.data, "This Month total must be ₹2,370 for the 3 matching expenses"

    def test_no_empty_state_message(self, client):
        response = self._get(client)
        assert b"No transactions in this period." not in response.data, (
            "Empty state must not appear when there are matching expenses"
        )

    def test_user_info_card_unaffected(self, client):
        response = self._get(client)
        assert b"Demo User" in response.data, "User info card must still show name under filter"
        assert b"demo@spendly.com" in response.data, "User info card must still show email under filter"


# ===========================================================================
# LAST MONTH FILTER  (frozen to 2026-05-04 → Last Month = April 2026)
# No seed expenses exist in April 2026 → empty state
# ===========================================================================

class TestLastMonthFilter:
    def _get(self, client):
        _login_as_demo(client)
        with patch("app.date") as mock_date:
            mock_date.today.return_value = FROZEN_TODAY
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            return client.get(
                f"/profile?date_from={LAST_MONTH_FROM}&date_to={LAST_MONTH_TO}"
            )

    def test_returns_200(self, client):
        response = self._get(client)
        assert response.status_code == 200

    def test_empty_state_message_shown(self, client):
        response = self._get(client)
        assert b"No transactions in this period." in response.data, (
            "Empty state message must appear when no expenses exist in the date range"
        )

    def test_stats_show_zero_total(self, client):
        response = self._get(client)
        assert "₹0".encode() in response.data, (
            "Total spent must be ₹0 when no expenses match the filter"
        )

    def test_stats_show_zero_transaction_count(self, client):
        response = self._get(client)
        data = response.data.decode("utf-8")
        # transaction_count = 0 must appear in the stats row
        assert ">0<" in data or "stat-value\">0" in data or ">0</span>" in data, (
            "Transaction count must be 0 when no expenses match"
        )

    def test_stats_show_dash_top_category(self, client):
        response = self._get(client)
        # The em dash or plain dash for top_category
        assert b"\xe2\x80\x94" in response.data or b"&mdash;" in response.data or b"\xe2\x80\x94" in response.data, (
            "Top category must show — when no expenses match"
        )

    def test_last_month_button_is_active(self, client):
        response = self._get(client)
        data = response.data.decode("utf-8")
        active_idx = data.find("filter-btn--active")
        surrounding = data[active_idx: active_idx + 100]
        assert "Last Month" in surrounding, (
            "The filter-btn--active element must be 'Last Month'"
        )

    def test_heading_contains_last_month_label(self, client):
        response = self._get(client)
        data = response.data.decode("utf-8")
        assert "Transaction History — Last Month" in data, (
            "Heading must append '— Last Month' when last-month filter is active"
        )

    def test_user_info_card_unaffected(self, client):
        response = self._get(client)
        assert b"Demo User" in response.data
        assert b"demo@spendly.com" in response.data


# ===========================================================================
# LAST 3 MONTHS FILTER  (frozen to 2026-05-04 → from 2026-02-03 to 2026-05-04)
# Seed expenses from 2026-05-01 to 2026-05-04 fall in range → 3 rows
# ===========================================================================

class TestLast3MonthsFilter:
    def _get(self, client):
        _login_as_demo(client)
        with patch("app.date") as mock_date:
            mock_date.today.return_value = FROZEN_TODAY
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            return client.get(
                f"/profile?date_from={LAST_3M_FROM}&date_to={LAST_3M_TO}"
            )

    def test_returns_200(self, client):
        response = self._get(client)
        assert response.status_code == 200

    def test_heading_contains_last_3_months_label(self, client):
        response = self._get(client)
        data = response.data.decode("utf-8")
        assert "Transaction History — Last 3 Months" in data, (
            "Heading must append '— Last 3 Months' when last-3-months filter is active"
        )

    def test_last_3_months_button_is_active(self, client):
        response = self._get(client)
        data = response.data.decode("utf-8")
        active_idx = data.find("filter-btn--active")
        surrounding = data[active_idx: active_idx + 120]
        assert "Last 3 Months" in surrounding, (
            "The filter-btn--active element must be 'Last 3 Months'"
        )

    def test_expenses_within_range_are_shown(self, client):
        """Expenses dated 2026-05-01 through 2026-05-04 must appear."""
        response = self._get(client)
        assert b"Grocery run" in response.data, "2026-05-01 expense must appear"
        assert b"Auto rickshaw" in response.data, "2026-05-02 expense must appear"
        assert b"Electricity bill" in response.data, "2026-05-03 expense must appear"

    def test_expenses_outside_range_not_shown(self, client):
        """Expenses dated after 2026-05-04 must NOT appear."""
        response = self._get(client)
        assert b"Pharmacy" not in response.data, "2026-05-05 expense must be excluded"
        assert b"Restaurant dinner" not in response.data, "2026-05-15 expense must be excluded"

    def test_no_empty_state_message(self, client):
        response = self._get(client)
        assert b"No transactions in this period." not in response.data

    def test_user_info_card_unaffected(self, client):
        response = self._get(client)
        assert b"Demo User" in response.data
        assert b"demo@spendly.com" in response.data


# ===========================================================================
# DIRECT URL — explicit May 2026 date range covers all 8 seed expenses
# ===========================================================================

class TestDirectUrlFilter:
    def test_explicit_full_may_range_returns_all_seed_expenses(self, client):
        """
        GET /profile?date_from=2026-05-01&date_to=2026-05-31
        All 8 seed expenses fall in May 2026, so all should appear.
        """
        _login_as_demo(client)
        response = client.get("/profile?date_from=2026-05-01&date_to=2026-05-31")
        assert response.status_code == 200
        assert b"6,575" in response.data, (
            "All 8 seed expenses totalling ₹6,575 must appear for the full May range"
        )
        assert b"Restaurant dinner" in response.data, "Last seed expense (2026-05-15) must be included"
        assert b"Grocery run" in response.data, "First seed expense (2026-05-01) must be included"

    def test_explicit_range_heading_not_all_time(self, client):
        """A custom range that doesn't match any preset gets 'All Time' active (fallback)."""
        _login_as_demo(client)
        response = client.get("/profile?date_from=2026-05-01&date_to=2026-05-31")
        data = response.data.decode("utf-8")
        # date_from=2026-05-01 & date_to=2026-05-31 does NOT match any preset computed
        # relative to 2026-05-04, so active_range falls back to All Time and the heading
        # has no suffix.
        assert "Transaction History —" not in data, (
            "Unrecognised date params must fall back to All Time (no heading suffix)"
        )

    def test_explicit_may_1_to_4_matches_this_month_preset_behavior(self, client):
        """
        date_from=2026-05-01&date_to=2026-05-04 is the exact This Month preset when
        today is frozen to 2026-05-04.  Filtered results must match (3 expenses).
        """
        _login_as_demo(client)
        # Note: we're passing exact strings that match the preset computed for 2026-05-04,
        # so the active_range detection will label this 'This Month' only if the
        # server also uses the same frozen date.  We patch for this test.
        with patch("app.date") as mock_date:
            mock_date.today.return_value = FROZEN_TODAY
            mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
            response = client.get(
                f"/profile?date_from={THIS_MONTH_FROM}&date_to={THIS_MONTH_TO}"
            )
        assert b"2,370" in response.data, (
            "3 expenses totalling ₹2,370 must appear for the This Month date range"
        )
        assert b"Pharmacy" not in response.data, "Expense after date_to must be excluded"


# ===========================================================================
# ACTIVE BUTTON FALLBACK — unrecognised params → All Time active
# ===========================================================================

class TestActiveFallback:
    def test_unknown_date_range_activates_all_time_button(self, client):
        """
        When date params don't match any preset the server falls back to All Time.
        The All Time button must carry filter-btn--active.
        """
        _login_as_demo(client)
        response = client.get("/profile?date_from=2023-01-01&date_to=2023-12-31")
        assert response.status_code == 200
        data = response.data.decode("utf-8")
        active_idx = data.find("filter-btn--active")
        assert active_idx != -1, "filter-btn--active must exist in the page"
        surrounding = data[active_idx: active_idx + 100]
        assert "All Time" in surrounding, (
            "All Time button must be active when params match no preset"
        )

    def test_no_date_params_activates_all_time_button(self, client):
        _login_as_demo(client)
        response = client.get("/profile")
        data = response.data.decode("utf-8")
        active_idx = data.find("filter-btn--active")
        surrounding = data[active_idx: active_idx + 100]
        assert "All Time" in surrounding


# ===========================================================================
# EMPTY STATE — a date range with no matching expenses
# ===========================================================================

class TestEmptyState:
    def test_empty_range_shows_no_transactions_message(self, client):
        _login_as_demo(client)
        response = client.get("/profile?date_from=2020-01-01&date_to=2020-01-31")
        assert response.status_code == 200
        assert b"No transactions in this period." in response.data, (
            "Empty-state message must appear when no expenses exist in the given range"
        )

    def test_empty_range_shows_zero_total(self, client):
        _login_as_demo(client)
        response = client.get("/profile?date_from=2020-01-01&date_to=2020-01-31")
        assert "₹0".encode() in response.data, "₹0 must appear in stats for empty date range"

    def test_empty_range_shows_dash_top_category(self, client):
        _login_as_demo(client)
        response = client.get("/profile?date_from=2020-01-01&date_to=2020-01-31")
        # The em-dash character is rendered directly in the template
        assert "—".encode("utf-8") in response.data, (
            "Top category must be — when no expenses match"
        )

    def test_empty_range_user_card_still_shows(self, client):
        _login_as_demo(client)
        response = client.get("/profile?date_from=2020-01-01&date_to=2020-01-31")
        assert b"Demo User" in response.data, "User info card must be unaffected by empty filter"

    def test_category_breakdown_empty_for_no_expenses(self, client):
        """When the filter yields no expenses the category breakdown section must be empty."""
        _login_as_demo(client)
        response = client.get("/profile?date_from=2020-01-01&date_to=2020-01-31")
        # None of the seed categories should appear in this filtered response
        for cat in ("Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"):
            assert cat.encode() not in response.data, (
                f"Category '{cat}' must not appear in breakdown when filter returns no data"
            )


# ===========================================================================
# QUERY HELPER UNIT TESTS — get_summary_stats
# ===========================================================================

class TestGetSummaryStatsDateBounds:
    def test_no_bounds_returns_all_expenses(self):
        uid = _create_isolated_user("stats_all")
        _add_expense(uid, 1000.0, "Food",  "2026-04-10", "April food")
        _add_expense(uid, 500.0,  "Bills", "2026-05-01", "May bill")

        result = get_summary_stats(uid)

        assert result["transaction_count"] == 2, "No bounds must count all expenses"
        assert result["total_spent"] == "₹1,500", "No bounds total must sum all expenses"

    def test_with_bounds_returns_subset(self):
        uid = _create_isolated_user("stats_subset")
        _add_expense(uid, 1000.0, "Food",  "2026-04-10", "April food")
        _add_expense(uid, 500.0,  "Bills", "2026-05-01", "May bill")

        result = get_summary_stats(uid, date_from="2026-05-01", date_to="2026-05-31")

        assert result["transaction_count"] == 1, "Bounds must exclude April expense"
        assert result["total_spent"] == "₹500", "Total must reflect only the May expense"
        assert result["top_category"] == "Bills"

    def test_bounds_with_no_matching_expenses_returns_zero_stats(self):
        uid = _create_isolated_user("stats_empty")
        _add_expense(uid, 1000.0, "Food", "2026-05-01", "May food")

        result = get_summary_stats(uid, date_from="2026-04-01", date_to="2026-04-30")

        assert result["transaction_count"] == 0
        assert result["total_spent"] == "₹0"
        assert result["top_category"] == "—"

    def test_bounds_include_boundary_dates(self):
        """date_from and date_to are inclusive (>= and <=)."""
        uid = _create_isolated_user("stats_boundary")
        _add_expense(uid, 200.0, "Food", "2026-05-01", "Boundary start")
        _add_expense(uid, 300.0, "Food", "2026-05-31", "Boundary end")
        _add_expense(uid, 999.0, "Food", "2026-06-01", "Just outside")

        result = get_summary_stats(uid, date_from="2026-05-01", date_to="2026-05-31")

        assert result["transaction_count"] == 2, "Both boundary dates must be included"
        assert result["total_spent"] == "₹500"

    def test_top_category_reflects_filtered_expenses(self):
        uid = _create_isolated_user("stats_topcategory")
        _add_expense(uid, 100.0,  "Food",      "2026-04-01", "old food")
        _add_expense(uid, 5000.0, "Shopping",  "2026-04-02", "old shopping")
        _add_expense(uid, 300.0,  "Transport", "2026-05-01", "new transport")
        _add_expense(uid, 200.0,  "Food",      "2026-05-02", "new food")

        # Without bounds: top is Shopping (5000)
        all_time = get_summary_stats(uid)
        assert all_time["top_category"] == "Shopping"

        # With bounds restricted to May: top is Transport (300) > Food (200)
        may_result = get_summary_stats(uid, date_from="2026-05-01", date_to="2026-05-31")
        assert may_result["top_category"] == "Transport"


# ===========================================================================
# QUERY HELPER UNIT TESTS — get_recent_transactions
# ===========================================================================

class TestGetRecentTransactionsDateBounds:
    def test_no_bounds_returns_all_transactions(self):
        uid = _create_isolated_user("txn_all")
        _add_expense(uid, 100.0, "Food",      "2026-04-01", "April")
        _add_expense(uid, 200.0, "Transport", "2026-05-01", "May")

        result = get_recent_transactions(uid)

        assert len(result) == 2, "No bounds must return all transactions"

    def test_with_bounds_returns_only_matching_rows(self):
        uid = _create_isolated_user("txn_filtered")
        _add_expense(uid, 100.0, "Food",      "2026-04-01", "April food")
        _add_expense(uid, 200.0, "Transport", "2026-05-01", "May transport")
        _add_expense(uid, 300.0, "Bills",     "2026-06-01", "June bills")

        result = get_recent_transactions(uid, date_from="2026-05-01", date_to="2026-05-31")

        assert len(result) == 1, "Only the May expense must be returned"
        assert result[0]["description"] == "May transport"

    def test_with_bounds_returns_empty_list_when_no_match(self):
        uid = _create_isolated_user("txn_empty")
        _add_expense(uid, 100.0, "Food", "2026-05-01", "May food")

        result = get_recent_transactions(uid, date_from="2026-04-01", date_to="2026-04-30")

        assert result == [], "Empty list must be returned when no transactions match the bounds"

    def test_bounds_ordering_is_newest_first(self):
        uid = _create_isolated_user("txn_order")
        _add_expense(uid, 100.0, "Food",      "2026-05-01", "First")
        _add_expense(uid, 200.0, "Transport", "2026-05-10", "Last")

        result = get_recent_transactions(uid, date_from="2026-05-01", date_to="2026-05-31")

        assert len(result) == 2
        assert result[0]["description"] == "Last", "Newest expense must come first"
        assert result[1]["description"] == "First"

    def test_bounds_include_boundary_dates(self):
        uid = _create_isolated_user("txn_boundary")
        _add_expense(uid, 50.0,  "Other", "2026-05-01", "Start boundary")
        _add_expense(uid, 50.0,  "Other", "2026-05-31", "End boundary")
        _add_expense(uid, 999.0, "Other", "2026-06-01", "Excluded")

        result = get_recent_transactions(uid, date_from="2026-05-01", date_to="2026-05-31")

        descriptions = [r["description"] for r in result]
        assert "Start boundary" in descriptions
        assert "End boundary" in descriptions
        assert "Excluded" not in descriptions

    def test_amount_formatted_with_rupee_symbol_under_bounds(self):
        uid = _create_isolated_user("txn_rupee")
        _add_expense(uid, 1500.0, "Bills", "2026-05-05", "Filtered expense")

        result = get_recent_transactions(uid, date_from="2026-05-01", date_to="2026-05-31")

        assert len(result) == 1
        assert result[0]["amount"] == "₹1,500", "Amount must be formatted with ₹ and comma separator"

    def test_limit_respected_with_date_bounds(self):
        uid = _create_isolated_user("txn_limit")
        for day in range(1, 11):  # 10 expenses in May
            _add_expense(uid, 100.0, "Food", f"2026-05-{day:02d}", f"Expense {day}")

        result = get_recent_transactions(uid, limit=3, date_from="2026-05-01", date_to="2026-05-31")

        assert len(result) == 3, "Limit must be respected even when date bounds are provided"


# ===========================================================================
# QUERY HELPER UNIT TESTS — get_category_breakdown
# ===========================================================================

class TestGetCategoryBreakdownDateBounds:
    def test_no_bounds_returns_all_categories(self):
        uid = _create_isolated_user("cat_all")
        _add_expense(uid, 200.0, "Food",      "2026-04-01", "")
        _add_expense(uid, 300.0, "Transport", "2026-05-01", "")

        result = get_category_breakdown(uid)

        names = [c["name"] for c in result]
        assert "Food" in names
        assert "Transport" in names

    def test_with_bounds_returns_only_matching_categories(self):
        uid = _create_isolated_user("cat_filtered")
        _add_expense(uid, 200.0, "Food",      "2026-04-01", "April food")
        _add_expense(uid, 300.0, "Transport", "2026-05-01", "May transport")
        _add_expense(uid, 100.0, "Bills",     "2026-05-15", "May bills")

        result = get_category_breakdown(uid, date_from="2026-05-01", date_to="2026-05-31")

        names = [c["name"] for c in result]
        assert "Food" not in names, "April category must be excluded by date bounds"
        assert "Transport" in names
        assert "Bills" in names

    def test_with_bounds_returns_empty_list_when_no_match(self):
        uid = _create_isolated_user("cat_empty")
        _add_expense(uid, 500.0, "Shopping", "2026-05-10", "May shopping")

        result = get_category_breakdown(uid, date_from="2026-04-01", date_to="2026-04-30")

        assert result == [], "Empty list must be returned when no expenses match the bounds"

    def test_pcts_sum_to_100_under_bounds(self):
        uid = _create_isolated_user("cat_pct")
        _add_expense(uid, 400.0, "Food",      "2026-05-01", "")
        _add_expense(uid, 300.0, "Transport", "2026-05-02", "")
        _add_expense(uid, 300.0, "Bills",     "2026-05-03", "")
        # Expense outside filter range — must not affect percentages
        _add_expense(uid, 9999.0, "Other",   "2026-04-01", "")

        result = get_category_breakdown(uid, date_from="2026-05-01", date_to="2026-05-31")

        assert sum(c["pct"] for c in result) == 100, (
            "Category percentages must sum to 100 when date bounds are applied"
        )

    def test_categories_sorted_by_amount_under_bounds(self):
        uid = _create_isolated_user("cat_sorted")
        _add_expense(uid, 100.0,  "Food",      "2026-05-01", "")
        _add_expense(uid, 2000.0, "Shopping",  "2026-05-02", "")
        _add_expense(uid, 500.0,  "Transport", "2026-05-03", "")

        result = get_category_breakdown(uid, date_from="2026-05-01", date_to="2026-05-31")

        assert result[0]["name"] == "Shopping", "Highest-spend category must be first"
        assert result[1]["name"] == "Transport"
        assert result[2]["name"] == "Food"

    def test_amounts_formatted_with_rupee_under_bounds(self):
        uid = _create_isolated_user("cat_rupee")
        _add_expense(uid, 3500.0, "Health", "2026-05-05", "")

        result = get_category_breakdown(uid, date_from="2026-05-01", date_to="2026-05-31")

        assert len(result) == 1
        assert result[0]["amount"] == "₹3,500", "Category amount must carry ₹ symbol and comma"

    def test_bounds_include_boundary_dates_for_categories(self):
        uid = _create_isolated_user("cat_boundary")
        _add_expense(uid, 100.0, "Food", "2026-05-01", "start")
        _add_expense(uid, 100.0, "Food", "2026-05-31", "end")
        _add_expense(uid, 100.0, "Food", "2026-06-01", "excluded")

        result = get_category_breakdown(uid, date_from="2026-05-01", date_to="2026-05-31")

        assert len(result) == 1
        assert result[0]["name"] == "Food"
        assert result[0]["amount"] == "₹200", (
            "Both boundary dates must be included; excluded date must not contribute"
        )
