@echo off
echo ============================================
echo   Ngwe Lwe System - Build Installer
echo ============================================

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Install PyInstaller if missing
pip install pyinstaller --quiet

:: ── Step 1: PyInstaller ──────────────────────
echo.
echo [1/2] Building EXE with PyInstaller...
echo.

if exist dist\NgweLwe-Demo rmdir /s /q dist\NgweLwe-Demo
if exist build rmdir /s /q build

pyinstaller ^
  --name "NgweLwe-Demo" ^
  --onedir ^
  --windowed ^
  --add-data "backend\database.sql;backend" ^
  --hidden-import "uvicorn.logging" ^
  --hidden-import "uvicorn.loops" ^
  --hidden-import "uvicorn.loops.auto" ^
  --hidden-import "uvicorn.protocols" ^
  --hidden-import "uvicorn.protocols.http" ^
  --hidden-import "uvicorn.protocols.http.auto" ^
  --hidden-import "uvicorn.protocols.websockets" ^
  --hidden-import "uvicorn.protocols.websockets.auto" ^
  --hidden-import "uvicorn.lifespan" ^
  --hidden-import "uvicorn.lifespan.on" ^
  --hidden-import "anyio._backends._asyncio" ^
  --hidden-import "anyio._backends._trio" ^
  --hidden-import "bcrypt" ^
  --hidden-import "passlib" ^
  --hidden-import "multipart" ^
  --collect-all "uvicorn" ^
  --collect-all "fastapi" ^
  --collect-all "PyQt6" ^
  run_demo.py

if errorlevel 1 (
  echo.
  echo ERROR: PyInstaller build failed. See errors above.
  pause
  exit /b 1
)

echo.
echo [1/2] PyInstaller build complete.

:: ── Step 2: Inno Setup ──────────────────────
echo.
echo [2/2] Compiling Windows installer with Inno Setup...
echo.

:: Detect Inno Setup installation
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC=C:\Program Files\Inno Setup 6\ISCC.exe
) else if exist "C:\Program Files (x86)\Inno Setup 5\ISCC.exe" (
    set ISCC=C:\Program Files (x86)\Inno Setup 5\ISCC.exe
)

if "%ISCC%"=="" (
  echo ERROR: Inno Setup not found.
  echo.
  echo Please install Inno Setup 6 from:
  echo   https://jrsoftware.org/isdl.php
  echo.
  echo Then re-run this script.
  pause
  exit /b 1
)

if not exist installer mkdir installer

"%ISCC%" setup.iss

if errorlevel 1 (
  echo.
  echo ERROR: Inno Setup compilation failed. See errors above.
  pause
  exit /b 1
)

:: ── Done ────────────────────────────────────
echo.
echo ============================================
echo   BUILD COMPLETE
echo ============================================
echo.
echo Installer: installer\NgweLweSystem-Setup-v1.0.0.exe
echo.
echo Distribute that single file to any Windows PC.
echo No Python or dependencies required on the target machine.
echo.
echo Default login credentials:
echo   Username: owner     Password: admin123
echo   Username: employee1 Password: admin123
echo.
pause
