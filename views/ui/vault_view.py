from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,

    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from repositories.vault_repository import VaultRepository
from services.api_client import ApiClient
from views.receive_float_dialog import ReceiveFloatDialog
from views.widgets.denomination_input import DenominationInputWidget
from views.transaction_view import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_RED,
    ACCENT_YELLOW,
    BG_CARD,
    BG_DARK,
    BG_INPUT,
    BORDER_COLOR,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

DENOMINATIONS = [50, 100, 200, 500, 1000, 5000, 10000, 20000]
INPUT_BORDER = "#585b70"


def _accent_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color}; color: {BG_DARK}; "
        f"border: none; border-radius: 6px; padding: 8px 18px; "
        f"font-size: 13px; font-weight: bold; }}"
        f"QPushButton:disabled {{ background-color: #585b70; color: #6c7086; }}"
    )
    return btn


def _cell(text: str, align=Qt.AlignmentFlag.AlignLeft) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text))
    item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    return item


def _compact_action_btn(text: str, color: str) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color}; color: {BG_DARK}; "
        f"border: none; border-radius: 4px; padding: 4px 10px; "
        f"font-size: 11px; font-weight: bold; }}"
        f"QPushButton:hover {{ background-color: {color}; }}"
        f"QPushButton:disabled {{ background-color: #585b70; color: #6c7086; }}"
    )
    return btn


class ReturnCashDialog(QDialog):
    def __init__(self, repo: VaultRepository, float_data: dict, balance: dict, parent=None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._float_data = float_data
        self._balance = balance.get("denominations", {}) or {}
        self._spinboxes: dict[int, QSpinBox] = {}
        self._total_label: Optional[QLabel] = None
        self._pin_input: Optional[QLineEdit] = None
        self._error_label: Optional[QLabel] = None
        self._note_input: Optional[QLineEdit] = None
        self.denominations: dict[str, int] = {}
        self.pin: str = ""
        self.note: Optional[str] = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("Return Cash to Cashier")
        self.setFixedWidth(480)
        self.setStyleSheet(
            f"QDialog {{ background-color: {BG_DARK}; }}"
            f"QWidget {{ color: {TEXT_PRIMARY}; background-color: {BG_DARK}; }}"
            f"QLineEdit, QSpinBox {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 6px; padding: 8px 12px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Return Cash")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {ACCENT_BLUE};")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(QLabel(t("col_denomination")), 0, 0)
        grid.addWidget(QLabel(t("col_quantity")), 0, 1)
        grid.addWidget(QLabel(t("col_value")), 0, 2)
        for i, denom in enumerate(DENOMINATIONS):
            available = int(self._balance.get(str(denom), 0) or 0)
            row = i + 1
            grid.addWidget(QLabel(f"{denom:,} MMK"), row, 0)
            spin = QSpinBox()
            spin.setRange(0, available)
            spin.setValue(available)
            spin.setFixedWidth(130)
            self._spinboxes[denom] = spin
            value = QLabel(f"{denom * available:,}")
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            spin.valueChanged.connect(
                lambda v, d=denom, lbl=value: (lbl.setText(f"{d * v:,}"), self._update_total())
            )
            grid.addWidget(spin, row, 1)
            grid.addWidget(value, row, 2)
        layout.addLayout(grid)

        total_row = QHBoxLayout()
        total_row.addWidget(QLabel("Total Return"))
        total_row.addStretch()
        self._total_label = QLabel("0 MMK")
        self._total_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._total_label.setStyleSheet(f"color: {ACCENT_GREEN};")
        total_row.addWidget(self._total_label)
        layout.addLayout(total_row)

        self._note_input = QLineEdit()
        self._note_input.setPlaceholderText(t("note_optional"))
        layout.addWidget(self._note_input)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"border: 1px solid {BORDER_COLOR};")
        layout.addWidget(sep)

        pin_lbl = QLabel("PIN")
        pin_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px;")
        layout.addWidget(pin_lbl)
        self._pin_input = QLineEdit()
        self._pin_input.setPlaceholderText("••••••")
        self._pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin_input.setMaxLength(6)
        layout.addWidget(self._pin_input)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        row = QHBoxLayout()
        cancel = _accent_btn(t("cancel"), TEXT_MUTED)
        cancel.clicked.connect(self.reject)
        submit = _accent_btn("Return to Cashier", ACCENT_GREEN)
        submit.clicked.connect(self._on_submit)
        row.addWidget(cancel)
        row.addStretch()
        row.addWidget(submit)
        layout.addLayout(row)
        self._update_total()

    def _update_total(self) -> None:
        total = sum(d * spin.value() for d, spin in self._spinboxes.items())
        if self._total_label:
            self._total_label.setText(f"{total:,} MMK")

    def _on_submit(self) -> None:
        denoms = {str(d): spin.value() for d, spin in self._spinboxes.items()}
        if sum(int(d) * q for d, q in denoms.items()) <= 0:
            QMessageBox.warning(self, t("error"), t("total_nonzero"))
            return
        pin = self._pin_input.text().strip() if self._pin_input else ""
        if len(pin) != 6 or not pin.isdigit():
            if self._error_label:
                self._error_label.setText(t("pin_invalid"))
                self._error_label.setVisible(True)
            return
        self.denominations = denoms
        self.pin = pin
        self.note = self._note_input.text().strip() if self._note_input else None
        self.accept()


class ConfirmReturnDialog(QDialog):
    """Cashier confirms employee float return — shows denomination breakdown + PIN."""

    def __init__(self, float_data: dict, balance_data: dict, parent=None) -> None:
        super().__init__(parent)
        self._float_data = float_data
        self._balance = balance_data.get("denominations", {}) or {}
        self._total = int(balance_data.get("total", 0) or 0)
        self.pin: str = ""
        self._pin_input: Optional[QLineEdit] = None
        self._error_label: Optional[QLabel] = None
        self._init_ui()

    def _init_ui(self) -> None:
        float_id = self._float_data.get("id", "?")
        employee = self._float_data.get("employee_name", "?")
        self.setWindowTitle(f"Confirm Return — Float #{float_id}")
        self.setFixedWidth(480)
        self.setStyleSheet(
            f"QDialog {{ background-color: {BG_DARK}; }}"
            f"QWidget {{ color: {TEXT_PRIMARY}; background-color: {BG_DARK}; }}"
            f"QLabel {{ background-color: transparent; }}"
            f"QTableWidget {{ background-color: {BG_CARD}; border: 1px solid {BORDER_COLOR}; "
            f"border-radius: 6px; gridline-color: {BORDER_COLOR}; font-size: 12px; }}"
            f"QTableWidget::item {{ padding: 6px; background-color: transparent; }}"
            f"QHeaderView::section {{ background-color: {BG_DARK}; color: {TEXT_SECONDARY}; "
            f"border: none; padding: 6px; font-weight: bold; }}"
            f"QLineEdit {{ background-color: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 6px; padding: 8px 12px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("Confirm Cash Return")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {ACCENT_BLUE};")
        layout.addWidget(title)

        info = QLabel(f"Employee: {employee}  |  Float #{float_id}")
        info.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(info)

        active = sorted(
            [(int(k), int(v)) for k, v in self._balance.items() if int(v) > 0],
            key=lambda x: x[0],
            reverse=True,
        )
        if active:
            table = QTableWidget(len(active), 3)
            table.setHorizontalHeaderLabels([t("col_denomination"), t("col_quantity"), t("col_value")])
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
            table.verticalHeader().setVisible(False)
            table.setMaximumHeight(min(220, 40 + len(active) * 32))
            hdr = table.horizontalHeader()
            hdr.setStretchLastSection(True)
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            for row_idx, (denom, qty) in enumerate(active):
                d_item = QTableWidgetItem(f"{denom:,} MMK")
                d_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                q_item = QTableWidgetItem(str(qty))
                q_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                v_item = QTableWidgetItem(f"{denom * qty:,}")
                v_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row_idx, 0, d_item)
                table.setItem(row_idx, 1, q_item)
                table.setItem(row_idx, 2, v_item)
            layout.addWidget(table)

        total_row = QHBoxLayout()
        total_row.addWidget(QLabel("Total Return"))
        total_row.addStretch()
        total_lbl = QLabel(f"{self._total:,} MMK")
        total_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        total_lbl.setStyleSheet(f"color: {ACCENT_GREEN};")
        total_row.addWidget(total_lbl)
        layout.addLayout(total_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"border: 1px solid {BORDER_COLOR};")
        layout.addWidget(sep)

        pin_lbl = QLabel("Cashier PIN")
        pin_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px;")
        layout.addWidget(pin_lbl)
        self._pin_input = QLineEdit()
        self._pin_input.setPlaceholderText("••••••")
        self._pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin_input.setMaxLength(6)
        self._pin_input.returnPressed.connect(self._on_confirm)
        layout.addWidget(self._pin_input)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        btn_row = QHBoxLayout()
        cancel = _accent_btn(t("cancel"), TEXT_MUTED)
        cancel.clicked.connect(self.reject)
        confirm = _accent_btn("Confirm Return", ACCENT_BLUE)
        confirm.clicked.connect(self._on_confirm)
        btn_row.addWidget(cancel)
        btn_row.addStretch()
        btn_row.addWidget(confirm)
        layout.addLayout(btn_row)
        self._pin_input.setFocus()

    def _on_confirm(self) -> None:
        pin = self._pin_input.text().strip() if self._pin_input else ""
        if len(pin) != 6 or not pin.isdigit():
            if self._error_label:
                self._error_label.setText(t("pin_invalid"))
                self._error_label.setVisible(True)
            return
        self.pin = pin
        self.accept()


class VaultPage(QWidget):
    def __init__(self, api: ApiClient, go_back=None) -> None:
        super().__init__()
        self._repo = VaultRepository(api)
        self._go_back = go_back
        self._denom_cards: dict[int, tuple[QLabel, QLabel]] = {}
        self._total_label: Optional[QLabel] = None
        self._title_label: Optional[QLabel] = None
        self._denom_title_label: Optional[QLabel] = None
        self._helper_label: Optional[QLabel] = None
        self._history_table: Optional[QTableWidget] = None
        self._active_float: Optional[dict] = None
        self._pending_float: Optional[dict] = None
        self._pending_reconciliation_float: Optional[dict] = None
        self._init_ui()

    def _init_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root = QWidget()
        root.setStyleSheet(f"background-color: {BG_DARK};")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)
        scroll.setWidget(root)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        top = QHBoxLayout()
        self._title_label = QLabel(self._vault_label())
        self._title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._title_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        top.addWidget(self._title_label)
        top.addStretch()
        refresh = _accent_btn(t("refresh"), ACCENT_BLUE)
        refresh.clicked.connect(self.load_data)
        receive = _accent_btn("Receive Float", ACCENT_GREEN)
        receive.clicked.connect(self._receive_float)
        return_btn = _accent_btn("Return Cash", ACCENT_YELLOW)
        return_btn.clicked.connect(self._return_cash)
        top.addWidget(refresh)
        top.addWidget(receive)
        top.addWidget(return_btn)
        if self._go_back:
            back = _accent_btn("Back", ACCENT_BLUE)
            back.clicked.connect(self._go_back)
            top.addWidget(back)
        layout.addLayout(top)

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; border: 1px solid {BORDER_COLOR}; }}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        self._denom_title_label = QLabel(f"{self._vault_label()} Denomination Balances")
        cl.addWidget(self._denom_title_label)
        grid = QGridLayout()
        grid.setSpacing(10)
        for col, denom in enumerate(reversed(DENOMINATIONS)):
            dcard = QFrame()
            dcard.setStyleSheet(
                f"QFrame {{ background-color: {BG_DARK}; border-radius: 8px; border: 1px solid {BORDER_COLOR}; }}"
            )
            dl = QVBoxLayout(dcard)
            denom_label = QLabel(f"{denom:,}")
            denom_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            denom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            denom_label.setStyleSheet(f"color: {ACCENT_BLUE}; border: none;")
            qty_label = QLabel("0 pcs")
            qty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            qty_label.setStyleSheet(f"border: none; color: {TEXT_PRIMARY};")
            value_label = QLabel("0 MMK")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet(f"border: none; color: {TEXT_SECONDARY};")
            dl.addWidget(denom_label)
            dl.addWidget(qty_label)
            dl.addWidget(value_label)
            self._denom_cards[denom] = (qty_label, value_label)
            grid.addWidget(dcard, 0, col)
        cl.addLayout(grid)
        total_row = QHBoxLayout()
        total_row.addWidget(QLabel("Total Cash:"))
        total_row.addStretch()
        self._total_label = QLabel("0 MMK")
        self._total_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._total_label.setStyleSheet(f"color: {ACCENT_GREEN};")
        total_row.addWidget(self._total_label)
        cl.addLayout(total_row)
        self._helper_label = QLabel(self._vault_helper())
        self._helper_label.setStyleSheet(f"color: {TEXT_SECONDARY}; border: none; font-size: 12px;")
        cl.addWidget(self._helper_label)
        layout.addWidget(card)

        hist = QLabel("Vault History")
        hist.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(hist)
        self._history_table = QTableWidget(0, 8)
        self._history_table.setHorizontalHeaderLabels(
            ["Date / Time", "Source", "Type", "Amount", "Status", "Reference", "Note", "Action"]
        )
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._history_table.horizontalHeader().setStretchLastSection(True)
        self._history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._history_table.setMinimumHeight(260)
        layout.addWidget(self._history_table)
        layout.addStretch()

    def load_data(self) -> None:
        try:
            if self._title_label:
                self._title_label.setText(self._vault_label())
            if self._denom_title_label:
                self._denom_title_label.setText(f"{self._vault_label()} Denomination Balances")
            if self._helper_label:
                self._helper_label.setText(self._vault_helper())
            history = self._repo.fetch_vault_history()
            floats = history.get("floats", [])
            self._active_float = self._repo.get_active_float()
            self._pending_float = self._repo.get_pending_float()
            self._pending_reconciliation_float = self._repo.get_pending_reconciliation_float()
            transactions = history.get("transactions", [])
            self._populate_denominations()
            self._populate_history(floats, transactions)
        except Exception as exc:
            QMessageBox.warning(self, t("error"), str(exc))

    def _populate_denominations(self) -> None:
        balance = {}
        total = 0
        if self._is_cashier():
            data = self._repo.api.get_vault()
            balance = data.get("denominations", {}) or {}
            total = int(data.get("total", 0) or 0)
        elif self._active_float:
            data = self._repo.get_float_balance(self._active_float["id"])
            balance = data.get("denominations", {}) or {}
            total = int(data.get("total", 0) or 0)
        for denom, (qty_label, value_label) in self._denom_cards.items():
            qty = int(balance.get(str(denom), 0) or 0)
            qty_label.setText(f"{qty} pcs")
            value_label.setText(f"{denom * qty:,} MMK")
        if self._total_label:
            self._total_label.setText(f"{total:,} MMK")

    def _is_cashier(self) -> bool:
        return ((self._repo.api.user or {}).get("role") or "").lower() == "cashier"

    def _vault_label(self) -> str:
        return "Main Vault" if self._is_cashier() else "Mini Vault"

    def _vault_helper(self) -> str:
        if self._is_cashier():
            return "Main Vault reflects float issues, returns, and completed Cash In handovers."
        return "Mini Vault is used for Cash Out only; Cash In is handed to the Cashier."

    def _populate_history(self, floats: list[dict], transactions: list[dict]) -> None:
        if self._history_table is None:
            return
        self._history_table.setRowCount(0)
        rows = self._build_float_history_rows(floats)
        rows.extend(self._build_transaction_history_rows(transactions))
        rows.sort(key=lambda r: r["sort_key"], reverse=True)
        for item in rows:
            values = item["values"]
            row = self._history_table.rowCount()
            self._history_table.insertRow(row)
            for col, value in enumerate(values):
                align = Qt.AlignmentFlag.AlignRight if col == 3 else Qt.AlignmentFlag.AlignLeft
                self._history_table.setItem(row, col, _cell(value, align))
            self._set_history_action(row, item)

    def _history_row(
        self,
        values: list[str],
        *,
        sort_key: str,
        row_type: str = "",
        status: str = "",
        float_data: Optional[dict] = None,
    ) -> dict:
        return {
            "values": values,
            "sort_key": sort_key,
            "row_type": row_type,
            "status": status,
            "float": float_data,
        }

    def _build_float_history_rows(self, floats: list[dict]) -> list[dict]:
        rows: list[dict] = []
        for f in floats:
            total = float(f.get("total_amount") or 0)
            current = float(f.get("current_balance") or 0)
            ref = f"Float #{f.get('id', '')}"
            note = f.get("note") or ""
            created = str(f.get("created_at", "") or "")
            received = str(f.get("received_at", "") or "")
            closed = str(f.get("closed_at", "") or "")
            status = f.get("status", "")
            if created:
                rows.append(self._history_row(
                    [
                        created[:16],
                        "Float",
                        "Issued",
                        f"{total:,.0f}",
                        status,
                        ref,
                        f"Issued by {f.get('issued_by_name') or ''}".strip(),
                    ],
                    sort_key=created,
                    row_type="float",
                    status=status,
                    float_data=f,
                ))
            if received:
                rows.append(self._history_row(
                    [
                        received[:16],
                        "Float",
                        "Received",
                        f"+{total:,.0f}",
                        status,
                        ref,
                        note,
                    ],
                    sort_key=received,
                    row_type="float",
                    status=status,
                    float_data=f,
                ))
            if status == "PENDING_RECONCILIATION":
                return_time = closed or received or created
                rows.append(self._history_row(
                    [
                        return_time[:16],
                        "Float",
                        "Return Requested",
                        f"-{current:,.0f}",
                        "RETURN_REQUESTED",
                        ref,
                        note,
                    ],
                    sort_key=return_time,
                    row_type="float",
                    status="RETURN_REQUESTED",
                    float_data=f,
                ))
            if closed:
                rows.append(self._history_row(
                    [
                        closed[:16],
                        "Float",
                        "Returned",
                        f"-{float(f.get('closing_total') or current):,.0f}",
                        "COMPLETED",
                        ref,
                        note,
                    ],
                    sort_key=closed,
                    row_type="float",
                    status="COMPLETED",
                    float_data=f,
                ))
        return rows

    def _build_transaction_history_rows(self, transactions: list[dict]) -> list[dict]:
        rows: list[dict] = []
        labels = {
            "cash_in": "Cash In",
            "cash_out": "Cash Out",
            "transfer": "Transfer",
            "exchange": "Exchange",
        }
        for txn in transactions:
            txn_type = (txn.get("transaction_type") or txn.get("txn_type") or "").lower()
            amount = float(txn.get("amount") or 0)
            if txn_type == "cash_in":
                signed_amount = f"+{amount:,.0f}"
                status = "Vault Increased"
            else:
                signed_amount = f"-{amount:,.0f}"
                status = "Vault Decreased"
            created = str(txn.get("created_at", "") or "")
            rows.append(self._history_row(
                [
                    created[:16],
                    "Transaction",
                    labels.get(txn_type, txn_type.title()),
                    signed_amount,
                    status,
                    f"Txn #{txn.get('id', '')}",
                    txn.get("note") or txn.get("customer_name") or "",
                ],
                sort_key=created,
                row_type="transaction",
                status=status,
            ))
        return rows

    def _set_history_action(self, row: int, item: dict) -> None:
        if self._history_table is None:
            return
        status = item.get("status", "")
        float_data = item.get("float") or {}
        role = (self._repo.api.user or {}).get("role")
        btn = None
        if status == "PENDING_RECEIPT":
            btn = _compact_action_btn("Receive", ACCENT_GREEN)
            btn.clicked.connect(lambda _, fd=dict(float_data): self._receive_float_row(fd))
        elif status == "RETURN_REQUESTED" and role == "cashier":
            btn = _compact_action_btn("Confirm Return", ACCENT_BLUE)
            btn.clicked.connect(lambda _, fd=dict(float_data): self._confirm_return_row(fd))
        if btn is None:
            self._history_table.setItem(row, 7, _cell("", Qt.AlignmentFlag.AlignCenter))
            return
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)
        layout.addWidget(btn)
        layout.addStretch()
        self._history_table.setCellWidget(row, 7, wrapper)

    def _open_receive_dialog(self, float_data: dict) -> None:
        float_id = float_data.get("id")
        if float_id is None:
            QMessageBox.warning(self, t("error"), "Float ID not found.")
            return
        try:
            detail = self._repo.api.get_float(int(float_id))
        except Exception:
            detail = float_data
        dlg = ReceiveFloatDialog(
            self._repo.api,
            detail,
            parent=self,
            confirm_callback=lambda pin, fid: self._repo.confirm_receipt(fid, pin),
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def _receive_float_row(self, float_data: dict) -> None:
        self._open_receive_dialog(float_data)

    def _confirm_return_row(self, float_data: dict) -> None:
        float_id = float_data.get("id")
        if float_id is None:
            QMessageBox.warning(self, t("error"), "Float ID not found.")
            return
        try:
            balance_data = self._repo.get_float_balance(int(float_id))
        except Exception:
            balance_data = {}
        dlg = ConfirmReturnDialog(float_data, balance_data, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._repo.api.confirm_float_return(int(float_id), dlg.pin)
            self.load_data()
        except Exception as exc:
            QMessageBox.warning(self, t("error"), str(exc))

    def _receive_float(self) -> None:
        if self._pending_reconciliation_float:
            QMessageBox.information(
                self,
                "Receive Float",
                "A returned float is pending cashier reconciliation. Please wait for cashier confirmation.",
            )
            return
        if not self._pending_float:
            QMessageBox.information(self, "Receive Float", "No pending float to receive.")
            return
        self._open_receive_dialog(self._pending_float)

    def _return_cash(self) -> None:
        if not self._active_float:
            QMessageBox.information(self, "Return Cash", "No active vault cash to return.")
            return
        balance = self._repo.get_float_balance(self._active_float["id"])
        dlg = ReturnCashDialog(self._repo, self._active_float, balance, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        pin, ok = QInputDialog.getText(
            self,
            "Return Cash",
            "Enter PIN to request cash return:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        pin = pin.strip()
        if len(pin) != 6 or not pin.isdigit():
            QMessageBox.warning(self, t("error"), t("pin_invalid"))
            return
        try:
            self._repo.return_cash(self._active_float["id"], pin, dlg.denominations, note=dlg.note)
            QMessageBox.information(self, "Return Cash", "Return request sent to cashier.")
            self.load_data()
        except Exception as exc:
            QMessageBox.warning(self, t("error"), str(exc))

class VaultView(QMainWindow):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self.setWindowTitle("Vault")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(f"QMainWindow {{ background-color: {BG_DARK}; }} QWidget {{ color: {TEXT_PRIMARY}; }}")
        self._page = VaultPage(self._api, self._go_dashboard)
        self.setCentralWidget(self._page)
        self._page.load_data()

    def _go_dashboard(self) -> None:
        from views.dashboard_view import DashboardView
        self._dashboard = DashboardView(self._api)
        self._dashboard.show()
        self.close()
