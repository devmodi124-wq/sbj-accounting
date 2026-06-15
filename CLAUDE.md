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
# One-time setup (macOS): venv + deps + SQLCipher binding (built from Homebrew sqlcipher)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
scripts/install_sqlcipher.sh           # brew install sqlcipher + build sqlcipher3

# Run the dev server (data dir lives OUTSIDE the repo)
KHATA_DATA_DIR=../khata-data .venv/bin/python -m uvicorn app.main:app --reload --port 8731
# …or the packaged entrypoint (picks a free port + opens the browser):
.venv/bin/python -m app.launcher

# Tests
.venv/bin/python -m pytest                     # all
.venv/bin/python -m pytest tests/test_orders.py -v
```

First launch shows a bootstrap screen to create the admin account. **`sqlcipher3` has no
universal wheel** — on macOS it is built from source against Homebrew sqlcipher (see
`scripts/install_sqlcipher.sh`); the Windows `.exe` build (GitHub Actions, `.github/workflows/
build-windows.yml`) uses `sqlcipher3-binary` + `pyinstaller khata.spec`. Do not build the exe on macOS.

## Database

The database file lives **outside** the repo at `../khata-data/khata.db` (or wherever `settings.backup_folder_path` points). This path is `.gitignore`d — no real customer data should ever enter git history. On first run, the app seeds `component_types` (Round/RND, Stone, Marquise/MRQ, Moti/Pearl, Chowk/CHK, Labour) and `purity_types` (14 KT, 18 KT, 22 KT, 916, Silver).

**Encryption model** (implemented in `app/crypto/keyfile.py` + `app/db.py`): one random 32-byte master key encrypts the DB (SQLCipher raw-key `PRAGMA key`). A side `khata.keys` file stores that master key wrapped per-user (scrypt KEK + AES-GCM). Any user unlocks it; admin password reset re-wraps without rekeying. The master key is held in `engine_state.master_key` while unlocked (needed for create-user / reset / kill-switch rekey). Frontend is a JSON API + vanilla JS (no framework); schema is `create_all` + a `schema_version` setting (no Alembic).

## Architecture

```
app/
  main.py            # FastAPI app: mounts static, includes all routers, serves SPA shell
  launcher.py        # packaged entrypoint (free port + open browser + uvicorn)
  config.py          # external data-dir resolution (KHATA_DATA_DIR), db/keyfile paths
  db.py              # SQLCipher engine factory + EngineState (holds master key while unlocked)
  runtime.py         # free-port + browser-open helpers
  killswitch.py      # Lock (rekey + seal) / Destroy (secure-delete), clean v2 interface
  crypto/keyfile.py  # master-key envelope (scrypt + AES-GCM); any user unlocks, admin re-wraps
  models/            # ORM package (user, masters, order, cash, purchase, ledger, system, auth)
  schemas/           # pydantic request/response models
  services/          # business logic: audit, matching, backdating, orders, cash, purchases,
                     #   dashboard, reports, ledger, seed, settings_store, backup,
                     #   import_template, import_data
  auth/              # security (bcrypt), service (bootstrap/login/logout), deps (current user/admin)
  routers/           # auth, customers, parties, orders, cash, purchases, lookups, users,
                     #   settings, dashboard, reports, ledgers, import_, system
  static/
    vendor/chart.umd.min.js     # vendored Chart.js
    fonts/                      # vendored Source Serif 4 + IBM Plex Sans (woff2)
    css/ (style.css, fonts.css)
    js/  (api.js, ui.js, app.js + views/*.js per screen)
  templates/index.html          # single SPA shell; JS renders all views client-side
```

The frontend is a **JSON API + vanilla JS SPA**: `index.html` is a static shell and each screen is a
view module under `static/js/views/` registered on `window.KhataViews` and lazily mounted by `app.js`.

**Critical architectural rule**: every mutating DB write is logged to `audit_log` automatically by
SQLAlchemy session events in `app/services/audit.py` (excluding `audit_log` and `sessions`). Route
handlers/services never log manually — they only set the acting user, which `get_current_user` does via
the `current_user_id` contextvar. Sessions use `expire_on_commit=False` so the audit layer can capture
old values on update.

## Key business rules

- **Backdating**: Employees cannot create/edit entries with a date earlier than `today - employee_backdate_limit_days` (admin-configurable setting, default 7). Admins are exempt. Show an inline error — never a silent failure.
- **Session**: Single active session app-wide. A second login invalidates the first session with a message.
- **Cash in hand** = sum of all `cash_entries` received − sum paid (all-time) + opening balance setting. A sale's **cash-mode** payment lines are mirrored into one auto-generated `cash_entries` row (`order_id` set, `auto_generated=True`) by `app/services/orders._sync_auto_cash`, so they count toward Cash-in-Hand; that mirror is reconciled (upsert/delete) on every order save. Non-cash modes (UPI/bank/…) do **not** touch the cash book.
- **Orders are multi-item, priced by weights×rates**: an `order` has one or more **items/pieces** (`order_items`) and its own pictures (`order_images.order_item_id`). Each piece is priced from gross weight (g) + diamond/stone/others weights (carats) + per-unit rates. **Net (metal) weight = gross − (diamond+stone+others)/5** (5 ct = 1 g, clamped ≥0). **Item subtotal = net×metal_rate + diamond_ct×diamond_rate + stone_ct×stone_rate + others_ct×others_rate + net×labour_rate** (`net_weight` + `subtotal` stored denormalized; compute helpers in `app/services/orders.py`). **Order total** = sum of item subtotals. Each piece requires a category. `update_order` diffs pieces by id so editing preserves a piece's pictures; removing a piece cascades its images. (Pre-v5 `order_components` is kept as a legacy orphan table; the `ComponentType` lookup is no longer used in orders.)
- **Order-level reference & source**: `orders.reference` is free text (e.g. friends/family); `orders.source_id` → `order_sources` lookup (Whatsapp/Instagram/… — configurable in Settings like the other dropdowns).
- **Split payments**: `order_payments` holds one `{mode, amount}` line per payment; `orders.payment_received` = Σ lines (denormalized).
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
