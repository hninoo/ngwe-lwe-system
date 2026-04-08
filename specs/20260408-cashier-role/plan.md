# Implementation Plan: Cashier Role & Cash Management

- **Feature**: Cashier Role with Cash Vault, Denomination Tracking, and Float Assignment
- **Spec Folder**: `specs/20260408-cashier-role/`
- **Date**: 2026-04-08
- **Status**: Draft — Awaiting Clarification
- **Stack**: PyQt6 (frontend) + FastAPI (backend) + SQLite (database)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Current State Analysis](#2-current-state-analysis)
3. [Database Schema Changes](#3-database-schema-changes)
4. [Backend Changes](#4-backend-changes)
5. [ViewModel Changes](#5-viewmodel-changes)
6. [UI Changes](#6-ui-changes)
7. [Workflow Walkthrough](#7-workflow-walkthrough)
8. [Migration Strategy](#8-migration-strategy)
9. [Permission Matrix](#9-permission-matrix)
10. [Testing Strategy](#10-testing-strategy)
11. [Implementation Phases](#11-implementation-phases)
12. [Assumptions & Risks](#12-assumptions--risks)
13. [Areas Requiring Clarification](#13-areas-requiring-clarification)

---

## 1. Overview

This feature introduces a third user role — `cashier` — that sits between the owner and employees in the cash-handling chain. The cashier acts as a physical vault: they receive and record deposited cash in denominations (like a bank teller), and they issue cash floats to employees at the start of each shift. Employees use their float to pay out withdrawals to customers. The cashier maintains a running denomination-level inventory of physical cash, and the owner can audit it at any time.

### Core Concepts

| Concept | Description |
|---|---|
| **Cash Vault** | The cashier's master physical cash inventory, stored as denomination rows |
| **Denomination Entry** | When a deposit is completed, the cashier records which physical notes were received (e.g., 10,000 × 5, 5,000 × 8) |
| **Cash Float** | A bundle of physical cash given by the cashier to an employee when their shift opens |
| **Float Assignment** | A record linking a float amount (with denomination breakdown) to an employee for a specific shift/session |
| **Float Return** | At shift close, the employee returns unused cash; the cashier reconciles the vault |

---

## 2. Current State Analysis

### Existing Role System

```sql
-- users table, current CHECK constraint
role TEXT NOT NULL DEFAULT 'employee' CHECK(role IN ('owner','employee'))
```

- `owner`: full system access, sees all reports, manages users
- `employee`: records transactions (deposit/withdraw/transfer/exchange), no cash custody

### Affected Files (existing)

| Layer | File | Change Required |
|---|---|---|
| Database | `backend/database.sql` | Add new tables; alter `users.role` CHECK |
| Model | `models/user.py` | Add `'cashier'` to role comment/type hint |
| Repository | `repositories/user_repository.py` | Add cashier-specific query helpers |
| Auth | `backend/auth.py` | No changes needed (role is token-passthrough) |
| Routes | `backend/routes/users.py` | Allow creating `cashier` role users |
| Routes | `backend/main.py` | Register new cashier router |
| ViewModel | `viewmodels/auth_viewmodel.py` | Add `is_cashier` property |
| Views | `views/dashboard_view.py` | Role-conditional sidebar menu items |

---

## 3. Database Schema Changes

### 3.1 Alter `users.role` CHECK Constraint

SQLite does not support `ALTER TABLE ... ALTER COLUMN`. The constraint must be recreated via a schema migration script. The new valid roles are: `'owner'`, `'employee'`, `'cashier'`.

```sql
-- Migration: recreate users table with updated CHECK constraint
-- Run once; existing rows are preserved via INSERT INTO ... SELECT

PRAGMA foreign_keys = OFF;

CREATE TABLE users_new (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'employee'
                  CHECK(role IN ('owner','employee','cashier')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO users_new SELECT * FROM users;
DROP TABLE users;
ALTER TABLE users_new RENAME TO users;

-- Recreate trigger
CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
AFTER UPDATE ON users FOR EACH ROW
BEGIN UPDATE users SET updated_at = datetime('now') WHERE id = NEW.id; END;

PRAGMA foreign_keys = ON;
```

This migration must run before any new tables reference `users.id` with cashier rows.

---

### 3.2 New Table: `cash_denominations`

Tracks the cashier's current physical vault inventory at denomination level.

```sql
-- ============================================================
-- 9. cash_denominations
-- The cashier's running vault inventory.
-- Each row = one denomination unit held right now.
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_denominations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    denomination    INTEGER NOT NULL,          -- e.g. 10000, 5000, 1000, 500, 100
    quantity        INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
    updated_by      INTEGER NOT NULL,          -- cashier user_id
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (updated_by) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cash_denom_value ON cash_denominations(denomination);
```

**Design notes:**
- One row per denomination. `quantity` is the current count held in the vault.
- A separate audit/history table (`cash_denomination_logs`) records every change for accountability.
- [NEEDS CLARIFICATION: Q1 — What denominations are used in practice? Standard Myanmar kyat notes are 100, 200, 500, 1000, 5000, 10000. Should 50 and 20 kyat coins also be supported, or only paper notes?]

---

### 3.3 New Table: `cash_denomination_logs`

Immutable audit trail of every change to vault denominations.

```sql
-- ============================================================
-- 10. cash_denomination_logs
-- Append-only audit trail for vault denomination changes.
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_denomination_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL
                    CHECK(event_type IN (
                        'deposit_received',   -- cashier records notes from a deposit
                        'float_issued',       -- notes removed from vault, given to employee
                        'float_returned',     -- notes returned by employee at shift close
                        'manual_adjustment'   -- owner/cashier manual correction
                    )),
    denomination    INTEGER NOT NULL,
    quantity_delta  INTEGER NOT NULL,          -- positive = added to vault, negative = removed
    quantity_after  INTEGER NOT NULL,          -- snapshot of quantity after this event
    reference_id    INTEGER,                   -- FK to deposit transaction_id or cash_float_assignments.id
    reference_type  TEXT,                      -- 'transaction' | 'float_assignment' | 'manual'
    performed_by    INTEGER NOT NULL,
    note            TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (performed_by) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_denom_log_event   ON cash_denomination_logs(event_type);
CREATE INDEX IF NOT EXISTS idx_denom_log_created ON cash_denomination_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_denom_log_ref     ON cash_denomination_logs(reference_id, reference_type);
```

---

### 3.4 New Table: `cash_float_assignments`

Records each float issued from the cashier to an employee for a shift.

```sql
-- ============================================================
-- 11. cash_float_assignments
-- Tracks each cash float given to an employee for a shift.
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_float_assignments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id     INTEGER NOT NULL,
    cashier_id      INTEGER NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK(status IN ('open','closed','partial_return')),
    total_float     REAL NOT NULL,             -- sum of all denominations × quantity issued
    total_returned  REAL NOT NULL DEFAULT 0.00,
    opened_at       TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at       TEXT,
    note            TEXT,
    FOREIGN KEY (employee_id) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (cashier_id)  REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_float_employee ON cash_float_assignments(employee_id, status);
CREATE INDEX IF NOT EXISTS idx_float_cashier  ON cash_float_assignments(cashier_id);
CREATE INDEX IF NOT EXISTS idx_float_opened   ON cash_float_assignments(opened_at);
```

---

### 3.5 New Table: `cash_float_denominations`

The denomination breakdown for each float assignment (both issued and returned portions).

```sql
-- ============================================================
-- 12. cash_float_denominations
-- Denomination detail for each float assignment.
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_float_denominations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    float_assignment_id INTEGER NOT NULL,
    direction           TEXT NOT NULL CHECK(direction IN ('issued','returned')),
    denomination        INTEGER NOT NULL,
    quantity            INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
    FOREIGN KEY (float_assignment_id)
        REFERENCES cash_float_assignments(id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_float_denom_assign
    ON cash_float_denominations(float_assignment_id, direction);
```

---

### 3.6 Schema Summary (new tables only)

```
cash_denominations          — current vault snapshot (one row per denomination)
cash_denomination_logs      — append-only change audit
cash_float_assignments      — one record per employee shift float
cash_float_denominations    — denomination rows for each float (issued / returned)
```

All new tables are added to `backend/database.sql` so `init_db()` creates them on fresh installs. Existing installs use the migration script (`migrations/002_cashier_role.sql`).

---

## 4. Backend Changes

### 4.1 Role Enforcement Helpers

Update `backend/auth.py` (add a helper used by route guards):

```python
def require_roles(*allowed_roles: str):
    """Dependency factory: raises 403 if current user role is not in allowed_roles."""
    def _check(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return _check
```

Usage example in route:
```python
@router.post("/vault/denominations")
def record_denominations(
    body: DenominationUpdateRequest,
    current_user: dict = Depends(require_roles("cashier", "owner")),
):
    ...
```

---

### 4.2 Update `backend/routes/users.py`

**Change 1:** Allow creating users with `cashier` role (owner only):

```python
class CreateUserRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "employee"   # was hardcoded to "employee"
```

Add validation:
```python
VALID_ROLES = {"owner", "employee", "cashier"}

@router.post("/")
def create_user(body: CreateUserRequest, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {VALID_ROLES}")
    # ... existing hash + create logic ...
    user_id = _user_repo.create({..., "role": body.role})
```

**Change 2:** Add endpoint to change role of an existing user (owner only):

```
PATCH /users/{user_id}/role
Body: { "role": "cashier" }
```

---

### 4.3 New Router: `backend/routes/cashier.py`

All cash management endpoints. Prefix: `/cashier`. Tags: `["cashier"]`.

#### Vault Denomination Endpoints

| Method | Path | Actor | Description |
|---|---|---|---|
| `GET` | `/cashier/vault` | cashier, owner | Get current vault denomination snapshot |
| `POST` | `/cashier/vault/deposit-entry` | cashier | Record denominations received from a deposit transaction |
| `PATCH` | `/cashier/vault/adjustment` | cashier, owner | Manual vault adjustment (e.g., recount discrepancy) |
| `GET` | `/cashier/vault/logs` | cashier, owner | Paginated denomination change history |

#### Float Assignment Endpoints

| Method | Path | Actor | Description |
|---|---|---|---|
| `POST` | `/cashier/floats` | cashier | Issue a float to an employee (opens shift) |
| `GET` | `/cashier/floats` | cashier, owner | List all float assignments (filterable by status/employee) |
| `GET` | `/cashier/floats/{id}` | cashier, owner, employee (own only) | Get single float assignment detail |
| `POST` | `/cashier/floats/{id}/return` | cashier | Record float return at shift close |
| `GET` | `/cashier/floats/active` | employee | Get employee's own currently open float |

#### Request/Response Models

```python
# --- Vault ---

class DenominationEntry(BaseModel):
    denomination: int    # e.g. 10000
    quantity: int        # e.g. 5

class DepositEntryRequest(BaseModel):
    transaction_id: int                     # links to transactions.id
    denominations: list[DenominationEntry]  # notes received

class ManualAdjustmentRequest(BaseModel):
    denominations: list[DenominationEntry]  # full new quantities (replaces current)
    note: str

class VaultSnapshotResponse(BaseModel):
    denominations: list[dict]   # [{denomination, quantity, value}]
    total_value: float
    last_updated: str

# --- Floats ---

class IssueFloatRequest(BaseModel):
    employee_id: int
    denominations: list[DenominationEntry]
    note: Optional[str] = None

class ReturnFloatRequest(BaseModel):
    denominations: list[DenominationEntry]  # notes physically returned
    note: Optional[str] = None
```

---

### 4.4 Register New Router in `backend/main.py`

```python
from backend.routes import cashier as cashier_routes
# ...
app.include_router(cashier_routes.router)
```

---

### 4.5 Deposit-to-Cashier Link (Optional Enhancement)

[NEEDS CLARIFICATION: Q2 — When the cashier records denominations for a deposit, should this be linked 1:1 to a specific `transactions.id` (the deposit record), or is the cashier's denomination entry a freestanding activity not tied to individual transactions? Linking tightly enables deposit-by-deposit audit trails but adds UI complexity.]

If linked: `cash_denomination_logs.reference_id` = `transactions.id`, `reference_type` = `'transaction'`.
If freestanding: cashier records denominations in bulk at end of day or at their own discretion.

---

## 5. ViewModel Changes

### 5.1 Update `viewmodels/auth_viewmodel.py`

Add role property:

```python
@property
def is_cashier(self) -> bool:
    return self._current_user is not None and self._current_user.role == "cashier"
```

Update comment in `models/user.py`:
```python
role: Optional[str] = None  # 'owner' | 'employee' | 'cashier'
```

---

### 5.2 New: `viewmodels/cashier_viewmodel.py`

Handles all vault and float logic by calling the FastAPI backend (via `ApiClient`), mirroring the pattern of `TransactionViewModel`.

**Responsibilities:**
- `get_vault_snapshot()` → `GET /cashier/vault`
- `record_deposit_entry(transaction_id, denominations)` → `POST /cashier/vault/deposit-entry`
- `issue_float(employee_id, denominations, note)` → `POST /cashier/floats`
- `return_float(float_id, denominations, note)` → `POST /cashier/floats/{id}/return`
- `get_float_assignments(status, employee_id)` → `GET /cashier/floats`
- `get_my_active_float()` → `GET /cashier/floats/active`

---

### 5.3 Denomination Calculator Helper

A pure utility (no I/O) used by both the ViewModel and UI:

```python
# utils/denomination_utils.py

STANDARD_DENOMINATIONS = [10000, 5000, 1000, 500, 100]  # descending

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

[NEEDS CLARIFICATION: Q3 — Should the system auto-suggest denomination breakdown when the cashier issues a float (e.g., "Employee needs 50,000 MMK → suggest 5 × 10,000"), or is manual entry always required?]

---

## 6. UI Changes

### 6.1 Role-Conditional Sidebar

The sidebar in `views/dashboard_view.py` currently uses a static `MENU_ITEMS` list. This must become role-conditional.

**Current `MENU_ITEMS`:**
```python
MENU_ITEMS = [
    ("Dashboard", "dashboard", 0),
    ("Transactions", "transactions", 1),
    ("Accounts", "accounts", 2),
    ("Reports", "reports", 3),
    ("Employees", "employees", 4),
    ("Settings", "settings", 5),
]
```

**New logic (role-based):**

| Menu Item | owner | cashier | employee |
|---|---|---|---|
| Dashboard | Yes | Yes (restricted) | Yes (restricted) |
| Transactions | Yes | No | Yes |
| Cash Vault | Yes | Yes | No |
| Float Management | Yes | Yes | No |
| My Float | No | No | Yes |
| Accounts | Yes | No | No |
| Reports | Yes | Yes (cash only) | No |
| Employees | Yes | No | No |
| Settings | Yes | Yes (own pwd only) | Yes (own pwd only) |

[NEEDS CLARIFICATION: Q4 — Should the cashier be able to see transaction history (read-only) or is that completely off-limits? Cashiers need to know which deposits came in to record denominations against them.]

---

### 6.2 New View: `views/cashier_view.py`

A new top-level view added to the `QStackedWidget` in `DashboardView`. Contains sub-panels navigated by tabs or a sub-sidebar:

#### Panel A: Vault Snapshot

- A table showing all denominations: columns `[Denomination | Quantity | Total Value]`
- Footer row: total vault value
- "Record Deposit Cash" button — opens `DepositEntryDialog`
- "Manual Adjustment" button (owner and cashier) — opens `ManualAdjustmentDialog`

#### Panel B: Issue Float

- Employee selector (`QComboBox` populated from `GET /users/` filtered to `role=employee`)
- Denomination entry grid: one row per denomination, a `QSpinBox` for quantity
- Auto-suggested total value label (live-updating as user changes quantities)
- "Issue Float" button
- [NEEDS CLARIFICATION: Q5 — Should the "Issue Float" screen warn if the requested float total exceeds the current vault balance for any denomination? (e.g., vault has 3 × 10,000 but cashier tries to issue 5 × 10,000)]

#### Panel C: Float Assignments

- Filterable table: columns `[#ID | Employee | Total Float | Total Returned | Status | Opened At | Closed At]`
- Filter controls: status dropdown, employee dropdown, date range
- "View Detail" button — opens `FloatDetailDialog`
- "Close Float / Record Return" button — opens `FloatReturnDialog`

#### Panel D: Denomination Logs

- Paginated table: `[Timestamp | Event Type | Denomination | Delta | After | Reference | Performed By]`
- Filter by event_type, date range

---

### 6.3 New View: `views/employee_float_view.py`

A lightweight view for employees (replaces or supplements the existing transaction view context):

- Shows the employee's **currently open float** at the top: total assigned, total used for withdrawals, remaining.
- [NEEDS CLARIFICATION: Q6 — Should the system automatically deduct from the employee's float balance when they record a withdrawal? For example: employee has a 100,000 MMK float; they record a 50,000 MMK withdrawal → float remaining shows 50,000. Or is the float balance purely informational / not tracked per-withdrawal?]
- "Report" panel showing the employee's shift activity (withdrawals processed since float was issued).

---

### 6.4 New Dialogs

| Dialog Class | Purpose |
|---|---|
| `DepositEntryDialog` | Cashier records denomination breakdown for a specific deposit |
| `IssueFloatDialog` | Cashier specifies denominations to give to an employee |
| `FloatReturnDialog` | Cashier records denominations returned at shift close |
| `ManualAdjustmentDialog` | Correct vault quantities (with mandatory note) |
| `FloatDetailDialog` | Read-only view of a float assignment's full denomination breakdown |

All dialogs follow the existing dark-theme stylesheet (`STYLESHEET` from `dashboard_view.py`) and use `QDialog` + `QDialogButtonBox` matching existing patterns.

---

### 6.5 Denomination Entry Widget (Reusable)

A custom `QWidget` subclass used inside all dialogs that need denomination input:

```python
# views/widgets/denomination_entry_widget.py
class DenominationEntryWidget(QWidget):
    """
    Renders a grid of [denomination label | QSpinBox] rows.
    Emits total_changed(float) signal whenever any spinbox changes.
    """
    total_changed = pyqtSignal(float)

    def __init__(self, denominations: list[int], parent=None): ...
    def get_entries(self) -> list[dict]: ...       # [{denomination, quantity}]
    def set_entries(self, entries: list[dict]): ... # pre-populate
    def get_total(self) -> float: ...
```

---

## 7. Workflow Walkthrough

### 7.1 Deposit → Cashier Records Denominations

```
1. Employee records a deposit transaction via existing Transactions view.
   POST /transactions/deposit  →  Transaction created (id=42, amount=50,000 MMK)

2. Cashier opens "Cash Vault" → "Record Deposit Cash"
   DepositEntryDialog opens, showing recent unrecorded deposits (or cashier enters manually).
   Cashier inputs: 10,000×3, 5,000×4 = 50,000 MMK total.

3. Client calls POST /cashier/vault/deposit-entry
   Body: { transaction_id: 42, denominations: [{denomination:10000,quantity:3},{denomination:5000,quantity:4}] }

4. Backend:
   a. Validates transaction exists and is of type 'deposit'
   b. Validates denomination total == transaction amount  [NEEDS CLARIFICATION: Q7 — Should there be strict validation that denominations sum to exactly the transaction amount, or is loose entry acceptable?]
   c. Updates cash_denominations: +3 to 10000 row, +4 to 5000 row
   d. Inserts cash_denomination_logs rows (event_type='deposit_received')
   e. Returns updated vault snapshot

5. Cashier's vault panel refreshes automatically.
```

### 7.2 Shift Open → Issue Float to Employee

```
1. Cashier opens "Float Management" → "Issue Float"
   IssueFloatDialog: selects employee, enters denominations.
   Example: 10,000×2, 5,000×4, 1,000×10 = 50,000 MMK float

2. Client calls POST /cashier/floats
   Body: { employee_id: 3, denominations: [...], note: "Morning shift" }

3. Backend:
   a. Validates employee exists and has role='employee'
   b. Validates employee has no currently 'open' float already
      [NEEDS CLARIFICATION: Q8 — Should an employee be allowed to have multiple open floats simultaneously (e.g., two cashiers issuing to the same employee), or strictly one open float per employee at a time?]
   c. Validates vault has sufficient quantity of each denomination
   d. Deducts denominations from cash_denominations
   e. Creates cash_float_assignments record (status='open')
   f. Creates cash_float_denominations rows (direction='issued')
   g. Inserts cash_denomination_logs (event_type='float_issued')
   h. Returns float assignment record

4. Employee's "My Float" panel now shows the active float.
```

### 7.3 Employee Handles Withdrawals

```
1. Customer arrives to withdraw cash.
2. Employee records withdrawal via existing Transactions view:
   POST /transactions/withdraw  →  Transaction created

3. [NEEDS CLARIFICATION: Q6 re-stated] — Is float balance auto-decremented per withdrawal,
   or does the employee manually report at shift end?

4. Physical cash: Employee pays customer from their float envelope.
```

### 7.4 Shift Close → Employee Returns Float

```
1. At end of shift, employee returns unused cash to cashier.
2. Cashier opens float assignment → "Close Float / Record Return"
   FloatReturnDialog: enters returned denominations.
   Example: issued 50,000; returned 20,000 (30,000 used in withdrawals)

3. Client calls POST /cashier/floats/{id}/return
   Body: { denominations: [...], note: "End of day" }

4. Backend:
   a. Validates float assignment is 'open'
   b. Validates returned total <= issued total
   c. Adds returned denominations back to cash_denominations
   d. Creates cash_float_denominations rows (direction='returned')
   e. Creates cash_denomination_logs rows (event_type='float_returned')
   f. Updates cash_float_assignments: status='closed', total_returned, closed_at
   g. Returns updated float assignment

5. Vault panel reflects the returned cash.
```

---

## 8. Migration Strategy

### New Installs

`init_db()` in `backend/database.py` reads `backend/database.sql` only when the `users` table does not exist. The updated `database.sql` will contain:
- The updated `users` table with `CHECK(role IN ('owner','employee','cashier'))`
- All four new tables (9, 10, 11, 12)

### Existing Installs

A migration script is needed because:
1. The `users.role` CHECK constraint must be changed.
2. Four new tables must be created.

**File:** `migrations/002_cashier_role.sql`

```sql
-- Migration 002: Cashier Role
-- Safe to run multiple times (uses IF NOT EXISTS / IF EXISTS patterns)

PRAGMA foreign_keys = OFF;

-- Step 1: Recreate users with updated CHECK
CREATE TABLE IF NOT EXISTS users_v2 (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'employee'
                  CHECK(role IN ('owner','employee','cashier')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO users_v2 SELECT * FROM users;

-- Only rename if users_v2 now has data and users still exists
DROP TABLE IF EXISTS users;
ALTER TABLE users_v2 RENAME TO users;

CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
AFTER UPDATE ON users FOR EACH ROW
BEGIN UPDATE users SET updated_at = datetime('now') WHERE id = NEW.id; END;

-- Step 2: New tables (idempotent)
CREATE TABLE IF NOT EXISTS cash_denominations ( ... );
CREATE TABLE IF NOT EXISTS cash_denomination_logs ( ... );
CREATE TABLE IF NOT EXISTS cash_float_assignments ( ... );
CREATE TABLE IF NOT EXISTS cash_float_denominations ( ... );

PRAGMA foreign_keys = ON;
```

**Invocation:** Add a migration runner to `backend/database.py` that detects and applies pending migrations on startup.

[NEEDS CLARIFICATION: Q9 — Is there an existing migration runner or versioning mechanism in the project, or should a simple `schema_version` table be introduced?]

---

## 9. Permission Matrix

| Action | owner | cashier | employee |
|---|---|---|---|
| Create/deactivate users | Yes | No | No |
| Assign any role | Yes | No | No |
| Record transactions (deposit/withdraw/etc.) | Yes | No | Yes |
| View vault snapshot | Yes | Yes | No |
| Record deposit denomination entry | Yes | Yes | No |
| Manual vault adjustment | Yes | Yes | No |
| Issue float to employee | Yes | Yes | No |
| View all float assignments | Yes | Yes | No |
| View own float | Yes | Yes | Yes (own) |
| Close/return float | Yes | Yes | No |
| View denomination logs | Yes | Yes | No |
| View reports (full) | Yes | No | No |
| View cash reports | Yes | Yes | No |

---

## 10. Testing Strategy

### Unit Tests

| Target | What to Test |
|---|---|
| `utils/denomination_utils.py` | `calculate_total`, `suggest_denominations` edge cases |
| `CashierViewModel` | Mock API responses; verify state changes |
| `DenominationEntryWidget` | Signal emission, `get_entries()` accuracy |

### Integration Tests (via `httpx` + FastAPI `TestClient`)

| Scenario | Expected |
|---|---|
| Issue float with insufficient vault quantity | 409 Conflict |
| Issue float to employee with existing open float | 409 Conflict |
| Return more than issued | 422 Unprocessable |
| Denomination log entries created on deposit entry | Log rows match entries |
| Employee cannot access `/cashier/vault` | 403 Forbidden |
| Cashier cannot access `/transactions/deposit` | 403 Forbidden [NEEDS CLARIFICATION: Q10 — Should cashiers be completely blocked from recording transactions, or should they have read-only access for reconciliation?] |

### Manual QA Checklist

- [ ] Create a `cashier` user via owner panel
- [ ] Log in as cashier — verify sidebar shows only cashier-appropriate menu items
- [ ] Record denomination entry after an employee deposits
- [ ] Issue a float to an employee; verify vault decrements correctly
- [ ] Log in as employee — verify "My Float" shows the issued float
- [ ] Employee records withdrawals; verify float tracking (per Q6 answer)
- [ ] Cashier closes float; verify vault increments on return
- [ ] Owner views denomination logs — all events present

---

## 11. Implementation Phases

### Phase 1 — Database & Migration (Gate: all SQL runs cleanly on existing DB)

1. Write `migrations/002_cashier_role.sql` with all DDL changes
2. Update `backend/database.sql` to include new tables and updated CHECK
3. Add migration runner to `backend/database.py`
4. Seed one cashier user in `database.sql` for development

**Deliverable:** `ngwe_lwe.db` migrated; `users` table accepts `cashier` role; four new tables exist.

---

### Phase 2 — Models, Repositories, Auth (Gate: all imports resolve)

1. Update `models/user.py` role comment
2. Create `models/cash_denomination.py` dataclass
3. Create `models/cash_float_assignment.py` dataclass
4. Create `repositories/cash_denomination_repository.py`
5. Create `repositories/cash_float_repository.py`
6. Add `require_roles()` helper to `backend/auth.py`
7. Update `repositories/user_repository.py` — add `get_employees()` query

**Deliverable:** All model/repository classes importable; `require_roles` dependency factory works.

---

### Phase 3 — Backend Routes (Gate: all endpoints return correct status codes in integration tests)

1. Create `backend/routes/cashier.py` with all vault and float endpoints
2. Update `backend/routes/users.py` — allow `cashier` role creation; add `PATCH /{id}/role`
3. Register cashier router in `backend/main.py`
4. Write integration tests for all cashier routes

**Deliverable:** All API endpoints live and tested.

---

### Phase 4 — ViewModels & Utilities (Gate: unit tests pass)

1. Create `utils/denomination_utils.py`
2. Create `viewmodels/cashier_viewmodel.py`
3. Update `viewmodels/auth_viewmodel.py` — add `is_cashier` property
4. Write unit tests for ViewModel and utilities

**Deliverable:** All ViewModel methods callable; unit tests green.

---

### Phase 5 — UI (Gate: manual QA checklist passes)

1. Create `views/widgets/denomination_entry_widget.py`
2. Create `views/cashier_view.py` (Vault Snapshot, Issue Float, Float Assignments, Logs panels)
3. Create `views/employee_float_view.py`
4. Create dialog classes: `DepositEntryDialog`, `IssueFloatDialog`, `FloatReturnDialog`, `ManualAdjustmentDialog`, `FloatDetailDialog`
5. Update `views/dashboard_view.py` — role-conditional sidebar; register new pages in `QStackedWidget`
6. Run manual QA checklist

**Deliverable:** Full UI functional for all three roles.

---

### Phase 6 — Polish & Release (Gate: no open clarifications, no P1 bugs)

1. Resolve all `[NEEDS CLARIFICATION]` items and update plan + code accordingly
2. Add seed cashier user to `database.sql`
3. Update `README.md` with cashier role documentation
4. Final regression test of existing owner/employee flows (ensure nothing broken)

---

## 12. Assumptions & Risks

| # | Assumption / Risk | Mitigation |
|---|---|---|
| A1 | Currency is always MMK for physical cash; no multi-currency vault needed | Confirm with user; vault schema uses `INTEGER denomination` (MMK kyat notes) |
| A2 | A single cashier exists at a time (no multi-cashier contention on vault) | `cash_denominations` uses SQLite WAL mode which handles concurrent reads; write contention unlikely |
| A3 | `init_db()` is only called once at startup; migration runner is separate | Implement migration runner as a separate function `run_migrations()` called before `init_db()` |
| A4 | The existing `services/api_client.py` pattern is used in CashierViewModel | Read `services/` directory to confirm; if `ApiClient` needs extension, add methods there |
| A5 | Employees cannot record deposits or withdrawals without an open float | [NEEDS CLARIFICATION: Q11 — Should the system enforce that an employee MUST have an open float before they can record a withdrawal? Or is the float system informational/non-blocking?] |
| R1 | SQLite CHECK constraint migration is destructive (table rename/copy) | Test thoroughly on a copy of the production DB before running in production |
| R2 | Float-to-withdrawal linkage is implicit (time-based), not FK-enforced | Acceptable for V1; can add `withdrawal_transaction_id` FK to floats in V2 |

---

## 13. Areas Requiring Clarification

The following questions are marked `[NEEDS CLARIFICATION]` throughout this document and must be resolved before Phase 5 (UI) begins. Phases 1–3 can proceed without answers to Q3, Q4, Q5, Q6.

---

**Q1** — Denominations
> What physical note and coin denominations should be supported?
> Proposed default: 10,000 / 5,000 / 1,000 / 500 / 100 MMK notes only.
> Should 200, 50, or 20 kyat coins be included?

**Q2** — Deposit-to-denomination linkage
> When the cashier records denominations for a deposit, should it be required to link to a specific deposit `transaction_id`, or can the cashier record cash received in bulk (freestanding, not per-transaction)?

**Q3** — Auto-suggest float denominations
> When issuing a float, should the app auto-calculate suggested denomination breakdown from a target amount entered by the cashier, or is manual denomination-by-denomination entry always used?

**Q4** — Cashier transaction visibility
> Should the cashier be able to view the transaction list (read-only) to see which deposits have come in — so they know which ones need denomination entries recorded? Or are they completely locked out of the Transactions view?

**Q5** — Vault sufficiency check on float issue
> Should the "Issue Float" screen show a warning (or hard block) if the requested denomination quantities exceed what is currently in the vault for that denomination?

**Q6** — Float balance auto-deduction on withdrawal
> When an employee records a withdrawal transaction, should the system automatically deduct that amount from their open float balance? Or is the float a one-time assignment and the reconciliation only happens when the cashier closes the float at shift end?

**Q7** — Strict denomination-sum validation
> When the cashier records a deposit denomination entry, should the total of (denomination × quantity) be validated to exactly equal the deposit transaction amount? Or is approximate/partial entry allowed (e.g., cashier records the big notes only, ignores coins)?

**Q8** — Multiple open floats per employee
> Can an employee have more than one open float at the same time? (e.g., morning float not yet closed when afternoon float is issued.) Or should the system enforce exactly one open float per employee?

**Q9** — Migration versioning
> Does the project already have a migration versioning mechanism (e.g., a `schema_version` table, Alembic, or a numbered SQL file runner)? Or should a simple integer-version table be introduced as part of this feature?

**Q10** — Cashier access to transaction recording
> Should cashiers be completely blocked from the `POST /transactions/deposit` and `POST /transactions/withdraw` routes? Or should they have any access (e.g., read-only `GET /transactions/recent` for reconciliation)?

**Q11** — Float enforcement for withdrawals
> Should the system block an employee from recording a withdrawal if they have no open float? Or is the float system advisory/informational (employee can still record transactions without a float)?
