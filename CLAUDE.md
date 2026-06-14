# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**Khata** — a fully offline, single-installation desktop accounting app for a small jewellery business. Replaces a scattered Excel workflow. Runs as a Windows `.exe` (PyInstaller), served on localhost, opened in the default browser. Single concurrent user, two roles (Admin / Employee).

The `BUILD_SPEC.md` is the canonical source of truth. `prototype.html` is the visual/UX reference — open it in a browser to see the three implemented screens (New Order, Dashboard, Debtors Report).

## Tech stack

- **Backend**: Python, FastAPI, Uvicorn
- **Database**: SQLite encrypted via SQLCipher (`sqlcipher3-binary` preferred for prebuilt wheels on both macOS and Windows)
- **Frontend**: Server-rendered HTML + vanilla JS (no framework), served by FastAPI
- **Charts**: Chart.js — must be vendored locally (fully offline)
- **Packaging**: PyInstaller → single Windows `.exe`
- **Fonts**: Source Serif 4 (headings) + IBM Plex Sans (UI/body) — vendor both locally for offline use

## Dev workflow

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (macOS)
uvicorn app.main:app --reload --port 8000

# Run a specific test file
pytest tests/test_orders.py -v

# Run all tests
pytest
```

The Windows `.exe` build runs via GitHub Actions on a Windows runner (or manually). Do not build it on macOS.

## Database

The database file lives **outside** the repo at `../khata-data/khata.db` (or wherever `settings.backup_folder_path` points). This path is `.gitignore`d — no real customer data should ever enter git history. On first run, the app seeds `component_types` (Round/RND, Stone, Marquise/MRQ, Moti/Pearl, Chowk/CHK, Labour) and `purity_types` (14 KT, 18 KT, 22 KT, 916, Silver).

**Encryption model**: SQLCipher encrypts the DB at rest. Any valid user's password must be able to unlock the DB (use a fixed master key stored encrypted per-user, not each user's raw password as the DB key). Losing one user's password must not lock out the entire database.

## Architecture

```
app/
  main.py          # FastAPI app, startup (open browser, init DB)
  database.py      # SQLAlchemy engine with SQLCipher, session management
  models.py        # SQLAlchemy ORM models (all tables)
  auth.py          # bcrypt hashing, JWT/session tokens, single-session enforcement
  audit.py         # Shared write layer — all mutations go through here and log to audit_log
  killswitch.py    # Lock / Destroy logic (clean interface for future v2 extensions)
  routers/
    orders.py
    cash.py
    purchases.py
    customers.py
    parties.py
    reports.py
    settings.py
    import_.py
  templates/       # Jinja2 HTML templates
  static/
    chart.js       # vendored
    fonts/         # vendored Source Serif 4 + IBM Plex Sans
    app.js
    style.css
```

**Critical architectural rule**: All writes to `orders`, `order_items`, `cash_entries`, `purchases`, `customers`, `parties`, `users`, `settings`, `component_types`, `purity_types` must go through `audit.py`'s shared write layer, which automatically logs to `audit_log`. Route handlers must not log manually.

## Key business rules

- **Backdating**: Employees cannot create/edit entries with a date earlier than `today - employee_backdate_limit_days` (admin-configurable setting, default 7). Admins are exempt. Show an inline error — never a silent failure.
- **Session**: Single active session app-wide. A second login invalidates the first session with a message.
- **Cash in hand** = sum of all `cash_entries` received − sum paid (all-time) + opening balance setting.
- **Order total** = sum of `order_items.price` (stored denormalized on `orders.total_amount`; recompute on item changes).
- **Balance**: `orders.balance = total_amount − payment_received`; `purchases.balance = amount − amount_paid`.
- **`is_backdated`**: computed bool set at save time (entry date vs. created_at).

## Design tokens (from prototype.html)

```css
--paper: #FBF8F2;    --paper-alt: #F4EFE5;
--ink: #1C1B19;      --ink-soft: #6B6459;
--hairline: #DDD5C6;
--copper: #A8714A;   --copper-soft: #E9DCCC;
--green: #2F5D4E;    --green-soft: #E3ECE8;
--red: #9B3B3B;      --red-soft: #F3E2E0;
--radius: 6px;
```

Table amounts: right-aligned, tabular numerals (`font-variant-numeric: tabular-nums`), green for received, red for outstanding balance. Sticky table headers. Filter bar above every report table.

## Kill switch (`app/killswitch.py`)

Two operations, both admin-only in Settings > Danger Zone, each requiring typed confirmation:
- **Lock**: Re-encrypts the DB with a new unknown key; stores new key in a separate sealed file.
- **Destroy**: Secure-overwrites and deletes the DB file (and local backups). Does NOT reach external backup paths. Document this clearly in the Settings UI.

Keep the kill-switch module isolated with a clean interface so v2 (remote trigger, duress codes, USB-key check) can extend it without touching the rest of the app.

## Import screen

Admin-only. Provides a downloadable Excel template (with an `Instructions` sheet and data-validation dropdowns). Upload → validate (show errors before committing) → import in a single transaction. Customer/party name matching is case-insensitive + trimmed; creates new records only when no match exists. Use the same matching logic as the New Order customer type-ahead search.

## Out of scope for v1

GST invoicing, multi-machine sync, network/remote access, PDF generation.
