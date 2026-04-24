"""
views/widgets/company_logo_label.py

Session-cached company logo widget with initial-letter placeholder fallback.
"""
from typing import TYPE_CHECKING, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import QLabel

if TYPE_CHECKING:
    from services.api_client import ApiClient

# ── Module-level session cache (cleared on logout) ────────────────────────────
_logo_cache: dict[int, QPixmap] = {}

# Deterministic color palette for placeholder circles
_PALETTE = [
    QColor("#89b4fa"),  # blue
    QColor("#a6e3a1"),  # green
    QColor("#f38ba8"),  # red
    QColor("#f9e2af"),  # yellow
    QColor("#cba6f7"),  # mauve
    QColor("#94e2d5"),  # teal
    QColor("#fab387"),  # peach
    QColor("#f5c2e7"),  # pink
]


def _render_placeholder(company_name: str, size: int) -> QPixmap:
    """
    Draw a colored circle containing the first letter of company_name.
    Color is deterministic: hash(company_name) % len(_PALETTE).
    """
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)

    color = _PALETTE[hash(company_name) % len(_PALETTE)]
    initial = (company_name[0].upper() if company_name else "?")

    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Draw colored filled circle
    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(0, 0, size, size)

    # Draw initial letter in white, bold
    font = QFont("Arial", max(8, size // 2), QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, initial)

    painter.end()
    return px


def get_logo_pixmap(
    api_client: "ApiClient",
    company_id: int,
    company_name: str,
    size: int = 32,
) -> QPixmap:
    """
    Return a cached QPixmap for the given company.
    Fetches via api_client.get_logo on first call; falls back to placeholder
    on any error. Result is cached in _logo_cache for the session.
    """
    if company_id not in _logo_cache:
        try:
            data = api_client.get_logo(company_id)
            px = QPixmap()
            if not px.loadFromData(data) or px.isNull():
                raise ValueError("loadFromData returned null pixmap")
            _logo_cache[company_id] = px.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        except Exception:
            _logo_cache[company_id] = _render_placeholder(company_name, size)
    return _logo_cache[company_id]


def clear_logo_cache() -> None:
    """Clear the session logo cache. Call on user logout."""
    _logo_cache.clear()


class CompanyLogoLabel(QLabel):
    """
    A QLabel that displays a company logo (fetched once per session)
    or an initial-letter placeholder if the logo is unavailable.
    """

    def __init__(
        self,
        api_client: "ApiClient",
        company_id: int,
        company_name: str,
        size: int = 32,
        parent=None,
    ) -> None:
        super().__init__(parent)
        pixmap = get_logo_pixmap(api_client, company_id, company_name, size)
        self.setPixmap(pixmap)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
