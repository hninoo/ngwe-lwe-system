from PyQt6.QtCore import Qt
from typing import Optional

from PyQt6.QtWidgets import QGridLayout, QLineEdit, QTableWidgetItem, QVBoxLayout, QWidget

from i18n import t
from views.ui.base_form_view import BaseFormView
from views.transaction_view import (
    ACCENT_GREEN,
    ACCENT_RED,
    field_label,
    format_datetime,
)
from views.widgets.company_selector import ServiceTypeSelector
from views.widgets.denomination_input import DenominationInputWidget


DENOMINATIONS = [20000, 10000, 5000, 1000, 500, 200, 100, 50]


class CashOutView(BaseFormView):
    transaction_type = "cash_out"

    _TXN_HEADERS = ["Time", "Account", "Customer", "Phone", "Amount", "Commission", "Total Fee"]
    _TXN_COL_WIDTHS = [170, 0, 0, 130, 120, 120, 120]
    _TXN_STRETCH: set = {1, 2}

    def __init__(self, api, navigate, repository=None) -> None:
        self._cash_out_denom_container: Optional[QWidget] = None
        self._cash_out_denom_widget: Optional[DenominationInputWidget] = None
        super().__init__(
            api,
            navigate,
            transaction_type=self.transaction_type,
            repository=repository,
        )

    # ── Form fields ──────────────────────────────────────────────────────────

    def _setup_fields(self, lo) -> None:
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        for col in range(12):
            grid.setColumnStretch(col, 1)

        # Row 0 — Service Type (left) | Account + balance hint (right)
        st_label = field_label(t("field_service_type"), required=True)
        self._service_type_selector = ServiceTypeSelector()
        self._service_type_selector.service_type_changed.connect(self._on_service_type_changed)
        grid.addWidget(self._gcell(st_label, self._service_type_selector), 0, 0, 1, 6)

        grid.addWidget(
            self._make_account_cell_with_balance(t("field_account"), required=True),
            0, 6, 1, 6,
        )

        # Row 1 — Customer Name | Customer Phone | Amount
        cust_name_label = field_label(t("customer_name_ph"), required=True)
        self._customer_name = QLineEdit()
        self._customer_name.setPlaceholderText(t("customer_name_ph"))
        self._customer_name.returnPressed.connect(
            lambda: self._customer_phone.setFocus() if self._customer_phone else None
        )
        grid.addWidget(self._gcell(cust_name_label, self._customer_name), 1, 0, 1, 4)

        cust_phone_label = field_label(t("customer_phone_ph"), required=True)
        self._customer_phone = QLineEdit()
        self._customer_phone.setPlaceholderText(t("customer_phone_ph"))
        self._customer_phone.returnPressed.connect(
            lambda: self._amount_input.setFocus() if self._amount_input else None
        )
        grid.addWidget(self._gcell(cust_phone_label, self._customer_phone), 1, 4, 1, 4)

        amount_label = field_label(t("field_amount"), required=True)
        grid.addWidget(self._gcell(amount_label, self._make_amount_input()), 1, 8, 1, 4)

        lo.addLayout(grid)
        lo.addLayout(self._make_fee_grid())
        self._cash_out_denom_container = QWidget()
        self._cash_out_denom_container.setLayout(QVBoxLayout())
        self._cash_out_denom_container.layout().setContentsMargins(0, 0, 0, 0)
        self._cash_out_denom_container.layout().setSpacing(0)
        lo.addWidget(self._cash_out_denom_container)
        self._set_cash_out_denom_widget()
        self._make_note_screenshot(lo)

    def load_data(self) -> None:
        super().load_data()
        self._refresh_cash_out_denominations()

    def _refresh_cash_out_denominations(self) -> None:
        if not self._cash_out_denom_container:
            return
        try:
            active_float = getattr(self, "_active_float", None)
            if not active_float:
                return
            balance = self._repository.get_float_denomination_balance(active_float["id"])
            max_quantities = balance.get("denominations", {}) or {}
            current = self._cash_out_denom_widget.breakdown()
            self._set_cash_out_denom_widget(max_quantities)
            self._cash_out_denom_widget.set_breakdown(current)
        except Exception:
            pass

    def _set_cash_out_denom_widget(self, max_quantities: Optional[dict] = None) -> None:
        if not self._cash_out_denom_container:
            return
        layout = self._cash_out_denom_container.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._cash_out_denom_widget = DenominationInputWidget(
            DENOMINATIONS,
            title="Mini Vault Cash Out Denominations",
            max_quantities=max_quantities,
        )
        self._cash_out_denom_widget.total_changed.connect(lambda _total: self._on_amount_changed())
        layout.addWidget(self._cash_out_denom_widget)

    def _cash_out_denominations_payload(self) -> Optional[dict[str, int]]:
        if self._repository.current_user.get("role") != "employee":
            return None
        return self._cash_out_denom_widget.breakdown() if self._cash_out_denom_widget else None

    def _validate_cash_out_denominations(self) -> Optional[str]:
        if self._repository.current_user.get("role") != "employee":
            return None
        if not self._cash_out_denom_widget:
            return "Mini Vault denomination breakdown is required."
        total = self._cash_out_denom_widget.total()
        amount = int(self._parse_amount())
        if total <= 0:
            return "Mini Vault denomination breakdown is required."
        if total != amount:
            return (
                f"Mini Vault denomination total {total:,.0f} MMK must match "
                f"Cash Out amount {amount:,.0f} MMK."
            )
        return None

    def _clear_cash_out_denominations(self) -> None:
        if self._cash_out_denom_widget:
            self._cash_out_denom_widget.clear()
            self._refresh_cash_out_denominations()

    # ── Table ────────────────────────────────────────────────────────────────

    def _set_txn_row(self, row: int, txn: dict) -> None:
        acc = self._find_account(txn.get("account_id"))
        total_fee = float(txn.get("customer_fee", 0) or 0)
        commission = float(txn.get("commission_amount", 0) or 0)

        items = [
            format_datetime(txn.get("created_at", "")),
            acc.get("account_name", "") if acc else str(txn.get("account_id", "")),
            txn.get("customer_name", "") or "-",
            txn.get("customer_phone", "") or "-",
            f"{float(txn.get('amount', 0) or 0):,.0f}",
            f"{commission:,.0f}",
            f"{total_fee:,.0f}",
        ]
        left_cols = {1, 2, 3}
        right_cols = {4, 5, 6}

        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            if col in left_cols:
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            elif col in right_cols:
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setToolTip(text)
            self._txn_table.setItem(row, col, item)
