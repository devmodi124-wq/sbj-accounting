# Khata — Phased Implementation Plan

## Context

Khata is a fully offline, single-installation desktop accounting app for a small jewellery
business (Sahibabad Jewellers), replacing a scattered Excel workflow. It runs as a Windows
`.exe` that starts a local FastAPI server and opens the browser to `127.0.0.1:<port>`.
Single concurrent user, two roles (Admin / Employee), encrypted-at-rest SQLite.

The repo's source of truth is `BUILD_SPEC.md`; `prototype.html` is the visual/UX reference for
three screens. This plan turns that spec into working software in self-contained phases, each of
which leaves the app runnable and testable.

### Locked decisions
- **Frontend:** JSON REST API (FastAPI) + vanilla JS. No framework. Chart.js + both fonts vendored locally.
- **DB unlock:** Keyfile-envelope model. One random master key encrypts the SQLCipher DB; a side
  `khata.keys` file (next to the DB, gitignored) stores per-user `{salt, wrapped_master_key, verifier}`.
  Login derives a KEK from the password, unwraps the master key, opens the DB. Admin reset re-wraps the
  master key under a new password. All keyfile entries lost = documented dead end (matches spec).
- **Schema management:** `Base.metadata.create_all()` on first run + a stored `schema_version` setting
  driving small hand-written upgrade steps later. No Alembic.

### Cross-cutting principles
- The DB file and `khata.keys` live **outside** the repo (default `../khata-data/`), via a config value,
  and are gitignored. No real customer data ever enters git.
- All mutating writes flow through one data-access/service layer so `audit_log` is written automatically
  (SQLAlchemy session events + a `contextvars` current-user), never manually per route.
- Build the data model so v2 additions (GST/HSN/tax fields) are not precluded, but implement none now.

---

## Tech stack & key libraries
- Python 3.11+, FastAPI, Uvicorn
- SQLAlchemy 2.0 ORM over SQLCipher SQLite via `sqlcipher3-binary` (DBAPI passed to SQLAlchemy's sqlite
  dialect; `PRAGMA key` issued on a `connect` event). `pysqlcipher3` is the fallback if wheels fail.
- `passlib[bcrypt]` for password hashing; `cryptography` for the key-envelope (scrypt/PBKDF2 KEK + AES-GCM wrap)
- `openpyxl` for Excel template generation + import parsing
- `pydantic` for request/response schemas
- `pytest` + `httpx` (FastAPI TestClient) for tests
- PyInstaller for packaging; GitHub Actions (Windows runner) for the `.exe` build

## Target structure
```
sbj-accounting/
  app/
    main.py            # FastAPI app, lifespan: DB init/seed, open browser
    config.py          # data dir path, port, defaults (env/config-file driven)
    runtime.py         # locked-DB state, browser launcher, port selection
    db.py              # engine (sqlcipher), SessionLocal, create_all + schema_version
    crypto/
      keyfile.py       # keyfile envelope: create/unlock/rewrap/verify
    models/            # SQLAlchemy models (one module per group)
    schemas/           # pydantic request/response models
    services/          # business logic + the audited write layer
      audit.py         # session-event audit logging + current-user contextvar
      matching.py      # shared case-insensitive/trimmed customer/party matching
      backdating.py    # employee backdate-limit enforcement
    auth/              # login/logout, single-session, role dependencies
    routers/           # auth, customers, parties, masters, orders, cash,
                       #   purchases, dashboard, reports, ledgers, import_, settings, killswitch
    killswitch.py      # Lock / Destroy (clean interface for v2)
    static/
      css/style.css    # ported from prototype.html design tokens
      js/              # api.js, format.js, table.js (sort/paginate), typeahead.js, per-screen modules
      fonts/           # vendored Source Serif 4 + IBM Plex Sans
      vendor/chart.js  # vendored
    templates/index.html  # single shell page; JS renders views client-side
  tests/
  requirements.txt
  .gitignore           # ../khata-data/, *.db, *.keys, build artifacts
  CLAUDE.md            # project guide
```

---

## Phases

Each phase is independently runnable and ends with a test/verify step. Order is foundation-first
because auth, encryption, and the audit layer underpin everything.

### Phase 0 — Scaffolding & encryption spike
- Project layout, `requirements.txt`, `.gitignore`, `app/config.py` (external data dir).
- **Spike first:** prove `sqlcipher3-binary` + SQLAlchemy can create, key, write and reopen an encrypted
  DB on macOS. If wheels are unreliable, fall back to `pysqlcipher3` and record the decision. This de-risks
  the whole project.
- FastAPI skeleton with lifespan, health route, static mounting, single `index.html` shell.
- Port prototype CSS into `static/css/style.css`; vendor fonts + Chart.js; remove the proto banner.
- `pytest` harness with a fixture that builds a throwaway encrypted DB per test.
- **Verify:** `uvicorn app.main:app --reload` serves the shell; spike test reopens an encrypted DB.

### Phase 1 — Data model, DB init, seeding, audit layer
- All models per spec §4: `users, customers, parties, component_types, purity_types, orders,
  order_items, cash_entries, purchases, settings, audit_log`. Add nullable `customer_id`/`party_id`
  on `cash_entries`; keep `is_backdated`, denormalized `total_amount`/`balance`. Leave room for tax fields.
- `db.py`: `create_all()` + `schema_version` setting; idempotent seed of the six component types, the
  purity types, and default settings (`employee_backdate_limit_days=7`, `currency_symbol=₹`,
  `date_format=DD-MM-YYYY`, opening cash balance, etc.).
- `services/audit.py`: SQLAlchemy `after_flush`/`after_commit` listeners capturing insert/update/delete on
  audited tables, writing `audit_log` with old/new JSON and the current user from a `contextvars` var set
  by request middleware.
- **Verify:** unit tests assert seeds exist, schema_version set, and a sample write produces an audit row.

### Phase 2 — Encryption envelope, auth, sessions, roles, backdating
- `crypto/keyfile.py`: create keyfile on first run, derive KEK (scrypt) from password, wrap/unwrap master
  key (AES-GCM), verify password, add/rewrap user entries (for create/reset). Bootstrap flow: first launch
  with no keyfile → create first admin (sets master key + first wrapped entry).
- Login/logout endpoints; signed session cookie; **single active session** (store current session token in
  a `sessions` table or settings; new login invalidates prior with an explanatory message).
- Role dependency (`require_admin`) and current-user dependency; middleware sets the audit contextvar.
- `services/backdating.py`: reject employee entries dated before `today - employee_backdate_limit_days`
  with an inline error; admins exempt. Reused by orders/cash/purchases.
- Login screen (vanilla JS) + locked-state handling stub.
- **Verify:** tests for unlock with correct/wrong password, second-login invalidation, admin password reset
  re-wrap, employee backdate rejection vs admin allowance.

### Phase 3 — Masters: customers, parties, component/purity types, users, settings
- CRUD routers + JSON schemas for customers and parties, including the type-ahead **search endpoint**.
- `services/matching.py`: case-insensitive, trimmed name matching — the single source reused by New Order
  search and Import.
- Admin-only management: component types & purity types (add/edit/deactivate/reorder via `sort_order`,
  `is_active`), users (create/deactivate/reset/assign role), settings (backdate limit, currency, date
  format, backup path).
- Settings screen + masters UI (vanilla JS, JSON-driven).
- **Verify:** CRUD tests; matching returns existing record vs signals new; deactivate preserves history;
  non-admin blocked from admin routes.

### Phase 4 — New Order screen (first major vertical feature)
- Order + order_items create/edit through the audited service layer; recompute `total_amount` from item
  prices on every change; `balance = total - payment_received`; set `is_backdated`; enforce backdating.
- Customer search-or-create inline (reusing Phase 3 search + matching).
- Dynamic component rows: type dropdown (active component types), pcs/weight/rate optional, purity dropdown
  enabled only where relevant (disabled for Labour), price required. Live totals/balance in JS.
- Save / Save as Draft / Cancel. **Draft = persist with status `pending`** (no separate enum value;
  the prototype's "Draft — not saved" is the unsaved UI state). Confirm if a hard draft flag is wanted.
- Port `view-entry` markup/behaviour to JSON+JS.
- **Verify:** create order with multiple components → totals correct, audit rows written; edit recomputes;
  backdated employee order rejected.

### Phase 5 — Cash entries & Purchases
- Cash entry CRUD (`received`/`paid`, optional link to customer/party, free-text person_name) and Purchase
  CRUD (party, amount/amount_paid → derived balance & status). Both through audited service + backdating.
- Simple entry/list screens.
- **Verify:** CRUD tests; cash-in-hand inputs and purchase balance/status derivations correct.

### Phase 6 — Dashboard
- Aggregation queries with a shared date-range resolver (Today / This Month / Quarter / Year / Custom):
  period Sales, Outstanding receivables, Outstanding payables, Cash-in-hand (all-time received−paid +
  opening balance), monthly sales trend (last 12 months), pending orders, top customers, sales by
  component type.
- Render stat cards + Chart.js trend (vendored) + tables per `view-dashboard`.
- **Verify:** seed known data; assert each aggregate; chart renders offline.

### Phase 7 — Reports & Ledgers
- Shared report infrastructure: filter bar, server-side sort/pagination, and **CSV export** helper, reused
  across all reports.
- Six reports (Sales, Order/Stock with days-pending, Debtors with ageing buckets, Creditors mirror,
  Purchases, Customer) + per-customer/party **ledgers** with running balance and dated **opening balance**
  entries (needed for migrated data). Debtors/Creditors rows link to ledgers.
- Port `view-debtors` as the template for the report pattern.
- **Verify:** ageing-bucket boundary tests (0-30/31-60/61-90/90+), ledger running-balance correctness,
  CSV output shape, sort/pagination.

### Phase 8 — Import (historical migration)
- Generate the downloadable Excel template (`openpyxl`): Customers, Parties, Opening Balances, Orders,
  Order Items, Cash Entries, Purchases, Instructions — with data-validation dropdowns where Excel allows.
- Admin-only import: upload → validate (unknown names, unknown component/purity, missing required fields,
  Order Items referencing missing Orders) → preview/error report **before commit** → import in one
  transaction. Reuse `services/matching.py` so import and manual entry stay consistent.
- **Verify:** round-trip a filled template; validation surfaces each error class; commit is atomic
  (rollback on any failure); names matched not duplicated.

### Phase 9 — Kill switch & backups
- `killswitch.py` clean interface (so v2 can add remote trigger / USB-key / duress codes):
  - **Lock:** `PRAGMA rekey` to a new random master key, write it to a separate sealed file, drop all
    keyfile user entries → next launch shows locked screen.
  - **Destroy:** secure-overwrite + delete DB, keyfile, and local backups (audit log included). Does NOT
    touch external backup paths — surface this clearly in the Danger Zone UI.
- Both gated behind admin + re-entered admin password + typed confirmation phrase + final modal.
- Backups: configurable `backup_folder_path`, manual "Backup now" (copy encrypted DB + keyfile) and a
  simple periodic copy.
- **Verify (carefully, on disposable data):** Lock then confirm prior passwords fail and locked screen
  shows; Destroy removes local files but leaves an external-path backup intact.

### Phase 10 — Packaging & CI
- PyInstaller spec bundling templates, static (fonts, vendored Chart.js), producing a single Windows `.exe`
  that picks a free port, starts Uvicorn, opens the browser, and on locked DB shows the locked screen.
- GitHub Actions Windows-runner workflow building the `.exe` on push/tag; artifact upload.
- **Verify:** CI produces a runnable `.exe`; manual smoke test on Windows (login → create order → dashboard).

---

## Verification (overall)
- `pytest` green at each phase; the audited write layer asserted to log every mutating table.
- `uvicorn app.main:app --reload --port 8000` for manual macOS testing after each phase.
- Security-sensitive flows (key envelope, single-session, kill switch) get explicit tests and are exercised
  only against disposable data in `../khata-data/`.

## Open items to confirm during build
- "Save as Draft" semantics: persist as `pending` (current assumption) vs. a dedicated draft flag.
- Final SQLCipher binding (`sqlcipher3-binary` vs `pysqlcipher3`) — decided by the Phase 0 spike.
