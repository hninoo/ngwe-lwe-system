from typing import Optional

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from services.api_client import ApiClient
from views.transaction_view import (
    ACCENT_BLUE,
    BG_CARD,
    BG_DARK,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TYPE_COLORS,
    accent_btn,
    format_datetime,
    scrollable_page,
    section_label,
    _get_txn_headers,
)
from views.widgets.company_selector import add_placeholder


class HistoryPage(QWidget):
    HISTORY_COL_WIDTHS = [180, 100, 0, 140, 0, 140, 140, 90, 90, 120, 90]
    HISTORY_STRETCH = {2, 4}

    def __init__(self, api: ApiClient, navigate) -> None:
        super().__init__()
        self._api = api
        self._navigate = navigate
        self._all_filtered: list[dict] = []
        self._accounts_cache: list[dict] = []
        self._limit = 50
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()
        layout.addWidget(section_label(t("txn_history_title")))
        layout.addWidget(self._build_filters())
        self._table = QTableWidget(0, 11)
        self._table.setHorizontalHeaderLabels(_get_txn_headers())
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(400)
        self._table.setWordWrap(False)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        for i, w in enumerate(self.HISTORY_COL_WIDTHS):
            if i in self.HISTORY_STRETCH:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(i, int(w))
        layout.addWidget(self._table)
        self._load_more_btn = accent_btn(t("load_more"))
        self._load_more_btn.clicked.connect(self._on_load_more)
        self._load_more_btn.setVisible(False)
        layout.addWidget(self._load_more_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _build_filters(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; border: 1px solid {BORDER_COLOR}; }}")
        lo = QHBoxLayout(frame)
        lo.setContentsMargins(14, 10, 14, 10)
        lo.setSpacing(12)
        lo.addWidget(QLabel(t("filter_from")))
        self._date_from = QDateEdit(QDate.currentDate())
        self._date_from.setCalendarPopup(True)
        lo.addWidget(self._date_from)
        lo.addWidget(QLabel(t("filter_to")))
        self._date_to = QDateEdit(QDate.currentDate())
        self._date_to.setCalendarPopup(True)
        lo.addWidget(self._date_to)
        lo.addWidget(QLabel(t("filter_type")))
        self._type_filter = QComboBox()
        add_placeholder(self._type_filter)
        self._type_filter.addItems(["All", "deposit", "withdraw", "transfer", "exchange"])
        lo.addWidget(self._type_filter)

        lo.addWidget(QLabel(t("filter_phone")))
        self._phone_filter = QLineEdit()
        self._phone_filter.setPlaceholderText(t("filter_phone_ph"))
        self._phone_filter.setFixedWidth(180)
        self._phone_filter.returnPressed.connect(self._on_search)
        lo.addWidget(self._phone_filter)

        btn = accent_btn(t("search"))
        btn.clicked.connect(self._on_search)
        lo.addWidget(btn)
        lo.addStretch()
        return frame

    def load_data(self) -> None:
        try:
            self._accounts_cache = self._api.get_accounts()
        except Exception:
            pass
        self._on_search()

    def _on_search(self) -> None:
        try:
            txns = self._api.get_recent_transactions(500)
            d_from = self._date_from.date().toString("yyyy-MM-dd")
            d_to = self._date_to.date().toString("yyyy-MM-dd")
            t_type = self._type_filter.currentText()
            phone_q = self._phone_filter.text().strip().lower()
            self._all_filtered = [tx for tx in txns
                if d_from <= str(tx.get("created_at", ""))[:10] <= d_to
                and (self._type_filter.currentIndex() <= 1 or tx.get("transaction_type") == t_type)
                and self._matches_phone(tx, phone_q)]
            self._show_rows(self._all_filtered[:self._limit])
            self._load_more_btn.setVisible(len(self._all_filtered) > self._limit)
        except Exception:
            pass

    def _on_load_more(self) -> None:
        try:
            current = self._table.rowCount()
            end = current + self._limit
            self._show_rows(self._all_filtered[:end])
            self._load_more_btn.setVisible(end < len(self._all_filtered))
        except Exception:
            pass

    def _matches_phone(self, txn: dict, query: str) -> bool:
        if not query:
            return True
        acc = self._lookup_account(txn.get("account_id"))
        fields = [
            str(txn.get("customer_phone", "") or "").lower(),
            str(txn.get("customer_name", "") or "").lower(),
            (acc.get("phone_number", "") or "").lower() if acc else "",
            (acc.get("account_name", "") or "").lower() if acc else "",
        ]
        return any(query in f for f in fields)

    def _show_rows(self, txns: list[dict]) -> None:
        self._table.setRowCount(len(txns))
        for row, txn in enumerate(txns):
            tt = txn.get("transaction_type", "")
            has_cust = tt in ("deposit", "withdraw")
            acc = self._lookup_account(txn.get("account_id"))
            fee_acc = self._lookup_account(txn.get("fee_account_id"))
            items = [
                format_datetime(txn.get("created_at", "")), tt,
                acc.get("account_name", "") if acc else str(txn.get("account_id", "")),
                acc.get("phone_number", "") if acc else "",
                (txn.get("customer_name", "") or "—") if has_cust else "—",
                (txn.get("customer_phone", "") or "—") if has_cust else "—",
                f"{float(txn.get('amount', 0)):,.0f}",
                f"{float(txn.get('commission_amount', 0)):,.0f}",
                f"{float(txn.get('customer_fee', 0)):,.0f}",
                fee_acc.get("account_name", "") if fee_acc else "—",
            ]
            left = {2, 3, 4, 5, 9}
            right = {6, 7, 8}
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                if col in left:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                elif col in right:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(text)
                if col == 1:
                    item.setForeground(QColor(TYPE_COLORS.get(tt, TEXT_PRIMARY)))
                self._table.setItem(row, col, item)
            path = txn.get("screenshot_path", "")
            if path:
                btn = QPushButton(t("view"))
                btn.setStyleSheet(f"QPushButton {{ background: {BG_DARK}; color: {ACCENT_BLUE}; border: none; border-radius: 4px; padding: 2px 6px; font-size: 11px; }}")
                btn.clicked.connect(lambda _, p=path: self._view_screenshot(p))
                self._table.setCellWidget(row, 10, btn)
            else:
                self._table.setItem(row, 10, QTableWidgetItem(""))
            self._table.setRowHeight(row, 30)

    def _lookup_account(self, account_id) -> Optional[dict]:
        if not account_id:
            return None
        for acc in self._accounts_cache:
            if acc.get("id") == account_id:
                return acc
        return None

    def _view_screenshot(self, path: str) -> None:
        try:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                return
            dlg = QDialog(self)
            dlg.setWindowTitle(t("screenshot_title"))
            dlg.setMinimumSize(600, 400)
            dlg.setStyleSheet(f"background-color: {BG_DARK};")
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("border: none;")
            img = QLabel()
            img.setPixmap(pixmap.scaledToWidth(min(pixmap.width(), 800), Qt.TransformationMode.SmoothTransformation))
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scroll.setWidget(img)
            lo = QVBoxLayout(dlg)
            lo.setContentsMargins(0, 0, 0, 0)
            lo.addWidget(scroll)
            dlg.exec()
        except Exception:
            pass
