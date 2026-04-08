-- Ngwe Lwe System — SQLite Schema

-- ============================================================
-- 0. schema_version (must be first)
-- ============================================================
CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);

-- ============================================================
-- 1. users
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    pin_hash      TEXT,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'employee' CHECK(role IN ('owner','employee','cashier')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
AFTER UPDATE ON users FOR EACH ROW
BEGIN UPDATE users SET updated_at = datetime('now') WHERE id = NEW.id; END;

-- ============================================================
-- 2. services
-- ============================================================
CREATE TABLE IF NOT EXISTS services (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT NOT NULL UNIQUE,
    service_type         TEXT NOT NULL,
    default_customer_fee REAL NOT NULL DEFAULT 0.00,
    is_active            INTEGER NOT NULL DEFAULT 1,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER IF NOT EXISTS trg_services_updated_at
AFTER UPDATE ON services FOR EACH ROW
BEGIN UPDATE services SET updated_at = datetime('now') WHERE id = NEW.id; END;

-- ============================================================
-- 3. accounts
-- ============================================================
CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id      INTEGER NOT NULL,
    account_name    TEXT NOT NULL,
    account_type    TEXT NOT NULL DEFAULT 'personal' CHECK(account_type IN ('personal','agent')),
    phone_number    TEXT NOT NULL,
    service_type    TEXT NOT NULL DEFAULT 'KPAY' CHECK(service_type IN ('KPAY','WAVE','BANK')),
    balance         REAL NOT NULL DEFAULT 0.00,
    commission_rate REAL NOT NULL DEFAULT 0.0000,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (service_id, phone_number),
    FOREIGN KEY (service_id) REFERENCES services(id) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE TRIGGER IF NOT EXISTS trg_accounts_updated_at
AFTER UPDATE ON accounts FOR EACH ROW
BEGIN UPDATE accounts SET updated_at = datetime('now') WHERE id = NEW.id; END;

-- ============================================================
-- 4. transactions
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_type    TEXT NOT NULL CHECK(transaction_type IN ('deposit','withdraw','transfer','exchange')),
    account_id          INTEGER NOT NULL,
    to_account_id       INTEGER,
    customer_name       TEXT,
    customer_phone      TEXT,
    amount              REAL NOT NULL,
    commission_amount   REAL NOT NULL DEFAULT 0.00,
    customer_fee        REAL NOT NULL DEFAULT 0.00,
    additional_fee_amount REAL NOT NULL DEFAULT 0.00,
    balance_change      REAL NOT NULL DEFAULT 0.00,
    currency            TEXT NOT NULL DEFAULT 'MMK',
    exchange_rate       REAL,
    fee_account_id      INTEGER,
    screenshot_path     TEXT,
    note                TEXT,
    created_by          INTEGER NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (account_id)    REFERENCES accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (to_account_id) REFERENCES accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (fee_account_id)REFERENCES accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (created_by)    REFERENCES users(id)    ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_txn_type       ON transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_txn_created    ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_txn_created_by ON transactions(created_by);

-- ============================================================
-- 5. commission_tiers
-- base=THB, quote=MMK; rates expressed as MMK per base_amount THB
-- PERCENTAGE values stored as decimals (e.g. 0.03 = 3%)
-- ============================================================
CREATE TABLE IF NOT EXISTS commission_tiers (
    id                             INTEGER PRIMARY KEY AUTOINCREMENT,
    service_type                   TEXT NOT NULL,
    account_type                   TEXT CHECK(account_type IN ('personal','agent')),
    amount_from                    REAL,
    amount_to                      REAL,
    fee_amount_type                TEXT NOT NULL DEFAULT 'FIXED' CHECK(fee_amount_type IN ('FIXED','PERCENTAGE')),
    fee_amount_deposit             REAL NOT NULL DEFAULT 0.0,
    fee_amount_withdraw            REAL NOT NULL DEFAULT 0.0,
    comm_type                      TEXT NOT NULL DEFAULT 'FIXED' CHECK(comm_type IN ('FIXED','PERCENTAGE')),
    comm_deposit                   REAL NOT NULL DEFAULT 0.0,
    comm_withdraw                  REAL NOT NULL DEFAULT 0.0,
    additional_fee_type            TEXT NOT NULL DEFAULT 'FIXED' CHECK(additional_fee_type IN ('FIXED','PERCENTAGE')),
    additional_fee_deposit_amount  REAL NOT NULL DEFAULT 0.0,
    additional_fee_withdraw_amount REAL NOT NULL DEFAULT 0.0,
    is_active                      INTEGER NOT NULL DEFAULT 1,
    created_at                     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tier_lookup ON commission_tiers(service_type, is_active);

-- ============================================================
-- 6. exchange_rates
-- base_amount: reference quantity of base currency
-- MMK→THB: THB = MMK * base_amount / sell_rate
-- THB→MMK: MMK = THB * buy_rate  / base_amount
-- ============================================================
CREATE TABLE IF NOT EXISTS exchange_rates (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    base_currency  TEXT NOT NULL DEFAULT 'THB',
    quote_currency TEXT NOT NULL DEFAULT 'MMK',
    base_amount    REAL NOT NULL DEFAULT 1.00,
    buy_rate       REAL NOT NULL,
    sell_rate      REAL NOT NULL,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER IF NOT EXISTS trg_exchange_rates_updated_at
AFTER UPDATE ON exchange_rates FOR EACH ROW
BEGIN UPDATE exchange_rates SET updated_at = datetime('now') WHERE id = NEW.id; END;
CREATE INDEX IF NOT EXISTS idx_rate_pair    ON exchange_rates(base_currency, quote_currency);
CREATE INDEX IF NOT EXISTS idx_rate_updated ON exchange_rates(updated_at);

-- ============================================================
-- 7. daily_summary
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_summary (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_date       TEXT NOT NULL UNIQUE,
    total_deposit      REAL NOT NULL DEFAULT 0.00,
    total_withdraw     REAL NOT NULL DEFAULT 0.00,
    total_transfer     REAL NOT NULL DEFAULT 0.00,
    total_exchange     REAL NOT NULL DEFAULT 0.00,
    total_commission   REAL NOT NULL DEFAULT 0.00,
    total_customer_fees REAL NOT NULL DEFAULT 0.00,
    total_profit       REAL NOT NULL DEFAULT 0.00,
    transaction_count  INTEGER NOT NULL DEFAULT 0,
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_summary_date ON daily_summary(summary_date);

-- ============================================================
-- 8. activity_logs
-- ============================================================
CREATE TABLE IF NOT EXISTS activity_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    action      TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id   INTEGER,
    details     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_log_user    ON activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_log_created ON activity_logs(created_at);

-- ============================================================
-- 9. cash_float_assignments
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_float_assignments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id  INTEGER NOT NULL,
    issued_by    INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','ACTIVE','CLOSED')),
    total_amount REAL NOT NULL DEFAULT 0.00,
    received_at  TEXT,
    closed_at    TEXT,
    closing_total REAL,
    note         TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (issued_by)   REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_float_employee ON cash_float_assignments(employee_id, status);

-- ============================================================
-- 10. cash_denomination_logs
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_denomination_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_type   TEXT NOT NULL CHECK(entry_type IN ('vault_in','vault_out','float_returned','adjustment')),
    denomination INTEGER NOT NULL CHECK(denomination IN (50,100,200,500,1000,5000,10000)),
    quantity     INTEGER NOT NULL,
    float_id     INTEGER,
    created_by   INTEGER NOT NULL,
    note         TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (float_id)   REFERENCES cash_float_assignments(id) ON UPDATE CASCADE ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_denom_log_created ON cash_denomination_logs(created_at);

-- ============================================================
-- 11. cash_float_denominations
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_float_denominations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    float_id     INTEGER NOT NULL,
    denomination INTEGER NOT NULL CHECK(denomination IN (50,100,200,500,1000,5000,10000)),
    quantity     INTEGER NOT NULL,
    FOREIGN KEY (float_id) REFERENCES cash_float_assignments(id) ON UPDATE CASCADE ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_float_denom_float ON cash_float_denominations(float_id);

-- ============================================================
-- SEED DATA
-- ============================================================

-- schema_version seed (fresh install = already at version 2)
INSERT OR IGNORE INTO schema_version (version, description) VALUES
(1, 'Add cashier role and pin_hash'),
(2, 'Create cash management tables');

-- Users  (password: admin123 — bcrypt, cost 12)
INSERT OR IGNORE INTO users (username, password_hash, full_name, role) VALUES
('owner',     '$2b$12$VttoZ/owwiQaf0WcW0lf0ujKgdjuN4hesATsSjhI/h7c0IsOFkSSe', 'Hnin Oo Wai Lwin', 'owner'),
('employee1', '$2b$12$VttoZ/owwiQaf0WcW0lf0ujKgdjuN4hesATsSjhI/h7c0IsOFkSSe', 'Aung Aung',        'employee'),
('employee2', '$2b$12$VttoZ/owwiQaf0WcW0lf0ujKgdjuN4hesATsSjhI/h7c0IsOFkSSe', 'Mya Mya',          'employee');

-- Services
INSERT OR IGNORE INTO services (name, service_type, default_customer_fee) VALUES
('KBZ Pay',      'mobile_wallet', 0),
('Wave Pay',     'mobile_wallet', 0),
('KBZ Bank',     'bank',          0),
('AYA Bank',     'bank',          0),
('CB Bank',      'bank',          0),
('MPT Pay',      'mobile_wallet', 0),
('OK Dollar',    'mobile_wallet', 0),
('True Money',   'mobile_wallet', 0),
('One Pay',      'mobile_wallet', 0),
('AYA Pay',      'mobile_wallet', 0),
('Yoma Pay',     'mobile_wallet', 0),
('City Express', 'express',       0),
('KBZ Express',  'express',       0),
('Thai Bank',    'bank',          0);

-- Accounts (KBZ Pay — service_id=1)
INSERT OR IGNORE INTO accounts (service_id, account_name, account_type, phone_number, service_type, balance) VALUES
(1, 'KPay Main',     'agent',    '09-987-654-321', 'KPAY', 5000000.00),
(1, 'KPay Personal', 'personal', '09-111-222-333', 'KPAY', 1200000.00);

-- Accounts (Wave Pay — service_id=2)
INSERT OR IGNORE INTO accounts (service_id, account_name, account_type, phone_number, service_type, balance) VALUES
(2, 'Wave Agent',    'agent',    '09-876-543-210', 'WAVE', 3500000.00),
(2, 'Wave Personal', 'personal', '09-444-555-666', 'WAVE',  800000.00);

-- Accounts (Banks)
INSERT OR IGNORE INTO accounts (service_id, account_name, account_type, phone_number, service_type, balance) VALUES
(3, 'KBZ Saving',  'personal', '01234567890', 'BANK', 10000000.00),
(4, 'AYA Current', 'personal', '09876543210', 'BANK',  7500000.00),
(5, 'CB Saving',   'personal', '05678901234', 'BANK',  2000000.00);

-- Accounts (Others)
INSERT OR IGNORE INTO accounts (service_id, account_name, account_type, phone_number, service_type, balance) VALUES
(6, 'MPT Agent',       'agent', '09-777-888-999', 'KPAY', 1500000.00),
(7, 'OK Dollar Agent', 'agent', '09-333-444-555', 'KPAY',  900000.00);

-- Exchange rate  (1 THB = 128.21 MMK)
INSERT OR IGNORE INTO exchange_rates (base_currency, quote_currency, base_amount, buy_rate, sell_rate) VALUES
('THB', 'MMK', 1.00, 128.2100, 128.2100);

-- Commission tiers — WAVE_WST agent
INSERT OR IGNORE INTO commission_tiers (service_type, account_type, amount_from, amount_to, fee_amount_type, fee_amount_deposit, fee_amount_withdraw, comm_type, comm_deposit, comm_withdraw, additional_fee_type, additional_fee_deposit_amount, additional_fee_withdraw_amount) VALUES
('WAVE_WST','agent',1,10000,'FIXED',400,0,'FIXED',69,88,'FIXED',0,0),
('WAVE_WST','agent',10001,25000,'FIXED',700,0,'FIXED',123,172,'FIXED',0,0),
('WAVE_WST','agent',25001,50000,'FIXED',1000,0,'FIXED',147,245,'FIXED',0,0),
('WAVE_WST','agent',50001,100000,'FIXED',1500,0,'FIXED',196,392,'FIXED',0,0),
('WAVE_WST','agent',100001,150000,'FIXED',2000,0,'FIXED',294,490,'FIXED',0,0),
('WAVE_WST','agent',150001,200000,'FIXED',2500,0,'FIXED',392,588,'FIXED',0,0),
('WAVE_WST','agent',200001,300000,'FIXED',3000,0,'FIXED',490,686,'FIXED',0,0),
('WAVE_WST','agent',300001,400000,'FIXED',4000,0,'FIXED',653,915,'FIXED',0,0),
('WAVE_WST','agent',400001,500000,'FIXED',4500,0,'FIXED',735,1029,'FIXED',0,0),
('WAVE_WST','agent',500001,600000,'FIXED',5400,0,'FIXED',882,1235,'FIXED',0,0),
('WAVE_WST','agent',600001,700000,'FIXED',6000,0,'FIXED',980,1372,'FIXED',0,0),
('WAVE_WST','agent',700001,800000,'FIXED',6700,0,'FIXED',1094,1532,'FIXED',0,0),
('WAVE_WST','agent',800001,900000,'FIXED',7400,0,'FIXED',1209,1692,'FIXED',0,0),
('WAVE_WST','agent',900001,1000000,'FIXED',8000,0,'FIXED',1307,1829,'FIXED',0,0);

-- Commission tiers — WAVE_ACCOUNT
INSERT OR IGNORE INTO commission_tiers (service_type, account_type, amount_from, amount_to, fee_amount_type, fee_amount_deposit, fee_amount_withdraw, comm_type, comm_deposit, comm_withdraw, additional_fee_type, additional_fee_deposit_amount, additional_fee_withdraw_amount) VALUES
('WAVE_ACCOUNT',NULL,0,30000,'FIXED',300,0,'FIXED',300,0,'FIXED',0,0),
('WAVE_ACCOUNT',NULL,30000,50000,'FIXED',500,0,'FIXED',500,0,'FIXED',0,0),
('WAVE_ACCOUNT',NULL,50000,70000,'FIXED',700,0,'FIXED',700,0,'FIXED',0,0),
('WAVE_ACCOUNT',NULL,70000,90000,'FIXED',1100,0,'FIXED',1100,0,'FIXED',0,0),
('WAVE_ACCOUNT',NULL,90000,100000,'FIXED',1400,0,'FIXED',1400,0,'FIXED',0,0),
('WAVE_ACCOUNT',NULL,100000,200000,'FIXED',1700,0,'FIXED',1700,0,'FIXED',0,0),
('WAVE_ACCOUNT',NULL,NULL,NULL,'PERCENTAGE',0.03,0,'PERCENTAGE',0.03,0,'FIXED',0,0);

-- Commission tiers — KPAY_WST agent
INSERT OR IGNORE INTO commission_tiers (service_type, account_type, amount_from, amount_to, fee_amount_type, fee_amount_deposit, fee_amount_withdraw, comm_type, comm_deposit, comm_withdraw, additional_fee_type, additional_fee_deposit_amount, additional_fee_withdraw_amount) VALUES
('KPAY_WST','agent',1,10000,'FIXED',400,0,'FIXED',80,80,'FIXED',0,0),
('KPAY_WST','agent',10001,25000,'FIXED',700,0,'FIXED',140,140,'FIXED',0,0),
('KPAY_WST','agent',25001,50000,'FIXED',1000,0,'FIXED',200,200,'FIXED',0,0),
('KPAY_WST','agent',50001,100000,'FIXED',1500,0,'FIXED',300,300,'FIXED',0,0),
('KPAY_WST','agent',100001,150000,'FIXED',2000,0,'FIXED',400,400,'FIXED',0,0),
('KPAY_WST','agent',150001,200000,'FIXED',2500,0,'FIXED',500,500,'FIXED',0,0),
('KPAY_WST','agent',200001,300000,'FIXED',3000,0,'FIXED',600,600,'FIXED',0,0),
('KPAY_WST','agent',300001,400000,'FIXED',4000,0,'FIXED',800,800,'FIXED',0,0),
('KPAY_WST','agent',400001,500000,'FIXED',4500,0,'FIXED',900,900,'FIXED',0,0),
('KPAY_WST','agent',500001,600000,'FIXED',5200,0,'FIXED',1040,1040,'FIXED',0,0),
('KPAY_WST','agent',600001,700000,'FIXED',5800,0,'FIXED',1160,1160,'FIXED',0,0),
('KPAY_WST','agent',700001,800000,'FIXED',6500,0,'FIXED',1300,1300,'FIXED',0,0),
('KPAY_WST','agent',800001,900000,'FIXED',7200,0,'FIXED',1440,1440,'FIXED',0,0),
('KPAY_WST','agent',900001,1000000,'FIXED',7800,0,'FIXED',1560,1560,'FIXED',0,0);

-- Activity logs
INSERT OR IGNORE INTO activity_logs (user_id, action, entity_type, entity_id, details) VALUES
(1, 'login',  'user', 1, 'Owner logged in'),
(2, 'login',  'user', 2, 'Employee logged in'),
(3, 'login',  'user', 3, 'Employee logged in'),
(1, 'update', 'exchange_rate', 1, 'Updated MMK/THB rate');
