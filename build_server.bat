@echo off
echo ============================================
echo   NgweLwe System - Build Server EXE
echo ============================================

pip install pyinstaller --quiet

if exist dist\NgweLweServer rmdir /s /q dist\NgweLweServer
if exist build rmdir /s /q build

echo Building... (1-2 minutes)

pyinstaller NgweLweServer.spec

if errorlevel 1 (
  echo.
  echo BUILD FAILED. See errors above.
  pause
  exit /b 1
)

echo.
echo ============================================
echo   BUILD COMPLETE
echo   Output: dist\NgweLweServer\NgweLweServer.exe
echo ============================================
echo.
echo Admin machine မှာ NgweLweServer.exe ကို double-click နှိပ်ပါ။
echo Host/Port configure လုပ်ပြီး Start Server နှိပ်ပါ။
echo.
pause
