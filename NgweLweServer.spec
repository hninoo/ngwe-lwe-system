# -*- mode: python ; coding: utf-8 -*-
# NgweLweServer.exe — server manager
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
    'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    'anyio._backends._asyncio', 'anyio._backends._trio',
    'bcrypt', 'passlib',
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
    _logos_tree,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NgweLweServer',
)
