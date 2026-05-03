import re
from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db
from database.queries import get_user_by_id, get_summary_stats, get_recent_transactions, get_category_breakdown

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"

with app.app_context():
    init_db()
    seed_db()


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_date(value):
    return value if value and _DATE_RE.match(value) else None


def _build_date_presets():
    today = date.today()
    first_of_month = today.replace(day=1)
    last_month_end = first_of_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    return [
        {"label": "This Month",    "date_from": first_of_month.isoformat(),               "date_to": today.isoformat()},
        {"label": "Last Month",    "date_from": last_month_start.isoformat(),             "date_to": last_month_end.isoformat()},
        {"label": "Last 3 Months", "date_from": (today - timedelta(days=90)).isoformat(), "date_to": today.isoformat()},
        {"label": "All Time",      "date_from": None,                                     "date_to": None},
    ]


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("profile"))
        return render_template("register.html")

    name     = request.form.get("name", "").strip()
    email    = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template("register.html", error="All fields are required.")

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        db.close()
        return render_template("register.html", error="An account with that email already exists.")

    cursor = db.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, generate_password_hash(password))
    )
    db.commit()
    new_id = cursor.lastrowid
    db.close()

    session["user_id"]   = new_id
    session["user_name"] = name
    return redirect(url_for("profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("profile"))
        return render_template("login.html")

    email    = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    db  = get_db()
    row = db.execute(
        "SELECT id, name, password_hash FROM users WHERE email = ?", (email,)
    ).fetchone()
    db.close()

    if row is None or not check_password_hash(row["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"]   = row["id"]
    session["user_name"] = row["name"]
    return redirect(url_for("profile"))


@app.route("/dashboard")
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("dashboard.html", user_name=session["user_name"])


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    presets = _build_date_presets()

    date_from = _valid_date(request.args.get("date_from"))
    date_to   = _valid_date(request.args.get("date_to"))
    if not (date_from and date_to):
        date_from = date_to = None

    active_range = "All Time"
    for p in presets:
        if date_from == p["date_from"] and date_to == p["date_to"]:
            active_range = p["label"]
            break

    initials = user["name"][0].upper()
    stats = get_summary_stats(user_id, date_from=date_from, date_to=date_to)
    expenses = get_recent_transactions(user_id, date_from=date_from, date_to=date_to)
    categories = get_category_breakdown(user_id, date_from=date_from, date_to=date_to)

    return render_template("profile.html",
                           user=user, initials=initials,
                           stats=stats, expenses=expenses,
                           categories=categories,
                           presets=presets, active_range=active_range)


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
