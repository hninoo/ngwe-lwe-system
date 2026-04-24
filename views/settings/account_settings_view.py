"""
views/settings/account_settings_view.py

Owner-only panel for full Account CRUD with Company → ServiceType cascade.
"""
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
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
from views.widgets.company_selector import CompanySelector, ServiceTypeSelector

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


class _AddAccountDialog(QDialog):
    def __init__(self, companies: list[dict], api: ApiClient,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._api = api
        self._companies = companies
        self.setWindowTitle(t("add_account"))
        self.setMinimumWidth(360)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_PRIMARY};")

        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        self._company_sel = CompanySelector()
        self._company_sel.populate(companies, api)
        self._company_sel.company_changed.connect(self._on_company_changed)
        form.addRow(t("field_company") + ":", self._company_sel)

        self._st_sel = ServiceTypeSelector()
        form.addRow(t("field_service_type") + ":", self._st_sel)

        self._name = QLineEdit()
        self._name.setPlaceholderText(t("account_name_ph"))
        self._name.setStyleSheet(_input_style())
        form.addRow(t("col_name") + ":", self._name)

        self._phone = QLineEdit()
        self._phone.setPlaceholderText(t("phone_ph"))
        self._phone.setStyleSheet(_input_style())
        form.addRow(t("col_phone") + ":", self._phone)

        self._balance = QLineEdit("0")
        self._balance.setStyleSheet(_input_style())
        form.addRow(t("col_balance") + ":", self._balance)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        # Load initial service types
        if companies:
            self._on_company_changed(companies[0]["id"])

    def _on_company_changed(self, company_id: int) -> None:
        try:
            sts = self._api.get_service_types(company_id)
        except Exception:
            sts = []
        self._st_sel.populate(sts)

    def _on_accept(self) -> None:
        if self._st_sel.selected_service_type_id() is None:
            QMessageBox.warning(self, "Error", t("err_select_service_type"))
            return
        if not self._name.text().strip():
            QMessageBox.warning(self, "Error", t("err_account_name_empty"))
            return
        if not self._phone.text().strip():
            QMessageBox.warning(self, "Error", t("err_phone_empty"))
            return
        self.accept()

    @property
    def service_type_id(self) -> Optional[int]:
        return self._st_sel.selected_service_type_id()

    @property
    def account_name(self) -> str:
        return self._name.text().strip()

    @property
    def phone_number(self) -> str:
        return self._phone.text().strip()

    @property
    def balance(self) -> float:
        try:
            return float(self._balance.text() or 0)
        except ValueError:
            return 0.0


class _EditAccountDialog(QDialog):
    def __init__(self, account: dict, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("edit_account"))
        self.setMinimumWidth(320)
        self.setStyleSheet(f"background-color: {BG_DARK}; color: {TEXT_PRIMARY};")

        form = QFormLayout(self)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(12)

        self._name = QLineEdit(account.get("account_name", ""))
        self._name.setStyleSheet(_input_style())
        form.addRow(t("col_name") + ":", self._name)

        self._phone = QLineEdit(account.get("phone_number", ""))
        self._phone.setStyleSheet(_input_style())
        form.addRow(t("col_phone") + ":", self._phone)

        self._balance = QLineEdit(str(account.get("balance", 0)))
        self._balance.setStyleSheet(_input_style())
        form.addRow(t("col_balance") + ":", self._balance)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_accept(self) -> None:
        if not self._name.text().strip():
            QMessageBox.warning(self, "Error", t("err_account_name_empty"))
            return
        self.accept()

    @property
    def account_name(self) -> str:
        return self._name.text().strip()

    @property
    def phone_number(self) -> str:
        return self._phone.text().strip()

    @property
    def balance(self) -> float:
        try:
            return float(self._balance.text() or 0)
        except ValueError:
            return 0.0


class AccountSettingsView(QWidget):
    """Owner-only full CRUD panel for accounts."""

    COLS = ["id", t("field_company"), t("field_service_type"),
            t("col_name"), t("col_phone"), t("col_balance"),
            t("col_status"), t("col_actions")]
    COL_ID = 0
    COL_COMPANY = 1
    COL_ST = 2
    COL_NAME = 3
    COL_PHONE = 4
    COL_BALANCE = 5
    COL_STATUS = 6
    COL_ACTIONS = 7

    def __init__(self, api: ApiClient, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._api = api
        self._accounts: list[dict] = []
        self._companies: list[dict] = []
        self._service_types: list[dict] = []
        self._company_name_map: dict[int, str] = {}
        self._st_name_map: dict[int, str] = {}
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Header
        header = QHBoxLayout()
        title = QLabel(t("nav_accounts"))
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        add_btn = _accent_btn(t("add_account"), ACCENT_GREEN)
        add_btn.clicked.connect(self._on_add)
        header.addWidget(add_btn)
        refresh_btn = _ghost_btn(t("refresh"))
        refresh_btn.clicked.connect(self.load_data)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(t("field_company") + ":"))
        self._company_filter = CompanySelector()
        self._company_filter.setFixedWidth(160)
        self._company_filter.company_changed.connect(self._on_filter_company_changed)
        filter_row.addWidget(self._company_filter)
        filter_row.addWidget(QLabel(t("field_service_type") + ":"))
        self._st_filter = ServiceTypeSelector()
        self._st_filter.setFixedWidth(160)
        self._st_filter.service_type_changed.connect(self._on_filter_st_changed)
        filter_row.addWidget(self._st_filter)
        load_all_btn = _ghost_btn(t("load_all"))
        load_all_btn.clicked.connect(self._load_all_accounts)
        filter_row.addWidget(load_all_btn)
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
        self._table.setStyleSheet(
            f"QTableWidget {{ background: {BG_CARD}; border: 1px solid {BORDER_COLOR}; border-radius: 8px; "
            f"gridline-color: {BORDER_COLOR}; font-size: 12px; }}"
            f"QHeaderView::section {{ background: {BG_DARK}; color: {TEXT_SECONDARY}; "
            f"border: none; padding: 6px; font-weight: bold; }}"
        )
        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_ID, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ID, 40)
        hdr.setSectionResizeMode(self.COL_COMPANY, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self.COL_ST, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ST, 90)
        hdr.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_NAME, 130)
        hdr.setSectionResizeMode(self.COL_PHONE, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_PHONE, 110)
        hdr.setSectionResizeMode(self.COL_BALANCE, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_BALANCE, 100)
        hdr.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_STATUS, 70)
        hdr.setSectionResizeMode(self.COL_ACTIONS, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(self.COL_ACTIONS, 220)
        layout.addWidget(self._table)

    def load_data(self) -> None:
        try:
            self._companies = self._api.get_companies()
        except Exception:
            self._companies = []

        self._company_name_map = {c["id"]: c.get("name", "") for c in self._companies}

        # Build a comprehensive service_type name map across all companies
        self._st_name_map = {}
        for company in self._companies:
            try:
                sts = self._api.get_service_types(company["id"])
                for st in sts:
                    self._st_name_map[st["id"]] = st.get("name", "")
            except Exception:
                pass

        self._company_filter.populate(self._companies, self._api)
        if self._companies:
            cid = self._companies[0]["id"]
            self._on_filter_company_changed(cid)
        else:
            self._load_all_accounts()

    def _on_filter_company_changed(self, company_id: int) -> None:
        try:
            sts = self._api.get_service_types(company_id)
        except Exception:
            sts = []
        self._service_types = sts
        self._st_filter.populate(sts)
        # Trigger load for first service type
        if sts:
            self._on_filter_st_changed(sts[0]["id"])
        else:
            self._accounts = []
            self._populate()

    def _on_filter_st_changed(self, service_type_id: int) -> None:
        try:
            self._accounts = self._api.get_accounts(service_type_id=service_type_id)
        except Exception:
            self._accounts = []
        self._populate()

    def _load_all_accounts(self) -> None:
        try:
            self._accounts = self._api.get_accounts()
        except Exception:
            self._accounts = []
        self._populate()

    def _populate(self) -> None:
        self._table.setRowCount(0)
        from PyQt6.QtGui import QColor

        for row, acc in enumerate(self._accounts):
            self._table.insertRow(row)
            self._table.setRowHeight(row, 36)

            acc_id = acc.get("id", 0)
            company_name = self._company_name_map.get(
                acc.get("company_id"), str(acc.get("company_id", ""))
            )
            st_name = self._st_name_map.get(
                acc.get("service_type_id"), str(acc.get("service_type_id", ""))
            )
            name = acc.get("account_name", "")
            phone = acc.get("phone_number", "")
            balance = float(acc.get("balance", 0))
            is_active = bool(acc.get("is_active", 1))

            for col, (text, align) in enumerate([
                (str(acc_id), True),
                (company_name, False),
                (st_name, True),
                (name, False),
                (phone, True),
                (f"{balance:,.0f}", True),
                (t("status_active") if is_active else t("status_inactive"), True),
            ]):
                item = QTableWidgetItem(text)
                if align:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == self.COL_STATUS:
                    item.setForeground(QColor(ACCENT_GREEN if is_active else ACCENT_RED))
                self._table.setItem(row, col, item)

            # Actions: Edit | Activate/Deactivate | Delete
            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(4)

            edit_btn = _ghost_btn(t("edit"), ACCENT_BLUE)
            edit_btn.clicked.connect(lambda _, aid=acc_id, a=acc: self._on_edit(aid, a))
            al.addWidget(edit_btn)

            tog_txt = t("deactivate") if is_active else t("activate")
            tog_color = ACCENT_RED if is_active else ACCENT_GREEN
            tog_btn = _ghost_btn(tog_txt, tog_color)
            tog_btn.clicked.connect(lambda _, aid=acc_id, active=is_active: self._on_toggle(aid, active))
            al.addWidget(tog_btn)

            del_btn = _ghost_btn(t("delete"), ACCENT_RED)
            del_btn.clicked.connect(lambda _, aid=acc_id, n=name: self._on_delete(aid, n))
            al.addWidget(del_btn)

            al.addStretch()
            self._table.setCellWidget(row, self.COL_ACTIONS, actions)

    def _on_add(self) -> None:
        if not self._companies:
            self._show_status(t("err_select_company"), error=True)
            return
        dlg = _AddAccountDialog(self._companies, self._api, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._api.create_account(
                dlg.service_type_id, dlg.account_name, dlg.phone_number, dlg.balance
            )
            self._show_status(t("account_created"))
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _on_edit(self, account_id: int, account: dict) -> None:
        dlg = _EditAccountDialog(account, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._api.update_account(account_id, {
                "account_name": dlg.account_name,
                "phone_number": dlg.phone_number,
                "balance": dlg.balance,
            })
            self._show_status(t("account_updated"))
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _on_toggle(self, account_id: int, currently_active: bool) -> None:
        action = t("deactivate") if currently_active else t("activate")
        reply = QMessageBox.question(
            self, action,
            f"{t('confirm_deactivate')}\n\nAccount ID: {account_id}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._api.update_account(account_id, {"is_active": not currently_active})
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _on_delete(self, account_id: int, account_name: str) -> None:
        reply = QMessageBox.warning(
            self,
            t("delete_account"),
            f"{t('confirm_delete_account')}\n\n"
            f"{t('col_name')}: {account_name}\n"
            f"ID: {account_id}\n\n"
            f"{t('action_cannot_be_undone')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._api.delete_account(account_id)
            self._show_status(t("account_deleted"))
            self.load_data()
        except Exception as e:
            self._show_status(str(e), error=True)

    def _show_status(self, msg: str, error: bool = False) -> None:
        color = ACCENT_RED if error else ACCENT_GREEN
        self._status.setStyleSheet(f"color: {color}; font-size: 12px;")
        self._status.setText(msg)
        self._status.setVisible(True)
