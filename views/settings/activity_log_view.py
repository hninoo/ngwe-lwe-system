"""
views/settings/activity_log_view.py

Owner-only read-only view for activity_logs table.
"""
from typing import Optional

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
BORDER_COLOR = "#313244"
INPUT_BORDER = "#585b70"


def _ghost_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; color: {color}; border: 1px solid {color}; "
        f"border-radius: 4px; padding: 3px 8px; font-size: 11px; }}"
        f"QPushButton:hover {{ background-color: {BG_INPUT}; }}"
    )
    return btn


def _accent_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color}; color: {BG_DARK}; "
        f"border: none; border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: bold; }}"
    )
    return btn


def _date_edit(default: QDate) -> QDateEdit:
    de = QDateEdit(default)
    de.setCalendarPopup(True)
    de.setDisplayFormat("yyyy-MM-dd")
    de.setStyleSheet(
        f"QDateEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
        f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 4px 8px; }}"
    )
    return de


class ActivityLogView(QWidget):
    """Owner-only read-only audit log viewer."""

    COLS = [
        "id", t("col_user"), t("col_action"), t("col_entity"),
        t("col_entity_id"), t("col_details"), t("col_created"),
    ]
    COL_ID = 0
    COL_USER = 1
    COL_ACTION = 2
    COL_ENTITY = 3
    COL_ENTITY_ID = 4
    COL_DETAILS = 5
    COL_CREATED = 6

    def __init__(self, api: ApiClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._api = api
        self._logs: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Title
        header = QHBoxLayout()
        title = QLabel(t("admin_activity_logs"))
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        refresh_btn = _ghost_btn(t("refresh"))
        refresh_btn.clicked.connect(self.load_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(t("date_label")))
        today = QDate.currentDate()
        self._date_filter = QDateEdit(today)
        self._date_filter.setCalendarPopup(True)
        self._date_filter.setDisplayFormat("yyyy-MM-dd")
        self._date_filter.setStyleSheet(
            f"QDateEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 4px 8px; }}"
        )
        filter_row.addWidget(self._date_filter)

        filter_row.addWidget(QLabel(t("col_entity") + ":"))
        self._entity_filter = QComboBox()
        self._entity_filter.addItems(["", "accounts", "transactions", "users",
                                       "companies", "service_types", "commission_tiers"])
        self._entity_filter.setFixedWidth(130)
        self._entity_filter.setStyleSheet(
            f"QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 4px 8px; }}"
        )
        filter_row.addWidget(self._entity_filter)

        filter_row.addWidget(QLabel(t("col_action") + ":"))
        self._action_filter = QLineEdit()
        self._action_filter.setPlaceholderText(t("search"))
        self._action_filter.setFixedWidth(120)
        self._action_filter.setStyleSheet(
            f"QLineEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 4px 8px; }}"
        )
        filter_row.addWidget(self._action_filter)

        load_btn = _accent_btn(t("btn_load"))
        load_btn.clicked.connect(self.load_data)
        filter_row.addWidget(load_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
        self._status.setVisible(False)
        layout.addWidget(self._status)

        # Table
        self._table = QTableWidget(0, len(self.COLS))
        self._table.setHorizontalHeaderLabels(self.COLS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(250)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._table.setStyleSheet(
            f"QTableWidget {{ background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; "
            f"gridline-color: {BORDER_COLOR}; font-size: 12px; }}"
            f"QHeaderView::section {{ background: {BG_DARK}; color: {TEXT_SECONDARY}; "
            f"border: none; padding: 6px; font-weight: bold; }}"
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_ID, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ID, 40)
        hdr.setSectionResizeMode(self.COL_USER, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_USER, 110)
        hdr.setSectionResizeMode(self.COL_ACTION, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ACTION, 120)
        hdr.setSectionResizeMode(self.COL_ENTITY, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ENTITY, 110)
        hdr.setSectionResizeMode(self.COL_ENTITY_ID, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ENTITY_ID, 70)
        hdr.setSectionResizeMode(self.COL_DETAILS, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self.COL_CREATED, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_CREATED, 140)
        layout.addWidget(self._table)

    def load_data(self) -> None:
        date = self._date_filter.date().toString("yyyy-MM-dd")
        entity_type = self._entity_filter.currentText() or None
        action = self._action_filter.text().strip() or None
        try:
            self._logs = self._api.get_activity_logs(
                entity_type=entity_type, action=action, date=date, limit=300
            )
            self._status.setVisible(False)
        except Exception as e:
            self._show_status(str(e), error=True)
            self._logs = []
        self._populate()

    def _populate(self) -> None:
        self._table.setRowCount(0)
        for row, log in enumerate(self._logs):
            self._table.insertRow(row)
            self._table.setRowHeight(row, 32)

            user_display = log.get("username") or str(log.get("user_id", ""))
            values = [
                str(log.get("id", "")),
                user_display,
                log.get("action", ""),
                log.get("entity_type", ""),
                str(log.get("entity_id", "") or "—"),
                log.get("details", "") or "—",
                str(log.get("created_at", ""))[:16],
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row, col, item)

    def _show_status(self, msg: str, error: bool = False) -> None:
        color = ACCENT_RED if error else ACCENT_GREEN
        self._status.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._status.setText(msg)
        self._status.setVisible(True)
