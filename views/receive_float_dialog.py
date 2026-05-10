from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from services.api_client import ApiClient

# ── Colors ──
BG_DARK = "#1e1e2e"
BG_CARD = "#2a2a3e"
BG_INPUT = "#313244"
TEXT_PRIMARY = "#cdd6f4"
TEXT_SECONDARY = "#a6adc8"
ACCENT_BLUE = "#89b4fa"
ACCENT_GREEN = "#a6e3a1"
ACCENT_RED = "#f38ba8"
ACCENT_YELLOW = "#f9e2af"
BORDER_COLOR = "#313244"
INPUT_BORDER = "#585b70"

DENOMINATIONS = [50, 100, 200, 500, 1000, 5000, 10000]

DIALOG_STYLE = f"""
    QDialog {{ background-color: {BG_DARK}; }}
    QWidget {{ color: {TEXT_PRIMARY}; background-color: {BG_DARK}; }}
    QLabel {{ background-color: transparent; }}
    QFrame {{ background-color: {BG_CARD}; border-radius: 8px; border: 1px solid {BORDER_COLOR}; }}
    QTableWidget {{
        background-color: {BG_CARD}; border: 1px solid {BORDER_COLOR};
        border-radius: 6px; gridline-color: {BORDER_COLOR}; font-size: 12px;
    }}
    QTableWidget::item {{ padding: 6px; background-color: transparent; }}
    QHeaderView::section {{
        background-color: {BG_DARK}; color: {TEXT_SECONDARY};
        border: none; padding: 6px; font-weight: bold; font-size: 11px;
    }}
    QLineEdit {{
        background-color: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {INPUT_BORDER}; border-radius: 6px;
        padding: 8px 12px; font-size: 14px; letter-spacing: 4px;
    }}
    QLineEdit:focus {{ border: 1px solid {ACCENT_BLUE}; }}
    QPushButton {{
        background-color: {ACCENT_BLUE}; color: {BG_DARK};
        border: none; border-radius: 6px; padding: 10px 24px;
        font-size: 13px; font-weight: bold;
    }}
    QPushButton:hover {{ background-color: #74c7ec; }}
    QPushButton:disabled {{ background-color: #585b70; color: #6c7086; }}
"""


class ReceiveFloatDialog(QDialog):
    """Shown to employee when they have a PENDING float to receive."""

    def __init__(
        self,
        api: ApiClient,
        float_data: dict,
        parent=None,
        confirm_callback: Optional[Callable[[str, int], dict]] = None,
    ) -> None:
        super().__init__(parent)
        self._api = api
        self._float_data = float_data
        self._confirm_callback = confirm_callback
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle(t("float_receipt_window"))
        self.setFixedWidth(480)
        self.setStyleSheet(DIALOG_STYLE)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel(t("float_ready_title"))
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {ACCENT_BLUE}; background: transparent;")
        layout.addWidget(title)

        # Info
        issued_by = self._float_data.get("issued_by_name", "Cashier")
        total = self._float_data.get("total_amount", 0)
        info = QLabel(
            f"Issued by: {issued_by}    |    Total: {int(total):,} MMK"
        )
        info.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; background: transparent;")
        layout.addWidget(info)

        # Denomination breakdown table
        layout.addWidget(self._build_denom_table())

        # Total row
        total_row = QHBoxLayout()
        total_lbl = QLabel(t("total_float_label"))
        total_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        total_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        total_val = QLabel(f"{int(total):,} MMK")
        total_val.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        total_val.setStyleSheet(f"color: {ACCENT_GREEN}; background: transparent;")
        total_row.addWidget(total_lbl)
        total_row.addStretch()
        total_row.addWidget(total_val)
        layout.addLayout(total_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"border: 1px solid {BORDER_COLOR}; background: {BORDER_COLOR};")
        layout.addWidget(sep)

        # PIN input
        pin_lbl = QLabel(t("pin_prompt"))
        pin_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; background: transparent;")
        layout.addWidget(pin_lbl)

        self._pin_input = QLineEdit()
        self._pin_input.setPlaceholderText("••••••")
        self._pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin_input.setMaxLength(6)
        self._pin_input.returnPressed.connect(self._on_confirm)
        layout.addWidget(self._pin_input)

        # Error label
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px; background: transparent;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # Buttons
        btn_row = QHBoxLayout()
        self._cancel_btn = QPushButton(t("cancel"))
        self._cancel_btn.setStyleSheet(
            f"QPushButton {{ background-color: #313244; color: {TEXT_PRIMARY}; "
            f"border: none; border-radius: 6px; padding: 10px 24px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: #45475a; }}"
        )
        self._cancel_btn.clicked.connect(self.reject)

        self._confirm_btn = QPushButton(t("confirm_receipt_btn"))
        self._confirm_btn.clicked.connect(self._on_confirm)

        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._confirm_btn)
        layout.addLayout(btn_row)

        self._pin_input.setFocus()

    def _build_denom_table(self) -> QTableWidget:
        denoms = self._float_data.get("denominations", [])
        # Filter to non-zero
        active_denoms = [d for d in denoms if d.get("quantity", 0) > 0]

        table = QTableWidget(len(active_denoms), 3)
        table.setHorizontalHeaderLabels([t("col_denomination"), t("col_quantity"), t("col_value")])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.verticalHeader().setVisible(False)
        table.setMaximumHeight(min(200, 40 + len(active_denoms) * 32))

        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        for row_idx, d in enumerate(active_denoms):
            denom = d.get("denomination", 0)
            qty = d.get("quantity", 0)
            value = denom * qty

            denom_item = QTableWidgetItem(f"{denom:,} MMK")
            denom_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            qty_item = QTableWidgetItem(str(qty))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            val_item = QTableWidgetItem(f"{value:,}")
            val_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            table.setItem(row_idx, 0, denom_item)
            table.setItem(row_idx, 1, qty_item)
            table.setItem(row_idx, 2, val_item)

        return table

    def _on_confirm(self) -> None:
        pin = self._pin_input.text().strip()
        if len(pin) != 6 or not pin.isdigit():
            self._show_error(t("pin_invalid"))
            return

        self._error_label.setVisible(False)
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.setText(t("verifying"))

        try:
            float_id = self._float_data["id"]
            if self._confirm_callback is not None:
                self._confirm_callback(pin, float_id)
            else:
                denoms = {
                    str(d["denomination"]): int(d["quantity"])
                    for d in self._float_data.get("denominations", [])
                    if int(d.get("quantity", 0)) > 0
                }
                self._api.receive_float(float_id, pin, denoms)
            self.accept()
        except Exception as e:
            error_text = str(e)
            # Try to extract a cleaner message from HTTP errors
            try:
                import requests
                if isinstance(e, requests.HTTPError) and e.response is not None:
                    detail = e.response.json().get("detail", str(e))
                    error_text = detail
            except Exception:
                pass
            self._show_error(f"Error: {error_text}")
            self._confirm_btn.setEnabled(True)
            self._confirm_btn.setText(t("confirm_receipt_btn"))
            self._pin_input.clear()
            self._pin_input.setFocus()

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)
