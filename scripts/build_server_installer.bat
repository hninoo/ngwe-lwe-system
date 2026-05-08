@echo off
pushd %~dp0..

echo ============================================================
echo   NgweLwe System -- Build Server Installer (v1.0.0-beta)
echo   Builds: NgweLweServer-v1.0.0-beta-Setup.exe
echo ============================================================

call venv\Scripts\activate.bat
if errorlevel 1 goto :venv_error

pip install pyinstaller --quiet

set "ISCC="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if not defined ISCC goto :iscc_error

echo.
echo [1/2] Building NgweLweServer.exe ...
echo.
if exist "dist\NgweLweServer" rmdir /s /q "dist\NgweLweServer"
if exist "build"              rmdir /s /q "build"
if not exist "assets\logos"   mkdir "assets\logos"

pyinstaller NgweLweServer.spec
if errorlevel 1 goto :pyinstaller_error
echo [1/2] Done.

echo.
echo [2/2] Building installer with Inno Setup...
echo.
if not exist "installer" mkdir "installer"
"%ISCC%" setup_server.iss
if errorlevel 1 goto :inno_error

echo.
echo ============================================================
echo   DONE -- installer\NgweLweServer-v1.0.0-beta-Setup.exe
echo ============================================================
echo.
pause
popd
exit /b 0

:venv_error
echo ERROR: Could not activate venv.
pause & popd & exit /b 1

:iscc_error
echo ERROR: Inno Setup 6 not found. Download from: https://jrsoftware.org/isdl.php
pause & popd & exit /b 1

:pyinstaller_error
echo ERROR: PyInstaller build failed. See output above.
pause & popd & exit /b 1

:inno_error
echo ERROR: Inno Setup build failed. See output above.
pause & popd & exit /b 1
