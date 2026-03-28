from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from services.api_client import ApiClient

# ── Colors (same as dashboard) ──
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

# ── Action definitions ──
ACTIONS = [
    ("deposit", "အသွင်း (Deposit)", ACCENT_GREEN),
    ("withdraw", "အထုတ် (Withdraw)", ACCENT_RED),
    ("transfer", "ဘဏ်ချင်းငွေလဲ (Transfer)", ACCENT_BLUE),
    ("exchange", "ကျပ်-ဘတ် (Exchange)", ACCENT_YELLOW),
]

INPUT_STYLE = (
    f"QLineEdit, QTextEdit, QComboBox {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; "
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
    QScrollBar:vertical {{
        background: {BG_DARK}; width: 8px; border: none;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_COLOR}; border-radius: 4px; min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QTableWidget {{
        background-color: {BG_CARD}; border: 1px solid {BORDER_COLOR};
        border-radius: 8px; gridline-color: {BORDER_COLOR}; font-size: 12px;
    }}
    QTableWidget::item {{ padding: 6px; }}
    QHeaderView::section {{
        background-color: {BG_DARK}; color: {TEXT_SECONDARY};
        border: none; padding: 8px; font-weight: bold; font-size: 12px;
    }}
    {INPUT_STYLE}
"""


class TransactionView(QMainWindow):

    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self._api = api_client
        self._selected_action: str = "deposit"
        self._screenshot_path: Optional[str] = None
        self._accounts_cache: list[dict] = []
        self._services_cache: list[dict] = []
        self._init_ui()
        self._load_services()
        self._load_my_transactions()

    # ── UI Setup ──

    def _init_ui(self) -> None:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self.setWindowTitle(f"ငွေလွှဲ — Employee: {fullname}")
        self.setMinimumSize(900, 700)
        self.setStyleSheet(STYLESHEET)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.setCentralWidget(scroll)

        container = QWidget()
        self._main_layout = QVBoxLayout(container)
        self._main_layout.setContentsMargins(24, 0, 24, 24)
        self._main_layout.setSpacing(16)

        self._main_layout.addWidget(self._build_top_bar())
        self._main_layout.addWidget(self._build_action_buttons())
        self._main_layout.addWidget(self._build_form())
        self._main_layout.addWidget(self._section_label("My Transactions"))
        self._main_layout.addWidget(self._build_txn_table())
        self._main_layout.addStretch()

        scroll.setWidget(container)

    # ── Top bar ──

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(60)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 10, 0, 10)

        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        title = QLabel(f"Employee — {fullname}")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        layout.addWidget(title)
        layout.addStretch()

        logout_btn = QPushButton("Logout")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT_RED}; color: {BG_DARK}; "
            f"border: none; border-radius: 6px; padding: 8px 20px; "
            f"font-size: 13px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: #eba0ac; }}"
        )
        logout_btn.clicked.connect(self._on_logout)
        layout.addWidget(logout_btn)

        return bar

    # ── Action buttons ──

    def _build_action_buttons(self) -> QFrame:
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._action_buttons: dict[str, QPushButton] = {}
        for key, label, color in ACTIONS:
            btn = QPushButton(label)
            btn.setFixedHeight(44)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._on_action_select(k))
            self._action_buttons[key] = btn
            layout.addWidget(btn)

        self._update_action_styles()
        return frame

    def _update_action_styles(self) -> None:
        for key, btn in self._action_buttons.items():
            color = dict((k, c) for k, _, c in ACTIONS).get(key, ACCENT_BLUE)
            if key == self._selected_action:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: {color}; color: {BG_DARK}; "
                    f"border: none; border-radius: 8px; font-size: 13px; font-weight: bold; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: transparent; color: {color}; "
                    f"border: 1px solid {color}; border-radius: 8px; font-size: 13px; }}"
                    f"QPushButton:hover {{ background-color: {BG_CARD}; }}"
                )

    def _on_action_select(self, key: str) -> None:
        try:
            self._selected_action = key
            self._update_action_styles()
            self._update_form_visibility()
            self._clear_form()
        except Exception:
            pass

    # ── Transaction form ──

    def _build_form(self) -> QFrame:
        self._form_frame = QFrame()
        self._form_frame.setStyleSheet(
            f"QFrame#txnForm {{ background-color: {BG_CARD}; border-radius: 10px; "
            f"border: 1px solid {BORDER_COLOR}; }}"
        )
        self._form_frame.setObjectName("txnForm")

        layout = QVBoxLayout(self._form_frame)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Service dropdown
        layout.addWidget(self._field_label("Service"))
        self._service_combo = QComboBox()
        self._service_combo.currentIndexChanged.connect(self._on_service_changed)
        layout.addWidget(self._service_combo)

        # Account dropdown
        layout.addWidget(self._field_label("Account"))
        self._account_combo = QComboBox()
        self._account_combo.currentIndexChanged.connect(self._on_account_changed)
        layout.addWidget(self._account_combo)

        # To Account (transfer only)
        self._to_account_label = self._field_label("To Account")
        layout.addWidget(self._to_account_label)
        self._to_account_combo = QComboBox()
        layout.addWidget(self._to_account_combo)

        # Customer Name + Phone row
        self._customer_label = self._field_label("Customer Name / Phone")
        layout.addWidget(self._customer_label)
        cust_row = QHBoxLayout()
        self._customer_name = QLineEdit()
        self._customer_name.setPlaceholderText("Customer Name")
        cust_row.addWidget(self._customer_name)
        self._customer_phone = QLineEdit()
        self._customer_phone.setPlaceholderText("Phone Number")
        cust_row.addWidget(self._customer_phone)
        layout.addLayout(cust_row)

        # Currency (exchange only)
        self._currency_label = self._field_label("Currency")
        layout.addWidget(self._currency_label)
        self._currency_combo = QComboBox()
        self._currency_combo.addItems(["MMK", "THB"])
        layout.addWidget(self._currency_combo)

        # Amount
        layout.addWidget(self._field_label("Amount"))
        self._amount_input = QLineEdit()
        self._amount_input.setPlaceholderText("0")
        self._amount_input.textChanged.connect(self._on_amount_changed)
        layout.addWidget(self._amount_input)

        # Commission (read-only)
        layout.addWidget(self._field_label("Commission"))
        self._commission_display = QLineEdit()
        self._commission_display.setReadOnly(True)
        self._commission_display.setText("0")
        self._commission_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {ACCENT_MAUVE}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 8px 12px; font-size: 13px; }}"
        )
        layout.addWidget(self._commission_display)

        # Customer Fee
        layout.addWidget(self._field_label("Customer Fee"))
        self._fee_input = QLineEdit()
        self._fee_input.setPlaceholderText("0")
        layout.addWidget(self._fee_input)

        # Balance Change (read-only)
        layout.addWidget(self._field_label("Balance Change"))
        self._balance_change_display = QLineEdit()
        self._balance_change_display.setReadOnly(True)
        self._balance_change_display.setText("0")
        self._balance_change_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {ACCENT_GREEN}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 8px 12px; font-size: 13px; }}"
        )
        layout.addWidget(self._balance_change_display)

        # Note
        layout.addWidget(self._field_label("Note"))
        self._note_input = QTextEdit()
        self._note_input.setFixedHeight(60)
        self._note_input.setPlaceholderText("Optional note...")
        layout.addWidget(self._note_input)

        # Screenshot
        ss_row = QHBoxLayout()
        self._screenshot_btn = QPushButton("Attach Screenshot")
        self._screenshot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._screenshot_btn.setStyleSheet(
            f"QPushButton {{ background-color: {BG_DARK}; color: {ACCENT_BLUE}; "
            f"border: 1px solid {ACCENT_BLUE}; border-radius: 6px; padding: 8px 16px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; }}"
        )
        self._screenshot_btn.clicked.connect(self._on_select_screenshot)
        ss_row.addWidget(self._screenshot_btn)
        self._screenshot_label = QLabel("No file selected")
        self._screenshot_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        ss_row.addWidget(self._screenshot_label, 1)
        layout.addLayout(ss_row)

        # Status message
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        # Save button
        self._save_btn = QPushButton("Save Transaction")
        self._save_btn.setFixedHeight(44)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT_BLUE}; color: {BG_DARK}; "
            f"border: none; border-radius: 8px; font-size: 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: #74c7ec; }}"
        )
        self._save_btn.clicked.connect(self._on_save)
        layout.addWidget(self._save_btn)

        self._update_form_visibility()
        return self._form_frame

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
        return label

    def _update_form_visibility(self) -> None:
        is_transfer = self._selected_action == "transfer"
        is_exchange = self._selected_action == "exchange"
        has_customer = self._selected_action in ("deposit", "withdraw")

        self._to_account_label.setVisible(is_transfer)
        self._to_account_combo.setVisible(is_transfer)
        self._customer_label.setVisible(has_customer)
        self._customer_name.setVisible(has_customer)
        self._customer_phone.setVisible(has_customer)
        self._currency_label.setVisible(is_exchange)
        self._currency_combo.setVisible(is_exchange)

    # ── Auto-calculate ──

    def _get_selected_account(self) -> Optional[dict]:
        idx = self._account_combo.currentIndex()
        if idx < 0 or idx >= len(self._accounts_cache):
            return None
        return self._accounts_cache[idx]

    def _on_amount_changed(self) -> None:
        try:
            self._recalculate()
        except Exception:
            pass

    def _on_account_changed(self, index: int) -> None:
        try:
            self._recalculate()
        except Exception:
            pass

    def _recalculate(self) -> None:
        account = self._get_selected_account()
        amount = self._parse_amount()
        if account is None or amount <= 0:
            self._commission_display.setText("0")
            self._balance_change_display.setText("0")
            return

        commission = self._calc_commission(account, amount)
        balance_change = self._calc_balance_change(account, amount, commission)
        self._commission_display.setText(f"{commission:,.0f}")
        self._balance_change_display.setText(f"{balance_change:,.0f}")

    def _calc_commission(self, account: dict, amount: float) -> float:
        if account.get("account_type") == "agent":
            return round(amount * float(account.get("commission_rate", 0)), 2)
        return 0.0

    def _calc_balance_change(self, account: dict, amount: float, commission: float) -> float:
        if account.get("account_type") == "agent":
            return round(amount - commission, 2)
        return amount

    def _parse_amount(self) -> float:
        try:
            return float(self._amount_input.text().replace(",", ""))
        except ValueError:
            return 0.0

    # ── Data loading ──

    def _load_services(self) -> None:
        try:
            self._services_cache = self._api.get_services()
            self._service_combo.clear()
            for s in self._services_cache:
                self._service_combo.addItem(s.get("name", ""))
        except Exception:
            pass

    def _on_service_changed(self, index: int) -> None:
        try:
            if index < 0 or index >= len(self._services_cache):
                return
            service_id = self._services_cache[index].get("id")
            self._accounts_cache = self._api.get_accounts(service_id=service_id)
            self._account_combo.clear()
            self._to_account_combo.clear()
            for a in self._accounts_cache:
                label = f"{a.get('account_name', '')} — {a.get('phone_number', '')} [{a.get('account_type', '')}]"
                self._account_combo.addItem(label)
                self._to_account_combo.addItem(label)
        except Exception:
            pass

    def _load_my_transactions(self) -> None:
        try:
            txns = self._api.get_recent_transactions(50)
            self._populate_txn_table(txns)
        except Exception:
            pass

    # ── Screenshot ──

    def _on_select_screenshot(self) -> None:
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Screenshot", "",
                "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
            )
            if path:
                self._screenshot_path = path
                filename = path.rsplit("/", 1)[-1] if "/" in path else path.rsplit("\\", 1)[-1]
                self._screenshot_label.setText(filename)
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

        if action == "deposit":
            self._api.create_deposit(
                account_id=account["id"], amount=amount,
                customer_name=self._customer_name.text().strip(),
                customer_phone=self._customer_phone.text().strip(),
                screenshot_path=self._screenshot_path, note=note,
            )
        elif action == "withdraw":
            self._api.create_withdraw(
                account_id=account["id"], amount=amount,
                customer_name=self._customer_name.text().strip(),
                customer_phone=self._customer_phone.text().strip(),
                screenshot_path=self._screenshot_path, note=note,
            )
        elif action == "transfer":
            to_idx = self._to_account_combo.currentIndex()
            to_acc = self._accounts_cache[to_idx]
            self._api.create_transfer(
                from_account_id=account["id"], to_account_id=to_acc["id"],
                amount=amount, screenshot_path=self._screenshot_path, note=note,
            )
        elif action == "exchange":
            self._api.create_exchange(
                account_id=account["id"], amount=amount,
                currency=self._currency_combo.currentText(),
                screenshot_path=self._screenshot_path, note=note,
            )

        self._show_status("Transaction saved successfully!", error=False)
        self._clear_form()
        self._load_my_transactions()

    def _validate(self) -> Optional[str]:
        if self._account_combo.currentIndex() < 0:
            return "Account ရွေးပါ"
        if self._parse_amount() <= 0:
            return "Amount ထည့်ပါ"
        if not self._screenshot_path:
            return "Screenshot မပါဘဲ Save လို့မရပါ"

        if self._selected_action in ("deposit", "withdraw"):
            if not self._customer_name.text().strip():
                return "Customer Name ထည့်ပါ"
            if not self._customer_phone.text().strip():
                return "Customer Phone ထည့်ပါ"

        if self._selected_action == "transfer":
            to_idx = self._to_account_combo.currentIndex()
            from_idx = self._account_combo.currentIndex()
            if to_idx < 0:
                return "To Account ရွေးပါ"
            if to_idx == from_idx:
                return "From နှင့် To Account တူလို့မရပါ"

        return None

    def _clear_form(self) -> None:
        self._amount_input.clear()
        self._customer_name.clear()
        self._customer_phone.clear()
        self._fee_input.clear()
        self._note_input.clear()
        self._commission_display.setText("0")
        self._balance_change_display.setText("0")
        self._screenshot_path = None
        self._screenshot_label.setText("No file selected")
        self._screenshot_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")

    def _show_status(self, message: str, error: bool = False) -> None:
        color = ERROR_COLOR if error else SUCCESS_COLOR
        self._status_label.setText(message)
        self._status_label.setStyleSheet(f"color: {color}; font-size: 13px;")
        self._status_label.setVisible(True)

    # ── My Transactions table ──

    def _build_txn_table(self) -> QTableWidget:
        headers = [
            "Time", "Type", "Account", "Amount",
            "Commission", "Fee", "Balance Change", "Screenshot",
        ]
        self._txn_table = QTableWidget(0, len(headers))
        self._txn_table.setHorizontalHeaderLabels(headers)
        self._txn_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._txn_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._txn_table.setAlternatingRowColors(True)
        self._txn_table.verticalHeader().setVisible(False)
        self._txn_table.setMinimumHeight(250)

        header = self._txn_table.horizontalHeader()
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
            txn_type,
            str(txn.get("account_id", "")),
            f"{float(txn.get('amount', 0)):,.0f}",
            f"{float(txn.get('commission_amount', 0)):,.0f}",
            f"{float(txn.get('customer_fee', 0)):,.0f}",
            f"{float(txn.get('balance_change', 0)):,.0f}",
        ]
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if col == 1:
                from PyQt6.QtGui import QColor
                item.setForeground(QColor(color))
            self._txn_table.setItem(row, col, item)

        path = txn.get("screenshot_path", "")
        btn = QPushButton("View" if path else "-")
        btn.setEnabled(bool(path))
        btn.setStyleSheet(
            f"QPushButton {{ background: {BG_DARK}; color: {ACCENT_BLUE}; "
            f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; }}"
            f"QPushButton:hover {{ background: {BORDER_COLOR}; }}"
        )
        self._txn_table.setCellWidget(row, 7, btn)

    # ── Helpers ──

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        return label

    # ── Logout ──

    def _on_logout(self) -> None:
        try:
            self._api.logout()
            from views.login_view import LoginView
            self._login = LoginView(self._api)
            self._login.show()
            self.close()
        except Exception:
            pass
