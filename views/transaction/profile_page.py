from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from services.api_client import ApiClient
from views.transaction_view import (
    ACCENT_BLUE,
    ACCENT_TEAL,
    BG_CARD,
    BG_DARK,
    BORDER_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    TEXT_MUTED,
    TEXT_SECONDARY,
    accent_btn,
    field_label,
    scrollable_page,
    section_label,
)


class ProfilePage(QWidget):
    def __init__(self, api: ApiClient, navigate) -> None:
        super().__init__()
        self._api = api
        self._navigate = navigate
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = scrollable_page()
        layout.addWidget(section_label(t("profile_title")))

        # Info card
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; border: 1px solid {BORDER_COLOR}; }}")
        clo = QVBoxLayout(card)
        clo.setContentsMargins(20, 20, 20, 20)
        clo.setSpacing(10)

        user = self._api.user or {}
        name_label = QLabel(user.get("full_name", ""))
        name_label.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        clo.addWidget(name_label)

        info_row = QHBoxLayout()
        un = QLabel(f"@{user.get('username', '')}")
        un.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 13px;")
        info_row.addWidget(un)
        role = user.get("role", "employee")
        badge = QLabel(role.upper())
        badge_color = ACCENT_TEAL if role == "owner" else ACCENT_BLUE
        badge.setStyleSheet(
            f"color: {badge_color}; background-color: {BG_DARK}; border-radius: 4px; padding: 2px 10px; font-size: 11px; font-weight: bold;")
        info_row.addWidget(badge)
        info_row.addStretch()
        clo.addLayout(info_row)
        layout.addWidget(card)

        # Change password
        layout.addSpacing(10)
        layout.addWidget(section_label(t("change_password")))

        pw_card = QFrame()
        pw_card.setStyleSheet(f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; border: 1px solid {BORDER_COLOR}; }}")
        plo = QVBoxLayout(pw_card)
        plo.setContentsMargins(20, 20, 20, 20)
        plo.setSpacing(12)

        plo.addWidget(field_label(t("current_password_ph"), required=True))
        self._old_pw = QLineEdit()
        self._old_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._old_pw.setPlaceholderText(t("current_password_ph"))
        plo.addWidget(self._old_pw)

        plo.addWidget(field_label(t("new_password_ph"), required=True))
        self._new_pw = QLineEdit()
        self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pw.setPlaceholderText(t("new_password_ph"))
        plo.addWidget(self._new_pw)

        plo.addWidget(field_label(t("confirm_password_ph"), required=True))
        self._confirm_pw = QLineEdit()
        self._confirm_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pw.setPlaceholderText(t("confirm_password_ph"))
        plo.addWidget(self._confirm_pw)

        self._pw_status = QLabel("")
        self._pw_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pw_status.setVisible(False)
        plo.addWidget(self._pw_status)

        save_btn = accent_btn(t("save_password"))
        save_btn.clicked.connect(self._on_save_password)
        plo.addWidget(save_btn)

        layout.addWidget(pw_card)

        # PIN management (set first-time or change existing)
        layout.addSpacing(10)
        layout.addWidget(section_label(t("pin_section_title")))

        pin_card = QFrame()
        pin_card.setStyleSheet(f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; border: 1px solid {BORDER_COLOR}; }}")
        pin_lo = QVBoxLayout(pin_card)
        pin_lo.setContentsMargins(20, 20, 20, 20)
        pin_lo.setSpacing(12)

        pin_desc = QLabel(t("pin_section_desc"))
        pin_desc.setWordWrap(True)
        pin_desc.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px; background: transparent;")
        pin_lo.addWidget(pin_desc)

        pin_lo.addWidget(field_label(t("current_pin_ph")))
        self._current_pin = QLineEdit()
        self._current_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self._current_pin.setPlaceholderText(t("current_pin_optional_ph"))
        self._current_pin.setMaxLength(6)
        pin_lo.addWidget(self._current_pin)

        pin_lo.addWidget(field_label(t("new_pin_ph"), required=True))
        self._new_pin = QLineEdit()
        self._new_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pin.setPlaceholderText("••••••")
        self._new_pin.setMaxLength(6)
        pin_lo.addWidget(self._new_pin)

        pin_lo.addWidget(field_label(t("confirm_pin_ph"), required=True))
        self._confirm_pin = QLineEdit()
        self._confirm_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pin.setPlaceholderText("••••••")
        self._confirm_pin.setMaxLength(6)
        self._confirm_pin.returnPressed.connect(self._on_save_pin)
        pin_lo.addWidget(self._confirm_pin)

        self._pin_status = QLabel("")
        self._pin_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pin_status.setVisible(False)
        pin_lo.addWidget(self._pin_status)

        save_pin_btn = accent_btn(t("save_pin"))
        save_pin_btn.clicked.connect(self._on_save_pin)
        pin_lo.addWidget(save_pin_btn)

        layout.addWidget(pin_card)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_data(self) -> None:
        pass

    def _validate_pin_fields(self, new_pin: str, confirm_pin: str) -> str | None:
        """Return an error key string if invalid, else None."""
        if not new_pin or not confirm_pin:
            return t("pin_required")
        if not new_pin.isdigit() or len(new_pin) != 6:
            return t("pin_digits_only")
        if new_pin != confirm_pin:
            return t("pin_mismatch")
        return None

    def _on_save_pin(self) -> None:
        current = self._current_pin.text().strip()
        new_pin = self._new_pin.text().strip()
        confirm = self._confirm_pin.text().strip()

        err = self._validate_pin_fields(new_pin, confirm)
        if err:
            if "match" in err.lower() or "မတူ" in err:
                self._confirm_pin.clear()
                self._confirm_pin.setFocus()
            self._show_pin_status(err, True)
            return

        try:
            if current:
                self._api.change_pin(current, new_pin)
                self._show_pin_status(t("change_pin_success"), False)
            else:
                user_id = (self._api.user or {}).get("id")
                if user_id is None:
                    self._show_pin_status("User ID not found. Please re-login.", True)
                    return
                self._api.set_user_pin(user_id, new_pin)
                self._show_pin_status(t("pin_success"), False)
            self._current_pin.clear()
            self._new_pin.clear()
            self._confirm_pin.clear()
        except Exception as e:
            self._show_pin_status(f"Error: {e}", True)
            if current:
                self._current_pin.clear()
                self._current_pin.setFocus()

    def _show_pin_status(self, msg: str, error: bool) -> None:
        self._pin_status.setText(msg)
        self._pin_status.setStyleSheet(f"color: {ERROR_COLOR if error else SUCCESS_COLOR}; font-size: 12px;")
        self._pin_status.setVisible(True)

    def _on_save_password(self) -> None:
        try:
            old = self._old_pw.text()
            new = self._new_pw.text()
            confirm = self._confirm_pw.text()
            if not old or not new:
                self._show_pw_status(t("pw_required"), True)
                return
            if new != confirm:
                self._show_pw_status(t("pw_mismatch"), True)
                return
            self._api.change_password(old, new)
            self._show_pw_status(t("pw_success"), False)
            self._old_pw.clear()
            self._new_pw.clear()
            self._confirm_pw.clear()
        except Exception as e:
            self._show_pw_status(f"Error: {e}", True)

    def _show_pw_status(self, msg: str, error: bool) -> None:
        self._pw_status.setText(msg)
        self._pw_status.setStyleSheet(f"color: {ERROR_COLOR if error else SUCCESS_COLOR}; font-size: 12px;")
        self._pw_status.setVisible(True)
