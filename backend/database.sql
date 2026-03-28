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
    balance_change DECIMAL(18, 2) NOT NULL DEFAULT 0.00,
    currency VARCHAR(3) NOT NULL DEFAULT 'MMK',
    exchange_rate DECIMAL(18, 4),
    screenshot_path VARCHAR(500),
    note TEXT,
    created_by INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (to_account_id) REFERENCES accounts(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    FOREIGN KEY (created_by) REFERENCES users(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_txn_type (transaction_type),
    INDEX idx_txn_created (created_at),
    INDEX idx_txn_created_by (created_by)
) ENGINE=InnoDB;

-- ============================================================
-- 5. exchange_rates - MMK ↔ THB rates
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
-- Seed: default owner account (password: admin123 — change immediately)
-- ============================================================
INSERT INTO users (username, password_hash, full_name, role)
VALUES ('owner', SHA2('admin123', 256), 'Owner', 'owner');
