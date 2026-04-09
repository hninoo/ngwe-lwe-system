@echo off
echo ============================================
echo   Ngwe Lwe System - Build Demo EXE
echo ============================================

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Install PyInstaller if missing
pip install pyinstaller --quiet

:: Clean previous build
if exist dist\NgweLwe-Demo rmdir /s /q dist\NgweLwe-Demo
if exist build rmdir /s /q build

echo Building... (this takes 1-2 minutes)

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
  echo BUILD FAILED. See errors above.
  pause
  exit /b 1
)

echo.
echo ============================================
echo   BUILD COMPLETE
echo   Output: dist\NgweLwe-Demo\NgweLwe-Demo.exe
echo ============================================
echo.
echo To run demo: open dist\NgweLwe-Demo\ and double-click NgweLwe-Demo.exe
echo The database (ngwe_lwe.db) will be created automatically on first run.
echo.
echo Default login:
echo   Username: owner     Password: admin123
echo   Username: employee1 Password: admin123
echo.
pause
