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
from services.api_client import ApiClient
from views.widgets.company_selector import ServiceTypeSelector, AccountSelector
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
    "deposit": ACCENT_GREEN,
    "withdraw": ACCENT_RED,
    "transfer": ACCENT_BLUE,
    "exchange": ACCENT_YELLOW,
}

def _get_actions():
    return [
        ("deposit", t("action_deposit"), ACCENT_GREEN),
        ("withdraw", t("action_withdraw"), ACCENT_RED),
        ("transfer", t("action_transfer"), ACCENT_BLUE),
        ("exchange", t("action_exchange"), ACCENT_YELLOW),
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
    _COLS = 4

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
        self._grid.setSpacing(6)
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


# ════════════════════════════════════════════
# Page 0: Home (Landing)
# ════════════════════════════════════════════
class HomePage(QWidget):
    def __init__(self, api: ApiClient, navigate) -> None:
        super().__init__()
        self._api = api
        self._navigate = navigate
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Top bar
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

        # Cards row
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)

        cards = [
            (t("new_transaction"), t("new_transaction_desc"), ACCENT_GREEN, 1),
            (t("txn_history"), t("txn_history_desc"), ACCENT_BLUE, 2),
            (t("my_profile"), t("my_profile_desc"), ACCENT_MAUVE, 3),
        ]
        for title_text, desc, color, page_idx in cards:
            cards_layout.addWidget(self._card(title_text, desc, color, page_idx))

        layout.addLayout(cards_layout)
        layout.addStretch()
        layout.addStretch()

    def _card(self, title: str, desc: str, color: str, page: int) -> QFrame:
        card = QFrame()
        card.setFixedHeight(160)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 12px; "
            f"border: 2px solid {color}; }}"
            f"QFrame:hover {{ background-color: {BG_INPUT}; }}"
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        t = QLabel(title)
        t.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {color}; border: none;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(t)

        d = QLabel(desc)
        d.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; border: none;")
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(d)

        card.mousePressEvent = lambda e, p=page: self._navigate(p)
        return card

    def update_time(self) -> None:
        try:
            self._time_label.setText(datetime.now(MMT).strftime("%d-%m-%Y  %I:%M:%S %p"))
        except Exception:
            pass


# ════════════════════════════════════════════
# Page 1: Transaction Form
# ════════════════════════════════════════════
class TransactionFormPage(QWidget):
    def __init__(self, api: ApiClient, navigate) -> None:
        super().__init__()
        self._api = api
        self._navigate = navigate
        self._selected_action: str = "deposit"
        self._screenshot_path: Optional[str] = None
        self._accounts_cache: list[dict] = []
        self._to_accounts_cache: list[dict] = []
        self._fee_accounts_cache: list[dict] = []
        self._all_companies_cache: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()
        layout.addWidget(back_button(lambda: self._navigate(0)))
        layout.addWidget(section_label(t("transaction")))
        layout.addWidget(self._build_action_buttons())
        layout.addWidget(self._build_form())
        layout.addWidget(section_label(t("todays_transactions")))
        layout.addWidget(self._build_txn_table())
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_data(self) -> None:
        self._load_companies()
        self._load_my_transactions()
        user = self._api.user or {}
        if user.get("role") == "employee":
            self._set_float_state(self._check_float_status())

    def _check_float_status(self) -> bool:
        try:
            floats = self._api.get_floats()
            return any(f.get("status") == "ACTIVE" for f in floats)
        except Exception:
            return True

    def _set_float_state(self, has_float: bool) -> None:
        self._float_banner.setText("" if has_float else t("warn_no_float_banner"))
        self._float_banner.setVisible(not has_float)
        for key in ("withdraw", "transfer", "exchange"):
            btn = self._action_buttons.get(key)
            if btn:
                btn.setEnabled(has_float)
        if not has_float and self._selected_action in ("withdraw", "transfer", "exchange"):
            self._on_action_select("deposit")

    # ── Action buttons ──
    def _build_action_buttons(self) -> QFrame:
        frame = QFrame()
        lo = QHBoxLayout(frame)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(10)
        self._action_buttons: dict[str, QPushButton] = {}
        for key, label, color in _get_actions():
            btn = QPushButton(label)
            btn.setFixedHeight(44)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._on_action_select(k))
            self._action_buttons[key] = btn
            lo.addWidget(btn)
        self._update_action_styles()
        return frame

    def _update_action_styles(self) -> None:
        for key, btn in self._action_buttons.items():
            color = dict((k, c) for k, _, c in _get_actions()).get(key, ACCENT_BLUE)
            disabled = not btn.isEnabled()
            if disabled:
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; color: {TEXT_MUTED}; "
                    f"border: 1px solid {TEXT_MUTED}; border-radius: 8px; font-size: 13px; }}")
            elif key == self._selected_action:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {color}; color: {BG_DARK}; border: none; border-radius: 8px; font-size: 13px; font-weight: bold; }}")
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: transparent; color: {color}; border: 1px solid {color}; border-radius: 8px; font-size: 13px; }}"
                    f"QPushButton:hover {{ background-color: {BG_CARD}; }}")

    def _on_action_select(self, key: str) -> None:
        try:
            self._selected_action = key
            self._update_action_styles()
            self._update_form_visibility()
            self._repopulate_company_selectors()
            self._clear_form()
        except Exception:
            pass

    # ── Form ──
    def _build_form(self) -> QFrame:
        self._form_frame = QFrame()
        self._form_frame.setObjectName("txnForm")
        self._form_frame.setStyleSheet(
            f"QFrame#txnForm {{ background-color: {BG_CARD}; border-radius: 10px; border: 1px solid {BORDER_COLOR}; }}")

        lo = QVBoxLayout(self._form_frame)
        lo.setContentsMargins(20, 20, 20, 20)
        lo.setSpacing(12)

        lo.addWidget(field_label(t("field_company"), required=True))
        self._company_selector = CompanyGridSelector()
        self._company_selector.company_changed.connect(self._on_company_changed)
        lo.addWidget(self._company_selector)

        self._service_type_label = field_label(t("field_service_type"), required=True)
        lo.addWidget(self._service_type_label)
        self._service_type_selector = ServiceTypeSelector()
        self._service_type_selector.service_type_changed.connect(self._on_service_type_changed)
        lo.addWidget(self._service_type_selector)

        lo.addWidget(field_label(t("field_account"), required=True))
        self._account_selector = AccountSelector()
        self._account_selector.currentIndexChanged.connect(self._on_account_changed)
        lo.addWidget(self._account_selector)

        self._balance_hint = QLabel("")
        self._balance_hint.setVisible(False)
        lo.addWidget(self._balance_hint)

        # Transfer: to-side cascade
        self._to_company_label = field_label(t("field_to_company"), required=True)
        lo.addWidget(self._to_company_label)
        self._to_company_selector = CompanyGridSelector()
        self._to_company_selector.company_changed.connect(self._on_to_company_changed)
        lo.addWidget(self._to_company_selector)

        self._to_service_type_label = field_label(t("field_to_service_type"), required=True)
        lo.addWidget(self._to_service_type_label)
        self._to_service_type_selector = ServiceTypeSelector()
        self._to_service_type_selector.service_type_changed.connect(self._on_to_service_type_changed)
        lo.addWidget(self._to_service_type_selector)

        self._to_account_label = field_label(t("field_to_account"), required=True)
        lo.addWidget(self._to_account_label)
        self._to_account_selector = AccountSelector()
        lo.addWidget(self._to_account_selector)

        self._customer_label = field_label(t("field_customer"), required=True)
        lo.addWidget(self._customer_label)
        cust_row = QHBoxLayout()
        self._customer_name = QLineEdit()
        self._customer_name.setPlaceholderText(t("customer_name_ph"))
        self._customer_name.returnPressed.connect(lambda: self._customer_phone.setFocus())
        cust_row.addWidget(self._customer_name)
        self._customer_phone = QLineEdit()
        self._customer_phone.setPlaceholderText(t("customer_phone_ph"))
        self._customer_phone.returnPressed.connect(lambda: self._amount_input.setFocus())
        cust_row.addWidget(self._customer_phone)
        lo.addLayout(cust_row)

        self._currency_label = field_label(t("field_currency"), required=True)
        lo.addWidget(self._currency_label)
        self._currency_combo = QComboBox()
        self._currency_combo.addItems(["MMK", "THB"])
        lo.addWidget(self._currency_combo)

        lo.addWidget(field_label(t("field_amount"), required=True))
        self._amount_input = QLineEdit()
        self._amount_input.setPlaceholderText("0")
        self._amount_input.textChanged.connect(self._on_amount_changed)
        self._amount_input.returnPressed.connect(lambda: self._fee_account_combo.setFocus())
        lo.addWidget(self._amount_input)

        self._commission_label = field_label(t("field_commission"))
        lo.addWidget(self._commission_label)
        self._commission_display = QLineEdit()
        self._commission_display.setReadOnly(True)
        self._commission_display.setText("0")
        self._commission_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {ACCENT_MAUVE}; border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 8px 12px; font-size: 13px; }}")
        lo.addWidget(self._commission_display)

        lo.addWidget(field_label(t("field_customer_fee")))
        self._fee_display = QLineEdit()
        self._fee_display.setReadOnly(True)
        self._fee_display.setText("0")
        self._fee_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {ACCENT_TEAL}; border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 8px 12px; font-size: 13px; }}")
        lo.addWidget(self._fee_display)

        lo.addWidget(field_label(t("field_additional_fee")))
        self._additional_fee_display = QLineEdit()
        self._additional_fee_display.setReadOnly(True)
        self._additional_fee_display.setText("0")
        self._additional_fee_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {ACCENT_YELLOW}; border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 8px 12px; font-size: 13px; }}")
        lo.addWidget(self._additional_fee_display)

        lo.addWidget(field_label(t("field_total_fee")))
        self._total_charge_display = QLineEdit()
        self._total_charge_display.setReadOnly(True)
        self._total_charge_display.setText("0")
        self._total_charge_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {TEXT_PRIMARY}; border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 8px 12px; font-size: 13px; font-weight: bold; }}")
        lo.addWidget(self._total_charge_display)

        self._fee_hint = QLabel("")
        self._fee_hint.setStyleSheet(f"color: {ACCENT_TEAL}; font-size: 11px; font-style: italic; padding-left: 2px;")
        self._fee_hint.setVisible(False)
        lo.addWidget(self._fee_hint)

        lo.addWidget(field_label(t("field_fee_account")))
        self._fee_account_combo = QComboBox()
        self._fee_account_combo.addItem(t("select_placeholder"))
        lo.addWidget(self._fee_account_combo)

        lo.addWidget(field_label(t("field_balance_change")))
        self._balance_change_display = QLineEdit()
        self._balance_change_display.setReadOnly(True)
        self._balance_change_display.setText("0")
        self._balance_change_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {ACCENT_GREEN}; border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 8px 12px; font-size: 13px; }}")
        lo.addWidget(self._balance_change_display)

        lo.addWidget(field_label(t("field_note")))
        self._note_input = TabTextEdit(on_enter=lambda: self._screenshot_btn.setFocus())
        self._note_input.setFixedHeight(60)
        self._note_input.setPlaceholderText(t("note_placeholder"))
        lo.addWidget(self._note_input)

        ss_row = QHBoxLayout()
        self._screenshot_btn = QPushButton(t("attach_screenshot"))
        self._screenshot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._screenshot_btn.setStyleSheet(
            f"QPushButton {{ background-color: {BG_DARK}; color: {ACCENT_BLUE}; border: 1px solid {ACCENT_BLUE}; border-radius: 6px; padding: 8px 16px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; }}")
        self._screenshot_btn.clicked.connect(self._on_select_screenshot)
        ss_row.addWidget(self._screenshot_btn)
        self._screenshot_label = QLabel(t("no_file_selected"))
        self._screenshot_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        ss_row.addWidget(self._screenshot_label, 1)
        lo.addLayout(ss_row)

        self._float_banner = QLabel("")
        self._float_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._float_banner.setStyleSheet(
            f"background-color: #45475a; color: {ACCENT_YELLOW}; "
            f"border-radius: 6px; padding: 8px 12px; font-size: 12px; font-weight: bold;"
        )
        self._float_banner.setVisible(False)
        lo.addWidget(self._float_banner)

        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        lo.addWidget(self._status_label)

        self._save_btn = accent_btn(t("save_transaction"))
        self._save_btn.setFixedHeight(44)
        self._save_btn.clicked.connect(self._on_save)
        lo.addWidget(self._save_btn)

        self._update_form_visibility()
        return self._form_frame

    def _update_form_visibility(self) -> None:
        is_transfer = self._selected_action == "transfer"
        is_exchange = self._selected_action == "exchange"
        has_customer = self._selected_action in ("deposit", "withdraw")
        need_st = self._selected_action in ("deposit", "withdraw")
        # Service type selector only shown for deposit/withdraw (Pay types)
        self._service_type_label.setVisible(need_st)
        self._service_type_selector.setVisible(need_st)
        # To-side cascade for transfer only; service type is always auto-selected
        self._to_company_label.setVisible(is_transfer)
        self._to_company_selector.setVisible(is_transfer)
        self._to_service_type_label.setVisible(False)
        self._to_service_type_selector.setVisible(False)
        self._to_account_label.setVisible(is_transfer)
        self._to_account_selector.setVisible(is_transfer)
        self._customer_label.setVisible(has_customer)
        self._customer_name.setVisible(has_customer)
        self._customer_phone.setVisible(has_customer)
        self._currency_label.setVisible(is_exchange)
        self._currency_combo.setVisible(is_exchange)

    # ── Calculations ──
    def _get_selected_account(self) -> Optional[dict]:
        return self._account_selector.selected_account()

    def _on_amount_changed(self) -> None:
        try:
            self._recalculate()
            self._update_balance_hint()
        except Exception:
            pass

    def _on_account_changed(self, index: int) -> None:
        try:
            self._recalculate()
            self._update_balance_hint()
        except Exception:
            pass

    def _recalculate(self) -> None:
        account = self._get_selected_account()
        amount = self._parse_amount()

        if account is None or amount <= 0:
            self._commission_display.setText("0")
            self._balance_change_display.setText("0")
            self._fee_display.setText("0")
            self._additional_fee_display.setText("0")
            self._total_charge_display.setText("0")
            self._fee_hint.setVisible(False)
            return

        tier = self._lookup_tier(account, amount)
        is_withdraw = self._selected_action == "withdraw"

        if tier is None:
            self._commission_display.setText("0")
            self._fee_display.setText("0")
            self._additional_fee_display.setText("0")
            self._total_charge_display.setText("0")
            self._balance_change_display.setText(f"{amount:,.0f}")
            self._fee_hint.setText(t("no_tier"))
            self._fee_hint.setStyleSheet(f"color: {ACCENT_YELLOW}; font-size: 11px; font-style: italic; padding-left: 2px;")
            self._fee_hint.setVisible(True)
            return

        fee_type = (tier.get("fee_amount_type") or "FIXED").upper()
        comm_type_val = (tier.get("comm_type") or "FIXED").upper()
        add_type = (tier.get("additional_fee_type") or "FIXED").upper()

        if is_withdraw:
            fee_raw = float(tier.get("fee_amount_withdraw") or 0)
            comm_raw = float(tier.get("comm_withdraw") or 0)
            add_raw = float(tier.get("additional_fee_withdraw_amount") or 0)
        else:
            fee_raw = float(tier.get("fee_amount_deposit") or 0)
            comm_raw = float(tier.get("comm_deposit") or 0)
            add_raw = float(tier.get("additional_fee_deposit_amount") or 0)

        fee_amount = round(amount * fee_raw, 2) if fee_type == "PERCENTAGE" else fee_raw
        commission = round(amount * comm_raw, 2) if comm_type_val == "PERCENTAGE" else comm_raw
        additional = round(amount * add_raw, 2) if add_type == "PERCENTAGE" else add_raw

        # deposit/exchange: balance increases; withdraw/transfer: from-account decreases
        balance_change = -amount if self._selected_action in ("withdraw", "transfer") else amount
        total_fee = fee_amount + additional
        customer_total = amount + total_fee

        self._commission_display.setText(f"{commission:,.0f}")
        self._fee_display.setText(f"{fee_amount:,.0f}")
        self._additional_fee_display.setText(f"{additional:,.0f}")
        self._total_charge_display.setText(f"{total_fee:,.0f}")
        self._balance_change_display.setText(f"{balance_change:,.0f}")

        if is_withdraw:
            self._fee_hint.setText(
                f"Withdrawal: {amount:,.0f}  |  Fee: {fee_amount:,.0f} + {additional:,.0f} = {total_fee:,.0f}  |  "
                f"Customer pays (fee): {total_fee:,.0f}  |  Agent commission: {commission:,.0f}")
        else:
            self._fee_hint.setText(
                f"Customer pays: {amount:,.0f} + {total_fee:,.0f} (fee) = {customer_total:,.0f}  |  "
                f"To fee account: {total_fee:,.0f}  |  Agent commission: {commission:,.0f}")
        self._fee_hint.setStyleSheet(f"color: {ACCENT_TEAL}; font-size: 11px; font-style: italic; padding-left: 2px;")
        self._fee_hint.setVisible(True)

    def _lookup_tier(self, account: dict, amount: float) -> Optional[dict]:
        service_type_id = account.get("service_type_id")
        if service_type_id is None:
            return None
        try:
            tier = self._api.lookup_tier(service_type_id, amount)
            if (tier.get("fee_amount_deposit", 0) == 0 and tier.get("fee_amount_withdraw", 0) == 0
                    and tier.get("comm_deposit", 0) == 0 and tier.get("comm_withdraw", 0) == 0):
                return None
            return tier
        except Exception:
            return None

    def _calc_commission(self, account: dict, amount: float) -> float:
        tier = self._lookup_tier(account, amount)
        if tier is None:
            return 0.0
        comm_type_val = (tier.get("comm_type") or "FIXED").upper()
        if self._selected_action == "withdraw":
            raw = float(tier.get("comm_withdraw") or 0)
        else:
            raw = float(tier.get("comm_deposit") or 0)
        if comm_type_val == "PERCENTAGE":
            return round(amount * raw, 2)
        return raw

    def _calc_balance_change(self, amount: float) -> float:
        # commission is agent profit, not deducted from account balance
        return round(amount, 2)

    def _parse_amount(self) -> float:
        try:
            return float(self._amount_input.text().replace(",", ""))
        except ValueError:
            return 0.0

    def _parse_additional_fee(self) -> float:
        try:
            return float(self._additional_fee_display.text().replace(",", ""))
        except ValueError:
            return 0.0

    def _parse_total_fee(self) -> float:
        try:
            base = float(self._fee_display.text().replace(",", ""))
        except ValueError:
            base = 0.0
        return base + self._parse_additional_fee()

    def _get_fee_account_id(self) -> Optional[int]:
        idx = self._fee_account_combo.currentIndex()
        if idx <= 0:
            return None
        acc_idx = idx - 1
        if acc_idx < len(self._fee_accounts_cache):
            acc_id = self._fee_accounts_cache[acc_idx].get("id")
            return acc_id if acc_id != 0 else None
        return None

    def _get_fresh_balance(self, account_id: int) -> float:
        try:
            return float(self._api.get_account(account_id).get("balance", 0))
        except Exception:
            return 0.0

    def _calc_projected(self, balance: float, amount: float) -> float:
        if amount <= 0:
            return balance
        if self._selected_action in ("withdraw", "transfer"):
            return balance - amount
        if self._selected_action == "deposit":
            return balance + amount
        return balance  # exchange: balance increases, no check needed

    def _update_balance_hint(self) -> None:
        account = self._get_selected_account()
        if account is None:
            self._balance_hint.setVisible(False)
            return
        balance = self._get_fresh_balance(account["id"])
        amount = self._parse_amount()
        if amount <= 0:
            c = ACCENT_GREEN if balance >= 0 else ACCENT_RED
            self._balance_hint.setText(t("current_balance", balance=f"{balance:,.0f}"))
            self._balance_hint.setStyleSheet(f"color: {c}; font-size: 12px; font-style: italic; padding-left: 2px;")
        else:
            projected = self._calc_projected(balance, amount)
            c = ACCENT_GREEN if projected >= 0 else ACCENT_RED
            self._balance_hint.setText(t("balance_after", balance=f"{balance:,.0f}", projected=f"{projected:,.0f}"))
            self._balance_hint.setStyleSheet(f"color: {c}; font-size: 12px; font-style: italic; padding-left: 2px;")
        self._balance_hint.setVisible(True)

    # ── Data loading ──
    def _get_companies_for_action(self) -> list[dict]:
        if self._selected_action in ("deposit", "withdraw"):
            return [c for c in self._all_companies_cache if c.get("category") in ("Pay", "Both")]
        return [c for c in self._all_companies_cache if c.get("category") in ("Bank", "Both")]

    def _repopulate_company_selectors(self) -> None:
        if not self._all_companies_cache:
            return
        filtered = self._get_companies_for_action()
        self._company_selector.blockSignals(True)
        self._company_selector.populate(filtered, self._api)
        self._company_selector.blockSignals(False)
        self._to_company_selector.blockSignals(True)
        self._to_company_selector.populate(filtered, self._api)
        self._to_company_selector.blockSignals(False)
        cid = self._company_selector.selected_company_id()
        if cid is not None:
            self._on_company_changed(cid)
        cid_to = self._to_company_selector.selected_company_id()
        if cid_to is not None:
            self._on_to_company_changed(cid_to)

    def _load_companies(self) -> None:
        try:
            self._all_companies_cache = self._api.get_companies()
            self._repopulate_company_selectors()
        except Exception:
            pass
        self._load_fee_accounts()

    def _load_fee_accounts(self) -> None:
        try:
            all_accounts = self._api.get_accounts()
            fee_accs = [
                a for a in all_accounts
                if int(a.get("is_fee_account") or 0) == 1
            ]
            self._fee_accounts_cache = [FEE_CASH_ITEM] + fee_accs
        except Exception as e:
            print(f"[fee_accounts] load error: {e}")
            self._fee_accounts_cache = [FEE_CASH_ITEM]

        self._fee_account_combo.clear()
        self._fee_account_combo.addItem(t("select_placeholder"))
        # index 0 = placeholder, index 1 = Cash, index 2+ = fee accounts (is_fee_account=1)
        for a in self._fee_accounts_cache:
            label = (
                f"{a.get('account_name', '')} | {a.get('phone_number', '')}"
                if a.get("phone_number")
                else a.get("account_name", "")
            )
            self._fee_account_combo.addItem(label)

    def _on_company_changed(self, company_id: int) -> None:
        try:
            service_types = self._api.get_service_types(company_id)
            if self._selected_action in ("transfer", "exchange"):
                target = self._selected_action.capitalize()  # "Transfer" or "Exchange"
                st = next((s for s in service_types if s.get("name", "").lower() == target.lower()), None)
                if st:
                    self._on_service_type_changed(st["id"])
            else:
                self._service_type_selector.populate(service_types)
                st_id = self._service_type_selector.selected_service_type_id()
                if st_id is not None:
                    self._on_service_type_changed(st_id)
        except Exception:
            pass

    def _on_service_type_changed(self, service_type_id: int) -> None:
        try:
            accounts = self._api.get_accounts(service_type_id=service_type_id)
            self._account_selector.populate(accounts)
            self._accounts_cache = accounts
            self._on_account_changed(0)
        except Exception:
            pass

    def _on_to_company_changed(self, company_id: int) -> None:
        try:
            service_types = self._api.get_service_types(company_id)
            st = next((s for s in service_types if s.get("name", "").lower() == "transfer"), None)
            if st:
                self._on_to_service_type_changed(st["id"])
        except Exception:
            pass

    def _on_to_service_type_changed(self, service_type_id: int) -> None:
        try:
            accounts = self._api.get_accounts(service_type_id=service_type_id)
            self._to_account_selector.populate(accounts)
            self._to_accounts_cache = accounts
        except Exception:
            pass

    def _load_my_transactions(self) -> None:
        try:
            self._populate_txn_table(self._api.get_recent_transactions(50))
        except Exception:
            pass

    # ── Screenshot ──
    def _on_select_screenshot(self) -> None:
        try:
            path, _ = QFileDialog.getOpenFileName(self, t("select_screenshot"), "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)")
            if path:
                self._screenshot_path = path
                self._screenshot_label.setText(path.rsplit("/", 1)[-1] if "/" in path else path.rsplit("\\", 1)[-1])
                self._screenshot_label.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
        except Exception:
            pass

    # ── Save ──
    def _on_save(self) -> None:
        try:
            self._handle_save()
        except Exception as e:
            self._show_status(f"Error: {e}", error=True)

    def _handle_save(self) -> None:
        error = self._validate()
        if error:
            self._show_status(error, error=True)
            return
        action = self._selected_action
        amount = self._parse_amount()
        account = self._get_selected_account()
        note = self._note_input.toPlainText().strip() or None
        fee = self._parse_total_fee()
        additional = self._parse_additional_fee()
        fee_acc = self._get_fee_account_id()

        if action == "deposit":
            self._api.create_deposit(account_id=account["id"], amount=amount,
                customer_name=self._customer_name.text().strip(), customer_phone=self._customer_phone.text().strip(),
                screenshot_path=self._screenshot_path, customer_fee=fee, additional_fee_amount=additional, fee_account_id=fee_acc, note=note)
        elif action == "withdraw":
            self._api.create_withdraw(account_id=account["id"], amount=amount,
                customer_name=self._customer_name.text().strip(), customer_phone=self._customer_phone.text().strip(),
                screenshot_path=self._screenshot_path, customer_fee=fee, additional_fee_amount=additional, fee_account_id=fee_acc, note=note)
        elif action == "transfer":
            to_acc_id = self._to_account_selector.selected_account_id()
            self._api.create_transfer(from_account_id=account["id"], to_account_id=to_acc_id,
                amount=amount, screenshot_path=self._screenshot_path, customer_fee=fee, additional_fee_amount=additional, fee_account_id=fee_acc, note=note)
        elif action == "exchange":
            self._api.create_exchange(account_id=account["id"], amount=amount,
                currency=self._currency_combo.currentText(), screenshot_path=self._screenshot_path,
                customer_fee=fee, additional_fee_amount=additional, fee_account_id=fee_acc, note=note)
        self._show_status(t("txn_saved"), error=False)
        self._clear_form()
        self._load_my_transactions()

    def _validate(self) -> Optional[str]:
        user = self._api.user or {}
        if user.get("role") == "employee" and self._selected_action in ("withdraw", "transfer", "exchange"):
            if not self._check_float_status():
                return t("err_no_float")
        if self._account_selector.selected_account_id() is None:
            return t("err_select_account")
        if self._parse_amount() <= 0:
            return t("err_enter_amount")
        if self._selected_action in ("deposit", "withdraw"):
            if not self._customer_name.text().strip():
                return t("err_customer_name")
            if not self._customer_phone.text().strip():
                return t("err_customer_phone")
        if self._selected_action == "transfer":
            to_acc_id = self._to_account_selector.selected_account_id()
            if to_acc_id is None:
                return t("err_select_to_account")
            if to_acc_id == self._account_selector.selected_account_id():
                return t("err_same_account")
        if self._selected_action in ("withdraw", "transfer"):
            account = self._get_selected_account()
            if account:
                balance = self._get_fresh_balance(account["id"])
                if self._calc_projected(balance, self._parse_amount()) < 0:
                    return t("err_insufficient", balance=f"{balance:,.0f}")
        return None

    def _clear_form(self) -> None:
        self._amount_input.clear()
        self._customer_name.clear()
        self._customer_phone.clear()
        self._fee_display.setText("0")
        self._additional_fee_display.setText("0")
        self._total_charge_display.setText("0")
        self._fee_hint.setVisible(False)
        self._fee_account_combo.setCurrentIndex(0)
        self._note_input.clear()
        self._commission_display.setText("0")
        self._balance_change_display.setText("0")
        self._balance_hint.setVisible(False)
        self._screenshot_path = None
        self._screenshot_label.setText(t("no_file_selected"))
        self._screenshot_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")

    def _show_status(self, msg: str, error: bool = False) -> None:
        self._status_label.setText(msg)
        self._status_label.setStyleSheet(f"color: {ERROR_COLOR if error else SUCCESS_COLOR}; font-size: 13px;")
        self._status_label.setVisible(True)

    # ── Table ──
    TXN_COL_WIDTHS = [180, 100, 0, 140, 0, 140, 140, 90, 90, 120, 90]
    TXN_STRETCH = {2, 4}

    def _build_txn_table(self) -> QTableWidget:
        self._txn_table = QTableWidget(0, len(_get_txn_headers()))
        self._txn_table.setHorizontalHeaderLabels(_get_txn_headers())
        self._txn_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._txn_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._txn_table.setAlternatingRowColors(True)
        self._txn_table.verticalHeader().setVisible(False)
        self._txn_table.setMinimumHeight(250)
        self._txn_table.setWordWrap(False)
        self._txn_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._txn_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        header = self._txn_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        for i, w in enumerate(self.TXN_COL_WIDTHS):
            if i in self.TXN_STRETCH:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self._txn_table.setColumnWidth(i, w)
        return self._txn_table

    def _populate_txn_table(self, txns: list[dict]) -> None:
        self._txn_table.setRowCount(len(txns))
        for row, txn in enumerate(txns):
            self._set_txn_row(row, txn)
            self._txn_table.setRowHeight(row, 30)

    def _set_txn_row(self, row: int, txn: dict) -> None:
        tt = txn.get("transaction_type", "")
        acc = self._find_account(txn.get("account_id"))
        fee_acc = self._find_account(txn.get("fee_account_id"))
        has_cust = tt in ("deposit", "withdraw")
        items = [
            format_datetime(txn.get("created_at", "")), tt,
            acc.get("account_name", "") if acc else str(txn.get("account_id", "")),
            acc.get("phone_number", "") if acc else "",
            txn.get("customer_name", "") or "—" if has_cust else "—",
            txn.get("customer_phone", "") or "—" if has_cust else "—",
            f"{float(txn.get('amount', 0)):,.0f}",
            f"{float(txn.get('commission_amount', 0)):,.0f}",
            f"{float(txn.get('customer_fee', 0)):,.0f}",
            fee_acc.get("account_name", "") if fee_acc else "—",
        ]
        left = {2, 3, 4, 5, 9}
        right = {6, 7, 8}
        additional = float(txn.get("additional_fee_amount", 0))
        base_fee = float(txn.get("customer_fee", 0)) - additional
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            if col in left:
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            elif col in right:
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col == 8:
                item.setToolTip(f"Base: {base_fee:,.0f} + Extra: {additional:,.0f}")
            else:
                item.setToolTip(text)
            if col == 1:
                item.setForeground(QColor(TYPE_COLORS.get(tt, TEXT_PRIMARY)))
            self._txn_table.setItem(row, col, item)
        path = txn.get("screenshot_path", "")
        if path:
            btn = QPushButton(t("view"))
            btn.setStyleSheet(f"QPushButton {{ background: {BG_DARK}; color: {ACCENT_BLUE}; border: none; border-radius: 4px; padding: 2px 6px; font-size: 11px; }}")
            btn.clicked.connect(lambda _, p=path: self._show_screenshot(p))
            self._txn_table.setCellWidget(row, 10, btn)
        else:
            self._txn_table.setItem(row, 10, QTableWidgetItem(""))

    def _find_account(self, account_id) -> Optional[dict]:
        if not account_id:
            return None
        for acc in self._accounts_cache:
            if acc.get("id") == account_id:
                return acc
        for acc in self._fee_accounts_cache:
            if acc.get("id") == account_id:
                return acc
        return None

    def _show_screenshot(self, path: str) -> None:
        try:
            pixmap = QPixmap(path)
            if pixmap.isNull():
                self._show_status(t("err_open_file", path=path), error=True)
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
        except Exception as e:
            self._show_status(t("err_screenshot", error=str(e)), error=True)


# ════════════════════════════════════════════
# Page 2: Transaction History
# ════════════════════════════════════════════
class HistoryPage(QWidget):
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
        layout.addWidget(back_button(lambda: self._navigate(0)))
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
        for i, w in enumerate(TransactionFormPage.TXN_COL_WIDTHS):
            if i in TransactionFormPage.TXN_STRETCH:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(i, w)
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
                and (t_type == "All" or tx.get("transaction_type") == t_type)
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


# ════════════════════════════════════════════
# Page 3: Profile
# ════════════════════════════════════════════
class ProfilePage(QWidget):
    def __init__(self, api: ApiClient, navigate) -> None:
        super().__init__()
        self._api = api
        self._navigate = navigate
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()
        layout.addWidget(back_button(lambda: self._navigate(0)))
        layout.addWidget(section_label(t("profile_title")))

        # Info card
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; border: 1px solid {BORDER_COLOR}; }}")
        clo = QVBoxLayout(card)
        clo.setContentsMargins(20, 20, 20, 20)
        clo.setSpacing(10)

        user = self._api.user or {}
        name_label = QLabel(user.get("full_name", ""))
        name_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        clo.addWidget(name_label)

        info_row = QHBoxLayout()
        un = QLabel(f"@{user.get('username', '')}")
        un.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        info_row.addWidget(un)
        role = user.get("role", "employee")
        badge = QLabel(role.upper())
        badge_color = ACCENT_TEAL if role == "owner" else ACCENT_BLUE
        badge.setStyleSheet(
            f"color: {badge_color}; background-color: {BG_DARK}; border-radius: 4px; padding: 2px 10px; font-size: 11px; font-weight: bold;")
        info_row.addWidget(badge)
        info_row.addStretch()
        clo.addLayout(info_row)
        layout.addWidget(card)

        # Change password
        layout.addSpacing(10)
        layout.addWidget(section_label(t("change_password")))

        pw_card = QFrame()
        pw_card.setStyleSheet(f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; border: 1px solid {BORDER_COLOR}; }}")
        plo = QVBoxLayout(pw_card)
        plo.setContentsMargins(20, 20, 20, 20)
        plo.setSpacing(12)

        plo.addWidget(field_label(t("current_password_ph"), required=True))
        self._old_pw = QLineEdit()
        self._old_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._old_pw.setPlaceholderText(t("current_password_ph"))
        plo.addWidget(self._old_pw)

        plo.addWidget(field_label(t("new_password_ph"), required=True))
        self._new_pw = QLineEdit()
        self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pw.setPlaceholderText(t("new_password_ph"))
        plo.addWidget(self._new_pw)

        plo.addWidget(field_label(t("confirm_password_ph"), required=True))
        self._confirm_pw = QLineEdit()
        self._confirm_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pw.setPlaceholderText(t("confirm_password_ph"))
        plo.addWidget(self._confirm_pw)

        self._pw_status = QLabel("")
        self._pw_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pw_status.setVisible(False)
        plo.addWidget(self._pw_status)

        save_btn = accent_btn(t("save_password"))
        save_btn.clicked.connect(self._on_save_password)
        plo.addWidget(save_btn)

        layout.addWidget(pw_card)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_data(self) -> None:
        pass

    def _on_save_password(self) -> None:
        try:
            old = self._old_pw.text()
            new = self._new_pw.text()
            confirm = self._confirm_pw.text()
            if not old or not new:
                self._show_pw_status(t("pw_required"), True)
                return
            if new != confirm:
                self._show_pw_status(t("pw_mismatch"), True)
                return
            self._api.change_password(old, new)
            self._show_pw_status(t("pw_success"), False)
            self._old_pw.clear()
            self._new_pw.clear()
            self._confirm_pw.clear()
        except Exception as e:
            self._show_pw_status(f"Error: {e}", True)

    def _show_pw_status(self, msg: str, error: bool) -> None:
        self._pw_status.setText(msg)
        self._pw_status.setStyleSheet(f"color: {ERROR_COLOR if error else SUCCESS_COLOR}; font-size: 12px;")
        self._pw_status.setVisible(True)


# ════════════════════════════════════════════
# Main TransactionView — QStackedWidget host
# ════════════════════════════════════════════
class TransactionView(QMainWindow):
    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self._api = api_client
        self._init_ui()
        self._start_clock()
        on_change(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self.setWindowTitle(f"{t('app_title')} — {fullname}")
        # Cascade to sub-pages: action buttons
        for key, label, _ in _get_actions():
            if key in self._form._action_buttons:
                self._form._action_buttons[key].setText(label)
        # Cascade to sub-pages: table headers
        headers = _get_txn_headers()
        self._form._txn_table.setHorizontalHeaderLabels(headers)
        self._history._table.setHorizontalHeaderLabels(headers)

    def _init_ui(self) -> None:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self.setWindowTitle(f"{t('app_title')} — {fullname}")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(STYLESHEET)

        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._home = HomePage(self._api, self._navigate)
        self._form = TransactionFormPage(self._api, self._navigate)
        self._history = HistoryPage(self._api, self._navigate)
        self._profile = ProfilePage(self._api, self._navigate)

        self._pages = [self._home, self._form, self._history, self._profile]
        for p in self._pages:
            self._stack.addWidget(p)

        self._stack.setCurrentIndex(0)

    def _navigate(self, page: int) -> None:
        try:
            if page == -1:
                self._on_logout()
                return
            self._stack.setCurrentIndex(page)
            p = self._pages[page]
            if hasattr(p, "load_data"):
                p.load_data()
        except Exception:
            pass

    def _start_clock(self) -> None:
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._home.update_time)
        self._clock.start(1000)
        self._home.update_time()

    def _on_logout(self) -> None:
        try:
            self._clock.stop()
            self._api.logout()
            from views.login_view import LoginView
            self._login = LoginView(self._api)
            self._login.show()
            self.close()
        except Exception:
            pass
