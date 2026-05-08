import json
import os
from datetime import datetime, date, timezone, timedelta

MMT = timezone(timedelta(hours=6, minutes=30))  # Myanmar Time (Yangon)
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QDate
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QDoubleSpinBox,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from services.api_client import ApiClient
from i18n import t, on_change
from views.widgets.company_selector import CompanySelector, ServiceTypeSelector
from views.admin_page import ExchangeRateSubView, CommissionTierSubView, PasswordSubView
from views.settings.company_settings_view import CompanySettingsView
from views.settings.service_type_settings_view import ServiceTypeSettingsView
from views.settings.user_settings_view import UserSettingsView
from views.settings.activity_log_view import ActivityLogView
from views.settings.cash_float_admin_view import CashFloatAdminView

# ── Colors ──
BG_DARK = "#1e1e2e"
BG_SIDEBAR = "#181825"
BG_CARD = "#2a2a3e"
BG_CONTENT = "#1e1e2e"
BG_INPUT = "#313244"
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
INPUT_BORDER = "#585b70"

SIDEBAR_WIDTH = 240
REFRESH_INTERVAL_MS = 30000
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8000/ws")

TYPE_COLORS = {
    "deposit": ACCENT_GREEN,
    "withdraw": ACCENT_RED,
    "transfer": ACCENT_BLUE,
    "exchange": ACCENT_YELLOW,
}

# ── Unified sidebar navigation structure ─────────────────────────────────────
# Each entry: (section_i18n_key | None, [(item_i18n_key, page_idx, icon_char)])
# section_i18n_key=None → no section header (used for Dashboard at the top)
_SIDEBAR_GROUPS: list[tuple[str | None, list[tuple[str, int, str]]]] = [
    (None, [
        ("nav_dashboard",          0, "◆"),
    ]),
    ("nav_group_transactions", [
        ("admin_all_transactions", 1, "↕"),
        ("admin_activity_logs",    2, "≡"),
    ]),
    ("nav_group_accounts", [
        ("nav_accounts",           3, "◉"),
    ]),
    ("nav_group_reports", [
        ("nav_reports",            4, "■"),
    ]),
    ("admin_group_staff", [
        ("nav_users",              5, "●"),
    ]),
    ("admin_group_master", [
        ("admin_companies",        6, "○"),
        ("admin_service_types",    7, "⚙"),
        ("admin_commission_tiers", 8, "◎"),
        ("admin_exchange_rate",    9, "↻"),
    ]),
    ("admin_group_operations", [
        ("admin_cash_floats",     10, "⊙"),
    ]),
    ("admin_group_system", [
        ("admin_change_password", 11, "⊕"),
    ]),
]

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
        border: none; padding: 8px;
        font-weight: bold; font-size: 12px;
    }}
    QLineEdit, QComboBox, QDateEdit {{
        background-color: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {INPUT_BORDER}; border-radius: 6px;
        padding: 8px 12px; font-size: 13px;
    }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {ACCENT_BLUE}; }}
    QComboBox::drop-down {{ border: none; }}
    QComboBox QAbstractItemView {{
        background-color: {BG_INPUT}; color: {TEXT_PRIMARY};
        selection-background-color: {BG_CARD};
    }}
"""


# ════════════════════════════════════════════
# WebSocket thread
# ════════════════════════════════════════════
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


# ════════════════════════════════════════════
# Shared helpers
# ════════════════════════════════════════════
def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    label.setStyleSheet(f"color: {TEXT_PRIMARY};")
    return label


def type_badge(text: str) -> QLabel:
    color = ACCENT_TEAL if text == "agent" else TEXT_MUTED
    badge = QLabel(text.upper())
    badge.setStyleSheet(
        f"color: {color}; background-color: {BG_DARK}; border-radius: 4px; "
        f"padding: 2px 8px; font-size: 10px; font-weight: bold;"
    )
    return badge


def make_table(headers: list[str], min_h: int = 300) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setMinimumHeight(min_h)
    hdr = table.horizontalHeader()
    hdr.setStretchLastSection(True)
    for i in range(len(headers) - 1):
        hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
    return table


def accent_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color}; color: {BG_DARK}; "
        f"border: none; border-radius: 6px; padding: 8px 18px; "
        f"font-size: 13px; font-weight: bold; }}"
        f"QPushButton:hover {{ opacity: 0.8; }}"
    )
    return btn


def card_frame() -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; "
        f"border: 1px solid {BORDER_COLOR}; }}"
    )
    return f


def scrollable_page() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    container = QWidget()
    container.setStyleSheet(f"background-color: {BG_CONTENT};")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(24, 20, 24, 24)
    layout.setSpacing(16)
    scroll.setWidget(container)
    return scroll, layout


# ════════════════════════════════════════════
# Page 0: Dashboard (Home)
# ════════════════════════════════════════════
class DashboardPage(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._stat_labels: dict[str, QLabel] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()
        self._summary_label = section_label(t("todays_summary"))
        layout.addWidget(self._summary_label)
        layout.addWidget(self._build_stats_row())
        self._balances_label = section_label(t("account_balances"))
        layout.addWidget(self._balances_label)
        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(12)
        layout.addWidget(self._grid_container)
        self._recent_txn_label = section_label(t("recent_transactions"))
        layout.addWidget(self._recent_txn_label)
        self._txn_table = make_table([
            t("col_time"), t("col_employee"), t("col_type"), t("col_service"), t("col_account"),
            t("col_amount"), t("col_commission"), t("col_fee"), t("col_screenshot"),
        ])
        layout.addWidget(self._txn_table)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _build_stats_row(self) -> QFrame:
        row = QFrame()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        cards = [
            ("deposit", t("todays_deposits"), ACCENT_GREEN),
            ("withdraw", t("todays_withdrawals"), ACCENT_RED),
            ("transfer", t("transfers"), ACCENT_BLUE),
            ("exchange", t("exchange"), ACCENT_YELLOW),
            ("fees", t("fees_commission"), ACCENT_MAUVE),
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
        lo = QVBoxLayout(card)
        lo.setContentsMargins(14, 12, 14, 12)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        lo.addWidget(lbl)
        v = QLabel("0")
        v.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        v.setStyleSheet(f"color: {color};")
        self._stat_labels[key] = v
        lo.addWidget(v)
        return card

    def load_data(self) -> None:
        try:
            s = self._api.get_dashboard_summary()
            self._stat_labels["deposit"].setText(f"{s.get('total_deposit',0):,.0f}")
            self._stat_labels["withdraw"].setText(f"{s.get('total_withdraw',0):,.0f}")
            self._stat_labels["transfer"].setText(f"{s.get('total_transfer',0):,.0f}")
            self._stat_labels["exchange"].setText(f"{s.get('total_exchange',0):,.0f}")
            fees = s.get("total_customer_fees", 0) + s.get("total_commission", 0)
            self._stat_labels["fees"].setText(f"{fees:,.0f}")
        except Exception:
            pass
        try:
            accs = self._api.get_dashboard_accounts()
            self._rebuild_grid(accs)
        except Exception:
            pass
        try:
            txns = self._api.get_recent_transactions(20)
            self._populate_table(txns)
        except Exception:
            pass

    def _rebuild_grid(self, accounts: list[dict]) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, acc in enumerate(accounts):
            r, c = divmod(i, 3)
            self._grid.addWidget(self._acc_card(acc), r, c)

    def _acc_card(self, acc: dict) -> QFrame:
        card = QFrame()
        card.setFixedHeight(100)
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 8px; "
            f"border: 1px solid {BORDER_COLOR}; }}"
        )
        lo = QVBoxLayout(card)
        lo.setContentsMargins(14, 10, 14, 10)
        lo.setSpacing(4)
        top = QHBoxLayout()
        n = QLabel(acc.get("account_name", ""))
        n.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        top.addWidget(n)
        top.addStretch()
        lo.addLayout(top)
        p = QLabel(acc.get("phone_number", ""))
        p.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 11px;")
        lo.addWidget(p)
        bal = float(acc.get("balance", 0))
        bl = QLabel(f"{bal:,.0f} MMK")
        bl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        bl.setStyleSheet(f"color: {ACCENT_GREEN if bal >= 0 else ACCENT_RED};")
        lo.addWidget(bl)
        return card

    def _populate_table(self, txns: list[dict]) -> None:
        self._txn_table.setRowCount(len(txns))
        for row, txn in enumerate(txns):
            created = txn.get("created_at", "")
            if isinstance(created, str) and len(created) > 16:
                created = created[11:16]
            tt = txn.get("transaction_type", "")
            items = [
                str(created), str(txn.get("created_by", "")), tt, "",
                str(txn.get("account_id", "")),
                f"{float(txn.get('amount',0)):,.0f}",
                f"{float(txn.get('commission_amount',0)):,.0f}",
                f"{float(txn.get('customer_fee',0)):,.0f}",
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 2:
                    item.setForeground(QColor(TYPE_COLORS.get(tt, TEXT_PRIMARY)))
                self._txn_table.setItem(row, col, item)
            path = txn.get("screenshot_path", "")
            btn = QPushButton(t("view") if path else "-")
            btn.setEnabled(bool(path))
            btn.setStyleSheet(
                f"QPushButton {{ background: {BG_DARK}; color: {ACCENT_BLUE}; "
                f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; }}"
            )
            self._txn_table.setCellWidget(row, 8, btn)

    def update_from_ws(self, accounts: list[dict]) -> None:
        self._rebuild_grid(accounts)
        self.load_data()


# ════════════════════════════════════════════
# Page 1: Transactions (full history + filters)
# ════════════════════════════════════════════
class TransactionsPage(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._loaded = False
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()
        self._title_label = section_label(t("transactions_title"))
        layout.addWidget(self._title_label)
        layout.addWidget(self._build_filters())
        self._table = make_table([
            t("col_time"), t("col_employee"), t("col_type"), t("col_service"), t("col_account"),
            t("col_amount"), t("col_commission"), t("col_fee"), t("col_screenshot"),
        ], 400)
        layout.addWidget(self._table)
        self._load_more_btn = accent_btn(t("load_more"))
        self._load_more_btn.clicked.connect(self._on_load_more)
        layout.addWidget(self._load_more_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._offset = 0
        self._limit = 50

    def _build_filters(self) -> QFrame:
        frame = card_frame()
        lo = QHBoxLayout(frame)
        lo.setContentsMargins(14, 10, 14, 10)
        lo.setSpacing(12)

        lo.addWidget(QLabel(t("filter_from")))
        self._date_from = QDateEdit(QDate.currentDate().addDays(-7))
        self._date_from.setCalendarPopup(True)
        lo.addWidget(self._date_from)

        lo.addWidget(QLabel(t("filter_to")))
        self._date_to = QDateEdit(QDate.currentDate())
        self._date_to.setCalendarPopup(True)
        lo.addWidget(self._date_to)

        lo.addWidget(QLabel(t("filter_type")))
        self._type_filter = QComboBox()
        self._type_filter.addItems([t("all"), "deposit", "withdraw", "transfer", "exchange"])
        lo.addWidget(self._type_filter)

        search_btn = accent_btn(t("search"))
        search_btn.clicked.connect(self._on_search)
        lo.addWidget(search_btn)
        lo.addStretch()

        return frame

    def load_data(self) -> None:
        self._offset = 0
        self._on_search()

    def _on_search(self) -> None:
        try:
            self._offset = 0
            txns = self._api.get_recent_transactions(200)
            filtered = self._apply_filters(txns)
            self._all_filtered = filtered
            self._show_page(filtered[:self._limit])
            self._load_more_btn.setVisible(len(filtered) > self._limit)
        except Exception:
            pass

    def _on_load_more(self) -> None:
        try:
            self._offset += self._limit
            end = self._offset + self._limit
            self._show_page(self._all_filtered[:end])
            self._load_more_btn.setVisible(end < len(self._all_filtered))
        except Exception:
            pass

    def _apply_filters(self, txns: list[dict]) -> list[dict]:
        d_from = self._date_from.date().toString("yyyy-MM-dd")
        d_to = self._date_to.date().toString("yyyy-MM-dd")
        t_type = self._type_filter.currentText()

        result = []
        for tx in txns:
            created = str(tx.get("created_at", ""))[:10]
            if created < d_from or created > d_to:
                continue
            if t_type != t("all") and tx.get("transaction_type") != t_type:
                continue
            result.append(tx)
        return result

    def _show_page(self, txns: list[dict]) -> None:
        self._table.setRowCount(len(txns))
        for row, txn in enumerate(txns):
            created = txn.get("created_at", "")
            if isinstance(created, str) and len(created) > 16:
                created = created[11:16]
            tt = txn.get("transaction_type", "")
            items = [
                str(created), str(txn.get("created_by", "")), tt, "",
                str(txn.get("account_id", "")),
                f"{float(txn.get('amount',0)):,.0f}",
                f"{float(txn.get('commission_amount',0)):,.0f}",
                f"{float(txn.get('customer_fee',0)):,.0f}",
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 2:
                    item.setForeground(QColor(TYPE_COLORS.get(tt, TEXT_PRIMARY)))
                self._table.setItem(row, col, item)
            path = txn.get("screenshot_path", "")
            btn = QPushButton(t("view") if path else "-")
            btn.setEnabled(bool(path))
            btn.setStyleSheet(
                f"QPushButton {{ background: {BG_DARK}; color: {ACCENT_BLUE}; "
                f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; }}"
            )
            self._table.setCellWidget(row, 8, btn)


# ════════════════════════════════════════════
# Accounts CRUD dialogs
# ════════════════════════════════════════════
def _ghost_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; color: {color}; "
        f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; font-weight: bold; }}"
        f"QPushButton:hover {{ background: {BG_CARD}; }}"
    )
    return btn


class _AccountDialog(QDialog):
    """Shared base for Add / Edit account dialogs."""

    def __init__(self, api: ApiClient, parent=None, account: dict | None = None) -> None:
        super().__init__(parent)
        self._api = api
        self._account = account
        self._companies: list[dict] = []
        self._service_types: list[dict] = []
        self.setWindowTitle(t("edit_account") if account else t("add_account"))
        self.setMinimumWidth(400)
        self._build_ui()
        self._load_companies()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self._company_combo = CompanySelector()
        self._st_combo = ServiceTypeSelector()
        self._name_edit = QLineEdit()
        self._phone_edit = QLineEdit()
        self._balance_spin = QSpinBox()
        self._balance_spin.setRange(0, 999_999_999)
        self._balance_spin.setSingleStep(1000)

        for w in (self._company_combo, self._st_combo, self._name_edit,
                  self._phone_edit, self._balance_spin):
            w.setStyleSheet(
                f"background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; "
                f"border: 1px solid {INPUT_BORDER}; border-radius: 6px; padding: 6px 10px;"
            )

        form.addRow(t("col_company") + ":", self._company_combo)
        form.addRow(t("col_service_type") + ":", self._st_combo)
        form.addRow(t("col_name") + ":", self._name_edit)
        form.addRow(t("col_phone") + ":", self._phone_edit)
        if not self._account:
            form.addRow(t("col_balance") + ":", self._balance_spin)
        layout.addLayout(form)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {ACCENT_RED}; font-size: 11px;")
        layout.addWidget(self._status_lbl)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._company_combo.company_changed.connect(self._on_company_changed)

    def _load_companies(self) -> None:
        try:
            self._companies = self._api.get_companies()
        except Exception:
            self._companies = []
        self._company_combo.populate(self._companies, self._api)

        if self._account:
            cid = self._account.get("company_id")
            for i in range(self._company_combo.count()):
                if self._company_combo.itemData(i) == cid:
                    self._company_combo.setCurrentIndex(i)
                    break
        if self._company_combo.count():
            self._on_company_changed(self._company_combo.currentData() or 0)

        if self._account:
            self._name_edit.setText(self._account.get("account_name", ""))
            self._phone_edit.setText(self._account.get("phone_number", ""))

    def _on_company_changed(self, company_id: int) -> None:
        try:
            self._service_types = self._api.get_service_types(company_id)
        except Exception:
            self._service_types = []
        self._st_combo.populate(self._service_types)
        if self._account:
            stid = self._account.get("service_type_id")
            for i in range(self._st_combo.count()):
                if self._st_combo.itemData(i) == stid:
                    self._st_combo.setCurrentIndex(i)
                    break

    def _on_accept(self) -> None:
        st_id = self._st_combo.selected_service_type_id()
        name = self._name_edit.text().strip()
        phone = self._phone_edit.text().strip()

        if not st_id:
            self._status_lbl.setText(t("col_service_type") + " required")
            return
        if not name:
            self._status_lbl.setText(t("col_name") + " required")
            return
        if not phone:
            self._status_lbl.setText(t("col_phone") + " required")
            return

        try:
            if self._account:
                self._api.update_account(self._account["id"], {
                    "service_type_id": st_id,
                    "account_name": name,
                    "phone_number": phone,
                })
            else:
                self._api.create_account(st_id, name, phone, float(self._balance_spin.value()))
            self.accept()
        except Exception as e:
            self._status_lbl.setText(str(e))


class _BalanceAdjustDialog(QDialog):
    def __init__(self, api: ApiClient, account: dict, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._account = account
        self.setWindowTitle(t("adjust_balance"))
        self.setMinimumWidth(380)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        current_balance = float(self._account.get("balance", 0))
        cur_lbl = QLabel(f"{current_balance:,.2f}")
        cur_lbl.setStyleSheet(f"color: {ACCENT_GREEN}; font-weight: bold; font-size: 14px;")
        form.addRow(t("lbl_current_balance") + ":", cur_lbl)

        self._amount_spin = QDoubleSpinBox()
        self._amount_spin.setRange(-999_999_999.0, 999_999_999.0)
        self._amount_spin.setDecimals(2)
        self._amount_spin.setSingleStep(1000.0)
        self._amount_spin.setPrefix("+/- ")
        self._amount_spin.setStyleSheet(
            f"background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 6px; padding: 6px 10px;"
        )
        form.addRow(t("lbl_adjustment") + ":", self._amount_spin)

        self._remark_edit = QTextEdit()
        self._remark_edit.setFixedHeight(72)
        self._remark_edit.setStyleSheet(
            f"background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 6px; padding: 6px 10px;"
        )
        form.addRow(t("lbl_remark") + ":", self._remark_edit)
        layout.addLayout(form)

        self._preview_lbl = QLabel("")
        self._preview_lbl.setStyleSheet(f"color: {ACCENT_YELLOW}; font-size: 12px;")
        layout.addWidget(self._preview_lbl)
        self._amount_spin.valueChanged.connect(self._update_preview)
        self._update_preview(0.0)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {ACCENT_RED}; font-size: 11px;")
        layout.addWidget(self._status_lbl)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _update_preview(self, _: float = 0.0) -> None:
        current = float(self._account.get("balance", 0))
        new_bal = current + self._amount_spin.value()
        color = ACCENT_GREEN if new_bal >= 0 else ACCENT_RED
        self._preview_lbl.setText(
            f"{current:,.2f}  →  "
            f"<span style='color:{color}; font-weight:bold'>{new_bal:,.2f}</span>"
        )
        self._preview_lbl.setTextFormat(Qt.TextFormat.RichText)

    def _on_accept(self) -> None:
        amount = self._amount_spin.value()
        remark = self._remark_edit.toPlainText().strip()
        if amount == 0.0:
            self._status_lbl.setText(t("lbl_adjustment") + " cannot be 0")
            return
        if not remark:
            self._status_lbl.setText(t("lbl_remark") + " required")
            return
        try:
            self._api.adjust_account_balance(self._account["id"], amount, remark)
            self.accept()
        except Exception as e:
            self._status_lbl.setText(str(e))


# ════════════════════════════════════════════
# Page 2: Accounts management
# ════════════════════════════════════════════
class AccountsPage(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._company_name_map: dict[int, str] = {}
        self._st_name_map: dict[int, str] = {}
        self._companies: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()

        # ── Header row ──
        header_row = QHBoxLayout()
        self._title_label = section_label(t("accounts_title"))
        header_row.addWidget(self._title_label)
        header_row.addStretch()
        self._add_btn = accent_btn(t("add_account"), ACCENT_BLUE)
        self._add_btn.clicked.connect(self._on_add)
        header_row.addWidget(self._add_btn)
        refresh_btn = accent_btn(t("refresh"), ACCENT_MAUVE)
        refresh_btn.clicked.connect(self.load_data)
        header_row.addWidget(refresh_btn)
        layout.addLayout(header_row)

        # ── Filter row ──
        filter_row = QHBoxLayout()
        self._company_filter = CompanySelector()
        self._company_filter.setMinimumWidth(160)
        self._st_filter = ServiceTypeSelector()
        self._st_filter.setMinimumWidth(160)
        self._company_filter.company_changed.connect(self._on_filter_company_changed)
        self._st_filter.service_type_changed.connect(self._on_filter_st_changed)
        filter_row.addWidget(QLabel(t("col_company") + ":"))
        filter_row.addWidget(self._company_filter)
        filter_row.addWidget(QLabel(t("col_service_type") + ":"))
        filter_row.addWidget(self._st_filter)
        load_all_btn = accent_btn(t("refresh"), ACCENT_TEAL)
        load_all_btn.clicked.connect(self.load_data)
        filter_row.addWidget(load_all_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # ── Status label ──
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
        layout.addWidget(self._status_lbl)

        # ── Table ──
        self._table = make_table([
            t("col_id"), t("col_company"), t("col_name"), t("col_phone"),
            t("col_service_type"), t("col_balance"), t("col_active"), t("col_action"),
        ], 400)
        layout.addWidget(self._table)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_data(self) -> None:
        try:
            self._companies = self._api.get_companies()
        except Exception:
            self._companies = []

        self._company_name_map = {c["id"]: c.get("name", "") for c in self._companies}
        self._st_name_map = {}
        for company in self._companies:
            try:
                sts = self._api.get_service_types(company["id"])
                for st in sts:
                    self._st_name_map[st["id"]] = st.get("name", "")
            except Exception:
                pass

        # Rebuild company filter while keeping current selection
        selected_cid = self._company_filter.selected_company_id()
        self._company_filter.blockSignals(True)
        self._company_filter.populate(self._companies, self._api)
        if selected_cid is not None:
            for i in range(self._company_filter.count()):
                if self._company_filter.itemData(i) == selected_cid:
                    self._company_filter.setCurrentIndex(i)
                    break
        self._company_filter.blockSignals(False)

        cid = self._company_filter.selected_company_id()
        stid = self._st_filter.selected_service_type_id()

        try:
            if stid:
                accounts = self._api.get_accounts(service_type_id=stid)
            elif cid:
                accounts = self._api.get_accounts(company_id=cid)
            else:
                accounts = self._api.get_accounts()
            self._populate(accounts)
        except Exception:
            pass

        is_owner = (self._api.user or {}).get("role") == "owner"
        self._add_btn.setVisible(is_owner)

    def _on_filter_company_changed(self, company_id: int) -> None:
        try:
            sts = self._api.get_service_types(company_id)
        except Exception:
            sts = []
        self._st_filter.populate(sts)
        try:
            accounts = self._api.get_accounts(company_id=company_id)
            self._populate(accounts)
        except Exception:
            pass

    def _on_filter_st_changed(self, st_id: int) -> None:
        try:
            accounts = self._api.get_accounts(service_type_id=st_id)
            self._populate(accounts)
        except Exception:
            pass

    def _populate(self, accounts: list[dict]) -> None:
        is_owner = (self._api.user or {}).get("role") == "owner"
        self._table.setRowCount(len(accounts))
        for row, acc in enumerate(accounts):
            cid = acc.get("company_id", "")
            stid = acc.get("service_type_id", "")
            items = [
                str(acc.get("id", "")),
                self._company_name_map.get(cid, str(cid)),
                acc.get("account_name", ""),
                acc.get("phone_number", ""),
                self._st_name_map.get(stid, str(stid)),
                f"{float(acc.get('balance', 0)):,.0f}",
                t("status_active") if acc.get("is_active") else t("status_inactive"),
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 5:
                    v = float(acc.get("balance", 0))
                    item.setForeground(QColor(ACCENT_GREEN if v >= 0 else ACCENT_RED))
                if col == 6:
                    c = ACCENT_GREEN if acc.get("is_active") else ACCENT_RED
                    item.setForeground(QColor(c))
                self._table.setItem(row, col, item)

            acc_id = acc.get("id")
            name = acc.get("account_name", "")
            active = bool(acc.get("is_active"))

            action_widget = QWidget()
            al = QHBoxLayout(action_widget)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(4)

            if is_owner:
                edit_btn = _ghost_btn(t("edit"), ACCENT_BLUE)
                edit_btn.clicked.connect(lambda _, a=acc: self._on_edit(a))
                al.addWidget(edit_btn)

                adj_btn = _ghost_btn(t("adjust_balance"), ACCENT_YELLOW)
                adj_btn.clicked.connect(lambda _, a=acc: self._on_adjust_balance(a))
                al.addWidget(adj_btn)

            toggle_color = ACCENT_RED if active else ACCENT_GREEN
            toggle_text = t("btn_deactivate") if active else t("btn_activate")
            toggle_btn = _ghost_btn(toggle_text, toggle_color)
            toggle_btn.clicked.connect(lambda _, aid=acc_id, cur=active: self._on_toggle(aid, cur))
            al.addWidget(toggle_btn)

            if is_owner:
                del_btn = _ghost_btn(t("delete"), ACCENT_RED)
                del_btn.clicked.connect(lambda _, aid=acc_id, n=name: self._on_delete(aid, n))
                al.addWidget(del_btn)

            self._table.setCellWidget(row, 7, action_widget)

    def _show_status(self, msg: str, error: bool = False) -> None:
        color = ACCENT_RED if error else ACCENT_GREEN
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._status_lbl.setText(msg)
        QTimer.singleShot(4000, lambda: self._status_lbl.setText(""))

    def _on_add(self) -> None:
        dlg = _AccountDialog(self._api, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._show_status(t("account_created"))
            self.load_data()

    def _on_edit(self, account: dict) -> None:
        dlg = _AccountDialog(self._api, parent=self, account=account)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._show_status(t("account_updated"))
            self.load_data()

    def _on_adjust_balance(self, account: dict) -> None:
        dlg = _BalanceAdjustDialog(self._api, account, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._show_status(t("balance_adjusted"))
            self.load_data()

    def _on_toggle(self, account_id: int, currently_active: bool) -> None:
        try:
            self._api.update_account(account_id, {"is_active": not currently_active})
            self._show_status(
                t("status_inactive") if currently_active else t("status_active")
            )
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _on_delete(self, account_id: int, account_name: str) -> None:
        reply = QMessageBox.warning(
            self,
            t("delete_account"),
            f"{t('confirm_delete_account')}\n\n"
            f"{t('col_name')}: {account_name}\n"
            f"ID: {account_id}\n\n"
            f"{t('action_cannot_be_undone')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._api.delete_account(account_id)
            self._show_status(t("account_deleted"))
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)


# ════════════════════════════════════════════
# Page 3: Reports (daily summary)
# ════════════════════════════════════════════
class ReportsPage(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()
        self._title_label = section_label(t("reports_title"))
        layout.addWidget(self._title_label)

        picker_row = QHBoxLayout()
        picker_row.addWidget(QLabel(t("date_label")))
        self._date_picker = QDateEdit(QDate.currentDate())
        self._date_picker.setCalendarPopup(True)
        picker_row.addWidget(self._date_picker)
        load_btn = accent_btn(t("load_report"))
        load_btn.clicked.connect(self._on_load)
        picker_row.addWidget(load_btn)
        picker_row.addStretch()
        layout.addLayout(picker_row)

        self._cards_frame = QFrame()
        self._cards_layout = QGridLayout(self._cards_frame)
        self._cards_layout.setSpacing(12)
        layout.addWidget(self._cards_frame)
        layout.addStretch()

        self._report_labels: dict[str, QLabel] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_data(self) -> None:
        self._on_load()

    def _on_load(self) -> None:
        try:
            d = self._date_picker.date().toString("yyyy-MM-dd")
            s = self._api.get_daily_report(d)
            self._show_report(s)
        except Exception:
            pass

    def _show_report(self, s: dict) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._report_labels.clear()

        items = [
            (t("total_deposit"), s.get("total_deposit", 0), ACCENT_GREEN),
            (t("total_withdraw"), s.get("total_withdraw", 0), ACCENT_RED),
            (t("total_transfer"), s.get("total_transfer", 0), ACCENT_BLUE),
            (t("total_exchange"), s.get("total_exchange", 0), ACCENT_YELLOW),
            (t("total_commission"), s.get("total_commission", 0), ACCENT_MAUVE),
            (t("total_customer_fees"), s.get("total_customer_fees", 0), ACCENT_TEAL),
            (t("txn_count"), s.get("transaction_count", 0), ACCENT_BLUE),
        ]
        for i, (label, value, color) in enumerate(items):
            r, c = divmod(i, 3)
            card = QFrame()
            card.setFixedHeight(90)
            card.setStyleSheet(
                f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; "
                f"border-left: 3px solid {color}; }}"
            )
            lo = QVBoxLayout(card)
            lo.setContentsMargins(14, 12, 14, 12)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            lo.addWidget(lbl)
            v = QLabel(f"{value:,.0f}" if isinstance(value, (int, float)) else str(value))
            v.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
            v.setStyleSheet(f"color: {color};")
            lo.addWidget(v)
            self._cards_layout.addWidget(card, r, c)


# ════════════════════════════════════════════
# Page 4: Employees
# ════════════════════════════════════════════
class AddEmployeeDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("add_user_dialog_title"))
        self.setFixedSize(350, 260)
        self.setStyleSheet(f"background-color: {BG_CARD}; color: {TEXT_PRIMARY};")

        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText(t("col_username"))
        layout.addRow(f"{t('col_username')}:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText(t("field_password"))
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow(f"{t('field_password')}:", self.password_input)

        self.fullname_input = QLineEdit()
        self.fullname_input.setPlaceholderText(t("col_fullname"))
        layout.addRow(f"{t('col_fullname')}:", self.fullname_input)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["employee", "cashier"])
        layout.addRow(t("role_label"), self.role_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)


class EmployeesPage(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()

        header = QHBoxLayout()
        header.addWidget(section_label(t("users_title")))
        header.addStretch()
        add_btn = accent_btn(t("add_user_btn"), ACCENT_GREEN)
        add_btn.clicked.connect(self._on_add)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self._table = make_table([
            t("col_id"), t("col_username"), t("col_fullname"),
            t("col_role"), t("col_active"), t("col_created"), t("col_action"),
        ])
        layout.addWidget(self._table)
        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setVisible(False)
        layout.addWidget(self._status)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_data(self) -> None:
        try:
            users = self._api.get_users()
            self._populate(users)
        except Exception:
            pass

    def _populate(self, users: list[dict]) -> None:
        self._users = users
        self._table.setRowCount(len(users))
        for row, u in enumerate(users):
            created = str(u.get("created_at", ""))[:10]
            items = [
                str(u.get("id", "")),
                u.get("username", ""),
                u.get("full_name", ""),
                u.get("role", ""),
                "Active" if u.get("is_active") else "Inactive",
                created,
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 4:
                    c = ACCENT_GREEN if u.get("is_active") else ACCENT_RED
                    item.setForeground(QColor(c))
                self._table.setItem(row, col, item)

            role = u.get("role", "")
            # Color-code role badge
            role_item = self._table.item(row, 3)
            if role_item:
                role_color = {
                    "owner":    ACCENT_BLUE,
                    "cashier":  ACCENT_MAUVE,
                    "employee": ACCENT_TEAL,
                }.get(role, TEXT_SECONDARY)
                role_item.setForeground(QColor(role_color))

            if role in ("employee", "cashier"):
                is_active = u.get("is_active", True)
                txt = "Deactivate" if is_active else "Activate"
                color = ACCENT_RED if is_active else ACCENT_GREEN
                btn = QPushButton(txt)
                btn.setStyleSheet(
                    f"QPushButton {{ background: {BG_DARK}; color: {color}; "
                    f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; }}"
                )
                btn.clicked.connect(lambda _, uid=u["id"], active=is_active: self._toggle(uid, active))
                self._table.setCellWidget(row, 6, btn)
            else:
                self._table.setItem(row, 6, QTableWidgetItem("—"))

    def _toggle(self, user_id: int, currently_active: bool) -> None:
        try:
            self._api.toggle_user_active(user_id, not currently_active)
            self.load_data()
        except Exception:
            pass

    def _on_add(self) -> None:
        try:
            dlg = AddEmployeeDialog(self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            u = dlg.username_input.text().strip()
            p = dlg.password_input.text().strip()
            f = dlg.fullname_input.text().strip()
            role = dlg.role_combo.currentText()
            if not u or not p or not f:
                self._status.setText("All fields are required.")
                self._status.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
                self._status.setVisible(True)
                return
            self._api.create_user(u, p, f, role=role)
            self._status.setText(f"{role.capitalize()} account '{u}' created successfully.")
            self._status.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
            self._status.setVisible(True)
            self.load_data()
        except Exception as e:
            self._status.setText(f"Error: {e}")
            self._status.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
            self._status.setVisible(True)


# ════════════════════════════════════════════
# Main DashboardView — unified single-sidebar layout
# ════════════════════════════════════════════
class DashboardView(QMainWindow):
    """
    Owner dashboard with a single unified sidebar.
    All navigation is in one sidebar — no secondary admin panel.
    """

    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self._api = api_client
        self._ws_thread: Optional[WebSocketThread] = None
        # idx → QPushButton
        self._nav_buttons: dict[int, QPushButton] = {}
        # idx → (i18n_key, icon_char) — used for retranslation
        self._nav_button_data: dict[int, tuple[str, str]] = {}
        self._current_page = 0
        self._init_ui()
        self._start_timers()
        self._start_websocket()
        self._pages[0].load_data()
        on_change(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self.setWindowTitle(f"{t('app_title')} — {fullname}")
        for idx, (key, icon) in self._nav_button_data.items():
            if idx in self._nav_buttons:
                self._nav_buttons[idx].setText(f"  {icon}  {t(key)}")
        if self._current_page in self._nav_button_data:
            key, _ = self._nav_button_data[self._current_page]
            self._page_title.setText(t(key))

    def _init_ui(self) -> None:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self.setWindowTitle(f"{t('app_title')} — {fullname}")
        self.setMinimumSize(1200, 750)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_sidebar())

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self._build_top_bar())

        self._stack = QStackedWidget()
        self._pages: list = []

        # Pages — indices must match _SIDEBAR_GROUPS page_idx values above
        for page in [
            DashboardPage(self._api),            # 0  Dashboard
            TransactionsPage(self._api),         # 1  All Transactions
            ActivityLogView(self._api),          # 2  Activity Logs
            AccountsPage(self._api),             # 3  Accounts
            ReportsPage(self._api),              # 4  Reports
            UserSettingsView(self._api),         # 5  Users
            CompanySettingsView(self._api),      # 6  Companies
            ServiceTypeSettingsView(self._api),  # 7  Service Types
            CommissionTierSubView(self._api),    # 8  Commission Tiers
            ExchangeRateSubView(self._api),      # 9  Exchange Rate
            CashFloatAdminView(self._api),       # 10 Cash Floats
            PasswordSubView(self._api),          # 11 Change Password
        ]:
            self._stack.addWidget(page)
            self._pages.append(page)

        right.addWidget(self._stack, 1)

        right_widget = QWidget()
        right_widget.setLayout(right)
        main_layout.addWidget(right_widget, 1)

        # Select first page after pages are wired up
        self._select(0)

    # ── Sidebar ─────────────────────────────────────────────

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar.setStyleSheet(f"background-color: {BG_SIDEBAR};")

        outer = QVBoxLayout(sidebar)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._sidebar_logo())

        # Divider below logo
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {BORDER_COLOR};")
        outer.addWidget(sep)

        # Scrollable nav items
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            f"QScrollBar:vertical {{ background: {BG_SIDEBAR}; width: 4px; border: none; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER_COLOR}; border-radius: 2px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        nav_widget = QWidget()
        nav_widget.setStyleSheet(f"background-color: {BG_SIDEBAR};")
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 8, 0, 8)
        nav_layout.setSpacing(0)

        for section_key, items in _SIDEBAR_GROUPS:
            if section_key is not None:
                nav_layout.addWidget(self._section_label(section_key))
            for item_key, idx, icon in items:
                btn = self._nav_btn(item_key, idx, icon)
                self._nav_buttons[idx] = btn
                self._nav_button_data[idx] = (item_key, icon)
                nav_layout.addWidget(btn)

        nav_layout.addStretch()
        scroll.setWidget(nav_widget)
        outer.addWidget(scroll, 1)

        # Logout pinned at bottom
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background-color: {BORDER_COLOR};")
        outer.addWidget(sep2)
        outer.addWidget(self._sidebar_logout_button())

        return sidebar

    def _sidebar_logo(self) -> QLabel:
        logo = QLabel(t("app_title"))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        logo.setStyleSheet(
            f"color: {ACCENT_BLUE}; padding: 18px 12px 16px 12px; "
            f"background-color: {BG_SIDEBAR};"
        )
        return logo

    def _section_label(self, i18n_key: str) -> QLabel:
        lbl = QLabel(t(i18n_key).upper())
        lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; padding: 14px 16px 4px 16px; "
            f"letter-spacing: 1.5px; background: transparent;"
        )
        return lbl

    def _nav_btn(self, i18n_key: str, idx: int, icon: str) -> QPushButton:
        btn = QPushButton(f"  {icon}  {t(i18n_key)}")
        btn.setFixedHeight(38)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFont(QFont("Segoe UI", 12))
        btn.setStyleSheet(self._btn_style(False))
        btn.clicked.connect(lambda _, i=idx: self._select(i))
        return btn

    def _sidebar_logout_button(self) -> QPushButton:
        btn = QPushButton(f"  ✕  {t('logout')}")
        btn.setFixedHeight(42)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFont(QFont("Segoe UI", 12))
        btn.setStyleSheet(
            f"QPushButton {{ text-align: left; background: transparent; color: {ACCENT_RED}; "
            f"border: none; border-left: 3px solid transparent; "
            f"padding-left: 13px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; color: {ACCENT_RED}; }}"
        )
        btn.clicked.connect(self._on_logout)
        return btn

    def _btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ text-align: left; background-color: {BG_CARD}; "
                f"color: {ACCENT_BLUE}; border: none; "
                f"border-left: 3px solid {ACCENT_BLUE}; "
                f"padding-left: 13px; font-size: 13px; }}"
                f"QPushButton:hover {{ background-color: {BG_CARD}; }}"
            )
        return (
            f"QPushButton {{ text-align: left; background-color: transparent; "
            f"color: {TEXT_SECONDARY}; border: none; "
            f"border-left: 3px solid transparent; "
            f"padding-left: 13px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; color: {TEXT_PRIMARY}; }}"
        )

    # ── Top bar ──────────────────────────────────────────────

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(60)
        bar.setStyleSheet(
            f"background-color: {BG_CONTENT}; "
            f"border-bottom: 1px solid {BORDER_COLOR};"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 10, 24, 10)

        self._page_title = QLabel(t("nav_dashboard"))
        self._page_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(self._page_title)
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
            self._time_label.setText(datetime.now(MMT).strftime("%d-%m-%Y  %I:%M:%S %p"))
        except Exception:
            pass

    # ── Navigation ───────────────────────────────────────────

    def _select(self, idx: int) -> None:
        try:
            self._current_page = idx
            self._stack.setCurrentIndex(idx)

            for i, btn in self._nav_buttons.items():
                btn.setStyleSheet(self._btn_style(i == idx))

            if idx in self._nav_button_data:
                key, _ = self._nav_button_data[idx]
                self._page_title.setText(t(key))

            page = self._pages[idx]
            if hasattr(page, "load_data"):
                page.load_data()
        except Exception:
            pass

    # Keep old name as alias so any external callers still work
    def _on_menu_click(self, index: int, key: str = "") -> None:
        self._select(index)

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
            if self._current_page == 0:
                self._pages[0].load_data()
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
                if self._current_page == 0:
                    self._pages[0].update_from_ws(accounts)
        except Exception:
            pass

    # ── Logout ──

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
