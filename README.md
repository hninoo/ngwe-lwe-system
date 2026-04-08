# Ngwe Lwe System (ငွေလွှဲ)

Myanmar Money Transfer Business Management System — a desktop application for managing money transfer operations with real-time owner monitoring and employee transaction handling.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop UI | PyQt6 |
| Backend API | FastAPI + Uvicorn |
| Database | MySQL 8 |
| Real-time | WebSocket |
| Language | Python 3.12+ |

## Architecture

**MVVM + Repository Pattern**

```
Views (PyQt6) → ViewModels → Repositories → MySQL
                    ↓
              Services (API Client, WebSocket)
```

```
ngwe-lwe-system/
├── backend/                # FastAPI server
│   ├── main.py             # App setup, WebSocket endpoint
│   ├── database.py         # MySQL connection pooling
│   ├── database.sql        # Schema + seed data
│   ├── auth.py             # HMAC-SHA256 token auth
│   ├── websocket_manager.py
│   └── routes/             # REST API endpoints
├── models/                 # Data classes
├── repositories/           # Database access layer
├── viewmodels/             # Business logic + UI state
├── views/                  # PyQt6 UI components
├── services/               # API client
├── main.py                 # Desktop app entry point
├── requirements.txt
└── .env
```

## Features

- **Two roles:** Owner (dashboard + management) and Employee (transactions)
- **4 transaction types:** Deposit, Withdraw, Transfer, Exchange (MMK/THB)
- **14 payment services:** KPay, Wave, MPT Pay, KBZ Bank, Thai Bank, etc.
- **Commission tiers:** Dynamic fee/commission lookup by service, account type, and amount range
- **Real-time sync:** WebSocket broadcasts balance updates to owner dashboard
- **Mandatory screenshots** for all transactions
- **Activity audit trail** for all user actions

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
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ngwe_lwe_db
DB_USER=root
DB_PASSWORD=
APP_SECRET=your_secret_key_here
API_BASE_URL=http://127.0.0.1:8000
```

### 4. Create database

```bash
mysql -u root < backend/database.sql
```

This creates the schema and inserts seed data (users, services, accounts, commission tiers).

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
| Employee | `employee1` | `admin123` |
| Employee | `employee2` | `admin123` |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login |
| POST | `/auth/logout` | Logout |
| GET | `/services/` | List payment services |
| GET | `/accounts/` | List accounts |
| PATCH | `/accounts/{id}/balance` | Update balance (owner) |
| POST | `/transactions/deposit` | Create deposit |
| POST | `/transactions/withdraw` | Create withdrawal |
| POST | `/transactions/transfer` | Create transfer |
| POST | `/transactions/exchange` | Create currency exchange |
| GET | `/transactions/recent` | Recent transactions |
| GET | `/dashboard/summary` | Today's summary (owner) |
| GET | `/dashboard/accounts` | All accounts (owner) |
| GET | `/exchange-rates/latest` | Current exchange rates |
| POST | `/exchange-rates/` | Update rates (owner) |
| GET | `/commission-tiers/` | List commission tiers |
| GET | `/commission-tiers/lookup` | Lookup tier for amount |
| GET | `/users/` | List users (owner) |
| POST | `/users/` | Create employee (owner) |
| GET | `/reports/daily` | Daily report (owner) |
| WS | `/ws` | Real-time balance updates |
| GET | `/health` | Health check |

API docs available at `http://127.0.0.1:8000/docs` (Swagger UI).

## Transaction Workflow

1. Employee logs in and selects transaction type
2. Fills in account, amount, customer details
3. Attaches screenshot (mandatory)
4. Submits — backend looks up commission tier, calculates fees, updates balances
5. WebSocket broadcasts update to owner dashboard in real-time

## Database Schema

- **users** — Owner and employee accounts
- **services** — 14 payment services (KPay, Wave, banks, etc.)
- **accounts** — Phone numbers per service with balances
- **transactions** — All transaction records (immutable)
- **commission_tiers** — Fee/commission lookup by amount range
- **exchange_rates** — MMK/THB currency rates
- **daily_summary** — Auto-calculated daily totals
- **activity_logs** — Immutable audit trail
