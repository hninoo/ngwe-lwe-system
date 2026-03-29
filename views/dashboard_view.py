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
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
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

SIDEBAR_WIDTH = 200
REFRESH_INTERVAL_MS = 30000
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8000/ws")

TYPE_COLORS = {
    "deposit": ACCENT_GREEN,
    "withdraw": ACCENT_RED,
    "transfer": ACCENT_BLUE,
    "exchange": ACCENT_YELLOW,
}

MENU_ITEMS = [
    ("Dashboard", "dashboard", 0),
    ("Transactions", "transactions", 1),
    ("Accounts", "accounts", 2),
    ("Reports", "reports", 3),
    ("Employees", "employees", 4),
    ("Settings", "settings", 5),
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
        layout.addWidget(section_label("Today's Summary"))
        layout.addWidget(self._build_stats_row())
        layout.addWidget(section_label("Account Balances"))
        self._grid_container = QWidget()
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(12)
        layout.addWidget(self._grid_container)
        layout.addWidget(section_label("Recent Transactions"))
        self._txn_table = make_table([
            "Time", "Employee", "Type", "Service", "Account",
            "Amount", "Commission", "Fee", "Screenshot",
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
        lo = QVBoxLayout(card)
        lo.setContentsMargins(14, 12, 14, 12)
        t = QLabel(label)
        t.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
        lo.addWidget(t)
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
        top.addWidget(type_badge(acc.get("account_type", "personal")))
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
            btn = QPushButton("View" if path else "-")
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
        layout.addWidget(section_label("Transaction History"))
        layout.addWidget(self._build_filters())
        self._table = make_table([
            "Time", "Employee", "Type", "Service", "Account",
            "Amount", "Commission", "Fee", "Screenshot",
        ], 400)
        layout.addWidget(self._table)
        self._load_more_btn = accent_btn("Load More")
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

        lo.addWidget(QLabel("From:"))
        self._date_from = QDateEdit(QDate.currentDate().addDays(-7))
        self._date_from.setCalendarPopup(True)
        lo.addWidget(self._date_from)

        lo.addWidget(QLabel("To:"))
        self._date_to = QDateEdit(QDate.currentDate())
        self._date_to.setCalendarPopup(True)
        lo.addWidget(self._date_to)

        lo.addWidget(QLabel("Type:"))
        self._type_filter = QComboBox()
        self._type_filter.addItems(["All", "deposit", "withdraw", "transfer", "exchange"])
        lo.addWidget(self._type_filter)

        search_btn = accent_btn("Search")
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
        for t in txns:
            created = str(t.get("created_at", ""))[:10]
            if created < d_from or created > d_to:
                continue
            if t_type != "All" and t.get("transaction_type") != t_type:
                continue
            result.append(t)
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
            btn = QPushButton("View" if path else "-")
            btn.setEnabled(bool(path))
            btn.setStyleSheet(
                f"QPushButton {{ background: {BG_DARK}; color: {ACCENT_BLUE}; "
                f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; }}"
            )
            self._table.setCellWidget(row, 8, btn)


# ════════════════════════════════════════════
# Page 2: Accounts management
# ════════════════════════════════════════════
class AccountsPage(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()
        layout.addWidget(section_label("Accounts Management"))
        self._table = make_table([
            "ID", "Service", "Name", "Phone", "Type",
            "Balance", "Commission %", "Active", "Action",
        ], 400)
        layout.addWidget(self._table)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_data(self) -> None:
        try:
            accounts = self._api.get_accounts()
            self._populate(accounts)
        except Exception:
            pass

    def _populate(self, accounts: list[dict]) -> None:
        self._table.setRowCount(len(accounts))
        for row, acc in enumerate(accounts):
            items = [
                str(acc.get("id", "")),
                str(acc.get("service_id", "")),
                acc.get("account_name", ""),
                acc.get("phone_number", ""),
                acc.get("account_type", ""),
                f"{float(acc.get('balance', 0)):,.0f}",
                f"{float(acc.get('commission_rate', 0)):.2%}",
                "Active" if acc.get("is_active") else "Inactive",
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 4:
                    c = ACCENT_TEAL if text == "agent" else TEXT_MUTED
                    item.setForeground(QColor(c))
                if col == 5:
                    v = float(acc.get("balance", 0))
                    item.setForeground(QColor(ACCENT_GREEN if v >= 0 else ACCENT_RED))
                if col == 7:
                    c = ACCENT_GREEN if acc.get("is_active") else ACCENT_RED
                    item.setForeground(QColor(c))
                self._table.setItem(row, col, item)

            toggle_text = "Deactivate" if acc.get("is_active") else "Activate"
            toggle_btn = QPushButton(toggle_text)
            toggle_btn.setStyleSheet(
                f"QPushButton {{ background: {BG_DARK}; color: {ACCENT_YELLOW}; "
                f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; }}"
            )
            self._table.setCellWidget(row, 8, toggle_btn)


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
        layout.addWidget(section_label("Daily Report"))

        picker_row = QHBoxLayout()
        picker_row.addWidget(QLabel("Date:"))
        self._date_picker = QDateEdit(QDate.currentDate())
        self._date_picker.setCalendarPopup(True)
        picker_row.addWidget(self._date_picker)
        load_btn = accent_btn("Load Report")
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
            ("Total Deposit", s.get("total_deposit", 0), ACCENT_GREEN),
            ("Total Withdraw", s.get("total_withdraw", 0), ACCENT_RED),
            ("Total Transfer", s.get("total_transfer", 0), ACCENT_BLUE),
            ("Total Exchange", s.get("total_exchange", 0), ACCENT_YELLOW),
            ("Total Commission", s.get("total_commission", 0), ACCENT_MAUVE),
            ("Total Customer Fees", s.get("total_customer_fees", 0), ACCENT_TEAL),
            ("Transaction Count", s.get("transaction_count", 0), ACCENT_BLUE),
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
            t = QLabel(label)
            t.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
            lo.addWidget(t)
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
        self.setWindowTitle("Add Employee")
        self.setFixedSize(350, 220)
        self.setStyleSheet(f"background-color: {BG_CARD}; color: {TEXT_PRIMARY};")

        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        layout.addRow("Username:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Password:", self.password_input)

        self.fullname_input = QLineEdit()
        self.fullname_input.setPlaceholderText("Full Name")
        layout.addRow("Full Name:", self.fullname_input)

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
        header.addWidget(section_label("Employees"))
        header.addStretch()
        add_btn = accent_btn("+ Add Employee", ACCENT_GREEN)
        add_btn.clicked.connect(self._on_add)
        header.addWidget(add_btn)
        layout.addLayout(header)

        self._table = make_table([
            "ID", "Username", "Full Name", "Role", "Active", "Created", "Action",
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

            if u.get("role") == "employee":
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
            if not u or not p or not f:
                self._status.setText("All fields required")
                self._status.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
                self._status.setVisible(True)
                return
            self._api.create_user(u, p, f)
            self._status.setText(f"Employee '{u}' created")
            self._status.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
            self._status.setVisible(True)
            self.load_data()
        except Exception as e:
            self._status.setText(f"Error: {e}")
            self._status.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
            self._status.setVisible(True)


# ════════════════════════════════════════════
# Page 5: Settings
# ════════════════════════════════════════════
class SettingsPage(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()

        # Exchange rate section
        layout.addWidget(section_label("Exchange Rate (MMK/THB)"))
        rate_card = card_frame()
        rate_lo = QVBoxLayout(rate_card)
        rate_lo.setContentsMargins(20, 16, 20, 16)
        rate_lo.setSpacing(10)

        self._current_rate_label = QLabel("Current: —")
        self._current_rate_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        rate_lo.addWidget(self._current_rate_label)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Buy Rate:"))
        self._buy_input = QLineEdit()
        self._buy_input.setPlaceholderText("0.0000")
        row1.addWidget(self._buy_input)
        row1.addWidget(QLabel("Sell Rate:"))
        self._sell_input = QLineEdit()
        self._sell_input.setPlaceholderText("0.0000")
        row1.addWidget(self._sell_input)
        rate_lo.addLayout(row1)

        save_rate_btn = accent_btn("Save Rate")
        save_rate_btn.clicked.connect(self._on_save_rate)
        rate_lo.addWidget(save_rate_btn)
        self._rate_status = QLabel("")
        self._rate_status.setVisible(False)
        rate_lo.addWidget(self._rate_status)

        layout.addWidget(rate_card)

        # Change password section
        layout.addSpacing(10)
        layout.addWidget(section_label("Change Password"))
        pw_card = card_frame()
        pw_lo = QVBoxLayout(pw_card)
        pw_lo.setContentsMargins(20, 16, 20, 16)
        pw_lo.setSpacing(10)

        self._old_pw = QLineEdit()
        self._old_pw.setPlaceholderText("Current Password")
        self._old_pw.setEchoMode(QLineEdit.EchoMode.Password)
        pw_lo.addWidget(self._old_pw)

        self._new_pw = QLineEdit()
        self._new_pw.setPlaceholderText("New Password")
        self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        pw_lo.addWidget(self._new_pw)

        self._confirm_pw = QLineEdit()
        self._confirm_pw.setPlaceholderText("Confirm New Password")
        self._confirm_pw.setEchoMode(QLineEdit.EchoMode.Password)
        pw_lo.addWidget(self._confirm_pw)

        save_pw_btn = accent_btn("Change Password")
        save_pw_btn.clicked.connect(self._on_save_password)
        pw_lo.addWidget(save_pw_btn)
        self._pw_status = QLabel("")
        self._pw_status.setVisible(False)
        pw_lo.addWidget(self._pw_status)

        layout.addWidget(pw_card)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_data(self) -> None:
        try:
            rate = self._api.get_exchange_rate()
            buy = rate.get("buy_rate", 0)
            sell = rate.get("sell_rate", 0)
            self._current_rate_label.setText(f"Current: Buy {buy:.4f} / Sell {sell:.4f}")
            self._buy_input.setText(str(buy) if buy else "")
            self._sell_input.setText(str(sell) if sell else "")
        except Exception:
            pass

    def _on_save_rate(self) -> None:
        try:
            buy = float(self._buy_input.text())
            sell = float(self._sell_input.text())
            self._api.update_exchange_rate(buy, sell)
            self._rate_status.setText("Rate saved!")
            self._rate_status.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
            self._rate_status.setVisible(True)
            self.load_data()
        except Exception as e:
            self._rate_status.setText(f"Error: {e}")
            self._rate_status.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
            self._rate_status.setVisible(True)

    def _on_save_password(self) -> None:
        try:
            old = self._old_pw.text()
            new = self._new_pw.text()
            confirm = self._confirm_pw.text()
            if not old or not new:
                self._pw_status.setText("Fill all fields")
                self._pw_status.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
                self._pw_status.setVisible(True)
                return
            if new != confirm:
                self._pw_status.setText("Passwords do not match")
                self._pw_status.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
                self._pw_status.setVisible(True)
                return
            self._api.change_password(old, new)
            self._pw_status.setText("Password changed!")
            self._pw_status.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
            self._pw_status.setVisible(True)
            self._old_pw.clear()
            self._new_pw.clear()
            self._confirm_pw.clear()
        except Exception as e:
            self._pw_status.setText(f"Error: {e}")
            self._pw_status.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
            self._pw_status.setVisible(True)


# ════════════════════════════════════════════
# Main DashboardView — QStackedWidget host
# ════════════════════════════════════════════
class DashboardView(QMainWindow):

    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self._api = api_client
        self._ws_thread: Optional[WebSocketThread] = None
        self._menu_buttons: dict[str, QPushButton] = {}
        self._current_page = 0
        self._init_ui()
        self._start_timers()
        self._start_websocket()
        self._pages[0].load_data()

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

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        right.addWidget(self._build_top_bar())

        self._stack = QStackedWidget()
        self._pages: list = []

        p0 = DashboardPage(self._api)
        p1 = TransactionsPage(self._api)
        p2 = AccountsPage(self._api)
        p3 = ReportsPage(self._api)
        p4 = EmployeesPage(self._api)
        p5 = SettingsPage(self._api)

        for p in [p0, p1, p2, p3, p4, p5]:
            self._stack.addWidget(p)
            self._pages.append(p)

        right.addWidget(self._stack, 1)

        right_widget = QWidget()
        right_widget.setLayout(right)
        main_layout.addWidget(right_widget, 1)

    # ── Sidebar ──

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar.setStyleSheet(f"background-color: {BG_SIDEBAR};")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar_logo())
        layout.addSpacing(10)
        for label, key, idx in MENU_ITEMS:
            layout.addWidget(self._sidebar_button(label, key, idx))
        layout.addStretch()
        layout.addWidget(self._sidebar_logout_button())
        return sidebar

    def _sidebar_logo(self) -> QLabel:
        logo = QLabel("ငွေလွှဲ System")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        logo.setStyleSheet(f"color: {ACCENT_BLUE}; padding: 20px 10px;")
        return logo

    def _sidebar_button(self, label: str, key: str, idx: int) -> QPushButton:
        btn = QPushButton(f"  {label}")
        btn.setFixedHeight(42)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(self._menu_style(idx == 0))
        btn.clicked.connect(lambda _, i=idx, k=key: self._on_menu_click(i, k))
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

    # ── Top bar ──

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"background-color: {BG_CONTENT};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 10, 24, 10)

        self._page_title = QLabel("Owner Dashboard")
        self._page_title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
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

    # ── Navigation ──

    def _on_menu_click(self, index: int, key: str) -> None:
        try:
            self._current_page = index
            self._stack.setCurrentIndex(index)
            for k, btn in self._menu_buttons.items():
                btn.setStyleSheet(self._menu_style(k == key))

            titles = {
                0: "Owner Dashboard", 1: "Transactions",
                2: "Accounts", 3: "Reports",
                4: "Employees", 5: "Settings",
            }
            self._page_title.setText(titles.get(index, ""))

            page = self._pages[index]
            if hasattr(page, "load_data"):
                page.load_data()
        except Exception:
            pass

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
