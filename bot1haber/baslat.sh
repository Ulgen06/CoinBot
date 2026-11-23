#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "[1/3] Python kontrol ediliyor..."
if command -v python3 >/dev/null 2>&1; then
    PY_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PY_CMD="python"
else
    echo "HATA: Python3 bulunamadi! Lutfen brew install python ile kurun."
    exit 1
fi

echo "[2/3] Sistem Baslatiliyor (Core + Web Server + Trader)..."
$PY_CMD run.py &
BOT_PID=$!

echo "[3/3] Web Dashboard Aciliyor (http://localhost:9001)..."
sleep 5
if command -v open >/dev/null 2>&1; then
    open "http://localhost:9001"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:9001"
fi

echo "Sistem aktif (PID: $BOT_PID). Durdurmak icin Ctrl+C."
wait $BOT_PID
