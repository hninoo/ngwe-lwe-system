"""
Ngwe Lwe System — Demo launcher
Starts the API server in a background thread, then opens the desktop UI.
Double-click this file (or the built exe) to run everything.
"""
import os
import sys

# ── Resolve base directory (works both as .py and as PyInstaller exe) ──
if getattr(sys, "frozen", False):
    _BASE = os.path.dirname(sys.executable)
    # PyInstaller extracts bundled data here
    _BUNDLE = sys._MEIPASS  # type: ignore[attr-defined]
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE = _BASE

# ── Set env vars BEFORE any backend imports (auth.py checks APP_SECRET at import) ──
os.environ.setdefault("DB_PATH",       os.path.join(_BASE, "ngwe_lwe.db"))
os.environ.setdefault("APP_SECRET",    "NgweLwe-Demo-Secret-Key-2024")
os.environ.setdefault("API_BASE_URL",  "http://127.0.0.1:8000")
os.environ.setdefault("WS_URL",        "ws://127.0.0.1:8000/ws")

# ── Standard imports (after env is set) ──
import threading
import time

import requests
import uvicorn
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


# ────────────────────────────────────────────
# Server thread
# ────────────────────────────────────────────
class _ThreadSafeServer(uvicorn.Server):
    """Skip OS signal handlers — only valid in main thread."""
    def install_signal_handlers(self) -> None:
        pass


def _start_server() -> None:
    from backend.main import app as fastapi_app
    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
        access_log=False,
        use_colors=False,  # sys.stdout is None in --windowed exe
    )
    server = _ThreadSafeServer(config)
    server.run()


def _wait_for_server(timeout: int = 15) -> bool:
    """Poll /health until the server responds or timeout is reached."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get("http://127.0.0.1:8000/health", timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


# ────────────────────────────────────────────
# Splash screen
# ────────────────────────────────────────────
class SplashScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ငွေလွှဲ System")
        self.setFixedSize(340, 160)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("background-color: #1e1e2e;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("ငွေလွှဲ System")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #89b4fa; background: transparent;")
        layout.addWidget(title)

        self._status = QLabel("Starting server…")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("color: #a6adc8; font-size: 13px; background: transparent;")
        layout.addWidget(self._status)

        # Centre on screen
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2,
        )

    def set_status(self, text: str) -> None:
        self._status.setText(text)
        QApplication.processEvents()


# ────────────────────────────────────────────
# Main
# ────────────────────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)

    splash = SplashScreen()
    splash.show()
    QApplication.processEvents()

    # Start API server in daemon thread
    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()

    splash.set_status("Waiting for server…")

    if not _wait_for_server(timeout=20):
        splash.set_status("Failed to start server. Check port 8000.")
        time.sleep(3)
        sys.exit(1)

    splash.set_status("Ready!")
    time.sleep(0.4)
    splash.close()

    from services.api_client import ApiClient
    from views.login_view import LoginView

    api = ApiClient()
    window = LoginView(api)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
