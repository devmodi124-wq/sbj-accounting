# Khata — Jewellery Shop Accounting App
## Build Spec v1 (for Claude Code)

This document is the source of truth for building the application. The accompanying `prototype.html`
shows the intended look, feel, and core interaction patterns for three screens (New Order, Dashboard,
Debtors Report) — use it as a visual/UX reference, not as final code.

---

## 1. Overview

A fully offline, single-installation desktop accounting tool for a small jewellery business, replacing
a scattered Excel-based workflow. Runs on Windows, packaged as a single executable. Single concurrent
user, multiple named accounts with role-based access (Admin / Employee).

---

## 2. Tech stack

- **Backend**: Python, FastAPI
- **Database**: SQLite, encrypted at rest via SQLCipher (`sqlcipher3-binary` or `pysqlcipher3` —
  choose whichever has reliable prebuilt wheels for both macOS dev and Windows target)
- **Frontend**: Server-rendered or lightweight JS (vanilla JS / htmx-style is fine) served by FastAPI,
  styled per `prototype.html`'s design tokens — no heavy frontend framework needed
- **Charts**: Chart.js (CDN or vendored locally — must work fully offline, so vendor it)
- **Packaging**: PyInstaller → single Windows `.exe` that starts the server and opens the default
  browser to `http://127.0.0.1:<port>`
- **Dev workflow**: Developed on macOS by running the FastAPI app directly with `uvicorn`/`python`.
  Windows `.exe` build happens via GitHub Actions (Windows runner) on push/tag, or manually on a
  Windows machine when needed. The database file must live **outside** the git repo (e.g.
  `../khata-data/` sibling folder), referenced via a config value, and must be in `.gitignore`
  regardless. No real customer data should ever enter the git history.

---

## 3. Roles & authentication

- **Users**: username + password (bcrypt-hashed), role = `admin` | `employee`
- **Master DB password**: Each user's password is used (directly or via a key-derivation step) to
  unlock/derive access to the encrypted SQLite database. Design so that:
  - Any valid user (admin or employee) can unlock the DB to start the app
  - Losing one user's password must not lock out the whole database — there must be a recovery path
    (e.g. an admin can reset another user's password while logged in; if ALL users are locked out,
    that's an acknowledged edge case to document, not silently handled)
- **Session**: Single active session enforced app-wide (if a second login occurs, the first session
  is invalidated, with a message explaining why)
- **Backdating control**:
  - Setting: `employee_backdate_limit_days` (integer, admin-configurable, default e.g. 7)
  - Employees cannot create or edit entries (orders, cash entries, purchases) with a date earlier
    than `today - employee_backdate_limit_days`
  - Admins are exempt from this restriction
  - Attempting a disallowed backdated entry shows a clear inline error, not a silent failure

---

## 4. Data model

### `users`
- id, username (unique), password_hash, role (`admin`|`employee`), full_name, is_active, created_at

### `customers`
- id, name, phone, address, notes, created_at, created_by

### `parties` (suppliers / creditors)
- id, name, phone, address, notes, created_at, created_by

### `component_types`
- id, name (e.g. "Round (RND)", "Stone", "Marquise (MRQ)", "Moti (Pearl)", "Chowk (CHK)", "Labour")
- is_active (admin can deactivate without deleting, to preserve history)
- sort_order
- Admin-only CRUD. Seed with the six types above on first run.

### `purity_types`
- id, name (e.g. "14 KT", "18 KT", "22 KT", "916", "Silver")
- is_active, sort_order
- Admin-only CRUD. Seed with common Indian jewellery purities on first run.

### `orders`
- id, customer_id (FK), order_date, item_name, order_code (nullable), notes
- status (`pending` | `delivered`)
- total_amount (derived from sum of order_items.price, but stored for performance — recompute on
  item changes)
- payment_received, balance (= total_amount - payment_received)
- payment_mode (`cash`|`upi`|`bank_transfer`|`old_gold_exchange`|`other`)
- created_by (FK users), created_at, updated_at
- is_backdated (bool, computed at save time based on order_date vs created_at)

### `order_items` (components)
- id, order_id (FK), component_type_id (FK)
- pcs (nullable — not all components have a piece count)
- weight (decimal, grams; nullable)
- purity_type_id (FK, nullable — not all components have purity, e.g. Labour)
- rate (decimal, nullable)
- price (decimal — always present, this is what sums into order total)
- sort_order (preserve row order as entered)

### `cash_entries`
- id, entry_date, person_name (free text OR optionally link to customer_id/party_id — see note below)
- details, entry_type (`received`|`paid`), amount
- created_by, created_at, is_backdated

> Note on `cash_entries.person_name`: the source Excel mixes customer and supplier names freely in
> the CASH sheet. Recommend: add nullable `customer_id` and `party_id` FKs alongside `person_name`
> free text, so entries can optionally link to a master record (for ledger rollups) while still
> allowing quick free-text entry for one-off cash movements that don't belong to a tracked party.

### `purchases`
- id, purchase_date, party_id (FK), details, entry_notes (free text, e.g. "3 ct @ 6600")
- amount, amount_paid, balance (= amount - amount_paid)
- status (derived: `paid` if balance = 0, else `pending`)
- created_by, created_at, is_backdated

### `settings`
- key (unique), value
- Keys include: `employee_backdate_limit_days`, `currency_symbol` (default "₹"),
  `date_format` (default "DD-MM-YYYY"), `backup_folder_path`, `master_pin_hash` (for kill switch)

### `audit_log`
- id, user_id (FK), action (`create`|`update`|`delete`), table_name, record_id
- old_value (JSON, nullable), new_value (JSON, nullable), timestamp
- This is populated automatically by a shared data-access layer — individual route handlers
  should not need to remember to log manually. Every write to orders, order_items, cash_entries,
  purchases, customers, parties, users, settings, component_types, purity_types must be logged.

---

## 5. Kill switch

- Triggered by entering a special admin PIN sequence in a hidden/admin-only UI location (e.g. a
  "Danger Zone" section under Settings, admin-only, requiring re-entry of the admin's own password
  to access)
- Two actions, each requiring a typed confirmation phrase (e.g. type "DESTROY" or "LOCK"):
  - **Lock**: Re-encrypts the database with a new key not known to any current user, and shows a
    locked screen on next launch. Reversible only if the new key is recoverable (document this —
    v1 can store the new key in a separate sealed file the admin must secure elsewhere, e.g. on
    a different pendrive)
  - **Destroy**: Secure-overwrites and deletes the database file (and any backup copies present on
    the same machine), including the audit log. Irreversible. Requires the strongest confirmation
    UX (typed phrase + re-entered admin password + a final "this cannot be undone" modal)
- **Build for extensibility**: structure the kill-switch logic as its own module
  (e.g. `app/killswitch.py`) with a clean interface, so v2 improvements (remote trigger, USB-key
  presence check, duress codes, etc.) can be added without touching the rest of the app.
- Backups: a configurable `backup_folder_path` (ideally pointing to a different drive/pendrive) holds
  periodic encrypted copies of the DB. Destroy explicitly does NOT reach outside the local machine —
  if the admin configured backups to an external path, those survive. This should be documented
  clearly in the Settings UI so the admin understands the implication.

---

## 6. Screens

### 6.1 New Order (see prototype `view-entry`)
- Customer search-or-create (type-ahead against `customers`, with phone shown for disambiguation;
  "+ Add new customer" option creates a new customer record inline)
- Order date (subject to backdating rule), order code (optional), item name, status (pending/delivered), notes
- Dynamic component rows: component type (dropdown from `component_types`), pcs, weight, purity
  (dropdown from `purity_types`, only enabled for component types where purity is relevant — Labour
  typically has none), rate, price. Add/remove rows freely.
- Total amount = sum of all component prices (live-calculated, read-only)
- Payment received (editable), balance = total - received (live-calculated)
- Payment mode dropdown
- Save / Save as Draft / Cancel

### 6.2 Dashboard (see prototype `view-dashboard`)
- Date range selector (Today / This Month / This Quarter / This Year / Custom)
- Stat cards: Sales (period), Outstanding receivables, Outstanding payables, Cash in hand
  - Cash in hand = sum of cash_entries.received - sum of cash_entries.paid (running, all-time) +
    any opening balance setting
- Sales trend chart (monthly, last 12 months)
- Pending orders list (status = pending)
- Top customers table (by total billed, period-scoped)
- Sales by component type table (period-scoped)

### 6.3 Reports (six total + ledgers)

All reports share: filter bar (search box + relevant dropdown filters + date range where applicable),
sortable column headers (click to sort, indicate direction), pagination, and an Export button
(CSV export is sufficient for v1).

1. **Sales Report** — one row per order: date, customer, item, total, received, balance, status.
   Filters: date range, customer, status.
2. **Order / Stock Report** — pending vs delivered orders as a work-in-progress tracker: date,
   customer, item, component summary, status, days pending. Filters: status, date range.
3. **Debtors Report** (see prototype `view-debtors`) — per customer: total billed, received,
   balance, last transaction date, ageing bucket (0-30/31-60/61-90/90+ days, based on last
   transaction or order date with outstanding balance). Filters: search, ageing bucket, sort.
   "Ledger" button per row links to that customer's ledger (6.4).
4. **Creditors Report** — mirror of Debtors, per party: total purchases, paid, balance, ageing.
5. **Purchase Report** — one row per purchase: date, party, details, amount, paid, balance, status.
   Filters: date range, party, status.
6. **Customer Report** — per customer: contact info, lifetime total purchases, order count, average
   order value, outstanding balance, last visit date. Drill-down to order history.

### 6.4 Ledgers
- Per-customer or per-party running ledger: chronological list of all transactions (orders, cash
  entries, purchases as applicable) with debit/credit/running balance columns
- Must support an "opening balance" per customer/party (needed for migrated historical data —
  store as a dated entry at the start of each ledger)
- Exportable (CSV)

### 6.5 Settings (admin-only)
- Manage component types (add/edit/deactivate/reorder)
- Manage purity types (add/edit/deactivate/reorder)
- Manage users (create/deactivate/reset password, assign role)
- Set `employee_backdate_limit_days`
- Configure `backup_folder_path` and trigger manual backup
- Kill switch ("Danger Zone")

---

## 7. Import (historical data migration)

- Provide a downloadable Excel **template** with separate sheets, matching the data model 1:1:
  - `Customers` (name, phone, address, notes)
  - `Parties` (name, phone, address, notes)
  - `Opening Balances` (entity type, entity name, as-of date, opening balance amount, debit/credit)
  - `Orders` (order reference no., customer name, order date, item name, order code, status,
    payment received, payment mode, notes) — one row per order
  - `Order Items` (order reference no. — matches the Orders sheet, component type, pcs, weight,
    purity, rate, price) — one or more rows per order, linked by reference number
  - `Cash Entries` (date, person name, details, type, amount)
  - `Purchases` (date, party name, details, entry notes, amount, amount paid)
  - An `Instructions` sheet explaining each column, with data-validation dropdowns for component
    type / purity / status / entry type where Excel allows
- Build an admin-only "Import" screen: upload the filled template, run validation (unknown customer
  names, unknown component types/purities, missing required fields, order references in `Order Items`
  that don't exist in `Orders`), show a preview/error report **before** committing, then import in a
  single transaction. Customer/party names should be matched against existing master records
  (case-insensitive, trimmed) and create new ones only when no match exists — same matching logic
  used in the New Order customer search, so import and manual entry stay consistent.
- This import path is for one-time/occasional bulk migration only — not a sync mechanism.

---

## 8. Design reference

Follow `prototype.html` for: color tokens (paper/ink/copper/green/red), typography (Source Serif 4
for headings, IBM Plex Sans for UI/body/tabular data), table styling (sticky headers, tabular
numerals, green/red amount coloring for received/outstanding), filter bar pattern, sidebar nav
structure, and stat-card layout on the dashboard. Vendor both fonts locally for offline use.

---

## 9. Explicitly out of scope for v1

- GST-compliant invoicing (build data model with this in mind — e.g. don't preclude adding HSN
  codes / tax fields later — but no tax calculation or compliant invoice format now)
- Multi-machine sync
- Remote/network access (strictly localhost)
- Anything beyond CSV export (no PDF invoice generation, etc.) unless trivial to add
