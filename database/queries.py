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


def get_summary_stats(user_id):
    db = get_db()
    try:
        row = db.execute(
            "SELECT SUM(amount), COUNT(*) FROM expenses WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        total, count = row[0], row[1]

        if total is None or count == 0:
            return {"total_spent": "₹0", "transaction_count": 0, "top_category": "—"}

        top_row = db.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        top_category = top_row[0] if top_row else "—"

        return {
            "total_spent": f"₹{int(total):,}",
            "transaction_count": int(count),
            "top_category": top_category,
        }
    finally:
        db.close()


def get_recent_transactions(user_id, limit=10):
    db = get_db()
    try:
        rows = db.execute(
            "SELECT amount, category, date, description FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit),
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


def get_category_breakdown(user_id):
    db = get_db()
    try:
        rows = db.execute(
            "SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
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
