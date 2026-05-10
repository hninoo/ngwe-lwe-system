from datetime import datetime, timezone, timedelta
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QDate, QSize, pyqtSignal
from PyQt6.QtGui import QFont, QKeyEvent, QColor, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpacerItem,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from i18n import t, on_change
from repositories.history_repository import HistoryRepository
from repositories.profile_repository import ProfileRepository
from repositories.transaction_ui_repository import TransactionUiRepository
from services.api_client import ApiClient
from views.widgets.company_selector import ServiceTypeSelector, AccountSelector, add_placeholder
from views.widgets.company_logo_label import get_logo_pixmap

MMT = timezone(timedelta(hours=6, minutes=30))

# ── Colors ──
BG_DARK = "#1e1e2e"
BG_CARD = "#2a2a3e"
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
BG_INPUT = "#313244"
INPUT_BORDER = "#585b70"
SUCCESS_COLOR = "#a6e3a1"
ERROR_COLOR = "#f38ba8"

TYPE_COLORS = {
    "cash_in": ACCENT_GREEN,
    "cash_out": ACCENT_RED,
    "transfer": ACCENT_BLUE,
    "exchange": ACCENT_YELLOW,
}

TRANSACTION_TYPE_ALIASES = {
    "cash_in": "cash_in",
    "cash out": "cash_out",
    "cash_out": "cash_out",
    "cash in": "cash_in",
    "cash_in": "cash_in",
    "cash_out": "cash_out",
    "transfer": "transfer",
    "exchange": "exchange",
    "history": "history",
    "profile": "profile",
}

TXN_TABLE_HEADERS = {
    "cash_in": ["Time", "Type", "Account", "Customer", "Phone", "Amount", "Fee/Commission", "Fee Account"],
    "cash_out": ["Time", "Type", "Account", "Customer", "Phone", "Amount", "Fee/Commission", "Fee Account"],
    "transfer": ["Time", "Source Acc", "Target Acc", "Amount", "Fee"],
    "exchange": ["Time", "Source", "Target", "Rate", "Fee"],
}


def normalize_transaction_type(transaction_type: str | None) -> str:
    return TRANSACTION_TYPE_ALIASES.get((transaction_type or "cash_in").strip().lower(), "cash_in")

def _get_actions():
    return [
        ("cash_in", "Cash In", ACCENT_GREEN),
        ("cash_out", "Cash Out", ACCENT_RED),
        ("transfer", "Transfer", ACCENT_BLUE),
        ("exchange", "Exchange", ACCENT_YELLOW),
    ]


def _get_txn_headers():
    return [
        t("col_date_time"), t("col_type"), t("col_account_name"), t("col_account_number"),
        t("col_customer"), t("col_customer_phone"), t("col_amount"), t("col_commission"),
        t("col_fee"), t("col_fee_account"), t("col_screenshot"),
    ]

INPUT_STYLE = (
    f"QLineEdit, QTextEdit, QComboBox, QDateEdit {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; "
    f"border: 1px solid {INPUT_BORDER}; border-radius: 6px; padding: 8px 12px; font-size: 13px; }} "
    f"QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{ border: 1px solid {ACCENT_BLUE}; }} "
    f"QComboBox::drop-down {{ border: none; }} "
    f"QComboBox QAbstractItemView {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; "
    f"selection-background-color: {BG_CARD}; }}"
)

STYLESHEET = f"""
    QMainWindow {{ background-color: {BG_DARK}; }}
    QWidget {{ color: {TEXT_PRIMARY}; }}
    QScrollArea {{ border: none; background-color: {BG_DARK}; }}
    QScrollBar:vertical {{ background: {BG_DARK}; width: 8px; border: none; }}
    QScrollBar::handle:vertical {{ background: {BORDER_COLOR}; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QTableWidget {{ background-color: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; gridline-color: {BORDER_COLOR}; font-size: 12px; }}
    QTableWidget::item {{ padding: 6px; }}
    QHeaderView::section {{ background-color: {BG_DARK}; color: {TEXT_SECONDARY}; border: none; padding: 8px; font-weight: bold; font-size: 12px; }}
    {INPUT_STYLE}
"""

FEE_CASH_ITEM = {"id": 0, "account_name": "Cash", "phone_number": ""}


class TabTextEdit(QTextEdit):
    def __init__(self, on_enter=None) -> None:
        super().__init__()
        self._on_enter = on_enter

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                super().keyPressEvent(event)
            elif self._on_enter:
                self._on_enter()
            else:
                self.focusNextChild()
        else:
            super().keyPressEvent(event)


# ── Shared helpers ──
def section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    return label


def field_label(text: str, required: bool = False) -> QLabel:
    if required:
        label = QLabel(f'{text} <span style="color: {ACCENT_RED};">*</span>')
        label.setTextFormat(Qt.TextFormat.RichText)
    else:
        label = QLabel(text)
    label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
    return label


def back_button(callback) -> QPushButton:
    btn = QPushButton(t("back"))
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedWidth(80)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; color: {ACCENT_BLUE}; "
        f"border: none; font-size: 13px; font-weight: bold; text-align: left; }}"
        f"QPushButton:hover {{ color: {TEXT_PRIMARY}; }}"
    )
    btn.clicked.connect(callback)
    return btn


def accent_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color}; color: {BG_DARK}; "
        f"border: none; border-radius: 8px; padding: 10px 20px; "
        f"font-size: 14px; font-weight: bold; }}"
        f"QPushButton:hover {{ opacity: 0.8; }}"
    )
    return btn


def scrollable_page() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    container = QWidget()
    container.setStyleSheet(f"background-color: {BG_DARK};")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(24, 16, 24, 24)
    layout.setSpacing(16)
    scroll.setWidget(container)
    return scroll, layout


def format_datetime(raw) -> str:
    try:
        dt = datetime.fromisoformat(str(raw)).astimezone(MMT)
        return dt.strftime("%d-%m-%Y %I:%M:%S %p")
    except (ValueError, TypeError):
        return str(raw)


# ════════════════════════════════════════════
# Company Grid Selector
# ════════════════════════════════════════════
class _CompanyTile(QFrame):
    """Single selectable company tile: logo + name label."""

    clicked_id = pyqtSignal(int)
    W, H = 90, 80

    def __init__(self, company_id: int, name: str, pixmap: QPixmap, parent=None) -> None:
        super().__init__(parent)
        self._company_id = company_id
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(name)

        lo = QVBoxLayout(self)
        lo.setContentsMargins(4, 8, 4, 5)
        lo.setSpacing(4)
        lo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(
            pixmap.scaled(QSize(38, 38), Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
        )
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("border: none; background: transparent;")
        lo.addWidget(icon_lbl)

        short = name if len(name) <= 11 else name[:10] + "…"
        name_lbl = QLabel(short)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_lbl.setStyleSheet(
            f"font-size: 10px; color: {TEXT_SECONDARY}; border: none; background: transparent;"
        )
        lo.addWidget(name_lbl)

        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(
                f"QFrame {{ background-color: {BG_INPUT}; "
                f"border: 2px solid {ACCENT_BLUE}; border-radius: 8px; }}"
            )
        else:
            self.setStyleSheet(
                f"QFrame {{ background-color: {BG_CARD}; "
                f"border: 1px solid {BORDER_COLOR}; border-radius: 8px; }}"
                f"QFrame:hover {{ background-color: {BG_INPUT}; "
                f"border: 1px solid {ACCENT_BLUE}88; }}"
            )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_id.emit(self._company_id)
        super().mousePressEvent(event)


class CompanyGridSelector(QWidget):
    """
    Scrollable icon-grid replacement for the CompanySelector QComboBox.
    Displays one tile per company (logo + name). Clicking a tile selects it.

    Drop-in API:
      populate(companies, api_client)   — rebuild tiles
      company_changed(int)              — signal emitted on selection change
      selected_company_id() -> int|None — current selection
    """

    company_changed = pyqtSignal(int)
    _COLS = 8

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._companies: list[dict] = []
        self._selected_id: Optional[int] = None
        self._tiles: dict[int, _CompanyTile] = {}
        self._populating = False

        self._inner = QWidget()
        self._inner.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(self._inner)
        self._grid.setContentsMargins(4, 4, 4, 4)
        self._grid.setSpacing(4)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._inner)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setFixedHeight(_CompanyTile.H + 22)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ border: 1px solid {BORDER_COLOR}; border-radius: 8px; "
            f"background-color: {BG_DARK}; }}"
            f"QScrollBar:vertical {{ background: {BG_DARK}; width: 6px; border: none; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER_COLOR}; border-radius: 3px; }}"
        )

        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.addWidget(self._scroll)

    def populate(self, companies: list[dict], api_client) -> None:
        self._populating = True
        for tile in self._tiles.values():
            tile.deleteLater()
        self._tiles.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._companies = companies
        self._selected_id = None

        for idx, company in enumerate(companies):
            cid = company["id"]
            name = company.get("name", "")
            pixmap = get_logo_pixmap(api_client, cid, name, size=38)
            tile = _CompanyTile(cid, name, pixmap)
            tile.clicked_id.connect(self._on_tile_clicked)
            row, col = divmod(idx, self._COLS)
            self._grid.addWidget(tile, row, col)
            self._tiles[cid] = tile

        # Resize scroll area to show 1 or 2 rows without wasted space
        n_rows = max(1, -(-len(companies) // self._COLS))  # ceil division
        visible_rows = min(n_rows, 2)
        self._scroll.setFixedHeight(visible_rows * (_CompanyTile.H + self._grid.spacing()) + 12)

        self._populating = False
        if companies:
            self._apply_selection(companies[0]["id"])
            self._selected_id = companies[0]["id"]

    def _on_tile_clicked(self, company_id: int) -> None:
        if self._populating or self.signalsBlocked():
            return
        self._apply_selection(company_id)
        self._selected_id = company_id
        self.company_changed.emit(company_id)

    def _apply_selection(self, company_id: int) -> None:
        for cid, tile in self._tiles.items():
            tile.set_selected(cid == company_id)

    def selected_company_id(self) -> Optional[int]:
        return self._selected_id


from views.transaction.history_view import HistoryView
from views.transaction.profile_view import ProfileView


# ════════════════════════════════════════════
# Main TransactionView — QStackedWidget host
# ════════════════════════════════════════════
class TransactionView(QMainWindow):
    PAGE_KEYS = ("cash_in", "cash_out", "transfer", "exchange", "history", "profile")

    # Stack indices — transaction types at 0-3, utility pages at 4-5
    PAGE_INDEX = {
        "cash_in": 0,
        "cash_out": 1,
        "transfer": 2,
        "exchange": 3,
        "history": 4,
        "profile": 5,
    }
    PAGE_LABELS = {
        "cash_in": "Cash In",
        "cash_out": "Cash Out",
        "transfer": "Transfer",
        "exchange": "Exchange",
        "history": "History",
        "profile": "Profile",
    }
    # Dashboard card page numbers → page keys
    _DASHBOARD_PAGE_MAP = {2: "history", 3: "profile"}

    def __init__(
        self,
        api_client: ApiClient,
        transaction_type: str | None = None,
    ) -> None:
        super().__init__()
        self._api = api_client
        self._repository = TransactionUiRepository(api_client)
        self._history_repository = HistoryRepository(self._repository)
        self._profile_repository = ProfileRepository(self._repository)
        initial = normalize_transaction_type(transaction_type)
        # Fallback to "cash_in" for unknown keys during normalization
        self._current_page_key: str = initial if initial in self.PAGE_INDEX else "cash_in"
        self._init_ui()
        on_change(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        fullname = self._repository.current_user.get("full_name", "")
        self.setWindowTitle(f"{t('app_title')} - {fullname}")
        self._update_breadcrumb()

    def _init_ui(self) -> None:
        fullname = self._repository.current_user.get("full_name", "")
        self.setWindowTitle(f"{t('app_title')} - {fullname}")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        central.setStyleSheet(f"background-color: {BG_DARK};")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_breadcrumb())

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(central)

        from views.transaction.cash_in_view import CashInView
        from views.transaction.cash_out_view import CashOutView
        from views.transaction.transfer_view import TransferView
        from views.transaction.exchange_view import ExchangeView

        self._pages: dict[str, QWidget] = {
            "cash_in": CashInView(self._api, self._navigate, self._repository),
            "cash_out": CashOutView(self._api, self._navigate, self._repository),
            "transfer": TransferView(self._api, self._navigate, self._repository),
            "exchange": ExchangeView(self._api, self._navigate, self._repository),
            "history": HistoryView(self._history_repository, self._navigate),
            "profile": ProfileView(self._profile_repository, self._navigate),
        }
        for key in self.PAGE_KEYS:
            self._stack.addWidget(self._pages[key])

        self.switch_to_page(self._current_page_key)

    # ── Breadcrumb ──────────────────────────────────────────────────────────

    def _build_breadcrumb(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(54)
        bar.setStyleSheet(
            f"QFrame {{ background-color: {BG_DARK}; border-bottom: 1px solid {BORDER_COLOR}; }}"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(24, 10, 24, 10)
        row.setSpacing(8)

        self._dashboard_link = QPushButton("Dashboard")
        self._dashboard_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dashboard_link.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {ACCENT_BLUE}; border: none; "
            f"font-size: 14px; font-weight: bold; padding: 0; }}"
            f"QPushButton:hover {{ color: {TEXT_PRIMARY}; }}"
        )
        self._dashboard_link.clicked.connect(self._go_dashboard)
        row.addWidget(self._dashboard_link)

        self._breadcrumb_tail = QLabel("")
        self._breadcrumb_tail.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 14px; font-weight: bold; background: transparent;"
        )
        row.addWidget(self._breadcrumb_tail)
        row.addStretch()

        self._back_btn = QPushButton("Back")
        self._back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._back_btn.setFixedHeight(34)
        self._back_btn.setStyleSheet(
            f"QPushButton {{ background-color: {BG_CARD}; color: {ACCENT_BLUE}; "
            f"border: 1px solid {ACCENT_BLUE}; border-radius: 6px; "
            f"padding: 6px 16px; font-size: 13px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; }}"
        )
        self._back_btn.clicked.connect(self._go_dashboard)
        row.addWidget(self._back_btn, alignment=Qt.AlignmentFlag.AlignRight)

        self._update_breadcrumb()
        return bar

    def _update_breadcrumb(self) -> None:
        if hasattr(self, "_breadcrumb_tail"):
            label = self._page_label(self._current_page_key)
            self._breadcrumb_tail.setText(f"/ {label}" if label else "")

    # ── Navigation ──────────────────────────────────────────────────────────

    def switch_to_page(self, key: str) -> None:
        """Switch the stack to any registered page key and reload its data."""
        key = self._resolve_page_key(key)
        self._current_page_key = key
        index = self.PAGE_INDEX[key]
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
        self._update_breadcrumb()
        page = self._pages[key]
        if hasattr(page, "load_data"):
            try:
                page.load_data()
            except Exception:
                return

    def switch_to_transaction(self, transaction_type: str) -> None:
        """Convenience wrapper — normalises a transaction-type string and delegates."""
        self.switch_to_page(normalize_transaction_type(transaction_type))

    def _resolve_page_key(self, key: str | None) -> str:
        resolved = normalize_transaction_type(key)
        if resolved in self.PAGE_INDEX and hasattr(self, "_pages") and resolved in self._pages:
            return resolved
        return "cash_in"

    def _page_label(self, key: str | None) -> str:
        return self.PAGE_LABELS.get(self._resolve_page_key(key), self.PAGE_LABELS["cash_in"])

    def _navigate(self, page: int, transaction_type: str | None = None) -> None:
        """Unified navigation callback used by all child pages."""
        if page == 0:
            # Explicit "go home" request from an internal back button
            self._go_dashboard()
            return
        if transaction_type:
            key = normalize_transaction_type(transaction_type)
            if key in self.PAGE_INDEX:
                self.switch_to_page(key)
            return
        # Map dashboard card page numbers to page keys
        key = self._DASHBOARD_PAGE_MAP.get(page)
        if key:
            self.switch_to_page(key)

    def _go_dashboard(self) -> None:
        from views.dashboard_view import DashboardView

        self._dashboard = DashboardView(self._api)
        self._dashboard.show()
        self.close()

    def closeEvent(self, event) -> None:
        super().closeEvent(event)
