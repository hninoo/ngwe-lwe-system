"""
views/server_info_view.py

Server Connection info page — shown in the SYSTEM sidebar section.
Displays local IP, port, and a copyable client setup URL.
"""

import socket

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from i18n import t

# ── Theme (mirrors dashboard_view / admin_page constants) ────────────────────
BG_DARK     = "#1e1e2e"
BG_CARD     = "#2a2a3e"
BG_CONTENT  = "#1e1e2e"
BG_INPUT    = "#313244"
TEXT_PRIMARY   = "#cdd6f4"
TEXT_SECONDARY = "#a6adc8"
TEXT_MUTED     = "#6c7086"
ACCENT_BLUE    = "#89b4fa"
ACCENT_GREEN   = "#a6e3a1"
BORDER_COLOR   = "#313244"

SERVER_PORT = 8000


def _get_local_ip() -> str:
    """Return the machine's LAN IP via a connectionless UDP probe."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


class ServerInfoSubView(QWidget):
    """Sidebar sub-page: Server Connection details."""

    def __init__(self) -> None:
        super().__init__()
        self._init_ui()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")

        container = QWidget()
        container.setStyleSheet(f"background-color: {BG_CONTENT};")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)
        scroll.setWidget(container)

        title = QLabel(t("admin_server_connection"))
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TEXT_PRIMARY};")
        layout.addWidget(title)

        self._card_container = QWidget()
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._card_container)
        layout.addStretch()

        self._build_card()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _build_card(self) -> None:
        # Clear any previous card
        while self._card_layout.count():
            item = self._card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        ip  = _get_local_ip()
        url = f"http://{ip}:{SERVER_PORT}"

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; "
            f"border: 1px solid {BORDER_COLOR}; }}"
        )
        lo = QVBoxLayout(card)
        lo.setContentsMargins(28, 24, 28, 24)
        lo.setSpacing(18)

        # ── Server Status ────────────────────────────────────────────────────
        lo.addLayout(self._row(
            t("server_status_label"),
            "●  " + t("server_status_online"),
            ACCENT_GREEN,
            bold=True,
        ))

        # ── Local IP ────────────────────────────────────────────────────────
        self._ip_lbl = QLabel(ip)
        self._ip_lbl.setFont(QFont("Courier New", 13))
        self._ip_lbl.setStyleSheet(f"color: {ACCENT_BLUE};")
        lo.addLayout(self._row_widget(t("server_ip_label"), self._ip_lbl))

        # ── Port ────────────────────────────────────────────────────────────
        lo.addLayout(self._row(t("server_port_label"), str(SERVER_PORT), ACCENT_BLUE))

        # ── Separator ───────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER_COLOR}; border: none;")
        lo.addWidget(sep)

        # ── Client Setup Link ────────────────────────────────────────────────
        link_hdr = QLabel(t("server_client_link_label"))
        link_hdr.setStyleSheet(
            f"color: {TEXT_SECONDARY}; font-size: 12px; font-weight: bold;"
        )
        lo.addWidget(link_hdr)

        link_row = QHBoxLayout()
        self._url_lbl = QLabel(url)
        self._url_lbl.setFont(QFont("Courier New", 13))
        self._url_lbl.setStyleSheet(
            f"QLabel {{ color: {ACCENT_GREEN}; background: {BG_INPUT}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 6px; "
            f"padding: 8px 14px; }}"
        )
        self._url_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        link_row.addWidget(self._url_lbl, 1)

        self._copy_btn = QPushButton(t("server_copy_btn"))
        self._copy_btn.setFixedHeight(36)
        self._copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._copy_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT_BLUE}; color: {BG_DARK}; "
            f"border: none; border-radius: 6px; padding: 6px 16px; "
            f"font-size: 12px; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {ACCENT_BLUE}cc; }}"
        )
        self._copy_btn.clicked.connect(self._on_copy)
        link_row.addWidget(self._copy_btn)
        lo.addLayout(link_row)

        self._copied_lbl = QLabel(t("server_copied_msg"))
        self._copied_lbl.setStyleSheet(
            f"color: {ACCENT_GREEN}; font-size: 12px; font-style: italic;"
        )
        self._copied_lbl.setVisible(False)
        lo.addWidget(self._copied_lbl)

        # ── Refresh button ───────────────────────────────────────────────────
        refresh_btn = QPushButton("↻  " + t("server_refresh_btn"))
        refresh_btn.setFixedHeight(34)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {TEXT_SECONDARY}; "
            f"border: 1px solid {BORDER_COLOR}; border-radius: 6px; "
            f"padding: 5px 14px; font-size: 12px; }}"
            f"QPushButton:hover {{ color: {TEXT_PRIMARY}; "
            f"border-color: {ACCENT_BLUE}; }}"
        )
        refresh_btn.clicked.connect(self.load_data)
        lo.addWidget(refresh_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        self._card_layout.addWidget(card)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _row(
        self, key: str, value: str, color: str, bold: bool = False
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        k = QLabel(key)
        k.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        k.setFixedWidth(190)
        row.addWidget(k)
        v = QLabel(value)
        font = QFont("Segoe UI", 13)
        if bold:
            font.setWeight(QFont.Weight.Bold)
        v.setFont(font)
        v.setStyleSheet(f"color: {color};")
        row.addWidget(v)
        row.addStretch()
        return row

    def _row_widget(self, key: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        k = QLabel(key)
        k.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        k.setFixedWidth(190)
        row.addWidget(k)
        row.addWidget(widget)
        row.addStretch()
        return row

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_copy(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self._url_lbl.text())
        self._copied_lbl.setVisible(True)
        QTimer.singleShot(2000, lambda: self._copied_lbl.setVisible(False))

    def load_data(self) -> None:
        """Re-detect IP and rebuild the card (called when sidebar item is clicked)."""
        self._build_card()
