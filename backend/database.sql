-- Ngwe Lwe — SQLite Schema (v4)

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
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    auth_version  INTEGER NOT NULL DEFAULT 0
);
CREATE TRIGGER IF NOT EXISTS trg_users_updated_at
AFTER UPDATE ON users FOR EACH ROW
BEGIN UPDATE users SET updated_at = datetime('now') WHERE id = NEW.id; END;

-- ============================================================
-- 2. companies
-- ============================================================
CREATE TABLE IF NOT EXISTS companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    logo_path   TEXT,
    category    TEXT NOT NULL DEFAULT 'Pay'
                CHECK(category IN ('Pay','Bank','Both')),
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TRIGGER IF NOT EXISTS trg_companies_updated_at
AFTER UPDATE ON companies FOR EACH ROW
BEGIN UPDATE companies SET updated_at = datetime('now') WHERE id = NEW.id; END;

-- ============================================================
-- 3. service_types
-- ============================================================
CREATE TABLE IF NOT EXISTS service_types (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id  INTEGER NOT NULL,
    name        TEXT NOT NULL,
    operation   TEXT NOT NULL
                CHECK(operation IN ('CashIn','CashOut','Transfer','Exchange','All')),
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(company_id, name),
    FOREIGN KEY (company_id) REFERENCES companies(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE TRIGGER IF NOT EXISTS trg_service_types_updated_at
AFTER UPDATE ON service_types FOR EACH ROW
BEGIN UPDATE service_types SET updated_at = datetime('now') WHERE id = NEW.id; END;

-- ============================================================
-- 4. accounts
-- ============================================================
CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    service_type_id INTEGER NOT NULL,
    account_name    TEXT NOT NULL,
    phone_number    TEXT NOT NULL,
    balance         REAL NOT NULL DEFAULT 0.00,
    commission_rate REAL NOT NULL DEFAULT 0.0000,
    is_active       INTEGER NOT NULL DEFAULT 1,
    is_fee_account  INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (service_type_id) REFERENCES service_types(id) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE TRIGGER IF NOT EXISTS trg_accounts_updated_at
AFTER UPDATE ON accounts FOR EACH ROW
BEGIN UPDATE accounts SET updated_at = datetime('now') WHERE id = NEW.id; END;
CREATE INDEX IF NOT EXISTS idx_accounts_service_type_id ON accounts(service_type_id);

-- ============================================================
-- 5. transactions
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_type    TEXT NOT NULL CHECK(transaction_type IN ('cash_in','cash_out','transfer','exchange')),
    account_id          INTEGER NOT NULL,
    to_account_id       INTEGER,
    from_company_id     INTEGER,
    to_company_id       INTEGER,
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
    cash_approved_by    INTEGER,
    cash_approved_at    TEXT,
    status              TEXT NOT NULL DEFAULT 'COMPLETED'
                        CHECK(status IN ('PENDING_CASHIER_CONFIRM','COMPLETED','CANCELLED')),
    vault_impact        TEXT
                        CHECK(vault_impact IN ('mini_vault_decrease','main_vault_increase','none')),
    confirmed_by        INTEGER,
    confirmed_at        TEXT,
    change_given        REAL NOT NULL DEFAULT 0,
    change_denominations TEXT,
    FOREIGN KEY (account_id)      REFERENCES accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (to_account_id)   REFERENCES accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (fee_account_id)  REFERENCES accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (created_by)      REFERENCES users(id)    ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (from_company_id) REFERENCES companies(id),
    FOREIGN KEY (to_company_id)   REFERENCES companies(id)
);
CREATE INDEX IF NOT EXISTS idx_txn_type       ON transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_txn_created    ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_txn_created_by ON transactions(created_by);
CREATE INDEX IF NOT EXISTS idx_pending_cash_ins ON transactions(status)
    WHERE status = 'PENDING_CASHIER_CONFIRM';

-- ============================================================
-- 6. commission_tiers
-- ============================================================
CREATE TABLE IF NOT EXISTS commission_tiers (
    id                             INTEGER PRIMARY KEY AUTOINCREMENT,
    service_type_id                INTEGER NOT NULL,
    amount_from                    REAL NOT NULL,
    amount_to                      REAL NOT NULL,
    fee_amount_type                TEXT NOT NULL DEFAULT 'FIXED' CHECK(fee_amount_type IN ('FIXED','PERCENTAGE')),
    fee_amount_deposit             REAL NOT NULL DEFAULT 0.0,
    fee_amount_withdraw            REAL NOT NULL DEFAULT 0.0,
    comm_type                      TEXT DEFAULT 'FIXED' CHECK(comm_type IN ('FIXED','PERCENTAGE')),
    comm_deposit                   REAL DEFAULT 0.0,
    comm_withdraw                  REAL DEFAULT 0.0,
    additional_fee_type            TEXT DEFAULT 'FIXED' CHECK(additional_fee_type IN ('FIXED','PERCENTAGE')),
    additional_fee_deposit_amount  REAL DEFAULT 0.0,
    additional_fee_withdraw_amount REAL DEFAULT 0.0,
    is_active                      INTEGER NOT NULL DEFAULT 1,
    created_at                     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (service_type_id) REFERENCES service_types(id) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_tier_lookup ON commission_tiers(service_type_id, is_active);

-- ============================================================
-- 7. exchange_rates
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
-- 8. daily_summary
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_summary (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    summary_date       TEXT NOT NULL UNIQUE,
    total_cash_in      REAL NOT NULL DEFAULT 0.00,
    total_cash_out     REAL NOT NULL DEFAULT 0.00,
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
-- 9. activity_logs
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
-- 10. cash_float_assignments
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_float_assignments (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id               INTEGER NOT NULL,
    issued_by                 INTEGER NOT NULL,
    status                    TEXT NOT NULL DEFAULT 'PENDING_RECEIPT'
                              CHECK(status IN ('PENDING_RECEIPT','ACTIVE','PENDING_RECONCILIATION','CLOSED')),
    total_amount              REAL NOT NULL DEFAULT 0.00,
    current_balance           REAL NOT NULL DEFAULT 0,
    return_denominations_json TEXT,
    received_at               TEXT,
    closed_at                 TEXT,
    closing_total             REAL,
    note                      TEXT,
    created_at                TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (issued_by)   REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_float_employee ON cash_float_assignments(employee_id, status);

-- ============================================================
-- 11. cash_denomination_logs
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_denomination_logs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_type     TEXT NOT NULL CHECK(entry_type IN ('vault_in','vault_out','float_returned','adjustment')),
    denomination   INTEGER NOT NULL CHECK(denomination IN (50,100,200,500,1000,5000,10000,20000)),
    quantity       INTEGER NOT NULL,
    float_id       INTEGER,
    transaction_id INTEGER,
    created_by     INTEGER NOT NULL,
    note           TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by)     REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (float_id)       REFERENCES cash_float_assignments(id) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON UPDATE CASCADE ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_denom_log_created ON cash_denomination_logs(created_at);

-- ============================================================
-- 12. cash_float_denominations
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_float_denominations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    float_id     INTEGER NOT NULL,
    denomination INTEGER NOT NULL CHECK(denomination IN (50,100,200,500,1000,5000,10000,20000)),
    quantity     INTEGER NOT NULL,
    FOREIGN KEY (float_id) REFERENCES cash_float_assignments(id) ON UPDATE CASCADE ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_float_denom_float ON cash_float_denominations(float_id);

-- ============================================================
-- 13. vault_transactions (immutable audit trail)
-- ============================================================
CREATE TABLE IF NOT EXISTS vault_transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_type       TEXT NOT NULL CHECK(txn_type IN (
                       'float_issue','float_receipt','cash_out',
                       'return_initiate','return_confirm','adjustment'
                   )),
    float_id       INTEGER,
    denomination   INTEGER NOT NULL CHECK(denomination IN (50,100,200,500,1000,5000,10000,20000)),
    quantity       INTEGER NOT NULL CHECK(quantity > 0),
    transaction_id INTEGER,
    performed_by   INTEGER NOT NULL,
    verified_by    INTEGER,
    note           TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (float_id)       REFERENCES cash_float_assignments(id),
    FOREIGN KEY (performed_by)   REFERENCES users(id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);
CREATE INDEX IF NOT EXISTS idx_vault_txn_float   ON vault_transactions(float_id);
CREATE INDEX IF NOT EXISTS idx_vault_txn_created ON vault_transactions(created_at);

-- ============================================================
-- 14. denomination/change management
-- ============================================================
CREATE TABLE IF NOT EXISTS note_denominations (
    id          INTEGER PRIMARY KEY,
    value       INTEGER NOT NULL UNIQUE CHECK(value IN (50,100,200,500,1000,5000,10000,20000)),
    label_mm    TEXT NOT NULL,
    label_en    TEXT NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vault_denomination_balances (
    denomination_id INTEGER PRIMARY KEY,
    quantity        INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
    total_value     INTEGER NOT NULL DEFAULT 0 CHECK(total_value >= 0),
    last_updated    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (denomination_id) REFERENCES note_denominations(id)
);

CREATE TABLE IF NOT EXISTS transaction_payment_denominations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id    INTEGER NOT NULL,
    denomination_id   INTEGER NOT NULL,
    quantity_paid     INTEGER NOT NULL DEFAULT 0 CHECK(quantity_paid >= 0),
    quantity_returned INTEGER NOT NULL DEFAULT 0 CHECK(quantity_returned >= 0),
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (transaction_id)  REFERENCES transactions(id) ON DELETE CASCADE,
    FOREIGN KEY (denomination_id) REFERENCES note_denominations(id)
);
CREATE INDEX IF NOT EXISTS idx_payment_denoms_txn
    ON transaction_payment_denominations(transaction_id);

-- ============================================================
-- 15. daily_reconciliation_logs
-- ============================================================
CREATE TABLE IF NOT EXISTS daily_reconciliation_logs (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    recon_date            TEXT NOT NULL,
    closed_by             INTEGER NOT NULL,
    closed_at             TEXT NOT NULL DEFAULT (datetime('now')),
    total_cash_in         REAL NOT NULL DEFAULT 0,
    total_cash_out        REAL NOT NULL DEFAULT 0,
    total_transfer        REAL NOT NULL DEFAULT 0,
    total_exchange        REAL NOT NULL DEFAULT 0,
    total_commission      REAL NOT NULL DEFAULT 0,
    total_customer_fees   REAL NOT NULL DEFAULT 0,
    main_vault_total      REAL NOT NULL DEFAULT 0,
    employee_floats_total REAL NOT NULL DEFAULT 0,
    total_cash            REAL NOT NULL DEFAULT 0,
    total_digital         REAL NOT NULL DEFAULT 0,
    grand_total           REAL NOT NULL DEFAULT 0,
    employee_snapshots    TEXT,
    account_snapshots     TEXT,
    vault_snapshot        TEXT,
    notes                 TEXT,
    FOREIGN KEY (closed_by) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_recon_date ON daily_reconciliation_logs(recon_date);

-- ============================================================
-- SEED DATA
-- ============================================================

-- schema_version seed (fresh install = all migrations applied)
INSERT OR IGNORE INTO schema_version (version, description) VALUES
(1, 'Add cashier role and pin_hash'),
(2, 'Create cash management tables'),
(3, 'Add cash approval fields to transactions'),
(4, 'Add companies, service_types; migrate accounts, commission_tiers, and transactions'),
(5, 'Add is_fee_account flag to accounts'),
(6, 'Add current_balance to floats; create daily_reconciliation_logs'),
(7, 'Rebuild cash_float_assignments with new statuses; create vault_transactions'),
(8, 'Add Pay_To_Pay service types for Bank companies'),
(9, 'Add auth_version for token revocation'),
(10, 'Add transaction status and vault impact fields'),
(11, 'Add denomination payment and vault balance tables'),
(12, 'Add 20,000 MMK denomination support');

INSERT OR IGNORE INTO note_denominations (id, value, label_mm, label_en, is_active) VALUES
(50, 50, '50 Kyats', '50 Kyats', 1),
(100, 100, '100 Kyats', '100 Kyats', 1),
(200, 200, '200 Kyats', '200 Kyats', 1),
(500, 500, '500 Kyats', '500 Kyats', 1),
(1000, 1000, '1,000 Kyats', '1,000 Kyats', 1),
(5000, 5000, '5,000 Kyats', '5,000 Kyats', 1),
(10000, 10000, '10,000 Kyats', '10,000 Kyats', 1),
(20000, 20000, '20,000 Kyats', '20,000 Kyats', 1);

INSERT OR IGNORE INTO vault_denomination_balances (denomination_id, quantity, total_value)
SELECT id, 0, 0 FROM note_denominations;

-- Users  (bcrypt, cost 12)
-- owner: admin123 / employee: employee123 / cashier: cashier123
INSERT OR IGNORE INTO users (username, password_hash, full_name, role) VALUES
('owner',    '$2b$12$Ip2fxV/CbjrmQC5Slhhuge9p0Lomxo/qFo1N0jAe3dqalhQrJX/zO', 'Owner Name',    'owner'),
('employee', '$2b$12$YMQbtr6qdvg.wS3t5S6/iOqgEweIOnaKqlKeXBbqWzdE48YO1CIJu', 'Employee Name', 'employee'),
('cashier',  '$2b$12$xVqJyqiLc4Buur1RbX84meWNqNmW9G/fkatHEA3MxrhjKkEemo48a', 'Cashier Name',  'cashier');

-- Companies (canonical + legacy)
INSERT OR IGNORE INTO companies (name, category, is_active) VALUES
('KBZ Pay',      'Pay',  1),
('Wave Money',   'Pay',  1),
('True Money',   'Pay',  1),
('KBZ Bank',     'Bank', 1),
('AYA Bank',     'Bank', 1),
('CB Bank',      'Bank', 1),
('AYA Pay',      'Pay',  1),
('Thai Bank',    'Bank', 1);

-- Service types per company (Pay: WST + Pay_To_Pay / Bank: Pay_To_Pay + Transfer + Exchange)
INSERT OR IGNORE INTO service_types (company_id, name, operation)
SELECT id, 'WST',       'All' FROM companies WHERE name IN ('KBZ Pay','Wave Money','True Money','AYA Pay');

INSERT OR IGNORE INTO service_types (company_id, name, operation)
SELECT id, 'Pay_To_Pay','All' FROM companies WHERE name IN ('KBZ Pay','Wave Money','True Money','AYA Pay');

INSERT OR IGNORE INTO service_types (company_id, name, operation)
SELECT id, 'Pay_To_Pay','All' FROM companies WHERE name IN ('KBZ Bank','AYA Bank','CB Bank','Thai Bank');

INSERT OR IGNORE INTO service_types (company_id, name, operation)
SELECT id, 'Transfer',  'Transfer' FROM companies WHERE name IN ('KBZ Bank','AYA Bank','CB Bank','Thai Bank');

INSERT OR IGNORE INTO service_types (company_id, name, operation)
SELECT id, 'Exchange',  'Exchange' FROM companies WHERE name IN ('KBZ Bank','AYA Bank','CB Bank','Thai Bank');
