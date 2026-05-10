import re

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtWidgets import QLineEdit


CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
AMOUNT_PATTERN = r"^\d{0,12}([.]\d{0,2})?$"
PIN_PATTERN = r"^\d{0,6}$"


def sanitize_text(value: str | None, max_length: int = 255) -> str:
    if value is None:
        return ""
    cleaned = CONTROL_CHARS_RE.sub("", str(value)).strip()
    return cleaned[:max_length]


def install_amount_validator(line_edit: QLineEdit) -> None:
    line_edit.setValidator(QRegularExpressionValidator(QRegularExpression(AMOUNT_PATTERN), line_edit))
    line_edit.setMaxLength(15)


def install_pin_validator(line_edit: QLineEdit) -> None:
    line_edit.setValidator(QRegularExpressionValidator(QRegularExpression(PIN_PATTERN), line_edit))
    line_edit.setMaxLength(6)
