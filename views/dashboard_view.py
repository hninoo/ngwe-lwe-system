import json
import os
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.api_client import ApiClient

# ── Colors ──
BG_DARK = "#1e1e2e"
BG_SIDEBAR = "#181825"
BG_CARD = "#2a2a3e"
BG_CONTENT = "#1e1e2e"
TEXT_PRIMARY = "#cdd6f4"
TEXT_SECONDARY = "#a6adc8"
TEXT_MUTED = "#6c7086"
ACCENT_BLUE = "#89b4fa"
ACCENT_GREEN = "#a6e3a1"
ACCENT_RED = "#f38ba8"
ACCENT_YELLOW = "#f9e2af"
ACCENT_MAUVE = "#cba6f7"
ACCENT_TEAL = "#94e2d5"
BORDER_COLOR = "#313244"

SIDEBAR_WIDTH = 200
REFRESH_INTERVAL_MS = 30000
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8000/ws")

# ── Type badge colors ──
TYPE_COLORS = {
    "deposit": ACCENT_GREEN,
    "withdraw": ACCENT_RED,
    "transfer": ACCENT_BLUE,
    "exchange": ACCENT_YELLOW,
}

# ── Menu items ──
MENU_ITEMS = [
    ("Dashboard", "dashboard"),
    ("Transactions", "transactions"),
    ("Accounts", "accounts"),
    ("Reports", "reports"),
    ("Employees", "employees"),
    ("Settings", "settings"),
]


# ── WebSocket thread ──
class WebSocketThread(QThread):
    message_received = pyqtSignal(str)

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url
        self._running = True

    def run(self) -> None:
        try:
            import websockets.sync.client as ws_client
            with ws_client.connect(self._url) as ws:
                while self._running:
                    try:
                        msg = ws.recv(timeout=5)
                        self.message_received.emit(msg)
                    except TimeoutError:
                        continue
        except Exception:
            pass

    def stop(self) -> None:
        self._running = False


# ── Main stylesheet ──
STYLESHEET = f"""
    QMainWindow {{ background-color: {BG_DARK}; }}
    QWidget {{ color: {TEXT_PRIMARY}; }}
    QScrollArea {{ border: none; background-color: {BG_CONTENT}; }}
    QScrollBar:vertical {{
        background: {BG_DARK}; width: 8px; border: none;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_COLOR}; border-radius: 4px; min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QTableWidget {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER_COLOR};
        border-radius: 8px;
        gridline-color: {BORDER_COLOR};
        font-size: 12px;
    }}
    QTableWidget::item {{ padding: 6px; }}
    QHeaderView::section {{
        background-color: {BG_SIDEBAR};
        color: {TEXT_SECONDARY};
        border: none;
        padding: 8px;
        font-weight: bold;
        font-size: 12px;
    }}
"""


class DashboardView(QMainWindow):

    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self._api = api_client
        self._ws_thread: Optional[WebSocketThread] = None
        self._menu_buttons: dict[str, QPushButton] = {}
        self._stat_labels: dict[str, QLabel] = {}
        self._init_ui()
        self._start_timers()
        self._start_websocket()
        self._load_data()

    # ── UI Setup ──

    def _init_ui(self) -> None:
        self.setWindowTitle("ငွေလွှဲ — Owner Dashboard")
        self.setMinimumSize(1200, 750)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_sidebar())
        main_layout.addWidget(self._build_content(), 1)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar.setStyleSheet(f"background-color: {BG_SIDEBAR};")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._sidebar_logo())
        layout.addSpacing(10)
        for label, key in MENU_ITEMS:
            layout.addWidget(self._sidebar_button(label, key))
        layout.addStretch()
        layout.addWidget(self._sidebar_logout_button())

        return sidebar

    def _sidebar_logo(self) -> QLabel:
        logo = QLabel("ငွေလွှဲ System")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        logo.setStyleSheet(f"color: {ACCENT_BLUE}; padding: 20px 10px;")
        return logo

    def _sidebar_button(self, label: str, key: str) -> QPushButton:
        btn = QPushButton(f"  {label}")
        btn.setFixedHeight(42)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(self._menu_style(key == "dashboard"))
        btn.clicked.connect(lambda _, k=key: self._on_menu_click(k))
        self._menu_buttons[key] = btn
        return btn

    def _sidebar_logout_button(self) -> QPushButton:
        btn = QPushButton("  Logout")
        btn.setFixedHeight(42)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ text-align: left; background: transparent; color: {ACCENT_RED}; "
            f"border: none; padding-left: 20px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; }}"
        )
        btn.clicked.connect(self._on_logout)
        return btn

    def _menu_style(self, active: bool) -> str:
        bg = BG_CARD if active else "transparent"
        color = ACCENT_BLUE if active else TEXT_SECONDARY
        left = f"3px solid {ACCENT_BLUE}" if active else "3px solid transparent"
        return (
            f"QPushButton {{ text-align: left; background-color: {bg}; color: {color}; "
            f"border: none; border-left: {left}; padding-left: 20px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; }}"
        )

    def _build_content(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        container.setStyleSheet(f"background-color: {BG_CONTENT};")
        self._content_layout = QVBoxLayout(container)
        self._content_layout.setContentsMargins(24, 0, 24, 24)
        self._content_layout.setSpacing(20)

        self._content_layout.addWidget(self._build_top_bar())
        self._content_layout.addWidget(self._build_stats_row())
        self._content_layout.addWidget(self._section_label("Account Balances"))
        self._accounts_grid_container = QWidget()
        self._accounts_grid = QGridLayout(self._accounts_grid_container)
        self._accounts_grid.setSpacing(12)
        self._content_layout.addWidget(self._accounts_grid_container)
        self._content_layout.addWidget(self._section_label("Recent Transactions"))
        self._content_layout.addWidget(self._build_txn_table())
        self._content_layout.addStretch()

        scroll.setWidget(container)
        return scroll

    # ── Top bar ──

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(60)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 10, 0, 10)

        title = QLabel("Owner Dashboard")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addStretch()

        username = self._api.user.get("full_name", "") if self._api.user else ""
        user_label = QLabel(username)
        user_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(user_label)
        layout.addSpacing(16)

        self._time_label = QLabel()
        self._time_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        self._update_time()
        layout.addWidget(self._time_label)

        return bar

    def _update_time(self) -> None:
        try:
            self._time_label.setText(datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        except Exception:
            pass

    # ── Stats row ──

    def _build_stats_row(self) -> QFrame:
        row = QFrame()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        cards = [
            ("deposit", "ယနေ့အသွင်း", ACCENT_GREEN),
            ("withdraw", "ယနေ့အထုတ်", ACCENT_RED),
            ("transfer", "ဘဏ်ချင်းငွေလဲ", ACCENT_BLUE),
            ("exchange", "ကျပ်→ဘတ်", ACCENT_YELLOW),
            ("fees", "Fee+Commission", ACCENT_MAUVE),
        ]
        for key, label, color in cards:
            layout.addWidget(self._stat_card(key, label, color))

        return row

    def _stat_card(self, key: str, label: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; "
            f"border-left: 3px solid {color}; }}"
        )
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setFixedHeight(90)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)

        title = QLabel(label)
        title.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(title)

        value = QLabel("0")
        value.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        value.setStyleSheet(f"color: {color};")
        self._stat_labels[key] = value
        layout.addWidget(value)

        return card

    # ── Accounts grid ──

    def _rebuild_accounts_grid(self, accounts: list[dict]) -> None:
        while self._accounts_grid.count():
            item = self._accounts_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 3
        for i, acc in enumerate(accounts):
            row, col = divmod(i, cols)
            self._accounts_grid.addWidget(self._account_card(acc), row, col)

    def _account_card(self, acc: dict) -> QFrame:
        card = QFrame()
        card.setFixedHeight(100)
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 8px; "
            f"border: 1px solid {BORDER_COLOR}; }}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        top = QHBoxLayout()
        name = QLabel(acc.get("account_name", ""))
        name.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        top.addWidget(name)
        top.addStretch()
        badge = self._type_badge(acc.get("account_type", "personal"))
        top.addWidget(badge)
        layout.addLayout(top)

        phone = QLabel(acc.get("phone_number", ""))
        phone.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(phone)

        balance = float(acc.get("balance", 0))
        bal_label = QLabel(f"{balance:,.0f} MMK")
        bal_color = ACCENT_GREEN if balance >= 0 else ACCENT_RED
        bal_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        bal_label.setStyleSheet(f"color: {bal_color};")
        layout.addWidget(bal_label)

        return card

    def _type_badge(self, text: str) -> QLabel:
        color = ACCENT_TEAL if text == "agent" else TEXT_MUTED
        badge = QLabel(text.upper())
        badge.setStyleSheet(
            f"color: {color}; background-color: {BG_DARK}; border-radius: 4px; "
            f"padding: 2px 8px; font-size: 10px; font-weight: bold;"
        )
        return badge

    # ── Transactions table ──

    def _build_txn_table(self) -> QTableWidget:
        headers = [
            "Time", "Employee", "Type", "Service", "Account",
            "Amount", "Commission", "Fee", "Screenshot",
        ]
        self._txn_table = QTableWidget(0, len(headers))
        self._txn_table.setHorizontalHeaderLabels(headers)
        self._txn_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._txn_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._txn_table.setAlternatingRowColors(True)
        self._txn_table.verticalHeader().setVisible(False)
        self._txn_table.setMinimumHeight(300)

        header = self._txn_table.horizontalHeader()
        from PyQt6.QtWidgets import QHeaderView
        header.setStretchLastSection(True)
        for i in range(len(headers) - 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        return self._txn_table

    def _populate_txn_table(self, transactions: list[dict]) -> None:
        self._txn_table.setRowCount(len(transactions))
        for row, txn in enumerate(transactions):
            self._set_txn_row(row, txn)

    def _set_txn_row(self, row: int, txn: dict) -> None:
        created = txn.get("created_at", "")
        if isinstance(created, str) and len(created) > 16:
            created = created[11:16]

        txn_type = txn.get("transaction_type", "")
        color = TYPE_COLORS.get(txn_type, TEXT_PRIMARY)

        items = [
            str(created),
            str(txn.get("created_by", "")),
            txn_type,
            "",
            str(txn.get("account_id", "")),
            f"{float(txn.get('amount', 0)):,.0f}",
            f"{float(txn.get('commission_amount', 0)):,.0f}",
            f"{float(txn.get('customer_fee', 0)):,.0f}",
        ]
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col == 2:
                item.setForeground(self._q_color(color))
            self._txn_table.setItem(row, col, item)

        self._add_screenshot_button(row, txn)

    def _add_screenshot_button(self, row: int, txn: dict) -> None:
        path = txn.get("screenshot_path", "")
        btn = QPushButton("View" if path else "-")
        btn.setEnabled(bool(path))
        btn.setStyleSheet(
            f"QPushButton {{ background: {BG_DARK}; color: {ACCENT_BLUE}; "
            f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {BORDER_COLOR}; }}"
        )
        self._txn_table.setCellWidget(row, 8, btn)

    def _q_color(self, hex_color: str):
        from PyQt6.QtGui import QColor
        return QColor(hex_color)

    # ── Helpers ──

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        return label

    # ── Data loading ──

    def _load_data(self) -> None:
        try:
            self._load_summary()
            self._load_accounts()
            self._load_transactions()
        except Exception:
            pass

    def _load_summary(self) -> None:
        summary = self._api.get_dashboard_summary()
        self._stat_labels["deposit"].setText(f"{summary.get('total_deposit', 0):,.0f}")
        self._stat_labels["withdraw"].setText(f"{summary.get('total_withdraw', 0):,.0f}")
        self._stat_labels["transfer"].setText(f"{summary.get('total_transfer', 0):,.0f}")
        self._stat_labels["exchange"].setText(f"{summary.get('total_exchange', 0):,.0f}")
        fees = summary.get("total_customer_fees", 0) + summary.get("total_commission", 0)
        self._stat_labels["fees"].setText(f"{fees:,.0f}")

    def _load_accounts(self) -> None:
        accounts = self._api.get_dashboard_accounts()
        self._rebuild_accounts_grid(accounts)

    def _load_transactions(self) -> None:
        txns = self._api.get_recent_transactions(20)
        self._populate_txn_table(txns)

    # ── Timers ──

    def _start_timers(self) -> None:
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_time)
        self._clock_timer.start(1000)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh)
        self._refresh_timer.start(REFRESH_INTERVAL_MS)

    def _on_refresh(self) -> None:
        try:
            self._load_data()
        except Exception:
            pass

    # ── WebSocket ──

    def _start_websocket(self) -> None:
        self._ws_thread = WebSocketThread(WS_URL)
        self._ws_thread.message_received.connect(self._on_ws_message)
        self._ws_thread.start()

    def _on_ws_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
            if data.get("type") == "balance_update":
                accounts = data.get("accounts", [])
                self._rebuild_accounts_grid(accounts)
                self._load_summary()
                self._load_transactions()
        except Exception:
            pass

    # ── Menu ──

    def _on_menu_click(self, key: str) -> None:
        try:
            for k, btn in self._menu_buttons.items():
                btn.setStyleSheet(self._menu_style(k == key))
        except Exception:
            pass

    def _on_logout(self) -> None:
        try:
            self._cleanup()
            self._api.logout()
            from views.login_view import LoginView
            self._login = LoginView(self._api)
            self._login.show()
            self.close()
        except Exception:
            pass

    # ── Cleanup ──

    def _cleanup(self) -> None:
        if self._ws_thread:
            self._ws_thread.stop()
            self._ws_thread.wait(2000)
        self._clock_timer.stop()
        self._refresh_timer.stop()

    def closeEvent(self, event) -> None:
        self._cleanup()
        super().closeEvent(event)
