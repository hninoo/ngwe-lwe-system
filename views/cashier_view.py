import json
import os
from datetime import datetime, date as date_type, timezone, timedelta
from typing import Optional

MMT = timezone(timedelta(hours=6, minutes=30))


def _to_mmt(raw) -> datetime:
    """Parse a UTC datetime string and return it in Myanmar Time."""
    try:
        dt = datetime.fromisoformat(str(raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(MMT)
    except Exception:
        return datetime.now(MMT)

from PyQt6.QtCore import Qt, QDate, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
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
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import t, on_change
from services.api_client import ApiClient

WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8000/ws")

# ── Colors ──
BG_DARK = "#1e1e2e"
BG_SIDEBAR = "#181825"
BG_CARD = "#2a2a3e"
BG_CONTENT = "#1e1e2e"
BG_INPUT = "#313244"
TEXT_PRIMARY = "#cdd6f4"
TEXT_SECONDARY = "#a6adc8"
TEXT_MUTED = "#6c7086"
ACCENT_BLUE = "#89b4fa"
ACCENT_GREEN = "#a6e3a1"
ACCENT_RED = "#f38ba8"
ACCENT_YELLOW = "#f9e2af"
BORDER_COLOR = "#313244"
INPUT_BORDER = "#585b70"

DENOMINATIONS = [50, 100, 200, 500, 1000, 5000, 10000]
SIDEBAR_WIDTH = 200
REFRESH_INTERVAL_MS = 30_000
CASH_TOLERANCE = 100  # MMK — must match backend CASH_TOLERANCE_MMK

STYLESHEET = f"""
    QMainWindow {{ background-color: {BG_DARK}; }}
    QWidget {{ color: {TEXT_PRIMARY}; }}
    QScrollArea {{ border: none; background-color: {BG_CONTENT}; }}
    QScrollBar:vertical {{
        background: {BG_DARK}; width: 8px; border: none;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER_COLOR}; border-radius: 4px; min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QTableWidget {{
        background-color: {BG_CARD};
        border: 1px solid {BORDER_COLOR};
        border-radius: 8px;
        gridline-color: {BORDER_COLOR};
        font-size: 12px;
    }}
    QTableWidget::item {{ padding: 6px; }}
    QHeaderView::section {{
        background-color: {BG_SIDEBAR};
        color: {TEXT_SECONDARY};
        border: none; padding: 8px;
        font-weight: bold; font-size: 12px;
    }}
    QLineEdit, QComboBox, QSpinBox {{
        background-color: {BG_INPUT}; color: {TEXT_PRIMARY};
        border: 1px solid {INPUT_BORDER}; border-radius: 6px;
        padding: 8px 12px; font-size: 13px;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
        border: 1px solid {ACCENT_BLUE};
    }}
    QComboBox QAbstractItemView {{
        background-color: {BG_INPUT}; color: {TEXT_PRIMARY};
        selection-background-color: {BG_CARD};
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        background-color: {BG_INPUT}; border: none; width: 16px;
    }}
"""


# ════════════════════════════════════════════
# WebSocket thread (real-time transaction feed)
# ════════════════════════════════════════════
class WebSocketThread(QThread):
    message_received = pyqtSignal(str)

    def __init__(self, url: str, ticket_fn=None) -> None:
        super().__init__()
        self._base_url = url
        self._ticket_fn = ticket_fn
        self._running = True

    def run(self) -> None:
        try:
            import websockets.sync.client as ws_client
            ticket = self._ticket_fn() if self._ticket_fn else ""
            connect_url = f"{self._base_url}?ticket={ticket}" if ticket else self._base_url
            with ws_client.connect(connect_url) as ws:
                while self._running:
                    try:
                        msg = ws.recv(timeout=5)
                        self.message_received.emit(msg)
                    except TimeoutError:
                        pass
        except Exception:
            pass

    def stop(self) -> None:
        self._running = False


# ── Shared helpers ──

def _section_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    label.setStyleSheet(f"color: {TEXT_PRIMARY};")
    return label


def _accent_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color}; color: {BG_DARK}; "
        f"border: none; border-radius: 6px; padding: 8px 18px; "
        f"font-size: 13px; font-weight: bold; }}"
        f"QPushButton:hover {{ opacity: 0.85; }}"
        f"QPushButton:disabled {{ background-color: #585b70; color: #6c7086; }}"
    )
    return btn


def _card_frame() -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; "
        f"border: 1px solid {BORDER_COLOR}; }}"
    )
    return f


def _scrollable_page() -> tuple[QScrollArea, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    container = QWidget()
    container.setStyleSheet(f"background-color: {BG_CONTENT};")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(24, 20, 24, 24)
    layout.setSpacing(16)
    scroll.setWidget(container)
    return scroll, layout


def _make_table(headers: list[str], min_h: int = 200) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setMinimumHeight(min_h)
    hdr = table.horizontalHeader()
    hdr.setStretchLastSection(True)
    for i in range(len(headers) - 1):
        hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
    return table


def _cell(text: str, align=Qt.AlignmentFlag.AlignLeft) -> QTableWidgetItem:
    item = QTableWidgetItem(str(text))
    item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    return item


# ════════════════════════════════════════════
# VaultEntryDialog
# ════════════════════════════════════════════
class VaultEntryDialog(QDialog):
    """Dialog for recording vault_in or adjustment entries."""

    def __init__(self, api: ApiClient, entry_type: str = "vault_in", parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._entry_type = entry_type
        self._spinboxes: dict[int, QSpinBox] = {}
        self._total_label: Optional[QLabel] = None
        self._init_ui()

    def _init_ui(self) -> None:
        type_label = t("vault_in_title") if self._entry_type == "vault_in" else t("vault_adj_title")
        self.setWindowTitle(type_label)
        self.setFixedWidth(440)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG_DARK}; }}
            QWidget {{ color: {TEXT_PRIMARY}; background-color: {BG_DARK}; }}
            QLabel {{ background-color: transparent; }}
            QLineEdit, QSpinBox {{
                background-color: {BG_INPUT}; color: {TEXT_PRIMARY};
                border: 1px solid {INPUT_BORDER}; border-radius: 6px;
                padding: 6px 10px; font-size: 13px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: {BG_INPUT}; border: none; width: 16px;
            }}
            QPushButton {{
                background-color: {ACCENT_BLUE}; color: {BG_DARK};
                border: none; border-radius: 6px; padding: 8px 20px;
                font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #74c7ec; }}
        """)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title_lbl = QLabel(type_label)
        title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {ACCENT_BLUE}; background: transparent;")
        layout.addWidget(title_lbl)

        # Denomination grid
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(QLabel(t("col_denomination")), 0, 0)
        grid.addWidget(QLabel(t("col_quantity")), 0, 1)
        grid.addWidget(QLabel(t("col_value")), 0, 2)

        for i, denom in enumerate(DENOMINATIONS):
            row = i + 1
            denom_lbl = QLabel(f"{denom:,} MMK")
            denom_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")

            spin = QSpinBox()
            spin.setRange(0, 99_999_999)
            spin.setValue(0)
            spin.setFixedWidth(130)
            self._spinboxes[denom] = spin

            val_lbl = QLabel("0")
            val_lbl.setStyleSheet(f"color: {ACCENT_YELLOW}; background: transparent;")
            val_lbl.setFixedWidth(100)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            spin.valueChanged.connect(
                lambda v, d=denom, lbl=val_lbl: (
                    lbl.setText(f"{d * v:,}"),
                    self._update_total(),
                )
            )

            grid.addWidget(denom_lbl, row, 0)
            grid.addWidget(spin, row, 1)
            grid.addWidget(val_lbl, row, 2)

        layout.addLayout(grid)

        # Total
        total_row = QHBoxLayout()
        total_title = QLabel(t("total_label"))
        total_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        total_title.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        self._total_label = QLabel("0 MMK")
        self._total_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._total_label.setStyleSheet(f"color: {ACCENT_GREEN}; background: transparent;")
        total_row.addWidget(total_title)
        total_row.addStretch()
        total_row.addWidget(self._total_label)
        layout.addLayout(total_row)

        # Note
        layout.addWidget(QLabel(t("note_optional")))
        self._note_input = QLineEdit()
        self._note_input.setPlaceholderText(t("morning_cash_ph"))
        layout.addWidget(self._note_input)

        # Error
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px; background: transparent;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # Buttons
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background-color: #313244; color: {TEXT_PRIMARY}; "
            f"border: none; border-radius: 6px; padding: 8px 20px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: #45475a; }}"
        )
        cancel_btn.clicked.connect(self.reject)

        self._submit_btn = QPushButton(t("save_entry"))
        self._submit_btn.clicked.connect(self._on_submit)

        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._submit_btn)
        layout.addLayout(btn_row)

    def _update_total(self) -> None:
        total = sum(d * self._spinboxes[d].value() for d in DENOMINATIONS)
        if self._total_label:
            self._total_label.setText(f"{total:,} MMK")

    def _on_submit(self) -> None:
        denoms = {str(d): self._spinboxes[d].value() for d in DENOMINATIONS}
        total = sum(int(k) * v for k, v in denoms.items())
        if total == 0:
            self._error_label.setText(t("total_nonzero"))
            self._error_label.setVisible(True)
            return
        note = self._note_input.text().strip() or None
        try:
            self._api.record_vault_entry(self._entry_type, denoms, note)
            self.accept()
        except Exception as e:
            self._error_label.setText(f"Error: {e}")
            self._error_label.setVisible(True)


# ════════════════════════════════════════════
# FloatDetailDialog
# ════════════════════════════════════════════
class FloatDetailDialog(QDialog):
    """Shows denomination breakdown of a float."""

    def __init__(self, float_data: dict, parent=None) -> None:
        super().__init__(parent)
        self._float_data = float_data
        self._init_ui()

    def _init_ui(self) -> None:
        float_id = self._float_data.get("id", "?")
        employee = self._float_data.get("employee_name", "?")
        self.setWindowTitle(f"Float #{float_id} — {employee}")
        self.setFixedWidth(460)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG_DARK}; }}
            QWidget {{ color: {TEXT_PRIMARY}; background-color: {BG_DARK}; }}
            QLabel {{ background-color: transparent; }}
            QTableWidget {{
                background-color: {BG_CARD}; border: 1px solid {BORDER_COLOR};
                border-radius: 6px; gridline-color: {BORDER_COLOR}; font-size: 12px;
            }}
            QTableWidget::item {{ padding: 6px; background-color: transparent; }}
            QHeaderView::section {{
                background-color: {BG_DARK}; color: {TEXT_SECONDARY};
                border: none; padding: 6px; font-weight: bold;
            }}
            QPushButton {{
                background-color: {ACCENT_BLUE}; color: {BG_DARK};
                border: none; border-radius: 6px; padding: 8px 20px;
                font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #74c7ec; }}
        """)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header info
        status = self._float_data.get("status", "?")
        status_color = {
            "PENDING": ACCENT_YELLOW,
            "ACTIVE": ACCENT_GREEN,
            "CLOSED": TEXT_MUTED,
        }.get(status, TEXT_PRIMARY)

        header_lbl = QLabel(
            f"Float #{float_id}  —  Employee: {employee}  "
            f"  Status: <span style='color:{status_color}'>{status}</span>"
        )
        header_lbl.setTextFormat(Qt.TextFormat.RichText)
        header_lbl.setStyleSheet(f"font-size: 13px; background: transparent;")
        layout.addWidget(header_lbl)

        total = self._float_data.get("total_amount", 0)
        issued_by = self._float_data.get("issued_by_name", "?")
        meta_lbl = QLabel(t("issued_by_meta", issued_by=issued_by, total=f"{int(total):,}"))
        meta_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; background: transparent;")
        layout.addWidget(meta_lbl)

        # Denomination table
        denoms = self._float_data.get("denominations", [])
        active_denoms = [d for d in denoms if d.get("quantity", 0) > 0]

        table = QTableWidget(len(active_denoms), 3)
        table.setHorizontalHeaderLabels([t("col_denomination"), t("col_quantity"), t("col_value")])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.verticalHeader().setVisible(False)
        table.setMaximumHeight(min(240, 40 + len(active_denoms) * 32))
        hdr = table.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        for row_idx, d in enumerate(active_denoms):
            denom_val = d.get("denomination", 0)
            qty = d.get("quantity", 0)
            value = denom_val * qty
            d_item = _cell(f"{denom_val:,} MMK", Qt.AlignmentFlag.AlignCenter)
            q_item = _cell(str(qty), Qt.AlignmentFlag.AlignCenter)
            v_item = _cell(f"{value:,}", Qt.AlignmentFlag.AlignRight)
            table.setItem(row_idx, 0, d_item)
            table.setItem(row_idx, 1, q_item)
            table.setItem(row_idx, 2, v_item)

        layout.addWidget(table)

        # Closing info (if closed)
        if status == "CLOSED":
            closing_total = self._float_data.get("closing_total", 0)
            closed_at = self._float_data.get("closed_at", "?")
            close_lbl = QLabel(t("closing_total", total=f"{int(closing_total or 0):,}", closed_at=closed_at))
            close_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; background: transparent;")
            layout.addWidget(close_lbl)

        # Close button
        close_btn = QPushButton(t("close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


# ════════════════════════════════════════════
# Page 0: Vault
# ════════════════════════════════════════════
class VaultPage(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._denom_cards: dict[int, QLabel] = {}
        self._total_card_value: Optional[QLabel] = None
        self._log_table: Optional[QTableWidget] = None
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = _scrollable_page()
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

        # Title row
        title_row = QHBoxLayout()
        title_row.addWidget(_section_label(t("vault_title")))
        title_row.addStretch()
        refresh_btn = _accent_btn(t("refresh"), ACCENT_BLUE)
        refresh_btn.clicked.connect(self.load_data)
        entry_btn = _accent_btn(t("record_vault_entry"), ACCENT_GREEN)
        entry_btn.clicked.connect(self._open_vault_entry)
        title_row.addWidget(refresh_btn)
        title_row.addWidget(entry_btn)
        layout.addLayout(title_row)

        # Denomination cards grid
        cards_frame = _card_frame()
        cards_layout = QVBoxLayout(cards_frame)
        cards_layout.setContentsMargins(16, 16, 16, 16)
        cards_layout.setSpacing(10)

        sub_lbl = QLabel(t("denom_balances"))
        sub_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        sub_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
        cards_layout.addWidget(sub_lbl)

        grid = QGridLayout()
        grid.setSpacing(10)
        for col, denom in enumerate(DENOMINATIONS):
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background-color: {BG_DARK}; border-radius: 8px; "
                f"border: 1px solid {BORDER_COLOR}; }}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            card_layout.setSpacing(4)

            denom_lbl = QLabel(f"{denom:,}")
            denom_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            denom_lbl.setStyleSheet(f"color: {ACCENT_BLUE}; background: transparent; border: none;")
            denom_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            count_lbl = QLabel("0 pcs")
            count_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; font-size: 13px; background: transparent; border: none;")
            count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._denom_cards[denom] = count_lbl

            val_lbl = QLabel("0 MMK")
            val_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; background: transparent; border: none;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

            card_layout.addWidget(denom_lbl)
            card_layout.addWidget(count_lbl)
            card_layout.addWidget(val_lbl)

            # Store value label by denomination too
            card.setProperty("val_lbl", val_lbl)
            grid.addWidget(card, 0, col)

        self._denom_grid_cards: list[tuple[int, QLabel, QLabel]] = []
        for col, denom in enumerate(DENOMINATIONS):
            card_widget = grid.itemAtPosition(0, col).widget()
            if card_widget:
                val_lbl = card_widget.property("val_lbl")
                self._denom_grid_cards.append((denom, self._denom_cards[denom], val_lbl))

        cards_layout.addLayout(grid)

        # Total
        total_row = QHBoxLayout()
        total_title = QLabel(t("total_vault_value"))
        total_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        total_title.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        self._total_card_value = QLabel("0 MMK")
        self._total_card_value.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._total_card_value.setStyleSheet(f"color: {ACCENT_GREEN}; background: transparent;")
        total_row.addWidget(total_title)
        total_row.addStretch()
        total_row.addWidget(self._total_card_value)
        cards_layout.addLayout(total_row)
        layout.addWidget(cards_frame)

        # Denomination log table
        layout.addWidget(_section_label(t("recent_vault_entries")))
        self._log_table = _make_table([
            t("col_date_time"), t("col_entry_type"), t("col_denomination"),
            t("col_qty"), t("col_value_mmk"), t("col_note"), t("col_staff"),
        ])
        layout.addWidget(self._log_table)
        layout.addStretch()

    def _open_vault_entry(self) -> None:
        dlg = VaultEntryDialog(self._api, entry_type="vault_in", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_data()

    def load_data(self) -> None:
        try:
            vault = self._api.get_vault()
            balance = vault.get("denominations", {})
            total = vault.get("total", 0)

            for denom, count_lbl, val_lbl in self._denom_grid_cards:
                qty = balance.get(str(denom), 0)
                count_lbl.setText(f"{qty} pcs")
                val_lbl.setText(f"{denom * qty:,} MMK")

            if self._total_card_value:
                self._total_card_value.setText(f"{int(total):,} MMK")

            # Load logs
            logs = self._api.get_vault_logs()
            if self._log_table:
                self._log_table.setRowCount(0)
                for log in logs:
                    row = self._log_table.rowCount()
                    self._log_table.insertRow(row)
                    denom = log.get("denomination", 0)
                    qty = log.get("quantity", 0)
                    type_color = {
                        "vault_in": ACCENT_GREEN,
                        "vault_out": ACCENT_RED,
                        "float_returned": ACCENT_BLUE,
                        "adjustment": ACCENT_YELLOW,
                    }.get(log.get("entry_type", ""), TEXT_PRIMARY)

                    time_item = _cell(str(log.get("created_at", ""))[:19])
                    type_item = _cell(log.get("entry_type", ""))
                    type_item.setForeground(
                        __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(type_color)
                    )
                    self._log_table.setItem(row, 0, time_item)
                    self._log_table.setItem(row, 1, type_item)
                    self._log_table.setItem(row, 2, _cell(f"{denom:,}", Qt.AlignmentFlag.AlignRight))
                    self._log_table.setItem(row, 3, _cell(str(qty), Qt.AlignmentFlag.AlignRight))
                    self._log_table.setItem(row, 4, _cell(f"{denom * qty:,}", Qt.AlignmentFlag.AlignRight))
                    self._log_table.setItem(row, 5, _cell(log.get("note", "") or ""))
                    self._log_table.setItem(row, 6, _cell(str(log.get("created_by", ""))))
        except Exception:
            pass


# ════════════════════════════════════════════
# Page 1: Issue Float
# ════════════════════════════════════════════
class IssueFloatPage(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._spinboxes: dict[int, QSpinBox] = {}
        self._val_labels: dict[int, QLabel] = {}
        self._total_label: Optional[QLabel] = None
        self._employee_combo: Optional[QComboBox] = None
        self._employees: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = _scrollable_page()
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

        layout.addWidget(_section_label(t("issue_float_title")))

        # Employee selector
        emp_row = QHBoxLayout()
        emp_row.addWidget(QLabel(t("employee_label")))
        self._employee_combo = QComboBox()
        self._employee_combo.setFixedWidth(280)
        self._employee_combo.setMinimumHeight(34)
        # Minimal explicit colours — no ::drop-down subcontrol so Fusion still
        # renders the dropdown button natively (subcontrols trigger CSS-mode).
        self._employee_combo.setStyleSheet(
            f"QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; padding: 4px 8px; }}"
        )
        emp_row.addWidget(self._employee_combo)
        refresh_emp_btn = _accent_btn(t("refresh"), ACCENT_BLUE)
        refresh_emp_btn.setFixedWidth(80)
        refresh_emp_btn.clicked.connect(self.load_data)
        emp_row.addWidget(refresh_emp_btn)
        emp_row.addStretch()
        layout.addLayout(emp_row)

        # Denomination grid in a card
        card = _card_frame()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(8)

        card_layout.addWidget(QLabel(t("denom_breakdown")))

        grid = QGridLayout()
        grid.setSpacing(8)
        header_denom = QLabel(t("col_denomination"))
        header_denom.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: bold;")
        header_qty = QLabel(t("col_quantity"))
        header_qty.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: bold;")
        header_val = QLabel(t("col_value"))
        header_val.setStyleSheet(f"color: {TEXT_SECONDARY}; font-weight: bold; text-align: right;")
        grid.addWidget(header_denom, 0, 0)
        grid.addWidget(header_qty, 0, 1)
        grid.addWidget(header_val, 0, 2)

        for i, denom in enumerate(DENOMINATIONS):
            row = i + 1
            d_lbl = QLabel(f"{denom:,} MMK")
            d_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")

            spin = QSpinBox()
            spin.setRange(0, 99_999_999)
            spin.setValue(0)
            spin.setFixedWidth(130)
            self._spinboxes[denom] = spin

            val_lbl = QLabel("0")
            val_lbl.setStyleSheet(f"color: {ACCENT_YELLOW}; background: transparent;")
            val_lbl.setFixedWidth(120)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._val_labels[denom] = val_lbl

            spin.valueChanged.connect(
                lambda v, d=denom: self._on_spin_changed(d, v)
            )

            grid.addWidget(d_lbl, row, 0)
            grid.addWidget(spin, row, 1)
            grid.addWidget(val_lbl, row, 2)

        card_layout.addLayout(grid)

        # Total
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"border: 1px solid {BORDER_COLOR}; background: {BORDER_COLOR};")
        card_layout.addWidget(sep)

        total_row = QHBoxLayout()
        total_lbl = QLabel(t("total_float_amount"))
        total_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        total_lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
        self._total_label = QLabel("0 MMK")
        self._total_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._total_label.setStyleSheet(f"color: {ACCENT_GREEN}; background: transparent;")
        total_row.addWidget(total_lbl)
        total_row.addStretch()
        total_row.addWidget(self._total_label)
        card_layout.addLayout(total_row)

        layout.addWidget(card)

        # Note
        note_row = QHBoxLayout()
        note_row.addWidget(QLabel(t("note_optional")))
        self._note_input = QLineEdit()
        self._note_input.setPlaceholderText(t("morning_float_ph"))
        note_row.addWidget(self._note_input)
        layout.addLayout(note_row)

        # Error/status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px; background: transparent;")
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        # Issue button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._issue_btn = _accent_btn(t("issue_float_btn"), ACCENT_GREEN)
        self._issue_btn.clicked.connect(self._on_issue)
        btn_row.addWidget(self._issue_btn)
        layout.addLayout(btn_row)

        layout.addStretch()

    def _on_spin_changed(self, denom: int, value: int) -> None:
        self._val_labels[denom].setText(f"{denom * value:,}")
        total = sum(d * self._spinboxes[d].value() for d in DENOMINATIONS)
        if self._total_label:
            self._total_label.setText(f"{total:,} MMK")

    def load_data(self) -> None:
        try:
            self._employees = self._api.get_employees()
            if self._employee_combo is not None:
                self._employee_combo.clear()
                for u in self._employees:
                    name = (
                        (u.get("full_name") or "").strip()
                        or (u.get("username") or "").strip()
                        or f"Employee #{u.get('id', '?')}"
                    )
                    self._employee_combo.addItem(name, u.get("id"))
                if self._employees:
                    self._employee_combo.setCurrentIndex(0)
                self._employee_combo.update()
            count = len(self._employees)
            if count == 0:
                self._show_status("No active employees found in database.", is_error=True)
            else:
                self._show_status(f"{count} employee(s) loaded.", is_error=False)
        except Exception as e:
            self._show_status(f"Failed to load employees: {e}", is_error=True)

    def _on_issue(self) -> None:
        if not self._employee_combo or self._employee_combo.count() == 0:
            self._show_status(t("select_employee"), is_error=True)
            return

        employee_id = self._employee_combo.currentData()
        if employee_id is None:
            self._show_status(t("select_employee"), is_error=True)
            return

        denoms = {str(d): self._spinboxes[d].value() for d in DENOMINATIONS}
        total = sum(int(k) * v for k, v in denoms.items())
        if total == 0:
            self._show_status(t("float_zero_error"), is_error=True)
            return

        note = self._note_input.text().strip() or None
        self._issue_btn.setEnabled(False)
        self._issue_btn.setText(t("issuing_btn"))
        self._status_label.setVisible(False)

        try:
            self._api.issue_float(employee_id, denoms, note)
            self._show_status(t("float_success", total=f"{total:,}"), is_error=False)
            # Reset spinboxes
            for spin in self._spinboxes.values():
                spin.setValue(0)
            self._note_input.clear()
        except Exception as e:
            self._show_status(f"Error: {e}", is_error=True)
        finally:
            self._issue_btn.setEnabled(True)
            self._issue_btn.setText(t("issue_float_btn"))

    def _show_status(self, message: str, is_error: bool = True) -> None:
        if not message:
            self._status_label.setVisible(False)
            return
        color = ACCENT_RED if is_error else ACCENT_GREEN
        self._status_label.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")
        self._status_label.setText(message)
        self._status_label.setVisible(True)


# ════════════════════════════════════════════
# Page 2: Shifts / Float Assignments
# ════════════════════════════════════════════
class ShiftsPage(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._table: Optional[QTableWidget] = None
        self._floats_data: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = _scrollable_page()
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

        title_row = QHBoxLayout()
        title_row.addWidget(_section_label(t("shifts_title")))
        title_row.addStretch()
        refresh_btn = _accent_btn(t("refresh"), ACCENT_BLUE)
        refresh_btn.clicked.connect(self.load_data)
        title_row.addWidget(refresh_btn)
        layout.addLayout(title_row)

        self._table = _make_table([
            t("col_id"), t("col_employee"), t("col_status"), t("col_float_amount"),
            t("col_issued_by"), t("col_issued_at"), t("col_received_at"), t("col_closed_at"), t("col_action"),
        ], min_h=300)
        layout.addWidget(self._table)
        layout.addStretch()

    def load_data(self) -> None:
        try:
            self._floats_data = self._api.get_floats()
            if self._table is None:
                return
            self._table.setRowCount(0)
            for f in self._floats_data:
                row = self._table.rowCount()
                self._table.insertRow(row)

                status = f.get("status", "")
                status_color = {
                    "PENDING": ACCENT_YELLOW,
                    "ACTIVE": ACCENT_GREEN,
                    "CLOSED": TEXT_MUTED,
                }.get(status, TEXT_PRIMARY)

                total = f.get("total_amount", 0)

                self._table.setItem(row, 0, _cell(str(f.get("id", "")), Qt.AlignmentFlag.AlignCenter))
                self._table.setItem(row, 1, _cell(f.get("employee_name", "")))

                status_item = _cell(status, Qt.AlignmentFlag.AlignCenter)
                status_item.setForeground(
                    __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(status_color)
                )
                self._table.setItem(row, 2, status_item)
                self._table.setItem(row, 3, _cell(f"{int(total):,}", Qt.AlignmentFlag.AlignRight))
                self._table.setItem(row, 4, _cell(f.get("issued_by_name", "")))
                self._table.setItem(row, 5, _cell(str(f.get("created_at", ""))[:16]))
                self._table.setItem(row, 6, _cell(str(f.get("received_at", "") or "")[:16]))
                self._table.setItem(row, 7, _cell(str(f.get("closed_at", "") or "")[:16]))

                # Action button in last column
                view_btn = QPushButton(t("view"))
                view_btn.setStyleSheet(
                    f"QPushButton {{ background-color: {ACCENT_BLUE}; color: {BG_DARK}; "
                    f"border: none; border-radius: 4px; padding: 4px 12px; font-size: 11px; }}"
                    f"QPushButton:hover {{ background-color: #74c7ec; }}"
                )
                view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                float_data = f
                view_btn.clicked.connect(lambda _, fd=float_data: self._show_float_detail(fd))
                self._table.setCellWidget(row, 8, view_btn)
        except Exception:
            pass

    def _show_float_detail(self, float_data: dict) -> None:
        dlg = FloatDetailDialog(float_data, parent=self)
        dlg.exec()


# ════════════════════════════════════════════
# Cash Approval Dialog
# ════════════════════════════════════════════
class CashApprovalDialog(QDialog):
    """Cashier enters denomination breakdown when approving a transaction."""

    def __init__(self, api: ApiClient, txn: dict, parent=None) -> None:
        super().__init__(parent)
        self._api = api
        self._txn = txn
        self._expected: int = int(txn.get("amount", 0))
        self._spinboxes: dict[int, QSpinBox] = {}
        self._total_label: Optional[QLabel] = None
        self._diff_label: Optional[QLabel] = None
        self._submit_btn: Optional[QPushButton] = None
        self._init_ui()

    def _init_ui(self) -> None:
        txn_type = self._txn.get("transaction_type", "").upper()
        amount = self._txn.get("amount", 0)
        customer = self._txn.get("customer_name", "—")
        txn_id = self._txn.get("id", "?")

        self.setWindowTitle(t("cash_approval_window", txn_id=txn_id))
        self.setFixedWidth(460)
        self.setStyleSheet(f"""
            QDialog {{ background-color: {BG_DARK}; }}
            QWidget {{ color: {TEXT_PRIMARY}; background-color: {BG_DARK}; }}
            QLabel {{ background-color: transparent; }}
            QLineEdit, QSpinBox {{
                background-color: {BG_INPUT}; color: {TEXT_PRIMARY};
                border: 1px solid {INPUT_BORDER}; border-radius: 6px;
                padding: 6px 10px; font-size: 13px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: {BG_INPUT}; border: none; width: 16px;
            }}
            QPushButton {{
                background-color: {ACCENT_GREEN}; color: {BG_DARK};
                border: none; border-radius: 6px; padding: 8px 20px;
                font-size: 13px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: #94e2d5; }}
        """)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Transaction info
        title = QLabel(t("cash_confirm_heading", txn_id=txn_id))
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {ACCENT_GREEN};")
        layout.addWidget(title)

        type_color = {
            "DEPOSIT": ACCENT_GREEN, "WITHDRAW": ACCENT_RED,
            "TRANSFER": ACCENT_BLUE, "EXCHANGE": ACCENT_YELLOW,
        }.get(txn_type, TEXT_PRIMARY)
        # vault direction hint
        direction = t("vault_in_hint") if self._txn.get("transaction_type") == "deposit" \
            else t("vault_out_hint")
        info = QLabel(
            f"Type: <span style='color:{type_color}'>{txn_type}</span>  |  "
            f"Amount: <b>{amount:,.0f} MMK</b>  |  Customer: {customer}<br>"
            f"<span style='color:{TEXT_MUTED}; font-size:11px;'>{direction}</span>"
        )
        info.setTextFormat(Qt.TextFormat.RichText)
        info.setStyleSheet("font-size: 13px;")
        layout.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"border: 1px solid {BORDER_COLOR};")
        layout.addWidget(sep)

        # Denomination grid
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(QLabel(t("col_denomination")), 0, 0)
        grid.addWidget(QLabel(t("col_quantity")), 0, 1)
        grid.addWidget(QLabel(t("col_value")), 0, 2)

        for i, denom in enumerate(DENOMINATIONS):
            row_i = i + 1
            d_lbl = QLabel(f"{denom:,} MMK")
            d_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")

            spin = QSpinBox()
            spin.setRange(0, 99_999_999)
            spin.setValue(0)
            spin.setFixedWidth(130)
            self._spinboxes[denom] = spin

            val_lbl = QLabel("0")
            val_lbl.setStyleSheet(f"color: {ACCENT_YELLOW};")
            val_lbl.setFixedWidth(100)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            spin.valueChanged.connect(
                lambda v, d=denom, lbl=val_lbl: (
                    lbl.setText(f"{d * v:,}"),
                    self._update_total(),
                )
            )
            grid.addWidget(d_lbl, row_i, 0)
            grid.addWidget(spin, row_i, 1)
            grid.addWidget(val_lbl, row_i, 2)

        layout.addLayout(grid)

        # Separator before summary
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"border: 1px solid {BORDER_COLOR};")
        layout.addWidget(sep2)

        # Expected row
        expected_row = QHBoxLayout()
        exp_title = QLabel(t("expected_label"))
        exp_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        exp_title.setStyleSheet(f"color: {TEXT_SECONDARY};")
        exp_val = QLabel(f"{self._expected:,} MMK")
        exp_val.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        exp_val.setStyleSheet(f"color: {TEXT_PRIMARY};")
        expected_row.addWidget(exp_title)
        expected_row.addStretch()
        expected_row.addWidget(exp_val)
        layout.addLayout(expected_row)

        # Entered total row
        total_row = QHBoxLayout()
        total_lbl = QLabel(t("entered_label"))
        total_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        total_lbl.setStyleSheet(f"color: {TEXT_SECONDARY};")
        self._total_label = QLabel("0 MMK")
        self._total_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._total_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        total_row.addWidget(total_lbl)
        total_row.addStretch()
        total_row.addWidget(self._total_label)
        layout.addLayout(total_row)

        # Difference row
        diff_row = QHBoxLayout()
        diff_title = QLabel(t("difference_label"))
        diff_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._diff_label = QLabel("0 MMK  ✓")
        self._diff_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self._diff_label.setStyleSheet(f"color: {ACCENT_GREEN};")
        diff_row.addWidget(diff_title)
        diff_row.addStretch()
        diff_row.addWidget(self._diff_label)
        layout.addLayout(diff_row)

        # Note
        layout.addWidget(QLabel(t("note_optional")))
        self._note_input = QLineEdit()
        self._note_input.setPlaceholderText(t("morning_receipt_ph"))
        layout.addWidget(self._note_input)

        # Error
        self._error_label = QLabel("")
        self._error_label.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
        self._error_label.setVisible(False)
        layout.addWidget(self._error_label)

        # Buttons
        btn_row = QHBoxLayout()
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background-color: #313244; color: {TEXT_PRIMARY}; "
            f"border: none; border-radius: 6px; padding: 8px 20px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: #45475a; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        self._submit_btn = QPushButton(t("confirm_cash_btn"))
        self._submit_btn.clicked.connect(self._on_submit)
        btn_row.addWidget(cancel_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._submit_btn)
        layout.addLayout(btn_row)

        # Submit disabled until denominations match
        self._submit_btn.setEnabled(False)

    def _update_total(self) -> None:
        entered = sum(d * self._spinboxes[d].value() for d in DENOMINATIONS)
        diff = entered - self._expected
        within_tolerance = abs(diff) <= CASH_TOLERANCE

        if self._total_label:
            self._total_label.setText(f"{entered:,} MMK")

        if self._diff_label:
            if diff == 0:
                self._diff_label.setText("0 MMK  ✓")
                self._diff_label.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 13px;")
            elif within_tolerance:
                sign = "+" if diff > 0 else ""
                self._diff_label.setText(f"{sign}{diff:,} MMK  ✓ (within ±{CASH_TOLERANCE:,})")
                self._diff_label.setStyleSheet(f"color: {ACCENT_YELLOW}; font-size: 13px;")
            else:
                sign = "+" if diff > 0 else ""
                self._diff_label.setText(f"{sign}{diff:,} MMK  ✗ (limit ±{CASH_TOLERANCE:,})")
                self._diff_label.setStyleSheet(f"color: {ACCENT_RED}; font-size: 13px;")

        if self._submit_btn:
            self._submit_btn.setEnabled(within_tolerance and entered > 0)

    def _on_submit(self) -> None:
        denoms = {str(d): self._spinboxes[d].value() for d in DENOMINATIONS}
        note = self._note_input.text().strip() or None
        if self._submit_btn:
            self._submit_btn.setEnabled(False)
        try:
            self._api.approve_transaction(self._txn["id"], denoms, note)
            self.accept()
        except Exception as e:
            # Parse structured backend error (422 mismatch detail)
            msg = str(e)
            try:
                import requests as _req
                if isinstance(e, _req.HTTPError) and e.response is not None:
                    detail = e.response.json().get("detail", {})
                    if isinstance(detail, dict) and "message" in detail:
                        exp = detail.get("expected", 0)
                        ent = detail.get("entered", 0)
                        dif = detail.get("difference", 0)
                        msg = (
                            f"{detail['message']}\n"
                            f"Expected: {int(exp):,}  |  Entered: {int(ent):,}  |  "
                            f"Diff: {int(dif):+,} MMK"
                        )
            except Exception:
                pass
            self._error_label.setText(msg)
            self._error_label.setVisible(True)
            if self._submit_btn:
                self._submit_btn.setEnabled(True)


# ════════════════════════════════════════════
# Page 3: Transactions (with date filter + real-time + approval)
# ════════════════════════════════════════════
class TransactionsReadOnlyPage(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._table: Optional[QTableWidget] = None
        self._date_edit: Optional[QDateEdit] = None
        self._txns: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = _scrollable_page()
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

        # ── Title row ──
        title_row = QHBoxLayout()
        title_row.addWidget(_section_label(t("transactions_title")))
        title_row.addStretch()

        # Date filter
        title_row.addWidget(QLabel(t("date_label")))
        self._date_edit = QDateEdit(QDate.currentDate())
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        self._date_edit.setFixedWidth(130)
        self._date_edit.setStyleSheet(
            f"QDateEdit {{ background:{BG_INPUT}; color:{TEXT_PRIMARY}; "
            f"border:1px solid {INPUT_BORDER}; border-radius:6px; padding:5px 8px; }}"
        )
        self._date_edit.dateChanged.connect(self.load_data)
        title_row.addWidget(self._date_edit)

        refresh_btn = _accent_btn(t("refresh"), ACCENT_BLUE)
        refresh_btn.clicked.connect(self.load_data)
        title_row.addWidget(refresh_btn)
        layout.addLayout(title_row)

        # WS status badge
        self._ws_badge = QLabel(t("ws_live"))
        self._ws_badge.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 11px;")
        layout.addWidget(self._ws_badge, alignment=Qt.AlignmentFlag.AlignRight)

        # Table — includes Cash Status + Action columns
        self._table = _make_table([
            t("col_id"), t("col_date_time"), t("col_type"), t("col_customer"),
            t("col_amount_mmk"), t("col_fee_mmk"), t("col_staff"), t("col_cash_status"), t("col_action"),
        ], min_h=300)
        layout.addWidget(self._table)
        layout.addStretch()

    def load_data(self) -> None:
        try:
            all_txns = self._api.get_recent_transactions(limit=500)
            self._filter_and_populate(all_txns)
        except Exception:
            pass

    def _filter_and_populate(self, all_txns: list[dict]) -> None:
        sel_date = self._date_edit.date().toPyDate() if self._date_edit else date_type.today()
        filtered = [
            tx for tx in all_txns
            if _to_mmt(tx.get("created_at", "")).date() == sel_date
        ]
        self._txns = filtered
        self._populate(filtered)

    def on_new_transaction(self, txn: dict) -> None:
        """Called by CashierView when a new_transaction WS event arrives."""
        if self._date_edit is None:
            return
        sel_date = self._date_edit.date().toPyDate()
        if _to_mmt(txn.get("created_at", "")).date() == sel_date:
            self._txns.insert(0, txn)
            self._populate(self._txns)

    def _populate(self, txns: list[dict]) -> None:
        if self._table is None:
            return
        type_colors = {
            "deposit":  ACCENT_GREEN,
            "withdraw": ACCENT_RED,
            "transfer": ACCENT_BLUE,
            "exchange": ACCENT_YELLOW,
        }
        self._table.setRowCount(0)
        for tx in txns:
            row = self._table.rowCount()
            self._table.insertRow(row)
            txn_type = tx.get("transaction_type", "")
            color = type_colors.get(txn_type, TEXT_PRIMARY)
            amount = tx.get("amount", 0)
            fee = tx.get("customer_fee", 0)
            approved = tx.get("cash_approved_by") is not None

            time_str = _to_mmt(tx.get("created_at", "")).strftime("%d-%m-%Y %I:%M %p")
            self._table.setItem(row, 0, _cell(str(tx.get("id", "")), Qt.AlignmentFlag.AlignCenter))
            self._table.setItem(row, 1, _cell(time_str))
            type_item = _cell(txn_type.upper(), Qt.AlignmentFlag.AlignCenter)
            type_item.setForeground(QColor(color))
            self._table.setItem(row, 2, type_item)
            self._table.setItem(row, 3, _cell(tx.get("customer_name", "") or ""))
            self._table.setItem(row, 4, _cell(f"{amount:,.0f}", Qt.AlignmentFlag.AlignRight))
            self._table.setItem(row, 5, _cell(f"{fee:,.0f}", Qt.AlignmentFlag.AlignRight))
            self._table.setItem(row, 6, _cell(str(tx.get("created_by", ""))))

            # Cash status badge
            cash_item = _cell(t("approved_badge") if approved else t("pending_badge"), Qt.AlignmentFlag.AlignCenter)
            cash_item.setForeground(QColor(ACCENT_GREEN if approved else ACCENT_YELLOW))
            self._table.setItem(row, 7, cash_item)

            # Backend rejects employee withdraw/exchange (float already debited).
            # Owner-initiated cash-outs still require cashier approval here.
            if not approved and txn_type in ("deposit", "withdraw", "exchange"):
                btn = QPushButton(t("confirm_receipt_btn"))
                btn.setStyleSheet(
                    f"QPushButton {{ background:{ACCENT_GREEN}; color:{BG_DARK}; "
                    f"border:none; border-radius:4px; padding:4px 10px; font-size:11px; font-weight:bold; }}"
                    f"QPushButton:hover {{ background:#94e2d5; }}"
                )
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                txn_copy = dict(tx)
                btn.clicked.connect(lambda _, td=txn_copy: self._on_approve(td))
                self._table.setCellWidget(row, 8, btn)
            elif approved:
                approved_at = str(tx.get("cash_approved_at", ""))[:16]
                self._table.setItem(row, 8, _cell(approved_at, Qt.AlignmentFlag.AlignCenter))
            else:
                self._table.setItem(row, 8, _cell("—", Qt.AlignmentFlag.AlignCenter))

    def _on_approve(self, txn: dict) -> None:
        dlg = CashApprovalDialog(self._api, txn, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.load_data()


# ════════════════════════════════════════════
# CashierView — Main Window
# ════════════════════════════════════════════
class CashierView(QMainWindow):

    @staticmethod
    def _get_menu_items():
        return [
            (t("nav_vault"), 0),
            (t("nav_issue_float"), 1),
            (t("nav_shifts"), 2),
            (t("nav_transactions"), 3),
        ]

    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._current_page = 0
        self._menu_btns: list[QPushButton] = []
        self._pages: list[QWidget] = []
        self._ws_thread: Optional[WebSocketThread] = None
        self._init_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._auto_refresh)
        self._refresh_timer.start(REFRESH_INTERVAL_MS)
        self._start_websocket()
        self._load_current_page()
        on_change(self.retranslate_ui)

    def retranslate_ui(self) -> None:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self.setWindowTitle(f"{t('app_title')} — {t('sidebar_cashier')} — {fullname}")
        for i, (label, _) in enumerate(self._get_menu_items()):
            if i < len(self._menu_btns):
                self._menu_btns[i].setText(label)

    def _init_ui(self) -> None:
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        self.setWindowTitle(f"{t('app_title')} — {t('sidebar_cashier')} — {fullname}")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = self._build_sidebar()
        root.addWidget(sidebar)

        # Content stack
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background-color: {BG_CONTENT};")
        root.addWidget(self._stack, 1)

        # Create pages
        self._vault_page = VaultPage(self._api)
        self._issue_page = IssueFloatPage(self._api)
        self._shifts_page = ShiftsPage(self._api)
        self._txns_page = TransactionsReadOnlyPage(self._api)

        self._pages = [
            self._vault_page,
            self._issue_page,
            self._shifts_page,
            self._txns_page,
        ]

        for page in self._pages:
            self._stack.addWidget(page)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar.setStyleSheet(f"background-color: {BG_SIDEBAR};")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # App title
        title_widget = QWidget()
        title_widget.setFixedHeight(60)
        title_widget.setStyleSheet(f"background-color: {BG_SIDEBAR};")
        title_layout = QVBoxLayout(title_widget)
        title_layout.setContentsMargins(16, 0, 16, 0)
        title_lbl = QLabel(t("sidebar_cashier"))
        title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {ACCENT_BLUE}; background: transparent;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        title_layout.addWidget(title_lbl)
        layout.addWidget(title_widget)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {BORDER_COLOR}; border: none; max-height: 1px;")
        layout.addWidget(sep)

        # Menu buttons
        for label, page_idx in self._get_menu_items():
            btn = QPushButton(label)
            btn.setFixedHeight(46)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._menu_btn_style(False))
            btn.clicked.connect(lambda _, idx=page_idx: self._switch_page(idx))
            layout.addWidget(btn)
            self._menu_btns.append(btn)

        layout.addStretch()

        # Logout button
        logout_btn = QPushButton(t("logout"))
        logout_btn.setFixedHeight(46)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setStyleSheet(
            f"QPushButton {{ background-color: transparent; color: {ACCENT_RED}; "
            f"border: none; text-align: left; padding: 0 16px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: rgba(243,139,168,0.1); }}"
        )
        logout_btn.clicked.connect(self._on_logout)
        layout.addWidget(logout_btn)
        layout.setContentsMargins(0, 0, 0, 8)

        return sidebar

    def _menu_btn_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ background-color: rgba(137,180,250,0.15); "
                f"color: {ACCENT_BLUE}; border: none; border-left: 3px solid {ACCENT_BLUE}; "
                f"text-align: left; padding: 0 16px; font-size: 13px; font-weight: bold; }}"
            )
        return (
            f"QPushButton {{ background-color: transparent; color: {TEXT_SECONDARY}; "
            f"border: none; border-left: 3px solid transparent; "
            f"text-align: left; padding: 0 16px; font-size: 13px; }}"
            f"QPushButton:hover {{ background-color: rgba(137,180,250,0.08); color: {TEXT_PRIMARY}; }}"
        )

    def _switch_page(self, page_idx: int) -> None:
        self._current_page = page_idx
        self._stack.setCurrentIndex(page_idx)
        for i, btn in enumerate(self._menu_btns):
            btn.setStyleSheet(self._menu_btn_style(i == page_idx))
        self._load_current_page()

    def _load_current_page(self) -> None:
        page = self._pages[self._current_page]
        if hasattr(page, "load_data"):
            try:
                page.load_data()
            except Exception:
                pass

    def _auto_refresh(self) -> None:
        self._load_current_page()

    def _start_websocket(self) -> None:
        def _get_ticket() -> str:
            try:
                return self._api.get_ws_ticket()
            except Exception:
                return ""
        self._ws_thread = WebSocketThread(WS_URL, ticket_fn=_get_ticket)
        self._ws_thread.message_received.connect(self._on_ws_message)
        self._ws_thread.start()

    def _on_ws_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
            if data.get("type") == "new_transaction":
                txn = data.get("transaction", {})
                self._txns_page.on_new_transaction(txn)
                # Update WS badge to confirm live
                self._txns_page._ws_badge.setStyleSheet(
                    f"color: {ACCENT_GREEN}; font-size: 11px;"
                )
        except Exception:
            pass

    def _on_logout(self) -> None:
        try:
            self._api.logout()
        except Exception:
            pass
        self._refresh_timer.stop()
        if self._ws_thread:
            self._ws_thread.stop()
        from views.login_view import LoginView
        self._login_view = LoginView(self._api)
        self._login_view.show()
        self.close()

    def closeEvent(self, event) -> None:
        self._refresh_timer.stop()
        if self._ws_thread:
            self._ws_thread.stop()
        super().closeEvent(event)
