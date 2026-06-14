# Khata — Jewellery Shop Accounting

A fully offline, single-installation desktop accounting app for a small jewellery business
(Shree Balaji Jewellers), replacing a scattered Excel workflow. It runs a local FastAPI server and
opens in the default browser — all data stays on the machine, encrypted at rest.

- **Single machine, single concurrent user**, with named accounts and two roles (Admin / Employee).
- **Encrypted SQLite** (SQLCipher) — no data ever leaves the device, and the database file is
  encrypted on disk.
- **No internet required**: fonts and Chart.js are vendored locally.

---

## Features

- **New Order** — customer search‑or‑create; a required **Item Category** plus optional Item Name,
  **Weight Type**, and **Supplied From** (all configurable dropdowns); dynamic component rows
  (pieces / weight / purity / rate / price); **multiple pictures** of the piece (stored encrypted in
  the DB); live total and balance; payment mode; Save / Save as Draft.
- **Cash Book** — record cash received and paid, optionally linked to a customer or supplier.
- **Purchases** — supplier purchases with derived balance and paid/pending status.
- **Dashboard** — period sales, outstanding receivables/payables, cash in hand, 12‑month sales‑trend
  chart, pending orders, top customers, sales by component.
- **Reports** (CSV export, sortable, paginated) — Sales, Order/Stock, Debtors (with ageing buckets),
  Creditors, Purchases, Customers.
- **Ledgers** — per‑customer / per‑supplier running balance with dated opening balances.
- **Import** — fill an Excel template, validate (errors shown before anything is saved), then import
  historical data in a single transaction.
- **Administration** — manage users; configurable dropdowns (item categories, weight types, supplied
  from, component & purity types); app settings; data-storage location; backups; and a Danger Zone
  kill switch (Lock / Destroy).
- **Audit log** — every create/update/delete is recorded automatically with the acting user.

---

## Tech stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0
- **Database:** SQLite encrypted with SQLCipher (`sqlcipher3`)
- **Frontend:** JSON REST API + vanilla JavaScript (no framework); Chart.js for charts
- **Auth/crypto:** bcrypt password hashing; scrypt + AES‑GCM key envelope; `cryptography`
- **Import/export:** `openpyxl` (Excel), CSV
- **Packaging:** PyInstaller (single Windows `.exe`), built in GitHub Actions

---

## Getting started (macOS development)

> `sqlcipher3` has no universal wheel, so on macOS it is built from source against Homebrew's
> `sqlcipher`. `scripts/install_sqlcipher.sh` automates this.

```bash
# 1. Create a virtualenv and install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Install the SQLCipher binding (installs `brew install sqlcipher` if needed)
scripts/install_sqlcipher.sh

# 3. Run the app (the database lives OUTSIDE the repo)
KHATA_DATA_DIR=../khata-data .venv/bin/python -m uvicorn app.main:app --reload --port 8731
```

Open <http://127.0.0.1:8731>. On first launch you'll be prompted to **create the administrator
account**.

Alternatively, run the packaged entrypoint, which picks a free port and opens the browser for you:

```bash
.venv/bin/python -m app.launcher
```

### Configuration

| Variable          | Default                | Purpose                                          |
| ----------------- | ---------------------- | ------------------------------------------------ |
| `KHATA_DATA_DIR`  | `../khata-data`        | Where `khata.db` and `khata.keys` live (gitignored) |
| `KHATA_PORT`      | `8731`                 | Preferred local port                             |

The data directory must stay **outside** the repository — no real customer data should ever enter
git history.

---

## Testing

```bash
.venv/bin/python -m pytest                      # full suite (102 tests)
.venv/bin/python -m pytest tests/test_orders.py -v
```

---

## Project structure

```
app/
  main.py            FastAPI app: routers + SPA shell
  launcher.py        desktop entrypoint (free port + browser + uvicorn)
  config.py          external data-dir / paths
  db.py              SQLCipher engine + EngineState
  crypto/keyfile.py  master-key envelope (any user unlocks; admin re-wraps)
  killswitch.py      Lock (rekey + seal) / Destroy (secure delete)
  models/            ORM models
  schemas/           pydantic request/response models
  services/          business logic (audit, matching, orders, dashboard, reports, ledger, import…)
  auth/              password hashing, login/sessions, role dependencies
  routers/           HTTP endpoints
  static/, templates/  vanilla-JS SPA (views/*.js), vendored fonts + Chart.js
tests/               pytest suite
khata.spec           PyInstaller build spec
.github/workflows/   Windows .exe build
```

See [`CLAUDE.md`](CLAUDE.md) for architecture details and conventions, and
[`BUILD_SPEC.md`](BUILD_SPEC.md) for the original specification.

---

## Security model

- One random 32‑byte **master key** encrypts the database (SQLCipher).
- The master key is never stored directly. A side **keyfile** (`khata.keys`, next to the database)
  holds a copy of it wrapped per user under a key derived from that user's password (scrypt → AES‑GCM).
- Any valid user can unlock the database; an admin can reset another user's password (re‑wraps the
  master key without rekeying the database). If **all** keyfile entries are lost the database is
  unrecoverable — an acknowledged, documented dead end.
- **Backdating:** employees cannot enter records older than `employee_backdate_limit_days`
  (admin‑configurable); admins are exempt.
- **Single active session:** a new login invalidates the previous one.

### Kill switch (admin, Settings → Danger Zone)

- **Lock** — re‑encrypts the database with a brand‑new key written to a separate *sealed* file (which
  the admin must secure elsewhere) and clears all keyfile entries, locking everyone out.
- **Destroy** — securely overwrites and deletes the local database, keyfile, sealed key, and local
  backups. It deliberately does **not** touch a backup folder on an external path (e.g. a pendrive).

Both require re‑entering the admin password and typing a confirmation phrase.

### Backups

Backups copy the encrypted database + keyfile to the configured backup folder (set it to a pendrive
for off‑machine safety). Configure the path under Settings and use **Backup now**.

---

## Importing historical data

1. Settings → **Import** → download the Excel template (separate sheets for Customers, Parties,
   Opening Balances, Orders, Order Items, Cash Entries, Purchases, plus Instructions).
2. Fill it in. Customer/supplier names are matched case‑insensitively; new names are created
   automatically. `order_ref` links Order Items to Orders.
3. Upload and **Validate** — every problem (with sheet and row) is reported before anything is saved.
4. **Import** — applied in a single transaction; any error rolls the whole import back.

---

## Packaging (Windows `.exe`)

The Windows executable is built in CI (`.github/workflows/build-windows.yml`): push a `v*` tag or run
the workflow manually. It installs `sqlcipher3-binary`, runs smoke tests, builds with
`pyinstaller khata.spec`, and uploads `Khata.exe` as an artifact. Do not build the Windows exe on
macOS.

---

## Out of scope (v1)

GST‑compliant invoicing, multi‑machine sync, remote/network access, and any export beyond CSV. The
data model leaves room for tax fields to be added later.
