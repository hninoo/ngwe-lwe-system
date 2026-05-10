"""
views/settings/service_type_settings_view.py

Owner-only panel for managing ServiceTypes within a selected Company.
"""
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from services.api_client import ApiClient
from views.widgets.company_selector import add_placeholder

# ── Colors ────────────────────────────────────────────────────────────────────
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

OPERATIONS = ["All", "Deposit", "Withdraw", "Transfer", "Exchange"]


def _accent_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color}; color: {BG_DARK}; "
        f"border: none; border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: bold; }}"
    )
    return btn


def _ghost_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background: transparent; color: {color}; border: 1px solid {color}; "
        f"border-radius: 4px; padding: 3px 8px; font-size: 11px; }}"
        f"QPushButton:hover {{ background-color: {BG_INPUT}; }}"
    )
    return btn


class _AddServiceTypeDialog(QDialog):
    """Dialog to create a new service type."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("add_service_type"))
        self.setMinimumWidth(320)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_PRIMARY};")

        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(t("service_name_ph"))
        self._name_edit.setStyleSheet(
            f"QLineEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 6px 10px; }}"
        )
        form.addRow(t("col_name") + ":", self._name_edit)

        self._operation_combo = QComboBox()
        add_placeholder(self._operation_combo)
        self._operation_combo.addItems(OPERATIONS)
        self._operation_combo.setStyleSheet(
            f"QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 6px 10px; }}"
        )
        form.addRow(t("operation_label"), self._operation_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Error", t("err_service_name_empty"))
            return
        if self._operation_combo.currentIndex() <= 0:
            QMessageBox.warning(self, "Error", "Please select an operation.")
            return
        self.accept()

    @property
    def service_name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def operation(self) -> str:
        return self._operation_combo.currentText()


class ServiceTypeSettingsView(QWidget):
    """
    Owner-only panel for managing ServiceTypes.

    Shows a company selector at the top; the table below lists service types
    for the selected company with Add and Deactivate actions.
    """

    COLS = ["id", t("col_company"), t("col_name"), t("col_operation"), t("col_status"), t("col_actions")]
    COL_ID = 0
    COL_COMPANY = 1
    COL_NAME = 2
    COL_OPERATION = 3
    COL_STATUS = 4
    COL_ACTIONS = 5

    def __init__(self, api: ApiClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._api = api
        self._companies: list[dict] = []
        self._service_types: list[dict] = []
        self._selected_company_id: Optional[int] = None
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Title
        title_row = QHBoxLayout()
        title = QLabel(t("settings_service_types"))
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        title_row.addWidget(title)
        title_row.addStretch()

        refresh_btn = _ghost_btn(t("refresh"))
        refresh_btn.clicked.connect(self.load_data)
        title_row.addWidget(refresh_btn)
        layout.addLayout(title_row)

        # Company filter
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(t("field_company") + ":"))

        self._company_combo = QComboBox()
        self._company_combo.setFixedWidth(200)
        self._company_combo.setStyleSheet(
            f"QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 5px 10px; }}"
        )
        self._company_combo.currentIndexChanged.connect(self._on_company_selected)
        filter_row.addWidget(self._company_combo)

        self._add_btn = _accent_btn(t("add_service_type"), ACCENT_GREEN)
        self._add_btn.clicked.connect(self._on_add)
        filter_row.addWidget(self._add_btn)

        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Status label
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
        self._table.setMinimumHeight(300)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._table.setStyleSheet(
            f"QTableWidget {{ background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; "
            f"gridline-color: {BORDER_COLOR}; font-size: 12px; }}"
            f"QTableWidget::item {{ padding: 4px; }}"
            f"QHeaderView::section {{ background: {BG_DARK}; color: {TEXT_SECONDARY}; "
            f"border: none; padding: 6px; font-weight: bold; font-size: 12px; }}"
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_ID, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ID, 40)
        hdr.setSectionResizeMode(self.COL_COMPANY, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_NAME, 110)
        hdr.setSectionResizeMode(self.COL_OPERATION, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_OPERATION, 90)
        hdr.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_STATUS, 70)
        hdr.setSectionResizeMode(self.COL_ACTIONS, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ACTIONS, 110)
        layout.addWidget(self._table)

    def load_data(self) -> None:
        """Fetch companies, repopulate company combo, refresh service types."""
        try:
            self._companies = self._api.get_companies()
        except Exception:
            self._companies = []

        self._company_combo.blockSignals(True)
        self._company_combo.clear()
        add_placeholder(self._company_combo)
        for c in self._companies:
            self._company_combo.addItem(c.get("name", ""), userData=c.get("id"))
        self._company_combo.blockSignals(False)

        # Restore selection, otherwise leave placeholder selected.
        idx = 0
        if self._selected_company_id is not None:
            for i, c in enumerate(self._companies, start=1):
                if c.get("id") == self._selected_company_id:
                    idx = i
                    break
        self._company_combo.setCurrentIndex(idx)
        self._on_company_selected(idx)

    def _on_company_selected(self, index: int) -> None:
        if index <= 0:
            self._service_types = []
            self._selected_company_id = None
            self._populate_table()
            return
        company = self._companies[index - 1]
        self._selected_company_id = company.get("id")
        try:
            self._service_types = self._api.get_service_types(self._selected_company_id)
        except Exception:
            self._service_types = []
        self._populate_table()

    def _populate_table(self) -> None:
        self._table.setRowCount(0)
        for row, st in enumerate(self._service_types):
            self._table.insertRow(row)
            self._table.setRowHeight(row, 36)

            st_id = st.get("id", 0)
            company_name = self._get_company_name(st.get("company_id"))
            name = st.get("name", "")
            operation = st.get("operation", "")
            is_active = bool(st.get("is_active", 1))

            id_item = QTableWidgetItem(str(st_id))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, self.COL_ID, id_item)

            self._table.setItem(row, self.COL_COMPANY, QTableWidgetItem(company_name))

            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, self.COL_NAME, name_item)

            op_item = QTableWidgetItem(operation)
            op_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, self.COL_OPERATION, op_item)

            status_text = t("status_active") if is_active else t("status_inactive")
            status_color = ACCENT_GREEN if is_active else ACCENT_RED
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(
                __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(status_color)
            )
            self._table.setItem(row, self.COL_STATUS, status_item)

            # Actions
            if is_active:
                actions_widget = QWidget()
                al = QHBoxLayout(actions_widget)
                al.setContentsMargins(4, 2, 4, 2)
                al.setSpacing(4)
                deact_btn = _ghost_btn(t("deactivate"), ACCENT_RED)
                deact_btn.clicked.connect(
                    lambda _, sid=st_id, sname=name: self._on_deactivate(sid, sname)
                )
                al.addWidget(deact_btn)
                al.addStretch()
                self._table.setCellWidget(row, self.COL_ACTIONS, actions_widget)

    def _get_company_name(self, company_id: Optional[int]) -> str:
        if company_id is None:
            return ""
        for c in self._companies:
            if c.get("id") == company_id:
                return c.get("name", "")
        return str(company_id)

    def _on_add(self) -> None:
        if self._selected_company_id is None:
            self._show_status(t("err_select_company"), error=True)
            return
        dlg = _AddServiceTypeDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._api.create_service_type(
                self._selected_company_id, dlg.service_name, dlg.operation
            )
            self._show_status(t("service_type_created"))
            self._on_company_selected(self._company_combo.currentIndex())
        except Exception as e:
            self._show_status(str(e), error=True)

    def _on_deactivate(self, service_type_id: int, name: str) -> None:
        reply = QMessageBox.question(
            self,
            t("deactivate"),
            f"{t('confirm_deactivate')}\n\n{name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._api.update_service_type(service_type_id, {"is_active": False})
            self._show_status(t("service_type_deactivated"))
            self._on_company_selected(self._company_combo.currentIndex())
        except Exception as e:
            self._show_status(str(e), error=True)

    def _show_status(self, msg: str, error: bool = False) -> None:
        color = ACCENT_RED if error else ACCENT_GREEN
        self._status.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._status.setText(msg)
        self._status.setVisible(True)
