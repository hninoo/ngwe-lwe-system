from PyQt6.QtWidgets import QComboBox

from views.widgets.company_selector import add_placeholder


class SelectBox(QComboBox):
    """Reusable combo box with the required placeholder at index 0."""

    def __init__(self, parent=None, placeholder: str = "— Select —") -> None:
        super().__init__(parent)
        add_placeholder(self, placeholder)

    def reset_items(self, labels: list[str], user_data: list | None = None) -> None:
        self.clear()
        add_placeholder(self)
        user_data = user_data or [None] * len(labels)
        for label, data in zip(labels, user_data):
            self.addItem(label, userData=data)
        self.setCurrentIndex(0)

