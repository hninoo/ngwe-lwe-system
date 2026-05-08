@echo off
pushd %~dp0..

echo ============================================================
echo   Ngwe Lwe System -- Build Client Installer (v1.0.0-beta)
echo   Builds: NgweLwe-v1.0.0-beta-Setup.exe
echo ============================================================

call venv\Scripts\activate.bat
if errorlevel 1 goto :venv_error

pip install pyinstaller --quiet

set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if not defined ISCC goto :iscc_error

echo.
echo [1/2] Building NgweLweSystem.exe with PyInstaller...
echo.
if exist "dist\NgweLweSystem" rmdir /s /q "dist\NgweLweSystem"
if exist "build"              rmdir /s /q "build"

pyinstaller NgweLweClient.spec
if errorlevel 1 goto :pyinstaller_error
echo [1/2] Done.

echo.
echo [2/2] Compiling Windows installer with Inno Setup...
echo.
if not exist "installer" mkdir "installer"
"%ISCC%" setup.iss
if errorlevel 1 goto :inno_error

echo.
echo ============================================================
echo   BUILD COMPLETE
echo   installer\NgweLwe-v1.0.0-beta-Setup.exe
echo ============================================================
echo.
echo Default credentials:
echo   owner    / admin123
echo   employee / employee123
echo   cashier  / cashier123
echo.
pause
popd
exit /b 0

:venv_error
echo ERROR: Could not activate venv.
echo Run: python -m venv venv ^&^& pip install -r requirements.txt
pause & popd & exit /b 1

:iscc_error
echo ERROR: Inno Setup 6 not found. Download from: https://jrsoftware.org/isdl.php
pause & popd & exit /b 1

:pyinstaller_error
echo ERROR: PyInstaller build failed. See output above.
pause & popd & exit /b 1

:inno_error
echo ERROR: Inno Setup compilation failed. See output above.
pause & popd & exit /b 1
