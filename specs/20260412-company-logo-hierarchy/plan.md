# Company Logo and Service Hierarchy — Implementation Plan

**Specification**: [spec.md](spec.md)
**Created**: 2026-04-12
**Status**: Ready for Review
**Estimated Complexity**: High
**Estimated Duration**: 3–4 weeks

---

## Summary

This plan restructures the Ngwe Lwe's data model from a flat `services` table into a formal three-level hierarchy: **Company → ServiceType → Account/CommissionTier**. It adds company logo support (upload, storage, REST delivery, client-side display with fallback), restructures the commission tier lookup key from a free-text string to a proper foreign key, updates all layers of the stack (SQLite migration, repositories, viewmodels, REST routes, PyQt views), and ensures zero data loss for existing transactions and accounts.

---

## Technical Context

| Item | Value |
|---|---|
| Language | Python 3.11+ |
| Backend framework | FastAPI (served via Uvicorn) |
| Database | SQLite 3 with WAL mode, FK enforcement |
| Migration pattern | Numbered `_migrate_NNN(conn)` functions in `backend/database.py` |
| Current schema version | 3 (after cashier role, cash management, cash approval) |
| Client framework | PyQt6 |
| API transport | HTTP REST + JSON, JWT bearer auth |
| Logo storage | Local filesystem `assets/logos/` on server host |
| Logo delivery | New REST endpoint `GET /companies/{id}/logo` |
| Packaging | PyInstaller; server spec `NgweLweServer.spec` |
| i18n | Active (`i18n/` directory, `t()` helper in views) |

---

## Current State Analysis

### What exists today

```
services          — flat table: id, name, service_type (TEXT), default_customer_fee
accounts          — service_id (FK→services), account_type ('personal'|'agent'), service_type (TEXT 'KPAY'|'WAVE'|'BANK')
commission_tiers  — service_type (TEXT e.g. 'KPAY_WST', 'WAVE_WST', 'WAVE_ACCOUNT')
transactions      — account_id, to_account_id, transaction_type
```

The commission tier lookup key is assembled at runtime by `_map_tier_service_type()` inside both `viewmodels/transaction_viewmodel.py` and `views/transaction_view.py`, combining `account.service_type` and `account.account_type` into strings like `"KPAY_WST"` or `"WAVE_ACCOUNT"`.

### Target state

```
companies         — id, name, logo_path, category ('Pay'|'Bank'|'Both'), is_active
service_types     — id, company_id (FK→companies), name, operation, is_active
accounts          — service_type_id (FK→service_types)  [replaces service_id + service_type TEXT]
commission_tiers  — service_type_id (FK→service_types)  [replaces service_type TEXT]
transactions      — existing FK columns retained; from_company_id and to_company_id added as explicit INTEGER FK columns (Q3)
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│  PyQt6 Client                                           │
│  ┌─────────────────┐   ┌──────────────────────────────┐ │
│  │ CompanySelector  │   │ TransactionForm               │ │
│  │ (logo + name)   │   │ (dual company selector for   │ │
│  └────────┬────────┘   │  Transfer/Exchange)           │ │
│           │            └──────────────┬───────────────┘ │
│           └──── ApiClient ───────────┘                  │
└───────────────────────┬─────────────────────────────────┘
                        │ HTTP/JSON + Bearer JWT
┌───────────────────────▼─────────────────────────────────┐
│  FastAPI Server                                          │
│  /companies          /companies/{id}/logo                │
│  /service-types      /accounts   /transactions           │
│  /commission-tiers                                       │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│  SQLite (WAL)         assets/logos/                      │
│  companies            *.png / *.jpg / *.svg              │
│  service_types                                           │
│  accounts (migrated)                                     │
│  commission_tiers (migrated)                             │
└─────────────────────────────────────────────────────────┘
```

---

## New Database Schema

### Table: `companies`

```sql
CREATE TABLE companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    logo_path   TEXT,
    category    TEXT NOT NULL DEFAULT 'Pay'
                CHECK(category IN ('Pay','Bank','Both')),
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER trg_companies_updated_at
AFTER UPDATE ON companies FOR EACH ROW
BEGIN UPDATE companies SET updated_at = datetime('now') WHERE id = NEW.id; END;
```

Seed rows (canonical companies):
- KBZ Pay (Pay), Wave Money (Pay), True Money (Pay)
- KBZ Bank (Bank), AYA Bank (Bank), CB Bank (Bank)

Legacy services migrated as full Company records (Q1 — all active, none deactivated):
- MPT Pay (Pay), OK Dollar (Pay), One Pay (Pay), AYA Pay (Pay), Yoma Pay (Pay)
- City Express (Pay), KBZ Express (Pay), Thai Bank (Bank)

### Table: `service_types`

```sql
CREATE TABLE service_types (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL,
    name        TEXT NOT NULL,
    operation   TEXT NOT NULL
                CHECK(operation IN ('Deposit','Withdraw','Transfer','Exchange','All')),
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(company_id, name),
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE TRIGGER trg_service_types_updated_at
AFTER UPDATE ON service_types FOR EACH ROW
BEGIN UPDATE service_types SET updated_at = datetime('now') WHERE id = NEW.id; END;
```

Seed rows per company:
- KBZ Pay: WST (All), Pay_To_Pay (All)
- Wave Money: WST (All), Pay_To_Pay (All)
- True Money: WST (All), Pay_To_Pay (All)  — dedicated tier rows seeded in migration_004 (Q2)
- KBZ Bank: Transfer (Transfer), Exchange (Exchange)
- AYA Bank: Transfer (Transfer), Exchange (Exchange)
- CB Bank: Transfer (Transfer), Exchange (Exchange)
- MPT Pay: WST (All), Pay_To_Pay (All)
- OK Dollar: WST (All), Pay_To_Pay (All)
- One Pay: WST (All), Pay_To_Pay (All)
- AYA Pay: WST (All), Pay_To_Pay (All)
- Yoma Pay: WST (All), Pay_To_Pay (All)
- City Express: WST (All), Pay_To_Pay (All)
- KBZ Express: WST (All), Pay_To_Pay (All)
- Thai Bank: Transfer (Transfer), Exchange (Exchange)

### Migration `_migrate_004`: Add companies + service_types, relink accounts and commission_tiers

The migration must:

1. Create `companies` and `service_types` tables and seed them.
2. Seed all 14 legacy services as full Company records — none are deactivated (Q1).
3. Seed dedicated `service_types` rows for every company, including True Money WST and Pay_To_Pay tiers (Q2).
4. Add `service_type_id` column to `accounts`.
5. Populate `accounts.service_type_id` by mapping existing `(service_id, service_type, account_type)` to the new `service_types.id`.
6. Drop the old `accounts.service_type TEXT` column (via table-rebuild — SQLite does not support DROP COLUMN in older versions).
7. Drop `accounts.service_id` column (table-rebuild).
8. Add `service_type_id` column to `commission_tiers`.
9. Populate `commission_tiers.service_type_id` by mapping existing `service_type TEXT` keys (e.g., `'KPAY_WST'`) to the new `service_types.id`.
10. Drop the old `commission_tiers.service_type TEXT` and `commission_tiers.account_type TEXT` columns (table-rebuild).
11. Add `from_company_id INTEGER` and `to_company_id INTEGER` columns to the `transactions` table (Q3).
12. Populate `from_company_id` and `to_company_id` for existing Transfer/Exchange rows via join: `transactions → accounts → service_types → companies`.

The mapping from legacy string keys to new `service_types` IDs is:

| Legacy key | Company | ServiceType name |
|---|---|---|
| KPAY_WST | KBZ Pay | WST |
| WAVE_WST | Wave Money | WST |
| WAVE_ACCOUNT | Wave Money | Pay_To_Pay |
| TRUE_MONEY_WST | True Money | WST |
| TRUE_MONEY_PAY_TO_PAY | True Money | Pay_To_Pay |

All 14 legacy services from the `services` table are migrated forward as Company records (Q1 — MPT Pay, OK Dollar, True Money, One Pay, AYA Pay, Yoma Pay, City Express, KBZ Express, Thai Bank are all included; none deactivated). Each Pay-category company receives WST and Pay_To_Pay service_types; Thai Bank receives Transfer and Exchange service_types.

True Money receives its own dedicated commission tier rows for WST and Pay_To_Pay, seeded separately from KBZ Pay and Wave Money tiers (Q2).

`from_company_id` and `to_company_id` are stored as explicit new columns in the `transactions` table (Q3). This provides better audit trails and simpler reporting queries without requiring runtime joins through the account → service_type → company chain.

---

## Implementation Phases

### Phase 1: Database Migration (Schema + Seed)

**Objective**: Add `companies` and `service_types` tables, migrate `accounts` and `commission_tiers` to use FK references, maintain zero data loss.

**Files to modify**:
- `backend/database.py` — add `_migrate_004(conn)` function, register in `_run_migrations`
- `backend/database.sql` — add new table DDL and updated seed data for fresh installs

**Tasks**:

1. Write `_migrate_004(conn)` in `backend/database.py`:
   - Create `companies` table with trigger.
   - Insert all 14 company rows (6 canonical + 8 legacy: MPT Pay, OK Dollar, One Pay, AYA Pay, Yoma Pay, City Express, KBZ Express, Thai Bank) using `INSERT OR IGNORE`. All `is_active = 1`.
   - Create `service_types` table with trigger.
   - Insert service type rows for every company using `INSERT OR IGNORE`, including dedicated WST and Pay_To_Pay rows for True Money.
   - Seed True Money commission tier rows (WST and Pay_To_Pay) in `commission_tiers` using `INSERT OR IGNORE`, separate from KBZ Pay and Wave Money rows.
   - Rebuild `accounts` table: add `service_type_id` INTEGER NOT NULL, populate from join on `(service_id → services.name → companies.name → company_id, account.service_type TEXT)`, drop `service_type TEXT` and `service_id INTEGER`, recreate indexes and FK.
   - Rebuild `commission_tiers` table: add `service_type_id` INTEGER NOT NULL, populate from `service_type` TEXT key lookup (including True Money keys), drop `service_type TEXT` and `account_type TEXT` columns, recreate indexes.
   - Add `from_company_id INTEGER REFERENCES companies(id)` and `to_company_id INTEGER REFERENCES companies(id)` to `transactions` (ALTER TABLE — adding columns is safe in SQLite). Populate from join `transactions → accounts → service_types → companies` for existing Transfer/Exchange rows.
   - Register version 4: `"Add companies, service_types; migrate accounts, commission_tiers, and transactions"`.

2. Update `backend/database.sql` (fresh-install schema):
   - Add `companies` and `service_types` DDL blocks (numbered sections 2 and 3; renumber existing sections).
   - Remove `service_type TEXT` from `accounts` and `service_id` — replace with `service_type_id INTEGER NOT NULL FK → service_types`.
   - Remove `service_type TEXT` and `account_type TEXT` from `commission_tiers` — replace with `service_type_id INTEGER NOT NULL FK → service_types`.
   - Remove the legacy `services` seed block; add `companies` and `service_types` seed blocks.
   - Update `schema_version` seed to include version 4.

3. Create `assets/logos/` directory placeholder (`.gitkeep`) so PyInstaller can include it.

**Gate**: Run `python -c "from backend.database import init_db; init_db()"` against a copy of the production DB. Verify row counts in `accounts` and `commission_tiers` match pre-migration counts. Verify `service_types` rows are correctly populated.

---

### Phase 2: Model and Repository Layer

**Objective**: Replace `Service` model + `ServiceRepository` with `Company` and `ServiceType` models; update `Account` and `CommissionTier` models; update all repositories.

**Files to create**:
- `models/company.py`
- `models/service_type.py`
- `repositories/company_repository.py`
- `repositories/service_type_repository.py`

**Files to modify**:
- `models/account.py` — replace `service_id`, `service_type TEXT`, `account_type TEXT` fields with `service_type_id: int`; add `company_id: int` (denormalized, populated via join for display)
- `models/commission_tier.py` — replace `service_type TEXT`, `account_type TEXT` with `service_type_id: int`
- `repositories/account_repository.py` — update `_row_to_model`, `get_by_service`, queries to use `service_type_id`; add `get_by_company(company_id)` and `get_by_service_type(service_type_id)`
- `repositories/commission_tier_repository.py` — replace `service_type TEXT` parameter with `service_type_id: int` in `get_tier_for_amount` and `get_by_service_type`
- `repositories/service_repository.py` — deprecate or remove (services table is gone after migration)

**New model definitions**:

```python
# models/company.py
@dataclass
class Company:
    id: Optional[int] = None
    name: Optional[str] = None
    logo_path: Optional[str] = None
    category: Optional[str] = None   # 'Pay' | 'Bank' | 'Both'
    is_active: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# models/service_type.py
@dataclass
class ServiceType:
    id: Optional[int] = None
    company_id: Optional[int] = None
    name: Optional[str] = None       # 'WST' | 'Pay_To_Pay' | 'Transfer' | 'Exchange'
    operation: Optional[str] = None  # 'Deposit' | 'Withdraw' | 'Transfer' | 'Exchange' | 'All'
    is_active: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
```

**Commission tier lookup change**: The current key is `(service_type_string, account_type_string, amount)`. After migration the key becomes `(service_type_id: int, amount: float)`. The `_map_tier_service_type()` helper functions in `viewmodels/transaction_viewmodel.py` and `views/transaction_view.py` are **deleted**; the `service_type_id` is read directly from the `Account` object.

**Gate**: All repository unit tests pass. `get_tier_for_amount(service_type_id, amount)` returns correct tier for known seeded data.

---

### Phase 3: Viewmodel Layer

**Objective**: Update `TransactionViewModel` and `AccountViewModel` to use the new model fields; add `CompanyViewModel` and `ServiceTypeViewModel`.

**Files to create**:
- `viewmodels/company_viewmodel.py`
- `viewmodels/service_type_viewmodel.py`

**Files to modify**:
- `viewmodels/transaction_viewmodel.py` — remove `_map_tier_service_type`; pass `account.service_type_id` directly to `_tier_repo.get_tier_for_amount`; update `_get_tier`, `_calc_commission`
- `viewmodels/account_viewmodel.py` — add `get_accounts_by_company(company_id)`, `get_accounts_by_service_type(service_type_id)`

**Gate**: Existing deposit/withdraw/transfer/exchange transaction flows produce identical commission amounts as before the refactor (verified with a regression fixture).

---

### Phase 4: REST API Routes

**Objective**: Add company and service-type endpoints; add logo upload/serve endpoint; update accounts and commission-tier routes to use new FK fields.

**Files to create**:
- `backend/routes/companies.py`
- `backend/routes/service_types.py`

**Files to modify**:
- `backend/routes/accounts.py` — filter by `service_type_id` instead of `service_id`; return `company_id` in response payload
- `backend/routes/commission_tiers.py` — accept `service_type_id` parameter instead of `service_type` string
- `backend/main.py` — register new routers; mount `assets/logos/` as static directory
- `services/api_client.py` — add methods: `get_companies()`, `get_service_types(company_id)`, `get_accounts_by_service_type(service_type_id)`, `get_logo(company_id)`, `upload_logo(company_id, file_bytes, mime_type)`, `create_company(...)`, `update_company(...)`, `create_service_type(...)`, `update_service_type(...)`

**New endpoints**:

```
GET  /companies                          → list all companies (with logo_path)
POST /companies                          → create company (owner only)
GET  /companies/{id}                     → single company detail
PATCH /companies/{id}                    → update name/category/is_active (owner only)
GET  /companies/{id}/logo                → serve logo binary (any authenticated user)
POST /companies/{id}/logo                → upload logo file (owner only, multipart/form-data)
GET  /companies/{id}/service-types       → list service types for a company
POST /companies/{id}/service-types       → create service type (owner only)
PATCH /service-types/{id}               → update service type (owner only)
```

**Logo endpoint implementation notes**:
- `POST /companies/{id}/logo`: validate Content-Type in (`image/png`, `image/jpeg`, `image/svg+xml`), validate file size ≤ 200 KB, write to `assets/logos/{company_id}.{ext}`, update `companies.logo_path`.
- `GET /companies/{id}/logo`: read `companies.logo_path`, return `FileResponse` with correct MIME type; return 404 if `logo_path` is NULL.
- The `assets/logos/` directory must be created at server startup if it does not exist.

**Gate**: `curl` tests against a running dev server confirm all endpoints return correct JSON and logo binary. Logo file appears under `assets/logos/` after upload.

---

### Phase 5: PyQt6 Client — Logo Cache and Company Selector Widget

**Objective**: Build reusable `CompanyLogoLabel` widget that fetches logos via API, caches them in-session, falls back to an initial-letter placeholder, and build a `CompanySelector` combo box that shows logo + name.

**Files to create**:
- `views/widgets/company_logo_label.py` — `CompanyLogoLabel(QLabel)`: calls `api_client.get_logo(company_id)` once per session, caches `QPixmap` in a module-level dict keyed by `company_id`, renders at configurable size (default 32×32); if request fails, renders colored initial placeholder using `QPainter`.
- `views/widgets/company_selector.py` — `CompanySelector(QComboBox)`: populated from `api_client.get_companies()`; each item shows `QIcon` (from cached logo pixmap) + company name; emits `company_changed(company_id: int)` signal; triggers `service_type_selector` refresh.

**Files to modify**:
- `views/transaction_view.py`:
  - Replace the current account `QComboBox` (flat list) with a two-level `CompanySelector` → `ServiceTypeSelector` → `AccountSelector` cascade for Deposit/Withdraw.
  - For Transfer/Exchange: add a second `CompanySelector` row labelled "Customer pays in via" and "Shop pays out via".
  - Remove `_map_tier_service_type()` helper (already deleted in Phase 2/3).
  - Commission preview panel reads `service_type_id` from selected account directly.
- `views/dashboard_view.py` — add company logos in any summary cards that reference service names.
- `views/cashier_view.py` — update account picker if it references `service_id`.

**Logo fallback implementation**:
```python
def _render_placeholder(company_name: str, size: int) -> QPixmap:
    # Draw a colored circle with the first letter of company_name
    # Color is deterministic: hash(company_name) % len(PALETTE)
    ...
```

**Session-level logo cache**:
```python
_logo_cache: dict[int, QPixmap] = {}  # module-level, cleared on logout

def get_logo_pixmap(api_client, company_id: int, company_name: str, size: int) -> QPixmap:
    if company_id not in _logo_cache:
        try:
            data = api_client.get_logo(company_id)
            px = QPixmap()
            px.loadFromData(data)
            _logo_cache[company_id] = px.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        except Exception:
            _logo_cache[company_id] = _render_placeholder(company_name, size)
    return _logo_cache[company_id]
```

**Gate**: Manual test: launch client, open transaction form, verify company logos appear next to names; disconnect network to server, verify placeholder renders; change transaction type to Transfer, verify dual company selectors appear.

---

### Phase 6: Owner Settings Panel — Company and ServiceType CRUD + Logo Upload

**Objective**: Allow Owner role to manage Companies and ServiceTypes from the settings panel, including logo upload.

**Files to create**:
- `views/settings/company_settings_view.py` — `CompanySettingsView(QWidget)`: table of companies; "Add", "Edit", "Deactivate" buttons; inline logo preview; "Upload Logo" button opens `QFileDialog` filtered to `*.png *.jpg *.svg`; validates ≤ 200 KB before upload; calls `api_client.upload_logo`.
- `views/settings/service_type_settings_view.py` — `ServiceTypeSettingsView(QWidget)`: filtered by selected company; "Add", "Edit", "Deactivate" buttons.

**Files to modify**:
- `views/dashboard_view.py` or equivalent settings entry point — add "Companies" and "Service Types" tabs to settings panel (Owner-only tab visibility).

**Gate**: Owner can upload a PNG logo, it appears in the company list within 30 s auto-refresh; non-owner roles cannot see the upload button (visibility check in code).

---

### Phase 7: PyInstaller Packaging Update

**Objective**: Ensure `assets/logos/` is included in the server bundle.

**Files to modify**:
- `NgweLweServer.spec` — add `Tree('assets/logos', prefix='assets/logos')` to `COLLECT` datas; add `('assets/logos', 'assets/logos')` to `datas` in `Analysis`.
- `setup_server.iss` — add entry to copy `{app}\assets\logos\*` during install.
- `build_v1.0.1.bat` (or equivalent build script) — ensure `assets/logos/` directory is created before PyInstaller run if it does not exist.

**Gate**: Build server bundle, run from `dist/`, upload a logo via the API, confirm logo file is written to `assets/logos/` relative to the executable's working directory.

---

## File Change Inventory

| File | Action | Phase |
|---|---|---|
| `backend/database.py` | Modify — add `_migrate_004` | 1 |
| `backend/database.sql` | Modify — add companies/service_types DDL, update accounts/commission_tiers | 1 |
| `assets/logos/.gitkeep` | Create | 1 |
| `models/company.py` | Create | 2 |
| `models/service_type.py` | Create | 2 |
| `models/account.py` | Modify — replace `service_id`/`service_type TEXT` with `service_type_id` | 2 |
| `models/commission_tier.py` | Modify — replace `service_type TEXT`/`account_type TEXT` with `service_type_id` | 2 |
| `repositories/company_repository.py` | Create | 2 |
| `repositories/service_type_repository.py` | Create | 2 |
| `repositories/account_repository.py` | Modify — new query by `service_type_id` | 2 |
| `repositories/commission_tier_repository.py` | Modify — lookup by `service_type_id: int` | 2 |
| `repositories/service_repository.py` | Deprecate (retain for rollback, mark deprecated) | 2 |
| `viewmodels/company_viewmodel.py` | Create | 3 |
| `viewmodels/service_type_viewmodel.py` | Create | 3 |
| `viewmodels/transaction_viewmodel.py` | Modify — remove `_map_tier_service_type`, use `service_type_id` | 3 |
| `viewmodels/account_viewmodel.py` | Modify — add company/service_type filter methods | 3 |
| `backend/routes/companies.py` | Create | 4 |
| `backend/routes/service_types.py` | Create | 4 |
| `backend/routes/accounts.py` | Modify — filter by `service_type_id` | 4 |
| `backend/routes/commission_tiers.py` | Modify — accept `service_type_id` | 4 |
| `backend/main.py` | Modify — register new routers, serve `assets/logos/` | 4 |
| `services/api_client.py` | Modify — add company/service-type/logo methods | 4 |
| `views/widgets/company_logo_label.py` | Create | 5 |
| `views/widgets/company_selector.py` | Create | 5 |
| `views/transaction_view.py` | Modify — two-level company→service_type→account cascade | 5 |
| `views/dashboard_view.py` | Modify — company logos in summaries | 5 |
| `views/cashier_view.py` | Modify — update account picker | 5 |
| `views/settings/company_settings_view.py` | Create | 6 |
| `views/settings/service_type_settings_view.py` | Create | 6 |
| `NgweLweServer.spec` | Modify — include `assets/logos/` | 7 |
| `setup_server.iss` | Modify — copy logos dir | 7 |

---

## Dependencies and Sequencing

```
Phase 1 (DB Migration)
    ↓
Phase 2 (Models + Repositories)     ← blocks everything downstream
    ↓
Phase 3 (Viewmodels)
    ↓
Phase 4 (REST Routes)  ←────────────────────────────────┐
    ↓                                                    │
Phase 5 (PyQt Widgets + Views) ──── requires Phase 4 API│
    ↓                                                    │
Phase 6 (Settings Panel) ──── requires Phase 5 widgets  │
    ↓                                                    │
Phase 7 (Packaging) ──── requires Phase 4 (assets dir)  │
```

Phase 7 can be prepared (spec file edits) in parallel with Phase 5–6.

---

## Risk Assessment

### High Risk

**R-01 — SQLite table-rebuild migration complexity**
- SQLite does not support `DROP COLUMN` or `DROP FOREIGN KEY`. Migrating `accounts` and `commission_tiers` requires creating `_v2` tables, copying data, dropping old tables, renaming. Any error leaves DB in inconsistent state.
- Mitigation: Wrap entire `_migrate_004` in a single `conn.executescript()` call. Take a backup of `ngwe_lwe.db` before running migration in production. Test against a copy of production DB before deployment.

**R-02 — Commission tier key change breaks fee calculation**
- Current tier lookup uses string keys assembled at runtime. Switching to integer FK means any unmapped combination silently returns `None` (zero commission).
- Mitigation: Write a pre-migration validation query that lists all distinct `(service_type, account_type)` pairs in `commission_tiers` and verifies each maps to a `service_types` row. Fail migration if any unmapped pair exists.

### Medium Risk

**R-03 — Legacy account rows with service_id pointing to non-canonical companies**
- The `services` table contains 14 rows (MPT Pay, OK Dollar, True Money, One Pay, AYA Pay, Yoma Pay, City Express, KBZ Express, Thai Bank). Accounts linked to these must map to a `service_type_id`.
- Mitigation: Resolve via Q1 clarification before writing `_migrate_004`. Create Company+ServiceType rows for all necessary legacy services, or deactivate unneeded accounts.

**R-04 — Transaction view regression**
- The cascade `CompanySelector → ServiceTypeSelector → AccountSelector` is a significant UI refactor. Any signal wiring error could leave the commission preview blank or show incorrect tiers.
- Mitigation: Implement each selector as an isolated widget with unit-testable `populate(data)` and `selected_id()` methods before wiring into `transaction_view.py`.

### Low Risk

**R-05 — Logo file size and format validation**
- A malformed SVG or corrupt image uploaded via the API could crash `QPixmap.loadFromData`.
- Mitigation: Wrap `loadFromData` in try/except in the client; fall back to placeholder. Server-side: reject uploads that fail `imghdr` / `python-magic` validation (or check magic bytes manually).

**R-06 — PyInstaller `assets/logos/` not writable at runtime**
- If the server is installed to a write-protected location (e.g., `Program Files`), logo writes will fail.
- Mitigation: At server startup, check `assets/logos/` is writable; if not, log a clear error and fall back to a configurable `LOGO_DIR` environment variable.

---

## Testing Strategy

### Unit Tests (Python `pytest`)

| Test | Location | What it verifies |
|---|---|---|
| `test_migrate_004_accounts` | `tests/test_migration.py` | Every account row has a valid `service_type_id` after migration |
| `test_migrate_004_tiers` | `tests/test_migration.py` | Every commission_tier row has a valid `service_type_id` after migration |
| `test_migrate_004_zero_data_loss` | `tests/test_migration.py` | Row counts in accounts and commission_tiers unchanged |
| `test_tier_lookup_by_id` | `tests/test_commission_tier_repository.py` | `get_tier_for_amount(service_type_id, amount)` returns correct tier |
| `test_commission_calc_kpay_wst` | `tests/test_transaction_viewmodel.py` | Commission for KBZ Pay WST 50,000 MMK = 200 (matches legacy result) |
| `test_commission_calc_wave_wst` | `tests/test_transaction_viewmodel.py` | Commission for Wave Money WST 10,000 MMK = 123 deposit |
| `test_logo_upload_size_limit` | `tests/test_company_routes.py` | 201 KB file rejected with 422 |
| `test_logo_upload_invalid_type` | `tests/test_company_routes.py` | PDF file rejected with 422 |
| `test_logo_serve` | `tests/test_company_routes.py` | Uploaded PNG returned byte-for-byte by `GET /companies/{id}/logo` |

### Integration Tests

| Test | What it verifies |
|---|---|
| `test_deposit_flow_end_to_end` | Deposit transaction via API, verify account balance updated, commission recorded |
| `test_transfer_flow_cross_company` | Transfer from KBZ Bank account to KBZ Pay account, verify both balances, verify from/to accounts resolved to correct companies |
| `test_company_deactivate_cascade` | Deactivating a company deactivates all its service_types; `GET /accounts?active=true` returns 0 for those service_types |

### Manual Acceptance Tests (PyQt6 Client)

| Test ID | Steps | Pass Criterion |
|---|---|---|
| AC-01 | Open transaction form → Deposit tab → select "KBZ Pay" company | KBZ Pay logo appears; ServiceType dropdown shows "WST", "Pay_To_Pay" |
| AC-02 | Select WST, select account, enter 50000, click Calculate | Commission preview shows 1000 (fee) + 200 (commission) per KPAY_WST tier |
| AC-03 | Open transaction form → Transfer tab | Two company selectors appear: "Customer pays in via" and "Shop pays out via" |
| AC-04 | Kill server process, open transaction form | Logo placeholder (initial letter) renders for each company |
| AC-05 | Login as Owner → Settings → Companies → Upload Logo | File dialog opens; PNG ≤ 200 KB accepted; logo appears in company list |
| AC-06 | Login as Employee → Settings | Companies tab is not visible |
| AC-07 | Run server bundle from `dist/` after PyInstaller build | Upload logo, file appears under `dist/assets/logos/` |

---

## Complexity Tracking

| Item | Complexity | Reason |
|---|---|---|
| `_migrate_004` table rebuild | High | SQLite constraints require full table copy + rename for column changes |
| Commission tier key refactor | High | Touches model, repository, viewmodel, and view layers simultaneously |
| CompanySelector cascade widget | Medium | Three-level cascade with async logo loading and signal coordination |
| Logo upload/serve endpoint | Low | Standard FastAPI `UploadFile` + `FileResponse` pattern |
| PyInstaller datas update | Low | One-line addition to existing spec file |

---

## Clarifications Received

All clarification questions have been resolved. The answers below are incorporated throughout the plan body.

1. **Q1 — Legacy service migration scope**: All existing services (MPT Pay, OK Dollar, True Money, One Pay, AYA Pay, Yoma Pay, City Express, KBZ Express, Thai Bank) are migrated forward as full Company records. None will be deactivated at this time. `migration_004` seeds all 14 companies with `is_active = 1`.

2. **Q2 — True Money commission tiers**: True Money will have its own dedicated commission tier rows (WST and Pay_To_Pay) seeded in `migration_004`, separate from KBZ Pay and Wave Money tiers. No tier sharing between companies.

3. **Q3 — Cross-company columns on transactions**: `from_company_id` and `to_company_id` are stored as explicit new INTEGER FK columns in the `transactions` table. This provides better audit trails and simpler reporting queries. Existing Transfer/Exchange rows are back-filled during migration via join through `accounts → service_types → companies`.

---

## Progress Tracking

- [ ] Phase 1: DB migration written and tested against production DB copy
- [ ] Phase 2: Models and repositories updated; commission tier lookup verified
- [ ] Phase 3: Viewmodels updated; regression fixtures pass
- [ ] Phase 4: REST routes implemented; API smoke tests pass
- [ ] Phase 5: PyQt widgets built; manual UI acceptance tests AC-01 through AC-04 pass
- [ ] Phase 6: Settings panel built; AC-05 and AC-06 pass
- [ ] Phase 7: PyInstaller bundle updated; AC-07 passes
- [x] All clarification questions resolved (Q1, Q2, Q3 — answered 2026-04-12)
- [ ] Migration tested on a copy of the production database before deployment

---

*All clarification questions resolved. Run `/buddy:tasks` to generate the granular task list.*
