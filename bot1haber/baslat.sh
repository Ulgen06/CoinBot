#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"
export PYTHONWARNINGS="ignore"

clear 2>/dev/null || true
echo "=========================================="
echo "  ULGEN v31 • KRIPTO ANALIZ & TRADER BOT"
echo "=========================================="

if [ -x "../.venv/bin/python" ]; then
    PY_CMD="../.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PY_CMD="python"
else
    echo "HATA: Python3 bulunamadi! Lutfen brew install python ile kurun."
    exit 1
fi

echo "[1/2] Sistem baslatiliyor (Core + Web + Trader)..."
$PY_CMD run.py &
BOT_PID=$!

cleanup() {
    echo ""
    echo "Sistem kapatiliyor (Core + Trader)..."
    pkill -P "$BOT_PID" 2>/dev/null || true
    kill "$BOT_PID" 2>/dev/null || true
    wait "$BOT_PID" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "[2/2] Web Dashboard aciliyor (http://localhost:9001)..."
sleep 4
if command -v open >/dev/null 2>&1; then
    open "http://localhost:9001"
elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://localhost:9001"
fi

echo "Sistem aktif (PID: $BOT_PID). Durdurmak icin Ctrl+C."
echo "------------------------------------------"
wait $BOT_PID
