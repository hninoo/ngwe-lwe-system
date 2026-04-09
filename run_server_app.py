"""
NgweLwe Server Manager
Admin က host/port configure လုပ်ပြီး server start/stop လုပ်နိုင်သည်။
Double-click NgweLweServer.exe to run.
"""
import os
import sys
import json
import socket
import threading

# ── Resolve base directory ──
if getattr(sys, "frozen", False):
    _BASE = os.path.dirname(sys.executable)
    _BUNDLE = sys._MEIPASS  # type: ignore[attr-defined]
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE = _BASE

# ── Config file path ──
CONFIG_FILE = os.path.join(_BASE, "server_config.json")
DEFAULT_CONFIG = {"host": "0.0.0.0", "port": 8000}

# ── Env vars before backend imports ──
os.environ.setdefault("DB_PATH",    os.path.join(_BASE, "ngwe_lwe.db"))
os.environ.setdefault("APP_SECRET", "NgweLwe-Secret-Key-2024")

import uvicorn
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QGroupBox,
    QFormLayout, QMessageBox
)


# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_local_ip() -> str:
    """Get the LAN IP of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ─────────────────────────────────────────
# Uvicorn server — no OS signal handlers
# (signal.signal() only works in the main thread; calling it from a QThread
#  raises ValueError and silently crashes the app)
# ─────────────────────────────────────────
class _ThreadSafeServer(uvicorn.Server):
    def install_signal_handlers(self) -> None:
        pass  # skip — we use should_exit flag instead


# ─────────────────────────────────────────
# Server thread
# ─────────────────────────────────────────
class ServerThread(QThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port
        self._server = None

    def run(self):
        import logging
        import traceback

        class QtLogHandler(logging.Handler):
            def __init__(self, signal):
                super().__init__()
                self.signal = signal

            def emit(self, record):
                self.signal.emit(self.format(record))

        handler = QtLogHandler(self.log_signal)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

        uvicorn_logger = logging.getLogger("uvicorn")
        uvicorn_logger.addHandler(handler)
        uvicorn_logger.setLevel(logging.INFO)

        try:
            from backend.main import app as fastapi_app
            config = uvicorn.Config(
                fastapi_app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True,
                use_colors=False,  # sys.stdout is None in --windowed exe
            )
            self._server = _ThreadSafeServer(config)
            self._server.run()
        except Exception:
            self.error_signal.emit(traceback.format_exc())

    def stop(self):
        if self._server:
            self._server.should_exit = True


# ─────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────
class ServerManagerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self._thread: ServerThread | None = None
        self._config = load_config()
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("NgweLwe — Server Manager")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QWidget { background-color: #1e1e2e; color: #cdd6f4; font-family: 'Segoe UI'; font-size: 13px; }
            QGroupBox { border: 1px solid #45475a; border-radius: 6px; margin-top: 8px; padding-top: 8px; }
            QGroupBox::title { color: #89b4fa; padding: 0 4px; }
            QLineEdit { background: #313244; border: 1px solid #45475a; border-radius: 4px; padding: 5px 8px; color: #cdd6f4; }
            QLineEdit:focus { border-color: #89b4fa; }
            QPushButton { border-radius: 5px; padding: 7px 18px; font-weight: bold; }
            QTextEdit { background: #11111b; border: 1px solid #313244; border-radius: 4px; color: #a6e3a1; font-family: Consolas; font-size: 12px; }
        """)

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Title ──
        title = QLabel("ငွေလွှဲ System — Server Manager")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #89b4fa;")
        root.addWidget(title)

        # ── LAN IP hint ──
        local_ip = get_local_ip()
        ip_hint = QLabel(f"ဒီ machine ရဲ့ LAN IP:  {local_ip}")
        ip_hint.setStyleSheet("color: #f9e2af; font-size: 12px;")
        root.addWidget(ip_hint)

        # ── Config group ──
        cfg_box = QGroupBox("Server Configuration (Admin)")
        form = QFormLayout(cfg_box)
        form.setSpacing(8)

        self._host_edit = QLineEdit(self._config.get("host", "0.0.0.0"))
        self._host_edit.setPlaceholderText("e.g. 0.0.0.0  or  192.168.1.100")
        form.addRow("Host:", self._host_edit)

        self._port_edit = QLineEdit(str(self._config.get("port", 8000)))
        self._port_edit.setPlaceholderText("e.g. 8000")
        form.addRow("Port:", self._port_edit)

        # tip
        tip = QLabel(
            "0.0.0.0  →  LAN မှာ client တွေ ချိတ်ဆက်လို့ရမည်\n"
            "127.0.0.1  →  ဒီ machine တစ်ခုတည်းသာ access ရမည်"
        )
        tip.setStyleSheet("color: #6c7086; font-size: 11px;")
        form.addRow("", tip)
        root.addWidget(cfg_box)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("▶  Start Server")
        self._start_btn.setStyleSheet("background-color: #a6e3a1; color: #1e1e2e;")
        self._start_btn.clicked.connect(self._start_server)

        self._stop_btn = QPushButton("■  Stop Server")
        self._stop_btn.setStyleSheet("background-color: #f38ba8; color: #1e1e2e;")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop_server)

        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        root.addLayout(btn_row)

        # ── Status ──
        self._status_label = QLabel("● Stopped")
        self._status_label.setStyleSheet("color: #f38ba8; font-weight: bold;")
        root.addWidget(self._status_label)

        # ── Log ──
        log_box = QGroupBox("Server Log")
        log_layout = QVBoxLayout(log_box)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(200)
        log_layout.addWidget(self._log)
        root.addWidget(log_box)

        self.adjustSize()

    def _start_server(self):
        host = self._host_edit.text().strip()
        port_str = self._port_edit.text().strip()

        if not host:
            QMessageBox.warning(self, "Error", "Host ထည့်ပါ")
            return
        try:
            port = int(port_str)
            assert 1 <= port <= 65535
        except Exception:
            QMessageBox.warning(self, "Error", "Port မှန်ကန်အောင် ထည့်ပါ (1-65535)")
            return

        # Save config
        save_config({"host": host, "port": port})

        self._thread = ServerThread(host, port)
        self._thread.log_signal.connect(self._append_log)
        self._thread.error_signal.connect(self._on_server_error)
        self._thread.start()

        local_ip = get_local_ip()
        display_host = local_ip if host == "0.0.0.0" else host
        self._append_log(f"Server starting on {host}:{port}")
        self._append_log(f"Client တွေကို ဒီ URL ပေး:  http://{display_host}:{port}")

        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._host_edit.setEnabled(False)
        self._port_edit.setEnabled(False)
        self._status_label.setText("● Running")
        self._status_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")

    def _stop_server(self):
        if self._thread:
            self._thread.stop()
            self._thread.wait(3000)
            self._thread = None

        self._append_log("Server stopped.")
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._host_edit.setEnabled(True)
        self._port_edit.setEnabled(True)
        self._status_label.setText("● Stopped")
        self._status_label.setStyleSheet("color: #f38ba8; font-weight: bold;")

    def _append_log(self, msg: str):
        self._log.append(msg)

    def _on_server_error(self, tb: str):
        self._append_log("[ERROR] Server crashed:")
        for line in tb.splitlines():
            self._append_log(line)
        self._stop_server()
        QMessageBox.critical(self, "Server Error", tb)

    def closeEvent(self, event):
        if self._thread:
            self._stop_server()
        event.accept()


# ─────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    win = ServerManagerWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
