"""
views/daily_closing_view.py

Daily Closing Dashboard — Page 13 of the sidebar.

Sections
────────
  Digital  : All account balances with opening / net-change / closing columns.
  Physical : Main vault total + per-employee float balances.
  Pending  : Today's deposits not yet approved by the cashier (cash not in vault).
  Summary  : Total Cash Assets, Total Digital Assets, Grand Total stat cards.
  Action   : "Close Day" button — snapshots everything and closes all active floats.
"""

from datetime import datetime, timezone, timedelta

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from services.api_client import ApiClient

MMT = timezone(timedelta(hours=6, minutes=30))

# ── Palette (mirrors dashboard_view) ─────────────────────────────────────────
BG_DARK    = "#1e1e2e"
BG_CARD    = "#2a2a3e"
BG_CONTENT = "#1e1e2e"
BG_INPUT   = "#313244"
TEXT_PRIMARY   = "#cdd6f4"
TEXT_SECONDARY = "#a6adc8"
TEXT_MUTED     = "#6c7086"
ACCENT_BLUE    = "#89b4fa"
ACCENT_GREEN   = "#a6e3a1"
ACCENT_RED     = "#f38ba8"
ACCENT_YELLOW  = "#f9e2af"
ACCENT_MAUVE   = "#cba6f7"
ACCENT_TEAL    = "#94e2d5"
BORDER_COLOR   = "#313244"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _section_lbl(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
    lbl.setStyleSheet(f"color: {TEXT_PRIMARY}; padding-bottom: 4px;")
    return lbl


def _card() -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; "
        f"border: 1px solid {BORDER_COLOR}; }}"
    )
    return f


def _make_table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.setStyleSheet(
        f"QTableWidget {{ background-color: {BG_CARD}; border: none; "
        f"gridline-color: {BORDER_COLOR}; font-size: 12px; }}"
        f"QHeaderView::section {{ background-color: {BG_DARK}; color: {TEXT_SECONDARY}; "
        f"border: none; padding: 6px; font-weight: bold; font-size: 11px; }}"
    )
    hdr = t.horizontalHeader()
    hdr.setStretchLastSection(True)
    from PyQt6.QtWidgets import QHeaderView
    for i in range(len(headers) - 1):
        hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
    return t


def _stat_card(label: str, value: str, color: str) -> QFrame:
    card = QFrame()
    card.setFixedHeight(90)
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    card.setStyleSheet(
        f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; "
        f"border-left: 4px solid {color}; }}"
    )
    lo = QVBoxLayout(card)
    lo.setContentsMargins(16, 10, 16, 10)
    lo.setSpacing(4)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px;")
    lo.addWidget(lbl)
    val = QLabel(value)
    val.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
    val.setStyleSheet(f"color: {color};")
    val.setObjectName("stat_value")
    lo.addWidget(val)
    return card


# ── Main View ─────────────────────────────────────────────────────────────────

class DailyClosingView(QWidget):
    """Owner-only daily closing dashboard."""

    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._snapshot: dict = {}
        self._init_ui()

    # ── Build UI ─────────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        container.setStyleSheet(f"background-color: {BG_CONTENT};")
        self._layout = QVBoxLayout(container)
        self._layout.setContentsMargins(24, 20, 24, 28)
        self._layout.setSpacing(16)
        scroll.setWidget(container)

        # ── Header ───────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        self._title_lbl = QLabel(t("closing_title"))
        self._title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
        hdr.addWidget(self._title_lbl)
        hdr.addStretch()
        self._date_lbl = QLabel("")
        self._date_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")
        hdr.addWidget(self._date_lbl)
        refresh_btn = QPushButton("↻  " + t("refresh"))
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setFixedHeight(32)
        refresh_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TEXT_SECONDARY}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 6px; padding: 4px 14px; "
            f"font-size: 12px; }}"
            f"QPushButton:hover {{ color: {TEXT_PRIMARY}; border-color: {ACCENT_BLUE}; }}"
        )
        refresh_btn.clicked.connect(self.load_data)
        hdr.addWidget(refresh_btn)
        self._layout.addLayout(hdr)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
        self._layout.addWidget(self._status_lbl)

        # ── Digital Section ───────────────────────────────────────────────────
        self._layout.addWidget(_section_lbl(t("closing_digital_section")))
        digital_card = _card()
        digital_lo = QVBoxLayout(digital_card)
        digital_lo.setContentsMargins(12, 12, 12, 12)
        self._digital_table = _make_table([
            t("col_account"), t("col_phone"),
            t("col_opening_bal"), t("col_net_change"), t("col_closing_bal"),
        ])
        digital_lo.addWidget(self._digital_table)
        self._layout.addWidget(digital_card)

        # ── Physical Section ──────────────────────────────────────────────────
        self._layout.addWidget(_section_lbl(t("closing_physical_section")))
        physical_card = _card()
        phys_lo = QVBoxLayout(physical_card)
        phys_lo.setContentsMargins(20, 16, 20, 16)
        phys_lo.setSpacing(10)

        vault_row = QHBoxLayout()
        vault_lbl = QLabel(t("closing_main_vault"))
        vault_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        vault_row.addWidget(vault_lbl)
        self._vault_val = QLabel("0")
        self._vault_val.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._vault_val.setStyleSheet(f"color: {ACCENT_GREEN};")
        vault_row.addWidget(self._vault_val)
        vault_row.addStretch()
        phys_lo.addLayout(vault_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER_COLOR}; border: none;")
        phys_lo.addWidget(sep)

        float_hdr = QLabel(t("closing_employee_floats"))
        float_hdr.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
        phys_lo.addWidget(float_hdr)

        self._float_table = _make_table([
            t("col_employee"), t("col_float_balance"),
            t("col_opening_bal"),  # = total_amount (original float issued)
            t("float_status"),
        ])
        phys_lo.addWidget(self._float_table)

        # Denomination inventory header
        inv_hdr = QLabel(t("closing_vault_inventory"))
        inv_hdr.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;")
        phys_lo.addWidget(inv_hdr)

        self._inventory_table = _make_table(
            [t("col_employee")] + [f"{d:,}" for d in (50, 100, 200, 500, 1000, 5000, 10000)] + ["Total"]
        )
        self._inventory_table.setMaximumHeight(160)
        phys_lo.addWidget(self._inventory_table)

        self._layout.addWidget(physical_card)

        # ── Pending Deposits ──────────────────────────────────────────────────
        self._layout.addWidget(_section_lbl(t("closing_pending_deposits")))
        pending_card = _card()
        pending_lo = QVBoxLayout(pending_card)
        pending_lo.setContentsMargins(12, 12, 12, 12)
        self._pending_table = _make_table([
            "#", t("col_account"), t("col_customer"), t("col_amount"), t("col_time"),
        ])
        self._pending_table.setMaximumHeight(180)
        pending_lo.addWidget(self._pending_table)
        self._layout.addWidget(pending_card)

        # ── Summary Row ───────────────────────────────────────────────────────
        self._layout.addWidget(_section_lbl(""))
        summary_row = QHBoxLayout()
        self._card_cash    = _stat_card(t("closing_total_cash"),    "0", ACCENT_GREEN)
        self._card_digital = _stat_card(t("closing_total_digital"), "0", ACCENT_BLUE)
        self._card_grand   = _stat_card(t("closing_grand_total"),   "0", ACCENT_MAUVE)
        summary_row.addWidget(self._card_cash)
        summary_row.addWidget(self._card_digital)
        summary_row.addWidget(self._card_grand)
        self._layout.addLayout(summary_row)

        # ── Close Day Button ──────────────────────────────────────────────────
        self._close_btn = QPushButton(t("btn_close_day"))
        self._close_btn.setFixedHeight(46)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT_RED}; color: {BG_DARK}; "
            f"border: none; border-radius: 8px; font-size: 14px; font-weight: bold; }}"
            f"QPushButton:hover {{ background-color: {ACCENT_RED}cc; }}"
            f"QPushButton:pressed {{ background-color: {ACCENT_RED}88; }}"
        )
        self._close_btn.clicked.connect(self._on_close_day)
        self._layout.addWidget(self._close_btn)
        self._layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Data Loading ──────────────────────────────────────────────────────────

    def load_data(self) -> None:
        self._status_lbl.setText(t("closing_loading"))
        try:
            self._snapshot = self._api.get_reconciliation_snapshot()
            self._populate(self._snapshot)
            self._status_lbl.setText("")
        except Exception as e:
            self._status_lbl.setText(f"Error: {e}")

    def _populate(self, snap: dict) -> None:
        today = snap.get("date", str(datetime.now(MMT).date()))
        self._date_lbl.setText(today)

        # ── Digital table ─────────────────────────────────────────────────────
        accounts = snap.get("accounts", [])
        self._digital_table.setRowCount(len(accounts))
        for row, acc in enumerate(accounts):
            opening  = float(acc.get("opening_balance", 0))
            net      = float(acc.get("today_net", 0))
            closing  = float(acc.get("closing_balance", 0))
            cells = [
                acc.get("account_name", ""),
                acc.get("phone_number", ""),
                f"{opening:,.0f}",
                f"{net:+,.0f}",
                f"{closing:,.0f}",
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 3:  # net change colour
                    color = ACCENT_GREEN if net >= 0 else ACCENT_RED
                    item.setForeground(QColor(color))
                elif col == 4:  # closing balance
                    color = ACCENT_GREEN if closing >= 0 else ACCENT_RED
                    item.setForeground(QColor(color))
                self._digital_table.setItem(row, col, item)

        # ── Vault value ───────────────────────────────────────────────────────
        vault_total = float(snap.get("vault_total", 0))
        self._vault_val.setText(f"{vault_total:,.0f} MMK")

        # ── Employee floats table ─────────────────────────────────────────────
        floats = snap.get("employee_floats", [])
        self._float_table.setRowCount(len(floats))
        for row, f in enumerate(floats):
            cur_bal   = float(f.get("current_balance", 0))
            total_amt = float(f.get("total_amount", 0))
            status    = f.get("status", "")
            cells = [
                f.get("employee_name", ""),
                f"{cur_bal:,.0f}",
                f"{total_amt:,.0f}",
                status,
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 1:
                    item.setForeground(QColor(ACCENT_YELLOW))
                elif col == 3:
                    color = {
                        "ACTIVE": ACCENT_GREEN,
                        "PENDING_RECONCILIATION": ACCENT_MAUVE,
                    }.get(status, ACCENT_YELLOW)
                    item.setForeground(QColor(color))
                self._float_table.setItem(row, col, item)

        # ── Denomination inventory table ──────────────────────────────────────
        inventory = snap.get("denomination_inventory", {})
        emp_inventory = inventory.get("employee_floats", [])
        denoms_order = (50, 100, 200, 500, 1000, 5000, 10000)
        rows_inv = []
        main_vault_denoms = inventory.get("main_vault", {})
        if main_vault_denoms:
            rows_inv.append(("Main Vault", main_vault_denoms))
        for emp in emp_inventory:
            rows_inv.append((emp.get("employee_name", ""), emp.get("denomination_balance", {})))
        self._inventory_table.setRowCount(len(rows_inv))
        for row, (name, denom_dict) in enumerate(rows_inv):
            total = 0
            cells = [name]
            for d in denoms_order:
                qty = int(denom_dict.get(str(d), denom_dict.get(d, 0)))
                total += d * qty
                cells.append(str(qty) if qty else "—")
            cells.append(f"{total:,.0f}")
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self._inventory_table.setItem(row, col, item)

        # ── Pending deposits table ────────────────────────────────────────────
        pending = snap.get("pending_deposits", [])
        self._pending_table.setRowCount(len(pending))
        for row, dep in enumerate(pending):
            created = str(dep.get("created_at", ""))
            if len(created) > 16:
                created = created[11:16]
            cells = [
                str(dep.get("id", "")),
                str(dep.get("account_id", "")),
                str(dep.get("customer_name", "")),
                f"{float(dep.get('amount', 0)):,.0f}",
                created,
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 3:
                    item.setForeground(QColor(ACCENT_YELLOW))
                self._pending_table.setItem(row, col, item)

        # ── Summary cards ─────────────────────────────────────────────────────
        def _set_card(card: QFrame, value: float) -> None:
            val_lbl = card.findChild(QLabel, "stat_value")
            if val_lbl:
                val_lbl.setText(f"{value:,.0f}")

        _set_card(self._card_cash,    float(snap.get("total_cash", 0)))
        _set_card(self._card_digital, float(snap.get("total_digital", 0)))
        _set_card(self._card_grand,   float(snap.get("grand_total", 0)))

    # ── Close Day Handler ─────────────────────────────────────────────────────

    def _on_close_day(self) -> None:
        reply = QMessageBox.question(
            self,
            t("closing_confirm_title"),
            t("closing_confirm_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._api.close_day()
            self._status_lbl.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
            self._status_lbl.setText(t("closing_day_closed"))
            self.load_data()
            QTimer.singleShot(5000, lambda: self._status_lbl.setText(""))
        except Exception as e:
            self._status_lbl.setStyleSheet(f"color: {ACCENT_RED}; font-size: 12px;")
            self._status_lbl.setText(f"Error: {e}")
