@echo off
title ÜLGEN v30.0 - BAŞLATICI
cd /d "%~dp0"

echo [1/3] Eski işlemler temizleniyor...
taskkill /f /im python.exe /t >nul 2>&1
taskkill /f /im cmd.exe /fi "WINDOWTITLE eq ÜLGEN CORE*" /t >nul 2>&1

echo [2/3] Sistem Başlatılıyor (Core + Server + Trader)...
rem Yeni pencerede Python uygulamasını başlatıyoruz
start "ÜLGEN CORE" cmd /k ""C:\Users\karas\AppData\Local\Programs\Python\Python313\python.exe" run.py"

echo [3/3] Tarayıcı Açılıyor...
rem Server'ın ayağa kalkması için 5 saniye bekle
timeout /t 5 /nobreak >nul

rem Varsayılan tarayıcıda dashboard'u aç
start http://localhost:9001

echo.
echo ==========================================
echo   BAŞARILI! KEYİFLİ KAZANÇLAR İMPARATOR! 🚀
echo ==========================================
timeout /t 3 >nul
exit
