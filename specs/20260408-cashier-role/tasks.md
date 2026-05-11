# Implementation Tasks: Cashier Role & Cash Management

- **Feature**: Cashier Role with Cash Vault, Denomination Tracking, and Float Assignment
- **Spec Folder**: `specs/20260408-cashier-role/`
- **Plan**: `specs/20260408-cashier-role/plan.md`
- **Date Generated**: 2026-04-08
- **Status**: In Progress — Core implementation DONE; Remaining work identified below
- **Stack**: PyQt6 (frontend) + FastAPI (backend) + SQLite (database)

---

## Implementation Reality Summary

The core cashier feature has been implemented. The table below shows the overall status by file layer before the task list begins.

| Layer | File | Status |
|---|---|---|
| Database SQL | `backend/database.sql` | DONE — cashier role, pin_hash, schema_version, all cash tables |
| Database Python | `backend/database.py` | DONE — migration runner with _migrate_001 + _migrate_002 |
| Model | `models/user.py` | DONE — cashier role acknowledged |
| Model | `models/cash_denomination_log.py` | DONE |
| Model | `models/cash_float.py` | DONE — CashFloat + CashFloatDenomination |
| Repository | `repositories/cash_denomination_repository.py` | DONE |
| Repository | `repositories/cash_float_repository.py` | DONE |
| Repository | `repositories/user_repository.py` | DONE — get_pin_hash, get_employees added |
| Auth | `backend/auth.py` | DONE — require_roles() added |
| Routes | `backend/routes/cashier.py` | DONE — 9 endpoints |
| Routes | `backend/routes/transactions.py` | DONE — cashier block + float enforcement |
| Routes | `backend/routes/users.py` | DONE — cashier role creation + PIN endpoint |
| Routes | `backend/main.py` | DONE — cashier router registered |
| ViewModel | `viewmodels/auth_viewmodel.py` | DONE — is_cashier property |
| ViewModel | `viewmodels/cashier_viewmodel.py` | DONE |
| Service | `services/api_client.py` | DONE — all cashier methods added |
| View | `views/cashier_view.py` | DONE — 1065 lines, all panels present |
| View | `views/receive_float_dialog.py` | DONE — PIN confirmation dialog |
| View | `views/login_view.py` | DONE — cashier routing + pending float check |
| View | `views/dashboard_view.py` | PARTIAL — sidebar still uses static MENU_ITEMS, not role-conditional |
| View | `views/employee_float_view.py` | NOT DONE — file does not exist |
| Utility | `utils/denomination_utils.py` | NOT DONE — file does not exist |
| Widget | `views/widgets/denomination_entry_widget.py` | NOT DONE — not extracted; inline in views |
| Migration | `migrations/002_cashier_role.sql` | NOT DONE — migration handled in Python only, no standalone SQL file |
| Tests | `tests/` | NOT DONE — no test directory exists |

**Key schema divergence from plan:** The implemented schema differs from the plan in meaningful ways:
- No standalone `cash_denominations` snapshot table; the vault balance is computed live from `cash_denomination_logs` via aggregation (a cleaner design).
- `cash_float_assignments.status` uses `PENDING / ACTIVE / CLOSED` (not `open / closed / partial_return`).
- `cash_denomination_logs.entry_type` uses `vault_in / vault_out / float_returned / adjustment` (not the plan's event_type vocabulary).
- `cash_denomination_logs` has a `float_id` FK to `cash_float_assignments` (no `reference_type` column).
- Denominations supported: 50, 100, 200, 500, 1000, 5000, 10000, 20000 (coins included — Q1 resolved).
- `PATCH /users/{id}/role` endpoint was not implemented (only PIN and create-with-role exist).

---

## Task Categories

1. [Setup](#1-setup)
2. [Tests (TDD / Regression)](#2-tests-tdd--regression)
3. [Core — Remaining Implementation](#3-core--remaining-implementation)
4. [Integration — Wiring & Polish](#4-integration--wiring--polish)
5. [Documentation & Release](#5-documentation--release)

---

## 1. Setup

### T001 — DONE: Database schema updated with cashier role and cash tables
- **File**: `backend/database.sql`
- **Status**: DONE
- **Details**: `schema_version` table, `pin_hash` column on `users`, CHECK constraint extended to include `cashier`, tables `cash_float_assignments` (9), `cash_denomination_logs` (10), `cash_float_denominations` (11) all present. Seed data inserts schema versions 1 and 2.

### T002 — DONE: Migration runner added to database.py
- **File**: `backend/database.py`
- **Status**: DONE
- **Details**: `_migrate_001` (users table + pin_hash), `_migrate_002` (cash tables), `_run_migrations` dispatcher — all present and called on startup.

### T003 — Create `migrations/002_cashier_role.sql` standalone file [P]
- **File**: `migrations/002_cashier_role.sql`
- **Status**: NOT DONE
- **Why**: The plan specifies a standalone SQL migration file for DBA review and manual execution on production. The Python migration runner exists but the SQL file does not. This is needed for auditability and disaster recovery.
- **Action**: Create the `migrations/` directory. Write the idempotent SQL migration that mirrors what `_migrate_001` and `_migrate_002` do in Python. Use `IF NOT EXISTS` / `INSERT OR IGNORE` patterns throughout. Include the schema_version seed rows.
- **Acceptance**: Running the file against a pre-migration SQLite DB produces the same schema as the Python runner.

### T004 — Create `tests/` directory with conftest and fixtures [P]
- **File**: `tests/conftest.py`, `tests/__init__.py`
- **Status**: NOT DONE
- **Why**: No test infrastructure exists at all. All integration and unit tests depend on this.
- **Action**: Create `tests/` and `tests/__init__.py`. Create `tests/conftest.py` with:
  - An in-memory SQLite DB fixture that calls `init_db()` and `_run_migrations()`.
  - A FastAPI `TestClient` fixture wrapping `backend/main.py:app`.
  - JWT token factory fixtures for `owner`, `cashier`, and `employee` roles.
- **Dependencies**: None — can be done in parallel with T003.
- **Acceptance**: `pytest tests/` collects without errors.

---

## 2. Tests (TDD / Regression)

All test tasks depend on T004. Tasks T005–T012 are marked [P] because they target different files and have no inter-task dependencies once T004 exists.

### T005 — Write unit tests for migration runner [P]
- **File**: `tests/test_migrations.py`
- **Status**: NOT DONE
- **Depends on**: T004
- **Action**: Test that `_run_migrations()` applied against a blank DB creates all expected tables. Test idempotency — running migrations twice does not raise. Test that `schema_version` rows are inserted correctly.
- **Acceptance**: All assertions pass; no SQLite errors on re-run.

### T006 — Write integration tests: role enforcement on cashier routes [P]
- **File**: `tests/test_cashier_routes.py`
- **Status**: NOT DONE
- **Depends on**: T004
- **Scenarios to cover** (per plan Section 10):
  - `GET /cashier/vault` as `employee` → 403 Forbidden
  - `POST /cashier/vault/cash_in-entry` as `employee` → 403
  - `POST /cashier/floats` (issue float) as `employee` → 403
  - `GET /cashier/floats/pending` as `cashier` with no pending float → 404 or empty
  - `POST /cashier/floats` with insufficient vault quantity → 409 Conflict
  - `POST /cashier/floats` to employee who already has an ACTIVE float → 409 Conflict
  - `POST /cashier/floats/{id}/receive` with wrong PIN → 403
  - `POST /cashier/floats/{id}/close` with closing_total > total_amount → 422
  - `GET /cashier/vault/logs` as `cashier` → 200 with list
- **Acceptance**: All scenarios return the expected HTTP status codes.

### T007 — Write integration tests: transaction route cashier/float enforcement [P]
- **File**: `tests/test_transaction_enforcement.py`
- **Status**: NOT DONE
- **Depends on**: T004
- **Scenarios to cover** (per `backend/routes/transactions.py` lines inspected):
  - `POST /transactions/cash_in` as `cashier` → 403 (cashiers cannot record transactions)
  - `POST /transactions/cash_out` as `employee` with no active float → 403 "No active float"
  - `POST /transactions/cash_out` as `employee` with active float → 201
  - `POST /transactions/transfer` as `cashier` → 403
- **Acceptance**: All enforcement rules fire correctly.

### T008 — Write integration tests: user creation with cashier role [P]
- **File**: `tests/test_user_routes.py`
- **Status**: NOT DONE
- **Depends on**: T004
- **Scenarios to cover**:
  - `POST /users/` with `role: "cashier"` as `owner` → 201
  - `POST /users/` with `role: "cashier"` as `employee` → 403
  - `POST /users/` with `role: "owner"` as `owner` → 422 (owner cannot create another owner)
  - `POST /users/{id}/pin` with 6-digit PIN as owner → 200
  - `POST /users/{id}/pin` with 5-digit PIN → 422
  - `POST /users/{id}/pin` with non-numeric PIN → 422
- **Acceptance**: Role creation and PIN constraints are enforced.

### T009 — Write unit tests for CashDenominationRepository [P]
- **File**: `tests/test_cash_denomination_repository.py`
- **Status**: NOT DONE
- **Depends on**: T004
- **Action**: Use the in-memory DB fixture. Test:
  - `get_vault_balance()` returns all-zero dict on empty DB.
  - `record_bulk_entry('vault_in', {10000: 5, 1000: 3}, created_by=1)` persists correctly.
  - `get_vault_balance()` after vault_in reflects correct net quantities.
  - `get_pending_reserved()` correctly sums PENDING float denominations.
  - `get_available_balance()` = vault_balance - pending_reserved.
  - `record_bulk_entry` with all-zero quantities inserts nothing.
- **Acceptance**: All assertions pass against in-memory DB.

### T010 — Write unit tests for CashFloatRepository [P]
- **File**: `tests/test_cash_float_repository.py`
- **Status**: NOT DONE
- **Depends on**: T004
- **Action**: Use in-memory DB fixture. Test:
  - `create_float(employee_id, cashier_id, denominations, note)` creates PENDING record.
  - `get_pending_float_for_employee(employee_id)` returns the created float.
  - `activate_float(float_id, employee_id, pin_hash)` transitions to ACTIVE.
  - `get_active_float_for_employee(employee_id)` returns activated float.
  - `close_float(float_id, closing_denominations, closing_total)` transitions to CLOSED.
  - `list_floats()` returns all floats.
  - `get_float_denominations(float_id)` returns denomination rows.
- **Acceptance**: All state transitions and queries verified.

### T011 — Write unit tests for `utils/denomination_utils.py` [P]
- **File**: `tests/test_denomination_utils.py`
- **Status**: NOT DONE — utility file also does not exist (see T013)
- **Depends on**: T013 (denomination_utils must exist first)
- **Action**: Test:
  - `calculate_total([{"denomination": 10000, "quantity": 5}])` → 50000.0
  - `calculate_total([])` → 0.0
  - `suggest_denominations(50000)` → `[{denomination: 10000, quantity: 5}]`
  - `suggest_denominations(15500)` → `[{denomination: 10000, quantity: 1}, {denomination: 5000, quantity: 1}, {denomination: 500, quantity: 1}]`
  - `suggest_denominations(0)` → `[]`
  - `suggest_denominations(75)` → `[{denomination: 50, quantity: 1}]` (coins)
- **Acceptance**: All edge cases pass.

### T012 — Write manual QA checklist execution log [P]
- **File**: `specs/20260408-cashier-role/qa-checklist.md`
- **Status**: NOT DONE
- **Depends on**: T016, T017, T018 (UI tasks) and T003
- **Action**: Execute the manual QA checklist from plan Section 10 against a running application. Record pass/fail for each item. Flag any defects as GitHub issues or inline notes.
- **Checklist items**:
  - [ ] Create a `cashier` user via owner panel
  - [ ] Log in as cashier — verify sidebar shows only cashier-appropriate menu items
  - [ ] Record denomination entry (vault_in) as cashier
  - [ ] Issue a float to an employee; verify vault balance decrements
  - [ ] Log in as employee — verify pending float dialog appears on login
  - [ ] Employee receives float with correct 6-digit PIN
  - [ ] Employee records a cash_out — verify blocked without active float is fixed
  - [ ] Cashier closes float; verify vault increments on return
  - [ ] Owner views denomination logs — all event rows present
  - [ ] Owner can see all float assignments
  - [ ] Cashier cannot access `POST /transactions/cash_in` or `/cash_out`
- **Acceptance**: All checklist items pass; any failures documented.

---

## 3. Core — Remaining Implementation

### T013 — Create `utils/denomination_utils.py` [P]
- **File**: `utils/denomination_utils.py`
- **Status**: NOT DONE
- **Why**: The plan specifies this utility (Section 5.3). Currently denomination totals are computed inline in views. Centralizing this enables unit testing and reuse across dialogs.
- **Action**: Create `utils/` directory. Create `utils/__init__.py`. Create `utils/denomination_utils.py`:

```python
# utils/denomination_utils.py

STANDARD_DENOMINATIONS = [20000, 10000, 5000, 1000, 500, 200, 100, 50]  # descending, matches DB CHECK

def calculate_total(entries: list[dict]) -> float:
    """Sum of denomination * quantity for each entry."""
    return sum(e["denomination"] * e["quantity"] for e in entries)

def suggest_denominations(amount: float) -> list[dict]:
    """Greedy breakdown of an amount into standard denominations."""
    remaining = int(amount)
    result = []
    for d in STANDARD_DENOMINATIONS:
        if remaining >= d:
            qty = remaining // d
            result.append({"denomination": d, "quantity": qty})
            remaining -= qty * d
    return result
```
- **Acceptance**: File importable; T011 unit tests pass.

### T014 — Add `PATCH /users/{user_id}/role` endpoint [P]
- **File**: `backend/routes/users.py`
- **Status**: NOT DONE
- **Why**: The plan (Section 4.2) specifies an endpoint for changing an existing user's role. Currently only role assignment at creation time is supported. An owner may need to promote an employee to cashier or demote a cashier.
- **Action**: Add to `backend/routes/users.py`:

```python
class ChangeRoleRequest(BaseModel):
    role: Literal["employee", "cashier"]

@router.patch("/{user_id}/role")
def change_role(
    user_id: int,
    body: ChangeRoleRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(403, "Owner only")
    if current_user["user_id"] == user_id:
        raise HTTPException(400, "Cannot change your own role")
    _user_repo.update(user_id, {"role": body.role})
    return {"user_id": user_id, "role": body.role}
```
- **Acceptance**: `PATCH /users/3/role` with `{"role": "cashier"}` as owner → 200; as non-owner → 403.

### T015 — Add `change_role` to `services/api_client.py` [P]
- **File**: `services/api_client.py`
- **Status**: NOT DONE
- **Depends on**: T014 (endpoint must exist)
- **Action**: Add after `toggle_user_active`:

```python
def change_user_role(self, user_id: int, role: str) -> dict:
    return self._patch(f"/users/{user_id}/role", {"role": role})
```
- **Acceptance**: Method callable; returns dict from API.

---

## 4. Integration — Wiring & Polish

### T016 — Implement role-conditional sidebar in `views/dashboard_view.py`
- **File**: `views/dashboard_view.py`
- **Status**: PARTIAL — sidebar uses static `MENU_ITEMS` with no role logic
- **Why**: The plan (Section 6.1) requires role-conditional menu items. Currently all roles see the same 6 menu items regardless of their role.
- **Action**: Replace the static `MENU_ITEMS` list and `_build_sidebar()` loop with role-aware logic. The `DashboardView` already receives the logged-in user context; use `user.role` to filter items.

  Implement as a function:
  ```python
  def _get_menu_items_for_role(role: str) -> list[tuple[str, str, int]]:
      owner_items = [
          ("Dashboard", "dashboard", 0),
          ("Transactions", "transactions", 1),
          ("Accounts", "accounts", 2),
          ("Reports", "reports", 3),
          ("Employees", "employees", 4),
          ("Settings", "settings", 5),
      ]
      cashier_items = [
          ("Dashboard", "dashboard", 0),
          ("Cash Vault", "cashier", 6),
          ("Settings", "settings", 5),
      ]
      employee_items = [
          ("Dashboard", "dashboard", 0),
          ("Transactions", "transactions", 1),
          ("Settings", "settings", 5),
      ]
      return {"owner": owner_items, "cashier": cashier_items, "employee": employee_items}.get(role, employee_items)
  ```
  Register a `QStackedWidget` page index 6 pointing to `CashierView`.
- **Acceptance**: Logging in as cashier shows Cash Vault and Settings only (no Transactions, Accounts, Reports, Employees). Logging in as owner shows all original items.

### T017 — Create `views/employee_float_view.py`
- **File**: `views/employee_float_view.py`
- **Status**: NOT DONE
- **Why**: The plan (Section 6.3) specifies a lightweight view for employees showing their active float status. This was not created during implementation; employees currently have no float-status panel.
- **Action**: Create `views/employee_float_view.py` with a `EmployeeFloatView(QWidget)` class:
  - Calls `api_client.get_my_pending_float()` on load.
  - If a PENDING float exists, shows float details (total amount, denominations issued, cashier name) and a "Receive Float" button that opens `ReceiveFloatDialog`.
  - If an ACTIVE float exists, shows: total assigned, a status label, and an info message "Return unused cash to your cashier at shift end."
  - If no float, shows: "No float assigned. Contact your cashier."
  - Includes a refresh button.
- **Acceptance**: Employee sees correct float state after being issued a float. Status updates after receiving.

### T018 — Wire `EmployeeFloatView` into `DashboardView` sidebar for employee role
- **File**: `views/dashboard_view.py`
- **Status**: NOT DONE
- **Depends on**: T016, T017
- **Action**: Register `EmployeeFloatView` as `QStackedWidget` page index 7 (or next available). Add "My Float" to the `employee_items` list in the role-conditional sidebar (from T016). Wire the sidebar button click to show page 7.
- **Acceptance**: Employee sidebar includes "My Float" menu item. Clicking it shows `EmployeeFloatView`.

### T019 — Add role-change UI to owner's Employees panel [P]
- **File**: `views/dashboard_view.py` (Employees panel section)
- **Status**: NOT DONE
- **Depends on**: T014, T015
- **Why**: Owner can now call `PATCH /users/{id}/role` but there is no UI for it.
- **Action**: In the Employees panel context menu or button row, add a "Change Role" button. On click, open a `QInputDialog` or small dialog asking for the new role. Call `api_client.change_user_role(user_id, role)`. Refresh the employees table.
- **Acceptance**: Owner can change an employee to cashier and back from the UI.

### T020 — Extract `DenominationEntryWidget` to `views/widgets/denomination_entry_widget.py` [P]
- **File**: `views/widgets/denomination_entry_widget.py`
- **Status**: NOT DONE (inline implementation exists within dialogs)
- **Why**: The plan (Section 6.5) specifies a reusable `QWidget` subclass. Currently denomination grids are implemented inline in each dialog inside `cashier_view.py`. Extracting the widget enables reuse in `EmployeeFloatView` and reduces duplication.
- **Action**: Create `views/widgets/` directory and `views/widgets/__init__.py`. Extract the denomination spinbox grid into `DenominationEntryWidget(QWidget)` with:
  - `total_changed = pyqtSignal(float)`
  - `__init__(self, denominations: list[int], parent=None)`
  - `get_entries(self) -> list[dict]`
  - `set_entries(self, entries: list[dict]) -> None`
  - `get_total(self) -> float`
  Update `cashier_view.py` dialogs to import and use this widget.
- **Acceptance**: Widget emits `total_changed` on every spinbox change; all existing dialogs function identically.

### T021 — Verify vault sufficiency check in IssueFloatPage
- **File**: `views/cashier_view.py` — `IssueFloatPage`
- **Status**: NEEDS VERIFICATION
- **Why**: The plan (Q5) asks whether the Issue Float screen should warn or block if requested denomination quantities exceed vault available balance. The `CashierViewModel.get_available_balance()` method exists and the repository correctly computes available = vault − pending. Verify that `IssueFloatPage` calls this and shows a warning.
- **Action**: Read `IssueFloatPage` in `cashier_view.py` (line 579+). If no vault check is present, add:
  - On "Issue Float" button click, call `get_available_balance()`.
  - For each denomination in the form, if requested quantity > available, show a `QMessageBox.warning` listing the shortfall.
  - Optionally make it a hard block (disable Issue button).
- **Acceptance**: Attempting to issue 10 × 10,000 MMK when vault has 3 × 10,000 triggers a visible warning.

### T022 — Verify cashier transactions read-only page completeness
- **File**: `views/cashier_view.py` — `TransactionsReadOnlyPage` (line 843)
- **Status**: NEEDS VERIFICATION
- **Why**: The `CashierView` includes a `TransactionsReadOnlyPage` which is a pragmatic resolution of Q4 (cashier should see transaction history to record denominations). Verify this page loads correctly, respects auth, and links appropriately from the vault panel.
- **Action**: Manually test the Transactions tab in the cashier view. Confirm it shows cash_ins without exposing create/cash_out buttons. Add a note in `qa-checklist.md` (T012) for this scenario.
- **Acceptance**: Cashier can see cash_in transactions in read-only mode; no action buttons available.

---

## 5. Documentation & Release

### T023 — Update `README.md` with cashier role documentation [P]
- **File**: `README.md`
- **Status**: NOT DONE (file exists but cashier content not present)
- **Depends on**: T012 (QA complete)
- **Action**: Add a "Roles" section to `README.md` documenting:
  - The three roles: owner, employee, cashier — and their capabilities.
  - How to create a cashier user (owner panel → Employees → Create User → Role: Cashier).
  - How to set a cashier PIN (`POST /users/{id}/pin` or via owner UI once T019 implemented).
  - The float lifecycle: Issue → Receive (with PIN) → CashOuts → Close.
  - The denominations supported: 50, 100, 200, 500, 1000, 5000, 10000, 20000 MMK.
- **Acceptance**: README is accurate, readable, and covers the cashier workflow end-to-end.

### T024 — Final regression test: existing owner/employee flows [P]
- **File**: `tests/test_regression.py`
- **Status**: NOT DONE
- **Depends on**: T004
- **Why**: The plan (Phase 6) requires a final regression pass to confirm nothing was broken by cashier-role changes.
- **Action**: Write regression tests covering:
  - Owner login, create user, toggle active.
  - Employee records cash_in, cash_out, transfer, exchange — all succeed with active float.
  - Reports endpoint returns 200 for owner.
  - Auth: expired/invalid token returns 401.
  - Password change works for all roles.
- **Acceptance**: All existing flows pass with no regressions.

### T025 — Resolve open plan clarification questions and update plan status
- **File**: `specs/20260408-cashier-role/plan.md`
- **Status**: NOT DONE
- **Why**: The plan still shows Status: "Draft — Awaiting Clarification" and 11 `[NEEDS CLARIFICATION]` items. These must be resolved now that implementation choices are visible.
- **Action**: For each question, document the decision actually implemented:
  - Q1: Denominations 50, 100, 200, 500, 1000, 5000, 10000, 20000 (coins included — completed in DB CHECK constraint).
  - Q2: CashIn entry is freestanding (not 1:1 to transaction_id) — `cash_denomination_logs` uses `entry_type='vault_in'`, no reference_id FK.
  - Q3: No auto-suggest implemented (manual entry used; `utils/denomination_utils.py` will add suggest capability for future use).
  - Q4: Cashier sees read-only transaction list via `TransactionsReadOnlyPage` in `CashierView`.
  - Q5: Vault sufficiency check — see T021 (to be verified/implemented).
  - Q6: Float balance is not auto-decremented per cash_out; it is informational/reconciliation-only.
  - Q7: No strict denomination sum validation against transaction amount — freestanding entry.
  - Q8: One open float per employee enforced — `get_active_float_for_employee` checked before issue.
  - Q9: `schema_version` table introduced; Python migration runner handles versioning.
  - Q10: Cashiers are blocked from all transaction writes (403 for cash_in/cash_out/transfer/exchange as cashier).
  - Q11: Float enforcement is a hard block — `POST /transactions/cash_out` as employee with no active float → 403.
  Update plan Status from "Draft — Awaiting Clarification" to "Implemented — Pending QA".
- **Acceptance**: All clarification markers in plan.md are resolved with documented decisions.

---

## Dependency Graph

```
T003 (SQL migration file)     — independent
T004 (test infrastructure)    — independent; blocks T005-T012, T024

T004 --> T005  (migration tests)
T004 --> T006  (cashier route tests)
T004 --> T007  (transaction enforcement tests)
T004 --> T008  (user route tests)
T004 --> T009  (denomination repo tests)
T004 --> T010  (float repo tests)
T013 --> T011  (denomination utils tests)
T004 --> T011

T013 (denomination_utils)     — independent [P]
T014 (PATCH /role endpoint)   — independent [P]
T014 --> T015 (api_client.change_user_role)

T016 (role-conditional sidebar) — independent
T017 (EmployeeFloatView)        — independent [P]
T016 + T017 --> T018 (wire EmployeeFloatView into sidebar)
T014 + T015 --> T019 (role-change UI)

T020 (DenominationEntryWidget extraction) — independent [P]
T021 (vault sufficiency check)            — independent [P]
T022 (cashier txn page verify)            — independent [P]

T016 + T017 + T018 --> T012 (QA checklist)
T012 --> T023 (README)
T004 --> T024 (regression tests)
T012 + T024 --> T025 (resolve clarifications + update plan)
```

---

## Parallel Execution Groups

Tasks within each group can be run simultaneously:

**Group A — Foundation (start here):**
- T003 (SQL migration file)
- T004 (test infrastructure)
- T013 (denomination_utils)
- T014 (PATCH /role endpoint)

**Group B — After T004:**
- T005, T006, T007, T008, T009, T010 (all test files)

**Group C — After T013 + T004:**
- T011 (denomination utils tests)

**Group D — UI work (parallel to Group B):**
- T016 (role-conditional sidebar)
- T017 (EmployeeFloatView)
- T020 (DenominationEntryWidget extraction)
- T021 (vault sufficiency verify)
- T022 (cashier txn page verify)

**Group E — After T014:**
- T015 (api_client change_role)
- T019 (role-change UI)

**Group F — After T016 + T017:**
- T018 (wire EmployeeFloatView)

**Group G — After QA (T012):**
- T023 (README)
- T024 (regression tests)
- T025 (resolve clarifications)

---

## Validation Checklist

Before marking this feature complete, verify:

- [ ] T003: `migrations/002_cashier_role.sql` file exists and is idempotent
- [ ] T004: `pytest tests/` runs without collection errors
- [ ] T005: Migration idempotency tests pass
- [ ] T006: All 9 cashier route scenarios pass
- [ ] T007: All 4 transaction enforcement scenarios pass
- [ ] T008: Role creation and PIN constraint tests pass
- [ ] T009: CashDenominationRepository unit tests pass
- [ ] T010: CashFloatRepository state machine tests pass
- [ ] T011: DenominationUtils edge case tests pass
- [ ] T012: Manual QA checklist 100% green
- [ ] T013: `utils/denomination_utils.py` importable
- [ ] T014: `PATCH /users/{id}/role` returns 200 for owner, 403 for others
- [ ] T015: `api_client.change_user_role()` method present
- [ ] T016: Role-conditional sidebar shows correct items per role
- [ ] T017: `EmployeeFloatView` shows correct state (pending/active/none)
- [ ] T018: Employee sees "My Float" in sidebar
- [ ] T019: Owner can change user role from UI
- [ ] T020: `DenominationEntryWidget` extracted and reused in cashier dialogs
- [ ] T021: Vault sufficiency warning triggers on over-issue attempt
- [ ] T022: Cashier transactions page is read-only (no create buttons)
- [ ] T023: README covers cashier role documentation
- [ ] T024: All existing owner/employee flows pass regression
- [ ] T025: All plan clarification markers resolved; plan status updated

---

## Task Count Summary

| Category | Total | Done | Remaining |
|---|---|---|---|
| Setup | 4 | 2 | 2 (T003, T004) |
| Tests | 8 | 0 | 8 (T005-T012) |
| Core Remaining | 3 | 0 | 3 (T013-T015) |
| Integration / Polish | 7 | 0 | 7 (T016-T022) |
| Documentation & Release | 3 | 0 | 3 (T023-T025) |
| **Total** | **25** | **2** | **23** |

Parallel tasks available (marked [P]): T003, T004, T005, T006, T007, T008, T009, T010, T011, T013, T014, T015, T017, T019, T020, T021, T022, T023, T024
