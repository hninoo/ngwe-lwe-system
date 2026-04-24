# 📊 Ngwe Lwe System — Tables (Markdown)

## schema_version

| Column      | Type         | Description       |
| ----------- | ------------ | ----------------- |
| version     | INTEGER (PK) | Schema version    |
| applied_at  | TEXT         | Applied timestamp |
| description | TEXT         | Description       |

## users

| Column        | Type          | Description                |
| ------------- | ------------- | -------------------------- |
| id            | INTEGER (PK)  | User ID                    |
| username      | TEXT (UNIQUE) | Username                   |
| password_hash | TEXT          | Password hash              |
| pin_hash      | TEXT          | PIN hash                   |
| full_name     | TEXT          | Full name                  |
| role          | TEXT          | owner / employee / cashier |
| is_active     | INTEGER       | Active (1/0)               |
| created_at    | TEXT          | Created                    |
| updated_at    | TEXT          | Updated                    |

## companies

| Column     | Type          | Description                              |
| ---------- | ------------- | ---------------------------------------- |
| id         | INTEGER (PK)  | Company ID                               |
| name       | TEXT (UNIQUE) | Name                                     |
| logo_path  | TEXT          | Logo                                     |
| category   | TEXT          | DEPOSIT / WITHDRAW / TRANSFER / EXCHANGE |
| is_active  | INTEGER       | Active                                   |
| created_at | TEXT          | Created                                  |
| updated_at | TEXT          | Updated                                  |

## service_types

| Column     | Type         | Description      |
| ---------- | ------------ | ---------------- |
| id         | INTEGER (PK) | Service ID       |
| company_id | INTEGER (FK) | Company          |
| name       | TEXT         | WST / Pay_To_Pay |
| is_active  | INTEGER      | Active           |
| created_at | TEXT         | Created          |
| updated_at | TEXT         | Updated          |

## accounts

| Column          | Type         | Description |
| --------------- | ------------ | ----------- |
| id              | INTEGER (PK) | Account ID  |
| service_type_id | INTEGER (FK) | Service     |
| account_name    | TEXT         | Name        |
| phone_number    | TEXT         | Phone       |
| balance         | REAL         | Balance     |
| is_active       | INTEGER      | Active      |
| created_at      | TEXT         | Created     |
| updated_at      | TEXT         | Updated     |

## transactions

| Column                | Type         | Description                              |
| --------------------- | ------------ | ---------------------------------------- |
| id                    | INTEGER (PK) | Transaction ID                           |
| transaction_type      | TEXT         | deposit / withdraw / transfer / exchange |
| account_id            | INTEGER (FK) | From account                             |
| to_account_id         | INTEGER (FK) | To account                               |
| from_company_id       | INTEGER (FK) | From company                             |
| to_company_id         | INTEGER (FK) | To company                               |
| customer_name         | TEXT         | Customer                                 |
| customer_phone        | TEXT         | Phone                                    |
| amount                | REAL         | Amount                                   |
| commission_amount     | REAL         | Commission                               |
| customer_fee          | REAL         | Fee                                      |
| additional_fee_amount | REAL         | Extra fee                                |
| balance_change        | REAL         | Balance change                           |
| currency              | TEXT         | Currency                                 |
| exchange_rate         | REAL         | Rate                                     |
| fee_account_id        | INTEGER (FK) | Fee account                              |
| screenshot_path       | TEXT         | Screenshot                               |
| note                  | TEXT         | Note                                     |
| created_by            | INTEGER (FK) | User                                     |
| created_at            | TEXT         | Created                                  |
| cash_approved_by      | INTEGER (FK) | Approved by                              |
| cash_approved_at      | TEXT         | Approved time                            |

## commission_tiers

| Column                         | Type         | Description         |
| ------------------------------ | ------------ | ------------------- |
| id                             | INTEGER (PK) | Tier ID             |
| service_type_id                | INTEGER (FK) | Service             |
| amount_from                    | REAL         | Min                 |
| amount_to                      | REAL         | Max                 |
| fee_amount_type                | TEXT         | FIXED / PERCENTAGE  |
| fee_amount_deposit             | REAL         | Deposit fee         |
| fee_amount_withdraw            | REAL         | Withdraw fee        |
| comm_type                      | TEXT         | FIXED / PERCENTAGE  |
| comm_deposit                   | REAL         | Deposit commission  |
| comm_withdraw                  | REAL         | Withdraw commission |
| additional_fee_type            | TEXT         | FIXED / PERCENTAGE  |
| additional_fee_deposit_amount  | REAL         | Extra deposit fee   |
| additional_fee_withdraw_amount | REAL         | Extra withdraw fee  |
| is_active                      | INTEGER      | Active              |
| created_at                     | TEXT         | Created             |

> Note: fee and commission fields can store values like 0.01, 0.02, 0.03, etc.

## exchange_rates

| Column         | Type         | Description |
| -------------- | ------------ | ----------- |
| id             | INTEGER (PK) | Rate ID     |
| base_currency  | TEXT         | Base        |
| quote_currency | TEXT         | Quote       |
| base_amount    | REAL         | Base amount |
| buy_rate       | REAL         | Buy rate    |
| sell_rate      | REAL         | Sell rate   |
| updated_at     | TEXT         | Updated     |
| created_at     | TEXT         | Created     |

## daily_summary

| Column              | Type         | Description |
| ------------------- | ------------ | ----------- |
| id                  | INTEGER (PK) | ID          |
| summary_date        | TEXT         | Date        |
| total_deposit       | REAL         | Deposit     |
| total_withdraw      | REAL         | Withdraw    |
| total_transfer      | REAL         | Transfer    |
| total_exchange      | REAL         | Exchange    |
| total_commission    | REAL         | Commission  |
| total_customer_fees | REAL         | Fees        |
| total_profit        | REAL         | Profit      |
| transaction_count   | INTEGER      | Count       |
| created_at          | TEXT         | Created     |

## activity_logs

| Column      | Type         | Description |
| ----------- | ------------ | ----------- |
| id          | INTEGER (PK) | Log ID      |
| user_id     | INTEGER (FK) | User        |
| action      | TEXT         | Action      |
| entity_type | TEXT         | Table       |
| entity_id   | INTEGER      | Entity ID   |
| details     | TEXT         | Details     |
| created_at  | TEXT         | Created     |

## cash_float_assignments

| Column        | Type         | Description               |
| ------------- | ------------ | ------------------------- |
| id            | INTEGER (PK) | Float ID                  |
| employee_id   | INTEGER (FK) | Employee                  |
| issued_by     | INTEGER (FK) | Issuer                    |
| status        | TEXT         | PENDING / ACTIVE / CLOSED |
| total_amount  | REAL         | Total                     |
| received_at   | TEXT         | Received                  |
| closed_at     | TEXT         | Closed                    |
| closing_total | REAL         | Final                     |
| note          | TEXT         | Note                      |
| created_at    | TEXT         | Created                   |

## cash_denomination_logs

| Column       | Type         | Description                                        |
| ------------ | ------------ | -------------------------------------------------- |
| id           | INTEGER (PK) | Log ID                                             |
| entry_type   | TEXT         | vault_in / vault_out / float_returned / adjustment |
| denomination | INTEGER      | Note value                                         |
| quantity     | INTEGER      | Quantity                                           |
| float_id     | INTEGER (FK) | Float                                              |
| created_by   | INTEGER (FK) | User                                               |
| note         | TEXT         | Note                                               |
| created_at   | TEXT         | Created                                            |

## cash_float_denominations

| Column       | Type         | Description |
| ------------ | ------------ | ----------- |
| id           | INTEGER (PK) | ID          |
| float_id     | INTEGER (FK) | Float       |
| denomination | INTEGER      | Note        |
| quantity     | INTEGER      | Quantity    |