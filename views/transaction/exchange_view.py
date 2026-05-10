from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QGridLayout, QTableWidgetItem

from i18n import t
from views.transaction.base_form_view import BaseFormView
from views.transaction_view import (
    field_label,
    format_datetime,
)
from views.widgets.company_selector import add_placeholder


class ExchangeView(BaseFormView):
    transaction_type = "exchange"

    _TXN_HEADERS = ["Time", "Account", "Currency", "Rate", "Amount", "Fee"]
    _TXN_COL_WIDTHS = [170, 0, 80, 120, 130, 120]
    _TXN_STRETCH: set = {1}

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

        # Row 0 — Account + balance hint (left 8) | Currency (right 4)
        grid.addWidget(
            self._make_account_cell_with_balance(t("field_account"), required=True),
            0, 0, 1, 4,
        )

        currency_label = field_label(t("field_currency"), required=True)
        self._currency_combo = QComboBox()
        add_placeholder(self._currency_combo)
        self._currency_combo.addItems(["MMK", "THB"])
        grid.addWidget(self._gcell(currency_label, self._currency_combo), 0, 4, 1, 4)

        # Row 1 — Amount (right 4)
        amount_label = field_label(t("field_amount"), required=True)
        grid.addWidget(self._gcell(amount_label, self._make_amount_input()), 0, 8, 1, 4)

        lo.addLayout(grid)
        lo.addLayout(self._make_fee_grid())
        self._make_note_screenshot(lo)

    # ── Table ────────────────────────────────────────────────────────────────

    def _set_txn_row(self, row: int, txn: dict) -> None:
        acc = self._find_account(txn.get("account_id"))
        total_fee = float(txn.get("customer_fee", 0) or 0)
        rate = float(txn.get("exchange_rate", 0) or 0)

        items = [
            format_datetime(txn.get("created_at", "")),
            acc.get("account_name", "") if acc else str(txn.get("account_id", "")),
            str(txn.get("currency", "") or "-"),
            f"{rate:,.4f}",
            f"{float(txn.get('amount', 0) or 0):,.0f}",
            f"{total_fee:,.0f}",
        ]
        left_cols = {1}
        right_cols = {3, 4, 5}
        center_cols = {0, 2}

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
