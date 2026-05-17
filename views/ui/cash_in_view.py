from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QLineEdit, QGridLayout, QTableWidgetItem, QWidget

from i18n import t
from views.ui.base_form_view import BaseFormView
from views.transaction_view import (
    ACCENT_GREEN,
    ACCENT_RED,
    TEXT_MUTED,
    TYPE_COLORS,
    field_label,
    format_datetime,
)
from views.widgets.company_selector import ServiceTypeSelector, add_placeholder
from views.widgets.denomination_input import DenominationInputWidget


class CashInView(BaseFormView):
    transaction_type = "cash_in"

    _TXN_HEADERS = ["Time", "Account", "Customer", "Phone", "Amount", "Fee / Commission", "Fee Account"]
    _TXN_COL_WIDTHS = [170, 0, 0, 130, 120, 150, 140]
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
        from PyQt6.QtWidgets import QLineEdit

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
        lo.addWidget(field_label("Overpayment Change"))
        overpay_grid = QGridLayout()
        overpay_grid.setContentsMargins(0, 0, 0, 0)
        overpay_grid.setHorizontalSpacing(12)
        overpay_grid.setVerticalSpacing(10)
        for col in range(12):
            overpay_grid.setColumnStretch(col, 1)

        self._amount_received_input = QLineEdit()
        self._amount_received_input.setPlaceholderText("0")
        self._amount_received_input.textChanged.connect(self._update_overpayment_hint)
        overpay_grid.addWidget(
            self._gcell(field_label("Amount Received"), self._amount_received_input),
            0, 0, 1, 4,
        )

        self._overpayment_hint = QLabel("No overpayment change")
        self._overpayment_hint.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px;")
        overpay_grid.addWidget(self._overpayment_hint, 0, 4, 1, 8)

        denoms = self._load_denominations()
        self._change_breakdown = DenominationInputWidget(
            denoms,
            title="Change from employee float",
        )
        self._change_breakdown.setEnabled(False)
        self._change_breakdown.total_changed.connect(lambda _total: self._update_overpayment_hint())
        overpay_grid.addWidget(self._change_breakdown, 1, 0, 1, 12)
        lo.addLayout(overpay_grid)
        self._make_note_screenshot(lo)

    def _load_denominations(self) -> list[int]:
        try:
            rows = self._repository.get_denominations()
            values = [
                int(row.get("value", row.get("id")))
                for row in rows
                if int(row.get("is_active", 1) or 0) == 1
            ]
            return sorted(values, reverse=True) or [20000, 10000, 5000, 1000, 500, 200, 100, 50]
        except Exception:
            return [20000, 10000, 5000, 1000, 500, 200, 100, 50]

    def _parse_amount_received(self) -> float:
        try:
            return float(self._amount_received_input.text().replace(",", ""))
        except (AttributeError, ValueError):
            return 0.0

    def _on_amount_changed(self) -> None:
        super()._on_amount_changed()
        self._update_overpayment_hint()

    def _update_overpayment_hint(self) -> None:
        amount = self._parse_amount()
        received = self._parse_amount_received()

        if received <= 0:
            text = "No overpayment change"
            color = TEXT_MUTED
            self._set_change_breakdown_enabled(False)
        elif received < amount:
            text = "Amount received must be greater than or equal to Cash In amount."
            color = ACCENT_RED
            self._set_change_breakdown_enabled(False)
        elif received == amount:
            text = "No overpayment change"
            color = TEXT_MUTED
            self._set_change_breakdown_enabled(False)
        else:
            self._set_change_breakdown_enabled(True)
            change_due = received - amount
            change_total = self._change_breakdown.total()
            text = (
                f"Cash change due: {change_due:,.0f} MMK | "
                f"Breakdown: {change_total:,.0f} | "
                f"Digital account change: {-amount:,.0f}"
            )
            color = ACCENT_GREEN if change_due == change_total else ACCENT_RED
        self._overpayment_hint.setText(text)
        self._overpayment_hint.setStyleSheet(f"color: {color}; font-size: 12px;")

    def _set_change_breakdown_enabled(self, enabled: bool) -> None:
        if not hasattr(self, "_change_breakdown"):
            return
        if not enabled and self._change_breakdown.total() != 0:
            self._change_breakdown.clear()
        self._change_breakdown.setEnabled(enabled)

    def _cash_in_overpayment_payload(self) -> dict:
        received = self._parse_amount_received()
        amount = self._parse_amount()
        if received <= amount:
            return {}
        return {
            "amount_received": received,
            "change_breakdown": self._change_breakdown.breakdown(),
        }

    def _validate_cash_in_overpayment(self) -> str | None:
        amount = self._parse_amount()
        received = self._parse_amount_received()
        if received <= 0:
            return None
        if received < amount:
            return "Amount received must be greater than or equal to Cash In amount."
        if received == amount:
            return None
        change_due = received - amount
        if self._change_breakdown.total() != int(change_due):
            return "Change breakdown total must match overpayment change due."
        return None

    def _clear_cash_in_overpayment(self) -> None:
        if hasattr(self, "_amount_received_input"):
            self._amount_received_input.clear()
        if hasattr(self, "_change_breakdown"):
            self._change_breakdown.clear()
        if hasattr(self, "_overpayment_hint"):
            self._update_overpayment_hint()

    # ── Table ────────────────────────────────────────────────────────────────

    def _set_txn_row(self, row: int, txn: dict) -> None:
        acc = self._find_account(txn.get("account_id"))
        fee_acc = self._find_account(txn.get("fee_account_id"))
        total_fee = float(txn.get("customer_fee", 0) or 0)
        commission = float(txn.get("commission_amount", 0) or 0)

        items = [
            format_datetime(txn.get("created_at", "")),
            acc.get("account_name", "") if acc else str(txn.get("account_id", "")),
            txn.get("customer_name", "") or "-",
            txn.get("customer_phone", "") or "-",
            f"{float(txn.get('amount', 0) or 0):,.0f}",
            f"{total_fee:,.0f} / {commission:,.0f}",
            fee_acc.get("account_name", "") if fee_acc else "-",
        ]
        left_cols = {1, 2, 3, 6}
        right_cols = {4, 5}

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
