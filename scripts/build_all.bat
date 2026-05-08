@echo off
pushd %~dp0..

set "VERSION=1.0.0-beta"

echo ============================================================
echo   NgweLwe %VERSION% -- Full Build
echo   Output: installer\NgweLwe-v%VERSION%-Setup.exe
echo           (unified installer -- Host or Client Only)
echo ============================================================
echo.

:: ── Activate venv ────────────────────────────────────────────
call venv\Scripts\activate.bat
if errorlevel 1 goto :venv_error

pip install pyinstaller --quiet

:: ── Locate Inno Setup ────────────────────────────────────────
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if not defined ISCC goto :iscc_error

:: ── Kill any running instances (release DLL locks) ───────────
echo [CLEAN] Stopping running instances...
taskkill /f /im NgweLwe.exe /t                         >nul 2>&1
taskkill /f /im NgweLweServer.exe /t                   >nul 2>&1
taskkill /f /im python.exe /t /fi "status eq running"  >nul 2>&1
timeout /t 3 /nobreak >nul

:: ── Full clean (rmdir first, PowerShell fallback if locked) ──
echo [CLEAN] Removing previous build artefacts...
if exist "dist\NgweLwe" (
    rmdir /s /q "dist\NgweLwe" 2>nul
    if exist "dist\NgweLwe" (
        echo [CLEAN] Retrying with PowerShell...
        powershell -NoProfile -Command "Remove-Item -Recurse -Force 'dist\NgweLwe' -ErrorAction SilentlyContinue"
    )
)
if exist "dist\NgweLweServer" (
    rmdir /s /q "dist\NgweLweServer" 2>nul
    if exist "dist\NgweLweServer" (
        echo [CLEAN] Retrying with PowerShell...
        powershell -NoProfile -Command "Remove-Item -Recurse -Force 'dist\NgweLweServer' -ErrorAction SilentlyContinue"
    )
)
if exist "build" (
    rmdir /s /q "build" 2>nul
    if exist "build" (
        powershell -NoProfile -Command "Remove-Item -Recurse -Force 'build' -ErrorAction SilentlyContinue"
    )
)
echo [CLEAN] Done.
echo.

if not exist "installer"    mkdir "installer"
if not exist "assets\logos" mkdir "assets\logos"

:: ════════════════════════════════════════════════════════════
:: 1/3  PyInstaller -- NgweLweSystem.exe  (client)
::      Assets declared in NgweLweClient.spec datas list.
:: ════════════════════════════════════════════════════════════
echo [1/3] Building NgweLweSystem.exe (client) ...
echo.
pyinstaller NgweLweClient.spec
if errorlevel 1 goto :pyinstaller_error
echo [1/3] Done.

:: ════════════════════════════════════════════════════════════
:: 2/3  PyInstaller -- NgweLweServer.exe  (server)
::      Assets declared in NgweLweServer.spec datas list.
::      NOTE: --add-data is ignored when using a .spec file;
::      ('assets', 'assets') in the spec covers all assets/.
:: ════════════════════════════════════════════════════════════
echo.
echo [2/3] Building NgweLweServer.exe (server) ...
echo.
if exist "build" (
    rmdir /s /q "build" 2>nul
    if exist "build" powershell -NoProfile -Command "Remove-Item -Recurse -Force 'build' -ErrorAction SilentlyContinue"
)
pyinstaller NgweLweServer.spec
if errorlevel 1 goto :pyinstaller_error
echo [2/3] Done.

:: ════════════════════════════════════════════════════════════
:: 3/3  Inno Setup -- NgweLwe-v%VERSION%-Setup.exe (unified)
::      Requires both dist\NgweLweSystem and dist\NgweLweServer.
::      User selects Host or Client Only during installation.
:: ════════════════════════════════════════════════════════════
echo.
echo [3/3] Compiling NgweLwe-v%VERSION%-Setup.exe (unified installer) ...
echo.
"%ISCC%" setup.iss
if errorlevel 1 goto :inno_error
echo [3/3] Done.

echo.
echo ============================================================
echo   BUILD COMPLETE  -- v%VERSION%
echo ============================================================
echo.
echo   installer\NgweLwe-v%VERSION%-Setup.exe
echo.
echo   The installer will ask the user to choose:
echo     Host (Server + Client)  -- runs server + opens client
echo     Client Only             -- connects to a LAN server
echo.
echo   Default credentials:
echo     owner    / admin123
echo     employee / employee123
echo     cashier  / cashier123
echo.
pause
popd
exit /b 0

:: ── Error handlers ───────────────────────────────────────────
:venv_error
echo.
echo ERROR: Could not activate venv.
echo Run:   python -m venv venv ^&^& pip install -r requirements.txt
pause
popd
exit /b 1

:iscc_error
echo.
echo ERROR: Inno Setup 6 not found.
echo Download from: https://jrsoftware.org/isdl.php
pause
popd
exit /b 1

:pyinstaller_error
echo.
echo ERROR: PyInstaller build failed. See output above.
pause
popd
exit /b 1

:inno_error
echo.
echo ERROR: Inno Setup compilation failed. See output above.
pause
popd
exit /b 1
