import json
import os
from datetime import datetime, timezone, timedelta

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import on_change, t
from services.api_client import ApiClient
from views.admin_page import CommissionTierSubView, ExchangeRateSubView, PasswordSubView
from views.daily_closing_view import DailyClosingView
from views.server_info_view import ServerInfoSubView
from views.settings.account_settings_view import AccountSettingsView
from views.settings.activity_log_view import ActivityLogView
from views.settings.cash_float_admin_view import CashFloatAdminView
from views.settings.company_settings_view import CompanySettingsView
from views.settings.service_type_settings_view import ServiceTypeSettingsView
from views.settings.transaction_admin_view import TransactionAdminView
from views.settings.user_settings_view import UserSettingsView
from views.transaction_view import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_MAUVE,
    ACCENT_RED,
    ACCENT_TEAL,
    ACCENT_YELLOW,
    BG_CARD,
    BG_DARK,
    BG_INPUT,
    BORDER_COLOR,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

MMT = timezone(timedelta(hours=6, minutes=30))
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8000/ws")
SIDEBAR_WIDTH = 240
REFRESH_INTERVAL_MS = 30000

_OWNER_SIDEBAR_GROUPS: list[tuple[str | None, list[tuple[str, int, str]]]] = [
    (None, [("nav_dashboard", 0, "D")]),
    ("nav_group_transactions", [
        ("admin_all_transactions", 1, "T"),
        ("admin_activity_logs", 2, "L"),
    ]),
    ("nav_group_accounts", [("nav_accounts", 3, "A")]),
    ("nav_group_reports", [("nav_reports", 4, "R")]),
    ("admin_group_staff", [("nav_users", 5, "U")]),
    ("admin_group_master", [
        ("admin_companies", 6, "C"),
        ("admin_service_types", 7, "S"),
        ("admin_commission_tiers", 8, "%"),
        ("admin_exchange_rate", 9, "X"),
    ]),
    ("admin_group_operations", [
        ("admin_cash_floats", 10, "F"),
        ("nav_daily_closing", 13, "DC"),
    ]),
    ("admin_group_system", [
        ("admin_server_connection", 11, "N"),
        ("admin_change_password", 12, "P"),
    ]),
]

OWNER_STYLESHEET = f"""
    QMainWindow {{ background-color: {BG_DARK}; }}
    QWidget {{ color: {TEXT_PRIMARY}; }}
    QScrollArea {{ border: none; background-color: {BG_DARK}; }}
    QTableWidget {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER_COLOR};
        border-radius: 8px;
        gridline-color: {BORDER_COLOR};
        font-size: 12px;
    }}
    QTableWidget::item {{ padding: 6px; }}
    QHeaderView::section {{
        background-color: {BG_DARK};
        color: {TEXT_SECONDARY};
        border: none;
        padding: 8px;
        font-weight: bold;
        font-size: 12px;
    }}
"""


class WebSocketThread(QThread):
    message_received = pyqtSignal(str)

    def __init__(self, url: str, ticket_fn=None) -> None:
        super().__init__()
        self._base_url = url
        self._ticket_fn = ticket_fn
        self._running = True
        self._ws = None

    def run(self) -> None:
        try:
            import websockets.sync.client as ws_client
            ticket = self._ticket_fn() if self._ticket_fn else ""
            connect_url = f"{self._base_url}?ticket={ticket}" if ticket else self._base_url
            with ws_client.connect(connect_url) as ws:
                self._ws = ws
                while self._running:
                    try:
                        msg = ws.recv(timeout=5)
                        self.message_received.emit(msg)
                    except TimeoutError:
                        pass
        except Exception:
            pass
        finally:
            self._ws = None

    def stop(self) -> None:
        self._running = False
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass


class DashboardPage(QWidget):
    """Six-card launcher for employee transactions and utility screens."""

    def __init__(self, api: ApiClient, navigate) -> None:
        super().__init__()
        self._api = api
        self._navigate = navigate
        self._employee_floats: list[dict] = []
        self._employee_float: dict | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        top = QHBoxLayout()
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        title = QLabel(f"Welcome, {fullname}")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        top.addWidget(title)
        top.addStretch()

        self._time_label = QLabel()
        self._time_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        top.addWidget(self._time_label)

        logout_btn = QPushButton(t("logout"))
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT_RED}; color: {BG_DARK}; "
            f"border: none; border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: bold; }}"
        )
        logout_btn.clicked.connect(lambda: self._navigate(-1))
        top.addWidget(logout_btn)
        layout.addLayout(top)
        layout.addStretch()

        if self._is_employee():
            self._employee_floats = self._load_employee_floats()
            self._employee_float = self._load_employee_float()

        grid = QGridLayout()
        grid.setSpacing(18)
        cards = [
            ("Cash In", "Receiving digital, paying physical cash.", "CI", ACCENT_GREEN, 1, "cash_in"),
            ("Cash Out", "Receiving physical cash, sending digital.", "CO", ACCENT_RED, 1, "cash_out"),
            ("Transfer", "Bank-to-bank movement.", "TR", ACCENT_BLUE, 1, "transfer"),
            ("Exchange", "Currency conversion.", "EX", ACCENT_YELLOW, 1, "exchange"),
            ("Vault", "Denominations and cash total.", "VA", ACCENT_TEAL, 4, "vault"),
            ("History", "View all past records.", "HI", ACCENT_MAUVE, 2, None),
            ("Profile", "User settings and account info.", "PR", ACCENT_TEAL, 3, None),
        ]
        visible_cards = [
            card for card in cards
            if card[5] != "vault" or self._is_employee()
        ]
        for idx, (title, desc, icon, color, page, txn_type) in enumerate(visible_cards):
            row, col = divmod(idx, 3)
            disabled = txn_type == "cash_out" and self._is_employee() and not self._employee_has_cash()
            grid.addWidget(
                self._card(title, desc, icon, color, page, txn_type, disabled=disabled),
                row,
                col,
            )
        layout.addLayout(grid)
        layout.addStretch()

    def _is_employee(self) -> bool:
        return bool(self._api.user and self._api.user.get("role") == "employee")

    def _load_employee_floats(self) -> list[dict]:
        try:
            return self._api.get_floats()
        except Exception:
            return []

    def _load_employee_float(self) -> dict | None:
        active = [f for f in self._employee_floats if f.get("status") == "ACTIVE"]
        if not active:
            return None
        return max(active, key=lambda f: f.get("received_at") or f.get("created_at") or "")

    def _employee_has_cash(self) -> bool:
        if not self._employee_float:
            return False
        return float(self._employee_float.get("current_balance") or 0) > 0

    def _vault_card(self) -> QFrame:
        cash = float(self._employee_float.get("current_balance") or 0) if self._employee_float else 0
        status = self._employee_float.get("status", "NO ACTIVE FLOAT") if self._employee_float else "NO ACTIVE FLOAT"
        color = ACCENT_GREEN if cash > 0 else ACCENT_RED
        card = QFrame()
        card.setMinimumHeight(110)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; "
            f"border: 1px solid {BORDER_COLOR}; border-left: 5px solid {color}; }}"
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(22, 16, 22, 16)
        row.setSpacing(14)

        title_col = QVBoxLayout()
        title = QLabel("Vault")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {color}; border: none;")
        subtitle = QLabel("ငွေသားသေတ္တာ")
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; border: none;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        row.addLayout(title_col)
        row.addStretch()

        status_label = QLabel(status.replace("_", " ").title())
        status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; border: none;")
        row.addWidget(status_label)

        amount = QLabel(f"{cash:,.0f} MMK")
        amount.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        amount.setStyleSheet(f"color: {color}; border: none;")
        row.addWidget(amount)
        return card

    def _card(
        self,
        title: str,
        desc: str,
        icon: str,
        color: str,
        page: int,
        transaction_type: str | None,
        disabled: bool = False,
    ) -> QFrame:
        card = QFrame()
        card.setMinimumHeight(170)
        card.setCursor(Qt.CursorShape.ForbiddenCursor if disabled else Qt.CursorShape.PointingHandCursor)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if disabled:
            card.setStyleSheet(
                f"QFrame {{ background-color: {BG_CARD}; border-radius: 12px; "
                f"border: 1px solid {BORDER_COLOR}; border-left: 5px solid {TEXT_MUTED}; }}"
            )
            color = TEXT_MUTED
        else:
            card.setStyleSheet(
                f"QFrame {{ background-color: {BG_CARD}; border-radius: 12px; "
                f"border: 1px solid {BORDER_COLOR}; border-left: 5px solid {color}; }}"
                f"QFrame:hover {{ background-color: {BG_INPUT}; border: 1px solid {color}; border-left: 5px solid {color}; }}"
            )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        icon_label.setStyleSheet(f"color: {color}; border: none; background: transparent;")
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {color}; border: none;")
        layout.addWidget(title_label)

        desc_label = QLabel("Your vault has no cash. Contact cashier." if disabled else desc)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; border: none;")
        layout.addWidget(desc_label)
        if disabled:
            card.mousePressEvent = lambda e: self._show_no_cash_message()
        else:
            card.mousePressEvent = lambda e, p=page, tx=transaction_type: self._navigate(p, tx)
        return card

    def _show_vault_details(self) -> None:
        if not self._employee_float:
            history = self._format_float_history()
            QMessageBox.information(
                self,
                "Vault",
                "No active vault found.\n\n" + history,
            )
            return

        float_id = self._employee_float.get("id")
        try:
            balance = self._api.get_float_denomination_balance(float_id)
        except Exception as exc:
            QMessageBox.warning(self, "Vault", f"Unable to load vault details.\n{exc}")
            return

        denoms = balance.get("denominations", {}) or {}
        lines = ["Denominations:"]
        for denom in sorted((int(k) for k in denoms.keys()), reverse=True):
            qty = int(denoms.get(str(denom), 0) or 0)
            if qty:
                lines.append(f"{denom:,.0f} MMK x {qty} = {denom * qty:,.0f} MMK")
        if len(lines) == 1:
            lines.append("No cash denominations.")

        total = float(balance.get("total") or self._employee_float.get("current_balance") or 0)
        lines.append("")
        lines.append(f"Total Cash: {total:,.0f} MMK")
        lines.append("")
        lines.append(self._format_float_history())
        QMessageBox.information(self, "Vault", "\n".join(lines))

    def _format_float_history(self) -> str:
        if not self._employee_floats:
            return "Vault History:\nNo vault history."
        lines = ["Vault History:"]
        for f in self._employee_floats[:5]:
            status = str(f.get("status") or "-").replace("_", " ").title()
            amount = float(f.get("current_balance") or f.get("total_amount") or 0)
            created = f.get("received_at") or f.get("created_at") or ""
            lines.append(f"#{f.get('id')}  {status}  {amount:,.0f} MMK  {created}")
        return "\n".join(lines)

    def _show_no_cash_message(self) -> None:
        QMessageBox.warning(
            self,
            "No Cash In Vault",
            "Your vault has no cash. Please receive cash from the cashier before using Cash Out.",
        )

    def update_time(self) -> None:
        self._time_label.setText(datetime.now(MMT).strftime("%d-%m-%Y  %I:%M:%S %p"))


def _owner_scrollable_page() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(24, 20, 24, 24)
    layout.setSpacing(16)
    scroll.setWidget(container)
    return scroll, layout


class OwnerDashboardPage(QWidget):
    """Owner home dashboard with summary cards, balances, and recent transactions."""

    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._stat_labels: dict[str, QLabel] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = _owner_scrollable_page()
        layout.addWidget(self._section_label(t("todays_summary")))
        layout.addWidget(self._build_stats_row())
        layout.addWidget(self._section_label(t("account_balances")))
        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(12)
        layout.addWidget(self._grid_container)
        layout.addWidget(self._section_label(t("recent_transactions")))
        self._txn_table = self._make_table([
            t("col_time"),
            t("col_type"),
            t("col_account"),
            t("col_amount"),
            t("col_commission"),
            t("col_fee"),
        ])
        layout.addWidget(self._txn_table)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        return label

    def _build_stats_row(self) -> QFrame:
        row = QFrame()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        for key, label, color in [
            ("total_cash_in", t("total_cash_in"), ACCENT_GREEN),
            ("total_cash_out", t("total_cash_out"), ACCENT_RED),
            ("total_transfer", t("transfers"), ACCENT_BLUE),
            ("total_exchange", t("exchange"), ACCENT_YELLOW),
            ("fees", t("fees_commission"), ACCENT_MAUVE),
        ]:
            layout.addWidget(self._stat_card(key, label, color))
        return row

    def _stat_card(self, key: str, label: str, color: str) -> QFrame:
        card = QFrame()
        card.setFixedHeight(90)
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 8px; "
            f"border-left: 3px solid {color}; }}"
        )
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

    def _make_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setMinimumHeight(260)
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        for idx in range(len(headers) - 1):
            header.setSectionResizeMode(idx, QHeaderView.ResizeMode.ResizeToContents)
        return table

    def load_data(self) -> None:
        try:
            summary = self._api.get_dashboard_summary()
            self._stat_labels["total_cash_in"].setText(f"{float(summary.get('total_cash_in', 0) or 0):,.0f}")
            self._stat_labels["total_cash_out"].setText(f"{float(summary.get('total_cash_out', 0) or 0):,.0f}")
            self._stat_labels["total_transfer"].setText(f"{float(summary.get('total_transfer', 0) or 0):,.0f}")
            self._stat_labels["total_exchange"].setText(f"{float(summary.get('total_exchange', 0) or 0):,.0f}")
            fees = float(summary.get("total_customer_fees", 0) or 0) + float(summary.get("total_commission", 0) or 0)
            self._stat_labels["fees"].setText(f"{fees:,.0f}")
        except Exception:
            pass
        try:
            self._rebuild_accounts(self._api.get_dashboard_accounts())
        except Exception:
            pass
        try:
            self._populate_transactions(self._api.get_recent_transactions(20))
        except Exception:
            pass

    def update_from_ws(self, accounts: list[dict]) -> None:
        self._rebuild_accounts(accounts)
        self.load_data()

    def _rebuild_accounts(self, accounts: list[dict]) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for idx, account in enumerate(accounts):
            row, col = divmod(idx, 3)
            self._grid.addWidget(self._account_card(account), row, col)

    def _account_card(self, account: dict) -> QFrame:
        card = QFrame()
        card.setFixedHeight(100)
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 8px; "
            f"border: 1px solid {BORDER_COLOR}; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        title = QLabel(account.get("account_name", ""))
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        phone = QLabel(account.get("phone_number", ""))
        phone.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(phone)
        balance = float(account.get("balance", 0) or 0)
        balance_label = QLabel(f"{balance:,.0f} MMK")
        balance_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        balance_label.setStyleSheet(f"color: {ACCENT_GREEN if balance >= 0 else ACCENT_RED};")
        layout.addWidget(balance_label)
        return card

    def _populate_transactions(self, transactions: list[dict]) -> None:
        self._txn_table.setRowCount(len(transactions))
        for row, txn in enumerate(transactions):
            created = str(txn.get("created_at", ""))
            if len(created) > 16:
                created = created[:16]
            txn_type = txn.get("transaction_type", "")
            values = [
                created,
                txn_type,
                str(txn.get("account_id", "")),
                f"{float(txn.get('amount', 0) or 0):,.0f}",
                f"{float(txn.get('commission_amount', 0) or 0):,.0f}",
                f"{float(txn.get('customer_fee', 0) or 0):,.0f}",
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._txn_table.setItem(row, col, item)


class OwnerReportsPage(QWidget):
    """Small owner reports landing page backed by the daily report endpoint."""

    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        title = QLabel(t("nav_reports"))
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(self._status)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels(["Metric", "Value"])
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    def load_data(self) -> None:
        today = datetime.now(MMT).strftime("%Y-%m-%d")
        try:
            report = self._api.get_daily_report(today)
        except Exception as exc:
            self._status.setText(f"Unable to load daily report: {exc}")
            self._table.setRowCount(0)
            return
        self._status.setText(f"Daily report: {today}")
        rows = [
            ("Total transactions", report.get("transaction_count", 0)),
            ("Cash In", report.get("total_cash_in", 0)),
            ("Cash Out", report.get("total_cash_out", 0)),
            ("Transfer", report.get("total_transfer", 0)),
            ("Exchange", report.get("total_exchange", 0)),
            ("Fees", report.get("total_customer_fees", 0)),
            ("Commission", report.get("total_commission", 0)),
        ]
        self._table.setRowCount(len(rows))
        for row, (label, value) in enumerate(rows):
            self._table.setItem(row, 0, QTableWidgetItem(str(label)))
            self._table.setItem(row, 1, QTableWidgetItem(f"{float(value or 0):,.0f}"))


class DashboardView(QMainWindow):
    """Role-aware dashboard shell.

    Owner gets the full management sidebar. Employee gets the six-card launcher.
    Cashier should normally be routed to CashierView, but falls back to the
    launcher if this class is ever constructed directly.
    """

    switch_to_transaction = pyqtSignal(str)

    def __init__(self, api_client: ApiClient, navigate=None) -> None:
        super().__init__()
        self._api = api_client
        self._external_navigate = navigate
        self._ws_thread: WebSocketThread | None = None
        self._clock: QTimer | None = None
        self._clock_timer: QTimer | None = None
        self._refresh_timer: QTimer | None = None
        self._daily_closing_view: DailyClosingView | None = None
        self._nav_buttons: dict[int, QPushButton] = {}
        self._nav_button_data: dict[int, tuple[str, str]] = {}
        self._current_page = 0

        role = (self._api.user or {}).get("role")
        if role == "owner":
            self._build_owner_ui()
        else:
            self._build_employee_ui()

    def _build_employee_ui(self) -> None:
        self.setWindowTitle(t("app_title"))
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(
            f"QMainWindow {{ background-color: {BG_DARK}; }} QWidget {{ color: {TEXT_PRIMARY}; }}"
        )
        self._page = DashboardPage(self._api, self._navigate)
        self.setCentralWidget(self._page)
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._page.update_time)
        self._clock.start(1000)
        self._page.update_time()
        self._ws_thread: WebSocketThread | None = None
        self._start_websocket()

    def _build_owner_ui(self) -> None:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self.setWindowTitle(f"{t('app_title')} - {fullname}")
        self.setMinimumSize(1200, 750)
        self.setStyleSheet(OWNER_STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_owner_sidebar())

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self._build_owner_top_bar())

        self._stack = QStackedWidget()
        self._pages: list[QWidget] = []
        self._daily_closing_view = DailyClosingView(self._api)
        for page in [
            OwnerDashboardPage(self._api),
            TransactionAdminView(self._api),
            ActivityLogView(self._api),
            AccountSettingsView(self._api),
            OwnerReportsPage(self._api),
            UserSettingsView(self._api),
            CompanySettingsView(self._api),
            ServiceTypeSettingsView(self._api),
            CommissionTierSubView(self._api),
            ExchangeRateSubView(self._api),
            CashFloatAdminView(self._api),
            ServerInfoSubView(),
            PasswordSubView(self._api),
            self._daily_closing_view,
        ]:
            self._stack.addWidget(page)
            self._pages.append(page)

        right.addWidget(self._stack, 1)
        right_widget = QWidget()
        right_widget.setLayout(right)
        root.addWidget(right_widget, 1)

        self._start_owner_timers()
        self._start_websocket()
        self._select_owner_page(0)
        on_change(self._retranslate_owner_ui)

    def _build_owner_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar.setStyleSheet("background-color: #181825;")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        logo = QLabel(t("app_title"))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        logo.setStyleSheet(f"color: {ACCENT_BLUE}; padding: 18px 12px;")
        layout.addWidget(logo)

        for section_key, items in _OWNER_SIDEBAR_GROUPS:
            if section_key:
                section = QLabel(t(section_key).upper())
                section.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                section.setStyleSheet(f"color: {TEXT_MUTED}; padding: 14px 16px 4px 16px;")
                layout.addWidget(section)
            for item_key, idx, icon in items:
                btn = QPushButton(f"  {icon}  {t(item_key)}")
                btn.setFixedHeight(38)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(self._owner_nav_style(False))
                btn.clicked.connect(lambda _, i=idx: self._select_owner_page(i))
                self._nav_buttons[idx] = btn
                self._nav_button_data[idx] = (item_key, icon)
                layout.addWidget(btn)

        layout.addStretch()
        logout_btn = QPushButton(f"  X  {t('logout')}")
        logout_btn.setFixedHeight(42)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setStyleSheet(
            f"QPushButton {{ text-align: left; background: transparent; color: {ACCENT_RED}; "
            f"border: none; border-left: 3px solid transparent; padding-left: 13px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; }}"
        )
        logout_btn.clicked.connect(self._owner_logout)
        layout.addWidget(logout_btn)
        return sidebar

    def _build_owner_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"background-color: {BG_DARK}; border-bottom: 1px solid {BORDER_COLOR};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 10, 24, 10)
        self._page_title = QLabel(t("nav_dashboard"))
        self._page_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(self._page_title)
        layout.addStretch()
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        user_label = QLabel(fullname)
        user_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(user_label)
        layout.addSpacing(16)
        self._owner_time_label = QLabel()
        self._owner_time_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        layout.addWidget(self._owner_time_label)
        self._update_owner_time()
        return bar

    def _owner_nav_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ text-align: left; background-color: {BG_CARD}; color: {ACCENT_BLUE}; "
                f"border: none; border-left: 3px solid {ACCENT_BLUE}; padding-left: 13px; font-size: 13px; }}"
            )
        return (
            f"QPushButton {{ text-align: left; background-color: transparent; color: {TEXT_SECONDARY}; "
            f"border: none; border-left: 3px solid transparent; padding-left: 13px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; color: {TEXT_PRIMARY}; }}"
        )

    def _select_owner_page(self, idx: int) -> None:
        self._current_page = idx
        self._stack.setCurrentIndex(idx)
        for page_idx, button in self._nav_buttons.items():
            button.setStyleSheet(self._owner_nav_style(page_idx == idx))
        if idx in self._nav_button_data:
            key, _icon = self._nav_button_data[idx]
            self._page_title.setText(t(key))
        page = self._pages[idx]
        if hasattr(page, "load_data"):
            page.load_data()

    def _start_owner_timers(self) -> None:
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_owner_time)
        self._clock_timer.start(1000)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_owner_home)
        self._refresh_timer.start(REFRESH_INTERVAL_MS)

    def _update_owner_time(self) -> None:
        self._owner_time_label.setText(datetime.now(MMT).strftime("%d-%m-%Y  %I:%M:%S %p"))

    def _refresh_owner_home(self) -> None:
        if self._current_page == 0 and self._pages:
            page = self._pages[0]
            if hasattr(page, "load_data"):
                page.load_data()

    def _retranslate_owner_ui(self) -> None:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self.setWindowTitle(f"{t('app_title')} - {fullname}")
        for idx, (key, icon) in self._nav_button_data.items():
            if idx in self._nav_buttons:
                self._nav_buttons[idx].setText(f"  {icon}  {t(key)}")
        if self._current_page in self._nav_button_data:
            key, _icon = self._nav_button_data[self._current_page]
            self._page_title.setText(t(key))

    def _start_websocket(self) -> None:
        def _get_ticket() -> str:
            try:
                return self._api.get_ws_ticket()
            except Exception:
                return ""
        self._ws_thread = WebSocketThread(WS_URL, ticket_fn=_get_ticket)
        self._ws_thread.message_received.connect(self._on_ws_message)
        self._ws_thread.start()

    def _refresh_dashboard_page(self) -> None:
        if (self._api.user or {}).get("role") == "owner":
            self._refresh_owner_home()
            return
        self._page = DashboardPage(self._api, self._navigate)
        self.setCentralWidget(self._page)
        try:
            self._clock.timeout.disconnect()
        except TypeError:
            pass
        self._clock.timeout.connect(self._page.update_time)
        self._page.update_time()

    def _on_ws_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
            msg_type = data.get("type")
            if (self._api.user or {}).get("role") == "owner":
                if msg_type == "balance_update" and self._current_page == 0:
                    self._pages[0].update_from_ws(data.get("accounts", []))
                if data.get("event") == "balance_update" and self._daily_closing_view:
                    self._daily_closing_view.handle_ws_event("balance_update")
            elif msg_type in {"float_issued", "float_return_confirmed"}:
                self._refresh_dashboard_page()
                QMessageBox.information(
                    self,
                    "Vault Update",
                    data.get("message", "Your vault status has changed."),
                )
            elif msg_type == "cash_in_confirmed":
                QMessageBox.information(
                    self,
                    "Cash In Confirmed",
                    data.get("message", "Your Cash In has been confirmed."),
                )
            elif msg_type == "cash_in_cancelled":
                self._refresh_dashboard_page()
                QMessageBox.warning(
                    self,
                    "Cash In Cancelled",
                    data.get("message", "Your Cash In was cancelled."),
                )
            elif msg_type == "transaction_approved":
                QMessageBox.information(
                    self,
                    "Transaction Approved",
                    data.get("message", "Your transaction has been approved."),
                )
        except Exception:
            pass

    def _navigate(self, page: int, transaction_type: str | None = None) -> None:
        if self._external_navigate:
            try:
                self._external_navigate(page, transaction_type)
            except TypeError:
                self._external_navigate(page)
            return
        if page == -1:
            self._api.logout()
            from views.login_view import LoginView
            self._login = LoginView(self._api)
            self._login.show()
            self.close()
            return
        if transaction_type == "vault":
            from views.transaction.vault_view import VaultView
            self._next = VaultView(self._api)
            self._next.show()
            self.close()
            return
        if transaction_type:
            self.switch_to_transaction.emit(transaction_type)
            if self.receivers(self.switch_to_transaction) > 0:
                return
        from views.transaction_view import TransactionView
        self._next = TransactionView(self._api, transaction_type=transaction_type)
        self._next._navigate(page, transaction_type)
        self._next.show()
        self.close()

    def _owner_logout(self) -> None:
        self._api.logout()
        from views.login_view import LoginView
        self._login = LoginView(self._api)
        self._login.show()
        self.close()

    def closeEvent(self, event) -> None:
        if self._clock:
            self._clock.stop()
        if self._clock_timer:
            self._clock_timer.stop()
        if self._refresh_timer:
            self._refresh_timer.stop()
        if self._ws_thread:
            self._ws_thread.stop()
            self._ws_thread.wait(2000)
        super().closeEvent(event)


__all__ = ["DashboardPage", "DashboardView"]
