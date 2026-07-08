@echo off
cd /d "%~dp0\.."

echo --- 1. KILLING ALL PYTHON PROCESSES ---
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul
timeout /t 2 /nobreak >nul

set "SITE_PACKAGES=%~dp0..\python\xtts_env\Lib\site-packages"

echo --- 2. CLEANING UP OLD CFFI ---
if exist "%SITE_PACKAGES%\cffi" rmdir /s /q "%SITE_PACKAGES%\cffi"
if exist "%SITE_PACKAGES%\~ffi" rmdir /s /q "%SITE_PACKAGES%\~ffi"
if exist "%SITE_PACKAGES%\_cffi_backend.cp311-win_amd64.pyd" del /f /q "%SITE_PACKAGES%\_cffi_backend.cp311-win_amd64.pyd"
for /d %%G in ("%SITE_PACKAGES%\cffi-*.dist-info") do rmdir /s /q "%%G"

echo --- 3. REINSTALLING CFFI VIA PIP ---
"python\runtime\python.exe" -m pip install cffi==2.1.0 --no-deps --target "%SITE_PACKAGES%" --force-reinstall --no-cache-dir --upgrade --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org

echo.
echo --- 4. VERIFYING ---
"python\runtime\python.exe" -c "import sys; sys.path.insert(0, r'%SITE_PACKAGES%'); import cffi; print('CFFI:', cffi.__version__); import _cffi_backend; print('Backend:', _cffi_backend.__version__); print('CFFI: OK')"

echo.
pause
