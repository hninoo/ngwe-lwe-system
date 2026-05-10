"""
views/settings/transaction_admin_view.py

Owner-only panel: read all transactions with filters, delete individual records.
"""
from typing import Optional

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from services.api_client import ApiClient

BG_DARK = "#1e1e2e"
BG_CARD = "#2a2a3e"
BG_INPUT = "#313244"
TEXT_PRIMARY = "#cdd6f4"
TEXT_SECONDARY = "#a6adc8"
ACCENT_BLUE = "#89b4fa"
ACCENT_GREEN = "#a6e3a1"
ACCENT_RED = "#f38ba8"
ACCENT_YELLOW = "#f9e2af"
ACCENT_TEAL = "#94e2d5"
BORDER_COLOR = "#313244"
INPUT_BORDER = "#585b70"

TXN_TYPE_COLORS = {
    "cash_in":  ACCENT_GREEN,
    "cash_out": ACCENT_RED,
    "transfer": ACCENT_BLUE,
    "exchange": ACCENT_YELLOW,
}

TXN_TYPES = ["", "cash_in", "cash_out", "transfer", "exchange"]


def _accent_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color}; color: {BG_DARK}; "
        f"border: none; border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: bold; }}"
    )
    return btn


def _ghost_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; color: {color}; border: 1px solid {color}; "
        f"border-radius: 4px; padding: 3px 8px; font-size: 11px; }}"
        f"QPushButton:hover {{ background-color: {BG_INPUT}; }}"
    )
    return btn


def _date_edit(default: QDate) -> QDateEdit:
    de = QDateEdit(default)
    de.setCalendarPopup(True)
    de.setDisplayFormat("yyyy-MM-dd")
    de.setStyleSheet(
        f"QDateEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
        f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 4px 8px; }}"
    )
    return de


class TransactionAdminView(QWidget):
    """Owner-only read + delete view for all transactions."""

    COLS = [
        "id", t("col_type"), t("col_account"), t("col_to_account"),
        t("col_customer"), t("col_amount"), t("col_fee"), t("col_commission"),
        t("col_currency"), t("col_created"), t("col_actions"),
    ]
    COL_ID = 0
    COL_TYPE = 1
    COL_ACCOUNT = 2
    COL_TO_ACC = 3
    COL_CUSTOMER = 4
    COL_AMOUNT = 5
    COL_FEE = 6
    COL_COMM = 7
    COL_CURRENCY = 8
    COL_CREATED = 9
    COL_ACTIONS = 10

    def __init__(self, api: ApiClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._api = api
        self._transactions: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Title
        header = QHBoxLayout()
        title = QLabel(t("admin_transactions"))
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(t("date_from") + ":"))
        today = QDate.currentDate()
        self._date_from = _date_edit(today.addDays(-30))
        filter_row.addWidget(self._date_from)
        filter_row.addWidget(QLabel(t("date_to") + ":"))
        self._date_to = _date_edit(today)
        filter_row.addWidget(self._date_to)

        filter_row.addWidget(QLabel(t("col_type") + ":"))
        self._type_filter = QComboBox()
        self._type_filter.addItems([t("all")] + TXN_TYPES[1:])
        self._type_filter.setFixedWidth(100)
        self._type_filter.setStyleSheet(
            f"QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 4px 8px; }}"
        )
        filter_row.addWidget(self._type_filter)

        load_btn = _accent_btn(t("btn_load"))
        load_btn.clicked.connect(self.load_data)
        filter_row.addWidget(load_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
        self._status.setVisible(False)
        layout.addWidget(self._status)

        # Table
        self._table = QTableWidget(0, len(self.COLS))
        self._table.setHorizontalHeaderLabels(self.COLS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(280)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._table.setStyleSheet(
            f"QTableWidget {{ background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; "
            f"gridline-color: {BORDER_COLOR}; font-size: 12px; }}"
            f"QHeaderView::section {{ background: {BG_DARK}; color: {TEXT_SECONDARY}; "
            f"border: none; padding: 6px; font-weight: bold; }}"
        )
        hdr = self._table.horizontalHeader()
        for i in range(len(self.COLS)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_CUSTOMER, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

    def load_data(self) -> None:
        date_from = self._date_from.date().toString("yyyy-MM-dd")
        date_to = self._date_to.date().toString("yyyy-MM-dd")
        idx = self._type_filter.currentIndex()
        txn_type = TXN_TYPES[idx] if idx > 0 else None
        try:
            self._transactions = self._api.get_all_transactions(
                date_from=date_from, date_to=date_to, txn_type=txn_type, limit=500
            )
        except Exception as e:
            self._show_status(str(e), error=True)
            self._transactions = []
        self._populate()

    def _populate(self) -> None:
        self._table.setRowCount(0)
        for row, txn in enumerate(self._transactions):
            self._table.insertRow(row)
            self._table.setRowHeight(row, 34)

            txn_id = txn.get("id", 0)
            txn_type = txn.get("transaction_type", "")
            amount = float(txn.get("amount", 0))
            fee = float(txn.get("customer_fee", 0))
            comm = float(txn.get("commission_amount", 0))
            customer = txn.get("customer_name", "") or "—"
            currency = txn.get("currency", "MMK")
            created = str(txn.get("created_at", ""))[:16]

            values = [
                str(txn_id),
                txn_type,
                str(txn.get("account_id", "")),
                str(txn.get("to_account_id", "") or "—"),
                customer,
                f"{amount:,.0f}",
                f"{fee:,.0f}",
                f"{comm:,.0f}",
                currency,
                created,
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == self.COL_TYPE:
                    item.setForeground(QColor(TXN_TYPE_COLORS.get(txn_type, TEXT_SECONDARY)))
                self._table.setItem(row, col, item)

            del_btn = QPushButton(t("delete"))
            del_btn.setStyleSheet(
                f"QPushButton {{ background: {BG_DARK}; color: {ACCENT_RED}; "
                f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; }}"
            )
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(lambda _, tid=txn_id: self._on_delete(tid))
            self._table.setCellWidget(row, self.COL_ACTIONS, del_btn)

    def _on_delete(self, txn_id: int) -> None:
        reply = QMessageBox.warning(
            self, t("delete"),
            f"{t('confirm_delete_txn')}\n\nID: {txn_id}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._api.delete_transaction(txn_id)
            self._show_status(f"Transaction {txn_id} deleted.")
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _show_status(self, msg: str, error: bool = False) -> None:
        color = ACCENT_RED if error else ACCENT_GREEN
        self._status.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._status.setText(msg)
        self._status.setVisible(True)
