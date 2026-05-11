import json
import os
from datetime import datetime, timezone, timedelta

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
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
    TEXT_SECONDARY,
)

MMT = timezone(timedelta(hours=6, minutes=30))
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8000/ws")


class WebSocketThread(QThread):
    message_received = pyqtSignal(str)

    def __init__(self, url: str, ticket_fn=None) -> None:
        super().__init__()
        self._base_url = url
        self._ticket_fn = ticket_fn
        self._running = True
        self._ws = None

    def run(self) -> None:
        try:
            import websockets.sync.client as ws_client
            ticket = self._ticket_fn() if self._ticket_fn else ""
            connect_url = f"{self._base_url}?ticket={ticket}" if ticket else self._base_url
            with ws_client.connect(connect_url) as ws:
                self._ws = ws
                while self._running:
                    try:
                        msg = ws.recv(timeout=5)
                        self.message_received.emit(msg)
                    except TimeoutError:
                        pass
        except Exception:
            pass
        finally:
            self._ws = None

    def stop(self) -> None:
        self._running = False
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass


class DashboardPage(QWidget):
    """Six-card launcher for employee transactions and utility screens."""

    def __init__(self, api: ApiClient, navigate) -> None:
        super().__init__()
        self._api = api
        self._navigate = navigate
        self._employee_floats: list[dict] = []
        self._employee_float: dict | None = None
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

        if self._is_employee():
            self._employee_floats = self._load_employee_floats()
            self._employee_float = self._load_employee_float()

        grid = QGridLayout()
        grid.setSpacing(18)
        cards = [
            ("Cash In", "Receiving digital, paying physical cash.", "CI", ACCENT_GREEN, 1, "cash_in"),
            ("Cash Out", "Receiving physical cash, sending digital.", "CO", ACCENT_RED, 1, "cash_out"),
            ("Transfer", "Bank-to-bank movement.", "TR", ACCENT_BLUE, 1, "transfer"),
            ("Exchange", "Currency conversion.", "EX", ACCENT_YELLOW, 1, "exchange"),
            ("Vault", "Denominations and cash total.", "VA", ACCENT_TEAL, 4, "vault"),
            ("History", "View all past records.", "HI", ACCENT_MAUVE, 2, None),
            ("Profile", "User settings and account info.", "PR", ACCENT_TEAL, 3, None),
        ]
        visible_cards = [
            card for card in cards
            if card[5] != "vault" or self._is_employee()
        ]
        for idx, (title, desc, icon, color, page, txn_type) in enumerate(visible_cards):
            row, col = divmod(idx, 3)
            disabled = txn_type == "cash_out" and self._is_employee() and not self._employee_has_cash()
            grid.addWidget(
                self._card(title, desc, icon, color, page, txn_type, disabled=disabled),
                row,
                col,
            )
        layout.addLayout(grid)
        layout.addStretch()

    def _is_employee(self) -> bool:
        return bool(self._api.user and self._api.user.get("role") == "employee")

    def _load_employee_floats(self) -> list[dict]:
        try:
            return self._api.get_floats()
        except Exception:
            return []

    def _load_employee_float(self) -> dict | None:
        active = [f for f in self._employee_floats if f.get("status") == "ACTIVE"]
        if not active:
            return None
        return max(active, key=lambda f: f.get("received_at") or f.get("created_at") or "")

    def _employee_has_cash(self) -> bool:
        if not self._employee_float:
            return False
        return float(self._employee_float.get("current_balance") or 0) > 0

    def _vault_card(self) -> QFrame:
        cash = float(self._employee_float.get("current_balance") or 0) if self._employee_float else 0
        status = self._employee_float.get("status", "NO ACTIVE FLOAT") if self._employee_float else "NO ACTIVE FLOAT"
        color = ACCENT_GREEN if cash > 0 else ACCENT_RED
        card = QFrame()
        card.setMinimumHeight(110)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setStyleSheet(
            f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; "
            f"border: 1px solid {BORDER_COLOR}; border-left: 5px solid {color}; }}"
        )
        row = QHBoxLayout(card)
        row.setContentsMargins(22, 16, 22, 16)
        row.setSpacing(14)

        title_col = QVBoxLayout()
        title = QLabel("Vault")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {color}; border: none;")
        subtitle = QLabel("ငွေသားသေတ္တာ")
        subtitle.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; border: none;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        row.addLayout(title_col)
        row.addStretch()

        status_label = QLabel(status.replace("_", " ").title())
        status_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; border: none;")
        row.addWidget(status_label)

        amount = QLabel(f"{cash:,.0f} MMK")
        amount.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        amount.setStyleSheet(f"color: {color}; border: none;")
        row.addWidget(amount)
        return card

    def _card(
        self,
        title: str,
        desc: str,
        icon: str,
        color: str,
        page: int,
        transaction_type: str | None,
        disabled: bool = False,
    ) -> QFrame:
        card = QFrame()
        card.setMinimumHeight(170)
        card.setCursor(Qt.CursorShape.ForbiddenCursor if disabled else Qt.CursorShape.PointingHandCursor)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if disabled:
            card.setStyleSheet(
                f"QFrame {{ background-color: {BG_CARD}; border-radius: 12px; "
                f"border: 1px solid {BORDER_COLOR}; border-left: 5px solid {TEXT_MUTED}; }}"
            )
            color = TEXT_MUTED
        else:
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

        desc_label = QLabel("Your vault has no cash. Contact cashier." if disabled else desc)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 12px; border: none;")
        layout.addWidget(desc_label)
        if disabled:
            card.mousePressEvent = lambda e: self._show_no_cash_message()
        else:
            card.mousePressEvent = lambda e, p=page, tx=transaction_type: self._navigate(p, tx)
        return card

    def _show_vault_details(self) -> None:
        if not self._employee_float:
            history = self._format_float_history()
            QMessageBox.information(
                self,
                "Vault",
                "No active vault found.\n\n" + history,
            )
            return

        float_id = self._employee_float.get("id")
        try:
            balance = self._api.get_float_denomination_balance(float_id)
        except Exception as exc:
            QMessageBox.warning(self, "Vault", f"Unable to load vault details.\n{exc}")
            return

        denoms = balance.get("denominations", {}) or {}
        lines = ["Denominations:"]
        for denom in sorted((int(k) for k in denoms.keys()), reverse=True):
            qty = int(denoms.get(str(denom), 0) or 0)
            if qty:
                lines.append(f"{denom:,.0f} MMK x {qty} = {denom * qty:,.0f} MMK")
        if len(lines) == 1:
            lines.append("No cash denominations.")

        total = float(balance.get("total") or self._employee_float.get("current_balance") or 0)
        lines.append("")
        lines.append(f"Total Cash: {total:,.0f} MMK")
        lines.append("")
        lines.append(self._format_float_history())
        QMessageBox.information(self, "Vault", "\n".join(lines))

    def _format_float_history(self) -> str:
        if not self._employee_floats:
            return "Vault History:\nNo vault history."
        lines = ["Vault History:"]
        for f in self._employee_floats[:5]:
            status = str(f.get("status") or "-").replace("_", " ").title()
            amount = float(f.get("current_balance") or f.get("total_amount") or 0)
            created = f.get("received_at") or f.get("created_at") or ""
            lines.append(f"#{f.get('id')}  {status}  {amount:,.0f} MMK  {created}")
        return "\n".join(lines)

    def _show_no_cash_message(self) -> None:
        QMessageBox.warning(
            self,
            "No Cash In Vault",
            "Your vault has no cash. Please receive cash from the cashier before using Cash Out.",
        )

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
        self._ws_thread: WebSocketThread | None = None
        self._start_websocket()

    def _start_websocket(self) -> None:
        def _get_ticket() -> str:
            try:
                return self._api.get_ws_ticket()
            except Exception:
                return ""
        self._ws_thread = WebSocketThread(WS_URL, ticket_fn=_get_ticket)
        self._ws_thread.message_received.connect(self._on_ws_message)
        self._ws_thread.start()

    def _refresh_dashboard_page(self) -> None:
        self._page = DashboardPage(self._api, self._navigate)
        self.setCentralWidget(self._page)
        try:
            self._clock.timeout.disconnect()
        except TypeError:
            pass
        self._clock.timeout.connect(self._page.update_time)
        self._page.update_time()

    def _on_ws_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
            msg_type = data.get("type")
            if msg_type in {"float_issued", "float_return_confirmed"}:
                self._refresh_dashboard_page()
                QMessageBox.information(
                    self,
                    "Vault Update",
                    data.get("message", "Your vault status has changed."),
                )
            elif msg_type == "cash_in_confirmed":
                QMessageBox.information(
                    self,
                    "Cash In Confirmed",
                    data.get("message", "Your Cash In has been confirmed."),
                )
            elif msg_type == "cash_in_cancelled":
                self._refresh_dashboard_page()
                QMessageBox.warning(
                    self,
                    "Cash In Cancelled",
                    data.get("message", "Your Cash In was cancelled."),
                )
            elif msg_type == "transaction_approved":
                QMessageBox.information(
                    self,
                    "Transaction Approved",
                    data.get("message", "Your transaction has been approved."),
                )
        except Exception:
            pass

    def _navigate(self, page: int, transaction_type: str | None = None) -> None:
        if page == -1:
            self._api.logout()
            from views.login_view import LoginView
            self._login = LoginView(self._api)
            self._login.show()
            self.close()
            return
        if transaction_type == "vault":
            from views.transaction.vault_view import VaultView
            self._next = VaultView(self._api)
            self._next.show()
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

    def closeEvent(self, event) -> None:
        self._clock.stop()
        if self._ws_thread:
            self._ws_thread.stop()
            self._ws_thread.wait(2000)
        super().closeEvent(event)


__all__ = ["DashboardPage", "DashboardView"]
