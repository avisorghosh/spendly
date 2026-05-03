# Spec: Login and Logout

## Overview
Step 3 completes the session lifecycle by implementing the `/logout` route. Login was delivered in Step 2; this step adds the matching sign-out action so users can end their session cleanly. It also updates the navbar "Sign out" link (already conditionally rendered in Step 2) so it points to a real route instead of a placeholder, completing the full authenticate → use → sign-out flow.

## Depends on
- Step 1 (Database Setup) — requires `users` table and `get_db()`
- Step 2 (Registration) — requires Flask session, `app.secret_key`, `/login`, and `/dashboard` to already exist

## Routes
- `GET /logout` — clear the Flask session and redirect to `/` (landing page) — logged-in only (redirect to `/login` if not authenticated)

## Database changes
No database changes.

## Templates
- **Modify:** `templates/base.html` — ensure the "Sign out" navbar link href points to `{{ url_for('logout') }}` (it may already be wired correctly from Step 2; verify and fix if needed)

## Files to change
- `app.py` — replace the `/logout` placeholder with a real implementation: clear the session with `session.clear()` and redirect to `url_for('landing')`
- `templates/base.html` — verify/fix the "Sign out" link href

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `session.clear()` to wipe all session data — do not selectively delete individual keys
- After logout, redirect to the landing page (`/`), not to `/login`
- If the user is not logged in and hits `/logout`, redirect to `/login` rather than raising an error

## Definition of done
- [ ] Clicking "Sign out" in the navbar while logged in clears the session and lands on the landing page (`/`)
- [ ] After signing out, navigating to `/dashboard` redirects to `/login` (session is fully cleared)
- [ ] Visiting `/logout` while not logged in redirects to `/login` without raising an error
- [ ] The "Sign out" navbar link is visible only when a user is logged in
- [ ] The "Sign in" and "Register" navbar links are visible only when no user is logged in
