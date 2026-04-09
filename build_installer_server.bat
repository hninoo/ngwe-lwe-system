@echo off
echo ============================================================
echo   NgweLwe System — Build Server Installer
echo ============================================================

:: Step 1: Build server exe with PyInstaller
echo.
echo [1/2] Building NgweLweServer.exe ...
echo.

if exist dist\NgweLweServer rmdir /s /q dist\NgweLweServer
if exist build rmdir /s /q build

pip install pyinstaller --quiet

pyinstaller NgweLweServer.spec

if errorlevel 1 (
  echo.
  echo ERROR: PyInstaller build failed.
  pause
  exit /b 1
)

:: Step 2: Build installer with Inno Setup
echo.
echo [2/2] Building installer with Inno Setup ...
echo.

:: Try common Inno Setup locations
set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"

if %ISCC%=="" (
  echo ERROR: Inno Setup 6 not found.
  echo Download from: https://jrsoftware.org/isdl.php
  pause
  exit /b 1
)

%ISCC% setup_server.iss

if errorlevel 1 (
  echo.
  echo ERROR: Inno Setup build failed.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo   DONE
echo   installer\NgweLweServer-Setup-v1.0.0.exe
echo ============================================================
echo.
echo Customer ကို ပေးရမည့် file ၂ ခု:
echo   1. installer\NgweLweSystem-Setup-v1.0.0.exe   (Client)
echo   2. installer\NgweLweServer-Setup-v1.0.0.exe   (Server)
echo.
pause
