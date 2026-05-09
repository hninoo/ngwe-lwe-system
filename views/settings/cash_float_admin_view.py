"""
views/settings/cash_float_admin_view.py

Owner-only read-only view for cash_float_assignments and denomination logs.
"""
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from services.api_client import ApiClient

BG_DARK = "#1e1e2e"
BG_CARD = "#2a2a3e"
BG_INPUT = "#313244"
TEXT_PRIMARY = "#cdd6f4"
TEXT_SECONDARY = "#a6adc8"
ACCENT_BLUE = "#89b4fa"
ACCENT_GREEN = "#a6e3a1"
ACCENT_RED = "#f38ba8"
ACCENT_YELLOW = "#f9e2af"
ACCENT_MAUVE = "#cba6f7"
BORDER_COLOR = "#313244"
INPUT_BORDER = "#585b70"

STATUS_COLORS = {
    "PENDING": ACCENT_YELLOW,          # legacy — maps to PENDING_RECEIPT after migration
    "PENDING_RECEIPT": ACCENT_YELLOW,
    "ACTIVE": ACCENT_GREEN,
    "PENDING_RECONCILIATION": ACCENT_MAUVE,
    "CLOSED": TEXT_SECONDARY,
}


def _ghost_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; color: {color}; border: 1px solid {color}; "
        f"border-radius: 4px; padding: 3px 8px; font-size: 11px; }}"
        f"QPushButton:hover {{ background-color: {BG_INPUT}; }}"
    )
    return btn


class _FloatDetailDialog(QDialog):
    """Shows denomination breakdown for a cash float."""

    def __init__(self, float_data: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{t('float_detail')} — ID {float_data.get('id')}")
        self.setMinimumWidth(380)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_PRIMARY};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)

        # Summary info
        for label, value in [
            (t("col_employee"), str(float_data.get("employee_id", ""))),
            (t("float_status"), float_data.get("status", "")),
            (t("float_total"), f"{float(float_data.get('total_amount', 0)):,.0f} MMK"),
            (t("float_closing"), f"{float(float_data.get('closing_total') or 0):,.0f} MMK"),
            (t("col_note"), float_data.get("note") or "—"),
        ]:
            row = QHBoxLayout()
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
            lbl.setFixedWidth(120)
            val = QLabel(str(value))
            val.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 12px;")
            row.addWidget(lbl)
            row.addWidget(val)
            row.addStretch()
            layout.addLayout(row)

        layout.addSpacing(8)

        # Denominations table
        denoms = float_data.get("denominations", [])
        denom_label = QLabel(t("float_denominations"))
        denom_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; font-weight: bold;")
        layout.addWidget(denom_label)

        if denoms:
            dtbl = QTableWidget(len(denoms), 3)
            dtbl.setHorizontalHeaderLabels([t("col_denomination"), t("col_quantity"), t("col_subtotal")])
            dtbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            dtbl.verticalHeader().setVisible(False)
            dtbl.setStyleSheet(
                f"QTableWidget {{ background: {BG_CARD}; border: none; font-size: 12px; }}"
                f"QHeaderView::section {{ background: {BG_DARK}; color: {TEXT_SECONDARY}; "
                f"border: none; padding: 4px; }}"
            )
            dtbl.horizontalHeader().setStretchLastSection(True)
            for r, d in enumerate(denoms):
                denom_val = d.get("denomination", 0)
                qty = d.get("quantity", 0)
                subtotal = denom_val * qty
                for c, text in enumerate([f"{denom_val:,}", str(qty), f"{subtotal:,}"]):
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    dtbl.setItem(r, c, item)
            layout.addWidget(dtbl)
        else:
            layout.addWidget(QLabel(t("no_denomination_data")))

        close_btn = QPushButton(t("close"))
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 6px 14px; }}"
        )
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


class CashFloatAdminView(QWidget):
    """Cashier/owner panel for cash float assignments."""

    COLS = [
        "id", t("col_employee"), t("float_issued_by"),
        t("float_status"), t("float_total"), t("col_created"),
        t("float_received"), t("float_closed"), t("col_note"), t("col_actions"),
    ]
    COL_ID = 0
    COL_EMPLOYEE = 1
    COL_ISSUED = 2
    COL_STATUS = 3
    COL_TOTAL = 4
    COL_CREATED = 5
    COL_RECEIVED = 6
    COL_CLOSED = 7
    COL_NOTE = 8
    COL_ACTIONS = 9

    def __init__(self, api: ApiClient, role: str = "owner", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._api = api
        self._role = role
        self._floats: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(t("admin_cash_floats"))
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        refresh_btn = _ghost_btn(t("refresh"))
        refresh_btn.clicked.connect(self.load_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
        self._status.setVisible(False)
        layout.addWidget(self._status)

        self._table = QTableWidget(0, len(self.COLS))
        self._table.setHorizontalHeaderLabels(self.COLS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(220)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._table.setStyleSheet(
            f"QTableWidget {{ background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; "
            f"gridline-color: {BORDER_COLOR}; font-size: 12px; }}"
            f"QHeaderView::section {{ background: {BG_DARK}; color: {TEXT_SECONDARY}; "
            f"border: none; padding: 6px; font-weight: bold; }}"
        )
        hdr = self._table.horizontalHeader()
        for i in range(len(self.COLS)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_NOTE, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._table)

    def load_data(self) -> None:
        try:
            self._floats = self._api.get_floats()
            self._status.setVisible(False)
        except Exception as e:
            self._floats = []
            self._status.setText(str(e))
            self._status.setVisible(True)
        self._populate()

    def _populate(self) -> None:
        self._table.setRowCount(0)
        for row, fl in enumerate(self._floats):
            self._table.insertRow(row)
            self._table.setRowHeight(row, 34)

            float_id = fl.get("id", 0)
            status = fl.get("status", "")
            total = float(fl.get("total_amount", 0))
            closing = float(fl.get("closing_total") or 0)

            values = [
                str(float_id),
                str(fl.get("employee_id", "")),
                str(fl.get("issued_by", "")),
                status,
                f"{total:,.0f}",
                str(fl.get("created_at", ""))[:16],
                str(fl.get("received_at", "") or "—")[:16],
                str(fl.get("closed_at", "") or "—")[:16],
                fl.get("note", "") or "—",
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == self.COL_STATUS:
                    item.setForeground(QColor(STATUS_COLORS.get(status, TEXT_SECONDARY)))
                self._table.setItem(row, col, item)

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setSpacing(4)

            view_btn = _ghost_btn(t("view"), ACCENT_BLUE)
            view_btn.clicked.connect(lambda _, f=fl: self._on_view(f))
            action_layout.addWidget(view_btn)

            if self._role == "cashier" and status == "PENDING_RECONCILIATION":
                confirm_btn = _ghost_btn(t("btn_confirm_return"), ACCENT_GREEN)
                confirm_btn.clicked.connect(lambda _, fid=float_id: self._on_confirm_return(fid))
                action_layout.addWidget(confirm_btn)

            self._table.setCellWidget(row, self.COL_ACTIONS, action_widget)

    def _on_view(self, float_data: dict) -> None:
        dlg = _FloatDetailDialog(float_data, self)
        dlg.exec()

    def _on_confirm_return(self, float_id: int) -> None:
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        pin, ok = QInputDialog.getText(
            self,
            t("btn_confirm_return"),
            t("enter_cashier_pin"),
            echo=QInputDialog.EchoMode.Password if hasattr(QInputDialog, "EchoMode") else 0,
        )
        if not ok or not pin:
            return
        try:
            self._api.confirm_float_return(float_id, pin)
            self.load_data()
        except Exception as e:
            QMessageBox.warning(self, t("error"), str(e))
