from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QLineEdit, QTableWidgetItem

from i18n import t
from views.transaction.base_form_view import BaseFormView
from views.transaction_view import (
    ACCENT_GREEN,
    ACCENT_RED,
    field_label,
    format_datetime,
)
from views.widgets.company_selector import ServiceTypeSelector


class CashOutView(BaseFormView):
    transaction_type = "cash_out"

    _TXN_HEADERS = ["Time", "Account", "Customer", "Phone", "Amount", "Commission", "Total Fee"]
    _TXN_COL_WIDTHS = [170, 0, 0, 130, 120, 120, 120]
    _TXN_STRETCH: set = {1, 2}

    def __init__(self, api, navigate, repository=None) -> None:
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
        self._make_note_screenshot(lo)

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
