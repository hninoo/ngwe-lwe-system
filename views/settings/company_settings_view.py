"""
views/settings/company_settings_view.py

Owner-only panel for managing Companies and their logos.
"""
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
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

# ── Colors (shared with rest of app) ─────────────────────────────────────────
BG_DARK = "#1e1e2e"
BG_CARD = "#2a2a3e"
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

MAX_LOGO_BYTES = 200 * 1024  # 200 KB
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg"}
MIME_MAP = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}

CATEGORIES = ["Pay", "Bank", "Both"]


def _accent_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color}; color: {BG_DARK}; "
        f"border: none; border-radius: 6px; padding: 6px 14px; font-size: 12px; font-weight: bold; }}"
        f"QPushButton:hover {{ opacity: 0.85; }}"
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


class _AddCompanyDialog(QDialog):
    """Simple dialog to create a new company (name + category)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("add_company"))
        self.setMinimumWidth(320)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_PRIMARY};")

        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(t("company_name_ph"))
        self._name_edit.setStyleSheet(
            f"QLineEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 6px 10px; }}"
        )
        form.addRow(t("col_name") + ":", self._name_edit)

        self._category_combo = QComboBox()
        self._category_combo.addItems(CATEGORIES)
        self._category_combo.setStyleSheet(
            f"QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 6px 10px; }}"
        )
        form.addRow(t("category_label"), self._category_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Error", t("err_company_name_empty"))
            return
        self.accept()

    @property
    def company_name(self) -> str:
        return self._name_edit.text().strip()

    @property
    def category(self) -> str:
        return self._category_combo.currentText()


class CompanySettingsView(QWidget):
    """
    Owner-only panel for managing Companies.

    Displays an active-company table with logo preview, Add, Upload Logo,
    and Deactivate actions.
    """

    COLS = ["id", t("col_logo"), t("col_company"), t("col_category"), t("col_status"), t("col_actions")]
    COL_ID = 0
    COL_LOGO = 1
    COL_NAME = 2
    COL_CATEGORY = 3
    COL_STATUS = 4
    COL_ACTIONS = 5

    def __init__(self, api: ApiClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._api = api
        self._companies: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Title + Add button
        header = QHBoxLayout()
        title = QLabel(t("settings_companies"))
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()

        self._add_btn = _accent_btn(t("add_company"), ACCENT_GREEN)
        self._add_btn.clicked.connect(self._on_add)
        header.addWidget(self._add_btn)

        refresh_btn = _ghost_btn(t("refresh"))
        refresh_btn.clicked.connect(self.load_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

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
        hdr.setSectionResizeMode(self.COL_LOGO, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_LOGO, 44)
        hdr.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self.COL_CATEGORY, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_CATEGORY, 70)
        hdr.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_STATUS, 70)
        hdr.setSectionResizeMode(self.COL_ACTIONS, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ACTIONS, 200)
        layout.addWidget(self._table)

    def load_data(self) -> None:
        """Fetch companies from API and repopulate table."""
        try:
            self._companies = self._api.get_companies()
        except Exception:
            self._companies = []
        self._populate_table()

    def _populate_table(self) -> None:
        self._table.setRowCount(0)
        for row, company in enumerate(self._companies):
            self._table.insertRow(row)
            self._table.setRowHeight(row, 40)

            company_id = company.get("id", 0)
            name = company.get("name", "")
            category = company.get("category", "")
            is_active = bool(company.get("is_active", 1))

            # ID
            id_item = QTableWidgetItem(str(company_id))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, self.COL_ID, id_item)

            # Logo thumbnail
            logo_lbl = QLabel()
            logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_lbl.setFixedSize(40, 36)
            self._load_logo_thumbnail(logo_lbl, company_id, name)
            self._table.setCellWidget(row, self.COL_LOGO, logo_lbl)

            # Name
            self._table.setItem(row, self.COL_NAME, QTableWidgetItem(name))

            # Category
            cat_item = QTableWidgetItem(category)
            cat_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, self.COL_CATEGORY, cat_item)

            # Status
            status_text = t("status_active") if is_active else t("status_inactive")
            status_color = ACCENT_GREEN if is_active else ACCENT_RED
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(
                __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(status_color)
            )
            self._table.setItem(row, self.COL_STATUS, status_item)

            # Actions cell
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            logo_btn = _ghost_btn(t("upload_logo"), ACCENT_BLUE)
            logo_btn.clicked.connect(lambda _, cid=company_id, cname=name: self._on_upload_logo(cid, cname))
            actions_layout.addWidget(logo_btn)

            if is_active:
                deact_btn = _ghost_btn(t("deactivate"), ACCENT_RED)
                deact_btn.clicked.connect(lambda _, cid=company_id, cname=name: self._on_deactivate(cid, cname))
                actions_layout.addWidget(deact_btn)

            actions_layout.addStretch()
            self._table.setCellWidget(row, self.COL_ACTIONS, actions_widget)

    def _load_logo_thumbnail(self, label: QLabel, company_id: int, company_name: str) -> None:
        try:
            data = self._api.get_logo(company_id)
            px = QPixmap()
            if px.loadFromData(data) and not px.isNull():
                label.setPixmap(px.scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
                return
        except Exception:
            pass
        # Placeholder: first letter
        label.setText(company_name[0].upper() if company_name else "?")
        label.setStyleSheet(f"color: {TEXT_PRIMARY}; font-weight: bold; font-size: 14px;")

    def _on_add(self) -> None:
        dlg = _AddCompanyDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._api.create_company(dlg.company_name, dlg.category)
            self._show_status(t("company_created"))
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _on_upload_logo(self, company_id: int, company_name: str) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("upload_logo"),
            "",
            "Images (*.png *.jpg *.jpeg *.svg)",
        )
        if not path:
            return
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            self._show_status(t("logo_invalid_type"), error=True)
            return
        file_bytes = p.read_bytes()
        if len(file_bytes) > MAX_LOGO_BYTES:
            self._show_status(t("logo_too_large"), error=True)
            return
        try:
            mime = MIME_MAP.get(suffix, "image/png")
            self._api.upload_logo(company_id, file_bytes, mime)
            self._show_status(t("logo_uploaded"))
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _on_deactivate(self, company_id: int, company_name: str) -> None:
        reply = QMessageBox.question(
            self,
            t("deactivate"),
            f"{t('confirm_deactivate')}\n\n{company_name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._api.update_company(company_id, {"is_active": False})
            self._show_status(t("company_deactivated"))
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _show_status(self, msg: str, error: bool = False) -> None:
        color = ACCENT_RED if error else ACCENT_GREEN
        self._status.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._status.setText(msg)
        self._status.setVisible(True)
