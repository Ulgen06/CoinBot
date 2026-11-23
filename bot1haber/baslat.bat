@echo off
chcp 65001 >nul
title ÜLGEN v31.0 - BAŞLATICI
cd /d "%~dp0"

echo [1/3] Python kontrol ediliyor...
where py >nul 2>&1
if %errorlevel%==0 (
    set "PY_CMD=py"
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set "PY_CMD=python"
    ) else (
        echo HATA: Python bulunamadi! Lutfen python.org adresinden kurun.
        pause
        exit /b 1
    )
)

echo [2/3] Sistem Baslatiliyor (Core + Web Server + Trader)...
start "ÜLGEN CORE" cmd /k "%PY_CMD% run.py"

echo [3/3] Web Dashboard Aciliyor...
timeout /t 5 /nobreak >nul
start http://localhost:9001

echo.
echo ==========================================
echo   BASARILI! KEYIFLI KAZANCLAR!
echo ==========================================
timeout /t 3 >nul
exit
