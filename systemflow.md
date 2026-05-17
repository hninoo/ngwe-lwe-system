# Ngwe Lwe System Flow

This document summarizes the runtime and business flow of the Ngwe Lwe System as implemented in the current project.

## System Overview

Ngwe Lwe is a PyQt6 desktop money-transfer application backed by a FastAPI server and SQLite database. The desktop client can either host a local backend or connect to a LAN backend. Users authenticate through the API, receive role-specific desktop screens, and perform account, transaction, vault, float, reporting, and administration workflows.

```mermaid
flowchart LR
    User["Owner / Cashier / Employee"] --> UI["PyQt6 Desktop UI"]
    UI --> Views["Views"]
    Views --> ViewModels["ViewModels"]
    ViewModels --> ApiClient["services.api_client.ApiClient"]
    ApiClient --> API["FastAPI backend"]
    API --> Routes["Route modules"]
    Routes --> Repos["Repositories / VaultService"]
    Repos --> DB[("SQLite database")]
    Routes --> WS["ConnectionManager"]
    WS --> UI
```

## Main Runtime Flow

The unified launcher in `main.py` decides whether this machine should host the server or connect as a client. In host mode it starts Uvicorn in a background Qt thread, waits for `/health`, then opens the login view. In client mode it reads saved host settings, checks the remote server, and lets the user change the server if needed.

```mermaid
flowchart TD
    Start["Start main.py"] --> LoadCfg["Read app_config.json or show startup choice"]
    LoadCfg --> Host{"Host mode?"}
    Host -- Yes --> SetLocal["Set DB_PATH, APP_SECRET, API_BASE_URL, WS_URL"]
    SetLocal --> StartServer["Start backend.main:app in ServerThread"]
    StartServer --> Health["Poll /health"]
    Health --> LoginHost["Open LoginView with host info"]
    Host -- No --> ReadClient["Read client_config.json / installer host"]
    ReadClient --> Probe["Probe server /health"]
    Probe --> Connected{"Connected?"}
    Connected -- No --> ServerDialog["Show ServerConfigDialog"]
    Connected -- Yes --> ApplyUrls["Apply API and WS URLs"]
    ServerDialog --> ApplyUrls
    ApplyUrls --> LoginClient["Open LoginView"]
```

There is also a standalone server manager in `run_server_app.py` that lets an admin configure host and port, start or stop the Uvicorn backend, and view server logs.

## Authentication And Role Flow

Authentication is handled by `POST /auth/login`. The backend validates credentials, returns a HMAC-SHA256 bearer token, and the desktop stores the token in `ApiClient`. After login, `LoginView` opens a role-specific window.

```mermaid
flowchart TD
    Login["LoginView username/password"] --> AuthAPI["POST /auth/login"]
    AuthAPI --> AuthRepo["UserRepository + bcrypt password check"]
    AuthRepo --> Token["Create bearer token with user_id, role, auth_version"]
    Token --> Client["ApiClient stores token and user"]
    Client --> Role{"User role"}
    Role -- owner --> OwnerUI["DashboardView with owner/admin pages"]
    Role -- cashier --> CashierUI["CashierView"]
    Role -- employee --> EmployeeUI["DashboardView / TransactionView"]
    EmployeeUI --> PendingFloat["Check /cashier/floats/my-pending"]
    PendingFloat --> ReceiveDialog["ReceiveFloatDialog if pending float exists"]
```

Every protected API request passes through `backend.auth.get_current_user()`. Role checks are enforced in route modules such as `transactions.py`, `cashier.py`, `users.py`, and the owner-only administration routes.

## API And Persistence Flow

The FastAPI app is assembled in `backend/main.py`. On startup it ensures logo storage exists, initializes and migrates the database, creates a shared WebSocket `ConnectionManager`, and includes all route modules.

```mermaid
flowchart TD
    FastAPI["backend.main FastAPI app"] --> Lifespan["lifespan()"]
    Lifespan --> InitDb["backend.database.init_db()"]
    InitDb --> Schema["database.sql + numbered migrations"]
    FastAPI --> Routers["Included routers"]
    Routers --> Auth["/auth"]
    Routers --> Transactions["/transactions"]
    Routers --> Cashier["/cashier"]
    Routers --> Admin["/accounts /users /companies /service-types /commission-tiers"]
    Routers --> Reports["/dashboard /reports /reconciliation /activity-logs"]
    Routers --> Repos["Repositories"]
    Repos --> Atomic["backend.database.atomic() for multi-step financial writes"]
    Atomic --> SQLite[("ngwe_lwe.db")]
```

Important persistence tables include `users`, `companies`, `service_types`, `accounts`, `transactions`, `commission_tiers`, `exchange_rates`, `cash_float_assignments`, `cash_float_denominations`, `cash_denomination_logs`, `vault_denomination_balances`, `transaction_payment_denominations`, `daily_reconciliation_logs`, and `activity_logs`.

## WebSocket Refresh Flow

Real-time updates use a short-lived one-time WebSocket ticket instead of placing the bearer token in the WebSocket URL.

```mermaid
sequenceDiagram
    participant Client as Desktop Client
    participant API as FastAPI
    participant Tickets as TicketStore
    participant WS as ConnectionManager

    Client->>API: POST /auth/login
    API-->>Client: bearer token
    Client->>API: POST /ws-ticket
    API->>Tickets: issue ticket for user_id and role
    API-->>Client: ticket
    Client->>API: WS /ws?ticket=...
    API->>Tickets: consume ticket once
    API->>WS: connect(websocket, user_info)
    API-->>Client: role/user-targeted events
```

Routes publish events through `ConnectionManager` after important state changes. Examples include `cash_in_pending`, `cash_in_confirmed`, `cash_in_cancelled`, `pending_cash_in_update`, `new_transaction`, `balance_update`, `float_issued`, `float_received`, `float_return_initiated`, `float_return_confirmed`, `float_update`, `transaction_approved`, and `transaction_payment_recorded`.

## Transaction Creation Flow

Employees and owners create normal transactions through `/transactions`. Cashiers are blocked from creating normal transactions. Employees must have an active cash float before creating cash-impacting transaction records.

```mermaid
flowchart TD
    Form["Transaction UI form"] --> ApiClient["ApiClient create_* method"]
    ApiClient --> Route["/transactions/cash_in, cash_out, transfer, exchange"]
    Route --> AuthRole["Authenticate and role-check user"]
    AuthRole --> CashierBlocked{"Role is cashier?"}
    CashierBlocked -- Yes --> Deny["403: Cashiers cannot record transactions"]
    CashierBlocked -- No --> EmployeeFloat{"Employee?"}
    EmployeeFloat -- Yes --> ActiveFloat["Require active float"]
    EmployeeFloat -- No --> VM["TransactionViewModel"]
    ActiveFloat --> VM
    VM --> Repo["CashIn/CashOut/Transfer/Exchange repository"]
    Repo --> Atomic["Atomic balance, fee, float, and transaction updates"]
    Atomic --> DB[("SQLite")]
    DB --> Broadcast["Broadcast balance/new transaction events"]
```

The transaction repositories share common logic in `TransactionOperationBase`: amount validation, fee tier lookup, server-side fee resolution, employee float validation, fee account updates, audit logging, and MMK fee rounding.

## Cash In Flow

Cash In is a two-step workflow. The employee records the digital movement first, then a cashier confirms the physical cash with PIN and denominations.

```mermaid
sequenceDiagram
    participant Employee
    participant Transactions as /transactions/cash_in
    participant CashInRepo as CashInRepository
    participant DB as SQLite
    participant Cashier as Cashier
    participant CashierAPI as /cashier/transactions/{id}
    participant WS as WebSocket

    Employee->>Transactions: Create Cash In
    Transactions->>Transactions: Require non-cashier user and active employee float
    Transactions->>CashInRepo: create(...)
    CashInRepo->>DB: Deduct digital account balance
    CashInRepo->>DB: Save PENDING_CASHIER_CONFIRM transaction
    CashInRepo->>DB: Deduct employee change from float if overpayment exists
    Transactions->>WS: cash_in_pending to cashiers
    Cashier->>CashierAPI: confirm-cash-in with PIN and denominations
    CashierAPI->>CashierAPI: Validate cashier PIN and net cash total
    CashierAPI->>DB: Mark transaction COMPLETED
    CashierAPI->>DB: Credit main vault denominations
    CashierAPI->>WS: cash_in_confirmed and pending_cash_in_update
```

If the cashier cancels a pending Cash In, `CashInRepository.cancel_pending_cash_in()` reverses the digital account deduction inside an atomic transaction before marking the transaction cancelled. If the reversal cannot be applied safely, the cancellation fails and the transaction remains pending.

## Cash Out, Transfer, And Exchange Flow

Cash Out, Transfer, and Exchange complete through their respective transaction repositories. The backend calculates fees from commission tiers and updates balances inside atomic transactions.

```mermaid
flowchart TD
    Request["Employee/owner submits cash_out, transfer, or exchange"] --> Validate["Validate amount, screenshot path, role, active float"]
    Validate --> Fee["Resolve commission tier and total fee server-side"]
    Fee --> Operation{"Operation type"}
    Operation -- cash_out --> CashOut["Credit account digital balance and deduct employee float denominations"]
    Operation -- transfer --> Transfer["Move digital value between accounts and handle employee cash denominations"]
    Operation -- exchange --> Exchange["Apply exchange transaction and denomination impact"]
    CashOut --> Save["Save transaction and activity log"]
    Transfer --> Save
    Exchange --> Save
    Save --> Broadcast["Broadcast balance_update and new_transaction"]
```

## Cash Float Lifecycle

The cashier manages the main vault and issues floats to employees. Employees must receive a float with PIN and denomination verification before they can use it.

```mermaid
flowchart TD
    Vault["Main vault denominations"] --> Issue["Cashier issues float: POST /cashier/floats"]
    Issue --> DebitVault["VaultService debits main vault"]
    DebitVault --> PendingFloat["cash_float_assignments status pending"]
    PendingFloat --> NotifyEmployee["WebSocket float_issued to employee"]
    NotifyEmployee --> Receive["Employee confirms receipt with PIN and denominations"]
    Receive --> ActiveFloat["Float becomes active"]
    ActiveFloat --> Transactions["Employee creates cash workflows"]
    Transactions --> ReturnStart["Employee initiates return with denominations and PIN"]
    ReturnStart --> PendingReturn["Float pending reconciliation"]
    PendingReturn --> ConfirmReturn["Cashier confirms return with PIN"]
    ConfirmReturn --> CreditVault["Main vault credited"]
    CreditVault --> Closed["Float closed"]
```

`VaultService` and `CashFloatRepository` guard denomination mismatches, insufficient denomination balances, invalid float state transitions, and atomic vault/float updates.

## Cashier Vault And Approval Flow

Cashier routes are centered around physical cash control: main vault entries, pending Cash In confirmation, transaction cash approval, and fee payment with change.

```mermaid
flowchart TD
    CashierUI["CashierView"] --> VaultEntry["Record vault entry or adjustment"]
    CashierUI --> PendingCashIns["Review pending Cash Ins"]
    CashierUI --> Approve["Approve supported cash workflows"]
    CashierUI --> Payment["Record fee payment and change"]
    VaultEntry --> VaultRepo["CashDenominationRepository"]
    PendingCashIns --> TxnRepo["TransactionRepository"]
    Approve --> Atomic["atomic()"]
    Payment --> VaultService["VaultService.record_transaction_payment"]
    Atomic --> Logs["cash_denomination_logs + activity_logs"]
    VaultService --> Logs
    Logs --> Inventory["Updated vault / float inventory"]
```

Cashier PIN checks are rate-limited for high-risk actions such as receiving returns, confirming Cash In, cancelling Cash In, and employee float receipt/return flows.

## Administration And Reporting Flow

Owners use dashboard and settings screens to manage system reference data and reporting.

```mermaid
flowchart LR
    Owner["Owner Dashboard"] --> Accounts["Accounts"]
    Owner --> Users["Users and PINs"]
    Owner --> Companies["Companies and logos"]
    Owner --> ServiceTypes["Service types"]
    Owner --> Tiers["Commission tiers"]
    Owner --> Rates["Exchange rates"]
    Owner --> Reports["Daily reports"]
    Owner --> Reconciliation["Daily reconciliation"]
    Owner --> Activity["Activity logs"]
    Accounts --> DB[("SQLite")]
    Users --> DB
    Companies --> DB
    ServiceTypes --> DB
    Tiers --> DB
    Rates --> DB
    Reports --> DB
    Reconciliation --> DB
    Activity --> DB
```

Administrative routes use repository classes such as `AccountRepository`, `UserRepository`, `CompanyRepository`, `ServiceTypeRepository`, `CommissionTierRepository`, `ExchangeRateRepository`, `DailyReconciliationRepository`, and `TransactionRepository`.

## Security And Data Integrity Flow

```mermaid
flowchart TD
    Request["Incoming API request"] --> Auth["Bearer token validation"]
    Auth --> Version["auth_version check"]
    Version --> Role["Route-level role check"]
    Role --> Validation["Pydantic and custom validation"]
    Validation --> Money["normalize_money and Decimal-safe calculations"]
    Money --> Atomic["atomic SQLite transaction for financial writes"]
    Atomic --> Guards["Active account, float, denomination, and state guards"]
    Guards --> Audit["activity_logs and denomination logs"]
```

Key controls include strong `APP_SECRET`, bcrypt password/PIN hashing, login and PIN rate limiting, short-lived one-use WebSocket tickets, disabled hard deletes for financial transactions, screenshot path validation, active-account balance updates, denomination validation, and atomic repository-level financial writes.

## High-Level Module Map

| Area | Main files |
| --- | --- |
| Desktop startup | `main.py`, `run_server_app.py` |
| API app | `backend/main.py` |
| Auth/security | `backend/auth.py`, `backend/security_policy.py`, `backend/rate_limit.py` |
| WebSocket | `backend/websocket_manager.py` |
| Routes | `backend/routes/*.py` |
| Database | `backend/database.py`, `backend/database.sql`, `ngwe_lwe.db` |
| Domain models | `models/*.py` |
| Business persistence | `repositories/*.py` |
| Desktop API bridge | `services/api_client.py` |
| Vault operations | `services/vault_service.py` |
| UI orchestration | `viewmodels/*.py` |
| Desktop screens | `views/*.py`, `views/ui/*.py`, `views/settings/*.py` |
| Tests | `tests/*.py` |
