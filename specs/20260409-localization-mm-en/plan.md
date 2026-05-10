# Localization (Myanmar / English) — Implementation Plan

**Spec identifier**: localization-mm-en
**Status**: Draft
**Estimated Complexity**: Medium
**Estimated Duration**: 3–5 days (solo developer)
**Date**: 2026-04-09

---

## 1. Overview

Add bilingual (Myanmar — `mm`, English — `en`) localization to every user-facing
string in the Ngwe Lwe cashier system. Myanmar is the default language. The
selected language must persist across application restarts and must be switchable
at runtime without restarting the application.

---

## 2. Technical Approach

### 2.1 Architecture — dict-based i18n module

A lightweight, zero-dependency i18n module will live at `i18n/i18n.py`. It owns:

- A nested dict of all translatable strings, keyed by string key then locale code.
- The currently active locale (default `"mm"`).
- A `t(key)` lookup function.
- A persistence layer (reads/writes the `client_config.json` file already used by
  `run_client.py`).
- A signal mechanism so that views can re-render their labels when the locale
  changes at runtime.

No Qt Linguist, no `.ts`/`.qm` files, no third-party packages.

### 2.2 Module layout

```
ngwe-lwe-system/
  i18n/
    __init__.py          # re-exports t(), set_locale(), get_locale(), on_change()
    i18n.py              # I18n singleton + translation dict
  views/
    login_view.py        # patched to call t()
    dashboard_view.py    # patched
    transaction_view.py  # patched
    cashier_view.py      # patched
    receive_float_dialog.py  # patched
  run_client.py          # patched — language switcher widget added to LoginView
```

### 2.3 Persistence

The existing `client_config.json` file (already read/written by `run_client.py`)
will gain a `"language"` key:

```json
{
  "host": "192.168.1.1",
  "port": 8000,
  "language": "mm"
}
```

The i18n module loads this key on import. `run_client.py` already calls
`save_config()` on successful connect; that function will be extended to also
persist the current locale.

### 2.4 Runtime language switching

A language toggle control (described in section 4.3) emits a signal when the
user changes language. All live views subscribe to this signal via a central
`language_changed` hook and call `retranslate_ui()` on themselves.

### 2.5 Font handling

Myanmar text in Pyqt6 renders correctly with the **Padauk** or **Zawgyi** fonts
if installed. The existing `"Segoe UI"` font family will be supplemented: the
i18n module will expose `ui_font(size)` that returns `QFont("Padauk", size)` for
`"mm"` and `QFont("Segoe UI", size)` for `"en"`.

[NEEDS CLARIFICATION: Which Myanmar font is installed on the target machines —
Padauk (Unicode), Zawgyi, or another? This affects the translation strings: Zawgyi
uses a legacy encoding that differs from standard Unicode Myanmar. The plan assumes
Unicode (Padauk) unless told otherwise.]

---

## 3. Translation Dictionary Structure

The full dict lives inside `i18n/i18n.py`.  Each key is a stable English
identifier; each value is a sub-dict with `"mm"` and `"en"` entries.

```python
TRANSLATIONS: dict[str, dict[str, str]] = {
    # ── General ──
    "app_title":            {"mm": "ငွေလွှဲ System",           "en": "NgweLwe System"},
    "logout":               {"mm": "ထွက်မည်",                 "en": "Logout"},
    "refresh":              {"mm": "ပြန်ဆွဲမည်",               "en": "Refresh"},
    "cancel":               {"mm": "မလုပ်ပါ",                  "en": "Cancel"},
    "save":                 {"mm": "သိမ်းမည်",                  "en": "Save"},
    "close":                {"mm": "ပိတ်မည်",                   "en": "Close"},
    "search":               {"mm": "ရှာမည်",                    "en": "Search"},
    "load_more":            {"mm": "ထပ်ဆောင်းကြည့်မည်",        "en": "Load More"},
    "view":                 {"mm": "ကြည့်မည်",                  "en": "View"},
    "back":                 {"mm": "← နောက်သို့",              "en": "← Back"},
    "no_file_selected":     {"mm": "ဖိုင်မရွေးရသေး",           "en": "No file selected"},
    "attach_screenshot":    {"mm": "Screenshot တင်မည်",        "en": "Attach Screenshot"},
    "active":               {"mm": "အသုံးပြုနေဆဲ",            "en": "Active"},
    "inactive":             {"mm": "ပိတ်ထားသည်",               "en": "Inactive"},
    "activate":             {"mm": "ဖွင့်မည်",                  "en": "Activate"},
    "deactivate":           {"mm": "ပိတ်မည်",                   "en": "Deactivate"},
    "error_prefix":         {"mm": "အမှား:",                    "en": "Error:"},
    "all":                  {"mm": "အားလုံး",                   "en": "All"},
    "language":             {"mm": "ဘာသာစကား",                 "en": "Language"},

    # ── Login ──
    "login_title":          {"mm": "ငွေလွှဲ System",           "en": "NgweLwe System"},
    "username_placeholder": {"mm": "အသုံးပြုသူအမည်",           "en": "Username"},
    "password_placeholder": {"mm": "စကားဝှက်",                 "en": "Password"},
    "sign_in":              {"mm": "ဝင်မည်",                    "en": "Sign In"},
    "signing_in":           {"mm": "ဝင်နေသည်...",               "en": "Signing in..."},
    "login_empty_error":    {"mm": "အသုံးပြုသူအမည်နှင့် စကားဝှက် ထည့်ပါ။",
                             "en": "Please enter your username and password."},
    "login_fail":           {"mm": "ဝင်ရောက်မရပါ။ ဆာဗာ ချိတ်ဆက်မှုကို စစ်ဆေးပါ။",
                             "en": "Sign-in failed. Please check your server connection."},

    # ── Home / Welcome ──
    "welcome":              {"mm": "ကြိုဆိုပါသည်",              "en": "Welcome"},
    "new_transaction":      {"mm": "ငွေလွှဲသစ်",               "en": "New Transaction"},
    "new_transaction_desc": {"mm": "ငွေလွှဲ အသစ်ဖန်တီးမည်",    "en": "Create a new transaction"},
    "txn_history":          {"mm": "ငွေလွှဲမှတ်တမ်း",           "en": "Transaction History"},
    "txn_history_desc":     {"mm": "ယခင်ငွေလွှဲများ ကြည့်ရှုမည်", "en": "View past transactions"},
    "my_profile":           {"mm": "ကျွန်ုပ်၏ပရိုဖိုင်",       "en": "My Profile"},
    "my_profile_desc":      {"mm": "အကောင့်ဆက်တင်",             "en": "Account settings"},

    # ── Sidebar navigation ──
    "nav_dashboard":        {"mm": "ဒက်ရှ်ဘုတ်",               "en": "Dashboard"},
    "nav_transactions":     {"mm": "ငွေလွှဲများ",               "en": "Transactions"},
    "nav_accounts":         {"mm": "အကောင့်များ",               "en": "Accounts"},
    "nav_reports":          {"mm": "အစီရင်ခံစာ",               "en": "Reports"},
    "nav_users":            {"mm": "အသုံးပြုသူများ",            "en": "Users"},
    "nav_settings":         {"mm": "ဆက်တင်",                    "en": "Settings"},
    "nav_vault":            {"mm": "ငွေသေတ္တာ",                 "en": "Vault"},
    "nav_issue_float":      {"mm": "ငွေဆောင်ပေးမည်",           "en": "Issue Float"},
    "nav_shifts":           {"mm": "အလှည့်ကျများ",              "en": "Shifts"},
    "sidebar_cashier":      {"mm": "ငွေကိုင်",                  "en": "Cashier"},

    # ── Dashboard stats ──
    "todays_cash_ins":      {"mm": "ယနေ့ ငွေသွင်းစုစုပေါင်း",  "en": "Today's CashIns"},
    "todays_cash_outs":   {"mm": "ယနေ့ ငွေထုတ်စုစုပေါင်း",   "en": "Today's CashOuts"},
    "transfers":            {"mm": "လွှဲငွေများ",                "en": "Transfers"},
    "exchange":             {"mm": "ငွေလဲလှယ်",                 "en": "Exchange"},
    "fees_commission":      {"mm": "ကြေးနှင့် ကော်မရှင်",      "en": "Fees & Commission"},
    "todays_summary":       {"mm": "ယနေ့ အနှစ်ချုပ်",          "en": "Today's Summary"},
    "account_balances":     {"mm": "အကောင့်လက်ကျန်ငွေ",        "en": "Account Balances"},
    "recent_transactions":  {"mm": "မကြာမီ ငွေလွှဲများ",       "en": "Recent Transactions"},

    # ── Transaction table headers ──
    "col_time":             {"mm": "အချိန်",                    "en": "Time"},
    "col_employee":         {"mm": "ဝန်ထမ်း",                   "en": "Employee"},
    "col_type":             {"mm": "အမျိုးအစား",                 "en": "Type"},
    "col_service":          {"mm": "ဝန်ဆောင်မှု",               "en": "Service"},
    "col_account":          {"mm": "အကောင့်",                   "en": "Account"},
    "col_amount":           {"mm": "ပမာဏ",                      "en": "Amount"},
    "col_commission":       {"mm": "ကော်မရှင်",                 "en": "Commission"},
    "col_fee":              {"mm": "ကြေး",                       "en": "Fee"},
    "col_screenshot":       {"mm": "ဓာတ်ပုံ",                   "en": "Screenshot"},
    "col_id":               {"mm": "ID",                         "en": "ID"},
    "col_date_time":        {"mm": "ရက်/အချိန်",                 "en": "Date / Time"},
    "col_customer":         {"mm": "ဖောက်သည်",                  "en": "Customer"},
    "col_amount_mmk":       {"mm": "ပမာဏ (MMK)",                 "en": "Amount (MMK)"},
    "col_fee_mmk":          {"mm": "ကြေး (MMK)",                 "en": "Fee (MMK)"},
    "col_staff":            {"mm": "ဝန်ထမ်း",                   "en": "Staff"},
    "col_cash_status":      {"mm": "ငွေသားအခြေအနေ",            "en": "Cash Status"},
    "col_action":           {"mm": "လုပ်ဆောင်ချက်",             "en": "Action"},
    "col_status":           {"mm": "အခြေအနေ",                   "en": "Status"},
    "col_float_amount":     {"mm": "Float ငွေပမာဏ",             "en": "Float Amount"},
    "col_issued_by":        {"mm": "ထုတ်ပေးသူ",                 "en": "Issued By"},
    "col_issued_at":        {"mm": "ထုတ်ပေးသောအချိန်",          "en": "Issued At"},
    "col_received_at":      {"mm": "လက်ခံသောအချိန်",            "en": "Received At"},
    "col_closed_at":        {"mm": "ပိတ်သောအချိန်",             "en": "Closed At"},

    # ── Transaction form ──
    "transaction":          {"mm": "ငွေလွှဲ",                   "en": "Transaction"},
    "action_cash_in":       {"mm": "ငွေသွင်း",                  "en": "CashIn"},
    "action_cash_out":      {"mm": "ငွေထုတ်",                   "en": "CashOut"},
    "action_transfer":      {"mm": "လွှဲပြောင်း",               "en": "Transfer"},
    "action_exchange":      {"mm": "ငွေလဲ",                     "en": "Exchange"},
    "field_service":        {"mm": "ဝန်ဆောင်မှု",               "en": "Service"},
    "field_account":        {"mm": "အကောင့်",                   "en": "Account"},
    "field_to_account":     {"mm": "လက်ခံအကောင့်",              "en": "To Account"},
    "field_customer":       {"mm": "ဖောက်သည်အမည် / ဖုန်း",    "en": "Customer Name / Phone"},
    "customer_name_ph":     {"mm": "ဖောက်သည်အမည်",             "en": "Customer Name"},
    "customer_phone_ph":    {"mm": "ဖုန်းနံပါတ်",               "en": "Phone Number"},
    "field_currency":       {"mm": "ငွေကြေး",                   "en": "Currency"},
    "field_amount":         {"mm": "ပမာဏ",                      "en": "Amount"},
    "field_commission":     {"mm": "ကော်မရှင်",                 "en": "Commission"},
    "field_customer_fee":   {"mm": "ဖောက်သည်ကြေး (Tier)",      "en": "Customer Fee (from tier)"},
    "field_additional_fee": {"mm": "ထပ်ဆောင်းကြေး (Tier)",     "en": "Additional Fee (from tier)"},
    "field_total_fee":      {"mm": "ကြေးစုစုပေါင်း (→ ကြေးအကောင့်)",
                             "en": "Total Fee  (→ Fee Account)"},
    "field_fee_account":    {"mm": "ကြေးအကောင့်",               "en": "Fee Account"},
    "field_balance_change": {"mm": "လက်ကျန်ငွေပြောင်းလဲမှု",  "en": "Balance Change"},
    "field_note":           {"mm": "မှတ်ချက်",                  "en": "Note"},
    "note_placeholder":     {"mm": "ထပ်ဆောင်းမှတ်ချက်... (Ctrl+Enter နှိပ်ရင် မျဉ်းသစ်)",
                             "en": "Optional note... (Ctrl+Enter for new line)"},
    "select_placeholder":   {"mm": "— ရွေးပါ —",               "en": "— Select —"},
    "save_transaction":     {"mm": "ငွေလွှဲသိမ်းမည်",           "en": "Save Transaction"},
    "todays_transactions":  {"mm": "ယနေ့ ငွေလွှဲများ",         "en": "Today's Transactions"},

    # ── Transaction history filters ──
    "txn_history_title":    {"mm": "ငွေလွှဲမှတ်တမ်း",           "en": "Transaction History"},
    "filter_from":          {"mm": "မှ:",                        "en": "From:"},
    "filter_to":            {"mm": "သို့:",                     "en": "To:"},
    "filter_type":          {"mm": "အမျိုးအစား:",               "en": "Type:"},

    # ── Accounts page ──
    "accounts_title":       {"mm": "အကောင့်စီမံခန့်ခွဲမှု",     "en": "Accounts Management"},
    "col_service_id":       {"mm": "ဝန်ဆောင်မှု",               "en": "Service"},
    "col_name":             {"mm": "အမည်",                      "en": "Name"},
    "col_phone":            {"mm": "ဖုန်း",                     "en": "Phone"},
    "col_acc_type":         {"mm": "အကောင့်အမျိုးအစား",         "en": "Type"},
    "col_service_type":     {"mm": "ဝန်ဆောင်မှုအမျိုးအစား",    "en": "Service Type"},
    "col_balance":          {"mm": "လက်ကျန်ငွေ",               "en": "Balance"},
    "col_active":           {"mm": "အသုံးပြုနေဆဲ",             "en": "Active"},

    # ── Reports page ──
    "reports_title":        {"mm": "နေ့စဥ် အစီရင်ခံစာ",        "en": "Daily Report"},
    "date_label":           {"mm": "ရက်:",                      "en": "Date:"},
    "load_report":          {"mm": "အစီရင်ခံစာတင်မည်",         "en": "Load Report"},
    "total_cash_in":        {"mm": "ငွေသွင်းစုစုပေါင်း",        "en": "Total CashIn"},
    "total_cash_out":       {"mm": "ငွေထုတ်စုစုပေါင်း",         "en": "Total CashOut"},
    "total_transfer":       {"mm": "လွှဲပြောင်းစုစုပေါင်း",     "en": "Total Transfer"},
    "total_exchange":       {"mm": "ငွေလဲစုစုပေါင်း",          "en": "Total Exchange"},
    "total_commission":     {"mm": "ကော်မရှင်စုစုပေါင်း",       "en": "Total Commission"},
    "total_customer_fees":  {"mm": "ဖောက်သည်ကြေးစုစုပေါင်း",  "en": "Total Customer Fees"},
    "txn_count":            {"mm": "ငွေလွှဲအရေအတွက်",           "en": "Transaction Count"},

    # ── Settings page ──
    "settings_exrate":      {"mm": "ငွေလဲနှုန်း (THB/MMK)",    "en": "Exchange Rate  (base: THB / quote: MMK)"},
    "current_rate":         {"mm": "လက်ရှိ: —",                 "en": "Current: —"},
    "base_amount_thb":      {"mm": "အခြေခံပမာဏ (THB):",        "en": "Base Amount  (THB):"},
    "buy_rate_label":       {"mm": "ဝယ်နှုန်း (MMK/THB):",     "en": "Buy Rate  (MMK per base THB):"},
    "sell_rate_label":      {"mm": "ရောင်းနှုန်း (MMK/THB):",  "en": "Sell Rate  (MMK per base THB):"},
    "save_rate":            {"mm": "နှုန်းသိမ်းမည်",            "en": "Save Rate"},
    "settings_password":    {"mm": "စကားဝှက်ပြောင်းမည်",       "en": "Change Password"},
    "current_password_ph":  {"mm": "လက်ရှိစကားဝှက်",           "en": "Current Password"},
    "new_password_ph":      {"mm": "စကားဝှက်အသစ်",             "en": "New Password"},
    "confirm_password_ph":  {"mm": "စကားဝှက်အသစ် အတည်ပြုရန်", "en": "Confirm New Password"},
    "change_password_btn":  {"mm": "စကားဝှက်ပြောင်းမည်",       "en": "Change Password"},
    "settings_tiers":       {"mm": "ကော်မရှင် Tiers",           "en": "Commission Tiers"},
    "add_tier":             {"mm": "+ Tier ထည့်မည်",            "en": "+ Add Tier"},
    "pw_mismatch":          {"mm": "စကားဝှက် မတူပါ။",          "en": "Passwords do not match. Please try again."},
    "pw_required":          {"mm": "ကိုင်ရမည့် fields ဖြည့်ပါ။",
                             "en": "Please fill in all required fields."},
    "pw_success":           {"mm": "စကားဝှက် အောင်မြင်စွာ ပြောင်းပြီ။",
                             "en": "Password changed successfully."},
    "rate_saved":           {"mm": "ငွေလဲနှုန်း သိမ်းပြီ။",   "en": "Exchange rate saved successfully."},

    # ── Users page ──
    "users_title":          {"mm": "အသုံးပြုသူများ",            "en": "Users"},
    "add_user":             {"mm": "+ အသုံးပြုသူထည့်မည်",      "en": "+ Add User"},
    "col_username":         {"mm": "အသုံးပြုသူအမည်",           "en": "Username"},
    "col_fullname":         {"mm": "အမည်အပြည့်",                "en": "Full Name"},
    "col_role":             {"mm": "ရာထူး",                     "en": "Role"},
    "col_created":          {"mm": "ဖန်တီးသောရက်",             "en": "Created"},
    "add_user_dialog_title":{"mm": "အသုံးပြုသူထည့်မည်",        "en": "Add User"},
    "role_label":           {"mm": "ရာထူး:",                    "en": "Role:"},
    "all_fields_required":  {"mm": "Field အားလုံး ဖြည့်ရမည်။",  "en": "All fields are required."},

    # ── Vault page ──
    "vault_title":          {"mm": "ငွေသေတ္တာ အနှစ်ချုပ်",     "en": "Vault Overview"},
    "denom_balances":       {"mm": "ငွေတန်ဖိုးအလိုက် လက်ကျန်",  "en": "Denomination Balances"},
    "total_vault_value":    {"mm": "ငွေသေတ္တာ စုစုပေါင်း:",     "en": "Total Vault Value:"},
    "recent_vault_entries": {"mm": "မကြာမီ ငွေသေတ္တာမှတ်တမ်း", "en": "Recent Vault Entries"},
    "record_vault_entry":   {"mm": "ငွေသေတ္တာမှတ်တမ်းသွင်းမည်", "en": "Record Vault Entry"},
    "col_entry_type":       {"mm": "မှတ်တမ်းအမျိုးအစား",        "en": "Entry Type"},
    "col_denomination":     {"mm": "ငွေတန်ဖိုး",                "en": "Denomination"},
    "col_qty":              {"mm": "အရေအတွက်",                  "en": "Qty"},
    "col_value_mmk":        {"mm": "တန်ဖိုး (MMK)",             "en": "Value (MMK)"},
    "col_note":             {"mm": "မှတ်ချက်",                  "en": "Note"},

    # ── Issue Float page ──
    "issue_float_title":    {"mm": "ဝန်ထမ်းသို့ Float ပေးမည်",  "en": "Issue Float to Employee"},
    "employee_label":       {"mm": "ဝန်ထမ်း:",                  "en": "Employee:"},
    "denom_breakdown":      {"mm": "ငွေတန်ဖိုးအလိုက် ဖော်ပြချက်:", "en": "Denomination Breakdown:"},
    "col_quantity":         {"mm": "အရေအတွက်",                  "en": "Quantity"},
    "col_value":            {"mm": "တန်ဖိုး",                    "en": "Value"},
    "total_float_amount":   {"mm": "Float ငွေ စုစုပေါင်း:",     "en": "Total Float Amount:"},
    "note_optional":        {"mm": "မှတ်ချက် (မဖြစ်မနေမဟုတ်):", "en": "Note (optional):"},
    "morning_float_ph":     {"mm": "e.g. နံနက်ပိုင်း ငွေ",     "en": "e.g. Morning shift float"},
    "issue_float_btn":      {"mm": "Float ပေးမည်",              "en": "Issue Float"},
    "issuing_btn":          {"mm": "ပေးနေသည်...",               "en": "Issuing..."},
    "no_employee":          {"mm": "ဝန်ထမ်း မရွေးရသေး",         "en": "No employee selected"},
    "select_employee":      {"mm": "ဝန်ထမ်းရွေးပါ",             "en": "Please select an employee"},
    "float_zero_error":     {"mm": "Float ငွေ သုညထက် ကြီးရမည်", "en": "Float total must be greater than zero"},
    "float_success":        {"mm": "Float အောင်မြင်စွာ ပေးပြီ။ စုစုပေါင်း: {total} MMK",
                             "en": "Float issued successfully. Total: {total} MMK"},

    # ── Shifts page ──
    "shifts_title":         {"mm": "Float ခွဲဝေမှုများ",        "en": "Float Assignments"},

    # ── VaultEntryDialog ──
    "vault_in_title":       {"mm": "ငွေသေတ္တာသွင်းမည်",         "en": "Add Cash to Vault"},
    "vault_adj_title":      {"mm": "ငွေသေတ္တာ ပြင်ဆင်မည်",     "en": "Vault Adjustment"},
    "total_label":          {"mm": "စုစုပေါင်း:",               "en": "Total:"},
    "save_entry":           {"mm": "မှတ်တမ်းသိမ်းမည်",           "en": "Save Entry"},
    "total_nonzero":        {"mm": "စုစုပေါင်း သုညထက် ကြီးရမည်", "en": "Total must be greater than zero"},

    # ── FloatDetailDialog ──
    "issued_by_label":      {"mm": "ထုတ်ပေးသူ:",               "en": "Issued by:"},
    "total_amount_label":   {"mm": "စုစုပေါင်း:",               "en": "Total:"},
    "closing_total":        {"mm": "ပိတ်ချိန်ငွေပမာဏ:",         "en": "Closing total:"},
    "closed_at_label":      {"mm": "ပိတ်ချိန်:",                "en": "Closed:"},

    # ── CashApprovalDialog ──
    "cash_approval_title":  {"mm": "ငွေသားအတည်ပြု — Txn #{txn_id}",
                             "en": "Cash Approval — Txn #{txn_id}"},
    "cash_confirm_heading": {"mm": "ငွေသားလက်ခံအတည်ပြု — Txn #{txn_id}",
                             "en": "Cash Receipt Confirmation — Txn #{txn_id}"},
    "vault_in_hint":        {"mm": "ငွေသေတ္တာသွင်း — ဖောက်သည်ထံမှ ငွေလက်ခံ",
                             "en": "Vault In — Cash Received from Customer"},
    "vault_out_hint":       {"mm": "ငွေသေတ္တာထုတ် — ဖောက်သည်သို့ ငွေပေး",
                             "en": "Vault Out — Cash Dispensed to Customer"},
    "expected_label":       {"mm": "မျှော်မှန်း:",              "en": "Expected:"},
    "entered_label":        {"mm": "ထည့်သွင်းသည်:",             "en": "Entered:"},
    "difference_label":     {"mm": "ကွာခြားချက်:",              "en": "Difference:"},
    "morning_receipt_ph":   {"mm": "e.g. နံနက်ပိုင်း ရောင်းငွေ", "en": "e.g. Morning shift receipts"},
    "confirm_receipt_btn":  {"mm": "လက်ခံအတည်ပြုမည်",          "en": "Confirm Receipt"},
    "approved_badge":       {"mm": "✓ အတည်ပြုပြီ",             "en": "✓ Approved"},
    "pending_badge":        {"mm": "စောင့်ဆိုင်းဆဲ",            "en": "Pending"},

    # ── ReceiveFloatDialog ──
    "float_receipt_window": {"mm": "Float လက်ခံ — PIN အတည်ပြုမည်",
                             "en": "Float Receipt — PIN Confirmation"},
    "float_ready_title":    {"mm": "Float လက်ခံရန် အဆင်သင့်ဖြစ်ပြီ",
                             "en": "Float Ready for Collection"},
    "float_issued_info":    {"mm": "ထုတ်ပေးသူ: {issued_by}    |    စုစုပေါင်း: {total} MMK",
                             "en": "Issued by: {issued_by}    |    Total: {total} MMK"},
    "total_float_label":    {"mm": "Float ငွေ စုစုပေါင်း:",     "en": "Total Float:"},
    "pin_prompt":           {"mm": "PIN ၆ လုံး ထည့်ကာ လက်ခံကြောင်း အတည်ပြုပါ:",
                             "en": "Enter your 6-digit PIN to confirm receipt:"},
    "pin_invalid":          {"mm": "PIN ၆ လုံး ဂဏန်းဖြင့် ထည့်ရမည်။",
                             "en": "PIN must be exactly 6 digits."},
    "verifying":            {"mm": "စစ်ဆေးနေသည်...",            "en": "Verifying..."},

    # ── run_client ServerConfigDialog ──
    "server_conn_title":    {"mm": "Ngwe Lwe — ဆာဗာချိတ်ဆက်မည်",
                             "en": "Ngwe Lwe — Server Connection"},
    "server_config_box":    {"mm": "ဆာဗာ ဆက်တင်",             "en": "Server Configuration"},
    "server_ip_label":      {"mm": "ဆာဗာ IP:",                  "en": "Server IP:"},
    "port_label":           {"mm": "ဆိပ်ကမ်း:",                "en": "Port:"},
    "connect_btn":          {"mm": "ချိတ်ဆက်မည်",               "en": "Connect"},
    "connected_msg":        {"mm": "ချိတ်ဆက်ပြီ!",             "en": "Connected!"},
    "server_sub":           {"mm": "ဆာဗာ IP နှင့် Port ထည့်ပြီး Connect နှိပ်ပါ။",
                             "en": "Enter your server IP address and port, then click Connect."},
    "ip_required":          {"mm": "ဆာဗာ IP ထည့်ပါ။",          "en": "Please enter the server IP address."},
    "port_invalid":         {"mm": "Port သည် 1–65535 ဂဏန်းဖြစ်ရမည်။",
                             "en": "Port must be a number between 1 and 65535."},
    "ws_live":              {"mm": "● အသက်ဝင်နေ",               "en": "● Live"},
}
```

---

## 4. Implementation Phases

### Phase 1 — i18n Module (Day 1)

**Objective**: Build the standalone i18n module with no view dependencies.

**Tasks**:

1. Create `i18n/` package directory with `__init__.py`.
2. Create `i18n/i18n.py`:
   - Define `TRANSLATIONS` dict (full content as above).
   - Define `_locale: str = "mm"` module-level variable.
   - Implement `t(key: str, **kwargs) -> str`:
     - Looks up `TRANSLATIONS[key][_locale]`.
     - Falls back to `TRANSLATIONS[key]["en"]` if mm key missing.
     - Falls back to `key` itself if key not found (safe degradation).
     - Applies `str.format_map(kwargs)` for parameterised strings (e.g. `{total}`, `{txn_id}`).
   - Implement `set_locale(locale: str) -> None` — sets `_locale`, calls all
     registered listeners, persists to config.
   - Implement `get_locale() -> str`.
   - Implement `on_change(callback: Callable[[], None]) -> None` — registers a
     listener. Each view calls this in `__init__`.
   - Implement `_persist_locale(locale: str) -> None` — opens `client_config.json`,
     merges `"language"` key, writes back.
   - Implement `_load_persisted_locale() -> None` — called on module import,
     reads `"language"` from `client_config.json` if it exists.
   - Expose `ui_font(size: int, bold: bool = False) -> QFont` helper.
3. Create `i18n/__init__.py` exporting `t`, `set_locale`, `get_locale`, `on_change`,
   `ui_font`.
4. Write a quick smoke test (manual invocation, not a test suite) to confirm
   `t("logout")` returns `"ထွက်မည်"` and `t("logout")` returns `"Logout"` after
   calling `set_locale("en")`.

**Deliverable**: `i18n/` package importable by any view; `t("key")` returns correct
string for current locale.

**Dependencies**: None (no view changes yet).

---

### Phase 2 — login_view.py and run_client.py (Day 1–2)

**Objective**: Translate the first-seen UI (server config dialog and login screen)
and add the language toggle widget.

**Tasks**:

1. **Language toggle widget** — add a `QComboBox` or pair of `QRadioButton`s to
   `LoginView._init_ui()`:
   - Placed in the bottom footer area (same row as the existing
     `_server_label` / `_change_server_btn`).
   - Shows `"မြန်မာ / EN"` or a two-item combo: `["မြန်မာ (mm)", "English (en)"]`.
   - On change: calls `i18n.set_locale("mm")` or `i18n.set_locale("en")`.
   - Pre-selects the persisted locale on load.
2. Refactor `LoginView._init_ui()` to store references to all translatable
   widgets (`_title_label`, `_username_input`, `_password_input`, `_login_btn`).
3. Add `LoginView.retranslate_ui()` method — sets text/placeholder on all stored
   refs using `t()`.
4. Register `retranslate_ui` with `i18n.on_change()` in `__init__`.
5. Refactor `ServerConfigDialog` in `run_client.py` the same way:
   - Store refs to translatable widgets.
   - Add `retranslate_ui()`.
   - Register with `on_change`.
6. Update all hard-coded error/status strings in `_handle_login()`,
   `_on_connect()`, etc., to call `t()`.

**Deliverable**: Login screen and server-config dialog fully bilingual; language
toggle persists and retranslates both dialogs without restart.

**Dependencies**: Phase 1.

---

### Phase 3 — transaction_view.py (Day 2)

**Objective**: Translate employee-facing transaction UI.

**Tasks**:

1. Translate `ACTIONS` list — replace hard-coded English labels with `t()` calls.
   Note: `ACTIONS` is a module-level constant; move it inside `HomePage` or
   `TransactionFormPage.__init__` where `t()` can be called at construction time,
   or define action-key-to-label mapping and call `t()` per widget.
2. `HomePage`:
   - Store refs to welcome `QLabel`, card title/desc labels.
   - Add `retranslate_ui()`.
   - Register with `on_change`.
3. `TransactionFormPage`:
   - Replace all `field_label(...)` and `section_label(...)` calls that use
     hard-coded strings — store the resulting `QLabel` widgets as instance attrs
     so `retranslate_ui()` can update them.
   - Update `_save_btn`, `_screenshot_btn`, `_note_input` placeholder text.
   - Add `retranslate_ui()` and register with `on_change`.
4. `TransactionHistoryPage`:
   - Update table headers via `self._table.setHorizontalHeaderLabels([t(...), ...])`.
   - Update filter labels (`"From:"`, `"To:"`, `"Type:"`).
   - Add `retranslate_ui()` and register.
5. Helper functions `field_label()`, `section_label()`, `back_button()` — these
   already accept a `text` arg; callers will now pass `t("key")` instead of a
   hard-coded string. No change to the helpers themselves.
6. Update `TransactionView` main window — translate logout button, `_ws_badge`.

**Deliverable**: Employee transaction view fully bilingual.

**Dependencies**: Phase 1.

---

### Phase 4 — dashboard_view.py (Day 2–3)

**Objective**: Translate owner dashboard.

**Tasks**:

1. Translate `MENU_ITEMS` constant — same approach as `ACTIONS`: move into
   `DashboardView._build_sidebar()` and call `t()` per item, or store the sidebar
   buttons as instance attrs keyed by page index and update in `retranslate_ui()`.
2. `DashboardPage`:
   - Translate stat card labels (`"Today's CashIns"` etc.).
   - Translate table headers for `_txn_table`.
   - Store stat-card label widgets in `_stat_labels_text: dict[str, QLabel]` (separate
     from `_stat_labels` which holds value labels) so they can be updated.
   - Add `retranslate_ui()`.
3. `TransactionsPage`:
   - Translate table headers and filter labels.
   - Translate `_load_more_btn`.
   - Add `retranslate_ui()`.
4. `AccountsPage`:
   - Translate section label and table headers.
   - Translate `"Active"` / `"Inactive"` / `"Activate"` / `"Deactivate"` button text.
   - Add `retranslate_ui()`.
5. `ReportsPage`:
   - Translate section label, date label, load button.
   - The report cards are built dynamically in `_show_report()`; replace hard-coded
     label strings with `t()` calls.
   - Add `retranslate_ui()`.
6. `AddEmployeeDialog`:
   - Translate window title, form row labels, role combo.
   - Add `retranslate_ui()`.
7. `EmployeesPage`:
   - Translate section label, add-user button, table headers.
   - Add `retranslate_ui()`.
8. `SettingsPage`:
   - Translate all section labels, form labels, buttons, placeholders.
   - Add `retranslate_ui()`.
9. `DashboardView` main window:
   - Translate sidebar title and menu item buttons.
   - Translate logout button.
   - Add `retranslate_ui()` that cascades to all page `retranslate_ui()` calls.

**Deliverable**: Owner dashboard fully bilingual.

**Dependencies**: Phase 1.

---

### Phase 5 — cashier_view.py (Day 3)

**Objective**: Translate cashier-role UI.

**Tasks**:

1. `VaultEntryDialog`:
   - Translate window title (uses `entry_type` to pick title key: `"vault_in_title"` /
     `"vault_adj_title"`).
   - Translate grid headers `"Denomination"`, `"Quantity"`, `"Value"`.
   - Translate total row, note label, buttons.
2. `FloatDetailDialog`:
   - Translate table headers, issued-by text, closing-total label, close button.
3. `VaultPage`:
   - Translate section labels, denomination balances label, total vault label,
     log table headers, `"Record Vault Entry"` and `"Refresh"` buttons.
4. `IssueFloatPage`:
   - Translate section label, employee label, denomination grid headers, total
     label, note label, issue button.
5. `ShiftsPage`:
   - Translate section label, table headers, `"Refresh"` and `"View"` buttons.
6. `CashApprovalDialog`:
   - Translate window title, heading label, vault-direction hint, denomination
     grid headers, expected/entered/difference rows, note label, submit button.
7. `TransactionsReadOnlyPage`:
   - Translate section label, date label, table headers, `"● Live"` badge,
     `"Refresh"` button, `"✓ Approved"` / `"Pending"` cell text,
     `"Confirm Receipt"` action button text.
8. `CashierView` main window:
   - Translate sidebar title (`"Cashier"`), menu items, logout button.
   - Add `retranslate_ui()` cascading to all pages.

**Deliverable**: Cashier view fully bilingual.

**Dependencies**: Phase 1.

---

### Phase 6 — receive_float_dialog.py (Day 3)

**Objective**: Translate the float-receipt dialog shown to employees on login.

**Tasks**:

1. Translate window title.
2. Translate `"Float Ready for Collection"` heading.
3. Translate info row (issued-by / total) using parameterised `t()`.
4. Translate table headers `"Denomination"`, `"Quantity"`, `"Value"`.
5. Translate total-float row label.
6. Translate PIN prompt text.
7. Translate `"Cancel"` and `"Confirm Receipt"` buttons.
8. Translate validation error (`"PIN must be exactly 6 digits."`).
9. Translate `"Verifying..."` interim button text.
10. Register with `on_change` (language cannot be changed while dialog is open in
    practice, but it is good hygiene).

**Deliverable**: Float dialog bilingual.

**Dependencies**: Phase 1.

---

### Phase 7 — Integration, Font & Config wiring (Day 4)

**Objective**: Wire config persistence, ensure Myanmar font loads correctly, and
integrate the language switcher end-to-end.

**Tasks**:

1. Extend `run_client.py` `save_config()` to include `"language"` from
   `i18n.get_locale()`.
2. Ensure `i18n._load_persisted_locale()` is called before any `QApplication`
   window is constructed (i.e., at module import time, which happens as part of
   `import i18n`).
3. Validate Myanmar font rendering:
   - Call `QFontDatabase.families()` on startup; if `"Padauk"` is present, use it
     for the `"mm"` locale.
   - If not present, fall back to `"Myanmar Text"` (ships with Windows 8.1+).
   - If neither, fall back to system default (text may render with boxes but is
     not a blocker).
4. Update `NgweLweClient.spec` (PyInstaller) to bundle the `i18n/` package if not
   already auto-discovered.
5. Manual end-to-end test:
   - Launch app in `mm` (default) — verify all labels display Myanmar.
   - Switch to `en` at login screen — verify all open windows retranslate live.
   - Close and reopen — verify `en` persists.
   - Switch back to `mm` — verify revert works.

**Deliverable**: Fully integrated, persistent, runtime-switchable bilingual system.

**Dependencies**: Phases 1–6.

---

### Phase 8 — QA and Cleanup (Day 4–5)

**Objective**: Final review, edge-case handling, and any Myanmar translation review.

**Tasks**:

1. Review all `t()` key usages for missing keys; ensure safe fallback to English
   is logged (add a `warnings.warn` in `t()` for missing keys during development,
   remove before release).
2. Review Myanmar translation strings with a native speaker if possible.
   [NEEDS CLARIFICATION: Is a native Myanmar speaker available to review the
   translation strings, or should the plan treat the translations as provisional
   and subject to correction?]
3. Verify denomination-related strings that are mixed Myanmar/numeric render
   cleanly (e.g., `"50 pcs"` — should `"pcs"` become `"ခု"` in Myanmar, or remain
   English for professional use?).
   [NEEDS CLARIFICATION: Should quantity units ("pcs", "MMK") be translated into
   Myanmar (e.g., "ခု" for pieces) or remain as international abbreviations?]
4. Ensure dynamically-generated strings (transaction type values from the API,
   account types `"agent"` / `"personal"`, status values `"PENDING"` / `"ACTIVE"` /
   `"CLOSED"`) are either mapped through the translation dict or deliberately left
   as-is (they may be API-canonical codes).
   [NEEDS CLARIFICATION: Should API-returned enum values like "PENDING", "ACTIVE",
   "CLOSED", "cash_in", "cash_out" be displayed as-is (unchanged from API) or
   translated? If translated, a mapping in i18n.py is needed.]
5. Test with long Myanmar strings to confirm no layout truncation in sidebar
   buttons (fixed-width 200px) or table headers.
6. Remove development-only `warnings.warn` call.
7. Update `README.md` or `SKILL.md` with a note about the i18n module if
   applicable.

**Deliverable**: Production-ready bilingual system.

**Dependencies**: Phases 1–7.

---

## 5. File Inventory

| File | Action | New file? |
|------|--------|-----------|
| `i18n/__init__.py` | Create | Yes |
| `i18n/i18n.py` | Create | Yes |
| `views/login_view.py` | Modify | No |
| `views/dashboard_view.py` | Modify | No |
| `views/transaction_view.py` | Modify | No |
| `views/cashier_view.py` | Modify | No |
| `views/receive_float_dialog.py` | Modify | No |
| `run_client.py` | Modify | No |
| `NgweLweClient.spec` | Minor update (add i18n to hiddenimports if needed) | No |

No new pip dependencies are required.

---

## 6. Integration Pattern for Views

Every view class follows this identical 4-step pattern:

```python
# Step 1 — import at top of file
from i18n import t, on_change

# Step 2 — in __init__, after _init_ui():
on_change(self.retranslate_ui)

# Step 3 — store widget refs during _init_ui()
self._title_label = QLabel(t("some_key"))
self._save_btn    = QPushButton(t("save"))

# Step 4 — implement retranslate_ui()
def retranslate_ui(self) -> None:
    self._title_label.setText(t("some_key"))
    self._save_btn.setText(t("save"))
    # table headers (example)
    self._table.setHorizontalHeaderLabels([
        t("col_time"), t("col_employee"), t("col_type"),
    ])
```

---

## 7. Language Switcher UI Placement

The language toggle lives in `LoginView` in the bottom footer bar, alongside the
existing server-address label and "Change Server" button.

Proposed layout (footer row, left-to-right):
```
[Server: 192.168.1.1:8000]  [Change Server]   ... stretch ...   [မြန်မာ ▾ / EN]
```

The toggle is a `QComboBox` with two items:
- `"မြန်မာ (mm)"`  → calls `set_locale("mm")`
- `"English (en)"` → calls `set_locale("en")`

Once the user logs in and navigates to the main window, language switching is
no longer exposed in the UI (the selection made at login persists). If in-app
switching from the Settings page is also desired, the same combo can be added
to `SettingsPage`.

[NEEDS CLARIFICATION: Should a language selector also appear inside the app
(e.g., in the Settings page for owner, or the Profile card for employees), or
is the login-screen selector the only one needed?]

---

## 8. Parameterised Strings

Some strings include runtime values. The `t()` function supports Python
`str.format_map`:

```python
# In i18n.py
def t(key: str, **kwargs) -> str:
    template = TRANSLATIONS.get(key, {}).get(_locale) or key
    if kwargs:
        return template.format_map(kwargs)
    return template
```

Usage in views:

```python
# Float success message
t("float_success", total=f"{total:,}")

# Issued-by info line in ReceiveFloatDialog
t("float_issued_info", issued_by=issued_by, total=f"{int(total):,}")

# Cash approval window title
t("cash_approval_title", txn_id=txn_id)
```

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Myanmar font not installed on user machine | Low–Medium | Medium | Detect at startup; fall back to "Myanmar Text" (Win 8.1+); document minimum OS requirement |
| Zawgyi vs Unicode encoding mismatch | Low–Medium | High | Confirm font type once; if Zawgyi, the entire translation dict must use Zawgyi-encoded strings — plan treats Unicode as default |
| Wide Myanmar strings overflow fixed sidebar (200px) | Medium | Low | Test after Phase 5; shorten Myanmar labels or reduce font size for sidebar only |
| Module-level `ACTIONS` / `MENU_ITEMS` constants evaluated before locale loads | Low | Medium | Move label resolution to widget-construction time, not module import time |
| `retranslate_ui` called on a destroyed/hidden widget | Low | Low | Use `QObject.deleteLater()` pattern; guard with `try/except` |
| `on_change` registry grows unbounded (e.g., repeated dialog open/close) | Low | Low | Dialogs are short-lived; listeners are function refs that become garbage-collected. If needed, use `weakref`. |

---

## 10. Testing Strategy

### Manual smoke tests (per phase)
- Switch locale before opening a screen — all labels in the new locale.
- Switch locale while a screen is open — labels update immediately without re-opening.
- Close and reopen the application — locale persists from `client_config.json`.
- Open a dialog (e.g., `VaultEntryDialog`) and verify its labels match the active locale.

### Edge-case tests
- Missing translation key: `t("nonexistent_key")` returns `"nonexistent_key"` (no exception).
- Parameterised call with no kwargs: `t("float_success")` returns the raw template string (acceptable).
- Locale set to an unsupported value: falls back to `"en"`.

### No automated test suite is planned for this feature.

[NEEDS CLARIFICATION: Is there any existing test infrastructure (pytest, unittest)
in this project that new tests should integrate with, or are manual tests
sufficient for this project?]

---

## 11. Assumptions

1. The existing `client_config.json` is writable from the application's working
   directory (already completed — `save_config()` writes it unconditionally).
2. The deployment target is Windows (completed from project context).
3. All views are constructed inside the Qt event loop (standard PyQt6 usage) so
   calling `setText()` in `retranslate_ui()` is safe from the main thread.
4. Unicode Myanmar font is the target encoding (see clarification above).
5. The `run_server_app.py` server-side UI (if any) is out of scope — localization
   targets client-side views only.

---

## 12. Out of Scope

- Server-side (FastAPI) error messages returned from the API are not translated.
- Database values (transaction types, service names) stored as English strings in
  the SQLite DB are not changed.
- The server administration UI in `run_server_app.py` is not localised.
- A formal `.po`/`.mo` translation workflow is not introduced.

---

## 13. Areas Requiring Clarification

The following questions are extracted from `[NEEDS CLARIFICATION]` markers
throughout this document:

1. **Myanmar font encoding** — Which Myanmar font is installed on the target
   machines: Padauk (Unicode), Zawgyi-One, or another? The translation strings
   must match the encoding of the installed font. The plan currently uses Unicode
   (Padauk-compatible) strings.

2. **Native translation review** — Is a native Myanmar speaker available to
   review and correct the translation strings, or are they to be treated as a
   first draft subject to later correction?

3. **Quantity unit translation** — Should unit abbreviations such as `"pcs"` (for
   denomination counts) and `"MMK"` remain as international abbreviations in both
   locales, or should they be rendered in Myanmar script (e.g., `"ခု"`) when
   `mm` is active?

4. **API enum display** — Should API-returned status and type codes (`"PENDING"`,
   `"ACTIVE"`, `"CLOSED"`, `"cash_in"`, `"cash_out"`, etc.) be translated into
   Myanmar in the UI, or displayed as-is for professional/operational clarity?

5. **In-app language selector** — Should a language toggle also appear inside the
   main application (e.g., in the Settings page or a profile menu), in addition to
   the login-screen toggle? Or is it login-screen only?

6. **Test infrastructure** — Does this project have an existing pytest or unittest
   setup that automated i18n tests should be added to, or is manual testing
   sufficient?
