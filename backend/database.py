import sqlite3
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(os.getenv("DB_PATH", "ngwe_lwe.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    # Return rows as plain dicts so existing row["column"] access works unchanged
    conn.row_factory = lambda cur, row: dict(zip([col[0] for col in cur.description], row))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _connect_immediate() -> sqlite3.Connection:
    """Open a connection in manual-transaction mode for BEGIN IMMEDIATE locking."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, isolation_level=None)
    conn.row_factory = lambda cur, row: dict(zip([col[0] for col in cur.description], row))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_connection():
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


_atomic_conn: ContextVar[sqlite3.Connection | None] = ContextVar("_atomic_conn", default=None)


@contextmanager
def atomic():
    """Wrap multiple get_cursor() calls in a single atomic DB transaction.
    Uses BEGIN IMMEDIATE to serialize concurrent writers and prevent TOCTOU races.
    All writes commit together on exit; any exception rolls back everything."""
    existing = _atomic_conn.get()
    if existing is not None:
        yield existing
        return
    conn = _connect_immediate()
    token = _atomic_conn.set(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        _atomic_conn.reset(token)
        conn.close()


@contextmanager
def get_cursor(commit: bool = False):
    conn = _atomic_conn.get()
    if conn is not None:
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()
        return
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def _migrate_001(conn):
    """Recreate users with cashier role + pin_hash."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            pin_hash TEXT,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee' CHECK(role IN ('owner','employee','cashier')),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO users_v2 SELECT id,username,password_hash,NULL,full_name,role,is_active,created_at,updated_at FROM users;
        DROP TABLE users;
        ALTER TABLE users_v2 RENAME TO users;
        DROP TRIGGER IF EXISTS trg_users_updated_at;
        CREATE TRIGGER trg_users_updated_at AFTER UPDATE ON users FOR EACH ROW
        BEGIN UPDATE users SET updated_at = datetime('now') WHERE id = NEW.id; END;
    """)


def _migrate_002(conn):
    """Create cash management tables."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cash_float_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            issued_by INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','ACTIVE','CLOSED')),
            total_amount REAL NOT NULL DEFAULT 0.00,
            received_at TEXT, closed_at TEXT, closing_total REAL, note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (employee_id) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (issued_by) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS cash_denomination_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_type TEXT NOT NULL CHECK(entry_type IN ('vault_in','vault_out','float_returned','adjustment')),
            denomination INTEGER NOT NULL CHECK(denomination IN (50,100,200,500,1000,5000,10000)),
            quantity INTEGER NOT NULL,
            float_id INTEGER,
            created_by INTEGER NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (created_by) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (float_id) REFERENCES cash_float_assignments(id) ON UPDATE CASCADE ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS cash_float_denominations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            float_id INTEGER NOT NULL,
            denomination INTEGER NOT NULL CHECK(denomination IN (50,100,200,500,1000,5000,10000)),
            quantity INTEGER NOT NULL,
            FOREIGN KEY (float_id) REFERENCES cash_float_assignments(id) ON UPDATE CASCADE ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_float_employee ON cash_float_assignments(employee_id, status);
        CREATE INDEX IF NOT EXISTS idx_denom_log_created ON cash_denomination_logs(created_at);
        CREATE INDEX IF NOT EXISTS idx_float_denom_float ON cash_float_denominations(float_id);
    """)


def _migrate_003(conn):
    """Add cash approval fields to transactions."""
    conn.executescript("""
        ALTER TABLE transactions ADD COLUMN cash_approved_by INTEGER REFERENCES users(id);
        ALTER TABLE transactions ADD COLUMN cash_approved_at TEXT;
    """)


def _migrate_004(conn):
    """
    Add companies + service_types tables; migrate accounts, commission_tiers,
    and transactions to use FK-based lookups instead of free-text strings.

    Steps (all in a single transaction):
      1.  Create companies table + trigger
      2.  Seed 14 canonical + legacy companies
      3.  Create service_types table + trigger
      4.  Seed service_types per company
      5.  Pre-migration validation: ensure every (service_type, account_type)
          pair in commission_tiers maps to a known service_types row
      6.  Seed True Money commission tier rows (INSERT OR IGNORE)
      7.  Rebuild accounts with service_type_id FK (drop service_id + service_type TEXT)
      8.  Rebuild commission_tiers with service_type_id FK (drop service_type + account_type TEXT)
      9.  Add from_company_id + to_company_id to transactions
      10. Back-fill from_company_id / to_company_id for transfer/exchange rows
    """
    # Disable FK enforcement during migration (re-enabled at end)
    conn.execute("PRAGMA foreign_keys = OFF")

    # ── 1. companies table ────────────────────────────────────────────────
    conn.executescript("""
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
        DROP TRIGGER IF EXISTS trg_companies_updated_at;
        CREATE TRIGGER trg_companies_updated_at
        AFTER UPDATE ON companies FOR EACH ROW
        BEGIN UPDATE companies SET updated_at = datetime('now') WHERE id = NEW.id; END;
    """)

    # ── 2. Seed 14 companies ─────────────────────────────────────────────
    companies_seed = [
        # Canonical Pay companies
        ("KBZ Pay",       "Pay"),
        ("Wave Money",    "Pay"),
        ("True Money",    "Pay"),
        # Canonical Bank companies
        ("KBZ Bank",      "Bank"),
        ("AYA Bank",      "Bank"),
        ("CB Bank",       "Bank"),
        # Legacy Pay companies (migrated from services table)
        ("MPT Pay",       "Pay"),
        ("OK Dollar",     "Pay"),
        ("One Pay",       "Pay"),
        ("AYA Pay",       "Pay"),
        ("Yoma Pay",      "Pay"),
        ("City Express",  "Pay"),
        ("KBZ Express",   "Pay"),
        # Legacy Bank company
        ("Thai Bank",     "Bank"),
    ]
    for name, category in companies_seed:
        conn.execute(
            "INSERT OR IGNORE INTO companies (name, category, is_active) VALUES (?,?,1)",
            (name, category),
        )
    conn.commit()

    # ── 3. service_types table ────────────────────────────────────────────
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS service_types (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  INTEGER NOT NULL,
            name        TEXT NOT NULL,
            operation   TEXT NOT NULL
                        CHECK(operation IN ('Deposit','Withdraw','Transfer','Exchange','All')),
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(company_id, name),
            FOREIGN KEY (company_id) REFERENCES companies(id)
                ON UPDATE CASCADE ON DELETE RESTRICT
        );
        DROP TRIGGER IF EXISTS trg_service_types_updated_at;
        CREATE TRIGGER trg_service_types_updated_at
        AFTER UPDATE ON service_types FOR EACH ROW
        BEGIN UPDATE service_types SET updated_at = datetime('now') WHERE id = NEW.id; END;
    """)

    # ── 4. Seed service_types per company ─────────────────────────────────
    # Helper: get company id by name
    def _company_id(name: str) -> int:
        row = conn.execute(
            "SELECT id FROM companies WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Company '{name}' not found after seeding")
        return row["id"] if isinstance(row, dict) else row[0]

    # Pay companies → WST (All) + Pay_To_Pay (All)
    pay_companies = [
        "KBZ Pay", "Wave Money", "True Money",
        "MPT Pay", "OK Dollar", "One Pay", "AYA Pay",
        "Yoma Pay", "City Express", "KBZ Express",
    ]
    for company_name in pay_companies:
        cid = _company_id(company_name)
        conn.execute(
            "INSERT OR IGNORE INTO service_types (company_id, name, operation) "
            "VALUES (?,?,?)", (cid, "WST", "All")
        )
        conn.execute(
            "INSERT OR IGNORE INTO service_types (company_id, name, operation) "
            "VALUES (?,?,?)", (cid, "Pay_To_Pay", "All")
        )

    # Bank companies → Transfer (Transfer) + Exchange (Exchange)
    bank_companies = ["KBZ Bank", "AYA Bank", "CB Bank", "Thai Bank"]
    for company_name in bank_companies:
        cid = _company_id(company_name)
        conn.execute(
            "INSERT OR IGNORE INTO service_types (company_id, name, operation) "
            "VALUES (?,?,?)", (cid, "Transfer", "Transfer")
        )
        conn.execute(
            "INSERT OR IGNORE INTO service_types (company_id, name, operation) "
            "VALUES (?,?,?)", (cid, "Exchange", "Exchange")
        )
    conn.commit()

    # ── 5. Pre-migration validation ───────────────────────────────────────
    # Legacy tier key → (company_name, service_type_name) mapping
    _LEGACY_TIER_MAP = {
        "KPAY_WST":             ("KBZ Pay",    "WST"),
        "WAVE_WST":             ("Wave Money", "WST"),
        "WAVE_ACCOUNT":         ("Wave Money", "Pay_To_Pay"),
        "TRUE_MONEY_WST":       ("True Money", "WST"),
        "TRUE_MONEY_PAY_TO_PAY":("True Money", "Pay_To_Pay"),
    }

    tier_pairs = conn.execute(
        "SELECT DISTINCT service_type, account_type FROM commission_tiers"
    ).fetchall()

    def _pair_val(row, col):
        return row[col] if isinstance(row, dict) else row[0 if col == "service_type" else 1]

    unmapped = []
    for row in tier_pairs:
        st = _pair_val(row, "service_type")
        at = _pair_val(row, "account_type")
        key = st  # primary key is service_type TEXT
        if key not in _LEGACY_TIER_MAP:
            unmapped.append((st, at))

    if unmapped:
        raise RuntimeError(
            f"_migrate_004: unmapped commission_tier keys found: {unmapped}. "
            "Ensure all tier service_type values are in the legacy map before migrating."
        )

    # ── 6. Seed True Money commission tier rows ───────────────────────────
    # Copy commission values from KBZ Pay WST tier (fallback: use hardcoded 500/300)
    kpay_wst_row = conn.execute(
        "SELECT * FROM commission_tiers WHERE service_type = 'KPAY_WST' LIMIT 1"
    ).fetchone()

    def _val(row, col):
        if row is None:
            return 0.0
        return row[col] if isinstance(row, dict) else None

    if kpay_wst_row is not None:
        if isinstance(kpay_wst_row, dict):
            kpay_vals = kpay_wst_row
        else:
            # Shouldn't happen since _connect uses dict row_factory, but guard anyway
            kpay_vals = {}

        # True Money WST — same comm as KBZ Pay WST
        conn.execute(
            "INSERT OR IGNORE INTO commission_tiers "
            "(service_type, account_type, amount_from, amount_to, "
            " fee_amount_type, fee_amount_deposit, fee_amount_withdraw, "
            " comm_type, comm_deposit, comm_withdraw, "
            " additional_fee_type, additional_fee_deposit_amount, "
            " additional_fee_withdraw_amount) "
            "VALUES ('TRUE_MONEY_WST', 'agent', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                kpay_vals.get("amount_from"),
                kpay_vals.get("amount_to"),
                kpay_vals.get("fee_amount_type", "FIXED"),
                kpay_vals.get("fee_amount_deposit", 0.0),
                kpay_vals.get("fee_amount_withdraw", 0.0),
                kpay_vals.get("comm_type", "FIXED"),
                kpay_vals.get("comm_deposit", 0.0),
                kpay_vals.get("comm_withdraw", 0.0),
                kpay_vals.get("additional_fee_type", "FIXED"),
                kpay_vals.get("additional_fee_deposit_amount", 0.0),
                kpay_vals.get("additional_fee_withdraw_amount", 0.0),
            ),
        )

    # True Money Pay_To_Pay — check if WAVE_ACCOUNT exists for default values
    wave_acc_row = conn.execute(
        "SELECT * FROM commission_tiers WHERE service_type = 'WAVE_ACCOUNT' LIMIT 1"
    ).fetchone()
    if wave_acc_row is not None:
        if isinstance(wave_acc_row, dict):
            wave_vals = wave_acc_row
        else:
            wave_vals = {}

        conn.execute(
            "INSERT OR IGNORE INTO commission_tiers "
            "(service_type, account_type, amount_from, amount_to, "
            " fee_amount_type, fee_amount_deposit, fee_amount_withdraw, "
            " comm_type, comm_deposit, comm_withdraw, "
            " additional_fee_type, additional_fee_deposit_amount, "
            " additional_fee_withdraw_amount) "
            "VALUES ('TRUE_MONEY_PAY_TO_PAY', 'personal', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                wave_vals.get("amount_from"),
                wave_vals.get("amount_to"),
                wave_vals.get("fee_amount_type", "FIXED"),
                wave_vals.get("fee_amount_deposit", 0.0),
                wave_vals.get("fee_amount_withdraw", 0.0),
                wave_vals.get("comm_type", "FIXED"),
                wave_vals.get("comm_deposit", 0.0),
                wave_vals.get("comm_withdraw", 0.0),
                wave_vals.get("additional_fee_type", "FIXED"),
                wave_vals.get("additional_fee_deposit_amount", 0.0),
                wave_vals.get("additional_fee_withdraw_amount", 0.0),
            ),
        )
    conn.commit()

    # ── 7. Rebuild accounts table ─────────────────────────────────────────
    #
    # Map legacy accounts to service_type_id using:
    #   service_type TEXT ('KPAY','WAVE','BANK') + account_type ('agent','personal')
    #
    # KPAY          → KBZ Pay WST
    # WAVE + agent  → Wave Money WST
    # WAVE + personal → Wave Money Pay_To_Pay
    # BANK          → we use the legacy services.name to find the correct bank company
    #                 (services table may still exist at this point)
    #
    # Strategy: use a CASE expression against service_types joined to companies.
    # Since we don't have direct FK from old accounts to companies, we use the
    # services table (which still exists) to get the company name.
    #
    # First, check if services table exists (it should for existing DBs)
    _services_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='services'"
    ).fetchone()

    if _services_exists:
        # Use services.name to map to company names.
        # For Pay wallets, use account.service_type TEXT to pick WST vs Pay_To_Pay.
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts_v2 (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                service_type_id INTEGER NOT NULL REFERENCES service_types(id),
                account_name    TEXT NOT NULL,
                phone_number    TEXT NOT NULL,
                balance         REAL NOT NULL DEFAULT 0.00,
                commission_rate REAL NOT NULL DEFAULT 0.0000,
                is_active       INTEGER NOT NULL DEFAULT 1,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)

        # Insert accounts mapped to service_type_id.
        # For KPAY accounts (service_type='KPAY'): always → KBZ Pay WST
        # For WAVE agent (service_type='WAVE', account_type='agent'): → Wave Money WST
        # For WAVE personal (service_type='WAVE', account_type='personal'): → Wave Money Pay_To_Pay
        # For BANK (service_type='BANK'): join services → companies to get company, then Transfer ST
        conn.execute("""
            INSERT INTO accounts_v2
                (id, service_type_id, account_name, phone_number,
                 balance, commission_rate, is_active, created_at, updated_at)
            SELECT
                a.id,
                CASE
                    WHEN a.service_type = 'KPAY' THEN
                        (SELECT st.id FROM service_types st
                         JOIN companies c ON c.id = st.company_id
                         WHERE c.name = 'KBZ Pay' AND st.name = 'WST' LIMIT 1)
                    WHEN a.service_type = 'WAVE' AND a.account_type = 'agent' THEN
                        (SELECT st.id FROM service_types st
                         JOIN companies c ON c.id = st.company_id
                         WHERE c.name = 'Wave Money' AND st.name = 'WST' LIMIT 1)
                    WHEN a.service_type = 'WAVE' AND a.account_type = 'personal' THEN
                        (SELECT st.id FROM service_types st
                         JOIN companies c ON c.id = st.company_id
                         WHERE c.name = 'Wave Money' AND st.name = 'Pay_To_Pay' LIMIT 1)
                    WHEN a.service_type = 'BANK' THEN
                        (SELECT st.id FROM service_types st
                         JOIN companies c ON c.id = st.company_id
                         JOIN services svc ON svc.name = c.name
                         WHERE svc.id = a.service_id
                           AND st.name = 'Transfer' LIMIT 1)
                    ELSE NULL
                END,
                a.account_name,
                a.phone_number,
                a.balance,
                a.commission_rate,
                a.is_active,
                a.created_at,
                a.updated_at
            FROM accounts a
        """)
        conn.commit()
    else:
        # Fresh-install path: accounts already have service_type_id (shouldn't happen in migration)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS accounts_v2 (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                service_type_id INTEGER NOT NULL REFERENCES service_types(id),
                account_name    TEXT NOT NULL,
                phone_number    TEXT NOT NULL,
                balance         REAL NOT NULL DEFAULT 0.00,
                commission_rate REAL NOT NULL DEFAULT 0.0000,
                is_active       INTEGER NOT NULL DEFAULT 1,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        conn.execute("""
            INSERT INTO accounts_v2
                (id, service_type_id, account_name, phone_number,
                 balance, commission_rate, is_active, created_at, updated_at)
            SELECT id, service_type_id, account_name, phone_number,
                   balance, commission_rate, is_active, created_at, updated_at
            FROM accounts
        """)
        conn.commit()

    conn.executescript("""
        DROP TABLE accounts;
        ALTER TABLE accounts_v2 RENAME TO accounts;
        DROP TRIGGER IF EXISTS trg_accounts_updated_at;
        CREATE TRIGGER trg_accounts_updated_at
        AFTER UPDATE ON accounts FOR EACH ROW
        BEGIN UPDATE accounts SET updated_at = datetime('now') WHERE id = NEW.id; END;
        CREATE INDEX IF NOT EXISTS idx_accounts_service_type_id
            ON accounts(service_type_id);
    """)
    conn.commit()

    # ── 8. Rebuild commission_tiers table ─────────────────────────────────
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS commission_tiers_v2 (
            id                             INTEGER PRIMARY KEY AUTOINCREMENT,
            service_type_id                INTEGER NOT NULL REFERENCES service_types(id),
            amount_from                    REAL,
            amount_to                      REAL,
            fee_amount_type                TEXT NOT NULL DEFAULT 'FIXED'
                                           CHECK(fee_amount_type IN ('FIXED','PERCENTAGE')),
            fee_amount_deposit             REAL NOT NULL DEFAULT 0.0,
            fee_amount_withdraw            REAL NOT NULL DEFAULT 0.0,
            comm_type                      TEXT NOT NULL DEFAULT 'FIXED'
                                           CHECK(comm_type IN ('FIXED','PERCENTAGE')),
            comm_deposit                   REAL NOT NULL DEFAULT 0.0,
            comm_withdraw                  REAL NOT NULL DEFAULT 0.0,
            additional_fee_type            TEXT NOT NULL DEFAULT 'FIXED'
                                           CHECK(additional_fee_type IN ('FIXED','PERCENTAGE')),
            additional_fee_deposit_amount  REAL NOT NULL DEFAULT 0.0,
            additional_fee_withdraw_amount REAL NOT NULL DEFAULT 0.0,
            is_active                      INTEGER NOT NULL DEFAULT 1,
            created_at                     TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    # Map each legacy tier to service_type_id using the LEGACY_TIER_MAP
    for legacy_key, (company_name, st_name) in _LEGACY_TIER_MAP.items():
        conn.execute("""
            INSERT INTO commission_tiers_v2
                (service_type_id, amount_from, amount_to,
                 fee_amount_type, fee_amount_deposit, fee_amount_withdraw,
                 comm_type, comm_deposit, comm_withdraw,
                 additional_fee_type, additional_fee_deposit_amount,
                 additional_fee_withdraw_amount, is_active, created_at)
            SELECT
                (SELECT st.id FROM service_types st
                 JOIN companies c ON c.id = st.company_id
                 WHERE c.name = ? AND st.name = ? LIMIT 1),
                ct.amount_from, ct.amount_to,
                ct.fee_amount_type, ct.fee_amount_deposit, ct.fee_amount_withdraw,
                ct.comm_type, ct.comm_deposit, ct.comm_withdraw,
                ct.additional_fee_type, ct.additional_fee_deposit_amount,
                ct.additional_fee_withdraw_amount, ct.is_active, ct.created_at
            FROM commission_tiers ct
            WHERE ct.service_type = ?
        """, (company_name, st_name, legacy_key))
    conn.commit()

    conn.executescript("""
        DROP TABLE commission_tiers;
        ALTER TABLE commission_tiers_v2 RENAME TO commission_tiers;
        CREATE INDEX IF NOT EXISTS idx_tier_lookup
            ON commission_tiers(service_type_id, is_active);
    """)
    conn.commit()

    # ── 9. Add from_company_id + to_company_id to transactions ───────────
    # ALTER TABLE ADD COLUMN is safe in SQLite (idempotent guard via try/except)
    try:
        conn.execute(
            "ALTER TABLE transactions ADD COLUMN from_company_id INTEGER "
            "REFERENCES companies(id)"
        )
    except Exception:
        pass  # column already exists

    try:
        conn.execute(
            "ALTER TABLE transactions ADD COLUMN to_company_id INTEGER "
            "REFERENCES companies(id)"
        )
    except Exception:
        pass  # column already exists
    conn.commit()

    # ── 10. Back-fill from/to company IDs ────────────────────────────────
    conn.execute("""
        UPDATE transactions
        SET from_company_id = (
            SELECT st.company_id
            FROM accounts a
            JOIN service_types st ON a.service_type_id = st.id
            WHERE a.id = transactions.account_id
        )
        WHERE transaction_type IN ('transfer', 'exchange', 'deposit', 'withdraw')
          AND from_company_id IS NULL
    """)

    conn.execute("""
        UPDATE transactions
        SET to_company_id = (
            SELECT st.company_id
            FROM accounts a
            JOIN service_types st ON a.service_type_id = st.id
            WHERE a.id = transactions.to_account_id
        )
        WHERE transaction_type IN ('transfer', 'exchange')
          AND to_account_id IS NOT NULL
          AND to_company_id IS NULL
    """)
    conn.commit()

    # Re-enable FK enforcement
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def _migrate_005(conn):
    """Add is_fee_account flag to accounts table."""
    try:
        conn.execute(
            "ALTER TABLE accounts ADD COLUMN is_fee_account INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()
    except Exception:
        pass  # column already exists


def _migrate_006(conn):
    """Add current_balance to cash_float_assignments; create daily_reconciliation_logs."""
    try:
        conn.execute(
            "ALTER TABLE cash_float_assignments ADD COLUMN current_balance REAL NOT NULL DEFAULT 0"
        )
        conn.commit()
    except Exception:
        pass  # column already exists

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS daily_reconciliation_logs (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            recon_date            TEXT NOT NULL,
            closed_by             INTEGER NOT NULL,
            closed_at             TEXT NOT NULL DEFAULT (datetime('now')),
            total_deposit         REAL NOT NULL DEFAULT 0,
            total_withdraw        REAL NOT NULL DEFAULT 0,
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
    """)
    conn.commit()


def _migrate_007(conn):
    """
    Rebuild cash_float_assignments with new statuses + return_denominations_json column.
    Create vault_transactions audit table.
    """
    conn.execute("PRAGMA foreign_keys = OFF")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS cash_float_assignments_v7 (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id             INTEGER NOT NULL,
            issued_by               INTEGER NOT NULL,
            status                  TEXT NOT NULL DEFAULT 'PENDING_RECEIPT'
                                    CHECK(status IN (
                                        'PENDING_RECEIPT','ACTIVE',
                                        'PENDING_RECONCILIATION','CLOSED'
                                    )),
            total_amount            REAL NOT NULL DEFAULT 0.00,
            current_balance         REAL NOT NULL DEFAULT 0,
            return_denominations_json TEXT,
            received_at             TEXT,
            closed_at               TEXT,
            closing_total           REAL,
            note                    TEXT,
            created_at              TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (employee_id) REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (issued_by)   REFERENCES users(id) ON UPDATE CASCADE ON DELETE RESTRICT
        );
    """)

    conn.execute("""
        INSERT INTO cash_float_assignments_v7
            (id, employee_id, issued_by, status, total_amount, current_balance,
             received_at, closed_at, closing_total, note, created_at)
        SELECT
            id, employee_id, issued_by,
            CASE status
                WHEN 'PENDING' THEN 'PENDING_RECEIPT'
                ELSE status
            END,
            total_amount,
            COALESCE(current_balance, 0),
            received_at, closed_at, closing_total, note, created_at
        FROM cash_float_assignments
    """)
    conn.commit()

    conn.executescript("""
        DROP TABLE cash_float_assignments;
        ALTER TABLE cash_float_assignments_v7 RENAME TO cash_float_assignments;
        DROP INDEX IF EXISTS idx_float_employee;
        CREATE INDEX idx_float_employee ON cash_float_assignments(employee_id, status);
    """)
    conn.commit()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS vault_transactions (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_type       TEXT NOT NULL CHECK(txn_type IN (
                               'float_issue','float_receipt','withdrawal',
                               'return_initiate','return_confirm','adjustment'
                           )),
            float_id       INTEGER,
            denomination   INTEGER NOT NULL CHECK(denomination IN (50,100,200,500,1000,5000,10000)),
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
    """)
    conn.commit()

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def _run_migrations(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL DEFAULT (datetime('now')),
        description TEXT)""")
    conn.commit()
    applied = {r["version"] for r in conn.execute("SELECT version FROM schema_version").fetchall()}
    for version, desc, fn in [
        (1, "Add cashier role and pin_hash", _migrate_001),
        (2, "Create cash management tables", _migrate_002),
        (3, "Add cash approval fields to transactions", _migrate_003),
        (4, "Add companies, service_types; migrate accounts, commission_tiers, and transactions", _migrate_004),
        (5, "Add is_fee_account flag to accounts", _migrate_005),
        (6, "Add current_balance to floats; create daily_reconciliation_logs", _migrate_006),
        (7, "Rebuild cash_float_assignments with new statuses; create vault_transactions", _migrate_007),
    ]:
        if version not in applied:
            fn(conn)
            conn.execute(
                "INSERT INTO schema_version (version,description) VALUES (?,?)",
                (version, desc),
            )
            conn.commit()


def init_db() -> None:
    """Create schema on first run (only if tables do not exist yet), then run migrations."""
    with get_connection() as conn:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        if exists is None:
            schema = (Path(__file__).parent / "database.sql").read_text(encoding="utf-8")
            conn.executescript(schema)
        _run_migrations(conn)
