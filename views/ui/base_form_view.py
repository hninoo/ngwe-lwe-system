"""
views/ui/base_form_view.py

Abstract base for all transaction sub-views.  Each concrete sub-view
(CashInView, CashOutView, TransferView, ExchangeView) overrides
_setup_fields() to build only the fields relevant to its type, and
declares _TXN_HEADERS / _TXN_COL_WIDTHS / _TXN_STRETCH for its table.
"""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QKeyEvent, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from repositories.transaction_ui_repository import TransactionUiRepository
from services.api_client import ApiClient
from views.components.input_validation import install_amount_validator, sanitize_text
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
    ERROR_COLOR,
    FEE_CASH_ITEM,
    SUCCESS_COLOR,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TYPE_COLORS,
    CompanyGridSelector,
    TabTextEdit,
    accent_btn,
    field_label,
    format_datetime,
    normalize_transaction_type,
    scrollable_page,
    section_label,
)
from views.widgets.company_selector import AccountSelector, ServiceTypeSelector, add_placeholder


class BaseFormView(QWidget):
    # ── Sub-class must declare these ──────────────────────────────────────────
    _TXN_HEADERS: list[str] = []
    _TXN_COL_WIDTHS: list[int] = []
    _TXN_STRETCH: set[int] = set()

    def __init__(
        self,
        api: ApiClient,
        navigate,
        transaction_type: str = "cash_in",
        repository=None,
    ) -> None:
        super().__init__()
        self._navigate = navigate
        self._repository = repository or TransactionUiRepository(api)
        self._selected_action: str = normalize_transaction_type(transaction_type)
        self._screenshot_path: Optional[str] = None
        self._accounts_cache: list[dict] = []
        self._to_accounts_cache: list[dict] = []
        self._fee_accounts_cache: list[dict] = []
        self._all_companies_cache: list[dict] = []

        # Optional widgets — populated by _setup_fields() in each subclass
        self._service_type_selector: Optional[ServiceTypeSelector] = None
        self._account_selector: Optional[AccountSelector] = None
        self._to_company_selector: Optional[CompanyGridSelector] = None
        self._to_account_selector: Optional[AccountSelector] = None
        self._currency_combo: Optional[QComboBox] = None
        self._customer_name: Optional[QLineEdit] = None
        self._customer_phone: Optional[QLineEdit] = None
        self._balance_hint: Optional[QLabel] = None

        # Fee grid widgets — set by _make_fee_grid()
        self._amount_input: Optional[QLineEdit] = None
        self._commission_display: Optional[QLineEdit] = None
        self._fee_display: Optional[QLineEdit] = None
        self._additional_fee_display: Optional[QLineEdit] = None
        self._total_charge_display: Optional[QLineEdit] = None
        self._fee_hint: Optional[QLabel] = None
        self._fee_account_combo: Optional[QComboBox] = None
        self._balance_change_display: Optional[QLineEdit] = None
        self._note_input: Optional[TabTextEdit] = None
        self._screenshot_btn: Optional[QPushButton] = None
        self._screenshot_label: Optional[QLabel] = None

        self._init_ui()

    # ── Initialisation ──────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()
        layout.addWidget(section_label(t("transaction")))
        layout.addWidget(self._build_form())
        layout.addWidget(section_label(t("todays_transactions")))
        layout.addWidget(self._build_txn_table())
        layout.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Form shell ──────────────────────────────────────────────────────────

    def _build_form(self) -> QFrame:
        self._form_frame = QFrame()
        self._form_frame.setObjectName("txnForm")
        self._form_frame.setStyleSheet(
            f"QFrame#txnForm {{ background-color: {BG_CARD}; border-radius: 10px;"
            f" border: 1px solid {BORDER_COLOR}; }}"
        )
        lo = QVBoxLayout(self._form_frame)
        lo.setContentsMargins(20, 20, 20, 20)
        lo.setSpacing(12)

        # Company grid (always present)
        lo.addWidget(field_label(t("field_company"), required=True))
        self._company_selector = CompanyGridSelector()
        self._company_selector.company_changed.connect(self._on_company_changed)
        lo.addWidget(self._company_selector)

        # Type-specific fields injected by each sub-view
        self._setup_fields(lo)

        # Float warning banner
        self._float_banner = QLabel("")
        self._float_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._float_banner.setStyleSheet(
            f"background-color: #45475a; color: {ACCENT_YELLOW}; "
            f"border-radius: 6px; padding: 8px 12px; font-size: 12px; font-weight: bold;"
        )
        self._float_banner.setVisible(False)
        lo.addWidget(self._float_banner)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        lo.addWidget(self._status_label)

        # Save button — left-aligned
        save_row = QHBoxLayout()
        save_row.setContentsMargins(0, 20, 0, 0)
        save_row.setSpacing(0)
        self._save_btn = accent_btn(t("save_transaction"))
        self._save_btn.setFixedHeight(44)
        self._save_btn.clicked.connect(self._on_save)
        save_row.addWidget(self._save_btn)
        save_row.addItem(
            QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )
        lo.addLayout(save_row)

        return self._form_frame

    def _setup_fields(self, lo: QVBoxLayout) -> None:
        """Override in each sub-view to add type-specific fields."""

    def _cash_in_overpayment_payload(self) -> dict:
        return {}

    def _validate_cash_in_overpayment(self) -> Optional[str]:
        return None

    def _clear_cash_in_overpayment(self) -> None:
        return None

    def _cash_out_denominations_payload(self) -> Optional[dict[str, int]]:
        return None

    def _validate_cash_out_denominations(self) -> Optional[str]:
        return None

    def _clear_cash_out_denominations(self) -> None:
        return None

    # ── Shared field-building helpers ───────────────────────────────────────

    @staticmethod
    def _gcell(label: QLabel, widget: QWidget) -> QWidget:
        cell = QWidget()
        cl = QVBoxLayout(cell)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)
        cl.addWidget(label)
        cl.addWidget(widget)
        return cell

    def _make_account_cell_with_balance(
        self, label_text: str, required: bool = True
    ) -> QWidget:
        """Create account dropdown with current-balance hint on the right of the label."""
        acc_label = field_label(label_text, required=required)
        self._account_selector = AccountSelector()
        self._account_selector.currentIndexChanged.connect(self._on_account_changed)

        cell = QWidget()
        cl = QVBoxLayout(cell)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(acc_label)
        header.addItem(
            QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )
        self._balance_hint = QLabel("")
        self._balance_hint.setStyleSheet(
            f"color: {ACCENT_GREEN}; font-size: 11px; font-style: italic;"
        )
        self._balance_hint.setVisible(False)
        header.addWidget(self._balance_hint)
        cl.addLayout(header)
        cl.addWidget(self._account_selector)
        return cell

    def _make_amount_input(self) -> QLineEdit:
        self._amount_input = QLineEdit()
        install_amount_validator(self._amount_input)
        self._amount_input.setPlaceholderText("0")
        self._amount_input.textChanged.connect(self._on_amount_changed)
        # Focus next to fee account after amount; fee_account_combo set later by _make_fee_grid
        self._amount_input.returnPressed.connect(
            lambda: self._fee_account_combo.setFocus() if self._fee_account_combo else None
        )
        return self._amount_input

    def _make_fee_grid(self) -> QGridLayout:
        """Build the shared Fee / Commission / Total / Fee-Account / Balance-Change grid."""
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        for col in range(12):
            grid.setColumnStretch(col, 1)

        gcell = self._gcell

        # Row 0: customer fee | additional fee | commission
        self._fee_label = field_label(t("field_customer_fee"))
        self._fee_display = QLineEdit()
        self._fee_display.setReadOnly(True)
        self._fee_display.setText("0")
        self._fee_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {ACCENT_TEAL};"
            f" border: 1px solid {BORDER_COLOR}; border-radius: 6px;"
            f" padding: 8px 12px; font-size: 13px; }}"
        )
        grid.addWidget(gcell(self._fee_label, self._fee_display), 0, 0, 1, 4)

        self._additional_fee_label = field_label(t("field_additional_fee"))
        self._additional_fee_display = QLineEdit()
        self._additional_fee_display.setReadOnly(True)
        self._additional_fee_display.setText("0")
        self._additional_fee_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {ACCENT_YELLOW};"
            f" border: 1px solid {BORDER_COLOR}; border-radius: 6px;"
            f" padding: 8px 12px; font-size: 13px; }}"
        )
        grid.addWidget(gcell(self._additional_fee_label, self._additional_fee_display), 0, 4, 1, 4)

        self._commission_label = field_label(t("field_commission"))
        self._commission_display = QLineEdit()
        self._commission_display.setReadOnly(True)
        self._commission_display.setText("0")
        self._commission_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {ACCENT_MAUVE};"
            f" border: 1px solid {BORDER_COLOR}; border-radius: 6px;"
            f" padding: 8px 12px; font-size: 13px; }}"
        )
        grid.addWidget(gcell(self._commission_label, self._commission_display), 0, 8, 1, 4)

        # Row 1: total fee (+ hint) | fee account | balance change
        self._total_fee_label = field_label(t("field_total_fee"))
        self._total_charge_display = QLineEdit()
        self._total_charge_display.setReadOnly(True)
        self._total_charge_display.setText("0")
        self._total_charge_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {TEXT_PRIMARY};"
            f" border: 1px solid {BORDER_COLOR}; border-radius: 6px;"
            f" padding: 8px 12px; font-size: 13px; font-weight: bold; }}"
        )
        self._fee_hint = QLabel("")
        self._fee_hint.setStyleSheet(
            f"color: {ACCENT_TEAL}; font-size: 11px; font-style: italic; padding-left: 2px;"
        )
        self._fee_hint.setVisible(False)
        total_cell = QWidget()
        tlo = QVBoxLayout(total_cell)
        tlo.setContentsMargins(0, 0, 0, 0)
        tlo.setSpacing(4)
        tlo.addWidget(self._total_fee_label)
        tlo.addWidget(self._total_charge_display)
        tlo.addWidget(self._fee_hint)
        grid.addWidget(total_cell, 1, 0, 1, 4)

        self._fee_account_label = field_label(t("field_fee_account"))
        self._fee_account_combo = QComboBox()
        add_placeholder(self._fee_account_combo, t("select_placeholder"))
        grid.addWidget(gcell(self._fee_account_label, self._fee_account_combo), 1, 4, 1, 4)

        self._balance_change_label = field_label(t("field_balance_change"))
        self._balance_change_display = QLineEdit()
        self._balance_change_display.setReadOnly(True)
        self._balance_change_display.setText("0")
        self._balance_change_display.setStyleSheet(
            f"QLineEdit {{ background-color: {BG_DARK}; color: {ACCENT_GREEN};"
            f" border: 1px solid {BORDER_COLOR}; border-radius: 6px;"
            f" padding: 8px 12px; font-size: 13px; }}"
        )
        grid.addWidget(gcell(self._balance_change_label, self._balance_change_display), 1, 8, 1, 4)

        return grid

    def _make_note_screenshot(self, lo: QVBoxLayout) -> None:
        """Append note field and screenshot button to the given layout."""
        note_label = field_label(t("field_note"))
        self._note_input = TabTextEdit(on_enter=lambda: self._screenshot_btn and self._screenshot_btn.setFocus())
        self._note_input.setFixedHeight(60)
        self._note_input.setPlaceholderText(t("note_placeholder"))
        lo.addWidget(self._gcell(note_label, self._note_input))

        ss_row = QHBoxLayout()
        ss_row.setContentsMargins(0, 0, 0, 0)
        ss_row.setSpacing(10)
        ss_wrap = QWidget()
        ss_wrap.setLayout(ss_row)
        self._screenshot_btn = QPushButton(t("attach_screenshot"))
        self._screenshot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._screenshot_btn.setStyleSheet(
            f"QPushButton {{ background-color: {BG_DARK}; color: {ACCENT_BLUE};"
            f" border: 1px solid {ACCENT_BLUE}; border-radius: 6px;"
            f" padding: 8px 16px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: {BG_CARD}; }}"
        )
        self._screenshot_btn.clicked.connect(self._on_select_screenshot)
        ss_row.addWidget(self._screenshot_btn)
        self._screenshot_label = QLabel(t("no_file_selected"))
        self._screenshot_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        ss_row.addWidget(self._screenshot_label, 1)
        lo.addWidget(ss_wrap)

    # ── Float management ────────────────────────────────────────────────────

    def load_data(self) -> None:
        try:
            self._load_companies()
            self._load_my_transactions()
            user = self._repository.current_user
            if user.get("role") == "employee":
                self._set_float_state(self._check_float_status())
        except Exception:
            self._show_status(t("err_load_data") if t("err_load_data") != "err_load_data" else "Failed to load data.", error=True)

    def _check_float_status(self) -> bool:
        try:
            floats = self._repository.get_floats()
            self._active_float = next((f for f in floats if f.get("status") == "ACTIVE"), None)
            return self._active_float is not None
        except Exception:
            self._active_float = None
            return True

    def _set_float_state(self, has_float: bool) -> None:
        self._float_banner.setText("" if has_float else t("warn_no_float_banner"))
        self._float_banner.setVisible(not has_float)
        self._save_btn.setEnabled(has_float)

    # ── Calculations ────────────────────────────────────────────────────────

    def _get_selected_account(self) -> Optional[dict]:
        return self._account_selector.selected_account() if self._account_selector else None

    def _on_amount_changed(self) -> None:
        try:
            self._recalculate()
            self._update_balance_hint()
        except Exception:
            pass

    def _on_account_changed(self, _index: int = 0) -> None:
        try:
            self._recalculate()
            self._update_balance_hint()
        except Exception:
            pass

    def _recalculate(self) -> None:
        account = self._get_selected_account()
        amount = self._parse_amount()

        def _zero() -> None:
            if self._commission_display:
                self._commission_display.setText("0")
            if self._balance_change_display:
                self._balance_change_display.setText("0")
            if self._fee_display:
                self._fee_display.setText("0")
            if self._additional_fee_display:
                self._additional_fee_display.setText("0")
            if self._total_charge_display:
                self._total_charge_display.setText("0")
            if self._fee_hint:
                self._fee_hint.setVisible(False)

        if account is None or amount <= 0:
            _zero()
            return

        tier = self._lookup_tier(account, amount)
        is_cash_out = self._selected_action == "cash_out"

        if tier is None:
            if self._commission_display:
                self._commission_display.setText("0")
            if self._fee_display:
                self._fee_display.setText("0")
            if self._additional_fee_display:
                self._additional_fee_display.setText("0")
            if self._total_charge_display:
                self._total_charge_display.setText("0")
            if self._balance_change_display:
                balance_change = -amount if self._selected_action in ("cash_in", "transfer") else amount
                self._balance_change_display.setText(f"{balance_change:,.0f}")
            if self._fee_hint:
                self._fee_hint.setText(t("no_tier"))
                self._fee_hint.setStyleSheet(
                    f"color: {ACCENT_YELLOW}; font-size: 11px; font-style: italic; padding-left: 2px;"
                )
                self._fee_hint.setVisible(True)
            return

        fee_type = (tier.get("fee_amount_type") or "FIXED").upper()
        comm_type_val = (tier.get("comm_type") or "FIXED").upper()
        add_type = (tier.get("additional_fee_type") or "FIXED").upper()

        if is_cash_out:
            fee_raw = float(tier.get("fee_amount_cash_out") or 0)
            comm_raw = float(tier.get("comm_cash_out") or 0)
            add_raw = float(tier.get("additional_fee_cash_out_amount") or 0)
        else:
            fee_raw = float(tier.get("fee_amount_cash_in") or 0)
            comm_raw = float(tier.get("comm_cash_in") or 0)
            add_raw = float(tier.get("additional_fee_cash_in_amount") or 0)

        fee_amount = round(amount * fee_raw, 2) if fee_type == "PERCENTAGE" else fee_raw
        commission = round(amount * comm_raw, 2) if comm_type_val == "PERCENTAGE" else comm_raw
        additional = round(amount * add_raw, 2) if add_type == "PERCENTAGE" else add_raw

        # Match repository balance effects: Cash In and Transfer debit the selected account.
        if self._selected_action in ("cash_in", "transfer"):
            balance_change = -amount
        else:
            balance_change = amount

        total_fee = fee_amount + additional
        customer_total = amount + total_fee

        if self._commission_display:
            self._commission_display.setText(f"{commission:,.0f}")
        if self._fee_display:
            self._fee_display.setText(f"{fee_amount:,.0f}")
        if self._additional_fee_display:
            self._additional_fee_display.setText(f"{additional:,.0f}")
        if self._total_charge_display:
            self._total_charge_display.setText(f"{total_fee:,.0f}")
        if self._balance_change_display:
            self._balance_change_display.setText(f"{balance_change:,.0f}")

        if self._fee_hint:
            if is_cash_out:
                self._fee_hint.setText(
                    f"CashOut: {amount:,.0f}  |  Fee: {fee_amount:,.0f} + {additional:,.0f}"
                    f" = {total_fee:,.0f}  |  Agent commission: {commission:,.0f}"
                )
            else:
                self._fee_hint.setText(
                    f"Customer pays: {amount:,.0f} + {total_fee:,.0f} (fee) = {customer_total:,.0f}"
                    f"  |  To fee account: {total_fee:,.0f}  |  Agent commission: {commission:,.0f}"
                )
            self._fee_hint.setStyleSheet(
                f"color: {ACCENT_TEAL}; font-size: 11px; font-style: italic; padding-left: 2px;"
            )
            self._fee_hint.setVisible(True)

    def _lookup_tier(self, account: dict, amount: float) -> Optional[dict]:
        service_type_id = account.get("service_type_id")
        if service_type_id is None:
            return None
        try:
            tier = self._repository.lookup_tier(service_type_id, amount)
            if (
                tier.get("fee_amount_cash_in", 0) == 0
                and tier.get("fee_amount_cash_out", 0) == 0
                and tier.get("comm_cash_in", 0) == 0
                and tier.get("comm_cash_out", 0) == 0
            ):
                return None
            return tier
        except Exception:
            return None

    def _parse_amount(self) -> float:
        if not self._amount_input:
            return 0.0
        try:
            return float(self._amount_input.text().replace(",", ""))
        except ValueError:
            return 0.0

    def _parse_additional_fee(self) -> float:
        if not self._additional_fee_display:
            return 0.0
        try:
            return float(self._additional_fee_display.text().replace(",", ""))
        except ValueError:
            return 0.0

    def _parse_total_fee(self) -> float:
        base = 0.0
        if self._fee_display:
            try:
                base = float(self._fee_display.text().replace(",", ""))
            except ValueError:
                pass
        return base + self._parse_additional_fee()

    def _get_fee_account_id(self) -> Optional[int]:
        if not self._fee_account_combo:
            return None
        idx = self._fee_account_combo.currentIndex()
        if idx <= 0:
            return None
        acc_idx = idx - 1
        if acc_idx < len(self._fee_accounts_cache):
            acc_id = self._fee_accounts_cache[acc_idx].get("id")
            return acc_id if acc_id != 0 else None
        return None

    # ── Balance hint ────────────────────────────────────────────────────────

    def _get_fresh_balance(self, account_id: int) -> float:
        try:
            return float(self._repository.get_account(account_id).get("balance", 0))
        except Exception:
            return 0.0

    def _calc_projected(self, balance: float, amount: float) -> float:
        if amount <= 0:
            return balance
        # Match repository balance effects: Cash In and Transfer debit the selected account.
        if self._selected_action in ("cash_in", "transfer"):
            return balance - amount
        return balance + amount

    def _update_balance_hint(self) -> None:
        if not self._balance_hint:
            return
        account = self._get_selected_account()
        if account is None:
            self._balance_hint.setVisible(False)
            return
        balance = self._get_fresh_balance(account["id"])
        amount = self._parse_amount()
        if amount <= 0:
            c = ACCENT_GREEN if balance >= 0 else ACCENT_RED
            self._balance_hint.setText(t("current_balance", balance=f"{balance:,.0f}"))
            self._balance_hint.setStyleSheet(f"color: {c}; font-size: 11px; font-style: italic;")
        else:
            projected = self._calc_projected(balance, amount)
            c = ACCENT_GREEN if projected >= 0 else ACCENT_RED
            self._balance_hint.setText(
                t("balance_after", balance=f"{balance:,.0f}", projected=f"{projected:,.0f}")
            )
            self._balance_hint.setStyleSheet(f"color: {c}; font-size: 11px; font-style: italic;")
        self._balance_hint.setVisible(True)

    # ── Combo validation helpers ────────────────────────────────────────────

    def _set_combo_warning(self, combo: Optional[QComboBox], warn: bool) -> None:
        if combo is None:
            return
        if not warn:
            combo.setStyleSheet("")
            return
        combo.setStyleSheet(
            f"QComboBox {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY};"
            f" border: 1px solid {ACCENT_RED}; border-radius: 6px;"
            f" padding: 8px 12px; font-size: 13px; }}"
            f"QComboBox::drop-down {{ border: none; }}"
        )

    def _clear_combo_warnings(self) -> None:
        for combo in (
            self._service_type_selector,
            self._account_selector,
            self._currency_combo,
            self._to_account_selector,
        ):
            self._set_combo_warning(combo, False)

    # ── Data loading ────────────────────────────────────────────────────────

    def _get_companies_for_action(self) -> list[dict]:
        if self._selected_action in ("cash_in", "cash_out"):
            return [
                c for c in self._all_companies_cache
                if c.get("category") in ("Pay", "Bank", "Both")
            ]
        return [
            c for c in self._all_companies_cache
            if c.get("category") in ("Bank", "Both")
        ]

    def _repopulate_company_selectors(self) -> None:
        if not self._all_companies_cache:
            return
        filtered = self._get_companies_for_action()
        self._company_selector.blockSignals(True)
        self._company_selector.populate(filtered, self._repository)
        self._company_selector.blockSignals(False)
        if self._to_company_selector is not None:
            self._to_company_selector.blockSignals(True)
            self._to_company_selector.populate(filtered, self._repository)
            self._to_company_selector.blockSignals(False)
        cid = self._company_selector.selected_company_id()
        if cid is not None:
            self._on_company_changed(cid)
        if self._to_company_selector is not None:
            cid_to = self._to_company_selector.selected_company_id()
            if cid_to is not None:
                self._on_to_company_changed(cid_to)

    def _load_companies(self) -> None:
        try:
            self._all_companies_cache = self._repository.get_companies()
            self._repopulate_company_selectors()
        except Exception:
            self._show_status("Failed to load companies.", error=True)
        self._load_fee_accounts()

    def _load_fee_accounts(self) -> None:
        try:
            all_accounts = self._repository.get_accounts()
            fee_accs = [a for a in all_accounts if int(a.get("is_fee_account") or 0) == 1]
            self._fee_accounts_cache = [FEE_CASH_ITEM] + fee_accs
        except Exception:
            self._fee_accounts_cache = [FEE_CASH_ITEM]

        if not self._fee_account_combo:
            return
        self._fee_account_combo.clear()
        add_placeholder(self._fee_account_combo, t("select_placeholder"))
        for a in self._fee_accounts_cache:
            label = (
                f"{a.get('account_name', '')} | {a.get('phone_number', '')}"
                if a.get("phone_number")
                else a.get("account_name", "")
            )
            self._fee_account_combo.addItem(label)

    def _on_company_changed(self, company_id: int) -> None:
        try:
            service_types = self._repository.get_service_types(company_id)
            if self._selected_action in ("transfer", "exchange"):
                target = self._selected_action.capitalize()
                st = next(
                    (s for s in service_types if s.get("name", "").lower() == target.lower()),
                    None,
                )
                if st:
                    self._on_service_type_changed(st["id"])
            else:
                filtered = [
                    s for s in service_types
                    if s.get("operation") == "All" or s.get("name") in ("WST", "Pay_To_Pay")
                ]
                if self._service_type_selector is not None:
                    self._service_type_selector.populate(filtered)
                if self._account_selector is not None:
                    self._account_selector.populate([])
        except Exception:
            pass

    def _on_service_type_changed(self, service_type_id: int) -> None:
        try:
            accounts = self._repository.get_accounts(service_type_id=service_type_id)
            if self._account_selector is not None:
                self._account_selector.populate(accounts)
            self._accounts_cache = accounts
            self._on_account_changed(0)
        except Exception:
            pass

    def _on_to_company_changed(self, company_id: int) -> None:
        try:
            service_types = self._repository.get_service_types(company_id)
            st = next(
                (s for s in service_types if s.get("name", "").lower() == "transfer"),
                None,
            )
            if st:
                self._on_to_service_type_changed(st["id"])
        except Exception:
            pass

    def _on_to_service_type_changed(self, service_type_id: int) -> None:
        try:
            accounts = self._repository.get_accounts(service_type_id=service_type_id)
            if self._to_account_selector is not None:
                self._to_account_selector.populate(accounts)
            self._to_accounts_cache = accounts
        except Exception:
            pass

    def _load_my_transactions(self) -> None:
        try:
            self._populate_txn_table(self._repository.get_recent_transactions(50))
        except Exception:
            self._show_status("Failed to load transactions.", error=True)

    # ── Screenshot ──────────────────────────────────────────────────────────

    def _on_select_screenshot(self) -> None:
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, t("select_screenshot"), "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
            )
            if path and self._screenshot_label:
                self._screenshot_path = path
                name = path.rsplit("/", 1)[-1] if "/" in path else path.rsplit("\\", 1)[-1]
                self._screenshot_label.setText(name)
                self._screenshot_label.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
        except Exception:
            pass

    # ── Save ────────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        try:
            self._handle_save()
        except Exception as e:
            self._show_status(f"Error: {e}", error=True)

    def _handle_save(self) -> None:
        self._clear_combo_warnings()
        error = self._validate()
        if error:
            self._show_status(error, error=True)
            return
        action = self._selected_action
        amount = self._parse_amount()
        account = self._get_selected_account()
        note = sanitize_text(self._note_input.toPlainText(), 500) if self._note_input else None
        note = note or None
        fee = self._parse_total_fee()
        additional = self._parse_additional_fee()
        fee_acc = self._get_fee_account_id()

        if action == "cash_in":
            overpayment_payload = self._cash_in_overpayment_payload()
            if self._repository.current_user.get("role") == "employee":
                response = QMessageBox.warning(
                    self,
                    "Cash In - Important",
                    "After recording this cash_in, immediately hand the physical cash "
                    "to the Cashier for confirmation.\n\n"
                    "This amount will NOT be added to your Mini Vault balance.",
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                )
                if response != QMessageBox.StandardButton.Ok:
                    return
            self._repository.create_cash_in(
                account_id=account["id"],
                amount=amount,
                customer_name=sanitize_text(self._customer_name.text(), 120) if self._customer_name else "",
                customer_phone=sanitize_text(self._customer_phone.text(), 40) if self._customer_phone else "",
                screenshot_path=self._screenshot_path,
                customer_fee=fee,
                additional_fee_amount=additional,
                fee_account_id=fee_acc,
                note=note,
                **overpayment_payload,
            )
        elif action == "cash_out":
            self._repository.create_cash_out(
                account_id=account["id"],
                amount=amount,
                customer_name=sanitize_text(self._customer_name.text(), 120) if self._customer_name else "",
                customer_phone=sanitize_text(self._customer_phone.text(), 40) if self._customer_phone else "",
                screenshot_path=self._screenshot_path,
                customer_fee=fee,
                additional_fee_amount=additional,
                fee_account_id=fee_acc,
                note=note,
                denominations=self._cash_out_denominations_payload(),
            )
        elif action == "transfer":
            to_acc_id = self._to_account_selector.selected_account_id() if self._to_account_selector else None
            self._repository.create_transfer(
                from_account_id=account["id"],
                to_account_id=to_acc_id,
                amount=amount,
                screenshot_path=self._screenshot_path,
                customer_fee=fee,
                additional_fee_amount=additional,
                fee_account_id=fee_acc,
                note=note,
            )
        elif action == "exchange":
            currency = ""
            if self._currency_combo:
                currency = self._currency_combo.currentData() or self._currency_combo.currentText()
            self._repository.create_exchange(
                account_id=account["id"],
                amount=amount,
                currency=currency,
                screenshot_path=self._screenshot_path,
                customer_fee=fee,
                additional_fee_amount=additional,
                fee_account_id=fee_acc,
                note=note,
            )

        self._show_status(t("txn_saved"), error=False)
        self._clear_form()
        self._load_my_transactions()

    def _validate(self) -> Optional[str]:
        user = self._repository.current_user
        if user.get("role") == "employee" and self._selected_action in (
            "cash_out",
            "transfer",
            "exchange",
        ):
            if not self._check_float_status():
                return t("err_no_float")
            float_balance = float((getattr(self, "_active_float", None) or {}).get("current_balance") or 0)
            if self._parse_amount() > float_balance:
                return f"Vault Insufficient: available {float_balance:,.0f} MMK."

        if (
            self._selected_action in ("cash_in", "cash_out")
            and self._service_type_selector is not None
            and self._service_type_selector.selected_service_type_id() is None
        ):
            self._set_combo_warning(self._service_type_selector, True)
            return t("err_select_service_type")

        if self._account_selector is None or self._account_selector.selected_account_id() is None:
            self._set_combo_warning(self._account_selector, True)
            return t("err_select_account")

        if self._parse_amount() <= 0:
            return t("err_enter_amount")

        if (
            self._selected_action == "exchange"
            and self._currency_combo is not None
            and self._currency_combo.currentIndex() <= 0
        ):
            self._set_combo_warning(self._currency_combo, True)
            return t("err_select_currency")

        if self._selected_action in ("cash_in", "cash_out"):
            if self._customer_name and not self._customer_name.text().strip():
                return t("err_customer_name")
            if self._customer_phone and not self._customer_phone.text().strip():
                return t("err_customer_phone")
            if self._selected_action == "cash_in":
                overpayment_error = self._validate_cash_in_overpayment()
                if overpayment_error:
                    return overpayment_error
            if self._selected_action == "cash_out":
                denomination_error = self._validate_cash_out_denominations()
                if denomination_error:
                    return denomination_error

        if self._selected_action == "transfer":
            if self._to_account_selector is None:
                return t("err_select_to_account")
            to_acc_id = self._to_account_selector.selected_account_id()
            if to_acc_id is None:
                self._set_combo_warning(self._to_account_selector, True)
                return t("err_select_to_account")
            if to_acc_id == self._account_selector.selected_account_id():
                return t("err_same_account")

        # Insufficient-balance check for actions that decrease the account balance.
        if self._selected_action == "transfer":
            account = self._get_selected_account()
            if account:
                balance = self._get_fresh_balance(account["id"])
                if self._calc_projected(balance, self._parse_amount()) < 0:
                    return t("err_insufficient", balance=f"{balance:,.0f}")

        return None

    def _clear_form(self) -> None:
        if self._amount_input:
            self._amount_input.clear()
        if self._customer_name:
            self._customer_name.clear()
        if self._customer_phone:
            self._customer_phone.clear()
        if self._fee_display:
            self._fee_display.setText("0")
        if self._additional_fee_display:
            self._additional_fee_display.setText("0")
        if self._total_charge_display:
            self._total_charge_display.setText("0")
        if self._fee_hint:
            self._fee_hint.setVisible(False)
        if self._fee_account_combo:
            self._fee_account_combo.setCurrentIndex(0)
        if self._currency_combo:
            self._currency_combo.setCurrentIndex(0)
        if self._service_type_selector and self._service_type_selector.count():
            self._service_type_selector.setCurrentIndex(0)
        if self._account_selector and self._account_selector.count():
            self._account_selector.setCurrentIndex(0)
        if self._to_account_selector and self._to_account_selector.count():
            self._to_account_selector.setCurrentIndex(0)
        self._clear_combo_warnings()
        if self._note_input:
            self._note_input.clear()
        if self._commission_display:
            self._commission_display.setText("0")
        if self._balance_change_display:
            self._balance_change_display.setText("0")
        if self._balance_hint:
            self._balance_hint.setVisible(False)
        self._screenshot_path = None
        if self._screenshot_label:
            self._screenshot_label.setText(t("no_file_selected"))
            self._screenshot_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        self._clear_cash_in_overpayment()
        self._clear_cash_out_denominations()

    def _show_status(self, msg: str, error: bool = False) -> None:
        self._status_label.setText(msg)
        self._status_label.setStyleSheet(
            f"color: {ERROR_COLOR if error else SUCCESS_COLOR}; font-size: 13px;"
        )
        self._status_label.setVisible(True)

    # ── Transaction table ───────────────────────────────────────────────────

    def _build_txn_table(self) -> QTableWidget:
        headers = self._TXN_HEADERS or ["Time", "Account", "Amount", "Fee"]
        self._txn_table = QTableWidget(0, len(headers))
        self._txn_table.setHorizontalHeaderLabels(headers)
        self._txn_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._txn_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._txn_table.setAlternatingRowColors(True)
        self._txn_table.verticalHeader().setVisible(False)
        self._txn_table.setMinimumHeight(250)
        self._txn_table.setWordWrap(False)
        self._txn_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._txn_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._apply_table_columns()
        return self._txn_table

    def _apply_table_columns(self) -> None:
        widths = self._TXN_COL_WIDTHS or []
        stretch = self._TXN_STRETCH or set()
        header = self._txn_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        for i, w in enumerate(widths):
            if i in stretch:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self._txn_table.setColumnWidth(i, int(w))

    def _populate_txn_table(self, txns: list[dict]) -> None:
        filtered = [
            txn for txn in txns
            if txn.get("transaction_type") == self._selected_action
        ]
        self._txn_table.setRowCount(len(filtered))
        for row, txn in enumerate(filtered):
            self._set_txn_row(row, txn)
            self._txn_table.setRowHeight(row, 30)

    def _set_txn_row(self, row: int, txn: dict) -> None:
        """Override in each sub-view for type-specific column layout."""
        acc = self._find_account(txn.get("account_id"))
        total_fee = float(txn.get("customer_fee", 0) or 0)
        commission = float(txn.get("commission_amount", 0) or 0)
        items = [
            format_datetime(txn.get("created_at", "")),
            acc.get("account_name", "") if acc else str(txn.get("account_id", "")),
            f"{float(txn.get('amount', 0) or 0):,.0f}",
            f"{total_fee:,.0f} / {commission:,.0f}",
        ]
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setToolTip(text)
            self._txn_table.setItem(row, col, item)

    def _find_account(self, account_id) -> Optional[dict]:
        if not account_id:
            return None
        for cache in (self._accounts_cache, self._to_accounts_cache, self._fee_accounts_cache):
            for acc in cache:
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
            img.setPixmap(
                pixmap.scaledToWidth(
                    min(pixmap.width(), 800), Qt.TransformationMode.SmoothTransformation
                )
            )
            img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            scroll.setWidget(img)
            lo = QVBoxLayout(dlg)
            lo.setContentsMargins(0, 0, 0, 0)
            lo.addWidget(scroll)
            dlg.exec()
        except Exception as e:
            self._show_status(t("err_screenshot", error=str(e)), error=True)
