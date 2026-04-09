"""
NgweLwe System — Client Launcher
Server URL configure လုပ်ပြီး login screen ဖွင့်သည်။
Double-click NgweLweSystem.exe to run.
"""
import os
import sys
import json

# ── Resolve base directory ──
if getattr(sys, "frozen", False):
    _BASE = os.path.dirname(sys.executable)
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(_BASE, "client_config.json")
DEFAULT_HOST = "192.168.1.1"
DEFAULT_PORT = 8000

import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QDialog,
    QFormLayout, QMessageBox, QGroupBox,
)


# ─────────────────────────────────────────
# Config helpers
# ─────────────────────────────────────────
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"host": DEFAULT_HOST, "port": DEFAULT_PORT}


def save_config(host: str, port: int) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump({"host": host, "port": port}, f, indent=2)


def make_urls(host: str, port: int) -> tuple[str, str]:
    base = f"http://{host}:{port}"
    ws   = f"ws://{host}:{port}/ws"
    return base, ws


# ─────────────────────────────────────────
# Connection test thread
# ─────────────────────────────────────────
class ConnectThread(QThread):
    success = pyqtSignal()
    failure = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            r = requests.get(f"{self.url}/health", timeout=5)
            if r.status_code == 200:
                self.success.emit()
            else:
                self.failure.emit(f"Server မှ {r.status_code} response ရသည်")
        except requests.ConnectionError:
            self.failure.emit("Server ကို ချိတ်ဆက်၍ မရပါ\nIP/Port မှန်ကန်မှု စစ်ပါ")
        except requests.Timeout:
            self.failure.emit("Connection timeout — Server ဖွင့်ထားပါသလား?")
        except Exception as e:
            self.failure.emit(str(e))


# ─────────────────────────────────────────
# Server Config Dialog
# ─────────────────────────────────────────
STYLE = """
QWidget        { background:#1e1e2e; color:#cdd6f4; font-family:'Segoe UI'; font-size:13px; }
QGroupBox      { border:1px solid #45475a; border-radius:6px; margin-top:8px; padding-top:8px; }
QGroupBox::title { color:#89b4fa; padding:0 4px; }
QLineEdit      { background:#313244; border:1px solid #45475a; border-radius:4px;
                 padding:6px 10px; color:#cdd6f4; }
QLineEdit:focus { border-color:#89b4fa; }
QPushButton    { border-radius:5px; padding:8px 20px; font-weight:bold; }
"""


class ServerConfigDialog(QDialog):
    def __init__(self, parent=None, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        super().__init__(parent)
        self.setWindowTitle("ငွေလွှဲ System — Server ချိတ်ဆက်ရန်")
        self.setMinimumWidth(420)
        self.setStyleSheet(STYLE)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._result_host = host
        self._result_port = port
        self._thread: ConnectThread | None = None

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("ငွေလွှဲ System")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#89b4fa;")
        root.addWidget(title)

        sub = QLabel("Server IP နှင့် Port ထည့်ပြီး Connect နှိပ်ပါ")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color:#a6adc8; font-size:12px;")
        root.addWidget(sub)

        # Config box
        box = QGroupBox("Server Configuration")
        form = QFormLayout(box)
        form.setSpacing(10)

        self._host_edit = QLineEdit(host)
        self._host_edit.setPlaceholderText("e.g. 192.168.1.162")
        form.addRow("Server IP:", self._host_edit)

        self._port_edit = QLineEdit(str(port))
        self._port_edit.setPlaceholderText("e.g. 8000")
        form.addRow("Port:", self._port_edit)

        root.addWidget(box)

        # Status label
        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("font-size:12px;")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        # Connect button
        self._btn = QPushButton("Connect")
        self._btn.setStyleSheet("background:#89b4fa; color:#1e1e2e;")
        self._btn.clicked.connect(self._on_connect)
        self._port_edit.returnPressed.connect(self._on_connect)
        self._host_edit.returnPressed.connect(self._on_connect)
        root.addWidget(self._btn)

    # ── helpers ──
    def _set_status(self, msg: str, color: str):
        self._status.setText(msg)
        self._status.setStyleSheet(f"font-size:12px; color:{color};")

    def _on_connect(self):
        host = self._host_edit.text().strip()
        port_str = self._port_edit.text().strip()

        if not host:
            self._set_status("Server IP ထည့်ပါ", "#f38ba8")
            return
        try:
            port = int(port_str)
            assert 1 <= port <= 65535
        except Exception:
            self._set_status("Port မှန်ကန်သော နံပါတ် ထည့်ပါ (1-65535)", "#f38ba8")
            return

        base_url, _ = make_urls(host, port)
        self._set_status(f"Connecting to {base_url} ...", "#f9e2af")
        self._btn.setEnabled(False)
        QApplication.processEvents()

        self._thread = ConnectThread(base_url)
        self._thread.success.connect(lambda: self._on_success(host, port))
        self._thread.failure.connect(self._on_failure)
        self._thread.start()

    def _on_success(self, host: str, port: int):
        self._result_host = host
        self._result_port = port
        save_config(host, port)
        self._set_status("Connected!", "#a6e3a1")
        self.accept()

    def _on_failure(self, msg: str):
        self._set_status(msg, "#f38ba8")
        self._btn.setEnabled(True)

    # ── public result ──
    def result_host(self) -> str:
        return self._result_host

    def result_port(self) -> int:
        return self._result_port


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────
def main():
    app = QApplication(sys.argv)

    cfg = load_config()
    host = cfg.get("host", DEFAULT_HOST)
    port = cfg.get("port", DEFAULT_PORT)

    # Always show config dialog first run; otherwise try saved config silently
    first_run = not os.path.exists(CONFIG_FILE)

    if first_run:
        dlg = ServerConfigDialog(host=host, port=port)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        host = dlg.result_host()
        port = dlg.result_port()
    else:
        # Try saved config — if fail, show dialog
        base_url, _ = make_urls(host, port)
        try:
            r = requests.get(f"{base_url}/health", timeout=4)
            ok = r.status_code == 200
        except Exception:
            ok = False

        if not ok:
            dlg = ServerConfigDialog(host=host, port=port)
            dlg._set_status(
                f"Saved server ({host}:{port}) ကို ချိတ်ဆက်မရပါ\nIP/Port ပြင်ဆင်ပါ",
                "#f9e2af",
            )
            if dlg.exec() != QDialog.DialogCode.Accepted:
                sys.exit(0)
            host = dlg.result_host()
            port = dlg.result_port()

    # Set env vars for api_client.py
    base_url, ws_url = make_urls(host, port)
    os.environ["API_BASE_URL"] = base_url
    os.environ["WS_URL"]       = ws_url

    # Patch api_client BASE_URL (already imported by now)
    import services.api_client as _ac
    _ac.BASE_URL = base_url

    from services.api_client import ApiClient
    from views.login_view import LoginView

    api = ApiClient()

    # Attach "Change Server" action to login window
    login = LoginView(api)
    _patch_login_change_server(login, app, host, port)
    login.show()

    sys.exit(app.exec())


def _patch_login_change_server(login, app, host: str, port: int):
    """Add a small 'Change Server' link below the login form."""
    import services.api_client as _ac

    central = login.centralWidget()
    layout = central.layout()

    btn = QPushButton("⚙  Change Server")
    btn.setStyleSheet(
        "background:transparent; color:#585b70; font-size:11px; "
        "border:none; padding:4px;"
    )
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

    server_label = QLabel(f"Server: {host}:{port}")
    server_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    server_label.setStyleSheet("color:#45475a; font-size:11px;")
    layout.addWidget(server_label)

    def on_change():
        dlg = ServerConfigDialog(login, host=host, port=port)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_host = dlg.result_host()
            new_port = dlg.result_port()
            base_url, ws_url = make_urls(new_host, new_port)
            os.environ["API_BASE_URL"] = base_url
            os.environ["WS_URL"]       = ws_url
            _ac.BASE_URL = base_url
            server_label.setText(f"Server: {new_host}:{new_port}")

    btn.clicked.connect(on_change)


if __name__ == "__main__":
    main()
