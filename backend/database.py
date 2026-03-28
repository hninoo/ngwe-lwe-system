import os
from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling, Error
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "ngwe_lwe_db"),
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci",
}

_pool: pooling.MySQLConnectionPool | None = None


def get_pool() -> pooling.MySQLConnectionPool:
    """Return the shared connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="ngwe_lwe_pool",
            pool_size=5,
            pool_reset_session=True,
            **DB_CONFIG,
        )
    return _pool


@contextmanager
def get_connection():
    """Yield a connection from the pool. Auto-returns on exit."""
    conn = get_pool().get_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(commit: bool = False):
    """Yield a dictionary cursor. Optionally commits on clean exit."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            yield cursor
            if commit:
                conn.commit()
        except Error:
            conn.rollback()
            raise
        finally:
            cursor.close()


def init_db() -> None:
    """Verify the database connection is reachable."""
    with get_cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
