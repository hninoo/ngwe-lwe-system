# Ngwe Lwe System

Ngwe Lwe is a Myanmar money-transfer management system for small teams. It uses a PyQt6 desktop client, a FastAPI backend, SQLite storage, and role-aware WebSocket events for real-time cashier/employee/owner coordination.

The current codebase is optimized for a single-branch or small-office deployment with fewer than 10 users. SQLite is intentionally kept, with `BEGIN IMMEDIATE` atomic transactions, WAL mode, and repository-level balance guards to keep financial writes serialized and auditable.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Desktop UI | PyQt6 |
| Backend API | FastAPI + Uvicorn |
| Database | SQLite 3 |
| Real-time sync | FastAPI WebSocket |
| Auth | HMAC-SHA256 bearer tokens + one-time WebSocket tickets |
| Password/PIN hashing | bcrypt |
| Language | Python 3.10+ |
| i18n | Myanmar / English |

## Architecture

```text
PyQt6 Views
    -> ViewModels
    -> Services/ApiClient
    -> FastAPI Routes
    -> Repositories
    -> SQLite

FastAPI Routes
    -> Repository business operations
    -> WebSocket ConnectionManager
    -> Role/user-targeted desktop refresh events
```

Key directories:

```text
backend/                 FastAPI app, auth, database, routes, WebSocket manager
models/                  Dataclasses shared by repositories and viewmodels
repositories/            Database access and transaction business rules
services/                Desktop API client and vault service helpers
viewmodels/              UI-facing state and business orchestration
views/                   PyQt6 screens and dialogs
views/transaction/       Transaction forms and employee vault views
views/settings/          Owner/admin settings pages
i18n/                    Myanmar/English translations
tests/                   Repository, route, migration, and integration tests
```

## Roles

| Role | Responsibilities |
| --- | --- |
| Owner | Dashboard, accounts, users, companies, service types, exchange rates, commission tiers, reports, reconciliation, and audit logs. |
| Employee | Creates Cash In, Cash Out, Transfer, and Exchange transactions after receiving an active cash float. |
| Cashier | Issues/receives/returns employee floats, manages main vault denominations, confirms pending Cash In cash receipt, and approves cash workflows. |

Cashiers cannot create normal transactions. Employees must have an active float before transaction entry.

## Core Workflows

### Cash In

Cash In follows the banking-standard teller model: physical cash comes in, digital balance goes out.

1. Employee creates Cash In.
2. Account digital balance is deducted immediately inside an atomic transaction.
3. Transaction is saved as `PENDING_CASHIER_CONFIRM` with `vault_impact = none`.
4. Cashiers receive a `cash_in_pending` WebSocket event.
5. Cashier confirms with PIN and denomination breakdown.
6. Main vault is credited by denomination and transaction becomes `COMPLETED`.
7. If cashier cancels, `CashInRepository.cancel_pending_cash_in()` reverses the digital deduction first. If reversal fails because the account is inactive or missing, cancellation raises `RuntimeError` and the atomic transaction rolls back.

### Cash Out

Cash Out credits digital value and deducts employee float cash.

1. Employee must have an active float.
2. Float sufficiency and denomination checks run inside the atomic block.
3. Account balance is credited only when the account is active.
4. Employee mini-vault denominations/current balance are deducted.
5. Transaction completes immediately.

### Transfers and Exchange

Transfers and exchanges use the same repository pattern, server-side fee resolution, active float checks for employees, and role-aware WebSocket broadcasts for dashboards.

### Float Lifecycle

```text
Cashier issues float
    -> Employee receives with PIN and denomination verification
    -> Employee uses active float for cash workflows
    -> Employee initiates return with denomination breakdown
    -> Cashier confirms return with PIN
    -> Main vault is credited and float closes
```

### Denomination Exchange And Change

Cashiers and employees can record denomination-only exchanges without changing the float total. The backend validates that the outgoing and incoming note totals match, checks that the active float has the note being given and the main vault has the notes being returned, then atomically moves denominations between the employee float and main vault. Each exchange is saved in `denomination_exchanges` and activity logs.

Cashiers can also record fee payments with change:

1. Cashier enters notes received from the customer.
2. Backend calculates `change_due = received_total - fee_amount`.
3. If change denominations are not supplied, the backend calculates them using available vault notes.
4. Main vault denominations are updated atomically: received notes are added and change notes are subtracted.
5. `transaction_payment_denominations` stores paid and returned quantities per note.

## Money Rules

- Currency math at route boundaries is normalized through `backend.money.normalize_money()`.
- Repository balance mutations use `Decimal(str(value))` where precision matters.
- `AccountRepository.increment_balance()` only updates active accounts:

```sql
UPDATE accounts
SET balance = balance + ?
WHERE id = ? AND is_active = 1
```

- Fees are derived server-side from commission tiers. Client-supplied fee override fields are ignored by the repository fee resolver.
- MMK fee rounding is centralized in `TransactionOperationBase.round_fee()`:
  - `amount <= 0` returns `0`
  - remainder `<= 20` rounds down to the nearest 100
  - remainder `> 20` rounds up to the nearest 100
  - minimum positive fee is `100` MMK

## Real-Time Sync

WebSocket authentication uses a short-lived one-time ticket:

1. Client authenticates with `/auth/login`.
2. Client calls `POST /ws-ticket`.
3. Server issues a 30-second single-use ticket carrying `user_id` and `role`.
4. Client connects to `/ws?ticket=<ticket>`.
5. `ConnectionManager` stores the user context and can broadcast to:
   - all connected clients
   - one role
   - multiple roles
   - one user

Important event types currently emitted:

| Event | Target |
| --- | --- |
| `cash_in_pending` | Cashiers |
| `cash_in_confirmed` | Transaction creator |
| `cash_in_cancelled` | Transaction creator |
| `pending_cash_in_update` | Cashiers and owner |
| `new_transaction` | Cashiers and owner |
| `balance_update` | Cashiers and owner |
| `float_issued` | Assigned employee |
| `float_received` | Cashiers and owner |
| `float_return_initiated` | Cashiers and owner |
| `float_return_confirmed` | Assigned employee |
| `float_update` | Cashiers and owner |
| `transaction_approved` | Transaction creator |
| `transaction_update` | Cashiers and owner |

The desktop client runs WebSocket workers in `views/dashboard_view.py` and `views/cashier_view.py`, using Qt signals to update UI state safely from background threads.

## Security Controls

- Strong `APP_SECRET` required at startup; weak placeholders are rejected.
- Bearer token payload includes `auth_version`; user deactivation, role changes, password resets, and credential updates can revoke existing tokens.
- Login uses bcrypt and runs a dummy bcrypt check for missing users to reduce username-enumeration timing leaks.
- Login and PIN flows use in-memory rate limiting.
- WebSocket tickets are short-lived and single-use.
- Role checks are enforced on owner/cashier/employee routes.
- Cashier PIN is required for high-risk cash operations.
- Negative denomination counts are rejected by Pydantic validators and route parsing.
- Cash In confirmation denomination totals must match the transaction amount within `CASH_TOLERANCE_MMK = 500`.
- Screenshot paths accepted by transaction routes must be server-owned paths under `uploads/screenshots`; absolute paths, drive-letter paths, and `..` traversal are rejected.
- Hard transaction deletes are disabled; use reversal/cancel workflows instead.
- Activity logs capture financial and administrative actions.

Operational note: the rate limiter, WebSocket ticket store, and WebSocket connection manager are in-memory. Run a single Uvicorn worker unless these are moved to SQLite or Redis.

## Setup

Create and activate a virtual environment:

```powershell
python -m venv venv
venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Configure environment variables in `.env` or the process environment:

```text
APP_SECRET=<random string of at least 32 characters>
API_BASE_URL=http://127.0.0.1:8000
WS_URL=ws://127.0.0.1:8000/ws
DB_PATH=ngwe_lwe.db
CORS_ALLOW_ORIGINS=http://127.0.0.1,http://localhost
```

Initialize or migrate the database:

```powershell
python -c "from backend.database import init_db; init_db()"
```

The app also calls `init_db()` on backend startup.

## Running In Development

Start the backend:

```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Start the desktop client:

```powershell
python main.py
```

The desktop launcher can also run in host/client mode:

- Host mode starts the local Uvicorn server in a background Qt thread.
- Client mode connects to a LAN server from saved config or a startup dialog.

API docs are available at:

```text
http://127.0.0.1:8000/docs
```

## Testing

Run the full test suite:

```powershell
python -m pytest -q
```

Useful focused checks:

```powershell
python -m pytest -q tests/test_transaction_viewmodel.py tests/test_integration.py
python -m compileall -q .
```

## Main API Surface

Authentication and WebSocket:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/auth/login` | Login and receive bearer token |
| POST | `/auth/logout` | Logout response endpoint |
| POST | `/ws-ticket` | Issue one-time WebSocket ticket |
| WS | `/ws?ticket=...` | Role/user-aware real-time events |
| GET | `/health` | Health check and active WebSocket count |

Transactions:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/transactions/cash_in` | Create pending Cash In |
| POST | `/transactions/cash_out` | Create Cash Out |
| POST | `/transactions/transfer` | Create Transfer |
| POST | `/transactions/exchange` | Create Exchange |
| GET | `/transactions/` | Owner transaction listing with filters |
| GET | `/transactions/recent` | Recent transactions |
| GET | `/transactions/by-date` | Transactions for a date |
| DELETE | `/transactions/{txn_id}` | Disabled hard delete guard |

Cashier and vault:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/cashier/employees` | Employees visible to cashier |
| GET | `/cashier/vault` | Main vault summary |
| POST | `/cashier/vault/entry` | Record vault cash-in/adjustment |
| GET | `/cashier/vault/logs` | Vault denomination logs |
| GET | `/cashier/vault/inventory` | Main vault plus employee float inventory |
| GET | `/cashier/vault/denominations` | Main vault denomination balance for change |
| GET | `/cashier/denominations` | Configured MMK note denominations |
| POST | `/cashier/denomination/exchange` | Exchange denominations in an active employee float |
| GET | `/cashier/floats` | Float assignments |
| POST | `/cashier/floats` | Issue float |
| GET | `/cashier/floats/my-pending` | Employee pending float |
| GET | `/cashier/floats/{float_id}` | Float detail |
| GET | `/cashier/floats/{float_id}/denominations` | Float denomination balance |
| POST | `/cashier/floats/{float_id}/receive` | Employee receives float |
| POST | `/cashier/floats/{float_id}/initiate-return` | Employee initiates return |
| POST | `/cashier/floats/{float_id}/confirm-return` | Cashier confirms return |
| GET | `/cashier/pending-cash-ins` | Pending Cash In list |
| POST | `/cashier/transactions/{txn_id}/confirm-cash-in` | Confirm pending Cash In |
| POST | `/cashier/transactions/{txn_id}/cancel-cash-in` | Cancel and reverse pending Cash In |
| POST | `/cashier/transactions/{txn_id}/approve` | Approve supported cash workflows |
| POST | `/cashier/transactions/{txn_id}/payment` | Record customer fee payment and change |

Administration:

| Area | Endpoints |
| --- | --- |
| Accounts | `/accounts/`, `/accounts/{id}`, `/accounts/{id}/balance-adjust` |
| Users | `/users/`, `/users/{id}`, `/users/{id}/reset-password`, `/users/{id}/pin`, `/users/change-password`, `/users/change-pin` |
| Companies | `/companies/`, `/companies/{id}`, `/companies/{id}/logo`, `/companies/{id}/service-types` |
| Service types | `/service-types/{id}` |
| Commission tiers | `/commission-tiers/`, `/commission-tiers/lookup`, `/commission-tiers/{id}` |
| Exchange rates | `/exchange-rates/latest`, `/exchange-rates/` |
| Dashboard | `/dashboard/summary`, `/dashboard/accounts` |
| Reports | `/reports/daily` |
| Reconciliation | `/reconciliation/current`, `/reconciliation/close-day`, `/reconciliation/history` |
| Activity logs | `/activity-logs/` |

## Database

The database is created from `backend/database.sql` on first run and migrated by numbered migrations in `backend/database.py`.

Important tables:

- `users`
- `companies`
- `service_types`
- `accounts`
- `transactions`
- `commission_tiers`
- `exchange_rates`
- `cash_float_assignments`
- `cash_float_denominations`
- `cash_denomination_logs`
- `note_denominations`
- `vault_denomination_balances`
- `transaction_payment_denominations`
- `denomination_exchanges`
- `vault_transactions`
- `daily_reconciliation_logs`
- `activity_logs`
- `schema_version`

SQLite is configured with foreign keys enabled and WAL mode. Multi-step financial writes should use `backend.database.atomic()`.

## Build Notes

PyInstaller specs are included:

- `NgweLweServer.spec`
- `NgweLweClient.spec`

Installer scripts are included:

- `setup.iss`
- `setup_server.iss`

Use `scripts/build_all.bat` as the starting point for packaged builds.
