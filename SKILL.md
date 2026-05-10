# SKILL.md — ငွေလွှဲ Business Management System

## Project Overview
Myanmar money transfer business management system.
Owner monitors real-time. Employees handle transactions.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Desktop UI | PyQt6 (Windows) |
| Backend | Python FastAPI |
| Real-time Sync | WebSocket (FastAPI built-in) |
| Database | MySQL |
| License Protection | Motherboard ID (WMIC) |
| Version Control | Git + GitHub |

**V2 (future):** Flutter Mobile App

---

## Architecture Pattern

**MVVM + Repository + SOLID**

```
project/
├── models/              # Pure data classes (no logic)
├── repositories/        # All DB queries here only
├── viewmodels/          # UI state + business logic
├── views/               # PyQt6 UI — display only
├── services/            # WebSocket, License
├── backend/             # FastAPI server
│   ├── main.py
│   ├── database.py
│   ├── database.sql
│   └── routes/
├── main.py
├── .env
├── .gitignore
└── requirements.txt
```

**Data Flow:**
```
View ↔ ViewModel → Repository → MySQL
          ↓
       Service (WebSocket)
```

---

## SOLID Principles (enforce always)

- **S** — Single Responsibility: class တစ်ခု တစ်ခုခုပဲ လုပ်
- **O** — Open/Closed: extend လုပ်လို့ရ၊ modify မလုပ်ရ
- **L** — Liskov: subclass က parent behavior မပျက်ရ
- **I** — Interface Segregation: interface သေးသေး၊ တိတိကျကျ
- **D** — Dependency Inversion: concrete မဟုတ်ဘဲ abstraction ပေါ် depend လုပ်

**Clean Code Rules:**
- Function တစ်ခု 20 lines မကျော်ရ
- Magic number မသုံးရ — constants file ခွဲ
- Controller/ViewModel က Repository ကနေပဲ data ယူရမယ်
- DB query တွေ Repository layer ထဲပဲ

---

## Database Tables

| Table | အကြောင်း |
|---|---|
| `users` | Owner + Employee accounts |
| `services` | KPay, Wave, KBZ etc (14 services) |
| `accounts` | Phone numbers per service (Personal/Agent) |
| `transactions` | CashIn, CashOut, Transfer, Exchange |
| `exchange_rates` | MMK ↔ THB rates |
| `daily_summary` | Auto-calculated daily report |
| `activity_logs` | All user actions (audit trail) |

---

## Account Types

| Type | Balance Calculation |
|---|---|
| Personal | amount - commission (from commission_tiers) |
| Agent | amount - commission (from commission_tiers) |

## Commission Tiers (commission_tiers table)

All 3 service types (KPAY, WAVE, BANK) use `commission_tiers` table.

| Field | Purpose |
|---|---|
| `fee_amount` | Customer charge (ကောက်ခံမည့်) |
| `comm_send` | Agent earns on **CashIn** (customer sends in) |
| `comm_receive` | Agent earns on **CashOut** (customer takes out) |

- Tier lookup: `service_type` + `account_type` + `amount_from <= amount <= amount_to`
- BANK tiers: owner manually sets via Settings
- Tier not found → fee=0, commission=0
- `account.commission_rate` and `service.default_customer_fee` are **deprecated**

---

## Transaction Types

1. **CashIn (အသွင်း)** — Customer ငွေသား ပေး → wallet ထဲ လွှဲ
2. **CashOut (အထုတ်)** — Customer wallet → ငွေသား ထုတ်ပေး
3. **Bank Transfer (ဘဏ်ချင်းငွေလဲ)** — Account A → Account B
4. **Exchange (ကျပ်-ဘတ်)** — MMK ↔ THB

---

## User Roles

### Owner
- Dashboard — real-time balance အကုန်ကြည့်
- ဝန်ထမ်း transaction အကုန်ကြည့်
- Screenshot ကြည့်
- Account/Service/User စီမံ
- Exchange rate + Fee သတ်မှတ်
- Report/Summary
- System settings

### Employee
- Transaction လုပ် (4 types)
- ကိုယ့် transaction history ပဲ ကြည့်နိုင်
- Screenshot မဖြစ်မနေ attach ရမယ်
- Account/Service/Settings — ခွင့်မရှိ
- Delete/Edit — ခွင့်မရှိ

---

## Transaction Workflow

```
Login → Transaction ရွေး → Service + Account ရွေး
→ Amount ဖြည့် → Transfer လုပ် → Screenshot ရိုက် → Save
```

Screenshot မပါဘဲ Save လို့မရ.

---

## License Protection

```python
# Windows — Motherboard ID
import subprocess
result = subprocess.check_output('wmic baseboard get serialnumber', shell=True)
motherboard_id = result.decode().split('\n')[1].strip()

# Hash နဲ့ .lic file generate
import hashlib
key = hashlib.sha256(f"{motherboard_id}+SECRET_SALT".encode()).hexdigest()
```

App start logic:
```
.lic file ရှိ + Motherboard match → Real App launch
မဟုတ်ရင် → Fake game launch (snake/puzzle)
```

---

## Security

- Login: username/password per user
- Activity log: ဘယ်သူ ဘာလုပ်လဲ အကုန် record (ဖျက်လို့မရ)
- Permission: Employee → transaction only
- Mandatory screenshot
- No delete/edit for employees
- Daily balance reconciliation + alert

---

## V1 Build Order

1. MySQL schema (database.sql)
2. DB connection (database.py)
3. Models layer
4. Repository layer
5. Login screen
6. Owner Dashboard
7. Transaction Form (CashIn/CashOut)
8. WebSocket real-time sync
9. Screenshot system
10. Employee view
11. License protection
12. .exe build

---

## Environment Setup

```bash
# Mac (development)
python3 -m venv venv
source venv/bin/activate
pip install pyqt6 fastapi uvicorn websockets mysql-connector-python python-dotenv

# Windows (production)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**.env**
```
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ngwe_lwe_db
DB_USER=root
DB_PASSWORD=
APP_SECRET=your_secret_key_here
```

---

## Git Convention

```bash
git commit -m "feat: add transaction form"
git commit -m "fix: balance calculation agent type"
git commit -m "chore: update requirements"
git commit -m "refactor: move db queries to repository"
```

---

## Claude Code Prompt Template

```
Context: Myanmar money transfer desktop app.
Stack: PyQt6 + FastAPI + WebSocket + MySQL
Pattern: MVVM + Repository + SOLID
Rules:
- View = display only, no logic
- ViewModel = UI state + business logic
- Repository = DB queries only, no business logic
- Functions under 20 lines
- No magic numbers
- Type hints always

Task: [ဒီနေရာမှာ task ထည့်]
```

---

## Services Supported

KPay · Wave Pay · KBZ Pay · OK Dollar · MPT Pay · True Money · One Pay · AYA Pay · CB Pay · Yoma Pay · City Express · KBZ Express · OK Express · Thai Bank