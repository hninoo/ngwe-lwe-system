-- Ngwe Lwe System Database Schema
-- Myanmar Money Transfer Business Management System

CREATE DATABASE IF NOT EXISTS ngwe_lwe_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE ngwe_lwe_db;

-- ============================================================
-- 1. users - Owner + Employee accounts
-- ============================================================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role ENUM('owner', 'employee') NOT NULL DEFAULT 'employee',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================================
-- 2. services - KPay, Wave, KBZ etc (14 services)
-- ============================================================
CREATE TABLE services (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    service_type VARCHAR(50) NOT NULL,
    default_customer_fee DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================================
-- 3. accounts - Phone numbers per service (Personal/Agent)
-- ============================================================
CREATE TABLE accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    service_id INT NOT NULL,
    account_name VARCHAR(100) NOT NULL,
    account_type ENUM('personal', 'agent') NOT NULL DEFAULT 'personal',
    phone_number VARCHAR(30) NOT NULL,
    service_type ENUM('KPAY', 'WAVE', 'BANK') NOT NULL DEFAULT 'KPAY',
    balance DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    commission_rate DECIMAL(8, 4) NOT NULL DEFAULT 0.0000,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (service_id) REFERENCES services(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    UNIQUE KEY uq_service_phone (service_id, phone_number)
) ENGINE=InnoDB;

-- ============================================================
-- 4. transactions - Deposit, Withdraw, Transfer, Exchange
-- ============================================================
CREATE TABLE transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_type ENUM('deposit', 'withdraw', 'transfer', 'exchange') NOT NULL,
    account_id INT NOT NULL,
    to_account_id INT,
    customer_name VARCHAR(100),
    customer_phone VARCHAR(30),
    amount DECIMAL(18, 2) NOT NULL,
    commission_amount DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    customer_fee DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    additional_fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    balance_change DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    currency VARCHAR(3) NOT NULL DEFAULT 'MMK',
    exchange_rate DECIMAL(18, 4),
    fee_account_id INT,
    screenshot_path VARCHAR(500),
    note TEXT,
    created_by INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (to_account_id) REFERENCES accounts(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (fee_account_id) REFERENCES accounts(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (created_by) REFERENCES users(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_txn_type (transaction_type),
    INDEX idx_txn_created (created_at),
    INDEX idx_txn_created_by (created_by)
) ENGINE=InnoDB;

-- ============================================================
-- 5. commission_tiers - Commission lookup by service_type + amount range
-- ============================================================
CREATE TABLE commission_tiers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    service_type ENUM('KPAY', 'WAVE', 'BANK') NOT NULL,
    account_type ENUM('personal', 'agent') NOT NULL DEFAULT 'agent',
    amount_from DECIMAL(18, 2) NOT NULL,
    amount_to DECIMAL(18, 2) NOT NULL,
    fee_amount DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    comm_send DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    comm_receive DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tier_lookup (service_type, account_type, is_active)
) ENGINE=InnoDB;

-- Seed: WAVE agent tiers
INSERT INTO commission_tiers (service_type, account_type, amount_from, amount_to, fee_amount, comm_send, comm_receive) VALUES
('WAVE','agent',1,10000,400,69,88),
('WAVE','agent',10001,25000,700,123,172),
('WAVE','agent',25001,50000,1000,147,245),
('WAVE','agent',50001,100000,1500,196,392),
('WAVE','agent',100001,150000,2000,294,490),
('WAVE','agent',150001,200000,2500,392,588),
('WAVE','agent',200001,300000,3000,490,686),
('WAVE','agent',300001,400000,4000,653,915),
('WAVE','agent',400001,500000,4500,735,1029),
('WAVE','agent',500001,600000,5400,882,1235),
('WAVE','agent',600001,700000,6000,980,1372),
('WAVE','agent',700001,800000,6700,1094,1532),
('WAVE','agent',800001,900000,7400,1209,1692),
('WAVE','agent',900001,1000000,8000,1307,1829);

-- Seed: KPAY agent tiers
INSERT INTO commission_tiers (service_type, account_type, amount_from, amount_to, fee_amount, comm_send, comm_receive) VALUES
('KPAY','agent',1,10000,400,80,80),
('KPAY','agent',10001,25000,700,140,140),
('KPAY','agent',25001,50000,1000,200,200),
('KPAY','agent',50001,100000,1500,300,300),
('KPAY','agent',100001,150000,2000,400,400),
('KPAY','agent',150001,200000,2500,500,500),
('KPAY','agent',200001,300000,3000,600,600),
('KPAY','agent',300001,400000,4000,800,800),
('KPAY','agent',400001,500000,4500,900,900),
('KPAY','agent',500001,600000,5200,1040,1040),
('KPAY','agent',600001,700000,5800,1160,1160),
('KPAY','agent',700001,800000,6500,1300,1300),
('KPAY','agent',800001,900000,7200,1440,1440),
('KPAY','agent',900001,1000000,7800,1560,1560);

-- ============================================================
-- 6. exchange_rates - MMK ↔ THB rates
-- ============================================================
CREATE TABLE exchange_rates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    currency_pair VARCHAR(7) NOT NULL DEFAULT 'MMK/THB',
    buy_rate DECIMAL(18, 4) NOT NULL,
    sell_rate DECIMAL(18, 4) NOT NULL,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_rate_pair (currency_pair),
    INDEX idx_rate_updated (updated_at)
) ENGINE=InnoDB;

-- ============================================================
-- 6. daily_summary - Auto-calculated daily report
-- ============================================================
CREATE TABLE daily_summary (
    id INT AUTO_INCREMENT PRIMARY KEY,
    summary_date DATE NOT NULL UNIQUE,
    total_deposit DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    total_withdraw DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    total_transfer DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    total_exchange DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    total_commission DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    total_customer_fees DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    total_profit DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    transaction_count INT NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_summary_date (summary_date)
) ENGINE=InnoDB;

-- ============================================================
-- 7. activity_logs - All user actions (audit trail, cannot delete)
-- ============================================================
CREATE TABLE activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INT,
    details TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_log_user (user_id),
    INDEX idx_log_created (created_at)
) ENGINE=InnoDB;

-- ============================================================
-- DEMO DATA
-- ============================================================

-- Users (password: admin123)
INSERT INTO users (username, password_hash, full_name, role) VALUES
('owner', SHA2('admin123', 256), 'Hnin Oo Wai Lwin', 'owner'),
('employee1', SHA2('admin123', 256), 'Aung Aung', 'employee'),
('employee2', SHA2('admin123', 256), 'Mya Mya', 'employee');

-- Services
INSERT INTO services (name, service_type, default_customer_fee) VALUES
('KBZ Pay', 'mobile_wallet', 0),
('Wave Pay', 'mobile_wallet', 0),
('KBZ Bank', 'bank', 0),
('AYA Bank', 'bank', 0),
('CB Bank', 'bank', 0),
('MPT Pay', 'mobile_wallet', 0),
('OK Dollar', 'mobile_wallet', 0),
('True Money', 'mobile_wallet', 0),
('One Pay', 'mobile_wallet', 0),
('AYA Pay', 'mobile_wallet', 0),
('Yoma Pay', 'mobile_wallet', 0),
('City Express', 'express', 0),
('KBZ Express', 'express', 0),
('Thai Bank', 'bank', 0);

-- Accounts (KBZ Pay)
INSERT INTO accounts (service_id, account_name, account_type, phone_number, service_type, balance) VALUES
(1, 'KPay Main', 'agent', '09-987-654-321', 'KPAY', 5000000.00),
(1, 'KPay Personal', 'personal', '09-111-222-333', 'KPAY', 1200000.00);

-- Accounts (Wave Pay)
INSERT INTO accounts (service_id, account_name, account_type, phone_number, service_type, balance) VALUES
(2, 'Wave Agent', 'agent', '09-876-543-210', 'WAVE', 3500000.00),
(2, 'Wave Personal', 'personal', '09-444-555-666', 'WAVE', 800000.00);

-- Accounts (Banks)
INSERT INTO accounts (service_id, account_name, account_type, phone_number, service_type, balance) VALUES
(3, 'KBZ Saving', 'personal', '01234567890', 'BANK', 10000000.00),
(4, 'AYA Current', 'personal', '09876543210', 'BANK', 7500000.00),
(5, 'CB Saving', 'personal', '05678901234', 'BANK', 2000000.00);

-- Accounts (Others)
INSERT INTO accounts (service_id, account_name, account_type, phone_number, service_type, balance) VALUES
(6, 'MPT Agent', 'agent', '09-777-888-999', 'KPAY', 1500000.00),
(7, 'OK Dollar Agent', 'agent', '09-333-444-555', 'KPAY', 900000.00);

-- Exchange rates
INSERT INTO exchange_rates (currency_pair, buy_rate, sell_rate) VALUES
('MMK/THB', 75.5000, 76.5000);

-- Demo transactions (created by employee1, id=2)
INSERT INTO transactions (transaction_type, account_id, customer_name, customer_phone, amount, commission_amount, customer_fee, balance_change, currency, created_by) VALUES
('deposit', 1, 'Ko Min', '09-123-456-789', 50000, 196, 1500, 49804, 'MMK', 2),
('deposit', 1, 'Ma Hla', '09-234-567-890', 100000, 300, 2000, 99700, 'MMK', 2),
('withdraw', 3, 'U Tun', '09-345-678-901', 200000, 588, 2500, -199412, 'MMK', 2),
('deposit', 3, 'Daw Khin', '09-456-789-012', 30000, 147, 1000, 29853, 'MMK', 2),
('withdraw', 1, 'Ko Zaw', '09-567-890-123', 75000, 300, 1500, -74700, 'MMK', 2),
('transfer', 1, NULL, NULL, 500000, 900, 0, -499100, 'MMK', 2),
('deposit', 5, 'Ma Su', '09-678-901-234', 150000, 0, 0, 150000, 'MMK', 2),
('withdraw', 1, 'Ko Aye', '09-789-012-345', 25000, 140, 700, -24860, 'MMK', 3),
('deposit', 3, 'Ma Thin', '09-890-123-456', 80000, 392, 1500, 79608, 'MMK', 3),
('exchange', 1, NULL, NULL, 1000000, 0, 0, 1000000, 'THB', 2);

-- Activity logs
INSERT INTO activity_logs (user_id, action, entity_type, entity_id, details) VALUES
(1, 'login', 'user', 1, 'Owner logged in'),
(2, 'login', 'user', 2, 'Employee logged in'),
(2, 'create', 'transaction', 1, 'Deposit 50,000 MMK via KPay'),
(2, 'create', 'transaction', 2, 'Deposit 100,000 MMK via KPay'),
(2, 'create', 'transaction', 3, 'Withdraw 200,000 MMK via Wave'),
(3, 'login', 'user', 3, 'Employee logged in'),
(3, 'create', 'transaction', 8, 'Withdraw 25,000 MMK via KPay'),
(1, 'update', 'exchange_rate', 1, 'Updated MMK/THB rate');
