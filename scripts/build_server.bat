@echo off
pushd %~dp0..
echo ============================================================
echo   NgweLwe System — Build Server EXE
echo   Builds: NgweLweServer.exe  (standalone server manager)
echo ============================================================

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate venv.
    pause & popd & exit /b 1
)

pip install pyinstaller --quiet

if exist dist\NgweLweServer rmdir /s /q dist\NgweLweServer
if exist build              rmdir /s /q build

if not exist assets\logos mkdir assets\logos

echo Building... (1-2 minutes)
pyinstaller NgweLweServer.spec
if errorlevel 1 (
    echo BUILD FAILED. See errors above.
    pause & popd & exit /b 1
)

echo.
echo ============================================================
echo   BUILD COMPLETE
echo   dist\NgweLweServer\NgweLweServer.exe
echo ============================================================
echo.
echo Admin machine မှာ NgweLweServer.exe ကို double-click နှိပ်ပါ။
echo Host/Port configure လုပ်ပြီး Start Server နှိပ်ပါ။
echo.
pause
popd
