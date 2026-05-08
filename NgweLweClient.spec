# -*- mode: python ; coding: utf-8 -*-
# NgweLwe.exe — unified host+client launcher
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

# ── python-multipart: three-layer collection ──────────────────────────────────
# collect_all('multipart') can silently return nothing because the distribution
# is registered as "python-multipart" while the importable name is "multipart".
# collect_submodules() walks the module directory directly and is distribution-
# name-agnostic, so it always finds every submodule regardless of metadata.
_mp_mods = collect_submodules('multipart')

datas = [
    ('backend/database.sql', 'backend'),
    ('assets',               'assets'),
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
    'bcrypt', 'passlib',
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
    # python-multipart: explicit names as final fail-safe
    'multipart', 'multipart.multipart',
] + _mp_mods  # append every submodule found by directory walk

# collect_all covers data files, binaries, and any hook-discovered imports
for pkg in ('uvicorn', 'fastapi', 'PyQt6', 'multipart'):
    tmp = collect_all(pkg)
    datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

# Guard Tree so an empty or missing logos folder never aborts the build
_logos_tree = (
    Tree('assets/logos', prefix='assets/logos')
    if os.path.isdir('assets/logos') and os.listdir('assets/logos')
    else []
)

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
    name='NgweLwe',
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
    _logos_tree,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NgweLwe',
)
