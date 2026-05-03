# Spec: Registration

## Overview
Step 2 wires up the registration and login forms that already exist in the UI. It adds POST handlers for `/register` and `/login`, sets up Flask sessions with a secret key, and creates a minimal `/dashboard` page so users have a landing destination after authenticating. This is the first step where a user can create an account and persist identity across requests.

## Depends on
- Step 1 (Database Setup) — requires the `users` table and `get_db()` to be in place.

## Routes
- `POST /register` — validate form fields, check for duplicate email, hash password, insert user row, set session, redirect to `/dashboard` — public
- `POST /login` — look up user by email, verify password hash, set session, redirect to `/dashboard` — public
- `GET /dashboard` — render a welcome page showing the logged-in user's name — logged-in only (redirect to `/login` if not authenticated)

## Database changes
No database changes. The `users` table with `id`, `name`, `email`, `password_hash`, and `created_at` was created in Step 1.

## Templates
- **Create:** `templates/dashboard.html` — minimal logged-in landing page showing the user's name and a placeholder message
- **Modify:** `templates/base.html` — update the navbar to show a "Sign out" link when `session.user_id` is set, and "Sign in" / "Register" links when it is not

## Files to change
- `app.py` — set `app.secret_key`, import `session`, `redirect`, `url_for`, `request`, `flash` from Flask; add POST handlers for `/register` and `/login`; add `GET /dashboard` route; convert existing GET-only `@app.route("/register")` and `@app.route("/login")` to accept both `GET` and `POST`
- `templates/base.html` — navbar conditional on session state

## Files to create
- `templates/dashboard.html`

## New dependencies
No new dependencies. `werkzeug.security` (`generate_password_hash`, `check_password_hash`) is already available.

## Rules for implementation
- No SQLAlchemy or ORMs — use `get_db()` and raw SQL only
- Parameterised queries only — never use string formatting in SQL
- Hash passwords with `werkzeug.security.generate_password_hash`; verify with `check_password_hash`
- Use CSS variables — never hardcode hex values in new styles
- All templates extend `base.html`
- `app.secret_key` must be set before any session use; use a hard-coded dev string for now (e.g. `"spendly-dev-secret"`) — acceptable for a teaching project
- Store only `user_id` and `user_name` in the session (no password data)
- On duplicate email during registration, re-render `register.html` with `error="An account with that email already exists."`
- On bad credentials during login, re-render `login.html` with `error="Invalid email or password."`
- Password must be at least 8 characters — validate server-side, not just via HTML `minlength`
- `/dashboard` must redirect to `/login` if `session.get("user_id")` is falsy

## Definition of done
- [ ] Submitting the register form with valid data creates a new user row in `users` with a hashed password
- [ ] After successful registration the browser lands on `/dashboard` showing the new user's name
- [ ] Submitting the register form with an already-used email re-renders the form with an error message
- [ ] Submitting the register form with a password shorter than 8 characters re-renders with an error message
- [ ] Submitting the login form with correct credentials redirects to `/dashboard`
- [ ] Submitting the login form with wrong password re-renders the form with an error message
- [ ] Navigating to `/dashboard` while not logged in redirects to `/login`
- [ ] The navbar shows "Sign in" and "Register" links when logged out, and "Sign out" when logged in
- [ ] Passwords are never stored in plain text — verifiable by inspecting the `users` table
