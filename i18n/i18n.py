"""
Lightweight dict-based i18n module for Ngwe Lwe System.
Supports Myanmar (mm, default) and English (en).

Usage:
    from i18n import t, set_locale, get_locale, on_change, ui_font

    label.setText(t("logout"))
    set_locale("en")          # switches all listeners
"""

from __future__ import annotations

import json
import os
from typing import Callable

from PyQt6.QtGui import QFont

# ─────────────────────────────────────────────────────────
# Translation dictionary
# Keys are stable English identifiers.
# Values are {"mm": <Myanmar text>, "en": <English text>}.
# ─────────────────────────────────────────────────────────
TRANSLATIONS: dict[str, dict[str, str]] = {
    # ── General ──────────────────────────────────────────
    "app_title":              {"mm": "ငွေလွှဲ System",              "en": "Ngwe Lwe System"},
    "logout":                 {"mm": "ထွက်မည်",                    "en": "Logout"},
    "refresh":                {"mm": "ပြန်ဆွဲမည်",                 "en": "Refresh"},
    "cancel":                 {"mm": "မလုပ်ပါ",                    "en": "Cancel"},
    "save":                   {"mm": "သိမ်းမည်",                   "en": "Save"},
    "close":                  {"mm": "ပိတ်မည်",                    "en": "Close"},
    "search":                 {"mm": "ရှာမည်",                     "en": "Search"},
    "load_more":              {"mm": "ထပ်ဆောင်းကြည့်မည်",          "en": "Load More"},
    "view":                   {"mm": "ကြည့်မည်",                   "en": "View"},
    "back":                   {"mm": "← နောက်သို့",               "en": "← Back"},
    "no_file_selected":       {"mm": "ဖိုင်မရွေးရသေး",            "en": "No file selected"},
    "attach_screenshot":      {"mm": "Screenshot တင်မည်",          "en": "Attach Screenshot"},
    "active":                 {"mm": "အသုံးပြုနေဆဲ",              "en": "Active"},
    "inactive":               {"mm": "ပိတ်ထားသည်",                 "en": "Inactive"},
    "activate":               {"mm": "ဖွင့်မည်",                   "en": "Activate"},
    "deactivate":             {"mm": "ပိတ်မည်",                    "en": "Deactivate"},
    "all":                    {"mm": "အားလုံး",                    "en": "All"},
    "language":               {"mm": "ဘာသာစကား",                  "en": "Language"},
    "select_placeholder":     {"mm": "— ရွေးပါ —",                "en": "— Select —"},
    "date_label":             {"mm": "ရက်:",                       "en": "Date:"},
    "note_optional":          {"mm": "မှတ်ချက် (မဖြစ်မနေမဟုတ်):", "en": "Note (optional):"},

    # ── Login ────────────────────────────────────────────
    "login_title":            {"mm": "ငွေလွှဲ System",             "en": "Ngwe Lwe System"},
    "username_placeholder":   {"mm": "အသုံးပြုသူအမည်",            "en": "Username"},
    "password_placeholder":   {"mm": "စကားဝှက်",                  "en": "Password"},
    "sign_in":                {"mm": "ဝင်မည်",                     "en": "Sign In"},
    "signing_in":             {"mm": "ဝင်နေသည်...",               "en": "Signing in..."},
    "login_empty_error":      {"mm": "အသုံးပြုသူအမည်နှင့် စကားဝှက် ထည့်ပါ။",
                               "en": "Please enter your username and password."},
    "login_fail":             {"mm": "ဝင်ရောက်မရပါ။ ဆာဗာ ချိတ်ဆက်မှုကို စစ်ဆေးပါ။",
                               "en": "Sign-in failed. Please check your server connection."},
    "window_open_fail":       {"mm": "ဝင်းဒိုး ဖွင့်မရပါ: {error}",
                               "en": "Failed to open window: {error}"},

    # ── Home cards ───────────────────────────────────────
    "new_transaction":        {"mm": "ငွေလွှဲသစ်",                "en": "New Transaction"},
    "new_transaction_desc":   {"mm": "ငွေလွှဲ အသစ်ဖန်တီးမည်",    "en": "Create a new transaction"},
    "txn_history":            {"mm": "ငွေလွှဲမှတ်တမ်း",           "en": "Transaction History"},
    "txn_history_desc":       {"mm": "ယခင်ငွေလွှဲများ ကြည့်ရှုမည်","en": "View past transactions"},
    "my_profile":             {"mm": "ကျွန်ုပ်၏ ပရိုဖိုင်",       "en": "My Profile"},
    "my_profile_desc":        {"mm": "အကောင့်ဆက်တင်",             "en": "Account settings"},

    # ── Sidebar navigation ───────────────────────────────
    "nav_dashboard":          {"mm": "ဒက်ရှ်ဘုတ်",               "en": "Dashboard"},
    "nav_transactions":       {"mm": "ငွေလွှဲများ",               "en": "Transactions"},
    "nav_accounts":           {"mm": "အကောင့်များ",               "en": "Accounts"},
    "nav_reports":            {"mm": "အစီရင်ခံစာ",               "en": "Reports"},
    "nav_users":              {"mm": "အသုံးပြုသူများ",            "en": "Users"},
    "nav_settings":           {"mm": "ဆက်တင်",                   "en": "Settings"},
    # Sidebar section group labels
    "nav_group_transactions": {"mm": "ငွေလွှဲများ",               "en": "Transactions"},
    "nav_group_accounts":     {"mm": "အကောင့်များ",               "en": "Accounts"},
    "nav_group_reports":      {"mm": "အစီရင်ခံစာ",               "en": "Reports"},
    "nav_vault":              {"mm": "ငွေသေတ္တာ",                 "en": "Vault"},
    "nav_issue_float":        {"mm": "Float ထုတ်ပေးမည်",          "en": "Issue Float"},
    "nav_shifts":             {"mm": "Float ခွဲဝေမှုများ",        "en": "Shifts"},
    "sidebar_cashier":        {"mm": "ငွေကိုင်",                  "en": "Cashier"},

    # ── Dashboard stats ──────────────────────────────────
    "todays_deposits":        {"mm": "ယနေ့ ငွေသွင်းစုစုပေါင်း",  "en": "Today's Deposits"},
    "todays_withdrawals":     {"mm": "ယနေ့ ငွေထုတ်စုစုပေါင်း",   "en": "Today's Withdrawals"},
    "transfers":              {"mm": "လွှဲငွေများ",               "en": "Transfers"},
    "exchange":               {"mm": "ငွေလဲလှယ်",                "en": "Exchange"},
    "fees_commission":        {"mm": "ကြေးနှင့် ကော်မရှင်",      "en": "Fees & Commission"},
    "todays_summary":         {"mm": "ယနေ့ အနှစ်ချုပ်",          "en": "Today's Summary"},
    "account_balances":       {"mm": "အကောင့်လက်ကျန်ငွေ",        "en": "Account Balances"},
    "recent_transactions":    {"mm": "မကြာမီ ငွေလွှဲများ",        "en": "Recent Transactions"},

    # ── Table column headers ─────────────────────────────
    "col_id":                 {"mm": "ID",                         "en": "ID"},
    "col_time":               {"mm": "အချိန်",                    "en": "Time"},
    "col_date_time":          {"mm": "ရက်/အချိန်",                "en": "Date / Time"},
    "col_employee":           {"mm": "ဝန်ထမ်း",                   "en": "Employee"},
    "col_type":               {"mm": "အမျိုးအစား",                "en": "Type"},
    "col_service":            {"mm": "ဝန်ဆောင်မှု",               "en": "Service"},
    "col_account":            {"mm": "အကောင့်",                   "en": "Account"},
    "col_amount":             {"mm": "ပမာဏ",                      "en": "Amount"},
    "col_amount_mmk":         {"mm": "ပမာဏ (MMK)",                "en": "Amount (MMK)"},
    "col_commission":         {"mm": "ကော်မရှင်",                 "en": "Commission"},
    "col_fee":                {"mm": "ကြေး",                      "en": "Fee"},
    "col_fee_mmk":            {"mm": "ကြေး (MMK)",                "en": "Fee (MMK)"},
    "col_screenshot":         {"mm": "ဓာတ်ပုံ",                   "en": "Screenshot"},
    "col_customer":           {"mm": "ဖောက်သည်",                  "en": "Customer"},
    "col_staff":              {"mm": "ဝန်ထမ်း",                   "en": "Staff"},
    "col_cash_status":        {"mm": "ငွေသားအခြေအနေ",            "en": "Cash Status"},
    "col_action":             {"mm": "လုပ်ဆောင်ချက်",             "en": "Action"},
    "col_status":             {"mm": "အခြေအနေ",                   "en": "Status"},
    "col_float_amount":       {"mm": "Float ငွေပမာဏ",             "en": "Float Amount"},
    "col_issued_by":          {"mm": "ထုတ်ပေးသူ",                 "en": "Issued By"},
    "col_issued_at":          {"mm": "ထုတ်ပေးချိန်",              "en": "Issued At"},
    "col_received_at":        {"mm": "လက်ခံချိန်",                "en": "Received At"},
    "col_closed_at":          {"mm": "ပိတ်ချိန်",                 "en": "Closed At"},
    "col_denomination":       {"mm": "ငွေတန်ဖိုး",               "en": "Denomination"},
    "col_quantity":           {"mm": "အရေအတွက်",                  "en": "Quantity"},
    "col_qty":                {"mm": "အရေအတွက်",                  "en": "Qty"},
    "col_value":              {"mm": "တန်ဖိုး",                   "en": "Value"},
    "col_value_mmk":          {"mm": "တန်ဖိုး (MMK)",             "en": "Value (MMK)"},
    "col_entry_type":         {"mm": "မှတ်တမ်းအမျိုးအစား",        "en": "Entry Type"},
    "col_note":               {"mm": "မှတ်ချက်",                  "en": "Note"},
    "col_username":           {"mm": "အသုံးပြုသူအမည်",            "en": "Username"},
    "col_fullname":           {"mm": "အမည်အပြည့်",                "en": "Full Name"},
    "col_role":               {"mm": "ရာထူး",                     "en": "Role"},
    "col_created":            {"mm": "ဖန်တီးသောရက်",             "en": "Created"},
    "col_active":             {"mm": "အသုံးပြုနေဆဲ",             "en": "Active"},
    "col_name":               {"mm": "အမည်",                      "en": "Name"},
    "col_phone":              {"mm": "ဖုန်း",                     "en": "Phone"},
    "col_balance":            {"mm": "လက်ကျန်ငွေ",               "en": "Balance"},
    "col_account_name":       {"mm": "အကောင့်အမည်",              "en": "Account Name"},
    "col_account_number":     {"mm": "အကောင့်နံပါတ်",            "en": "Account Number"},
    "col_customer_phone":     {"mm": "ဖောက်သည်ဖုန်း",            "en": "Customer Phone"},
    "col_fee_account":        {"mm": "ကြေးပေးအကောင့်",           "en": "Fee Account"},
    "btn_set_fee":            {"mm": "ကြေးအကောင့်သတ်မှတ်",        "en": "Set Fee"},
    "btn_unset_fee":          {"mm": "ကြေးအကောင့်ဖျက်သိမ်း",      "en": "Unset Fee"},

    # ── Transaction form ─────────────────────────────────
    "transaction":            {"mm": "ငွေလွှဲ",                   "en": "Transaction"},
    "action_deposit":         {"mm": "ငွေသွင်း",                  "en": "Deposit"},
    "action_withdraw":        {"mm": "ငွေထုတ်",                   "en": "Withdraw"},
    "action_transfer":        {"mm": "လွှဲပြောင်း",               "en": "Transfer"},
    "action_exchange":        {"mm": "ငွေလဲ",                     "en": "Exchange"},
    "field_company":          {"mm": "ကုမ္ပဏီ",                   "en": "Company"},
    "field_service_type":     {"mm": "ဝန်ဆောင်မှုအမျိုးအစား",    "en": "Service Type"},
    "field_to_company":       {"mm": "ပို့ဆောင်မည့် ကုမ္ပဏီ",    "en": "To Company"},
    "field_to_service_type":  {"mm": "ပို့ဆောင်မည့် ဝန်ဆောင်မှု","en": "To Service Type"},
    "field_service":          {"mm": "ဝန်ဆောင်မှု",               "en": "Service"},
    "field_account":          {"mm": "အကောင့်",                   "en": "Account"},
    "field_to_account":       {"mm": "လက်ခံအကောင့်",              "en": "To Account"},
    "field_customer":         {"mm": "ဖောက်သည်အမည် / ဖုန်း",    "en": "Customer Name / Phone"},
    "customer_name_ph":       {"mm": "ဖောက်သည်အမည်",             "en": "Customer Name"},
    "customer_phone_ph":      {"mm": "ဖုန်းနံပါတ်",               "en": "Phone Number"},
    "field_currency":         {"mm": "ငွေကြေး",                   "en": "Currency"},
    "field_amount":           {"mm": "ပမာဏ",                      "en": "Amount"},
    "field_commission":       {"mm": "ကော်မရှင်",                 "en": "Commission"},
    "field_customer_fee":     {"mm": "ဖောက်သည်ကြေး (Tier)",      "en": "Customer Fee (from tier)"},
    "field_additional_fee":   {"mm": "ထပ်ဆောင်းကြေး (Tier)",     "en": "Additional Fee (from tier)"},
    "field_total_fee":        {"mm": "ကြေးစုစုပေါင်း (→ ကြေးအကောင့်)",
                               "en": "Total Fee  (→ Fee Account)"},
    "field_fee_account":      {"mm": "ကြေးအကောင့်",               "en": "Fee Account"},
    "field_balance_change":   {"mm": "လက်ကျန်ငွေပြောင်းလဲမှု",  "en": "Balance Change"},
    "field_note":             {"mm": "မှတ်ချက်",                  "en": "Note"},
    "note_placeholder":       {"mm": "ထပ်ဆောင်းမှတ်ချက်... (Ctrl+Enter နှိပ်ရင် မျဉ်းသစ်)",
                               "en": "Optional note... (Ctrl+Enter for new line)"},
    "save_transaction":       {"mm": "ငွေလွှဲသိမ်းမည်",           "en": "Save Transaction"},
    "todays_transactions":    {"mm": "ယနေ့ ငွေလွှဲများ",         "en": "Today's Transactions"},
    "no_tier":                {"mm": "Tier မသတ်မှတ်ရသေး — ကိုယ်တိုင် ဖြည့်ပါ",
                               "en": "No tier configured — please enter fees manually."},
    "current_balance":        {"mm": "လက်ရှိ လက်ကျန်ငွေ: {balance} MMK",
                               "en": "Current Balance: {balance} MMK"},
    "balance_after":          {"mm": "လက်ရှိ: {balance} → ငွေလွှဲပြီး: {projected} MMK",
                               "en": "Current: {balance}  →  After transaction: {projected} MMK"},
    "txn_saved":              {"mm": "ငွေလွှဲ အောင်မြင်စွာ သိမ်းပြီ။",
                               "en": "Transaction saved successfully."},
    "err_select_account":     {"mm": "အကောင့် ရွေးပါ။",           "en": "Please select an account."},
    "err_enter_amount":       {"mm": "ပမာဏ ထည့်ပါ။",              "en": "Please enter a valid amount."},
    "err_customer_name":      {"mm": "ဖောက်သည်အမည် ထည့်ပါ။",    "en": "Please enter the customer name."},
    "err_customer_phone":     {"mm": "ဖောက်သည်ဖုန်း ထည့်ပါ။",    "en": "Please enter the customer phone number."},
    "err_select_to_account":  {"mm": "လက်ခံအကောင့် ရွေးပါ။",     "en": "Please select the destination account."},
    "err_same_account":       {"mm": "ပို့သည့်နှင့် လက်ခံ အကောင့် မတူရ။",
                               "en": "Source and destination accounts must be different."},
    "err_insufficient":       {"mm": "လက်ကျန်ငွေ မလုံပါ (လက်ရှိ: {balance} MMK)。",
                               "en": "Insufficient balance (current: {balance} MMK)."},
    "err_no_float":           {"mm": "Float မလက်ခံရသေးပါ။ Cashier ထံမှ Float ယူပါ။",
                               "en": "No active float. Receive your float from the cashier first."},
    "warn_no_float_banner":   {"mm": "⚠ Float မရှိသေးပါ — ငွေထုတ်၊ ငွေလွှဲ၊ ငွေလဲ လုပ်ငန်းများ ပိတ်ထားသည်။",
                               "en": "⚠ No active float — Withdraw, Transfer and Exchange are disabled."},
    "err_open_file":          {"mm": "ဖိုင်ဖွင့်မရပါ: {path}",    "en": "Unable to open file: {path}"},
    "err_screenshot":         {"mm": "Screenshot တင်မရပါ: {error}","en": "Failed to load screenshot: {error}"},
    "select_screenshot":      {"mm": "Screenshot ရွေးပါ",           "en": "Select Screenshot"},
    "screenshot_title":       {"mm": "Screenshot",                  "en": "Screenshot"},

    # ── Transaction history filters ───────────────────────
    "txn_history_title":      {"mm": "ငွေလွှဲမှတ်တမ်း",           "en": "Transaction History"},
    "filter_from":            {"mm": "မှ:",                        "en": "From:"},
    "filter_to":              {"mm": "သို့:",                     "en": "To:"},
    "filter_type":            {"mm": "အမျိုးအစား:",               "en": "Type:"},
    "filter_phone":           {"mm": "ဖုန်း:",                    "en": "Phone:"},
    "filter_phone_ph":        {"mm": "အကောင့် / ဖောက်သည် နံပါတ်", "en": "Account / Customer No."},

    # ── Profile / Change Password ─────────────────────────
    "profile_title":          {"mm": "ပရိုဖိုင်",                 "en": "Profile"},
    "change_password":        {"mm": "စကားဝှက်ပြောင်းမည်",        "en": "Change Password"},
    "current_password_ph":    {"mm": "လက်ရှိ စကားဝှက်",           "en": "Current Password"},
    "new_password_ph":        {"mm": "စကားဝှက်အသစ်",              "en": "New Password"},
    "confirm_password_ph":    {"mm": "စကားဝှက်အသစ် အတည်ပြုရန်",  "en": "Confirm New Password"},
    "save_password":          {"mm": "စကားဝှက်သိမ်းမည်",           "en": "Save Password"},
    "pw_required":            {"mm": "Field အားလုံး ဖြည့်ရမည်။",   "en": "Please fill in all required fields."},
    "pw_mismatch":            {"mm": "စကားဝှက် မတူပါ။ ထပ်ကြိုးစားပါ။",
                               "en": "Passwords do not match. Please try again."},
    "pw_success":             {"mm": "စကားဝှက် အောင်မြင်စွာ ပြောင်းပြီ။",
                               "en": "Password changed successfully."},

    # ── Accounts page ─────────────────────────────────────
    "accounts_title":         {"mm": "အကောင့်စီမံခန့်ခွဲမှု",     "en": "Accounts Management"},
    "col_service_type":       {"mm": "ဝန်ဆောင်မှုအမျိုးအစား",     "en": "Service Type"},
    "status_active":          {"mm": "အသုံးပြုနေဆဲ",              "en": "Active"},
    "status_inactive":        {"mm": "ပိတ်ထားသည်",                "en": "Inactive"},
    "btn_deactivate":         {"mm": "ပိတ်မည်",                   "en": "Deactivate"},
    "btn_activate":           {"mm": "ဖွင့်မည်",                  "en": "Activate"},

    # ── Reports page ──────────────────────────────────────
    "reports_title":          {"mm": "နေ့စဥ် အစီရင်ခံစာ",        "en": "Daily Report"},
    "load_report":            {"mm": "အစီရင်ခံစာတင်မည်",          "en": "Load Report"},
    "total_deposit":          {"mm": "ငွေသွင်းစုစုပေါင်း",        "en": "Total Deposit"},
    "total_withdraw":         {"mm": "ငွေထုတ်စုစုပေါင်း",         "en": "Total Withdraw"},
    "total_transfer":         {"mm": "လွှဲပြောင်းစုစုပေါင်း",     "en": "Total Transfer"},
    "total_exchange":         {"mm": "ငွေလဲစုစုပေါင်း",           "en": "Total Exchange"},
    "total_commission":       {"mm": "ကော်မရှင်စုစုပေါင်း",       "en": "Total Commission"},
    "total_customer_fees":    {"mm": "ဖောက်သည်ကြေးစုစုပေါင်း",   "en": "Total Customer Fees"},
    "txn_count":              {"mm": "ငွေလွှဲအရေအတွက်",           "en": "Transaction Count"},

    # ── Settings page ─────────────────────────────────────
    "settings_exrate":        {"mm": "ငွေလဲနှုန်း (THB/MMK)",     "en": "Exchange Rate  (base: THB / quote: MMK)"},
    "current_rate_placeholder":{"mm": "လက်ရှိ: —",               "en": "Current: —"},
    "base_amount_thb":        {"mm": "အခြေခံပမာဏ (THB):",        "en": "Base Amount  (THB):"},
    "buy_rate_label":         {"mm": "ဝယ်နှုန်း (MMK/THB):",     "en": "Buy Rate  (MMK per base THB):"},
    "sell_rate_label":        {"mm": "ရောင်းနှုန်း (MMK/THB):",  "en": "Sell Rate  (MMK per base THB):"},
    "save_rate":              {"mm": "နှုန်းသိမ်းမည်",             "en": "Save Rate"},
    "rate_saved":             {"mm": "ငွေလဲနှုန်း သိမ်းပြီ။",    "en": "Exchange rate saved successfully."},
    "settings_tiers":         {"mm": "ကော်မရှင် Tiers",           "en": "Commission Tiers"},
    "add_tier":               {"mm": "+ Tier ထည့်မည်",            "en": "+ Add Tier"},
    "tier_added":             {"mm": "Commission tier အောင်မြင်စွာ ထည့်ပြီ။",
                               "en": "Commission tier added successfully."},
    "btn_load":               {"mm": "တင်မည်",                    "en": "Load"},
    "tier_acct_type":         {"mm": "အကောင့်အမျိုး:",            "en": "Acct Type:"},
    "tier_from_amount":       {"mm": "မှ:",                        "en": "From:"},
    "tier_to_amount":         {"mm": "သို့:",                     "en": "To:"},
    "tier_fee_type":          {"mm": "ကြေးအမျိုး:",               "en": "Fee Type:"},
    "tier_fee_dep":           {"mm": "ကြေး (သွင်း):",             "en": "Fee Dep:"},
    "tier_fee_with":          {"mm": "ကြေး (ထုတ်):",              "en": "Fee With:"},
    "tier_comm_type":         {"mm": "ကော်မရှင်အမျိုး:",          "en": "Comm Type:"},
    "tier_comm_dep":          {"mm": "ကော်မရှင် (သွင်း):",        "en": "Comm Dep:"},
    "tier_comm_with":         {"mm": "ကော်မရှင် (ထုတ်):",         "en": "Comm With:"},
    "tier_add_type":          {"mm": "ထပ်ကြေးအမျိုး:",            "en": "Add Type:"},
    "tier_add_dep":           {"mm": "ထပ်ကြေး (သွင်း):",          "en": "Add Dep:"},
    "tier_add_with":          {"mm": "ထပ်ကြေး (ထုတ်):",           "en": "Add With:"},
    "tier_col_acct_type":     {"mm": "အကောင့်အမျိုး",             "en": "Acct Type"},
    "tier_col_from":          {"mm": "မှ (MMK)",                   "en": "From (MMK)"},
    "tier_col_to":            {"mm": "သို့ (MMK)",                 "en": "To (MMK)"},
    "tier_col_fee_type":      {"mm": "ကြေးအမျိုး",               "en": "Fee Type"},
    "tier_col_fee_dep":       {"mm": "ကြေး (သွင်း)",              "en": "Fee Deposit"},
    "tier_col_fee_with":      {"mm": "ကြေး (ထုတ်)",               "en": "Fee Withdraw"},
    "tier_col_comm_type":     {"mm": "ကော်မရှင်အမျိုး",           "en": "Comm Type"},
    "tier_col_comm_dep":      {"mm": "ကော်မရှင် (သွင်း)",         "en": "Comm Deposit"},
    "tier_col_comm_with":     {"mm": "ကော်မရှင် (ထုတ်)",          "en": "Comm Withdraw"},
    "tier_col_add_type":      {"mm": "ထပ်ကြေးအမျိုး",             "en": "Add-on Type"},
    "tier_col_add_dep":       {"mm": "ထပ်ကြေး (သွင်း)",           "en": "Add-on Dep"},
    "tier_col_add_with":      {"mm": "ထပ်ကြေး (ထုတ်)",            "en": "Add-on With"},
    "tier_col_delete":        {"mm": "ဖျက်မည်",                   "en": "Delete"},

    # ── Users page ────────────────────────────────────────
    "users_title":            {"mm": "အသုံးပြုသူများ",            "en": "Users"},
    "add_user_btn":           {"mm": "+ အသုံးပြုသူထည့်မည်",      "en": "+ Add User"},
    "add_user_dialog_title":  {"mm": "အသုံးပြုသူထည့်မည်",        "en": "Add User"},
    "field_password":         {"mm": "စကားဝှက်",                  "en": "Password"},
    "role_label":             {"mm": "ရာထူး:",                    "en": "Role:"},
    "all_fields_required":    {"mm": "Field အားလုံး ဖြည့်ရမည်။",  "en": "All fields are required."},
    "user_created":           {"mm": "{role} အကောင့် '{user}' ဖန်တီးပြီ။",
                               "en": "{role} account '{user}' created successfully."},

    # ── Vault page ────────────────────────────────────────
    "vault_title":            {"mm": "ငွေသေတ္တာ အနှစ်ချုပ်",      "en": "Vault Overview"},
    "denom_balances":         {"mm": "ငွေတန်ဖိုးအလိုက် လက်ကျန်",  "en": "Denomination Balances"},
    "total_vault_value":      {"mm": "ငွေသေတ္တာ စုစုပေါင်း:",     "en": "Total Vault Value:"},
    "recent_vault_entries":   {"mm": "မကြာမီ ငွေသေတ္တာမှတ်တမ်း",  "en": "Recent Vault Entries"},
    "record_vault_entry":     {"mm": "ငွေသေတ္တာမှတ်တမ်း သွင်းမည်","en": "Record Vault Entry"},

    # ── VaultEntryDialog ──────────────────────────────────
    "vault_in_title":         {"mm": "ငွေသေတ္တာ ငွေသွင်းမည်",     "en": "Add Cash to Vault"},
    "vault_adj_title":        {"mm": "ငွေသေတ္တာ ပြင်ဆင်မည်",      "en": "Vault Adjustment"},
    "total_label":            {"mm": "စုစုပေါင်း:",               "en": "Total:"},
    "save_entry":             {"mm": "မှတ်တမ်းသိမ်းမည်",           "en": "Save Entry"},
    "total_nonzero":          {"mm": "စုစုပေါင်း သုညထက် ကြီးရမည်","en": "Total must be greater than zero"},
    "morning_cash_ph":        {"mm": "e.g. နံနက်ပိုင်း ငွေသွင်း", "en": "e.g. Morning cash top-up"},

    # ── Issue Float page ──────────────────────────────────
    "issue_float_title":      {"mm": "ဝန်ထမ်းသို့ Float ပေးမည်",  "en": "Issue Float to Employee"},
    "employee_label":         {"mm": "ဝန်ထမ်း:",                  "en": "Employee:"},
    "denom_breakdown":        {"mm": "ငွေတန်ဖိုးအလိုက် ဖော်ပြချက်:","en": "Denomination Breakdown:"},
    "total_float_amount":     {"mm": "Float ငွေ စုစုပေါင်း:",     "en": "Total Float Amount:"},
    "morning_float_ph":       {"mm": "e.g. နံနက်ပိုင်း Float",    "en": "e.g. Morning shift float"},
    "issue_float_btn":        {"mm": "Float ပေးမည်",              "en": "Issue Float"},
    "issuing_btn":            {"mm": "ပေးနေသည်...",               "en": "Issuing..."},
    "select_employee":        {"mm": "ဝန်ထမ်း ရွေးပါ",            "en": "Please select an employee"},
    "float_zero_error":       {"mm": "Float ငွေ သုညထက် ကြီးရမည်","en": "Float total must be greater than zero"},
    "float_success":          {"mm": "Float အောင်မြင်စွာ ပေးပြီ။ စုစုပေါင်း: {total} MMK",
                               "en": "Float issued successfully. Total: {total} MMK"},

    # ── Shifts page ───────────────────────────────────────
    "shifts_title":           {"mm": "Float ခွဲဝေမှုများ",        "en": "Float Assignments"},

    # ── FloatDetailDialog ─────────────────────────────────
    "issued_by_meta":         {"mm": "ထုတ်ပေးသူ: {issued_by}    |    စုစုပေါင်း: {total} MMK",
                               "en": "Issued by: {issued_by}    |    Total: {total} MMK"},
    "closing_total":          {"mm": "ပိတ်ချိန်ငွေ: {total} MMK    |    ပိတ်ချိန်: {closed_at}",
                               "en": "Closing total: {total} MMK    |    Closed: {closed_at}"},

    # ── Transactions page (cashier) ───────────────────────
    "transactions_title":     {"mm": "ငွေလွှဲများ",               "en": "Transactions"},
    "ws_live":                {"mm": "● အသက်ဝင်နေ",               "en": "● Live"},
    "confirm_receipt_btn":    {"mm": "လက်ခံ အတည်ပြုမည်",          "en": "Confirm Receipt"},
    "approved_badge":         {"mm": "✓ အတည်ပြုပြီ",             "en": "✓ Approved"},
    "pending_badge":          {"mm": "စောင့်ဆိုင်းဆဲ",            "en": "Pending"},

    # ── CashApprovalDialog ────────────────────────────────
    "cash_approval_window":   {"mm": "ငွေသားအတည်ပြု — Txn #{txn_id}",
                               "en": "Cash Approval — Txn #{txn_id}"},
    "cash_confirm_heading":   {"mm": "ငွေသားလက်ခံ အတည်ပြု — Txn #{txn_id}",
                               "en": "Cash Receipt Confirmation — Txn #{txn_id}"},
    "vault_in_hint":          {"mm": "ငွေသေတ္တာသွင်း — ဖောက်သည်ထံမှ ငွေလက်ခံ",
                               "en": "Vault In — Cash Received from Customer"},
    "vault_out_hint":         {"mm": "ငွေသေတ္တာထုတ် — ဖောက်သည်သို့ ငွေပေး",
                               "en": "Vault Out — Cash Dispensed to Customer"},
    "expected_label":         {"mm": "မျှော်မှန်း:",              "en": "Expected:"},
    "entered_label":          {"mm": "ထည့်သွင်းသည်:",             "en": "Entered:"},
    "difference_label":       {"mm": "ကွာခြားချက်:",              "en": "Difference:"},
    "morning_receipt_ph":     {"mm": "e.g. နံနက်ပိုင်း ရောင်းငွေ","en": "e.g. Morning shift receipts"},
    "confirm_cash_btn":       {"mm": "ငွေသား လက်ခံ အတည်ပြုမည်",  "en": "Confirm Cash Received"},
    "denom_nonzero":          {"mm": "ငွေသည် သုညထက် ကြီးရမည်",   "en": "Denomination total must be greater than zero"},

    # ── ReceiveFloatDialog ────────────────────────────────
    "float_receipt_window":   {"mm": "Float လက်ခံ — PIN အတည်ပြုမည်",
                               "en": "Float Receipt — PIN Confirmation"},
    "float_ready_title":      {"mm": "Float လက်ခံရန် အဆင်သင့်ဖြစ်ပြီ",
                               "en": "Float Ready for Collection"},
    "total_float_label":      {"mm": "Float ငွေ စုစုပေါင်း:",     "en": "Total Float:"},
    "pin_prompt":             {"mm": "PIN ၆ လုံး ထည့်ကာ လက်ခံကြောင်း အတည်ပြုပါ:",
                               "en": "Enter your 6-digit PIN to confirm receipt:"},
    "pin_invalid":            {"mm": "PIN ၆ လုံး ဂဏန်းဖြင့် ထည့်ရမည်။",
                               "en": "PIN must be exactly 6 digits."},
    "verifying":              {"mm": "စစ်ဆေးနေသည်...",            "en": "Verifying..."},

    # ── Server Config Dialog (run_client.py) ──────────────
    "server_conn_title":      {"mm": "Ngwe Lwe — ဆာဗာ ချိတ်ဆက်မည်",
                               "en": "Ngwe Lwe — Server Connection"},
    "server_config_box":      {"mm": "ဆာဗာ ဆက်တင်",              "en": "Server Configuration"},
    "server_ip_label":        {"mm": "ဆာဗာ IP:",                  "en": "Server IP:"},
    "port_label":             {"mm": "ဆိပ်ကမ်း (Port):",          "en": "Port:"},
    "server_sub":             {"mm": "ဆာဗာ IP နှင့် Port ထည့်ပြီး Connect နှိပ်ပါ။",
                               "en": "Enter your server IP address and port, then click Connect."},
    "connect_btn":            {"mm": "ချိတ်ဆက်မည်",               "en": "Connect"},
    "connected_msg":          {"mm": "ချိတ်ဆက်ပြီ!",             "en": "Connected!"},
    "ip_required":            {"mm": "ဆာဗာ IP ထည့်ပါ။",          "en": "Please enter the server IP address."},
    "port_invalid":           {"mm": "Port သည် 1–65535 ဖြစ်ရမည်။","en": "Port must be a number between 1 and 65535."},
    "connecting_to":          {"mm": "{url} သို့ ချိတ်ဆက်နေသည်...","en": "Connecting to {url}..."},
    "err_status_code":        {"mm": "ဆာဗာမှ {code} response ရပါသည်。",
                               "en": "Server returned status {code}."},
    "err_cannot_reach":       {"mm": "ဆာဗာ ချိတ်ဆက်မရပါ။\nIP/Port မှန်ကန်မှု စစ်ဆေးပါ。",
                               "en": "Unable to reach the server.\nPlease verify the IP address and port."},
    "err_timeout":            {"mm": "ချိတ်ဆက်မှု ကုန်ဆုံးသွားသည်။ ဆာဗာ ဖွင့်ထားပါသလား?",
                               "en": "Connection timed out. Is the server running?"},
    "saved_server_fail":      {"mm": "သိမ်းဆည်းထားသော ဆာဗာ ({host}:{port}) ချိတ်ဆက်မရပါ။\nIP/Port ပြင်ဆင်ပါ。",
                               "en": "Could not connect to saved server ({host}:{port}).\nPlease update the IP address and port."},
    "server_label":           {"mm": "ဆာဗာ: {host}:{port}",       "en": "Server: {host}:{port}"},
    "change_server":          {"mm": "⚙ ဆာဗာပြောင်းမည်",         "en": "⚙ Change Server"},

    # ── Server Manager (run_server_app.py) ───────────────
    "server_mgr_title":       {"mm": "Ngwe Lwe — ဆာဗာ စီမံခန့်ခွဲမှု",
                               "en": "Ngwe Lwe — Server Manager"},
    "lan_ip_hint":            {"mm": "ဤ Machine ၏ LAN IP:  {ip}", "en": "This machine's LAN IP:  {ip}"},
    "server_config_admin":    {"mm": "ဆာဗာ ဆက်တင် (Admin)",      "en": "Server Configuration (Admin)"},
    "host_label":             {"mm": "Host:",                       "en": "Host:"},
    "server_tip":             {"mm": "0.0.0.0  —  LAN ပေါ်မှ Client အားလုံး ချိတ်ဆက်နိုင်သည်\n127.0.0.1  —  ဤ Machine တစ်ခုတည်းသာ ဝင်ရောက်နိုင်သည်",
                               "en": "0.0.0.0  —  Accessible by all clients on the LAN\n127.0.0.1  —  Accessible on this machine only"},
    "start_server":           {"mm": "▶  ဆာဗာ စတင်မည်",           "en": "▶  Start Server"},
    "stop_server":            {"mm": "■  ဆာဗာ ရပ်မည်",            "en": "■  Stop Server"},
    "status_stopped":         {"mm": "● ရပ်နေသည်",                "en": "● Stopped"},
    "status_running":         {"mm": "● လည်ပတ်နေသည်",             "en": "● Running"},
    "server_log":             {"mm": "ဆာဗာ မှတ်တမ်း",             "en": "Server Log"},
    "host_required":          {"mm": "Host ထည့်ပါ။",               "en": "Please enter the host address."},
    "port_required":          {"mm": "Port ကို 1–65535 ဂဏန်းဖြင့် ထည့်ပါ။",
                               "en": "Port must be a number between 1 and 65535."},
    "validation_error":       {"mm": "စစ်ဆေးမှု အမှား",           "en": "Validation Error"},
    "starting_server":        {"mm": "{host}:{port} ပေါ်တွင် ဆာဗာ စတင်နေသည်...",
                               "en": "Starting server on {host}:{port}..."},
    "share_url":              {"mm": "Client များသို့ ဤ URL ပေးပါ:  {url}",
                               "en": "Share this URL with clients:  {url}"},
    "server_stopped":         {"mm": "ဆာဗာ ရပ်တန့်သွားသည်။",     "en": "Server stopped."},
    "server_error_title":     {"mm": "ဆာဗာ အမှား",                "en": "Server Error"},

    # ── Startup choice (main.py) ──────────────────────────────
    "startup_choice_sub":     {"mm": "ဤ Device ကို ဘယ်လိုသုံးမလဲ ရွေးချယ်ပါ",
                               "en": "Choose how to start this session"},
    "choice_host_btn":        {"mm": "▶  ဆာဗာ Host & App ဖွင့်မည်",
                               "en": "▶  Host Server & Open App"},
    "choice_host_desc":       {"mm": "Backend ကို ဤ machine ပေါ်တွင် start ပြီး App ဖွင့်မည်",
                               "en": "Start the backend on this machine, then open the app"},
    "choice_join_btn":        {"mm": "⚡  LAN ဆာဗာသို့ ချိတ်ဆက်မည်",
                               "en": "⚡  Join LAN Server"},
    "choice_join_desc":       {"mm": "LAN ပေါ်ရှိ ဆာဗာ IP ထည့်ပြီး App ဖွင့်မည်",
                               "en": "Enter a server IP on your LAN, then open the app"},
    "server_starting_msg":    {"mm": "ဆာဗာ စတင်နေသည်...",         "en": "Starting server…"},
    "server_ready_msg":       {"mm": "ဆာဗာ အသင့်ဖြစ်ပြီ!",        "en": "Server is ready!"},
    "server_start_failed":    {"mm": "ဆာဗာ မစတင်နိုင်ပါ။ Port 8000 ကို စစ်ဆေးပါ။",
                               "en": "Server failed to start. Check that port 8000 is free."},
    "host_active_label":      {"mm": "🟢 ဆာဗာ လည်ပတ်နေသည် — ချိတ်ဆက်ရန်: {ip} : {port}",
                               "en": "🟢 Server Active — Connect via: {ip} : {port}"},

    # ── Company / ServiceType settings ───────────────────────
    "settings_companies":     {"mm": "ကုမ္ပဏီများ",               "en": "Companies"},
    "settings_service_types": {"mm": "ဝန်ဆောင်မှုအမျိုးအစားများ","en": "Service Types"},
    "add_company":            {"mm": "+ ကုမ္ပဏီထည့်မည်",          "en": "+ Add Company"},
    "edit_company":           {"mm": "ကုမ္ပဏီပြင်မည်",            "en": "Edit Company"},
    "add_service_type":       {"mm": "+ ဝန်ဆောင်မှုထည့်မည်",     "en": "+ Add Service Type"},
    "upload_logo":            {"mm": "Logo တင်မည်",               "en": "Upload Logo"},
    "col_company":            {"mm": "ကုမ္ပဏီ",                   "en": "Company"},
    "col_category":           {"mm": "အမျိုးအစား",                "en": "Category"},
    "col_logo":               {"mm": "Logo",                       "en": "Logo"},
    "col_operation":          {"mm": "လုပ်ဆောင်ချက်",             "en": "Operation"},
    "col_name":               {"mm": "အမည်",                      "en": "Name"},
    "col_status":             {"mm": "အခြေအနေ",                   "en": "Status"},
    "col_actions":            {"mm": "လုပ်ဆောင်ချက်",             "en": "Actions"},
    "company_name_ph":        {"mm": "ကုမ္ပဏီအမည်",               "en": "Company Name"},
    "category_label":         {"mm": "အမျိုးအစား:",               "en": "Category:"},
    "service_name_ph":        {"mm": "ဝန်ဆောင်မှုအမည်",           "en": "Service Name"},
    "operation_label":        {"mm": "လုပ်ဆောင်ချက်:",            "en": "Operation:"},
    "logo_uploaded":          {"mm": "Logo တင်ပြီ။",              "en": "Logo uploaded successfully."},
    "company_created":        {"mm": "ကုမ္ပဏီ ဖန်တီးပြီ။",       "en": "Company created."},
    "company_updated":        {"mm": "ကုမ္ပဏီ ပြင်ဆင်ပြီ။",      "en": "Company updated."},
    "company_deactivated":    {"mm": "ကုမ္ပဏီ ပိတ်ထားပြီ။",      "en": "Company deactivated."},
    "service_type_created":   {"mm": "ဝန်ဆောင်မှုအမျိုးအစား ဖန်တီးပြီ။",
                               "en": "Service type created."},
    "service_type_deactivated":{"mm": "ဝန်ဆောင်မှုအမျိုးအစား ပိတ်ထားပြီ။",
                               "en": "Service type deactivated."},
    "err_company_name_empty": {"mm": "ကုမ္ပဏီအမည် ထည့်ပါ။",      "en": "Company name is required."},
    "err_service_name_empty": {"mm": "ဝန်ဆောင်မှုအမည် ထည့်ပါ။",  "en": "Service name is required."},
    "err_select_company":     {"mm": "ကုမ္ပဏီ ရွေးပါ",            "en": "Please select a company"},
    "err_select_service_type":{"mm": "ဝန်ဆောင်မှုအမျိုးအစား ရွေးပါ","en": "Please select a service type"},
    "err_tier_from_required": {"mm": "From amount သည် သုညထက် ကြီးရမည်။",
                               "en": "From amount must be greater than zero."},
    "err_tier_to_required":   {"mm": "To amount သည် သုညထက် ကြီးရမည်။",
                               "en": "To amount must be greater than zero."},
    "err_tier_range_order":   {"mm": "To amount သည် From amount ထက် ကြီးရမည်။",
                               "en": "To amount must be greater than From amount."},
    "err_tier_overlap":       {"mm": "{af}–{at} သည် ရှိပြီးသား tier {ef}–{et} နှင့် ထပ်နေသည်။",
                               "en": "Range {af}–{at} overlaps with existing tier {ef}–{et}."},
    "logo_too_large":         {"mm": "Logo ဖိုင် 200KB ထက် မကြီးရ",
                               "en": "Logo file must be ≤ 200 KB"},
    "logo_invalid_type":      {"mm": "PNG, JPG, SVG ဖိုင်သာ ခွင့်ပြုသည်",
                               "en": "Only PNG, JPG, or SVG files are allowed"},
    "confirm_deactivate":     {"mm": "ပိတ်ရန် သေချာပါသလား?",     "en": "Are you sure you want to deactivate?"},

    # ── User Settings CRUD ────────────────────────────────
    "edit_user":              {"mm": "အသုံးပြုသူ ပြင်မည်",         "en": "Edit User"},
    "reset_password":         {"mm": "စကားဝှက် ပြန်သတ်မှတ်မည်",   "en": "Reset Password"},
    "password_reset_ok":      {"mm": "စကားဝှက် ပြောင်းပြီ။",       "en": "Password reset successfully."},
    "user_updated":           {"mm": "အသုံးပြုသူ ပြင်ဆင်ပြီ။",     "en": "User updated."},
    "col_username":           {"mm": "အသုံးပြုသူအမည်",             "en": "Username"},
    "col_fullname":           {"mm": "အမည်အပြည့်",                 "en": "Full Name"},
    "col_role":               {"mm": "ရာထူး",                      "en": "Role"},
    "col_active":             {"mm": "အသုံးပြုနေဆဲ",               "en": "Active"},
    "col_created":            {"mm": "ဖန်တီးသည့်ရက်",              "en": "Created"},
    "col_password":           {"mm": "စကားဝှက်",                   "en": "Password"},
    "username_ph":            {"mm": "အသုံးပြုသူအမည်",             "en": "Username"},
    "fullname_ph":            {"mm": "အမည်အပြည့်",                 "en": "Full Name"},
    "err_username_empty":     {"mm": "အသုံးပြုသူအမည် ထည့်ပါ",     "en": "Username is required"},
    "err_fullname_empty":     {"mm": "အမည်အပြည့် ထည့်ပါ",         "en": "Full name is required"},
    "err_password_empty":     {"mm": "စကားဝှက် ထည့်ပါ",           "en": "Password is required"},

    # ── Account Settings CRUD ─────────────────────────────
    "add_account":            {"mm": "+ အကောင့်ထည့်မည်",           "en": "+ Add Account"},
    "edit_account":           {"mm": "အကောင့် ပြင်မည်",             "en": "Edit Account"},
    "account_created":        {"mm": "အကောင့် ဖန်တီးပြီ။",         "en": "Account created."},
    "account_updated":        {"mm": "အကောင့် ပြင်ဆင်ပြီ။",        "en": "Account updated."},
    "account_deleted":        {"mm": "အကောင့် ဖျက်ပြီ။",           "en": "Account deleted."},
    "delete_account":         {"mm": "အကောင့် ဖျက်မည်",             "en": "Delete Account"},
    "confirm_delete_account": {"mm": "ဤအကောင့်ကို ဖျက်မည်လား?",   "en": "Are you sure you want to delete this account?"},
    "action_cannot_be_undone":{"mm": "ဤလုပ်ဆောင်ချက်ကို ပြန်မရပါ။","en": "This action cannot be undone."},
    "adjust_balance":         {"mm": "လက်ကျန်ငွေ ပြင်မည်",          "en": "Adjust Balance"},
    "balance_adjusted":       {"mm": "လက်ကျန်ငွေ ပြင်ဆင်ပြီ။",      "en": "Balance adjusted."},
    "lbl_current_balance":    {"mm": "လက်ရှိ လက်ကျန်ငွေ",           "en": "Current Balance"},
    "lbl_adjustment":         {"mm": "ပြင်ဆင်မည့် ပမာဏ",            "en": "Adjustment Amount"},
    "lbl_remark":             {"mm": "မှတ်ချက်",                    "en": "Remark"},
    "account_name_ph":        {"mm": "အကောင့်အမည်",                "en": "Account Name"},
    "phone_ph":               {"mm": "ဖုန်းနံပါတ်",                "en": "Phone Number"},
    "col_phone":              {"mm": "ဖုန်းနံပါတ်",                "en": "Phone"},
    "col_balance":            {"mm": "လက်ကျန်",                    "en": "Balance"},
    "load_all":               {"mm": "အားလုံးကြည့်မည်",            "en": "Load All"},
    "err_account_name_empty": {"mm": "အကောင့်အမည် ထည့်ပါ",        "en": "Account name is required"},
    "err_phone_empty":        {"mm": "ဖုန်းနံပါတ် ထည့်ပါ",        "en": "Phone number is required"},

    # ── Transaction Admin ─────────────────────────────────
    "admin_transactions":     {"mm": "ငွေလွှဲ စီမံခန့်ခွဲမှု (Owner)", "en": "Transaction Admin (Owner)"},
    "col_type":               {"mm": "အမျိုးအစား",                 "en": "Type"},
    "col_account":            {"mm": "အကောင့်",                    "en": "Account"},
    "col_to_account":         {"mm": "ပေးပို့သည့် အကောင့်",       "en": "To Account"},
    "col_customer":           {"mm": "ဖောက်သည်",                   "en": "Customer"},
    "col_amount":             {"mm": "ငွေပမာဏ",                    "en": "Amount"},
    "col_fee":                {"mm": "ကြေး",                       "en": "Fee"},
    "col_commission":         {"mm": "ကော်မရှင်",                  "en": "Commission"},
    "col_currency":           {"mm": "ငွေကြေး",                    "en": "Currency"},
    "date_from":              {"mm": "မှ ရက်",                     "en": "Date From"},
    "date_to":                {"mm": "သို့ ရက်",                   "en": "Date To"},
    "delete":                 {"mm": "ဖျက်မည်",                    "en": "Delete"},
    "confirm_delete_txn":     {"mm": "ငွေလွှဲ ဖျက်မည်။ သေချာပါသလား?",
                               "en": "Delete this transaction permanently?"},

    # ── Activity Log ──────────────────────────────────────
    "admin_activity_logs":    {"mm": "လုပ်ဆောင်ချက် မှတ်တမ်း (Owner)",
                               "en": "Activity Logs (Owner)"},
    "col_user":               {"mm": "အသုံးပြုသူ",                 "en": "User"},
    "col_action":             {"mm": "လုပ်ဆောင်ချက်",              "en": "Action"},
    "col_entity":             {"mm": "ဇယား",                       "en": "Entity"},
    "col_entity_id":          {"mm": "Entity ID",                   "en": "Entity ID"},
    "col_details":            {"mm": "အသေးစိတ်",                   "en": "Details"},

    # ── Cash Float Admin ──────────────────────────────────
    "admin_cash_floats":      {"mm": "ငွေသားလုပ်ငန်း (Owner)",     "en": "Cash Float Admin (Owner)"},
    "float_detail":           {"mm": "Float အသေးစိတ်",             "en": "Float Detail"},
    "float_status":           {"mm": "အခြေအနေ",                    "en": "Status"},
    "float_total":            {"mm": "စုစုပေါင်း",                 "en": "Total"},
    "float_closing":          {"mm": "ပိတ်ချိန်ငွေ",               "en": "Closing Total"},
    "float_issued_by":        {"mm": "ထုတ်ပေးသူ",                  "en": "Issued By"},
    "float_received":         {"mm": "လက်ခံသည့်ချိန်",             "en": "Received At"},
    "float_closed":           {"mm": "ပိတ်သည့်ချိန်",              "en": "Closed At"},
    "float_denominations":    {"mm": "ငွေတန်ဖိုးအလိုက်",          "en": "Denominations"},
    "col_denomination":       {"mm": "ငွေတန်ဖိုး",                 "en": "Denomination"},
    "col_quantity":           {"mm": "အရေအတွက်",                   "en": "Quantity"},
    "col_subtotal":           {"mm": "ပင်မပမာဏ",                   "en": "Subtotal"},
    "col_note":               {"mm": "မှတ်ချက်",                   "en": "Note"},
    "col_employee":           {"mm": "ဝန်ထမ်း",                    "en": "Employee"},
    "no_denomination_data":   {"mm": "ငွေတန်ဖိုး မှတ်တမ်း မရှိပါ","en": "No denomination data available."},
    "edit":                   {"mm": "ပြင်မည်",                    "en": "Edit"},

    # ── Settings sections ─────────────────────────────────
    "settings_users":         {"mm": "အသုံးပြုသူ စီမံခန့်ခွဲမှု",  "en": "User Management"},
    "settings_accounts":      {"mm": "အကောင့် စီမံခန့်ခွဲမှု",    "en": "Account Management"},
    "settings_txn_admin":     {"mm": "ငွေလွှဲ စီမံခန့်ခွဲမှု",    "en": "Transaction Admin"},
    "settings_logs":          {"mm": "လုပ်ဆောင်ချက် မှတ်တမ်း",    "en": "Activity Logs"},
    "settings_floats":        {"mm": "ငွေသားလုပ်ငန်း",             "en": "Cash Float Admin"},

    # ── Admin panel navigation ────────────────────────────
    "admin_panel_title":      {"mm": "Admin Panel",                 "en": "Admin Panel"},
    "admin_group_master":     {"mm": "Master Data",                 "en": "Master Data"},
    "admin_group_staff":      {"mm": "ဝန်ထမ်းများ",               "en": "Staff"},
    "admin_group_operations": {"mm": "လုပ်ငန်းများ",               "en": "Operations"},
    "admin_group_system":     {"mm": "System",                      "en": "System"},
    "admin_companies":        {"mm": "ကုမ္ပဏီများ",               "en": "Companies"},
    "admin_service_types":    {"mm": "ဝန်ဆောင်မှုအမျိုးအစားများ", "en": "Service Types"},
    "admin_accounts":         {"mm": "အကောင့်များ",                "en": "Accounts"},
    "admin_commission_tiers": {"mm": "ကော်မရှင် Tiers",           "en": "Commission Tiers"},
    "admin_exchange_rate":    {"mm": "ငွေလဲနှုန်း",               "en": "Exchange Rate"},
    "admin_users":            {"mm": "အသုံးပြုသူများ",             "en": "Users"},
    "admin_all_transactions": {"mm": "ငွေလွှဲ အားလုံး",           "en": "All Transactions"},
    "admin_activity_logs":    {"mm": "လုပ်ဆောင်ချက် မှတ်တမ်း",    "en": "Activity Logs"},
    "admin_cash_floats":      {"mm": "ငွေသားလုပ်ငန်း",             "en": "Cash Floats"},
    "admin_server_connection": {"mm": "ဆာဗာ ချိတ်ဆက်မှု",          "en": "Server Connection"},
    "admin_change_password":  {"mm": "စကားဝှက်ပြောင်းမည်",        "en": "Change Password"},
    "nav_daily_closing":      {"mm": "နေ့ ပိတ်သိမ်းမှု",            "en": "Daily Closing"},

    # ── Server Connection page ───────────────────────────
    "server_status_label":    {"mm": "ဆာဗာ အခြေအနေ:",             "en": "Server Status:"},
    "server_status_online":   {"mm": "Online",                      "en": "Online"},
    "server_ip_label":        {"mm": "Local IP လိပ်စာ:",           "en": "Local IP Address:"},
    "server_port_label":      {"mm": "Port နံပါတ်:",               "en": "Port:"},
    "server_client_link_label":{"mm": "Client ချိတ်ဆက်ရန် Link:",  "en": "Client Setup Link:"},
    "server_copy_btn":        {"mm": "ကူးယူမည်",                   "en": "Copy"},
    "server_copied_msg":      {"mm": "ကူးယူပြီးပါပြီ!",            "en": "Copied to clipboard!"},
    "server_refresh_btn":     {"mm": "IP ပြန်စစ်မည်",              "en": "Refresh IP"},
    "save_password":          {"mm": "စကားဝှက်သိမ်းမည်",           "en": "Save Password"},

    # ── Daily Closing / Reconciliation ───────────────────
    "closing_title":           {"mm": "နေ့ ပိတ်သိမ်းမှု အစီရင်ခံစာ",  "en": "Daily Closing Report"},
    "closing_digital_section": {"mm": "ဒစ်ဂျစ်တယ် အကောင့် ငွေပမာဏ", "en": "Digital Account Balances"},
    "closing_physical_section":{"mm": "ငွေသား (လက်ကိုင်)",            "en": "Physical Cash"},
    "closing_main_vault":      {"mm": "ပင်မ ငွေသေတ္တာ",               "en": "Main Vault Balance"},
    "closing_employee_floats": {"mm": "ဝန်ထမ်းများ လက်ကိုင်ငွေ",     "en": "Employee Cash in Hand"},
    "closing_pending_deposits":{"mm": "ငွေသေတ္တာ မဝင်သေးသော အပ်ငွေ", "en": "Pending Deposits (Not in Vault)"},
    "col_opening_bal":         {"mm": "ဖွင့်ချိန်",                    "en": "Opening"},
    "col_net_change":          {"mm": "ကွာခြားချက်",                   "en": "Net Change"},
    "col_closing_bal":         {"mm": "ပိတ်ချိန်",                    "en": "Closing"},
    "col_float_balance":       {"mm": "Float ငွေပမာဏ",                "en": "Float Balance"},
    "closing_total_cash":      {"mm": "ငွေသား စုစုပေါင်း",             "en": "Total Cash Assets"},
    "closing_total_digital":   {"mm": "ဒစ်ဂျစ်တယ် စုစုပေါင်း",        "en": "Total Digital Assets"},
    "closing_grand_total":     {"mm": "ကြီးမားသော စုစုပေါင်း",         "en": "Grand Total"},
    "btn_close_day":           {"mm": "နေ့ ပိတ်မည်",                  "en": "Close Day"},
    "closing_confirm_title":   {"mm": "နေ့ ပိတ်ရန် သေချာပါသလား?",    "en": "Close Day?"},
    "closing_confirm_msg":     {
        "mm": "ဝန်ထမ်းများ Float အားလုံး ပိတ်မည်ဖြစ်ပြီး ညှိနှိုင်းမှု snapshot သိမ်းဆည်းမည်။ ဆက်လက်မည်လား?",
        "en": "All employee floats will be closed and the reconciliation snapshot will be saved. Continue?",
    },
    "closing_day_closed":      {"mm": "နေ့ ပိတ်သိမ်းပြီး။",            "en": "Day closed successfully."},
    "closing_loading":         {"mm": "ဒေတာ ဆွဲယူနေသည်...",           "en": "Loading data..."},
    "closing_no_floats":       {"mm": "ACTIVE Float မရှိပါ",           "en": "No active employee floats"},
    "closing_no_pending":      {"mm": "Pending အပ်ငွေ မရှိပါ",         "en": "No pending deposits"},
}


# ─────────────────────────────────────────────────────────
# Runtime state
# ─────────────────────────────────────────────────────────
_locale: str = "mm"
_listeners: list[Callable[[], None]] = []

# Config file path (same file used by run_client.py)
_CONFIG_PATH: str = ""  # resolved lazily on first persist


def _resolve_config_path() -> str:
    """Return the absolute path to client_config.json."""
    import sys
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "client_config.json")


# ─────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────

def t(key: str, **kwargs: object) -> str:
    """
    Return the translated string for *key* in the current locale.

    Falls back to English if the mm translation is missing,
    and falls back to the bare key if the key is unknown.
    Keyword arguments are applied via str.format_map().
    """
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key
    text = entry.get(_locale) or entry.get("en") or key
    if kwargs:
        try:
            text = text.format_map(kwargs)
        except (KeyError, ValueError):
            pass
    return text


def get_locale() -> str:
    """Return the currently active locale code ('mm' or 'en')."""
    return _locale


def set_locale(locale: str) -> None:
    """
    Switch to *locale* ('mm' or 'en'), notify all listeners,
    and persist the choice to client_config.json.
    """
    global _locale
    if locale not in ("mm", "en"):
        return
    _locale = locale
    _persist_locale(locale)
    for cb in list(_listeners):
        try:
            cb()
        except Exception:
            pass


def on_change(callback: Callable[[], None]) -> None:
    """Register *callback* to be called whenever the locale changes."""
    if callback not in _listeners:
        _listeners.append(callback)


def ui_font(size: int, bold: bool = False) -> "QFont":
    """
    Return a QFont appropriate for the current locale.
    Myanmar text uses Padauk (Unicode); English uses Segoe UI.
    """
    family = "Padauk" if _locale == "mm" else "Segoe UI"
    weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
    return QFont(family, size, weight)


# ─────────────────────────────────────────────────────────
# Persistence helpers
# ─────────────────────────────────────────────────────────

def _persist_locale(locale: str) -> None:
    """Write the locale to client_config.json."""
    try:
        path = _resolve_config_path()
        cfg: dict = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["language"] = locale
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _load_persisted_locale() -> None:
    """Read the saved locale from client_config.json on import."""
    global _locale
    try:
        path = _resolve_config_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            lang = cfg.get("language", "mm")
            if lang in ("mm", "en"):
                _locale = lang
    except Exception:
        pass


# Load persisted locale immediately on import
_load_persisted_locale()
