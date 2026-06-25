@echo off
title Obnovlenie GitHub - XTTS Studio
cd /d "C:\XTTS Studio"

echo ============================================
echo   Obnovlenie repozitoriya XTTS Studio
echo ============================================
echo.

echo [1/4] Proveryayu izmeneniya s GitHub...
git pull origin main
if errorlevel 1 (
    echo.
    echo OSHIBKA pri pull! Vozmojen konflikt - otkroy proekt i razberis vruchnuyu.
    pause
    exit /b 1
)
echo.

echo [2/4] Dobavlyayu vse izmenennye faily...
git add .
echo.

git diff --cached --quiet
if not errorlevel 1 (
    echo Net izmeneniy dlya kommita. Vsyo uje aktualno.
    echo.
    pause
    exit /b 0
)

echo [3/4] Vvedi soobshenie kommita (chto izmenilos):
set /p commit_msg="Soobshenie: "
if "%commit_msg%"=="" set commit_msg=update

git commit -m "%commit_msg%"
echo.

echo [4/4] Otpravlyayu izmeneniya na GitHub...
git push origin main
if errorlevel 1 (
    echo.
    echo OSHIBKA pri push! Proveri podklyuchenie ili avtorizaciyu.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Gotovo! Repozitoriy obnovlyon.
echo ============================================
echo.
pause
