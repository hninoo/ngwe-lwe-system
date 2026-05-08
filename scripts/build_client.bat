@echo off
pushd %~dp0..
echo ============================================================
echo   Ngwe Lwe System — Build Client Installer (v1.0.0-beta)
echo   Builds: NgweLweSystem-Setup-v1.0.1.exe
echo ============================================================

:: Activate virtual environment
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate venv.
    echo Run: python -m venv venv ^&^& pip install -r requirements.txt
    pause & popd & exit /b 1
)

pip install pyinstaller --quiet

:: ── Step 1: PyInstaller ──────────────────────────────────────
echo.
echo [1/2] Building NgweLweSystem.exe with PyInstaller...
echo.

if exist dist\NgweLweSystem rmdir /s /q dist\NgweLweSystem
if exist build              rmdir /s /q build

pyinstaller NgweLweClient.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed. See errors above.
    pause & popd & exit /b 1
)

echo [1/2] PyInstaller build complete.

:: ── Step 2: Inno Setup ──────────────────────────────────────
echo.
echo [2/2] Compiling Windows installer with Inno Setup...
echo.

set ISCC=
for %%P in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) do if exist %%P set ISCC=%%P

if "%ISCC%"=="" (
    echo ERROR: Inno Setup 6 not found.
    echo Download from: https://jrsoftware.org/isdl.php
    pause & popd & exit /b 1
)

if not exist installer mkdir installer
%ISCC% setup.iss
if errorlevel 1 (
    echo ERROR: Inno Setup compilation failed. See errors above.
    pause & popd & exit /b 1
)

:: ── Done ────────────────────────────────────────────────────
echo.
echo ============================================================
echo   BUILD COMPLETE
echo   installer\NgweLweSystem-Setup-v1.0.1.exe
echo ============================================================
echo.
echo Distribute that single file to client machines.
echo No Python or dependencies required on the target machine.
echo.
echo Default credentials:
echo   owner    / admin123
echo   employee / employee123
echo   cashier  / cashier123
echo.
pause
popd
