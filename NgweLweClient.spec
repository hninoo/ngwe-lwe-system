# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for NgweLweSystem.exe (unified host+client launcher)
# Entry point: main.py
from PyInstaller.utils.hooks import collect_all

datas = [
    ('backend/database.sql', 'backend'),
    ('assets/logos',         'assets/logos'),
    ('assets/app_icon.ico',  'assets'),
]
binaries = []
hiddenimports = [
    # Uvicorn internals
    'uvicorn.logging',
    'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    # Async / crypto
    'anyio._backends._asyncio', 'anyio._backends._trio',
    'bcrypt', 'passlib', 'multipart',
    # i18n
    'i18n', 'i18n.i18n',
    # Backend — all routes included so host mode works
    'backend', 'backend.main', 'backend.database', 'backend.auth',
    'backend.websocket_manager',
    'backend.routes', 'backend.routes.auth', 'backend.routes.accounts',
    'backend.routes.companies', 'backend.routes.service_types',
    'backend.routes.services', 'backend.routes.transactions',
    'backend.routes.dashboard', 'backend.routes.users',
    'backend.routes.exchange_rates', 'backend.routes.reports',
    'backend.routes.commission_tiers', 'backend.routes.activity_logs',
    'backend.routes.cashier',
    # Repositories
    'repositories', 'repositories.account_repository',
    'repositories.cash_float_repository', 'repositories.cash_denomination_repository',
    'repositories.user_repository',
    # Services + client UI
    'services', 'services.api_client',
    'views', 'views.login_view', 'views.dashboard_view',
    'views.transaction_view', 'views.cashier_view',
    'views.receive_float_dialog',
    'views.admin_page',
    'views.widgets', 'views.widgets.company_selector', 'views.widgets.company_logo_label',
    'views.settings', 'views.settings.company_settings_view',
    'views.settings.service_type_settings_view',
    'views.settings.user_settings_view', 'views.settings.account_settings_view',
    'views.settings.transaction_admin_view', 'views.settings.activity_log_view',
    'views.settings.cash_float_admin_view',
]

for pkg in ('uvicorn', 'fastapi', 'PyQt6'):
    tmp = collect_all(pkg)
    datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    icon='assets/app_icon.ico',
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
    Tree('assets/logos', prefix='assets/logos'),
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NgweLweSystem',
)
