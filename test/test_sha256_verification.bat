@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo Project root resolved to: %cd%

set PYTHON_EXE=%cd%\python\runtime\python.exe
set SCRIPT_PATH=%cd%\test\test_sha256_verification.py
set PYTHONPATH=%cd%\python\xtts_env\Lib\site-packages

echo Looking for python.exe at: %PYTHON_EXE%
echo Looking for script at:     %SCRIPT_PATH%
echo.

if not exist "%PYTHON_EXE%" (
    echo [ERROR] python.exe NOT FOUND at the path above.
    echo Check the real location of your portable Python and fix PYTHON_EXE in this .bat.
    echo.
    pause
    exit /b 1
)

if not exist "%SCRIPT_PATH%" (
    echo [ERROR] test_sha256_verification.py NOT FOUND at the path above.
    echo Make sure it's saved inside the test\ folder.
    echo.
    pause
    exit /b 1
)

echo Running SHA256 verification self-test...
echo.
"%PYTHON_EXE%" "%SCRIPT_PATH%"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAILED] SHA256 verification logic is broken - see output above.
) else (
    echo.
    echo [OK] SHA256 verification logic works as expected.
)

echo.
pause