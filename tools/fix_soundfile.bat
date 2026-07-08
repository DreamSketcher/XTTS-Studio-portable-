@echo off
cd /d "%~dp0\.."

echo --- Fixing broken NumPy package completely ---

set "SITE_PACKAGES=%~dp0..\python\xtts_env\Lib\site-packages"

echo 1. Removing ALL broken numpy folders...
if exist "%SITE_PACKAGES%\numpy" rmdir /s /q "%SITE_PACKAGES%\numpy"
if exist "%SITE_PACKAGES%\numpy.libs" rmdir /s /q "%SITE_PACKAGES%\numpy.libs"
if exist "%SITE_PACKAGES%\~umpy" rmdir /s /q "%SITE_PACKAGES%\~umpy"
if exist "%SITE_PACKAGES%\~umpy.libs" rmdir /s /q "%SITE_PACKAGES%\~umpy.libs"
for /d %%G in ("%SITE_PACKAGES%\numpy-*.dist-info") do rmdir /s /q "%%G"

echo 2. Removing ALL soundfile folders...
if exist "%SITE_PACKAGES%\soundfile" rmdir /s /q "%SITE_PACKAGES%\soundfile"
if exist "%SITE_PACKAGES%\_soundfile_data" rmdir /s /q "%SITE_PACKAGES%\_soundfile_data"
if exist "%SITE_PACKAGES%\_soundfile.py" del /f /q "%SITE_PACKAGES%\_soundfile.py"
if exist "%SITE_PACKAGES%\soundfile.py" del /f /q "%SITE_PACKAGES%\soundfile.py"
for /d %%G in ("%SITE_PACKAGES%\soundfile-*.dist-info") do rmdir /s /q "%%G"

echo 3. Reinstalling numpy cleanly...
"python\runtime\python.exe" -m pip install numpy==1.26.4 --no-deps --target "%SITE_PACKAGES%" --force-reinstall --no-cache-dir --upgrade --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org

echo.
echo 4. Reinstalling soundfile cleanly...
"python\runtime\python.exe" -m pip install soundfile --no-deps --target "%SITE_PACKAGES%" --force-reinstall --no-cache-dir --upgrade --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org

echo.
echo Verifying import...
"python\runtime\python.exe" -c "import sys; sys.path.insert(0, r'%SITE_PACKAGES%'); import numpy; print('Numpy version:', numpy.__version__); import soundfile; print('OK: soundfile imported')"

echo.
pause
