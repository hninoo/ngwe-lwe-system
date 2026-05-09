# Ngwe Lwe (ငွေလွှဲ)

Myanmar Money Transfer Business Management System — a desktop application for managing money transfer operations with real-time owner monitoring, employee transaction handling, and cashier cash float management.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop UI | PyQt6 |
| Backend API | FastAPI + Uvicorn |
| Database | SQLite 3 |
| Real-time | WebSocket |
| Language | Python 3.10+ |
| i18n | Myanmar / English bilingual |

## Architecture

**MVVM + Repository Pattern**

```
Views (PyQt6) → ViewModels → Repositories → SQLite
                    ↓
              Services (API Client, WebSocket)
```

```
ngwe-lwe-system/
├── backend/                # FastAPI server
│   ├── main.py             # App setup, WebSocket endpoint
│   ├── database.py         # SQLite connection + migrations
│   ├── database.sql        # Schema + seed data
│   ├── auth.py             # HMAC-SHA256 token auth
│   ├── websocket_manager.py
│   └── routes/             # REST API endpoints
├── models/                 # Data classes
├── repositories/           # Database access layer
├── viewmodels/             # Business logic + UI state
├── views/                  # PyQt6 UI components
├── services/               # API client
├── i18n/                   # Myanmar/English translations
├── main.py                 # Desktop app entry point
├── requirements.txt
└── .env
```

## Roles

### Owner
Full access: dashboard monitoring, account management, user management, exchange rates, commission tiers, reports, company and service-type hierarchy, fee account configuration.

### Employee
Transaction entry only: Deposit, Withdraw, Transfer, Exchange. Selects account, amount, customer details, attaches screenshot, and submits.

### Cashier
Cash float management: issues float to employees, approves cash for transactions, records vault entries, closes float sessions. Limited to cash operations — no transaction entry.

## Features

- **Three roles:** Owner, Employee, Cashier
- **4 transaction types:** Deposit, Withdraw, Transfer, Exchange (MMK/THB)
- **Company / service-type hierarchy:** Companies group service types; accounts belong to service types
- **Fee accounts:** Accounts flagged `is_fee_account=1` appear in the fee dropdown on transactions
- **Commission tiers:** Dynamic fee/commission lookup by service, account type, and amount range
- **Cash float & vault:** Cashier issues/closes float sessions, records vault denomination logs
- **Real-time sync:** WebSocket broadcasts balance updates to owner dashboard
- **Mandatory screenshots** for all transactions
- **Activity audit trail** for all user actions
- **Bilingual UI:** Myanmar and English, switchable at runtime

## Setup

### 1. Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy or edit `.env`:

```
APP_SECRET=your_secret_key_here
API_BASE_URL=http://127.0.0.1:8000
DB_PATH=ngwe_lwe.db
```

### 4. Initialize database

The database is created automatically on first run via SQLite migrations. To seed from scratch:

```bash
python -c "from backend.database import init_db; init_db()"
```

## Running

Start both the backend API and the desktop app:

**Terminal 1 — Backend:**

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — Desktop App:**

```bash
python main.py
```

### Demo Credentials

| Role | Username | Password |
|------|----------|----------|
| Owner | `owner` | `admin123` |
| Employee | `employee` | `employee123` |
| Cashier | `cashier` | `cashier123` |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login |
| POST | `/auth/logout` | Logout |
| GET | `/companies/` | List companies |
| POST | `/companies/` | Create company (owner) |
| PATCH | `/companies/{id}` | Update company (owner) |
| GET | `/companies/{id}/logo` | Get company logo |
| POST | `/companies/{id}/logo` | Upload company logo (owner) |
| GET | `/companies/{id}/service-types` | List service types for company |
| POST | `/companies/{id}/service-types` | Create service type (owner) |
| PATCH | `/service-types/{id}` | Update service type (owner) |
| DELETE | `/service-types/{id}` | Deactivate service type (owner) |
| GET | `/accounts/` | List accounts |
| POST | `/accounts/` | Create account (owner) |
| GET | `/accounts/{id}` | Get account |
| PATCH | `/accounts/{id}` | Update account (owner) |
| DELETE | `/accounts/{id}` | Deactivate account (owner) |
| PATCH | `/accounts/{id}/balance` | Set balance (owner) |
| POST | `/accounts/{id}/balance-adjust` | Adjust balance with log (owner) |
| POST | `/transactions/deposit` | Create deposit |
| POST | `/transactions/withdraw` | Create withdrawal |
| POST | `/transactions/transfer` | Create transfer |
| POST | `/transactions/exchange` | Create currency exchange |
| GET | `/transactions/` | List transactions with filters (owner) |
| GET | `/transactions/recent` | Recent transactions |
| GET | `/transactions/by-date` | Transactions by date |
| DELETE | `/transactions/{id}` | Delete transaction (owner) |
| GET | `/dashboard/summary` | Today's summary (owner) |
| GET | `/dashboard/accounts` | All accounts (owner) |
| GET | `/exchange-rates/latest` | Current exchange rates |
| POST | `/exchange-rates/` | Update rates (owner) |
| GET | `/commission-tiers/` | List commission tiers |
| GET | `/commission-tiers/lookup` | Lookup tier for amount |
| PUT | `/commission-tiers/{id}` | Update commission tier (owner) |
| DELETE | `/commission-tiers/{id}` | Delete commission tier (owner) |
| GET | `/users/` | List users (owner) |
| POST | `/users/` | Create user (owner) |
| PATCH | `/users/{id}` | Update user (owner) |
| POST | `/users/{id}/reset-password` | Reset password (owner) |
| PATCH | `/users/{id}/active` | Activate / deactivate user (owner) |
| POST | `/users/{id}/pin` | Set cashier PIN |
| POST | `/users/change-password` | Change own password |
| GET | `/cashier/vault` | Get vault balance |
| POST | `/cashier/vault/entry` | Record vault deposit / adjustment |
| GET | `/cashier/vault/logs` | Vault denomination logs |
| GET | `/cashier/floats` | List float assignments |
| POST | `/cashier/floats` | Issue float to employee (cashier) |
| GET | `/cashier/floats/my-pending` | Employee's pending float |
| GET | `/cashier/floats/{id}` | Get float assignment |
| POST | `/cashier/floats/{id}/receive` | Employee receive float with PIN |
| POST | `/cashier/floats/{id}/close` | Close float session |
| POST | `/cashier/transactions/{txn_id}/approve` | Approve cash for transaction |
| GET | `/reports/daily` | Daily report (owner) |
| GET | `/activity-logs/` | Activity audit log (owner) |
| WS | `/ws` | Real-time balance updates |
| GET | `/health` | Health check |

API docs available at `http://127.0.0.1:8000/docs` (Swagger UI).

## Transaction Workflow

1. Employee logs in and selects transaction type
2. Fills in account, amount, customer details
3. Selects fee account (Cash or flagged fee account)
4. Attaches screenshot (mandatory)
5. Submits — backend looks up commission tier, calculates fees, updates balances
6. WebSocket broadcasts update to owner dashboard in real-time

## Database Schema

- **users** — Owner, employee, and cashier accounts
- **companies** — Top-level company groupings
- **service_types** — Service types belonging to companies
- **accounts** — Phone numbers per service type with balances; `is_fee_account` flag marks fee collection accounts
- **transactions** — All transaction records (immutable)
- **commission_tiers** — Fee/commission lookup by amount range
- **exchange_rates** — MMK/THB currency rates
- **daily_summary** — Auto-calculated daily totals
- **cash_float_assignments** — Float assignments issued from cashier to employees
- **cash_denomination_logs** — Denomination-level entries for vault and float movements
- **activity_logs** — Immutable audit trail
- **schema_version** — Migration tracking
