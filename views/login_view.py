from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from i18n import t, set_locale, get_locale, on_change
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
WINDOW_HEIGHT = 520

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
    QComboBox {{
        background-color: {INPUT_BG};
        color: {TEXT_COLOR};
        border: 1px solid {INPUT_BORDER};
        border-radius: 5px;
        padding: 2px 6px;
        font-size: 11px;
    }}
    QComboBox::drop-down {{ border: none; }}
    QComboBox QAbstractItemView {{
        background-color: {INPUT_BG};
        color: {TEXT_COLOR};
        selection-background-color: #45475a;
    }}
"""


class LoginView(QMainWindow):

    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self._api = api_client
        self._init_ui()
        on_change(self.retranslate_ui)

    def _init_ui(self) -> None:
        self.setWindowTitle(t("login_title"))
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
        self._add_server_footer(layout)

    def _center_on_screen(self) -> None:
        screen = self.screen().availableGeometry()
        x = (screen.width() - WINDOW_WIDTH) // 2
        y = (screen.height() - WINDOW_HEIGHT) // 2
        self.move(x, y)

    def _add_title(self, layout: QVBoxLayout) -> None:
        self._title_label = QLabel(t("login_title"))
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        layout.addWidget(self._title_label)
        layout.addSpacing(20)

    def _add_inputs(self, layout: QVBoxLayout) -> None:
        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText(t("username_placeholder"))
        layout.addWidget(self._username_input)

        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText(t("password_placeholder"))
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
        self._login_btn = QPushButton(t("sign_in"))
        self._login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_btn.clicked.connect(self._on_login)
        layout.addWidget(self._login_btn)

    def _add_server_footer(self, layout: QVBoxLayout) -> None:
        """Server info + Change Server button + language switcher."""
        row = QHBoxLayout()

        self._server_label = QLabel(t("server_label", host="localhost", port=8000))
        self._server_label.setStyleSheet("color: #585b70; font-size: 11px;")
        row.addWidget(self._server_label, alignment=Qt.AlignmentFlag.AlignLeft)

        row.addStretch()

        # Language switcher
        self._lang_combo = QComboBox()
        self._lang_combo.addItem("မြန်မာ", "mm")
        self._lang_combo.addItem("English", "en")
        # Pre-select current locale
        idx = 0 if get_locale() == "mm" else 1
        self._lang_combo.setCurrentIndex(idx)
        self._lang_combo.currentIndexChanged.connect(self._on_lang_changed)
        row.addWidget(self._lang_combo)

        self._change_server_btn = QPushButton(t("change_server"))
        self._change_server_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._change_server_btn.setStyleSheet(
            "background:transparent; color:#89b4fa; font-size:11px; "
            "border:none; padding:2px 6px; text-decoration:underline;"
        )
        row.addWidget(self._change_server_btn, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(row)

    def _on_lang_changed(self, index: int) -> None:
        locale = self._lang_combo.itemData(index)
        set_locale(locale)

    def retranslate_ui(self) -> None:
        """Re-apply all translatable strings after a locale change."""
        self.setWindowTitle(t("login_title"))
        self._title_label.setText(t("login_title"))
        self._username_input.setPlaceholderText(t("username_placeholder"))
        self._password_input.setPlaceholderText(t("password_placeholder"))
        self._login_btn.setText(t("sign_in"))
        self._change_server_btn.setText(t("change_server"))
        # Keep server label text but re-apply translated template if possible
        current = self._server_label.text()
        if current:
            self._server_label.setText(current)  # server label is set externally

    def _on_login(self) -> None:
        try:
            self._handle_login()
        except Exception as e:
            self._show_error(f"Error: {e}")

    def _handle_login(self) -> None:
        username = self._username_input.text().strip()
        password = self._password_input.text().strip()

        if not username or not password:
            self._show_error(t("login_empty_error"))
            return

        self._error_label.setVisible(False)
        self._show_error(t("signing_in"))
        self._error_label.setStyleSheet(f"color: {TEXT_COLOR}; font-size: 13px;")
        QApplication.processEvents()

        try:
            self._api.login(username, password)
        except Exception:
            self._show_error(t("login_fail"))
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
            self._show_error(t("window_open_fail", error=e))

    def _create_role_window(self, role: str | None) -> QMainWindow:
        if role == "owner":
            from views.dashboard_view import DashboardView
            return DashboardView(self._api)

        if role == "cashier":
            from views.cashier_view import CashierView
            return CashierView(self._api)

        from views.transaction_view import TransactionView
        main_window = TransactionView(self._api)
        self._check_pending_float(main_window)
        return main_window

    def _check_pending_float(self, parent: QMainWindow) -> None:
        try:
            pending = self._api.get_my_pending_float()
            if pending is None:
                return
            from views.receive_float_dialog import ReceiveFloatDialog
            dlg = ReceiveFloatDialog(self._api, pending, parent)
            dlg.exec()
        except Exception:
            pass
