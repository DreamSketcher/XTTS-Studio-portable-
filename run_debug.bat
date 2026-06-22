@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0python\xtts_env\Lib\site-packages
"%~dp0python\runtime\python.exe" gui.py
pause