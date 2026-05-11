from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QGridLayout, QLabel, QSpinBox, QVBoxLayout, QWidget


class DenominationInputWidget(QWidget):
    """Reusable denomination input with live subtotal/total calculation."""

    total_changed = pyqtSignal(int)

    def __init__(
        self,
        denominations: list[int],
        *,
        title: Optional[str] = None,
        max_quantities: Optional[dict[str, int] | dict[int, int]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._denominations = denominations
        self._max_quantities = {
            int(k): int(v) for k, v in (max_quantities or {}).items()
        }
        self._spinboxes: dict[int, QSpinBox] = {}
        self._subtotal_labels: dict[int, QLabel] = {}
        self._total_label = QLabel("Total: 0 MMK")
        self._build(title)

    def _build(self, title: Optional[str]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        if title:
            layout.addWidget(QLabel(title))

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(QLabel("Denomination"), 0, 0)
        grid.addWidget(QLabel("Qty"), 0, 1)
        grid.addWidget(QLabel("Subtotal"), 0, 2)

        for row, denom in enumerate(self._denominations, start=1):
            grid.addWidget(QLabel(f"{denom:,} MMK"), row, 0)
            spin = QSpinBox()
            spin.setRange(0, self._max_quantities.get(denom, 99_999_999))
            spin.valueChanged.connect(lambda _value, d=denom: self._update_subtotal(d))
            self._spinboxes[denom] = spin
            grid.addWidget(spin, row, 1)

            subtotal = QLabel("0")
            self._subtotal_labels[denom] = subtotal
            grid.addWidget(subtotal, row, 2)

        layout.addLayout(grid)
        layout.addWidget(self._total_label)

    def _update_subtotal(self, denom: int) -> None:
        qty = self._spinboxes[denom].value()
        self._subtotal_labels[denom].setText(f"{denom * qty:,}")
        total = self.total()
        self._total_label.setText(f"Total: {total:,} MMK")
        self.total_changed.emit(total)

    def total(self) -> int:
        return sum(denom * spin.value() for denom, spin in self._spinboxes.items())

    def breakdown(self) -> dict[str, int]:
        return {
            str(denom): spin.value()
            for denom, spin in self._spinboxes.items()
            if spin.value() > 0
        }

    def set_breakdown(self, breakdown: dict[str, int] | dict[int, int]) -> None:
        values = {int(k): int(v) for k, v in breakdown.items()}
        for denom, spin in self._spinboxes.items():
            spin.setValue(values.get(denom, 0))

    def clear(self) -> None:
        for spin in self._spinboxes.values():
            spin.setValue(0)
