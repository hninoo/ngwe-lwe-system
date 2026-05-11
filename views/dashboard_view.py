import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

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
from views.ui.theme import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_MAUVE,
    ACCENT_RED,
    ACCENT_TEAL,
    ACCENT_YELLOW,
    BG_CARD,
    BG_DARK,
    BG_INPUT,
    BG_SIDEBAR,
    BORDER_COLOR,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
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

MMT = timezone(timedelta(hours=6, minutes=30))
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8000/ws")
SIDEBAR_WIDTH = 240
REFRESH_INTERVAL_MS = 30000


class OwnerPage(Enum):
    """Type-safe owner dashboard page indexes."""

    DASHBOARD = 0
    TRANSACTIONS = 1
    ACTIVITY_LOGS = 2
    ACCOUNTS = 3
    REPORTS = 4
    USERS = 5
    COMPANIES = 6
    SERVICE_TYPES = 7
    COMMISSION_TIERS = 8
    EXCHANGE_RATE = 9
    CASH_FLOATS = 10
    SERVER_CONNECTION = 11
    CHANGE_PASSWORD = 12
    DAILY_CLOSING = 13


@dataclass(frozen=True)
class NavItem:
    """Owner sidebar navigation item."""

    label_key: str
    page: OwnerPage
    icon: str


@dataclass(frozen=True)
class NavSection:
    """Owner sidebar navigation section."""

    label_key: str | None
    items: tuple[NavItem, ...]


OWNER_NAVIGATION: tuple[NavSection, ...] = (
    NavSection(None, (NavItem("nav_dashboard", OwnerPage.DASHBOARD, "D"),)),
    NavSection(
        "nav_group_transactions",
        (
            NavItem("admin_all_transactions", OwnerPage.TRANSACTIONS, "T"),
            NavItem("admin_activity_logs", OwnerPage.ACTIVITY_LOGS, "L"),
        ),
    ),
    NavSection("nav_group_accounts", (NavItem("nav_accounts", OwnerPage.ACCOUNTS, "A"),)),
    NavSection("nav_group_reports", (NavItem("nav_reports", OwnerPage.REPORTS, "R"),)),
    NavSection("admin_group_staff", (NavItem("nav_users", OwnerPage.USERS, "U"),)),
    NavSection(
        "admin_group_master",
        (
            NavItem("admin_companies", OwnerPage.COMPANIES, "C"),
            NavItem("admin_service_types", OwnerPage.SERVICE_TYPES, "S"),
            NavItem("admin_commission_tiers", OwnerPage.COMMISSION_TIERS, "%"),
            NavItem("admin_exchange_rate", OwnerPage.EXCHANGE_RATE, "X"),
        ),
    ),
    NavSection(
        "admin_group_operations",
        (
            NavItem("admin_cash_floats", OwnerPage.CASH_FLOATS, "F"),
            NavItem("nav_daily_closing", OwnerPage.DAILY_CLOSING, "DC"),
        ),
    ),
    NavSection(
        "admin_group_system",
        (
            NavItem("admin_server_connection", OwnerPage.SERVER_CONNECTION, "N"),
            NavItem("admin_change_password", OwnerPage.CHANGE_PASSWORD, "P"),
        ),
    ),
)

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


class ApiFetchThread(QThread):
    """Run a blocking API callable away from the Qt UI thread."""

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fetcher: Callable[[], Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fetcher = fetcher

    def run(self) -> None:
        try:
            self.succeeded.emit(self._fetcher())
        except Exception as exc:
            self.failed.emit(str(exc))


class DashboardController(QWidget):
    """Own dashboard timers and WebSocket lifetime."""

    clock_tick = pyqtSignal()
    refresh_tick = pyqtSignal()
    websocket_message = pyqtSignal(str)

    def __init__(self, api: ApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._clock_timer: QTimer | None = None
        self._refresh_timer: QTimer | None = None
        self._ws_thread: WebSocketThread | None = None

    def start_clock(self) -> None:
        """Start one-second clock ticks."""
        if self._clock_timer is not None:
            return
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self.clock_tick)
        self._clock_timer.start(1000)

    def start_refresh(self, interval_ms: int = REFRESH_INTERVAL_MS) -> None:
        """Start periodic dashboard refresh ticks."""
        if self._refresh_timer is not None:
            return
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_tick)
        self._refresh_timer.start(interval_ms)

    def start_websocket(self) -> None:
        """Start role-aware WebSocket listener."""
        if self._ws_thread is not None:
            return

        def get_ticket() -> str:
            try:
                return self._api.get_ws_ticket()
            except Exception:
                return ""

        self._ws_thread = WebSocketThread(WS_URL, ticket_fn=get_ticket)
        self._ws_thread.message_received.connect(self.websocket_message)
        self._ws_thread.start()

    def stop(self) -> None:
        """Stop all timers and worker threads."""
        for timer in (self._clock_timer, self._refresh_timer):
            if timer is not None:
                timer.stop()
        if self._ws_thread is not None:
            self._ws_thread.stop()
            self._ws_thread.wait(2000)
            self._ws_thread = None


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
                f"QFrame:hover {{ background-color: {BG_INPUT}; "
                f"border: 1px solid {color}; border-left: 5px solid {color}; }}"
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


class StatsRow(QWidget):
    """Reusable row of owner summary statistic cards."""

    def __init__(self) -> None:
        super().__init__()
        self._labels: dict[str, QLabel] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        for key, label_key, color in (
            ("total_cash_in", "total_cash_in", ACCENT_GREEN),
            ("total_cash_out", "total_cash_out", ACCENT_RED),
            ("total_transfer", "transfers", ACCENT_BLUE),
            ("total_exchange", "exchange", ACCENT_YELLOW),
            ("fees", "fees_commission", ACCENT_MAUVE),
        ):
            layout.addWidget(self._card(key, label_key, color))

    def _card(self, key: str, label_key: str, color: str) -> QFrame:
        card = QFrame()
        card.setFixedHeight(90)
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 8px; "
            f"border-left: 3px solid {color}; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        title = QLabel(t(label_key))
        title.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(title)
        value = QLabel("0")
        value.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        value.setStyleSheet(f"color: {color};")
        self._labels[key] = value
        layout.addWidget(value)
        return card

    def set_summary(self, summary: dict[str, Any]) -> None:
        """Render summary totals returned by the dashboard API."""
        values = {
            "total_cash_in": float(summary.get("total_cash_in", 0) or 0),
            "total_cash_out": float(summary.get("total_cash_out", 0) or 0),
            "total_transfer": float(summary.get("total_transfer", 0) or 0),
            "total_exchange": float(summary.get("total_exchange", 0) or 0),
            "fees": (
                float(summary.get("total_customer_fees", 0) or 0)
                + float(summary.get("total_commission", 0) or 0)
            ),
        }
        for key, value in values.items():
            self._labels[key].setText(f"{value:,.0f}")


class AccountGrid(QWidget):
    """Reusable owner account balance grid."""

    def __init__(self) -> None:
        super().__init__()
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(12)

    def set_accounts(self, accounts: list[dict]) -> None:
        """Replace account cards with the supplied account list."""
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
        title = QLabel(str(account.get("account_name", "")))
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        phone = QLabel(str(account.get("phone_number", "")))
        phone.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(phone)
        balance = float(account.get("balance", 0) or 0)
        balance_label = QLabel(f"{balance:,.0f} MMK")
        balance_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        balance_label.setStyleSheet(
            f"color: {ACCENT_GREEN if balance >= 0 else ACCENT_RED};"
        )
        layout.addWidget(balance_label)
        return card


class TransactionTable(QTableWidget):
    """Reusable owner transaction preview table."""

    def __init__(self) -> None:
        super().__init__(0, 6)
        self.setHorizontalHeaderLabels([
            t("col_time"),
            t("col_type"),
            t("col_account"),
            t("col_amount"),
            t("col_commission"),
            t("col_fee"),
        ])
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setMinimumHeight(260)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        for idx in range(5):
            header.setSectionResizeMode(idx, QHeaderView.ResizeMode.ResizeToContents)

    def set_transactions(self, transactions: list[dict]) -> None:
        """Render recent transactions."""
        self.setRowCount(len(transactions))
        for row, txn in enumerate(transactions):
            created = str(txn.get("created_at", ""))
            if len(created) > 16:
                created = created[:16]
            values = [
                created,
                str(txn.get("transaction_type", "")),
                str(txn.get("account_id", "")),
                f"{float(txn.get('amount', 0) or 0):,.0f}",
                f"{float(txn.get('commission_amount', 0) or 0):,.0f}",
                f"{float(txn.get('customer_fee', 0) or 0):,.0f}",
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(row, col, item)


class OwnerSidebar(QWidget):
    """Reusable owner navigation sidebar."""

    page_selected = pyqtSignal(object)
    logout_requested = pyqtSignal()

    def __init__(self, sections: tuple[NavSection, ...]) -> None:
        super().__init__()
        self._sections = sections
        self._buttons: dict[OwnerPage, QPushButton] = {}
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.setStyleSheet(f"background-color: {BG_SIDEBAR};")
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._logo = QLabel(t("app_title"))
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._logo.setStyleSheet(f"color: {ACCENT_BLUE}; padding: 18px 12px;")
        layout.addWidget(self._logo)

        for section in self._sections:
            if section.label_key:
                label = QLabel(t(section.label_key).upper())
                label.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
                label.setStyleSheet(
                    f"color: {TEXT_MUTED}; padding: 14px 16px 4px 16px;"
                )
                layout.addWidget(label)
            for item in section.items:
                button = QPushButton(f"  {item.icon}  {t(item.label_key)}")
                button.setFixedHeight(38)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setStyleSheet(self._style(False))
                button.clicked.connect(
                    lambda _checked=False, page=item.page: self.page_selected.emit(page)
                )
                self._buttons[item.page] = button
                layout.addWidget(button)

        layout.addStretch()
        logout_btn = QPushButton(f"  X  {t('logout')}")
        logout_btn.setFixedHeight(42)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setStyleSheet(
            f"QPushButton {{ text-align: left; background: transparent; "
            f"color: {ACCENT_RED}; border: none; border-left: 3px solid transparent; "
            f"padding-left: 13px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; }}"
        )
        logout_btn.clicked.connect(self.logout_requested)
        layout.addWidget(logout_btn)

    def set_active(self, page: OwnerPage) -> None:
        """Update active navigation button styling."""
        for item_page, button in self._buttons.items():
            button.setStyleSheet(self._style(item_page == page))

    def retranslate(self) -> None:
        """Update translated labels after locale changes."""
        self._logo.setText(t("app_title"))
        for section in self._sections:
            for item in section.items:
                self._buttons[item.page].setText(f"  {item.icon}  {t(item.label_key)}")

    @staticmethod
    def _style(active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ text-align: left; background-color: {BG_CARD}; "
                f"color: {ACCENT_BLUE}; border: none; border-left: 3px solid {ACCENT_BLUE}; "
                f"padding-left: 13px; font-size: 13px; }}"
            )
        return (
            f"QPushButton {{ text-align: left; background-color: transparent; "
            f"color: {TEXT_SECONDARY}; border: none; "
            f"border-left: 3px solid transparent; padding-left: 13px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; color: {TEXT_PRIMARY}; }}"
        )


class OwnerTopBar(QFrame):
    """Reusable owner top bar with page title, user name, and clock."""

    def __init__(self, full_name: str) -> None:
        super().__init__()
        self.setFixedHeight(60)
        self.setStyleSheet(
            f"background-color: {BG_DARK}; border-bottom: 1px solid {BORDER_COLOR};"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 10, 24, 10)
        self._title = QLabel(t("nav_dashboard"))
        self._title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(self._title)
        layout.addStretch()
        user_label = QLabel(full_name)
        user_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(user_label)
        layout.addSpacing(16)
        self._time_label = QLabel()
        self._time_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        layout.addWidget(self._time_label)

    def set_title(self, label_key: str) -> None:
        """Set title from an i18n key."""
        self._title.setText(t(label_key))

    def update_time(self) -> None:
        """Refresh displayed Myanmar time."""
        self._time_label.setText(datetime.now(MMT).strftime("%d-%m-%Y  %I:%M:%S %p"))


class OwnerDashboardPage(QWidget):
    """Owner home dashboard with summary cards, balances, and recent transactions."""

    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._fetch_thread: ApiFetchThread | None = None
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = _owner_scrollable_page()
        layout.addWidget(self._section_label(t("todays_summary")))
        self._stats = StatsRow()
        layout.addWidget(self._stats)
        layout.addWidget(self._section_label(t("account_balances")))
        self._account_grid = AccountGrid()
        layout.addWidget(self._account_grid)
        layout.addWidget(self._section_label(t("recent_transactions")))
        self._txn_table = TransactionTable()
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

    def load_data(self) -> None:
        """Fetch owner home data without blocking the UI thread."""
        if self._fetch_thread and self._fetch_thread.isRunning():
            return
        self._fetch_thread = ApiFetchThread(self._fetch_dashboard_data, self)
        self._fetch_thread.succeeded.connect(self._apply_dashboard_data)
        self._fetch_thread.finished.connect(self._clear_fetch_thread)
        self._fetch_thread.start()

    def update_from_ws(self, accounts: list[dict]) -> None:
        """Apply pushed account balances and refresh summary asynchronously."""
        self._account_grid.set_accounts(accounts)
        self.load_data()

    def stop(self) -> None:
        """Stop any in-flight data worker."""
        if self._fetch_thread and self._fetch_thread.isRunning():
            self._fetch_thread.quit()
            self._fetch_thread.wait(1000)

    def _fetch_dashboard_data(self) -> dict[str, Any]:
        return {
            "summary": self._api.get_dashboard_summary(),
            "accounts": self._api.get_dashboard_accounts(),
            "transactions": self._api.get_recent_transactions(20),
        }

    def _apply_dashboard_data(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        self._stats.set_summary(payload.get("summary", {}) or {})
        self._account_grid.set_accounts(payload.get("accounts", []) or [])
        self._txn_table.set_transactions(payload.get("transactions", []) or [])

    def _clear_fetch_thread(self) -> None:
        self._fetch_thread = None


class OwnerReportsPage(QWidget):
    """Small owner reports landing page backed by the daily report endpoint."""

    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._fetch_thread: ApiFetchThread | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 24)
        title = QLabel(t("nav_reports"))
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        layout.addWidget(self._status)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels([t("col_metric"), t("col_value")])
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    def load_data(self) -> None:
        """Fetch report data without blocking the UI thread."""
        if self._fetch_thread and self._fetch_thread.isRunning():
            return
        today = datetime.now(MMT).strftime("%Y-%m-%d")
        self._fetch_thread = ApiFetchThread(
            lambda: {"date": today, "report": self._api.get_daily_report(today)},
            self,
        )
        self._fetch_thread.succeeded.connect(self._apply_report_data)
        self._fetch_thread.failed.connect(self._show_report_error)
        self._fetch_thread.finished.connect(self._clear_fetch_thread)
        self._fetch_thread.start()

    def stop(self) -> None:
        """Stop any in-flight report worker."""
        if self._fetch_thread and self._fetch_thread.isRunning():
            self._fetch_thread.quit()
            self._fetch_thread.wait(1000)

    def _apply_report_data(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        today = str(payload.get("date", ""))
        report = payload.get("report", {}) or {}
        self._status.setText(f"{t('daily_report_for')}: {today}")
        rows = [
            (t("report_total_transactions"), report.get("transaction_count", 0)),
            (t("report_cash_in"), report.get("total_cash_in", 0)),
            (t("report_cash_out"), report.get("total_cash_out", 0)),
            (t("report_transfer"), report.get("total_transfer", 0)),
            (t("report_exchange"), report.get("total_exchange", 0)),
            (t("report_fees"), report.get("total_customer_fees", 0)),
            (t("report_commission"), report.get("total_commission", 0)),
        ]
        self._table.setRowCount(len(rows))
        for row, (label, value) in enumerate(rows):
            self._table.setItem(row, 0, QTableWidgetItem(str(label)))
            self._table.setItem(row, 1, QTableWidgetItem(f"{float(value or 0):,.0f}"))

    def _show_report_error(self, message: str) -> None:
        self._status.setText(t("err_load_data") if t("err_load_data") != "err_load_data" else message)
        self._table.setRowCount(0)

    def _clear_fetch_thread(self) -> None:
        self._fetch_thread = None


class DashboardView(QMainWindow):
    """Role-aware dashboard shell.

    Owner gets the full management sidebar. Employee gets the six-card launcher.
    Cashier must be routed to CashierView by the login flow.
    """

    switch_to_transaction = pyqtSignal(str)

    def __init__(self, api_client: ApiClient, navigate=None) -> None:
        super().__init__()
        self._api = api_client
        self._external_navigate = navigate
        self._controller = DashboardController(self._api, self)
        self._daily_closing_view: DailyClosingView | None = None
        self._current_page = 0

        role = (self._api.user or {}).get("role")
        assert role in ("owner", "cashier", "employee")
        if role == "owner":
            self._build_owner_ui()
        elif role == "employee":
            self._build_employee_ui()
        else:
            raise RuntimeError("Cashier users must be routed to CashierView.")

    def _build_employee_ui(self) -> None:
        self.setWindowTitle(t("app_title"))
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(
            f"QMainWindow {{ background-color: {BG_DARK}; }} QWidget {{ color: {TEXT_PRIMARY}; }}"
        )
        self._page = DashboardPage(self._api, self._navigate)
        self.setCentralWidget(self._page)
        self._controller.clock_tick.connect(self._page.update_time)
        self._controller.websocket_message.connect(self._on_ws_message)
        self._controller.start_clock()
        self._page.update_time()
        self._controller.start_websocket()

    def _build_owner_ui(self) -> None:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self.setWindowTitle(f"{t('app_title')} - {fullname}")
        self.setMinimumSize(1200, 750)
        self.setStyleSheet(OWNER_STYLESHEET)
        self._page_labels: dict[OwnerPage, str] = {}

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
        self._controller.websocket_message.connect(self._on_ws_message)
        self._controller.start_websocket()
        self._select_owner_page(OwnerPage.DASHBOARD, load=False)
        QTimer.singleShot(0, lambda: self._select_owner_page(OwnerPage.DASHBOARD))
        on_change(self._retranslate_owner_ui)

    def _build_owner_sidebar(self) -> QWidget:
        self._sidebar = OwnerSidebar(OWNER_NAVIGATION)
        self._sidebar.page_selected.connect(self._select_owner_page)
        self._sidebar.logout_requested.connect(self._owner_logout)
        for section in OWNER_NAVIGATION:
            for item in section.items:
                self._page_labels[item.page] = item.label_key
        return self._sidebar

    def _build_owner_top_bar(self) -> QFrame:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self._top_bar = OwnerTopBar(fullname)
        self._top_bar.update_time()
        return self._top_bar

    def _select_owner_page(self, page_id: object, load: bool = True) -> None:
        if not isinstance(page_id, OwnerPage):
            return
        self._current_page = page_id.value
        self._stack.setCurrentIndex(page_id.value)
        self._sidebar.set_active(page_id)
        label_key = self._page_labels.get(page_id, "nav_dashboard")
        self._top_bar.set_title(label_key)
        page = self._pages[page_id.value]
        if load and hasattr(page, "load_data"):
            page.load_data()

    def _start_owner_timers(self) -> None:
        self._controller.clock_tick.connect(self._top_bar.update_time)
        self._controller.refresh_tick.connect(self._refresh_owner_home)
        self._controller.start_clock()
        self._controller.start_refresh(REFRESH_INTERVAL_MS)

    def _refresh_owner_home(self) -> None:
        if self._current_page == 0 and self._pages:
            page = self._pages[0]
            if hasattr(page, "load_data"):
                page.load_data()

    def _retranslate_owner_ui(self) -> None:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self.setWindowTitle(f"{t('app_title')} - {fullname}")
        self._sidebar.retranslate()
        current = OwnerPage(self._current_page)
        self._top_bar.set_title(self._page_labels.get(current, "nav_dashboard"))

    def _refresh_dashboard_page(self) -> None:
        if (self._api.user or {}).get("role") == "owner":
            self._refresh_owner_home()
            return
        self._page = DashboardPage(self._api, self._navigate)
        self.setCentralWidget(self._page)
        self._controller.clock_tick.connect(self._page.update_time)
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
            from views.ui.vault_view import VaultView
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
        for page in getattr(self, "_pages", []):
            if hasattr(page, "stop"):
                page.stop()
        self._controller.stop()
        super().closeEvent(event)


__all__ = ["DashboardPage", "DashboardView"]
