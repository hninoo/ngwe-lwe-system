# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [
    ('backend/database.sql', 'backend'),
    ('assets/logos',        'assets/logos'),
    ('assets/app_icon.ico', 'assets'),
]
binaries = []
hiddenimports = [
    'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    'anyio._backends._asyncio', 'anyio._backends._trio',
    'bcrypt', 'passlib', 'multipart',
    # i18n
    'i18n', 'i18n.i18n',
    # backend modules
    'backend', 'backend.main', 'backend.database', 'backend.auth',
    'backend.websocket_manager',
    'backend.routes', 'backend.routes.auth', 'backend.routes.accounts',
    'backend.routes.companies', 'backend.routes.service_types',
    'backend.routes.services', 'backend.routes.transactions',
    'backend.routes.dashboard', 'backend.routes.users',
    'backend.routes.exchange_rates', 'backend.routes.reports',
    'backend.routes.commission_tiers', 'backend.routes.activity_logs',
    'backend.routes.cashier',
]

for pkg in ('uvicorn', 'fastapi', 'PyQt6'):
    tmp = collect_all(pkg)
    datas += tmp[0]; binaries += tmp[1]; hiddenimports += tmp[2]

a = Analysis(
    ['run_server_app.py'],
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
    name='NgweLweServer',
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
    name='NgweLweServer',
)
