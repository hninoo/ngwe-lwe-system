from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.api_client import ApiClient

# ── Style constants ──
BG_COLOR = "#1e1e2e"
TEXT_COLOR = "#cdd6f4"
INPUT_BG = "#313244"
INPUT_BORDER = "#585b70"
BTN_COLOR = "#89b4fa"
BTN_HOVER = "#74c7ec"
ERROR_COLOR = "#f38ba8"

WINDOW_WIDTH = 400
WINDOW_HEIGHT = 500

STYLESHEET = f"""
    QMainWindow {{ background-color: {BG_COLOR}; }}
    QLabel {{ color: {TEXT_COLOR}; }}
    QLineEdit {{
        background-color: {INPUT_BG};
        color: {TEXT_COLOR};
        border: 1px solid {INPUT_BORDER};
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 14px;
    }}
    QLineEdit:focus {{ border: 1px solid {BTN_COLOR}; }}
    QPushButton {{
        background-color: {BTN_COLOR};
        color: {BG_COLOR};
        border: none;
        border-radius: 8px;
        padding: 12px;
        font-size: 15px;
        font-weight: bold;
    }}
    QPushButton:hover {{ background-color: {BTN_HOVER}; }}
    QPushButton:pressed {{ background-color: {INPUT_BORDER}; }}
"""


class LoginView(QMainWindow):

    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self._api = api_client
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("ငွေလွှဲ System")
        self.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setStyleSheet(STYLESHEET)
        self._center_on_screen()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 60, 40, 40)
        layout.setSpacing(16)

        self._add_title(layout)
        self._add_inputs(layout)
        self._add_error_label(layout)
        self._add_login_button(layout)
        layout.addStretch()

    def _center_on_screen(self) -> None:
        screen = self.screen().availableGeometry()
        x = (screen.width() - WINDOW_WIDTH) // 2
        y = (screen.height() - WINDOW_HEIGHT) // 2
        self.move(x, y)

    def _add_title(self, layout: QVBoxLayout) -> None:
        title = QLabel("ငွေလွှဲ System")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addSpacing(20)

    def _add_inputs(self, layout: QVBoxLayout) -> None:
        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("Username")
        layout.addWidget(self._username_input)

        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("Password")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.returnPressed.connect(self._on_login)
        layout.addWidget(self._password_input)

    def _add_error_label(self, layout: QVBoxLayout) -> None:
        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setStyleSheet(f"color: {ERROR_COLOR}; font-size: 13px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

    def _add_login_button(self, layout: QVBoxLayout) -> None:
        btn = QPushButton("Login")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._on_login)
        layout.addWidget(btn)

    def _on_login(self) -> None:
        try:
            self._handle_login()
        except Exception as e:
            self._show_error(f"Error: {e}")

    def _handle_login(self) -> None:
        username = self._username_input.text().strip()
        password = self._password_input.text().strip()

        if not username or not password:
            self._show_error("Username နှင့် Password ထည့်ပါ")
            return

        try:
            self._api.login(username, password)
        except Exception:
            self._show_error("Login မအောင်မြင်ပါ — အချက်အလက် ပြန်စစ်ပါ")
            return

        self._error_label.setVisible(False)
        self._open_next_window()

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _open_next_window(self) -> None:
        try:
            role = self._api.user.get("role") if self._api.user else None
            window = self._create_role_window(role)
            self._next = window
            self._next.show()
            self.close()
        except Exception as e:
            self._show_error(f"Window ဖွင့်လို့မရပါ: {e}")

    def _create_role_window(self, role: str | None) -> QMainWindow:
        if role == "owner":
            try:
                from views.dashboard_view import DashboardView
                return DashboardView(self._api)
            except ImportError:
                return self._placeholder_window("Owner Dashboard")
        else:
            try:
                from views.transaction_view import TransactionView
                return TransactionView(self._api)
            except ImportError:
                return self._placeholder_window("Transaction Window")

    def _placeholder_window(self, title: str) -> QMainWindow:
        window = QMainWindow()
        window.setWindowTitle(f"ငွေလွှဲ — {title}")
        window.setFixedSize(WINDOW_WIDTH, WINDOW_HEIGHT)
        window.setStyleSheet(STYLESHEET)

        label = QLabel(f"{title}\n(Coming Soon)")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Segoe UI", 18))
        window.setCentralWidget(label)
        return window
