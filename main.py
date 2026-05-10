"""
Ngwe Lwe — unified launcher  (v1.0.0-beta)

Startup logic:
  1. Check %LOCALAPPDATA%/NgweLweSystem/app_config.json
       app_mode == "host"   → start local server automatically, open app
       app_mode == "client" → connect to saved/entered LAN server IP
  2. If no config file (dev / first run) → show StartupChoiceDialog
"""
import os
import sys
import json
import secrets
import socket
import time

# ── Resolve base directory (works both as .py and as PyInstaller exe) ──
if getattr(sys, "frozen", False):
    _BASE   = os.path.dirname(sys.executable)
    _BUNDLE = sys._MEIPASS  # type: ignore[attr-defined]
else:
    _BASE   = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE = _BASE

def _get_or_create_app_secret() -> str:
    """Read or generate a per-install secret stored in the app config directory."""
    config_dir = os.path.join(os.environ.get("LOCALAPPDATA", _BASE), "NgweLweSystem")
    os.makedirs(config_dir, exist_ok=True)
    secret_file = os.path.join(config_dir, "app_secret.key")
    if os.path.isfile(secret_file):
        try:
            with open(secret_file) as f:
                secret = f.read().strip()
            if len(secret) >= 32:
                return secret
        except Exception:
            pass
    secret = secrets.token_hex(32)
    try:
        with open(secret_file, "w") as f:
            f.write(secret)
    except Exception as exc:
        raise RuntimeError(
            f"Cannot write app secret to {secret_file}. "
            "All active sessions will be invalidated on restart. "
            f"Fix the file permissions or LOCALAPPDATA path. Underlying error: {exc}"
        ) from exc
    return secret


# ── Set env vars BEFORE any backend imports ──
os.environ.setdefault("DB_PATH",      os.path.join(_BASE, "ngwe_lwe.db"))
os.environ.setdefault("APP_SECRET",   _get_or_create_app_secret())
os.environ.setdefault("API_BASE_URL", "http://127.0.0.1:8000")
os.environ.setdefault("WS_URL",       "ws://127.0.0.1:8000/ws")

import requests
import uvicorn
from PyQt6.QtCore    import Qt, QThread, QTimer, QObject, pyqtSignal
from PyQt6.QtGui     import QColor, QFont, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication, QDialog, QWidget,
    QVBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QMessageBox,
)

from i18n import t


# ──────────────────────────────────────────────────────────
# App-wide constants
# ──────────────────────────────────────────────────────────
APP_VERSION     = "v1.0.0-beta"
APP_CONFIG_DIR  = os.path.join(os.environ.get("LOCALAPPDATA", _BASE), "NgweLweSystem")
APP_CONFIG_PATH = os.path.join(APP_CONFIG_DIR, "app_config.json")
# Icon path resolves correctly in both dev mode (_BUNDLE == project root)
# and frozen PyInstaller exe (_BUNDLE == sys._MEIPASS extraction dir)
_ICON_PATH      = os.path.join(_BUNDLE, "assets", "app_icon.ico")

_CLIENT_CONFIG  = os.path.join(_BASE, "client_config.json")
_DEFAULT_HOST   = "192.168.1.1"
_DEFAULT_PORT   = 8000
_LOCAL_PORT     = 8000
_SERVER_TIMEOUT = 20  # seconds to wait for local server to become ready

_STYLE = """
QWidget        { background:#1e1e2e; color:#cdd6f4; font-family:'Segoe UI'; font-size:13px; }
QGroupBox      { border:1px solid #45475a; border-radius:6px; margin-top:8px; padding-top:8px; }
QGroupBox::title { color:#89b4fa; padding:0 4px; }
QLineEdit      { background:#313244; border:1px solid #45475a; border-radius:4px;
                 padding:6px 10px; color:#cdd6f4; }
QLineEdit:focus { border-color:#89b4fa; }
QPushButton    { border-radius:5px; padding:8px 20px; font-weight:bold; }
"""


# ──────────────────────────────────────────────────────────
# Config / URL helpers
# ──────────────────────────────────────────────────────────
def _read_app_config() -> dict | None:
    """Return installer-written app_config, or None in dev/first-run mode."""
    if os.path.exists(APP_CONFIG_PATH):
        try:
            with open(APP_CONFIG_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _load_client_config() -> dict:
    if os.path.exists(_CLIENT_CONFIG):
        try:
            with open(_CLIENT_CONFIG) as f:
                return json.load(f)
        except Exception:
            pass
    return {"host": _DEFAULT_HOST, "port": _DEFAULT_PORT}


def _save_client_config(host: str, port: int) -> None:
    try:
        with open(_CLIENT_CONFIG, "w") as f:
            json.dump({"host": host, "port": port}, f, indent=2)
    except Exception:
        pass


def _make_urls(host: str, port: int) -> tuple[str, str]:
    return f"http://{host}:{port}", f"ws://{host}:{port}/ws"


def get_server_ip() -> str:
    """Return the machine's LAN IP (the interface used for outbound traffic)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())


def _apply_urls(base_url: str, ws_url: str) -> None:
    """Sync env vars and patch the already-imported api_client module."""
    os.environ["API_BASE_URL"] = base_url
    os.environ["WS_URL"]       = ws_url
    try:
        import services.api_client as _ac
        _ac.BASE_URL = base_url
    except Exception:
        pass


# ──────────────────────────────────────────────────────────
# Local server thread
# ──────────────────────────────────────────────────────────
class _NoSignalServer(uvicorn.Server):
    """Uvicorn without OS signal handlers (signal.signal only works in main thread)."""
    def install_signal_handlers(self) -> None:
        pass


class ServerThread(QThread):
    error_signal = pyqtSignal(str)

    def __init__(self, host: str = "127.0.0.1", port: int = _LOCAL_PORT) -> None:
        super().__init__()
        self.host = host
        self.port = port
        self._server: _NoSignalServer | None = None

    def run(self) -> None:
        import traceback
        try:
            from backend.main import app as fastapi_app
            cfg = uvicorn.Config(
                fastapi_app,
                host=self.host,
                port=self.port,
                log_level="warning",
                access_log=False,
                use_colors=False,
            )
            self._server = _NoSignalServer(cfg)
            self._server.run()
        except Exception:
            self.error_signal.emit(traceback.format_exc())

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True


# ──────────────────────────────────────────────────────────
# Server readiness watcher (non-blocking QTimer poll)
# ──────────────────────────────────────────────────────────
class _ServerWatcher(QObject):
    ready  = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, url: str, timeout: int = _SERVER_TIMEOUT) -> None:
        super().__init__()
        self._url      = url
        self._deadline = time.time() + timeout
        self._timer    = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._timer.start()

    def _poll(self) -> None:
        if time.time() > self._deadline:
            self._timer.stop()
            self.failed.emit(t("server_start_failed"))
            return
        try:
            r = requests.get(self._url, timeout=0.5)
            if r.status_code == 200:
                self._timer.stop()
                self.ready.emit()
        except Exception:
            pass


# ──────────────────────────────────────────────────────────
# Splash screen (shown while local server starts)
# ──────────────────────────────────────────────────────────
class _SplashScreen(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(t("app_title"))
        self.setFixedSize(340, 130)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setStyleSheet("background:#1e1e2e;")

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel(t("app_title"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        lbl.setStyleSheet("color:#89b4fa; background:transparent;")
        layout.addWidget(lbl)

        self._status = QLabel(t("server_starting_msg"))
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("color:#a6adc8; font-size:13px; background:transparent;")
        layout.addWidget(self._status)

        geo = QApplication.primaryScreen().availableGeometry()
        self.move((geo.width() - self.width()) // 2, (geo.height() - self.height()) // 2)

    def set_status(self, text: str) -> None:
        self._status.setText(text)
        QApplication.processEvents()


# ──────────────────────────────────────────────────────────
# LAN connection test thread
# ──────────────────────────────────────────────────────────
class _ConnectThread(QThread):
    success = pyqtSignal()
    failure = pyqtSignal(str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    def run(self) -> None:
        try:
            r = requests.get(f"{self._url}/health", timeout=5)
            if r.status_code == 200:
                self.success.emit()
            else:
                self.failure.emit(t("err_status_code", code=r.status_code))
        except requests.ConnectionError:
            self.failure.emit(t("err_cannot_reach"))
        except requests.Timeout:
            self.failure.emit(t("err_timeout"))
        except Exception as e:
            self.failure.emit(str(e))


# ──────────────────────────────────────────────────────────
# Server config dialog (LAN join / client mode)
# ──────────────────────────────────────────────────────────
class ServerConfigDialog(QDialog):
    def __init__(self, parent=None, host: str = _DEFAULT_HOST, port: int = _DEFAULT_PORT) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("server_conn_title"))
        self.setMinimumWidth(420)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self._result_host = host
        self._result_port = port
        self._thread: _ConnectThread | None = None

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 20, 20, 20)

        title = QLabel(t("app_title"))
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#89b4fa;")
        root.addWidget(title)

        sub = QLabel(t("server_sub"))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color:#a6adc8; font-size:12px;")
        root.addWidget(sub)

        box = QGroupBox(t("server_config_box"))
        form = QFormLayout(box)
        form.setSpacing(10)
        self._host_edit = QLineEdit(host)
        self._host_edit.setPlaceholderText("e.g. 192.168.1.162")
        form.addRow(t("server_ip_label"), self._host_edit)
        self._port_edit = QLineEdit(str(port))
        self._port_edit.setPlaceholderText("e.g. 8000")
        form.addRow(t("port_label"), self._port_edit)
        root.addWidget(box)

        self._status_lbl = QLabel("")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setWordWrap(True)
        root.addWidget(self._status_lbl)

        self._btn = QPushButton(t("connect_btn"))
        self._btn.setStyleSheet("background:#89b4fa; color:#1e1e2e;")
        self._btn.clicked.connect(self._on_connect)
        self._host_edit.returnPressed.connect(self._on_connect)
        self._port_edit.returnPressed.connect(self._on_connect)
        root.addWidget(self._btn)

    def set_initial_status(self, msg: str, color: str = "#f9e2af") -> None:
        self._set_status(msg, color)

    def _set_status(self, msg: str, color: str) -> None:
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"font-size:12px; color:{color};")

    def _on_connect(self) -> None:
        host     = self._host_edit.text().strip()
        port_str = self._port_edit.text().strip()
        if not host:
            self._set_status(t("ip_required"), "#f38ba8")
            return
        try:
            port = int(port_str)
            assert 1 <= port <= 65535
        except Exception:
            self._set_status(t("port_invalid"), "#f38ba8")
            return

        base_url, _ = _make_urls(host, port)
        self._set_status(t("connecting_to", url=base_url), "#f9e2af")
        self._btn.setEnabled(False)

        self._thread = _ConnectThread(base_url)
        self._thread.success.connect(lambda: self._on_success(host, port))
        self._thread.failure.connect(self._on_failure)
        self._thread.start()

    def _on_success(self, host: str, port: int) -> None:
        self._result_host = host
        self._result_port = port
        _save_client_config(host, port)
        self._set_status(t("connected_msg"), "#a6e3a1")
        self.accept()

    def _on_failure(self, msg: str) -> None:
        self._set_status(msg, "#f38ba8")
        self._btn.setEnabled(True)

    def result_host(self) -> str:
        return self._result_host

    def result_port(self) -> int:
        return self._result_port


# ──────────────────────────────────────────────────────────
# Startup choice dialog (dev / first-run only)
# ──────────────────────────────────────────────────────────
class _StartupChoiceDialog(QDialog):
    HOST_MODE = "host"
    JOIN_MODE = "join"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(t("app_title"))
        self.setMinimumWidth(440)
        self.setStyleSheet(_STYLE)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.mode: str = ""

        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(24, 24, 24, 24)

        title = QLabel(t("app_title"))
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color:#89b4fa;")
        root.addWidget(title)

        ver = QLabel(APP_VERSION)
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("color:#585b70; font-size:11px;")
        root.addWidget(ver)

        sub = QLabel(t("startup_choice_sub"))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color:#a6adc8; font-size:12px;")
        root.addWidget(sub)

        host_btn = QPushButton(t("choice_host_btn"))
        host_btn.setMinimumHeight(56)
        host_btn.setStyleSheet(
            "background:#a6e3a1; color:#1e1e2e; font-size:14px; border-radius:8px;"
        )
        host_btn.clicked.connect(lambda: self._pick(self.HOST_MODE))
        root.addWidget(host_btn)

        host_desc = QLabel(t("choice_host_desc"))
        host_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        host_desc.setStyleSheet("color:#6c7086; font-size:11px;")
        host_desc.setWordWrap(True)
        root.addWidget(host_desc)

        join_btn = QPushButton(t("choice_join_btn"))
        join_btn.setMinimumHeight(56)
        join_btn.setStyleSheet(
            "background:#89b4fa; color:#1e1e2e; font-size:14px; border-radius:8px;"
        )
        join_btn.clicked.connect(lambda: self._pick(self.JOIN_MODE))
        root.addWidget(join_btn)

        join_desc = QLabel(t("choice_join_desc"))
        join_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        join_desc.setStyleSheet("color:#6c7086; font-size:11px;")
        join_desc.setWordWrap(True)
        root.addWidget(join_desc)

    def _pick(self, mode: str) -> None:
        self.mode = mode
        self.accept()


# ──────────────────────────────────────────────────────────
# Open login window
# ──────────────────────────────────────────────────────────
def _repository_for_transaction_type(transaction_type: str):
    normalized = (transaction_type or "").strip().lower()
    if normalized == "cash_in":
        from repositories.cash_in_repo import CashInRepository
        return CashInRepository()
    if normalized == "cash_out":
        from repositories.cash_out_repo import CashOutRepository
        return CashOutRepository()
    if normalized == "transfer":
        from repositories.transfer_repo import TransferRepository
        return TransferRepository()
    if normalized == "exchange":
        from repositories.exchange_repo import ExchangeRepository
        return ExchangeRepository()
    raise ValueError(f"Unknown transaction type: {transaction_type}")


def _open_transaction_from_dashboard(dashboard, api, transaction_type: str) -> None:
    from views.transaction_view import TransactionView

    repository = _repository_for_transaction_type(transaction_type)
    transaction_window = TransactionView(
        api,
        transaction_type=transaction_type,
        operation_repository=repository,
    )
    dashboard._next = transaction_window
    transaction_window.show()
    dashboard.close()


def _open_login(
    app: QApplication,
    server_thread: "ServerThread | None",
    *,
    host_mode: bool,
    lan_host: str = "127.0.0.1",
    lan_port: int = _LOCAL_PORT,
) -> None:
    import services.api_client as _ac
    from services.api_client import ApiClient
    from views.login_view import LoginView

    api = ApiClient()

    def _connect_dashboard(dashboard) -> None:
        dashboard.switch_to_transaction.connect(
            lambda transaction_type, d=dashboard: _open_transaction_from_dashboard(
                d,
                api,
                transaction_type,
            )
        )

    window = LoginView(api, dashboard_controller=_connect_dashboard)
    window.set_version(APP_VERSION)

    if host_mode:
        window._change_server_btn.setVisible(False)
        window._server_label.setText(
            t("server_label", host="localhost", port=_LOCAL_PORT)
        )
        window.show_host_info(get_server_ip(), _LOCAL_PORT)
    else:
        _host = [lan_host]
        _port = [lan_port]
        window._server_label.setText(t("server_label", host=_host[0], port=_port[0]))

        def _on_change() -> None:
            dlg = ServerConfigDialog(window, host=_host[0], port=_port[0])
            if dlg.exec() == QDialog.DialogCode.Accepted:
                _host[0] = dlg.result_host()
                _port[0] = dlg.result_port()
                base_url, ws_url = _make_urls(_host[0], _port[0])
                _apply_urls(base_url, ws_url)
                window._server_label.setText(
                    t("server_label", host=_host[0], port=_port[0])
                )

        window._change_server_btn.clicked.connect(_on_change)

    if server_thread is not None:
        app.aboutToQuit.connect(lambda: (server_thread.stop(), server_thread.wait(4000)))

    window.show()


# ──────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)

    # Fusion + dark palette: Fusion respects QPalette for rendering internals
    # (combo box display-area text, spin box buttons, etc.) whereas the Windows 11
    # native renderer ignores stylesheet colours entirely.
    app.setStyle("Fusion")
    _dark = QPalette()
    _dark.setColor(QPalette.ColorRole.Window,          QColor("#1e1e2e"))
    _dark.setColor(QPalette.ColorRole.WindowText,      QColor("#cdd6f4"))
    _dark.setColor(QPalette.ColorRole.Base,            QColor("#313244"))
    _dark.setColor(QPalette.ColorRole.AlternateBase,   QColor("#2a2a3e"))
    _dark.setColor(QPalette.ColorRole.Text,            QColor("#cdd6f4"))
    _dark.setColor(QPalette.ColorRole.BrightText,      QColor("#cdd6f4"))
    _dark.setColor(QPalette.ColorRole.Button,          QColor("#313244"))
    _dark.setColor(QPalette.ColorRole.ButtonText,      QColor("#cdd6f4"))
    _dark.setColor(QPalette.ColorRole.Highlight,       QColor("#89b4fa"))
    _dark.setColor(QPalette.ColorRole.HighlightedText, QColor("#1e1e2e"))
    _dark.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#2a2a3e"))
    _dark.setColor(QPalette.ColorRole.ToolTipText,     QColor("#cdd6f4"))
    _dark.setColor(QPalette.ColorRole.PlaceholderText, QColor("#6c7086"))
    app.setPalette(_dark)

    # Set the app icon once — all windows and dialogs in this process inherit it
    _icon = QIcon(_ICON_PATH)
    if not _icon.isNull():
        app.setWindowIcon(_icon)

    # ── Determine mode from installer config or choice dialog ──
    app_cfg = _read_app_config()

    if app_cfg is not None:
        mode = app_cfg.get("app_mode", "client")
        cfg_host = app_cfg.get("host", _DEFAULT_HOST)
        cfg_port = int(app_cfg.get("port", _DEFAULT_PORT))
    else:
        # Dev / first-run: show choice dialog
        choice = _StartupChoiceDialog()
        if choice.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
        mode     = choice.mode
        cfg_host = _DEFAULT_HOST
        cfg_port = _DEFAULT_PORT

    # ── HOST MODE ─────────────────────────────────────────
    if mode == "host":
        base_url, ws_url = _make_urls("127.0.0.1", _LOCAL_PORT)
        _apply_urls(base_url, ws_url)

        splash = _SplashScreen()
        splash.show()
        QApplication.processEvents()

        server_thread = ServerThread(host="127.0.0.1", port=_LOCAL_PORT)

        def _on_server_error(tb: str) -> None:
            splash.close()
            QMessageBox.critical(
                None, t("server_error_title"),
                t("server_start_failed") + "\n\n" + tb,
            )
            sys.exit(1)

        server_thread.error_signal.connect(_on_server_error)
        server_thread.start()

        watcher = _ServerWatcher(f"{base_url}/health")

        def _on_ready() -> None:
            splash.set_status(t("server_ready_msg"))
            QTimer.singleShot(300, lambda: (
                splash.close(),
                _open_login(app, server_thread, host_mode=True),
            ))

        def _on_timeout(msg: str) -> None:
            splash.close()
            QMessageBox.critical(None, t("server_error_title"), msg)
            sys.exit(1)

        watcher.ready.connect(_on_ready)
        watcher.failed.connect(_on_timeout)
        watcher.start()

    # ── CLIENT / JOIN MODE ────────────────────────────────
    else:
        # Use host from app_config if present; else fall back to client_config.json
        if app_cfg and "host" in app_cfg:
            host = cfg_host
            port = cfg_port
        else:
            saved = _load_client_config()
            host  = saved.get("host", _DEFAULT_HOST)
            port  = saved.get("port", _DEFAULT_PORT)

        # Try saved host silently; show dialog on failure
        connected = False
        try:
            base_url, _ = _make_urls(host, port)
            r = requests.get(f"{base_url}/health", timeout=3)
            connected = r.status_code == 200
        except Exception:
            pass

        if not connected:
            dlg = ServerConfigDialog(host=host, port=port)
            if os.path.exists(_CLIENT_CONFIG) or (app_cfg and "host" in app_cfg):
                dlg.set_initial_status(
                    t("saved_server_fail", host=host, port=port), "#f9e2af"
                )
            if dlg.exec() != QDialog.DialogCode.Accepted:
                sys.exit(0)
            host = dlg.result_host()
            port = dlg.result_port()

        base_url, ws_url = _make_urls(host, port)
        _apply_urls(base_url, ws_url)
        _open_login(app, None, host_mode=False, lan_host=host, lan_port=port)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
