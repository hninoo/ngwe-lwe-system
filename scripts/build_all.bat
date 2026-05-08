@echo off
pushd %~dp0..

set "VERSION=1.0.0-beta"

echo ============================================================
echo   NgweLwe System %VERSION% -- Full Build
echo   Builds: NgweLwe-v%VERSION%-Setup.exe   (client)
echo           NgweLweServer-v%VERSION%-Setup.exe   (server manager)
echo ============================================================
echo.

:: ── Activate venv ────────────────────────────────────────────
call venv\Scripts\activate.bat
if errorlevel 1 goto :venv_error

pip install pyinstaller --quiet

:: ── Locate Inno Setup (quotes around assignment, not value) ──
set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if not defined ISCC goto :iscc_error

:: ── Kill any running instances (release DLL locks) ───────────
echo [CLEAN] Stopping any running app instances...
taskkill /f /im NgweLweSystem.exe  >nul 2>&1
taskkill /f /im NgweLweServer.exe  >nul 2>&1
timeout /t 1 /nobreak >nul

:: ── Full clean ───────────────────────────────────────────────
echo [CLEAN] Removing previous build artefacts...
if exist "dist\NgweLweSystem" rmdir /s /q "dist\NgweLweSystem"
if exist "dist\NgweLweServer" rmdir /s /q "dist\NgweLweServer"
if exist "build"              rmdir /s /q "build"
echo [CLEAN] Done.
echo.

if not exist "installer"    mkdir "installer"
if not exist "assets\logos" mkdir "assets\logos"

:: ════════════════════════════════════════════════════════════
:: 1/4  PyInstaller -- NgweLweSystem  (unified client)
:: ════════════════════════════════════════════════════════════
echo [1/4] Building NgweLweSystem.exe (unified client) ...
echo.
pyinstaller NgweLweClient.spec
if errorlevel 1 goto :pyinstaller_error
echo [1/4] Done.

:: ════════════════════════════════════════════════════════════
:: 2/4  Inno Setup -- NgweLwe-v%VERSION%-Setup.exe
:: ════════════════════════════════════════════════════════════
echo.
echo [2/4] Compiling NgweLwe-v%VERSION%-Setup.exe ...
echo.
"%ISCC%" setup.iss
if errorlevel 1 goto :inno_error
echo [2/4] Done.

:: ════════════════════════════════════════════════════════════
:: 3/4  PyInstaller -- NgweLweServer  (server manager)
:: ════════════════════════════════════════════════════════════
echo.
echo [3/4] Building NgweLweServer.exe (server manager) ...
echo.
if exist "build" rmdir /s /q "build"
pyinstaller NgweLweServer.spec
if errorlevel 1 goto :pyinstaller_error
echo [3/4] Done.

:: ════════════════════════════════════════════════════════════
:: 4/4  Inno Setup -- NgweLweServer-v%VERSION%-Setup.exe
:: ════════════════════════════════════════════════════════════
echo.
echo [4/4] Compiling NgweLweServer-v%VERSION%-Setup.exe ...
echo.
"%ISCC%" setup_server.iss
if errorlevel 1 goto :inno_error
echo [4/4] Done.

echo.
echo ============================================================
echo   BUILD COMPLETE  -- v%VERSION%
echo ============================================================
echo.
echo   installer\NgweLwe-v%VERSION%-Setup.exe        (Client / Host)
echo   installer\NgweLweServer-v%VERSION%-Setup.exe  (Server Manager)
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
echo Run: python -m venv venv ^&^& pip install -r requirements.txt
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
