from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db

app = Flask(__name__)
app.secret_key = "spendly-dev-secret"

with app.app_context():
    init_db()
    seed_db()


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

    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "January 2024",
    }
    initials = user["name"][0].upper()

    stats = {
        "total_spent": "₹6,575",
        "transaction_count": 8,
        "top_category": "Shopping",
    }

    expenses = [
        {"date": "May 15, 2026", "description": "Restaurant dinner", "category": "Food",          "amount": "₹980"},
        {"date": "May 10, 2026", "description": "Clothes",           "category": "Shopping",      "amount": "₹2,200"},
        {"date": "May 08, 2026", "description": "Movie tickets",     "category": "Entertainment", "amount": "₹350"},
        {"date": "May 05, 2026", "description": "Pharmacy",          "category": "Health",        "amount": "₹600"},
        {"date": "May 03, 2026", "description": "Electricity bill",  "category": "Bills",         "amount": "₹1,800"},
        {"date": "May 02, 2026", "description": "Auto rickshaw",     "category": "Transport",     "amount": "₹120"},
        {"date": "May 01, 2026", "description": "Grocery run",       "category": "Food",          "amount": "₹450"},
        {"date": "May 12, 2026", "description": "Miscellaneous",     "category": "Other",         "amount": "₹75"},
    ]

    categories = [
        {"name": "Shopping",      "amount": "₹2,200", "pct": 33},
        {"name": "Bills",         "amount": "₹1,800", "pct": 27},
        {"name": "Food",          "amount": "₹1,430", "pct": 22},
        {"name": "Health",        "amount": "₹600",   "pct": 9},
        {"name": "Entertainment", "amount": "₹350",   "pct": 5},
        {"name": "Transport",     "amount": "₹120",   "pct": 2},
        {"name": "Other",         "amount": "₹75",    "pct": 1},
    ]

    return render_template("profile.html",
                           user=user, initials=initials,
                           stats=stats, expenses=expenses,
                           categories=categories)


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
