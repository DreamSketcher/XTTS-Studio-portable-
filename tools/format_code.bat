@echo off
setlocal enabledelayedexpansion
title XTTS Studio AI - Code Formatter

REM ============================================================
REM  format_code.bat  --  auto-format project code
REM  Location: XTTS Studio AI\tools\format_code.bat
REM
REM  Formats ONLY the project source code.
REM  It NEVER touches the runtime environment (python\), libraries,
REM  models, outputs, etc.
REM
REM  Exclusions are loaded from:
REM    1. Configurable inline defaults (python, models, outputs, etc.)
REM    2. Custom exclusions file: tools\format_exclude.txt (if present)
REM
REM  Usage:
REM    format_code.bat          -^> format the code
REM    format_code.bat check    -^> only check, change nothing
REM ============================================================

REM --- Project root = parent folder of this .bat (tools\..) ---
cd /d "%~dp0.."

echo ==================================================
echo   XTTS STUDIO AI - CODE FORMATTER
echo ==================================================
echo   Root: "%CD%"
echo.

REM --- Find Python: portable envs first, then py / python ---
set "PY="
if exist "%CD%\python\runtime\python.exe" (
    set "PY=%CD%\python\runtime\python.exe"
) else if exist "%CD%\python\xtts_env\python.exe" (
    set "PY=%CD%\python\xtts_env\python.exe"
) else if exist "%CD%\python\xtts_env\Scripts\python.exe" (
    set "PY=%CD%\python\xtts_env\Scripts\python.exe"
) else if exist "%CD%\.venv\Scripts\python.exe" (
    set "PY=%CD%\.venv\Scripts\python.exe"
) else if exist "%CD%\venv\Scripts\python.exe" (
    set "PY=%CD%\venv\Scripts\python.exe"
)

if not defined PY (
    where py >nul 2>&1
    if not errorlevel 1 set "PY=py"
)
if not defined PY (
    where python >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

if not defined PY (
    echo [ERROR] Python not found.
    goto :end
)

echo   Python: "%PY%"
"%PY%" --version
echo.

REM --- Make sure black and ruff are installed ---
"%PY%" -m black --version >nul 2>&1
if errorlevel 1 (
    echo [SETUP] Installing black and ruff...
    "%PY%" -m pip install black==24.10.0 ruff==0.6.9
    echo.
)

REM --- Build exclusion flags for Black and Ruff ---
set "BLACK_EXCLUDE="
set "RUFF_EXCLUDE="

for /f "usebackq delims=" %%A in (`"%PY%" -c "import re; from pathlib import Path; f = Path('tools/format_exclude.txt'); items = ['python', 'library', 'models', 'outputs', 'logs', 'reference', 'word_rules_backups', '.venv', 'venv', 'build', 'dist']; [items.append(l.strip().strip('/').strip('\\')) for l in (f.read_text(encoding='utf-8').splitlines() if f.is_file() else []) if l.strip() and not l.strip().startswith('#') and l.strip().strip('/').strip('\\') not in items]; pat = '/(' + '|'.join(re.escape(x) for x in items) + ')/'; csv = ','.join(items); print(pat + '||' + csv)"`) do (
    set "EX_OUT=%%A"
)

for /f "tokens=1,2 delims=||" %%X in ("!EX_OUT!") do (
    set "BLACK_PAT=%%X"
    set "RUFF_CSV=%%Y"
)

if defined BLACK_PAT set "BLACK_EXCLUDE=--force-exclude "!BLACK_PAT!""
if defined RUFF_CSV set "RUFF_EXCLUDE=--extend-exclude "!RUFF_CSV!""

REM --- Targets: only project code, optional ones added if present ---
set "TARGETS=engine"
if exist "%CD%\tools" set "TARGETS=!TARGETS! tools"
if exist "%CD%\test" set "TARGETS=!TARGETS! test"
if exist "%CD%\gui.py" set "TARGETS=!TARGETS! gui.py"
if exist "%CD%\i18n.py" set "TARGETS=!TARGETS! i18n.py"
if exist "%CD%\generate_version_manifest.py" set "TARGETS=!TARGETS! generate_version_manifest.py"

echo   Targets : !TARGETS!
if exist "%CD%\tools\format_exclude.txt" (
    echo   Excludes: tools\format_exclude.txt loaded
) else (
    echo   Excludes: default runtime/models/outputs filters
)
echo.

if /i "%~1"=="check" goto :checkmode

REM --- Format mode ---
echo ==================================================
echo   BLACK - formatting
echo ==================================================
"%PY%" -m black !BLACK_EXCLUDE! !TARGETS!
echo.
echo ==================================================
echo   RUFF - lint auto-fix
echo ==================================================
"%PY%" -m ruff check !RUFF_EXCLUDE! !TARGETS! --fix
echo.
echo ==================================================
echo   BLACK - final pass after Ruff fixes
echo ==================================================
"%PY%" -m black !BLACK_EXCLUDE! !TARGETS!
echo.
echo ==================================================
echo   VERIFY
echo ==================================================
"%PY%" -m black --check !BLACK_EXCLUDE! !TARGETS!
"%PY%" -m ruff check !RUFF_EXCLUDE! !TARGETS!
echo.
echo [DONE] Formatting checks passed.
echo [NEXT] If source files changed, run Git Manager [1] to regenerate SHA256 and Ed25519 before push.
goto :end

:checkmode
echo ==================================================
echo   CHECK MODE - nothing will be changed
echo ==================================================
"%PY%" -m black --check !BLACK_EXCLUDE! !TARGETS!
echo.
"%PY%" -m ruff check !RUFF_EXCLUDE! !TARGETS!
echo.
echo [CHECK DONE] See results above.

:end
echo.
pause
endlocal
