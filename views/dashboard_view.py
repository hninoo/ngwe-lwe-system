from datetime import datetime, timezone, timedelta

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from services.api_client import ApiClient
from views.transaction_view import (
    ACCENT_BLUE,
    ACCENT_GREEN,
    ACCENT_MAUVE,
    ACCENT_RED,
    ACCENT_TEAL,
    ACCENT_YELLOW,
    BG_CARD,
    BG_DARK,
    BG_INPUT,
    BORDER_COLOR,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

MMT = timezone(timedelta(hours=6, minutes=30))


class DashboardPage(QWidget):
    """Six-card launcher for employee transactions and utility screens."""

    def __init__(self, api: ApiClient, navigate) -> None:
        super().__init__()
        self._api = api
        self._navigate = navigate
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        top = QHBoxLayout()
        fullname = self._api.user.get("full_name", "") if self._api.user else ""
        title = QLabel(f"Welcome, {fullname}")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        top.addWidget(title)
        top.addStretch()

        self._time_label = QLabel()
        self._time_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        top.addWidget(self._time_label)

        logout_btn = QPushButton(t("logout"))
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT_RED}; color: {BG_DARK}; "
            f"border: none; border-radius: 6px; padding: 8px 20px; font-size: 13px; font-weight: bold; }}"
        )
        logout_btn.clicked.connect(lambda: self._navigate(-1))
        top.addWidget(logout_btn)
        layout.addLayout(top)
        layout.addStretch()

        grid = QGridLayout()
        grid.setSpacing(18)
        cards = [
            ("Cash In", "Receiving digital, paying physical cash.", "CI", ACCENT_GREEN, 1, "cash_in"),
            ("Cash Out", "Receiving physical cash, sending digital.", "CO", ACCENT_RED, 1, "cash_out"),
            ("Transfer", "Bank-to-bank movement.", "TR", ACCENT_BLUE, 1, "transfer"),
            ("Exchange", "Currency conversion.", "EX", ACCENT_YELLOW, 1, "exchange"),
            ("History", "View all past records.", "HI", ACCENT_MAUVE, 2, None),
            ("Profile", "User settings and account info.", "PR", ACCENT_TEAL, 3, None),
        ]
        for idx, (title, desc, icon, color, page, txn_type) in enumerate(cards):
            row, col = divmod(idx, 3)
            grid.addWidget(self._card(title, desc, icon, color, page, txn_type), row, col)
        layout.addLayout(grid)
        layout.addStretch()

    def _card(
        self,
        title: str,
        desc: str,
        icon: str,
        color: str,
        page: int,
        transaction_type: str | None,
    ) -> QFrame:
        card = QFrame()
        card.setMinimumHeight(170)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 12px; "
            f"border: 1px solid {BORDER_COLOR}; border-left: 5px solid {color}; }}"
            f"QFrame:hover {{ background-color: {BG_INPUT}; border: 1px solid {color}; border-left: 5px solid {color}; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        icon_label.setStyleSheet(f"color: {color}; border: none; background: transparent;")
        layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {color}; border: none;")
        layout.addWidget(title_label)

        desc_label = QLabel(desc)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; border: none;")
        layout.addWidget(desc_label)
        card.mousePressEvent = lambda e, p=page, tx=transaction_type: self._navigate(p, tx)
        return card

    def update_time(self) -> None:
        self._time_label.setText(datetime.now(MMT).strftime("%d-%m-%Y  %I:%M:%S %p"))


class DashboardView(QMainWindow):
    """Standalone dashboard that opens TransactionView for transaction cards."""
    switch_to_transaction = pyqtSignal(str)

    def __init__(self, api_client: ApiClient) -> None:
        super().__init__()
        self._api = api_client
        self.setWindowTitle(t("app_title"))
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(f"QMainWindow {{ background-color: {BG_DARK}; }} QWidget {{ color: {TEXT_PRIMARY}; }}")
        self._page = DashboardPage(self._api, self._navigate)
        self.setCentralWidget(self._page)
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._page.update_time)
        self._clock.start(1000)
        self._page.update_time()

    def _navigate(self, page: int, transaction_type: str | None = None) -> None:
        if page == -1:
            self._api.logout()
            from views.login_view import LoginView
            self._login = LoginView(self._api)
            self._login.show()
            self.close()
            return
        if transaction_type:
            self.switch_to_transaction.emit(transaction_type)
            if self.receivers(self.switch_to_transaction) > 0:
                return
        from views.transaction_view import TransactionView
        self._next = TransactionView(self._api, transaction_type=transaction_type)
        self._next._navigate(page, transaction_type)
        self._next.show()
        self.close()


__all__ = ["DashboardPage", "DashboardView"]
