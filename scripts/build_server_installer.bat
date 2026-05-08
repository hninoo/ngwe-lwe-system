@echo off
pushd %~dp0..
echo ============================================================
echo   NgweLwe System — Build Server Installer
echo   Builds: NgweLweServer-Setup-v1.0.1.exe
echo ============================================================

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate venv.
    pause & popd & exit /b 1
)

pip install pyinstaller --quiet

:: Step 1: Build server EXE
echo.
echo [1/2] Building NgweLweServer.exe ...
echo.

if exist dist\NgweLweServer rmdir /s /q dist\NgweLweServer
if exist build              rmdir /s /q build

if not exist assets\logos mkdir assets\logos

pyinstaller NgweLweServer.spec
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause & popd & exit /b 1
)

:: Step 2: Build installer
echo.
echo [2/2] Building installer with Inno Setup...
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
%ISCC% setup_server.iss
if errorlevel 1 (
    echo ERROR: Inno Setup build failed.
    pause & popd & exit /b 1
)

echo.
echo ============================================================
echo   DONE — installer\NgweLweServer-Setup-v1.0.1.exe
echo ============================================================
echo.
pause
popd
