"""
views/settings/user_settings_view.py

Owner-only panel for full user management (CRUD + reset password).
"""
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
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

BG_DARK = "#1e1e2e"
BG_CARD = "#2a2a3e"
BG_INPUT = "#313244"
TEXT_PRIMARY = "#cdd6f4"
TEXT_SECONDARY = "#a6adc8"
ACCENT_BLUE = "#89b4fa"
ACCENT_GREEN = "#a6e3a1"
ACCENT_RED = "#f38ba8"
ACCENT_MAUVE = "#cba6f7"
ACCENT_TEAL = "#94e2d5"
BORDER_COLOR = "#313244"
INPUT_BORDER = "#585b70"

ROLES = ["employee", "cashier"]


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


def _input_style() -> str:
    return (
        f"QLineEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
        f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 6px 10px; }}"
    )


def _combo_style() -> str:
    return (
        f"QComboBox {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
        f"border: 1px solid {INPUT_BORDER}; border-radius: 4px; padding: 6px 10px; }}"
    )


class _AddUserDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("add_user_btn"))
        self.setMinimumWidth(340)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_PRIMARY};")
        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        self._username = QLineEdit()
        self._username.setPlaceholderText(t("username_ph"))
        self._username.setStyleSheet(_input_style())
        form.addRow(t("col_username") + ":", self._username)

        self._fullname = QLineEdit()
        self._fullname.setPlaceholderText(t("fullname_ph"))
        self._fullname.setStyleSheet(_input_style())
        form.addRow(t("col_fullname") + ":", self._fullname)

        self._password = QLineEdit()
        self._password.setPlaceholderText(t("new_password_ph"))
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setStyleSheet(_input_style())
        form.addRow(t("col_password") + ":", self._password)

        self._role = QComboBox()
        add_placeholder(self._role)
        self._role.addItems(ROLES)
        self._role.setStyleSheet(_combo_style())
        form.addRow(t("col_role") + ":", self._role)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self._username.text().strip():
            QMessageBox.warning(self, "Error", t("err_username_empty"))
            return
        if not self._fullname.text().strip():
            QMessageBox.warning(self, "Error", t("err_fullname_empty"))
            return
        if not self._password.text().strip():
            QMessageBox.warning(self, "Error", t("err_password_empty"))
            return
        if self._role.currentIndex() <= 0:
            QMessageBox.warning(self, "Error", "Please select a role.")
            return
        self.accept()

    @property
    def username(self) -> str:
        return self._username.text().strip()

    @property
    def full_name(self) -> str:
        return self._fullname.text().strip()

    @property
    def password(self) -> str:
        return self._password.text().strip()

    @property
    def role(self) -> str:
        return self._role.currentText()


class _EditUserDialog(QDialog):
    def __init__(self, user: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("edit_user"))
        self.setMinimumWidth(320)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_PRIMARY};")
        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        self._fullname = QLineEdit(user.get("full_name", ""))
        self._fullname.setStyleSheet(_input_style())
        form.addRow(t("col_fullname") + ":", self._fullname)

        self._role = QComboBox()
        add_placeholder(self._role)
        self._role.addItems(ROLES)
        current_role = user.get("role", "employee")
        if current_role in ROLES:
            self._role.setCurrentIndex(ROLES.index(current_role) + 1)
        self._role.setStyleSheet(_combo_style())
        form.addRow(t("col_role") + ":", self._role)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @property
    def full_name(self) -> str:
        return self._fullname.text().strip()

    @property
    def role(self) -> str:
        return self._role.currentText()


class _ResetPasswordDialog(QDialog):
    def __init__(self, username: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{t('reset_password')} — {username}")
        self.setMinimumWidth(300)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_PRIMARY};")
        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        self._pw = QLineEdit()
        self._pw.setPlaceholderText(t("new_password_ph"))
        self._pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw.setStyleSheet(_input_style())
        form.addRow(t("new_password_ph") + ":", self._pw)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self._pw.text().strip():
            QMessageBox.warning(self, "Error", t("err_password_empty"))
            return
        self.accept()

    @property
    def new_password(self) -> str:
        return self._pw.text().strip()


class UserSettingsView(QWidget):
    """Owner-only full CRUD panel for users."""

    COLS = ["id", t("col_username"), t("col_fullname"), t("col_role"),
            t("col_active"), t("col_created"), t("col_actions")]
    COL_ID = 0
    COL_USERNAME = 1
    COL_FULLNAME = 2
    COL_ROLE = 3
    COL_ACTIVE = 4
    COL_CREATED = 5
    COL_ACTIONS = 6

    ROLE_COLORS = {
        "owner": ACCENT_BLUE,
        "cashier": ACCENT_MAUVE,
        "employee": ACCENT_TEAL,
    }

    def __init__(self, api: ApiClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._api = api
        self._users: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(t("users_title"))
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        add_btn = _accent_btn(t("add_user_btn"), ACCENT_GREEN)
        add_btn.clicked.connect(self._on_add)
        header.addWidget(add_btn)
        refresh_btn = _ghost_btn(t("refresh"))
        refresh_btn.clicked.connect(self.load_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {ACCENT_GREEN}; font-size: 12px;")
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
        self._table.setStyleSheet(
            f"QTableWidget {{ background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; "
            f"gridline-color: {BORDER_COLOR}; font-size: 12px; }}"
            f"QHeaderView::section {{ background: {BG_DARK}; color: {TEXT_SECONDARY}; "
            f"border: none; padding: 6px; font-weight: bold; }}"
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_ID, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ID, 40)
        hdr.setSectionResizeMode(self.COL_USERNAME, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_USERNAME, 110)
        hdr.setSectionResizeMode(self.COL_FULLNAME, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self.COL_ROLE, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ROLE, 80)
        hdr.setSectionResizeMode(self.COL_ACTIVE, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ACTIVE, 70)
        hdr.setSectionResizeMode(self.COL_CREATED, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_CREATED, 90)
        hdr.setSectionResizeMode(self.COL_ACTIONS, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ACTIONS, 220)
        layout.addWidget(self._table)

    def load_data(self) -> None:
        try:
            self._users = self._api.get_users()
        except Exception:
            self._users = []
        self._populate()

    def _populate(self) -> None:
        self._table.setRowCount(0)
        for row, u in enumerate(self._users):
            self._table.insertRow(row)
            self._table.setRowHeight(row, 36)

            uid = u.get("id", 0)
            username = u.get("username", "")
            full_name = u.get("full_name", "")
            role = u.get("role", "")
            is_active = bool(u.get("is_active", 1))
            created = str(u.get("created_at", ""))[:10]

            for col, text in enumerate([str(uid), username, full_name, role,
                                         t("status_active") if is_active else t("status_inactive"),
                                         created]):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == self.COL_ROLE:
                    item.setForeground(QColor(self.ROLE_COLORS.get(role, TEXT_SECONDARY)))
                elif col == self.COL_ACTIVE:
                    item.setForeground(QColor(ACCENT_GREEN if is_active else ACCENT_RED))
                self._table.setItem(row, col, item)

            # Actions cell — skip for owner accounts
            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(4)

            if role != "owner":
                edit_btn = _ghost_btn(t("edit"), ACCENT_BLUE)
                edit_btn.clicked.connect(lambda _, uid=uid, usr=u: self._on_edit(uid, usr))
                al.addWidget(edit_btn)

                reset_btn = _ghost_btn(t("reset_password"), ACCENT_MAUVE)
                reset_btn.clicked.connect(
                    lambda _, uid=uid, uname=username: self._on_reset_pw(uid, uname)
                )
                al.addWidget(reset_btn)

                tog_txt = t("deactivate") if is_active else t("activate")
                tog_color = ACCENT_RED if is_active else ACCENT_GREEN
                tog_btn = _ghost_btn(tog_txt, tog_color)
                tog_btn.clicked.connect(
                    lambda _, uid=uid, active=is_active: self._on_toggle(uid, active)
                )
                al.addWidget(tog_btn)

            al.addStretch()
            self._table.setCellWidget(row, self.COL_ACTIONS, actions)

    def _on_add(self) -> None:
        dlg = _AddUserDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._api.create_user(dlg.username, dlg.password, dlg.full_name, dlg.role)
            self._show_status(t("user_created"))
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _on_edit(self, user_id: int, user: dict) -> None:
        dlg = _EditUserDialog(user, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._api.update_user(user_id, {"full_name": dlg.full_name, "role": dlg.role})
            self._show_status(t("user_updated"))
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _on_reset_pw(self, user_id: int, username: str) -> None:
        dlg = _ResetPasswordDialog(username, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._api.reset_user_password(user_id, dlg.new_password)
            self._show_status(t("password_reset_ok"))
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _on_toggle(self, user_id: int, currently_active: bool) -> None:
        try:
            self._api.toggle_user_active(user_id, not currently_active)
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _show_status(self, msg: str, error: bool = False) -> None:
        color = ACCENT_RED if error else ACCENT_GREEN
        self._status.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._status.setText(msg)
        self._status.setVisible(True)
