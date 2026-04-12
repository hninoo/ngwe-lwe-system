@echo off
setlocal enabledelayedexpansion
echo ============================================================
echo   NgweLwe System v1.0.1 — Full Build
echo   Builds: NgweLweSystem-Setup-v1.0.1.exe
echo           NgweLweServer-Setup-v1.0.1.exe
echo ============================================================
echo.

:: ── Activate venv ───────────────────────────────────────────
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate venv. Run: python -m venv venv ^&^& pip install -r requirements.txt
    pause & exit /b 1
)

pip install pyinstaller --quiet

:: ── Locate Inno Setup ───────────────────────────────────────
set ISCC=
for %%P in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) do (
    if exist %%P set ISCC=%%P
)
if "%ISCC%"=="" (
    echo ERROR: Inno Setup 6 not found.
    echo Download from: https://jrsoftware.org/isdl.php
    pause & exit /b 1
)

if not exist installer mkdir installer

:: ════════════════════════════════════════════════════════════
:: 1/4  PyInstaller — NgweLweSystem  (client)
:: ════════════════════════════════════════════════════════════
echo [1/4] Building NgweLweSystem.exe (client) ...
echo.
if exist dist\NgweLweSystem rmdir /s /q dist\NgweLweSystem
if exist build              rmdir /s /q build

pyinstaller NgweLweClient.spec
if errorlevel 1 (
    echo ERROR: NgweLweSystem PyInstaller build failed.
    pause & exit /b 1
)
echo [1/4] Done.

:: ════════════════════════════════════════════════════════════
:: 2/4  Inno Setup — NgweLweSystem-Setup-v1.0.1.exe
:: ════════════════════════════════════════════════════════════
echo.
echo [2/4] Compiling NgweLweSystem-Setup-v1.0.1.exe ...
echo.
%ISCC% setup.iss
if errorlevel 1 (
    echo ERROR: Inno Setup failed for NgweLweSystem.
    pause & exit /b 1
)
echo [2/4] Done.

:: ════════════════════════════════════════════════════════════
:: 3/4  PyInstaller — NgweLweServer  (server manager)
:: ════════════════════════════════════════════════════════════
echo.
echo [3/4] Building NgweLweServer.exe (server manager) ...
echo.
if exist dist\NgweLweServer rmdir /s /q dist\NgweLweServer
if exist build              rmdir /s /q build

pyinstaller NgweLweServer.spec
if errorlevel 1 (
    echo ERROR: NgweLweServer PyInstaller build failed.
    pause & exit /b 1
)
echo [3/4] Done.

:: ════════════════════════════════════════════════════════════
:: 4/4  Inno Setup — NgweLweServer-Setup-v1.0.1.exe
:: ════════════════════════════════════════════════════════════
echo.
echo [4/4] Compiling NgweLweServer-Setup-v1.0.1.exe ...
echo.
%ISCC% setup_server.iss
if errorlevel 1 (
    echo ERROR: Inno Setup failed for NgweLweServer.
    pause & exit /b 1
)
echo [4/4] Done.

:: ════════════════════════════════════════════════════════════
echo.
echo ============================================================
echo   BUILD COMPLETE  — v1.0.1
echo ============================================================
echo.
echo   installer\NgweLweSystem-Setup-v1.0.1.exe   (Client)
echo   installer\NgweLweServer-Setup-v1.0.1.exe   (Server)
echo.
echo   Default credentials:
echo     owner    / admin123
echo     employee / employee123
echo     cashier  / cashier123
echo.
pause
