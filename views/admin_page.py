"""
views/admin_page.py

Inline sub-view widgets used by the unified DashboardView sidebar.

  ExchangeRateSubView   — Exchange Rate settings page
  CommissionTierSubView — Commission Tiers management page
  PasswordSubView       — Change Password page

Note: AdminPage (the old two-panel layout with its own sidebar) has been
removed. All navigation is now handled by the single unified sidebar in
DashboardView (views/dashboard_view.py).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n import t
from services.api_client import ApiClient
from views.widgets.company_selector import CompanySelector, ServiceTypeSelector, add_placeholder

# ── Theme constants ───────────────────────────────────────────────────────────
BG_DARK     = "#1e1e2e"
BG_SIDEBAR  = "#181825"
BG_CARD     = "#2a2a3e"
BG_CONTENT  = "#1e1e2e"
BG_INPUT    = "#313244"
TEXT_PRIMARY   = "#cdd6f4"
TEXT_SECONDARY = "#a6adc8"
TEXT_MUTED     = "#6c7086"
ACCENT_BLUE    = "#89b4fa"
ACCENT_GREEN   = "#a6e3a1"
ACCENT_RED     = "#f38ba8"
ACCENT_YELLOW  = "#f9e2af"
BORDER_COLOR   = "#313244"
INPUT_BORDER   = "#585b70"


# ── Shared widget helpers ───────────────────────────────────────────────────

def _accent_btn(text: str, color: str = ACCENT_BLUE) -> QPushButton:
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton {{ background-color: {color}; color: {BG_DARK}; "
        f"border: none; border-radius: 6px; padding: 8px 18px; "
        f"font-size: 13px; font-weight: bold; }}"
        f"QPushButton:hover {{ background-color: {color}cc; }}"
    )
    return btn


def _card() -> QFrame:
    f = QFrame()
    f.setStyleSheet(
        f"QFrame {{ background-color: {BG_CARD}; border-radius: 10px; "
        f"border: 1px solid {BORDER_COLOR}; }}"
    )
    return f


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
    lbl.setStyleSheet(f"color: {TEXT_PRIMARY};")
    return lbl


def _scrollable() -> tuple["QScrollArea", "QVBoxLayout"]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("border: none;")
    container = QWidget()
    container.setStyleSheet(f"background-color: {BG_CONTENT};")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(24, 20, 24, 24)
    layout.setSpacing(16)
    scroll.setWidget(container)
    return scroll, layout


def _status_lbl() -> QLabel:
    lbl = QLabel("")
    lbl.setVisible(False)
    lbl.setFont(QFont("Segoe UI", 12))
    return lbl


def _set_ok(lbl: QLabel, msg: str) -> None:
    lbl.setText(msg)
    lbl.setStyleSheet(f"color: {ACCENT_GREEN};")
    lbl.setVisible(True)


def _set_err(lbl: QLabel, msg: str) -> None:
    lbl.setText(msg)
    lbl.setStyleSheet(f"color: {ACCENT_RED};")
    lbl.setVisible(True)


# ════════════════════════════════════════════════════════════
# Inline sub-view: Exchange Rate
# ════════════════════════════════════════════════════════════
class ExchangeRateSubView(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = _scrollable()
        layout.addWidget(_section_label(t("settings_exrate")))

        card = _card()
        lo = QVBoxLayout(card)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(12)

        self._current_lbl = QLabel(t("current_rate_placeholder"))
        self._current_lbl.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px;")
        lo.addWidget(self._current_lbl)

        self._hint_lbl = QLabel("")
        self._hint_lbl.setStyleSheet(
            f"color: {TEXT_MUTED}; font-size: 11px; font-style: italic;"
        )
        lo.addWidget(self._hint_lbl)

        # Base amount row
        row0 = QHBoxLayout()
        row0.addWidget(QLabel(t("base_amount_thb")))
        self._base_input = QLineEdit()
        self._base_input.setPlaceholderText("1")
        self._base_input.setFixedWidth(90)
        self._base_input.textChanged.connect(self._on_input_changed)
        row0.addWidget(self._base_input)
        row0.addStretch()
        lo.addLayout(row0)

        # Buy / Sell row
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(t("buy_rate_label")))
        self._buy_input = QLineEdit()
        self._buy_input.setPlaceholderText("128.2100")
        self._buy_input.textChanged.connect(self._on_input_changed)
        row1.addWidget(self._buy_input)
        row1.addSpacing(20)
        row1.addWidget(QLabel(t("sell_rate_label")))
        self._sell_input = QLineEdit()
        self._sell_input.setPlaceholderText("128.2100")
        self._sell_input.textChanged.connect(self._on_input_changed)
        row1.addWidget(self._sell_input)
        row1.addStretch()
        lo.addLayout(row1)

        save_btn = _accent_btn(t("save_rate"))
        save_btn.clicked.connect(self._on_save)
        lo.addWidget(save_btn)

        self._status = _status_lbl()
        lo.addWidget(self._status)

        layout.addWidget(card)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_data(self) -> None:
        try:
            rate = self._api.get_exchange_rate()
            base = float(rate.get("base_amount") or 1)
            buy  = float(rate.get("buy_rate") or 0)
            sell = float(rate.get("sell_rate") or 0)
            self._current_lbl.setText(
                f"Current:  {base:g} THB — Buy {buy:.4f} MMK  |  Sell {sell:.4f} MMK"
            )
            self._base_input.setText(f"{base:g}")
            self._buy_input.setText(f"{buy:.4f}" if buy else "")
            self._sell_input.setText(f"{sell:.4f}" if sell else "")
            self._update_hint(base, sell)
        except Exception:
            pass

    def _on_input_changed(self) -> None:
        try:
            base = float(self._base_input.text() or 1)
            sell = float(self._sell_input.text())
            self._update_hint(base, sell)
        except (ValueError, AttributeError):
            pass

    def _update_hint(self, base: float, sell: float) -> None:
        if sell > 0 and base > 0:
            eff = sell / base
            thb = round(100_000 / eff, 2)
            self._hint_lbl.setText(
                f"{base:g} THB = {sell:,.4f} MMK  |  "
                f"100,000 MMK = {thb:,.2f} THB  |  1 THB = {eff:,.4f} MMK"
            )
        else:
            self._hint_lbl.setText("")

    def _on_save(self) -> None:
        try:
            base = float(self._base_input.text() or 1)
            buy  = float(self._buy_input.text())
            sell = float(self._sell_input.text())
            self._api.update_exchange_rate(buy, sell, base_amount=base)
            _set_ok(self._status, t("rate_saved"))
            self.load_data()
        except Exception as e:
            _set_err(self._status, f"Error: {e}")


# ════════════════════════════════════════════════════════════
# Inline sub-view: Commission Tiers
# ════════════════════════════════════════════════════════════
class CommissionTierSubView(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._tiers_data: list[dict] = []
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = _scrollable()
        layout.addWidget(_section_label(t("settings_tiers")))

        card = _card()
        lo = QVBoxLayout(card)
        lo.setContentsMargins(20, 16, 20, 16)
        lo.setSpacing(10)

        # Filter row
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(t("field_company") + ":"))
        self._company_sel = CompanySelector()
        self._company_sel.setFixedWidth(165)
        self._company_sel.company_changed.connect(self._on_company_changed)
        filter_row.addWidget(self._company_sel)
        filter_row.addWidget(QLabel(t("field_service_type") + ":"))
        self._st_sel = ServiceTypeSelector()
        self._st_sel.setFixedWidth(165)
        filter_row.addWidget(self._st_sel)
        load_btn = _accent_btn(t("btn_load"))
        load_btn.clicked.connect(self._load_tiers)
        filter_row.addWidget(load_btn)
        filter_row.addStretch()
        lo.addLayout(filter_row)

        # Tier table
        _COLS = [
            t("col_id"), t("tier_col_from"), t("tier_col_to"),
            t("tier_col_fee_type"), t("tier_col_fee_dep"), t("tier_col_fee_with"),
            t("tier_col_comm_type"), t("tier_col_comm_dep"), t("tier_col_comm_with"),
            t("tier_col_add_type"), t("tier_col_add_dep"), t("tier_col_add_with"),
            t("tier_col_delete"),
        ]
        self._table = QTableWidget(0, len(_COLS))
        self._table.setHorizontalHeaderLabels(_COLS)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setMinimumHeight(240)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        hdr = self._table.horizontalHeader()
        hdr.setStretchLastSection(False)
        for i in range(len(_COLS)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        lo.addWidget(self._table)

        # Add form — row 1: range
        r1 = QHBoxLayout()
        r1.addWidget(QLabel(t("tier_from_amount")))
        self._new_from = QLineEdit(); self._new_from.setPlaceholderText("0"); self._new_from.setFixedWidth(85)
        r1.addWidget(self._new_from)
        r1.addWidget(QLabel(t("tier_to_amount")))
        self._new_to = QLineEdit(); self._new_to.setPlaceholderText("0"); self._new_to.setFixedWidth(85)
        r1.addWidget(self._new_to)
        r1.addStretch()
        lo.addLayout(r1)

        # Add form — row 2: fee
        r2 = QHBoxLayout()
        r2.addWidget(QLabel(t("tier_fee_type")))
        self._new_fee_type = QComboBox(); add_placeholder(self._new_fee_type); self._new_fee_type.addItems(["FIXED", "PERCENTAGE"]); self._new_fee_type.setFixedWidth(115)
        r2.addWidget(self._new_fee_type)
        r2.addWidget(QLabel(t("tier_fee_dep")))
        self._new_fee = QLineEdit(); self._new_fee.setPlaceholderText("0"); self._new_fee.setFixedWidth(85)
        r2.addWidget(self._new_fee)
        r2.addWidget(QLabel(t("tier_fee_with")))
        self._new_fee_w = QLineEdit(); self._new_fee_w.setPlaceholderText("0"); self._new_fee_w.setFixedWidth(85)
        r2.addWidget(self._new_fee_w)
        r2.addStretch()
        lo.addLayout(r2)

        # Add form — row 3: commission
        r3 = QHBoxLayout()
        r3.addWidget(QLabel(t("tier_comm_type")))
        self._new_comm_type = QComboBox(); add_placeholder(self._new_comm_type); self._new_comm_type.addItems(["FIXED", "PERCENTAGE"]); self._new_comm_type.setFixedWidth(115)
        r3.addWidget(self._new_comm_type)
        r3.addWidget(QLabel(t("tier_comm_dep")))
        self._new_comm_dep = QLineEdit(); self._new_comm_dep.setPlaceholderText("0"); self._new_comm_dep.setFixedWidth(85)
        r3.addWidget(self._new_comm_dep)
        r3.addWidget(QLabel(t("tier_comm_with")))
        self._new_comm_w = QLineEdit(); self._new_comm_w.setPlaceholderText("0"); self._new_comm_w.setFixedWidth(85)
        r3.addWidget(self._new_comm_w)
        r3.addStretch()
        lo.addLayout(r3)

        # Add form — row 4: additional fee + submit
        r4 = QHBoxLayout()
        r4.addWidget(QLabel(t("tier_add_type")))
        self._new_add_type = QComboBox(); add_placeholder(self._new_add_type); self._new_add_type.addItems(["FIXED", "PERCENTAGE"]); self._new_add_type.setFixedWidth(115)
        r4.addWidget(self._new_add_type)
        r4.addWidget(QLabel(t("tier_add_dep")))
        self._new_add_dep = QLineEdit(); self._new_add_dep.setPlaceholderText("0"); self._new_add_dep.setFixedWidth(85)
        r4.addWidget(self._new_add_dep)
        r4.addWidget(QLabel(t("tier_add_with")))
        self._new_add_w = QLineEdit(); self._new_add_w.setPlaceholderText("0"); self._new_add_w.setFixedWidth(85)
        r4.addWidget(self._new_add_w)
        add_btn = _accent_btn(t("add_tier"), ACCENT_GREEN)
        add_btn.clicked.connect(self._on_add)
        r4.addWidget(add_btn)
        r4.addStretch()
        lo.addLayout(r4)

        self._status = _status_lbl()
        lo.addWidget(self._status)

        layout.addWidget(card)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_data(self) -> None:
        try:
            companies = self._api.get_companies()
        except Exception:
            companies = []
        self._company_sel.populate(companies, self._api)
        self._load_tiers()

    def _on_company_changed(self, company_id: int) -> None:
        try:
            sts = self._api.get_service_types(company_id)
        except Exception:
            sts = []
        self._st_sel.populate(sts)

    def _load_tiers(self) -> None:
        st_id = self._st_sel.selected_service_type_id()
        if st_id is None:
            self._table.setRowCount(0)
            return
        try:
            tiers = self._api.get_commission_tiers(st_id)
            self._tiers_data = tiers
            self._table.setRowCount(len(tiers))
            for row, tier in enumerate(tiers):
                af = tier.get("amount_from")
                at_ = tier.get("amount_to")
                cells = [
                    str(tier.get("id", "")),
                    f"{float(af):,.0f}" if af is not None else "—",
                    f"{float(at_):,.0f}" if at_ is not None else "—",
                    tier.get("fee_amount_type") or "FIXED",
                    f"{float(tier.get('fee_amount_deposit') or 0):,.4g}",
                    f"{float(tier.get('fee_amount_withdraw') or 0):,.4g}",
                    tier.get("comm_type") or "FIXED",
                    f"{float(tier.get('comm_deposit') or 0):,.4g}",
                    f"{float(tier.get('comm_withdraw') or 0):,.4g}",
                    tier.get("additional_fee_type") or "FIXED",
                    f"{float(tier.get('additional_fee_deposit_amount') or 0):,.4g}",
                    f"{float(tier.get('additional_fee_withdraw_amount') or 0):,.4g}",
                ]
                for col, text in enumerate(cells):
                    item = QTableWidgetItem(text)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self._table.setItem(row, col, item)
                del_btn = QPushButton(t("tier_col_delete"))
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.setStyleSheet(
                    f"QPushButton {{ background: {BG_DARK}; color: {ACCENT_RED}; "
                    f"border: none; border-radius: 4px; padding: 4px 8px; font-size: 11px; }}"
                )
                del_btn.clicked.connect(lambda _, tid=tier["id"]: self._on_delete(tid))
                self._table.setCellWidget(row, 12, del_btn)
        except Exception:
            pass

    def _on_add(self) -> None:
        st_id = self._st_sel.selected_service_type_id()
        if st_id is None:
            _set_err(self._status, t("err_select_service_type"))
            return
        if (self._new_fee_type.currentIndex() <= 0
                or self._new_comm_type.currentIndex() <= 0
                or self._new_add_type.currentIndex() <= 0):
            _set_err(self._status, "Please select all fee/commission types.")
            return
        # Client-side range validation
        af_text = self._new_from.text().strip()
        at_text = self._new_to.text().strip()
        if not af_text or float(af_text) == 0:
            _set_err(self._status, t("err_tier_from_required"))
            return
        if not at_text or float(at_text) == 0:
            _set_err(self._status, t("err_tier_to_required"))
            return
        af_val = float(af_text)
        at_val = float(at_text)
        if at_val <= af_val:
            _set_err(self._status, t("err_tier_range_order"))
            return
        for tier in self._tiers_data:
            ef = tier.get("amount_from")
            et = tier.get("amount_to")
            if ef is None or et is None:
                continue
            if af_val < float(et) and at_val > float(ef):
                _set_err(self._status, t("err_tier_overlap").format(
                    af=f"{af_val:,.0f}", at=f"{at_val:,.0f}",
                    ef=f"{float(ef):,.0f}", et=f"{float(et):,.0f}",
                ))
                return
        try:
            data = {
                "service_type_id": st_id,
                "amount_from": af_val,
                "amount_to":   at_val,
                "fee_amount_type":     self._new_fee_type.currentText(),
                "fee_amount_deposit":  float(self._new_fee.text()   or 0),
                "fee_amount_withdraw": float(self._new_fee_w.text()  or 0),
                "comm_type":           self._new_comm_type.currentText(),
                "comm_deposit":        float(self._new_comm_dep.text() or 0),
                "comm_withdraw":       float(self._new_comm_w.text()   or 0),
                "additional_fee_type":             self._new_add_type.currentText(),
                "additional_fee_deposit_amount":   float(self._new_add_dep.text() or 0),
                "additional_fee_withdraw_amount":  float(self._new_add_w.text()   or 0),
            }
            self._api.create_commission_tier(data)
            for w in (self._new_from, self._new_to, self._new_fee, self._new_fee_w,
                      self._new_comm_dep, self._new_comm_w, self._new_add_dep, self._new_add_w):
                w.clear()
            _set_ok(self._status, t("tier_added"))
            self._load_tiers()
        except Exception as e:
            _set_err(self._status, f"Error: {e}")

    def _on_delete(self, tier_id: int) -> None:
        try:
            self._api.delete_commission_tier(tier_id)
            self._load_tiers()
        except Exception:
            pass


# ════════════════════════════════════════════════════════════
# Inline sub-view: Change Password
# ════════════════════════════════════════════════════════════
class PasswordSubView(QWidget):
    def __init__(self, api: ApiClient) -> None:
        super().__init__()
        self._api = api
        self._init_ui()

    def _init_ui(self) -> None:
        scroll, layout = _scrollable()
        layout.addWidget(_section_label(t("change_password")))

        card = _card()
        lo = QVBoxLayout(card)
        lo.setContentsMargins(24, 20, 24, 20)
        lo.setSpacing(12)

        self._old_pw = QLineEdit()
        self._old_pw.setPlaceholderText(t("current_password_ph"))
        self._old_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._old_pw.setStyleSheet(
            f"QLineEdit {{ background: {BG_INPUT}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {INPUT_BORDER}; border-radius: 6px; padding: 10px 14px; font-size: 13px; }}"
            f"QLineEdit:focus {{ border: 1px solid {ACCENT_BLUE}; }}"
        )
        lo.addWidget(self._old_pw)

        self._new_pw = QLineEdit()
        self._new_pw.setPlaceholderText(t("new_password_ph"))
        self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pw.setStyleSheet(self._old_pw.styleSheet())
        lo.addWidget(self._new_pw)

        self._confirm_pw = QLineEdit()
        self._confirm_pw.setPlaceholderText(t("confirm_password_ph"))
        self._confirm_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_pw.setStyleSheet(self._old_pw.styleSheet())
        lo.addWidget(self._confirm_pw)

        save_btn = _accent_btn(t("save_password"))
        save_btn.clicked.connect(self._on_save)
        lo.addWidget(save_btn)

        self._status = _status_lbl()
        lo.addWidget(self._status)

        layout.addWidget(card)
        layout.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def load_data(self) -> None:
        pass  # nothing to pre-load

    def _on_save(self) -> None:
        old     = self._old_pw.text()
        new     = self._new_pw.text()
        confirm = self._confirm_pw.text()
        if not old or not new:
            _set_err(self._status, t("pw_required"))
            return
        if new != confirm:
            _set_err(self._status, t("pw_mismatch"))
            return
        try:
            self._api.change_password(old, new)
            _set_ok(self._status, t("pw_success"))
            self._old_pw.clear()
            self._new_pw.clear()
            self._confirm_pw.clear()
        except Exception as e:
            _set_err(self._status, f"Error: {e}")


# AdminPage has been removed — navigation is now handled by the unified
# sidebar in views/dashboard_view.py. The three sub-view classes above
# (ExchangeRateSubView, CommissionTierSubView, PasswordSubView) are
# imported directly by DashboardView.
