from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from repositories.transaction_ui_repository import TransactionUiRepository
from services.api_client import ApiClient
from views.components.input_validation import sanitize_text
from views.ui.theme import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_RED,
    BG_CARD,
    BG_DARK,
    BORDER_COLOR,
    TEXT_MUTED,
    TEXT_PRIMARY,
)


def _scrollable_page() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet(f"border: none; background-color: {BG_DARK};")
    container = QWidget()
    container.setStyleSheet(f"background-color: {BG_DARK};")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(24, 20, 24, 24)
    layout.setSpacing(14)
    scroll.setWidget(container)
    return scroll, layout


def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    label.setStyleSheet(f"color: {TEXT_PRIMARY};")
    return label


def _accent_btn(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        f"QPushButton {{ background-color: {ACCENT_BLUE}; color: #ffffff; "
        f"border: none; border-radius: 6px; padding: 8px 16px; "
        f"font-size: 12px; font-weight: bold; }}"
        f"QPushButton:hover {{ background-color: {ACCENT_GREEN}; }}"
    )
    return button


class AccountOverviewView(QWidget):
    """Employee-facing account balance overview list."""

    COL_WIDTHS = [70, 220, 170, 130, 120, 150]
    STRETCH_COLS = {1}

    def __init__(self, repository: TransactionUiRepository, navigate) -> None:
        super().__init__()
        self._repository = repository
        self._navigate = navigate
        self._accounts: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = _scrollable_page()
        layout.addWidget(_section_label(t("account_overview_title")))
        layout.addWidget(self._build_filters())

        self._summary = QLabel("")
        self._summary.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        layout.addWidget(self._summary)

        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels([
            t("col_id"),
            t("col_account_name"),
            t("col_phone"),
            t("col_service"),
            t("col_status"),
            t("col_balance"),
        ])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(420)
        self._table.setWordWrap(False)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        for index, width in enumerate(self.COL_WIDTHS):
            if index in self.STRETCH_COLS:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(index, width)
        layout.addWidget(self._table)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _build_filters(self) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; "
            f"border: 1px solid {BORDER_COLOR}; }}"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)

        label = QLabel(t("search"))
        row.addWidget(label)

        self._search = QLineEdit()
        self._search.setPlaceholderText(t("account_overview_search_ph"))
        self._search.setFixedWidth(260)
        self._search.returnPressed.connect(self._apply_filter)
        row.addWidget(self._search)

        search_btn = _accent_btn(t("search"))
        search_btn.clicked.connect(self._apply_filter)
        row.addWidget(search_btn)

        refresh_btn = QPushButton(t("refresh"))
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {ACCENT_BLUE}; "
            f"border: 1px solid {ACCENT_BLUE}; border-radius: 6px; "
            f"padding: 7px 14px; font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; color: {TEXT_PRIMARY}; }}"
        )
        refresh_btn.clicked.connect(self.load_data)
        row.addWidget(refresh_btn)

        back_btn = QPushButton(t("back"))
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {TEXT_MUTED}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 6px; "
            f"padding: 7px 14px; font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ color: {TEXT_PRIMARY}; }}"
        )
        back_btn.clicked.connect(lambda: self._navigate(0))
        row.addWidget(back_btn)
        row.addStretch()
        return frame

    def load_data(self) -> None:
        try:
            self._accounts = self._repository.get_accounts()
        except Exception:
            self._accounts = []
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = sanitize_text(self._search.text(), 80).lower()
        accounts = [
            account for account in self._accounts
            if self._matches_query(account, query)
        ]
        self._show_rows(accounts)

    def _matches_query(self, account: dict, query: str) -> bool:
        if not query:
            return True
        fields = [
            str(account.get("id", "")),
            str(account.get("account_name", "") or "").lower(),
            str(account.get("phone_number", "") or "").lower(),
            str(account.get("service_type_id", "") or "").lower(),
        ]
        return any(query in field for field in fields)

    def _show_rows(self, accounts: list[dict]) -> None:
        total_balance = sum(float(account.get("balance", 0) or 0) for account in accounts)
        self._summary.setText(
            t("account_overview_summary", count=len(accounts), total=f"{total_balance:,.0f}")
        )
        self._table.setRowCount(len(accounts))
        for row, account in enumerate(accounts):
            balance = float(account.get("balance", 0) or 0)
            values = [
                str(account.get("id", "")),
                str(account.get("account_name", "")),
                str(account.get("phone_number", "")),
                str(account.get("service_type_id", "")),
                t("active") if account.get("is_active", True) else t("inactive"),
                f"{balance:,.0f} MMK",
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col in {1, 2}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                elif col == 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
                    item.setForeground(QColor(ACCENT_GREEN if balance >= 0 else ACCENT_RED))
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(text)
                self._table.setItem(row, col, item)
            self._table.setRowHeight(row, 32)


class AccountOverviewWindow(QMainWindow):
    """Standalone employee account overview window."""

    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self.setWindowTitle(t("account_overview_title"))
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(
            f"QMainWindow {{ background-color: {BG_DARK}; }} QWidget {{ color: {TEXT_PRIMARY}; }}"
        )
        repository = TransactionUiRepository(api)
        self._page = AccountOverviewView(repository, self._go_dashboard)
        self.setCentralWidget(self._page)
        self._page.load_data()

    def _go_dashboard(self, *_args) -> None:
        from views.dashboard_view import DashboardView

        self._dashboard = DashboardView(self._api)
        self._dashboard.show()
        self.close()
