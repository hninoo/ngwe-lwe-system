import sqlite3
import os
from contextlib import contextmanager
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


@contextmanager
def get_connection():
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(commit: bool = False):
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
