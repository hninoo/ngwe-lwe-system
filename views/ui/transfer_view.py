from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QTableWidgetItem, QVBoxLayout, QWidget

from i18n import t
from views.ui.base_form_view import BaseFormView
from views.transaction_view import (
    ACCENT_BLUE,
    BG_CARD,
    BORDER_COLOR,
    TEXT_SECONDARY,
    CompanyGridSelector,
    field_label,
    format_datetime,
)
from views.widgets.company_selector import AccountSelector, add_placeholder


class TransferView(BaseFormView):
    transaction_type = "transfer"

    _TXN_HEADERS = ["Time", "From Account", "To Account", "Amount", "Fee"]
    _TXN_COL_WIDTHS = [170, 0, 0, 130, 120]
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
        # ── FROM side ──────────────────────────────────────────────────────
        from_section = QLabel("From")
        from_section.setStyleSheet(f"color: {ACCENT_BLUE}; font-size: 12px; font-weight: bold;")
        lo.addWidget(from_section)

        # Account + balance hint (full width) and Amount side-by-side in a grid
        top_grid = QGridLayout()
        top_grid.setContentsMargins(0, 0, 0, 0)
        top_grid.setHorizontalSpacing(12)
        top_grid.setVerticalSpacing(10)
        for col in range(12):
            top_grid.setColumnStretch(col, 1)

        top_grid.addWidget(
            self._make_account_cell_with_balance(t("field_account"), required=True),
            0, 0, 1, 6,
        )

        amount_label = field_label(t("field_amount"), required=True)
        top_grid.addWidget(self._gcell(amount_label, self._make_amount_input()), 0, 6, 1, 6)

        lo.addLayout(top_grid)

        # ── TO side ────────────────────────────────────────────────────────
        to_section = QLabel("To")
        to_section.setStyleSheet(f"color: {ACCENT_BLUE}; font-size: 12px; font-weight: bold;")
        lo.addWidget(to_section)

        to_company_label = field_label(t("field_to_company"), required=True)
        lo.addWidget(to_company_label)
        self._to_company_selector = CompanyGridSelector()
        self._to_company_selector.company_changed.connect(self._on_to_company_changed)
        lo.addWidget(self._to_company_selector)

        to_account_label = field_label(t("field_to_account"), required=True)
        self._to_account_selector = AccountSelector()
        lo.addWidget(self._gcell(to_account_label, self._to_account_selector))

        # ── Fees ───────────────────────────────────────────────────────────
        lo.addLayout(self._make_fee_grid())
        self._make_note_screenshot(lo)

    # ── Table ────────────────────────────────────────────────────────────────

    def _set_txn_row(self, row: int, txn: dict) -> None:
        acc = self._find_account(txn.get("account_id"))
        to_acc = self._find_account(txn.get("to_account_id"))
        total_fee = float(txn.get("customer_fee", 0) or 0)

        items = [
            format_datetime(txn.get("created_at", "")),
            acc.get("account_name", "") if acc else str(txn.get("account_id", "")),
            to_acc.get("account_name", "") if to_acc else str(txn.get("to_account_id", "")),
            f"{float(txn.get('amount', 0) or 0):,.0f}",
            f"{total_fee:,.0f}",
        ]
        left_cols = {1, 2}
        right_cols = {3, 4}

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
