# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = [
    'anyio._backends._asyncio', 'anyio._backends._trio',
    'bcrypt', 'passlib', 'multipart',
    # i18n
    'i18n', 'i18n.i18n',
    # services + views
    'services', 'services.api_client',
    'views', 'views.login_view', 'views.dashboard_view',
    'views.transaction_view', 'views.cashier_view',
    'views.receive_float_dialog',
    'views.admin_page',
    'views.widgets', 'views.widgets.company_selector', 'views.widgets.company_logo_label',
    'views.settings', 'views.settings.company_settings_view', 'views.settings.service_type_settings_view',
    'views.settings.user_settings_view', 'views.settings.account_settings_view',
    'views.settings.transaction_admin_view', 'views.settings.activity_log_view',
    'views.settings.cash_float_admin_view',
]

for pkg in ('PyQt6',):
    tmp = collect_all(pkg)
    datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

a = Analysis(
    ['run_client.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['uvicorn', 'fastapi', 'backend'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NgweLweSystem',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NgweLweSystem',
)
