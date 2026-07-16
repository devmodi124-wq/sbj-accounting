# Khata — Features

A living catalogue of what the app can do today. **Keep this current**: whenever a
user-facing feature or capability is added, changed, or removed, update this file in the
same change (see the rule in `CLAUDE.md`).

Khata is a fully offline, single-installation desktop accounting app for a small jewellery
business. It runs as a Windows `.exe` that starts a local server and opens the browser.
Single concurrent user, two roles (**Admin** / **Employee**), encrypted-at-rest database.

---

## Security & access

- **Encrypted database** — SQLite encrypted at rest via SQLCipher; a random master key wraps the DB, itself stored per-user in a side keyfile (scrypt + AES-GCM).
- **First-run bootstrap** — first launch prompts to create the admin account.
- **Login / logout** with password (bcrypt).
- **Two roles** — Admin (full access) and Employee (restricted: no user management, no danger zone, backdating limit applies).
- **Single active session** app-wide — a second login invalidates the first with a message.
- **Audit log** — every mutating database write is recorded automatically (old/new values + acting user).
- **Backdating limit** — employees cannot create/edit entries older than `today − N` days (admin-configurable, default 7); admins are exempt. Inline error, never silent.

## Orders / Sales

- **Multi-item orders** — one order holds one or more pieces; each piece priced from weights × rates.
- **Weights×rates pricing** — gross weight (g) + diamond/stone/others (carats) + per-unit rates; net metal weight = gross − (diamond+stone+others)/5; subtotal computed per piece, order total = Σ pieces.
- **Typed diamonds** — a piece can carry multiple diamond lines, each `{type, carats, rate}`; the diamond type is an admin-configurable dropdown (seeded Chowki / Princess / Marquise / Other fancy / Lab-grown). All diamond carats count toward the net-weight deduction; each line's carats×rate adds to the subtotal.
- **Per-piece category** (required), plus optional item name, weight type, supply source, purity.
- **Order reference** (free text) and **source** (Whatsapp/Instagram/… configurable).
- **Split payments** — multiple `{mode, amount}` lines per order; cash-mode lines mirror into the cash book automatically.
- **Pictures per piece** — upload/view/delete images attached to each item.
- **Customer search-or-create** inline (case-insensitive, trimmed matching).
- **Order status** — pending / delivered.
- **Soft void / restore** — cancel an order (reversible); excluded from all money aggregations but kept visible (greyed) for restore.
- **Hard delete** (admin only) — removes the order and its mirrored cash entry.
- **Edit** order with piece-diffing that preserves each piece's pictures.

## Cash book

- **Cash entries** — received / paid, optional person + link to customer/party, free-text details.
- **Cash-in-hand** = all-time received − paid + opening balance; sale cash-mode payments mirrored in automatically.
- **Edit / delete** entries (auto-generated sale mirrors are locked — edit the order instead).

## Purchases

- **Purchase entries** — party, amount, amount paid → derived balance & status.
- **Edit / delete** entries.

## Dashboard

- **Period selector** with shared date presets.
- **Stat cards** — sales (with vs-previous-period delta), orders + average order value, net metal weight sold, cash in hand, outstanding receivables, outstanding payables.
- **Sales trend** chart (last 12 months, vendored Chart.js, fully offline).
- **Tables** — pending orders, top customers, sales by category, sales by source.

## Reports

- **Sales report** — filters (status, category, weight type, date preset/custom), per-row actions (view/edit/void/delete), **totals row**, and **category & source breakdown** panel.
- **Order / Stock report** — with days-pending; view/edit actions.
- **Debtors report** — outstanding receivables with ageing buckets (0-30/31-60/61-90/90+), links to ledger.
- **Creditors report** — outstanding payables mirror.
- **Purchases report** — filters by status / party.
- **Customer report** — order count, lifetime value, average order value.
- **Date-range presets** (shared everywhere) — all time, today, this/last month, this/last quarter, this/last year, last 7/30 days, custom.
- **CSV + Excel export** (Excel includes thumbnails) — each export ends with a **TOTAL row** summing the money/count columns; the Sales export also appends the category & source breakdown.

## Ledgers

- **Per-customer and per-party ledgers** with running balance.
- **Dated opening balances** (debit/credit) — needed for migrated historical data.
- **CSV export.**

## Masters / Settings (admin)

- **Tabbed settings page** — General · Dropdowns · Users · Storage & Backups · Danger Zone; only one section shows at a time (dropdown lookups share a compact multi-column tab).
- **Contacts** — customers and parties (create/edit/deactivate/delete).
- **Configurable lookups** — item categories, purity types, weight types, supply sources, order sources (add/edit/deactivate/reorder).
- **Users** — create, deactivate, assign role, reset password.
- **Settings** — backdate limit, currency symbol, date format, opening cash balance, backup folder path.

## Import (admin)

- **Downloadable Excel template** with an Instructions sheet and data-validation dropdowns.
- **Bulk import** — Customers, Parties, Opening Balances, Orders, Cash Entries, Purchases.
- **Multi-item orders** — Orders rows sharing the same `order_ref` collapse into one order with multiple pieces; the first row carries the order-level fields, each row is a piece. Blank `order_ref` = single-item order.
- **Typed diamond lines** — `diamond_type` (dropdown) sets a diamond line's type; rows sharing `order_ref`+`item_ref` collapse into one piece carrying several typed lines. Blank `diamond_type` falls back to `Diamond (Other fancy)`; an unknown name is a validation error.
- **Pictures via ZIP bundle** — list filenames in the `images` column, ZIP the workbook with an `images/` folder, upload the `.zip` (the endpoint auto-detects `.xlsx` vs `.zip`).
- **Validate-before-commit** — every error reported (with sheet + row) before anything is saved; commit is a single all-or-nothing transaction.
- **Name matching** reuses the same case-insensitive/trimmed logic as manual entry (no duplicates).

## Backups & danger zone (admin)

- **Manual backup** — copy the encrypted DB + keyfile to a configurable folder.
- **Storage settings** — view/set backup folder, see existing backups.
- **Kill switch — Lock** — re-encrypts the DB with a new unknown key (sealed separately); next launch shows locked screen.
- **Kill switch — Destroy** — secure-overwrites and deletes the local DB, keyfile, and local backups (does not reach external backup paths).
- Both kill-switch actions are admin-only and require typed confirmation.

## Packaging

- **Single Windows `.exe`** (PyInstaller) — picks a free port, starts the server, opens the browser.
- **Offline-first** — Chart.js and fonts vendored locally; no network calls.
- **CI** — GitHub Actions builds the `.exe` and publishes a GitHub Release on each tag.
