# Commission Tiers — Calculation Logic Report

**Date:** 2026-05-10  
**Scope:** Full calculation path for Deposit, Withdraw, Transfer, Exchange — frontend display + backend execution

---

## 1. How a Tier Is Selected

Every transaction type starts the same way: find the tier that matches the **source account's service type** and the **transaction amount**.

**File:** `repositories/commission_tier_repository.py` — `get_tier_for_amount()`

```
LOOKUP:  service_type_id = account.service_type_id
         is_active = 1
         amount_from <= transaction_amount <= amount_to
         LIMIT 1  (first match, insertion-order)
```

- The **service type comes from the account**, not chosen per transaction.
- If **no tier matches**, all fees and commission default to **0**.
- For **Transfer**, only the **from-account** service type is used. The to-account is ignored.

---

## 2. Shared Calculation Formula

Two charge types. Same formula applies to all transaction types:

```
FIXED      →  charge = raw_value
PERCENTAGE →  charge = round(amount × rate, 2)
```

The `rate` for PERCENTAGE tiers is stored as a decimal (e.g. `0.01` = 1%).

---

## 3. Deposit

**Files:** `viewmodels/transaction_viewmodel.py` lines 88–134, `views/transaction_view.py` lines 727–792

### Tier fields used

| Charge | Tier field | Type field |
|---|---|---|
| Commission (agent profit) | `comm_deposit` | `comm_type` |
| Customer fee | `fee_amount_deposit` | `fee_amount_type` |
| Additional fee | `additional_fee_deposit_amount` | `additional_fee_type` |

### Calculation

```
commission    = comm_deposit                         (FIXED)
              = round(amount × comm_deposit, 2)      (PERCENTAGE)

customer_fee  = fee_amount_deposit                   (FIXED)
              = round(amount × fee_amount_deposit, 2) (PERCENTAGE)

add_fee       = additional_fee_deposit_amount        (FIXED)
              = round(amount × additional_fee_deposit_amount, 2) (PERCENTAGE)

total_fee     = customer_fee + add_fee
```

### Balance changes

```
account.balance     += amount          (customer account increases)
fee_account.balance += total_fee       (if fee_account_id provided)
commission_amount    → stored in transaction record only (agent profit, no automatic credit)
```

### Example

Service type: Mobile Banking | Tier: 0–500,000 MMK | `comm_type=PERCENTAGE`, `comm_deposit=0.01` | `fee_amount_type=FIXED`, `fee_amount_deposit=2,000` | `additional_fee_type=FIXED`, `additional_fee_deposit_amount=0`

Amount = 100,000 MMK:
```
commission   = round(100,000 × 0.01, 2) = 1,000 MMK
customer_fee = 2,000 MMK
add_fee      = 0
total_fee    = 2,000 MMK
account balance +100,000
fee account   +2,000
```

---

## 4. Withdraw

**Files:** `viewmodels/transaction_viewmodel.py` lines 136–219, `views/transaction_view.py` lines 727–792

### Tier fields used

| Charge | Tier field | Type field |
|---|---|---|
| Commission (agent profit) | `comm_withdraw` | `comm_type` |
| Customer fee | `fee_amount_withdraw` | `fee_amount_type` |
| Additional fee | `additional_fee_withdraw_amount` | `additional_fee_type` |

### Calculation

```
commission    = comm_withdraw                          (FIXED)
              = round(amount × comm_withdraw, 2)       (PERCENTAGE)

customer_fee  = fee_amount_withdraw                    (FIXED)
              = round(amount × fee_amount_withdraw, 2) (PERCENTAGE)

add_fee       = additional_fee_withdraw_amount         (FIXED)
              = round(amount × additional_fee_withdraw_amount, 2) (PERCENTAGE)

total_fee     = customer_fee + add_fee
```

### Balance changes

```
account.balance     -= amount          (customer account decreases)
fee_account.balance += total_fee       (if fee_account_id provided)
employee float      -= amount          (if employee processes the cash-out)
commission_amount    → stored in transaction record only
```

### Example

Same service type | `comm_withdraw=0.005` (0.5%) | `fee_amount_withdraw=1,500` FIXED | `additional_fee_withdraw=0`

Amount = 200,000 MMK:
```
commission   = round(200,000 × 0.005, 2) = 1,000 MMK
customer_fee = 1,500 MMK
add_fee      = 0
total_fee    = 1,500 MMK
account balance -200,000
fee account     +1,500
employee float  -200,000
```

---

## 5. Transfer

**Files:** `viewmodels/transaction_viewmodel.py` lines 221–309, `views/transaction_view.py` lines 727–792

### Tier fields used

Transfer treats the **sending side as a "deposit/send"** operation — it uses the **deposit** tier fields, not the withdraw fields.  
Only the **from-account's service type** is used for lookup.

| Charge | Tier field | Type field |
|---|---|---|
| Commission (agent profit) | `comm_deposit` | `comm_type` |
| Customer fee | `fee_amount_deposit` | `fee_amount_type` |
| Additional fee | `additional_fee_deposit_amount` | `additional_fee_type` |

### Calculation

```
commission    = comm_deposit                         (FIXED)
              = round(amount × comm_deposit, 2)      (PERCENTAGE)

customer_fee  = fee_amount_deposit                   (FIXED)
              = round(amount × fee_amount_deposit, 2) (PERCENTAGE)

add_fee       = additional_fee_deposit_amount        (FIXED)
              = round(amount × additional_fee_deposit_amount, 2) (PERCENTAGE)

total_fee     = customer_fee + add_fee
```

### Balance changes

```
from_account.balance -= amount    (sender decreases)
to_account.balance   += amount    (receiver increases — full amount, no fee deducted)
fee_account.balance  += total_fee (if fee_account_id provided)
commission_amount     → stored in transaction record only
```

> **Note:** The receiver gets the full `amount`. Customer fee is charged to the sender separately, not deducted from the transferred amount.

### Example

From-account service type: Remittance | `comm_deposit=500` FIXED | `fee_amount_deposit=0.002` PERCENTAGE (0.2%)

Amount = 300,000 MMK:
```
commission   = 500 MMK
customer_fee = round(300,000 × 0.002, 2) = 600 MMK
add_fee      = 0
total_fee    = 600 MMK
from_account -300,000
to_account   +300,000
fee account  +600
```

---

## 6. Exchange

**Files:** `viewmodels/transaction_viewmodel.py` lines 311–402, `views/transaction_view.py` lines 727–792

### Tier fields used

Exchange also uses the **deposit** tier fields (same as transfer — treated as "send").

| Charge | Tier field | Type field |
|---|---|---|
| Commission (agent profit) | `comm_deposit` | `comm_type` |
| Customer fee | `fee_amount_deposit` | `fee_amount_type` |
| Additional fee | `additional_fee_deposit_amount` | `additional_fee_type` |

### Exchange rate resolution

```python
# Backend: viewmodels/transaction_viewmodel.py lines 327-335
if currency == "MMK":
    exchange_rate = sell_rate / base_amount   # Customer sells foreign, gets MMK
else:
    exchange_rate = buy_rate  / base_amount   # Customer buys foreign, gives MMK
```

The `exchange_rate` is stored in the transaction record. The `amount` field stores the **MMK equivalent** value (after conversion). Commission and fees are calculated on the **MMK amount**.

### Calculation

```
commission    = comm_deposit                         (FIXED)
              = round(amount × comm_deposit, 2)      (PERCENTAGE)

customer_fee  = fee_amount_deposit                   (FIXED)
              = round(amount × fee_amount_deposit, 2) (PERCENTAGE)

add_fee       = additional_fee_deposit_amount        (FIXED)
              = round(amount × additional_fee_deposit_amount, 2) (PERCENTAGE)

total_fee     = customer_fee + add_fee
```

### Balance changes

```
account.balance     += amount          (account increases by MMK amount)
fee_account.balance += total_fee       (if fee_account_id provided)
commission_amount    → stored in transaction record only
```

---

## 7. Summary: Which Tier Fields Each Transaction Type Uses

| | Deposit | Withdraw | Transfer | Exchange |
|---|---|---|---|---|
| **Lookup: service type from** | Source account | Source account | From-account only | Source account |
| **Commission field** | `comm_deposit` | `comm_withdraw` | `comm_deposit` | `comm_deposit` |
| **Commission type** | `comm_type` | `comm_type` | `comm_type` | `comm_type` |
| **Customer fee field** | `fee_amount_deposit` | `fee_amount_withdraw` | `fee_amount_deposit` | `fee_amount_deposit` |
| **Fee type** | `fee_amount_type` | `fee_amount_type` | `fee_amount_type` | `fee_amount_type` |
| **Add. fee field** | `additional_fee_deposit_amount` | `additional_fee_withdraw_amount` | `additional_fee_deposit_amount` | `additional_fee_deposit_amount` |
| **Add. fee type** | `additional_fee_type` | `additional_fee_type` | `additional_fee_type` | `additional_fee_type` |
| **Source balance** | +amount | −amount | −amount | +amount |
| **Destination balance** | — | — | +amount | — |
| **Employee float** | unchanged | −amount | −amount (if employee) | −amount (if employee) |

---

## 8. Where Commission Goes vs Where Fees Go

| | Commission | Customer Fee + Additional Fee |
|---|---|---|
| **Calculated on** | Transaction amount | Transaction amount |
| **Who pays** | — (agent keeps it) | Customer |
| **Credited to** | Nowhere automatically — stored in `transactions.commission_amount` for reporting | `fee_account` if `fee_account_id` is provided |
| **Effect on customer balance** | None | None (fee is separate from amount) |
| **Included in balance_change** | No | No |

---

## 9. Frontend vs Backend Calculation

The frontend calculates in real time as the user types (display only). The backend recalculates independently when the transaction is submitted. **No calculated values are sent from frontend to backend** — the backend queries the tier repo fresh.

| | Frontend (`views/transaction_view.py`) | Backend (`viewmodels/transaction_viewmodel.py`) |
|---|---|---|
| **Tier lookup** | `GET /commission-tiers/lookup` (API call) | `tier_repo.get_tier_for_amount()` (direct DB) |
| **Purpose** | Display only (live preview) | Actual calculation stored in DB |
| **Commission source** | `tier["comm_deposit"]` or `tier["comm_withdraw"]` | `tier.comm_deposit` or `tier.comm_withdraw` |
| **Rounding** | `round(amount × rate, 2)` | `round(amount × rate, 2)` |
| **Display precision** | `f"{value:,.0f}"` (0 decimals shown) | Stored as REAL (full precision) |

---

## 10. Known Issues

| # | Issue | Impact |
|---|---|---|
| 1 | `LIMIT 1` with no `ORDER BY` in tier lookup | Non-deterministic result if two tiers overlap |
| 2 | Transfer uses `comm_deposit` not a dedicated `comm_transfer` field | Cannot set different commission rates for transfer vs deposit |
| 3 | Exchange uses `comm_deposit` — cannot differentiate exchange commission from deposit | Same as above for exchange |
| 4 | Commission is never automatically credited to any account | Agent profit must be tracked manually via reports |
| 5 | If `fee_account_id` is NULL, total_fee is collected from customer but credited nowhere | Silent data loss |
| 6 | Frontend PERCENTAGE rate treated as decimal (0.01 = 1%) — no UI hint confirming this to the admin | Misconfiguration risk when adding tiers |
