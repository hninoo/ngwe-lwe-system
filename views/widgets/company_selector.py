"""
views/widgets/company_selector.py

Reusable cascade selectors for Company → ServiceType → Account.

Classes:
  CompanySelector(QComboBox)    — emits company_changed(int company_id)
  ServiceTypeSelector(QComboBox)
  AccountSelector(QComboBox)
"""
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import QComboBox

from views.widgets.company_logo_label import get_logo_pixmap

if TYPE_CHECKING:
    from services.api_client import ApiClient

SELECT_PLACEHOLDER = "— Select —"
PLACEHOLDER_COLOR = QColor("#6c7086")


def add_placeholder(combo: QComboBox, text: str = SELECT_PLACEHOLDER) -> None:
    combo.addItem(text, userData=None)
    font = QFont()
    font.setItalic(True)
    combo.setItemData(0, font, Qt.ItemDataRole.FontRole)
    combo.setItemData(0, PLACEHOLDER_COLOR, Qt.ItemDataRole.ForegroundRole)
    combo.setCurrentIndex(0)


class CompanySelector(QComboBox):
    """
    QComboBox populated with company entries (logo icon + name).
    Emits company_changed(company_id: int) when selection changes.
    """

    company_changed = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._companies: list[dict] = []
        self.currentIndexChanged.connect(self._on_index_changed)

    def populate(self, companies: list[dict], api_client: "ApiClient") -> None:
        """Clear and repopulate from a list of company dicts."""
        # Block signals while rebuilding to avoid spurious emissions
        self.blockSignals(True)
        self.clear()
        self._companies = companies
        add_placeholder(self)
        for company in companies:
            company_id = company["id"]
            company_name = company.get("name", "")
            pixmap = get_logo_pixmap(api_client, company_id, company_name, size=24)
            icon = QIcon(pixmap)
            self.addItem(icon, company_name, userData=company_id)
        self.setCurrentIndex(0)
        self.blockSignals(False)

    def selected_company_id(self) -> Optional[int]:
        """Return the currently selected company id, or None if empty."""
        if self.currentIndex() <= 0:
            return None
        data = self.currentData()
        return int(data) if data is not None else None

    def _on_index_changed(self, index: int) -> None:
        if index <= 0:
            return
        company_id = self.itemData(index)
        if company_id is not None:
            self.company_changed.emit(int(company_id))


class ServiceTypeSelector(QComboBox):
    """
    QComboBox populated with service_type entries for a given company.
    Emits service_type_changed(service_type_id: int) when selection changes.
    """

    service_type_changed = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._service_types: list[dict] = []
        self.currentIndexChanged.connect(self._on_index_changed)

    def populate(self, service_types: list[dict]) -> None:
        """Clear and repopulate from a list of service_type dicts."""
        self.blockSignals(True)
        self.clear()
        self._service_types = service_types
        add_placeholder(self)
        for st in service_types:
            self.addItem(st.get("name", ""), userData=st["id"])
        self.setCurrentIndex(0)
        self.blockSignals(False)

    def selected_service_type_id(self) -> Optional[int]:
        """Return the currently selected service_type id, or None if empty."""
        if self.currentIndex() <= 0:
            return None
        data = self.currentData()
        return int(data) if data is not None else None

    def _on_index_changed(self, index: int) -> None:
        if index <= 0:
            return
        st_id = self.itemData(index)
        if st_id is not None:
            self.service_type_changed.emit(int(st_id))


class AccountSelector(QComboBox):
    """
    QComboBox populated with account entries for a given service_type.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._accounts: list[dict] = []

    def populate(self, accounts: list[dict]) -> None:
        """Clear and repopulate from a list of account dicts."""
        self.blockSignals(True)
        self.clear()
        self._accounts = accounts
        add_placeholder(self)
        for acc in accounts:
            label = f"{acc.get('account_name', '')} — {acc.get('phone_number', '')}"
            self.addItem(label, userData=acc["id"])
        self.setCurrentIndex(0)
        self.blockSignals(False)

    def selected_account_id(self) -> Optional[int]:
        """Return the currently selected account id, or None if empty."""
        if self.currentIndex() <= 0:
            return None
        data = self.currentData()
        return int(data) if data is not None else None

    def selected_account(self) -> Optional[dict]:
        """Return the full account dict for the selected row."""
        idx = self.currentIndex() - 1
        if 0 <= idx < len(self._accounts):
            return self._accounts[idx]
        return None
