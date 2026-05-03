# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the dev server (http://localhost:5001)
python app.py

# Run all tests
pytest

# Run a single test file
pytest tests/test_auth.py

# Install dependencies
pip install -r requirements.txt
```

## Architecture

**Spendly** is a Flask expense-tracking web app targeting Indian users (currency: ₹). It is structured as a teaching project with placeholder routes that students implement in numbered steps.

### Stack
- **Backend**: Flask 3.1.3, Python, SQLite via the standard `sqlite3` module
- **Frontend**: Jinja2 templates (`templates/`), vanilla JS (`static/js/`), custom CSS (`static/css/`)
- **Testing**: pytest + pytest-flask

### Key files
- `app.py` — all routes live here; Flask app is created and runs on port 5001
- `database/db.py` — students write this; must expose `get_db()`, `init_db()`, and `seed_db()`
- `templates/base.html` — shared navbar/footer; all other templates extend this
- `static/css/landing.css` — landing-page-specific styles; `style.css` is global

### Implementation steps (student curriculum)
Routes marked "coming in Step N" are intentional placeholders:
- **Step 1**: `database/db.py` — SQLite connection, table creation, seed data
- **Step 3**: `/logout`
- **Step 4**: `/profile`
- **Steps 7–9**: `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`

### Design tokens
- Primary accent: `#1a472a` (deep green), secondary: `#c17f24` (warm gold), danger: `#c0392b`
- Fonts: DM Serif Display (headings), DM Sans (body) — loaded from Google Fonts in `base.html`
