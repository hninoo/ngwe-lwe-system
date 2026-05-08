# Company Logo and Service Hierarchy — Implementation Tasks

**Plan**: [plan.md](plan.md)
**Spec**: [spec.md](spec.md)
**Generated**: 2026-04-12
**Status**: Ready for Review

> **Note**: Clarification questions Q1, Q2, Q3 resolved 2026-04-12. All `[NEEDS CLARIFICATION: ...]` markers removed. See "Resolved Clarifications" section at end of document.
**Total Tasks**: 47
**Parallel Tasks**: 18 marked [P]

---

## Task Categories

| Category | Tasks | Description |
|---|---|---|
| Setup | T001–T004 | Directory scaffolding, test infrastructure, assets |
| Tests (TDD) | T005–T018 | Migration tests, repository tests, route tests — written first |
| Core — Phase 1 | T019–T021 | Database migration (`_migrate_004`) and fresh-install SQL |
| Core — Phase 2 | T022–T030 | Models and repositories |
| Core — Phase 3 | T031–T033 | Viewmodels |
| Core — Phase 4 | T034–T040 | REST routes and API client |
| Core — Phase 5 | T041–T044 | PyQt6 widgets and view updates |
| Core — Phase 6 | T045–T046 | Owner settings panel |
| Polish — Phase 7 | T047 | PyInstaller packaging update |

---

## Setup

### T001 — Create `tests/` directory with pytest infrastructure [P] [X]

**File**: `tests/__init__.py`, `tests/conftest.py`, `pyproject.toml` or `pytest.ini`

Create the top-level test package and shared fixtures. The `conftest.py` must provide:
- A `tmp_db` fixture: creates a fresh in-memory or file-based SQLite DB, runs `init_db()`, yields the connection, then tears down.
- A `seeded_db` fixture: extends `tmp_db` by loading the full schema including `_migrate_004` seed data (companies, service_types, commission_tiers).
- A `test_client` fixture: a FastAPI `TestClient` wrapping the app with a test DB injected.
- A `auth_headers` fixture: returns `{"Authorization": "Bearer <test-owner-token>"}` for route tests.

```
tests/__init__.py
tests/conftest.py
```

If `pytest` and `httpx` are not in `pyproject.toml`/`requirements.txt`, add them.

---

### T002 — Create `assets/logos/` directory with `.gitkeep` [P] [X]

**File**: `assets/logos/.gitkeep`

Create the directory that will store company logo files. The `.gitkeep` ensures the empty directory is tracked by git and included in PyInstaller builds.

```
assets/logos/.gitkeep
```

---

### T003 — Create `views/widgets/` package [P] [X]

**File**: `views/widgets/__init__.py`

Create the `widgets` sub-package inside `views/`. This package will contain `company_logo_label.py` and `company_selector.py` (implemented in Phase 5).

```
views/widgets/__init__.py
```

---

### T004 — Create `views/settings/` package [P] [X]

**File**: `views/settings/__init__.py`

Create the `settings` sub-package inside `views/`. This package will contain `company_settings_view.py` and `service_type_settings_view.py` (implemented in Phase 6).

```
views/settings/__init__.py
```

---

## Tests (TDD)

All tests in this section must be written before the implementation tasks they exercise. Run `pytest tests/ -x` to confirm they fail as expected (red) before implementation.

### T005 — Write migration tests: accounts re-linking [P] [X]

**File**: `tests/test_migration.py`

Write the `test_migrate_004_accounts` test case. The test must:
1. Create a minimal pre-migration DB with the old `accounts` schema (columns: `id`, `service_id`, `account_name`, `account_type`, `service_type` TEXT, `phone_number`, `balance`, `commission_rate`, `is_active`).
2. Insert at least one account row for each legacy service_type value (`KPAY`, `WAVE` with `account_type='agent'`, `WAVE` with `account_type='personal'`).
3. Call `_migrate_004(conn)` (import the private function from `backend.database`).
4. Assert every row in `accounts` has a non-NULL `service_type_id` INTEGER.
5. Assert `service_type_id` resolves to a valid row in `service_types`.
6. Assert the old `service_type` TEXT column no longer exists on `accounts`.
7. Assert the old `service_id` column no longer exists on `accounts`.

```
tests/test_migration.py  (new file, add test_migrate_004_accounts)
```

---

### T006 — Write migration tests: commission_tiers re-linking [P] [X]

**File**: `tests/test_migration.py`

Add `test_migrate_004_tiers` to the migration test file. The test must:
1. Insert legacy `commission_tiers` rows for keys: `KPAY_WST`, `WAVE_WST`, `WAVE_ACCOUNT`, `TRUE_MONEY_WST`, `TRUE_MONEY_PAY_TO_PAY`.
2. Call `_migrate_004(conn)`.
3. Assert every tier row has a non-NULL `service_type_id` INTEGER.
4. Assert the old `service_type` TEXT column no longer exists on `commission_tiers`.
5. Assert the old `account_type` TEXT column no longer exists on `commission_tiers`.

```
tests/test_migration.py  (append test_migrate_004_tiers)
```

---

### T007 — Write migration tests: zero data loss [P] [X]

**File**: `tests/test_migration.py`

Add `test_migrate_004_zero_data_loss`. The test must:
1. Count rows in `accounts` and `commission_tiers` before calling `_migrate_004`.
2. Call `_migrate_004(conn)`.
3. Assert post-migration row counts match pre-migration counts exactly.
4. Assert `transactions` row count is unchanged.

```
tests/test_migration.py  (append test_migrate_004_zero_data_loss)
```

---

### T008 — Write migration tests: transactions from/to company columns [P] [X]

**File**: `tests/test_migration.py`

Add `test_migrate_004_transaction_company_columns`. The test must:
1. Insert a transfer transaction with `account_id` linking to a KPAY account.
2. Call `_migrate_004(conn)`.
3. Assert `transactions` has `from_company_id` and `to_company_id` columns.
4. Assert the transfer transaction's `from_company_id` is non-NULL and maps to the correct company row.

```
tests/test_migration.py  (append test_migrate_004_transaction_company_columns)
```

---

### T009 — Write repository tests: `CompanyRepository` [P] [X]

**File**: `tests/test_company_repository.py`

Write unit tests for `CompanyRepository` (to be created in T022). Tests must cover:
- `get_all_active()` returns only rows where `is_active = 1`.
- `get_by_id(id)` returns the correct `Company` dataclass instance.
- `create(data)` inserts a new company and returns the new `id`.
- `update(id, data)` updates `name` and `category` fields.
- `deactivate(id)` sets `is_active = 0`.

Use the `seeded_db` fixture from `conftest.py`.

```
tests/test_company_repository.py  (new file)
```

---

### T010 — Write repository tests: `ServiceTypeRepository` [P] [X]

**File**: `tests/test_service_type_repository.py`

Write unit tests for `ServiceTypeRepository` (to be created in T023). Tests must cover:
- `get_by_company(company_id)` returns only service_types for that company.
- `get_by_id(id)` returns the correct `ServiceType` dataclass instance.
- `create(data)` inserts and returns the new `id`.
- `deactivate(id)` sets `is_active = 0` for the service_type and does not affect sibling rows.

```
tests/test_service_type_repository.py  (new file)
```

---

### T011 — Write repository tests: `CommissionTierRepository` with `service_type_id` [P] [X]

**File**: `tests/test_commission_tier_repository.py`

Write tests for the updated `CommissionTierRepository.get_tier_for_amount(service_type_id, amount)` signature. Tests must cover:
- `test_tier_lookup_by_id`: `get_tier_for_amount(service_type_id=<kpay_wst_id>, amount=50000)` returns the correct tier (verify `comm_deposit` matches seeded value).
- `test_tier_lookup_wave_wst`: Wave Money WST lookup returns distinct tier from KBZ Pay WST.
- `test_tier_lookup_true_money`: True Money WST has its own dedicated tier row.
- `test_tier_lookup_no_match`: Returns `None` for a service_type_id with no tier rows.

Use the `seeded_db` fixture.

```
tests/test_commission_tier_repository.py  (new file)
```

---

### T012 — Write viewmodel regression tests: commission calculation [P] [X]

**File**: `tests/test_transaction_viewmodel.py`

Write regression tests verifying commission amounts are preserved after the `service_type_id` refactor. Tests must cover:
- `test_commission_calc_kpay_wst`: Commission for KBZ Pay WST account at 50,000 MMK matches expected value (use seeded tier's `comm_deposit`).
- `test_commission_calc_wave_wst`: Commission for Wave Money WST agent account at 10,000 MMK returns the correct tier's `comm_deposit`.
- `test_commission_calc_wave_account`: Commission for Wave Money Pay_To_Pay personal account returns correct tier.
- `test_commission_calc_true_money_wst`: True Money WST returns its own dedicated tier (not KPAY tier).

Use dependency injection: pass mock repositories to `TransactionViewModel.__init__` so tests do not require a live DB.

```
tests/test_transaction_viewmodel.py  (new file)
```

---

### T013 — Write route tests: `GET /companies` and `GET /companies/{id}` [P] [X]

**File**: `tests/test_company_routes.py`

Write HTTP route tests using `TestClient`. Tests must cover:
- `GET /companies/` returns a list of company dicts with keys `id`, `name`, `category`, `is_active`, `logo_path`.
- `GET /companies/{id}` returns a single company dict.
- `GET /companies/9999` returns 404.
- Unauthenticated requests return 401.

```
tests/test_company_routes.py  (new file)
```

---

### T014 — Write route tests: logo upload and serve [P] [X]

**File**: `tests/test_company_routes.py`

Append logo endpoint tests to the company routes test file:
- `test_logo_upload_size_limit`: POST a 201 KB binary as `image/png` → expect 422.
- `test_logo_upload_invalid_type`: POST a PDF file as `application/pdf` → expect 422.
- `test_logo_serve`: Upload a valid PNG (≤ 200 KB), then `GET /companies/{id}/logo` returns the exact same bytes with `Content-Type: image/png`.
- `test_logo_serve_not_found`: `GET /companies/{id}/logo` when `logo_path IS NULL` → returns 404.
- Non-owner upload attempt → returns 403.

```
tests/test_company_routes.py  (append)
```

---

### T015 — Write route tests: `GET/POST /companies/{id}/service-types` [P] [X]

**File**: `tests/test_service_type_routes.py`

Write HTTP route tests:
- `GET /companies/{id}/service-types` returns list of service_type dicts with `id`, `company_id`, `name`, `operation`, `is_active`.
- `POST /companies/{id}/service-types` with owner auth creates a new service_type and returns 201.
- `POST /companies/{id}/service-types` with employee auth returns 403.
- `PATCH /service-types/{id}` with owner auth updates `name` / `is_active`.

```
tests/test_service_type_routes.py  (new file)
```

---

### T016 — Write route tests: updated `GET /accounts` with `service_type_id` filter [P] [X]

**File**: `tests/test_account_routes.py`

Write HTTP route tests for the updated accounts endpoint:
- `GET /accounts/?service_type_id=<id>` returns only accounts linked to that service_type.
- `GET /accounts/` without filter returns all active accounts.
- Response payload includes `service_type_id` and `company_id` fields; does NOT include old `service_id` or `service_type` TEXT fields.

```
tests/test_account_routes.py  (new file)
```

---

### T017 — Write route tests: updated `GET /commission-tiers` with `service_type_id` filter [P] [X]

**File**: `tests/test_commission_tier_routes.py`

Write HTTP route tests:
- `GET /commission-tiers/?service_type_id=<id>` returns tiers for that service_type.
- `GET /commission-tiers/lookup?service_type_id=<id>&amount=50000` returns correct tier dict.
- Legacy `service_type` string query param is no longer accepted (returns 422).

```
tests/test_commission_tier_routes.py  (new file)
```

---

### T018 — Write integration tests: deposit/transfer end-to-end [P] [X]

**File**: `tests/test_integration.py`

Write integration tests that exercise the full API stack:
- `test_deposit_flow_end_to_end`: POST a deposit transaction via `/transactions/` with a seeded account → assert 201 response, assert account balance updated via `GET /accounts/{id}`, assert commission recorded.
- `test_transfer_flow_cross_company`: POST a transfer from a KBZ Bank account to a KBZ Pay account → assert both balances updated, assert response includes `from_company_id` and `to_company_id`.
- `test_company_deactivate_cascade`: PATCH company `is_active=false` → `GET /accounts/?active=true` returns empty list for accounts linked to that company's service_types.

```
tests/test_integration.py  (new file)
```

---

## Core — Phase 1: Database Migration

### T019 — Write `_migrate_004(conn)` in `backend/database.py` [X]

**File**: `backend/database.py`

This is the highest-risk task. Wrap the entire migration in a single transaction. Implement `_migrate_004(conn)` following this exact order:

1. **Create `companies` table** with trigger `trg_companies_updated_at`.
2. **Seed 14 companies** using `INSERT OR IGNORE` with `is_active = 1`:
   - Canonical (6): KBZ Pay (Pay), Wave Money (Pay), True Money (Pay), KBZ Bank (Bank), AYA Bank (Bank), CB Bank (Bank).
   - Legacy from `services` table (8): MPT Pay (Pay), OK Dollar (Pay), One Pay (Pay), AYA Pay (Pay), Yoma Pay (Pay), City Express (Pay), KBZ Express (Pay), Thai Bank (Bank).
3. **Create `service_types` table** with trigger `trg_service_types_updated_at`.
4. **Seed service_types** for every company (`INSERT OR IGNORE`):
   - Pay-category companies: WST (All), Pay_To_Pay (All) — including dedicated True Money rows.
   - Bank-category companies: Transfer (Transfer), Exchange (Exchange).
5. **Pre-migration validation**: Query all distinct `(service_type TEXT, account_type TEXT)` pairs in `commission_tiers`. Verify each maps to a `service_types` row. If any unmapped pair exists, raise `RuntimeError` with a descriptive message listing the unmapped pairs.
6. **Rebuild `accounts` table** (SQLite table-copy pattern):
   - Create `accounts_v2` with `service_type_id INTEGER NOT NULL FK → service_types`, dropping `service_id` and `service_type TEXT`.
   - `INSERT INTO accounts_v2 SELECT ... FROM accounts JOIN services ... JOIN companies ... JOIN service_types ...` to populate `service_type_id`.
   - `DROP TABLE accounts; ALTER TABLE accounts_v2 RENAME TO accounts`.
   - Recreate indexes: `idx_accounts_service_type_id`.
7. **Seed True Money commission tier rows**: `INSERT OR IGNORE` for True Money WST and Pay_To_Pay tiers, copying commission values from KBZ Pay WST (or specifying explicit values from the spec).
8. **Rebuild `commission_tiers` table** (table-copy pattern):
   - Create `commission_tiers_v2` with `service_type_id INTEGER NOT NULL FK → service_types`, dropping `service_type TEXT` and `account_type TEXT`.
   - Populate using the legacy key mapping table:
     - `KPAY_WST` → company `KBZ Pay`, service_type `WST`
     - `WAVE_WST` → company `Wave Money`, service_type `WST`
     - `WAVE_ACCOUNT` → company `Wave Money`, service_type `Pay_To_Pay`
     - `TRUE_MONEY_WST` → company `True Money`, service_type `WST`
     - `TRUE_MONEY_PAY_TO_PAY` → company `True Money`, service_type `Pay_To_Pay`
   - `DROP TABLE commission_tiers; ALTER TABLE commission_tiers_v2 RENAME TO commission_tiers`.
9. **Add `from_company_id` and `to_company_id`** to `transactions` using `ALTER TABLE ... ADD COLUMN` (safe in SQLite).
10. **Back-fill `from_company_id` / `to_company_id`** for existing Transfer/Exchange rows via: `UPDATE transactions SET from_company_id = (SELECT st.company_id FROM accounts a JOIN service_types st ON a.service_type_id = st.id WHERE a.id = transactions.account_id) WHERE transaction_type IN ('transfer','exchange')`. Similarly for `to_company_id` using `to_account_id`.
11. **Register version 4** in `_run_migrations`: description `"Add companies, service_types; migrate accounts, commission_tiers, and transactions"`.

**Gate**: `python -c "from backend.database import init_db; init_db()"` against a copy of the production DB completes without error. T005–T008 pass (green).

```
backend/database.py  (modify — add _migrate_004, register in _run_migrations)
```

---

### T020 — Update `backend/database.sql` for fresh installs [X]

**File**: `backend/database.sql`

Update the fresh-install schema so new deployments match the migrated schema without running legacy migrations:

1. Add `companies` table DDL (with trigger) as section 2.
2. Add `service_types` table DDL (with trigger) as section 3.
3. Renumber existing sections accordingly.
4. Remove `service_type TEXT` and `service_id INTEGER` from `accounts` DDL; add `service_type_id INTEGER NOT NULL REFERENCES service_types(id)`.
5. Remove `service_type TEXT` and `account_type TEXT` from `commission_tiers` DDL; add `service_type_id INTEGER NOT NULL REFERENCES service_types(id)`.
6. Add `from_company_id INTEGER REFERENCES companies(id)` and `to_company_id INTEGER REFERENCES companies(id)` to `transactions` DDL.
7. Remove the legacy `services` seed INSERT block.
8. Add `companies` seed INSERT block (all 14 rows).
9. Add `service_types` seed INSERT block (all service_type rows per company).
10. Update `schema_version` seed to include version 4.

```
backend/database.sql  (modify)
```

---

### T021 — Add startup `assets/logos/` directory check to server [P] [X]

**File**: `backend/main.py`

In the `lifespan` async context manager (before `init_db()`), add:
```python
import os
logos_dir = Path("assets/logos")
logos_dir.mkdir(parents=True, exist_ok=True)
```

Also add a writability check: if `logos_dir` is not writable, log a `WARNING` using the Python `logging` module and record the configured `LOGO_DIR` environment variable fallback.

```
backend/main.py  (modify — add logos dir creation in lifespan)
```

---

## Core — Phase 2: Models and Repositories

### T022 — Create `models/company.py` [P] [X]

**File**: `models/company.py`

Create the `Company` dataclass exactly as specified in the plan:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class Company:
    id: Optional[int] = None
    name: Optional[str] = None
    logo_path: Optional[str] = None
    category: Optional[str] = None   # 'Pay' | 'Bank' | 'Both'
    is_active: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
```

```
models/company.py  (create)
```

---

### T023 — Create `models/service_type.py` [P] [X]

**File**: `models/service_type.py`

Create the `ServiceType` dataclass:

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class ServiceType:
    id: Optional[int] = None
    company_id: Optional[int] = None
    name: Optional[str] = None       # 'WST' | 'Pay_To_Pay' | 'Transfer' | 'Exchange'
    operation: Optional[str] = None  # 'Deposit'|'Withdraw'|'Transfer'|'Exchange'|'All'
    is_active: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
```

```
models/service_type.py  (create)
```

---

### T024 — Update `models/account.py` [X]

**File**: `models/account.py`

Replace the `service_id` and `service_type TEXT` fields with `service_type_id: int`. Add `company_id: int` as a denormalized display field populated via join. Remove `account_type` from the model (it is no longer a column — the account_type concept is now captured in the ServiceType name e.g. `WST` vs `Pay_To_Pay`).

[NEEDS CLARIFICATION: The plan removes `account_type` TEXT from the `accounts` table during the migration table rebuild (step 6 in T019). However, the current `Account` model has `account_type: Optional[str] = None` and it is used in `transaction_view.py` to display account type labels and in `commission_tier_repository.py` for tier lookups. After migration, does `account_type` still exist as a column in accounts (e.g., kept as-is for display) or is it fully dropped? The plan says to drop it from `accounts` and from `commission_tiers`, but does not explicitly show it being retained. Please confirm: should `account_type` be completely dropped from the `accounts` table, or should it be retained for UI display purposes?]

Update `_row_to_model` in `AccountRepository` (T026) accordingly once this is confirmed.

```
models/account.py  (modify)
```

---

### T025 — Update `models/commission_tier.py` [P] [X]

**File**: `models/commission_tier.py`

Replace `service_type: Optional[str]` and `account_type: Optional[str]` fields with `service_type_id: Optional[int]`:

```python
@dataclass
class CommissionTier:
    id: Optional[int] = None
    service_type_id: Optional[int] = None   # FK → service_types
    amount_from: Optional[float] = None
    amount_to: Optional[float] = None
    fee_amount_type: str = "FIXED"
    fee_amount_deposit: Optional[float] = None
    fee_amount_withdraw: Optional[float] = None
    comm_type: str = "FIXED"
    comm_deposit: Optional[float] = None
    comm_withdraw: Optional[float] = None
    additional_fee_type: str = "FIXED"
    additional_fee_deposit_amount: Optional[float] = None
    additional_fee_withdraw_amount: Optional[float] = None
    is_active: Optional[bool] = None
```

```
models/commission_tier.py  (modify)
```

---

### T026 — Update `models/transaction.py` [P] [X]

**File**: `models/transaction.py`

Add `from_company_id: Optional[int] = None` and `to_company_id: Optional[int] = None` fields to the `Transaction` dataclass. These correspond to the new columns added to the `transactions` table in `_migrate_004`.

```
models/transaction.py  (modify)
```

---

### T027 — Create `repositories/company_repository.py` [P] [X]

**File**: `repositories/company_repository.py`

Create `CompanyRepository(BaseRepository)` with:
- `table` property returning `"companies"`.
- `_row_to_model(row)` returning a `Company` instance.
- `get_all_active() -> list[Company]`: `SELECT * FROM companies WHERE is_active = 1 ORDER BY name`.
- `get_by_id(id) -> Optional[Company]`: inherited from `BaseRepository`.
- `create(data) -> int`: inherited.
- `update(id, data) -> bool`: inherited.
- `deactivate(company_id: int) -> bool`: sets `is_active = 0` and cascades to all `service_types` for that company (two UPDATE statements in a single `get_cursor(commit=True)` block).

```
repositories/company_repository.py  (create)
```

---

### T028 — Create `repositories/service_type_repository.py` [P] [X]

**File**: `repositories/service_type_repository.py`

Create `ServiceTypeRepository(BaseRepository)` with:
- `table` property returning `"service_types"`.
- `_row_to_model(row)` returning a `ServiceType` instance.
- `get_by_company(company_id: int) -> list[ServiceType]`: `SELECT * FROM service_types WHERE company_id = ? AND is_active = 1`.
- `get_all_active() -> list[ServiceType]`: `SELECT * FROM service_types WHERE is_active = 1`.
- `deactivate(service_type_id: int) -> bool`: sets `is_active = 0`.

```
repositories/service_type_repository.py  (create)
```

---

### T029 — Update `repositories/account_repository.py` [X]

**File**: `repositories/account_repository.py`

Update the repository to work with the new schema:
- In `_row_to_model`, replace `service_id=row["service_id"]` and `service_type=row["service_type"]` with `service_type_id=row["service_type_id"]` and `company_id=row.get("company_id")`.
- Remove `get_by_service(service_id)`.
- Add `get_by_service_type(service_type_id: int) -> list[Account]`: `SELECT a.*, st.company_id FROM accounts a JOIN service_types st ON a.service_type_id = st.id WHERE a.service_type_id = ? AND a.is_active = 1`.
- Add `get_by_company(company_id: int) -> list[Account]`: `SELECT a.*, st.company_id FROM accounts a JOIN service_types st ON a.service_type_id = st.id WHERE st.company_id = ? AND a.is_active = 1`.
- Update `get_all_active()` to JOIN `service_types` and include `company_id` in the result set.

```
repositories/account_repository.py  (modify)
```

---

### T030 — Update `repositories/commission_tier_repository.py` [X]

**File**: `repositories/commission_tier_repository.py`

Update to use `service_type_id: int` instead of string-based lookups:
- Update `_row_to_model` to map `service_type_id=row["service_type_id"]` (remove `service_type` and `account_type` fields).
- Replace `get_tier_for_amount(service_type: str, account_type: str, amount: float)` signature with `get_tier_for_amount(service_type_id: int, amount: float) -> Optional[CommissionTier]`. Update the SQL: `WHERE service_type_id = ? AND is_active = 1 AND (amount_from IS NULL OR amount_from <= ?) AND (amount_to IS NULL OR amount_to >= ?) LIMIT 1`.
- Replace `get_by_service_type(service_type: str, account_type: str)` signature with `get_by_service_type(service_type_id: int) -> list[CommissionTier]`.
- Update `create` and `update` methods to use `service_type_id` instead of `service_type`/`account_type`.

```
repositories/commission_tier_repository.py  (modify)
```

---

### T031 — Deprecate `repositories/service_repository.py` [X]

**File**: `repositories/service_repository.py`

Add a module-level deprecation warning at the top of the file:
```python
import warnings
warnings.warn(
    "ServiceRepository is deprecated after migration_004. "
    "Use CompanyRepository and ServiceTypeRepository instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

Do NOT delete the file — it is retained for potential rollback. Also remove the `ServiceRepository` import from `viewmodels/transaction_viewmodel.py` (the viewmodel no longer needs it after T032).

```
repositories/service_repository.py  (modify — add deprecation warning)
```

---

## Core — Phase 3: Viewmodels

### T032 — Create `viewmodels/company_viewmodel.py` [P] [X]

**File**: `viewmodels/company_viewmodel.py`

Create `CompanyViewModel` with:
- Constructor accepting optional `CompanyRepository` and `ServiceTypeRepository` instances.
- `get_all_active() -> list[Company]`: delegates to `CompanyRepository.get_all_active()`.
- `get_service_types(company_id: int) -> list[ServiceType]`: delegates to `ServiceTypeRepository.get_by_company(company_id)`.
- `create_company(name, category) -> Company`: creates and returns the new company.
- `update_company(company_id, data) -> bool`: delegates to repo `update`.
- `deactivate_company(company_id) -> bool`: delegates to `CompanyRepository.deactivate(company_id)`.
- `upload_logo_path(company_id: int, logo_path: str) -> bool`: calls `repo.update(company_id, {"logo_path": logo_path})`.

```
viewmodels/company_viewmodel.py  (create)
```

---

### T033 — Create `viewmodels/service_type_viewmodel.py` [P] [X]

**File**: `viewmodels/service_type_viewmodel.py`

Create `ServiceTypeViewModel` with:
- Constructor accepting optional `ServiceTypeRepository`.
- `get_by_company(company_id: int) -> list[ServiceType]`.
- `create_service_type(company_id, name, operation) -> ServiceType`.
- `update_service_type(service_type_id, data) -> bool`.
- `deactivate(service_type_id) -> bool`.

```
viewmodels/service_type_viewmodel.py  (create)
```

---

### T034 — Update `viewmodels/transaction_viewmodel.py` [X]

**File**: `viewmodels/transaction_viewmodel.py`

Remove the `_map_tier_service_type` helper function and update all references to use `service_type_id` directly from the `Account` object:

1. Remove `from repositories.service_repository import ServiceRepository` import.
2. Remove `service_repo` parameter from `__init__` and `self._service_repo`.
3. Delete the `_map_tier_service_type` function.
4. In `_get_tier(account, amount)`: replace the string mapping call with `return self._tier_repo.get_tier_for_amount(account.service_type_id, amount)`. Remove `service_type` and `account_type` local variables.
5. In `create_transfer`: add `from_company_id` and `to_company_id` fields to the `data` dict, resolved from `from_account.service_type_id` → `service_types.company_id` via a lightweight `ServiceTypeRepository` lookup. Pass `None` for deposit/withdraw transactions.
6. Similarly update `create_deposit`, `create_withdraw`, `create_exchange` to pass `from_company_id` (resolved from `account.service_type_id`).

**Gate**: T012 tests pass (green).

```
viewmodels/transaction_viewmodel.py  (modify)
```

---

### T035 — Update `viewmodels/account_viewmodel.py` [X]

**File**: `viewmodels/account_viewmodel.py`

Add new methods to `AccountViewModel`:
- `get_accounts_by_company(company_id: int) -> list[Account]`: delegates to `account_repo.get_by_company(company_id)`.
- `get_accounts_by_service_type(service_type_id: int) -> list[Account]`: delegates to `account_repo.get_by_service_type(service_type_id)`.
- Remove `get_accounts_by_service(service_id)` method (delegates to the now-removed `get_by_service`).

```
viewmodels/account_viewmodel.py  (modify)
```

---

## Core — Phase 4: REST Routes and API Client

### T036 — Create `backend/routes/companies.py` [X]

**File**: `backend/routes/companies.py`

Create a new FastAPI router with prefix `/companies` implementing all company endpoints:

- `GET /companies/` → `list[dict]`: returns all active companies; each dict includes `id`, `name`, `logo_path`, `category`, `is_active`. Auth: any authenticated user.
- `POST /companies/` → `dict`: owner only; body: `{name, category}`; returns `{id, message}`.
- `GET /companies/{company_id}` → `dict`: single company. Returns 404 if not found. Auth: any authenticated user.
- `PATCH /companies/{company_id}` → `dict`: owner only; body allows `name`, `category`, `is_active`.
- `POST /companies/{company_id}/logo` → `dict`: owner only; `UploadFile` multipart form. Validate `Content-Type` in (`image/png`, `image/jpeg`, `image/svg+xml`). Validate file size ≤ 200 KB (204,800 bytes) — read all bytes first, reject with 422 if oversized. Write to `assets/logos/{company_id}.{ext}`. Update `companies.logo_path`. Return `{message, logo_path}`.
- `GET /companies/{company_id}/logo` → `FileResponse`: read `logo_path` from DB; return `FileResponse` with correct MIME type. Return 404 if `logo_path IS NULL` or file does not exist.
- `GET /companies/{company_id}/service-types` → `list[dict]`: returns service_types for the company. Auth: any authenticated user.
- `POST /companies/{company_id}/service-types` → `dict`: owner only; body: `{name, operation}`.

Use `CompanyViewModel` and `ServiceTypeViewModel` instances (module-level singletons, same pattern as other routes).

```
backend/routes/companies.py  (create)
```

---

### T037 — Create `backend/routes/service_types.py` [X]

**File**: `backend/routes/service_types.py`

Create a new FastAPI router with prefix `/service-types`:

- `PATCH /service-types/{service_type_id}` → `dict`: owner only; body allows `name`, `operation`, `is_active`.
- `DELETE /service-types/{service_type_id}` → equivalent to deactivate (sets `is_active = 0`); owner only.

```
backend/routes/service_types.py  (create)
```

---

### T038 — Update `backend/routes/accounts.py` [X]

**File**: `backend/routes/accounts.py`

Update to use `company_id` and `service_type_id` server-side filters:
- Replace `service_id: int | None` query param with two optional params: `company_id: int | None` and `service_type_id: int | None`.
- When both are provided: call `_account_vm.get_accounts_by_service_type(service_type_id)` (service_type already implies company).
- When only `company_id` is provided: call `_account_vm.get_accounts_by_company(company_id)`.
- When neither is provided: return all active accounts.
- Ensure the response payload includes `service_type_id` and `company_id` fields; remove `service_id` and `service_type` TEXT from the serialized output.
- Example: `GET /accounts?company_id=1&service_type_id=2`

```
backend/routes/accounts.py  (modify)
```

---

### T039 — Update `backend/routes/commission_tiers.py` [X]

**File**: `backend/routes/commission_tiers.py`

Update all endpoints to use `service_type_id: int` instead of `service_type: str` and `account_type: str`:
- `GET /commission-tiers/` query params: replace `service_type: str, account_type: str` with `service_type_id: int`.
- `GET /commission-tiers/lookup` query params: replace `service_type: str, account_type: str` with `service_type_id: int`.
- `TierRequest` Pydantic model: replace `service_type: str` and `account_type: Optional[str]` fields with `service_type_id: int`.
- Update `create_tier` and `update_tier` handlers to use `service_type_id`.

**Gate**: T017 route tests pass (green).

```
backend/routes/commission_tiers.py  (modify)
```

---

### T040 — Update `backend/main.py` to register new routers [X]

**File**: `backend/main.py`

1. Import `companies` and `service_types` from `backend.routes`.
2. Add `app.include_router(companies.router)` and `app.include_router(service_types.router)`.
3. Remove `app.include_router(services.router)` (the `services` table no longer exists after migration; the endpoint is superseded by `/companies`).
4. The `assets/logos/` directory creation is handled in `lifespan` (T021).

```
backend/main.py  (modify)
```

---

### T041 — Update `services/api_client.py` with company/logo/service-type methods [X]

**File**: `services/api_client.py`

Add the following methods to `ApiClient`:

```python
# Companies
def get_companies(self) -> list[dict]: ...          # GET /companies/
def get_company(self, company_id: int) -> dict: ... # GET /companies/{id}
def create_company(self, name: str, category: str) -> dict: ...
def update_company(self, company_id: int, data: dict) -> dict: ...

# Logo
def get_logo(self, company_id: int) -> bytes: ...   # GET /companies/{id}/logo — returns raw bytes
def upload_logo(self, company_id: int, file_bytes: bytes, mime_type: str) -> dict: ...
    # POST /companies/{id}/logo — multipart/form-data

# ServiceTypes
def get_service_types(self, company_id: int) -> list[dict]: ...
    # GET /companies/{id}/service-types
def create_service_type(self, company_id: int, name: str, operation: str) -> dict: ...
def update_service_type(self, service_type_id: int, data: dict) -> dict: ...

# Accounts (updated)
def get_accounts(self, company_id: Optional[int] = None, service_type_id: Optional[int] = None) -> list[dict]: ...
    # GET /accounts/?company_id=<id>&service_type_id=<id>  (both filters supported; either may be omitted)
def get_accounts_by_company(self, company_id: int) -> list[dict]: ...
    # GET /accounts/?company_id=<id>
```

Add a `_post_multipart` private helper method for uploading binary files:
```python
def _post_multipart(self, path: str, file_bytes: bytes, mime_type: str, field: str = "file") -> Any:
    resp = requests.post(
        f"{BASE_URL}{path}",
        headers=self._headers(),
        files={field: ("logo", file_bytes, mime_type)},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()
```

Also add `_get_raw(path) -> bytes` that returns `resp.content` (not `resp.json()`) for the logo endpoint.

Remove `get_services()` method or mark it deprecated (the `/services` endpoint is removed in T040).

```
services/api_client.py  (modify)
```

---

## Core — Phase 5: PyQt6 Client Widgets and View Updates

### T042 — Create `views/widgets/company_logo_label.py` [P] [X]

**File**: `views/widgets/company_logo_label.py`

Create `CompanyLogoLabel(QLabel)` with:
- Module-level `_logo_cache: dict[int, QPixmap] = {}`.
- `_render_placeholder(company_name: str, size: int) -> QPixmap`: draws a colored circle with the first letter of `company_name`. Color is deterministic: `PALETTE[hash(company_name) % len(PALETTE)]` where `PALETTE` is a list of QColor values from the app's color scheme.
- `get_logo_pixmap(api_client, company_id: int, company_name: str, size: int) -> QPixmap`: module-level function. Checks `_logo_cache`; if missing, calls `api_client.get_logo(company_id)`, creates `QPixmap` via `loadFromData`, scales to `(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)`, stores in cache; on any exception, stores and returns `_render_placeholder`.
- `clear_logo_cache() -> None`: module-level function that clears `_logo_cache` (called on logout).
- `CompanyLogoLabel.__init__(self, api_client, company_id, company_name, size=32)`: calls `QLabel.__init__`, sets pixmap via `get_logo_pixmap`, sets `setFixedSize(size, size)`.

```
views/widgets/company_logo_label.py  (create)
```

---

### T043 — Create `views/widgets/company_selector.py` [P] [X]

**File**: `views/widgets/company_selector.py`

Create `CompanySelector(QComboBox)` with:
- `company_changed = pyqtSignal(int)` signal (emits selected `company_id`).
- `populate(companies: list[dict], api_client) -> None`: clears and repopulates the combobox. For each company dict, creates a `QIcon` from `get_logo_pixmap` (32×32) and calls `addItem(QIcon, company["name"], userData=company["id"])`.
- `selected_company_id() -> Optional[int]`: returns `self.currentData()`.
- Connects `currentIndexChanged` signal to emit `company_changed` with the new `company_id`.
- `ServiceTypeSelector(QComboBox)`: similarly structured combobox for service_types.
  - `populate(service_types: list[dict]) -> None`.
  - `selected_service_type_id() -> Optional[int]`.
- `AccountSelector(QComboBox)` (or reuse existing pattern).
  - `populate(accounts: list[dict]) -> None`.
  - `selected_account_id() -> Optional[int]`.

```
views/widgets/company_selector.py  (create)
```

---

### T044 — Update `views/transaction_view.py` — cascade selectors and dual company for Transfer/Exchange [X]

**File**: `views/transaction_view.py`

This is the highest-risk UI task. Implement carefully:

1. **Remove** `_map_tier_service_type` function at module top.
2. **Add imports**: `from views.widgets.company_logo_label import get_logo_pixmap, clear_logo_cache` and `from views.widgets.company_selector import CompanySelector, ServiceTypeSelector, AccountSelector`.
3. **For Deposit/Withdraw tabs**: replace the flat account `QComboBox` with a three-level cascade:
   - `CompanySelector` — a **logo-based button row** (not a combobox); populated from `api_client.get_companies()`, displaying each company's logo image (32×32 with letter fallback); selecting a logo emits `company_changed(company_id)`.
   - `ServiceTypeSelector` — a `QComboBox` populated from `api_client.get_service_types(company_id)` on `company_changed` signal; shows only service types belonging to the selected company.
   - `AccountSelector` — a `QComboBox` populated from `api_client.get_accounts(company_id=..., service_type_id=...)` on service type selection change.
4. **For Transfer tab**: add a second company/service_type/account cascade labelled with `t("customer_pays_in_via")` (from company) and `t("shop_pays_out_via")` (to company).
5. **For Exchange tab**: add a single company/service_type/account cascade (Exchange involves one account).
6. **Commission preview**: replace `_map_tier_service_type` call with direct `account.get("service_type_id")` read from selected account dict; pass `service_type_id` to `api_client.lookup_tier(service_type_id, amount)`.
7. **On logout**: call `clear_logo_cache()`.
8. Remove `self._services_cache` and replace `self._all_accounts_cache` population logic with company-level calls.

Add the following i18n keys to `i18n/` locale files (if they do not already exist): `customer_pays_in_via`, `shop_pays_out_via`.

**FEE_CASH_ITEM placement (resolved)**: The cash fee option is a **fixed entry placed above the company selector row**, before the cascade begins. It is not inside `AccountSelector`. In the form layout, render a dedicated `QRadioButton` or fixed `QComboBox` row labelled with the fee/cash i18n key at the top of the account selection group, so the user can choose "Cash" independently of any company/service type selection. The three-level cascade (Company Logo → ServiceType → Account) appears below this fixed row.

```
views/transaction_view.py  (modify)
```

---

## Core — Phase 6: Owner Settings Panel

### T045 — Create `views/settings/company_settings_view.py` [X]

**File**: `views/settings/company_settings_view.py`

Create `CompanySettingsView(QWidget)` with:
- A `QTableWidget` listing companies with columns: Logo (32×32), Name, Category, Status (Active/Inactive), Actions.
- "Add Company" button: opens a `QDialog` with name and category fields; calls `api_client.create_company`.
- "Edit" button per row: opens pre-populated `QDialog`; calls `api_client.update_company`.
- "Deactivate" button per row: calls `api_client.update_company(id, {"is_active": false})`; confirms with a `QMessageBox`.
- "Upload Logo" button per row: opens `QFileDialog` filtered to `"Images (*.png *.jpg *.svg)"`. Reads file bytes, validates size ≤ 200 KB (shows `QMessageBox.warning` if oversized). Calls `api_client.upload_logo`. On success, refreshes the logo in the table row by updating the `CompanyLogoLabel` widget. Clears the relevant entry in `_logo_cache` so the next transaction view load fetches the new logo.
- Auto-refresh via `QTimer` every 30 seconds.
- Owner-only visibility enforced: check `api_client.user["role"] == "owner"` before rendering action buttons; non-owner call raises or shows empty panel.

```
views/settings/company_settings_view.py  (create)
```

---

### T046 — Create `views/settings/service_type_settings_view.py` and wire settings tabs [X]

**File**: `views/settings/service_type_settings_view.py`, `views/dashboard_view.py`

**Part A** — Create `ServiceTypeSettingsView(QWidget)`:
- Accepts a `company_id` filter; shows `QTableWidget` of service_types for that company.
- "Add", "Edit", "Deactivate" buttons with `QDialog` forms.
- A `QComboBox` at the top to select the company (populated from `api_client.get_companies()`); changing company refreshes the table.

**Part B** — Update `views/dashboard_view.py`:
- Add "Companies" and "Service Types" tabs to the settings/admin panel section of the dashboard.
- Tab visibility: `"Companies"` and `"Service Types"` tabs are shown only when `api_client.user["role"] == "owner"`.
- Wire each tab to `CompanySettingsView` and `ServiceTypeSettingsView` respectively.

Also update `views/dashboard_view.py` account management table:
- Replace `service_id` column with `company_id` and `service_type_id` columns in the accounts table display.
- Replace `service_type TEXT` column with the company name (resolved from `company_id`).
- Update `_tier_service` QComboBox to be populated from `api_client.get_service_types(company_id)` rather than hardcoded strings.

```
views/settings/service_type_settings_view.py  (create)
views/dashboard_view.py  (modify)
```

---

## Polish — Phase 7: PyInstaller Packaging

### T047 — Update PyInstaller spec and Inno Setup script for `assets/logos/` [X]

**Files**: `NgweLweServer.spec`, `setup_server.iss`, `build_v1.0.1.bat`

**NgweLweServer.spec**:
- In the `Analysis` block's `datas` list, add: `('assets/logos', 'assets/logos')`.
- In the `COLLECT` block's positional args, add: `Tree('assets/logos', prefix='assets/logos')`.

**setup_server.iss**:
- In the `[Files]` section, add an entry to copy `{app}\assets\logos\*` during install, with `Flags: recursesubdirs createallsubdirs`.

**build_v1.0.1.bat**:
- Before the `pyinstaller` invocation, add: `if not exist assets\logos mkdir assets\logos`.

**Gate**: Build the server bundle, run from `dist/`, upload a logo via API, confirm the file is written to `assets/logos/` relative to the executable's working directory (AC-07).

```
NgweLweServer.spec  (modify)
setup_server.iss  (modify)
build_v1.0.1.bat  (modify)
```

---

## Dependency Graph

```
T001 (test infrastructure)
T002 (assets/logos dir)
T003 (views/widgets package)
T004 (views/settings package)
    ↓
T005–T018 (all TDD tests — written first, initially RED)
    ↓
T019 (_migrate_004) ← makes T005–T008 GREEN
    ↓
T020 (database.sql update)
T021 (main.py lifespan logos dir)
    ↓
T022 (models/company.py) [P with T023, T025, T026]
T023 (models/service_type.py)
T024 (models/account.py)
T025 (models/commission_tier.py)
T026 (models/transaction.py)
    ↓
T027 (company_repository) [P with T028]
T028 (service_type_repository)
T029 (account_repository update)
T030 (commission_tier_repository update)
T031 (service_repository deprecate)
    ↓  ← T009, T010, T011 become GREEN here
T032 (company_viewmodel) [P with T033]
T033 (service_type_viewmodel)
T034 (transaction_viewmodel update)
T035 (account_viewmodel update)
    ↓  ← T012 becomes GREEN here
T036 (routes/companies.py) [P with T037]
T037 (routes/service_types.py)
T038 (routes/accounts.py update)
T039 (routes/commission_tiers.py update)
T040 (main.py router registration) ← requires T036, T037, T038, T039
T041 (api_client.py update) ← requires T040
    ↓  ← T013–T017, T018 become GREEN here
T042 (company_logo_label widget) [P with T043]
T043 (company_selector widget)
    ↓  ← requires T041, T042, T043
T044 (transaction_view update)
    ↓
T045 (company_settings_view)
T046 (service_type_settings_view + dashboard wiring)
    ↓  ← AC-01 through AC-06 pass here
T047 (PyInstaller packaging)  ← can be PREPARED in parallel with T044–T046
```

---

## Parallel Execution Groups

The following tasks have no dependencies on each other within their group and can be worked simultaneously:

**Group A — Setup (day 1)**
```
T001 | T002 | T003 | T004
```

**Group B — TDD test authoring (can write all tests before any implementation)**
```
T005 | T006 | T007 | T008  (migration tests)
T009 | T010 | T011         (repository tests)
T012                       (viewmodel regression tests)
T013 | T014 | T015 | T016 | T017 | T018  (route + integration tests)
```

**Group C — Model creation (after T019)**
```
T022 | T023 | T025 | T026
```

**Group D — Repository creation (after Group C)**
```
T027 | T028
```

**Group E — Viewmodel creation (after Group D)**
```
T032 | T033
```

**Group F — Route creation (after Group E)**
```
T036 | T037
```

**Group G — Widget creation (after T041)**
```
T042 | T043
```

**Group H — Packaging prep (can be done anytime after T002)**
```
T047 spec/iss file edits only (defer `build` gate until T046 complete)
```

---

## Validation Checklist

Before marking tasks complete:

- [ ] All migration tests (T005–T008) pass GREEN after T019.
- [ ] All repository tests (T009–T011) pass GREEN after T027–T030.
- [ ] Regression commission tests (T012) pass GREEN after T034.
- [ ] All route tests (T013–T017) pass GREEN after T036–T040.
- [ ] Integration tests (T018) pass GREEN after T040.
- [ ] Every `accounts` row has a valid `service_type_id` FK after migration.
- [ ] Every `commission_tiers` row has a valid `service_type_id` FK after migration.
- [ ] `transactions` table has `from_company_id` and `to_company_id` columns after migration.
- [ ] Transfer/Exchange existing rows have `from_company_id` back-filled.
- [ ] No `service_type TEXT` or `account_type TEXT` columns remain in `accounts` or `commission_tiers`.
- [ ] `GET /companies/{id}/logo` returns correct bytes after upload (AC-05).
- [ ] Logo placeholder renders when API unreachable (AC-04).
- [ ] Dual company selectors appear for Transfer tab (AC-03).
- [ ] Non-owner users cannot see upload button (AC-06).
- [ ] PyInstaller bundle writes logos to `assets/logos/` inside `dist/` (AC-07).
- [ ] All `[NEEDS CLARIFICATION: ...]` markers resolved before implementation proceeds.

---

## Clarification Questions

The following clarifications are needed before implementation of the marked tasks begins:

**Q1** (in T024 — `models/account.py`):
After `_migrate_004` drops `service_type TEXT` and `service_id INTEGER` from the `accounts` table, the plan also references dropping `account_type TEXT`. However, `account_type` (values `'personal'` | `'agent'`) is currently used in `transaction_view.py` to display account labels and was used in commission tier lookups. Should `account_type` be **completely dropped** from the `accounts` table during the migration rebuild, or should it be **retained** as a column for UI display and auditing purposes? (If retained, `Account` model and `_row_to_model` should keep the field; if dropped, all UI references to `account_type` must be removed.)

**Q2** (in T041 and T044 — `api_client.py` and `transaction_view.py`):
The `dashboard_view.py` account management table currently calls `api_client.get_accounts()` without a company filter, then shows `service_id` and `service_type` columns. After migration, should there be a dedicated `GET /accounts/?company_id=<id>` query parameter on the accounts route (handled server-side via JOIN), or should the client fetch all accounts and filter client-side by `company_id` from the account's `company_id` field? Please specify the preferred filtering approach.

**Q3** (in T044 — `views/transaction_view.py`):
The current transaction form prepends a `FEE_CASH_ITEM` special entry to the accounts dropdown (representing a physical cash fee account). After the cascade `CompanySelector → ServiceTypeSelector → AccountSelector` refactor, where should this special cash fee option appear? Options: (a) as a special fixed entry before the `CompanySelector` row, (b) as the first item in the `AccountSelector` regardless of company selection, or (c) handled via a separate dedicated fee input field (not mixed into the account selector).
