# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter bar to the profile page so users can narrow their
transaction history, summary stats, and category breakdown to a specific period.
The page currently shows all-time data; this step introduces four preset filters
(This Month, Last Month, Last 3 Months, All Time) rendered as a button strip above
the stats row. Selecting a preset submits a GET request with `date_from` and
`date_to` query parameters; the backend passes those bounds into the existing query
helpers so all three dynamic sections update together. The user info card is
unaffected by the filter.

## Depends on
- Step 1: Database setup (`expenses` table with `date` column in `YYYY-MM-DD` format)
- Step 3: Login / Logout (session auth guard on `/profile`)
- Step 5: Backend routes for profile page (`database/queries.py` query helpers exist)

## Routes
No new routes. The existing `GET /profile` route is modified to accept optional
query parameters `date_from` and `date_to` (ISO 8601 strings: `YYYY-MM-DD`).

## Database changes
No database changes. The `expenses.date` column (`TEXT NOT NULL`) already stores
ISO 8601 dates that SQLite can filter with `>=` / `<=` comparisons.

## Templates
- **Modify**: `templates/profile.html`
  - Add a filter bar between the user info card and the stats row.
  - The bar contains four preset buttons: **This Month**, **Last Month**,
    **Last 3 Months**, **All Time**.
  - Each button is an `<a>` tag linking to `/profile?date_from=…&date_to=…`
    (or `/profile` for All Time).
  - The active preset button receives the CSS class `filter-btn--active`.
  - The section heading above transactions reads
    "Transaction History" for All Time, or
    "Transaction History — [Label]" when a filter is active (e.g.
    "Transaction History — This Month").
  - When a filter yields zero transactions, the table body shows a single
    "No transactions in this period." row spanning all columns.

## Files to change
- `app.py` — update the `profile()` view to:
  1. Read `date_from` and `date_to` from `request.args` (both default to `None`).
  2. Determine the active preset label and compute `date_from`/`date_to` for
     each preset using Python's `datetime` module (no third-party date library).
  3. Pass `date_from`, `date_to`, and `active_range` to the template context.
  4. Pass the computed bounds to the three query helpers.
- `database/queries.py` — update three helpers to accept optional date bounds:
  - `get_summary_stats(user_id, date_from=None, date_to=None)`
  - `get_recent_transactions(user_id, limit=10, date_from=None, date_to=None)`
  - `get_category_breakdown(user_id, date_from=None, date_to=None)`
  - When bounds are provided, append `AND date >= ? AND date <= ?` to the WHERE
    clause using parameterised queries. When `None`, queries are unchanged.

## Files to create
- `static/css/profile-filter.css` — styles for the filter bar and active button
  state; must use CSS variables only (no hardcoded hex values).

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles (except the existing `style="width: {{ c.pct }}%"` on cat-fill,
  which is data-driven and acceptable)
- Date arithmetic must use Python's `datetime` / `date` stdlib only — no `dateutil`,
  `arrow`, or other third-party packages
- Preset date ranges are computed relative to today (`datetime.today().date()`):
  - **This Month**: first day of current month → today
  - **Last Month**: first day of previous month → last day of previous month
  - **Last 3 Months**: date 90 days before today → today
  - **All Time**: no bounds (both params `None`)
- The active preset is detected by comparing the incoming `date_from`/`date_to`
  query params against the computed ranges for each preset; fall back to
  All Time if no match
- `get_user_by_id` is not modified — the user info card is always unfiltered
- Existing function signatures in `queries.py` must remain backwards-compatible
  (new params are keyword-only with `None` defaults)

## Definition of done
- [ ] The profile page shows a filter bar with four preset buttons above the stats row
- [ ] Clicking **This Month** reloads the page and shows only expenses from the
      current calendar month in the transaction table, stats, and category breakdown
- [ ] Clicking **Last Month** shows only expenses from the previous calendar month
- [ ] Clicking **Last 3 Months** shows expenses from the last 90 days
- [ ] Clicking **All Time** shows all expenses (the default, no query params in URL)
- [ ] The active filter button is visually distinct from the inactive ones
- [ ] Summary stats (total spent, transaction count, top category) reflect the
      filtered date range
- [ ] Category breakdown reflects the filtered date range
- [ ] Selecting a filter with no matching expenses shows "No transactions in this
      period." in the table and ₹0 / 0 / — in the stats, without any errors
- [ ] The user info card (name, email, member since) is unchanged regardless of filter
- [ ] Navigating directly to `/profile?date_from=2026-05-01&date_to=2026-05-31`
      produces the same result as clicking **This Month** during May 2026
