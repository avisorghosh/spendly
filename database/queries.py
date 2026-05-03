from datetime import datetime
from database.db import get_db


def get_user_by_id(user_id):
    db = get_db()
    try:
        row = db.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if row is None:
            return None
        member_since = datetime.strptime(row["created_at"][:10], "%Y-%m-%d").strftime("%B %Y")
        return {"name": row["name"], "email": row["email"], "member_since": member_since}
    finally:
        db.close()


def _date_where(user_id, date_from, date_to):
    conditions = ["user_id = ?"]
    params: list = [user_id]
    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)
    return "WHERE " + " AND ".join(conditions), params


def get_summary_stats(user_id, *, date_from=None, date_to=None):
    db = get_db()
    try:
        where, params = _date_where(user_id, date_from, date_to)

        row = db.execute(
            "SELECT SUM(amount), COUNT(*) FROM expenses " + where,
            params
        ).fetchone()
        total, count = row[0], row[1]

        if total is None or count == 0:
            return {"total_spent": "₹0", "transaction_count": 0, "top_category": "—"}

        top_row = db.execute(
            "SELECT category FROM expenses " + where +
            " GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            params
        ).fetchone()
        top_category = top_row[0] if top_row else "—"

        return {
            "total_spent": f"₹{int(total):,}",
            "transaction_count": int(count),
            "top_category": top_category,
        }
    finally:
        db.close()


def get_recent_transactions(user_id, limit=10, *, date_from=None, date_to=None):
    db = get_db()
    try:
        where, params = _date_where(user_id, date_from, date_to)

        rows = db.execute(
            "SELECT amount, category, date, description FROM expenses "
            + where + " ORDER BY date DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        transactions = []
        for row in rows:
            transactions.append({
                "date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%B %d, %Y"),
                "description": row["description"],
                "category": row["category"],
                "amount": f"₹{int(row['amount']):,}",
            })
        return transactions
    finally:
        db.close()


def get_category_breakdown(user_id, *, date_from=None, date_to=None):
    db = get_db()
    try:
        where, params = _date_where(user_id, date_from, date_to)

        rows = db.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            + where + " GROUP BY category ORDER BY total DESC",
            params,
        ).fetchall()
        if not rows:
            return []
        grand_total = sum(row["total"] for row in rows)
        pcts = [round(row["total"] / grand_total * 100) for row in rows]
        remainder = 100 - sum(pcts)
        pcts[0] += remainder
        return [
            {
                "name": row["category"],
                "amount": f"₹{int(row['total']):,}",
                "pct": pcts[i],
            }
            for i, row in enumerate(rows)
        ]
    finally:
        db.close()
