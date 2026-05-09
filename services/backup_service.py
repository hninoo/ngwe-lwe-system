import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupService:
    """Creates and manages point-in-time SQLite backups.

    Naming: ngwelwe_backup_YYYYMMDD_HHMMSS.db
    Location: <db_dir>/backups/ by default.
    Retention: files older than 30 days are deleted after each backup.
    Uses sqlite3.Connection.backup() for WAL-safe online copy.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        backup_dir: str | Path | None = None,
    ) -> None:
        self._db_path = Path(db_path or os.getenv("DB_PATH", "ngwe_lwe.db"))
        self._backup_dir = Path(backup_dir) if backup_dir else self._db_path.parent / "backups"

    def create_backup(self) -> Path:
        """Online-copy the live DB to the backups directory, then prune stale files."""
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dest = self._backup_dir / f"ngwelwe_backup_{timestamp}.db"

        src = sqlite3.connect(str(self._db_path))
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()

        check = sqlite3.connect(str(dest))
        try:
            results = check.execute("PRAGMA integrity_check").fetchall()
        finally:
            check.close()

        if not results or results[0][0] != "ok":
            dest.unlink(missing_ok=True)
            raise RuntimeError(f"Backup integrity check failed: {results}")

        logger.info("Backup created: %s", dest)
        self._prune()
        return dest

    def _prune(self, days: int = 30) -> None:
        """Delete backup files whose mtime is older than *days* days."""
        cutoff = datetime.now() - timedelta(days=days)
        for f in self._backup_dir.glob("ngwelwe_backup_*.db"):
            try:
                if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                    f.unlink()
                    logger.info("Pruned old backup: %s", f.name)
            except Exception as exc:
                logger.warning("Could not prune %s: %s", f.name, exc)
