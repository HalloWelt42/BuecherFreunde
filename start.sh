#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== BücherFreunde Entwicklungsumgebung ==="
echo ""

# Python prüfen
if ! command -v python3 &>/dev/null; then
    echo "FEHLER: python3 nicht gefunden"
    exit 1
fi

# Node prüfen
if ! command -v node &>/dev/null; then
    echo "FEHLER: node nicht gefunden"
    exit 1
fi

# .env erstellen falls nicht vorhanden
if [ ! -f .env ]; then
    echo "Erstelle .env aus .env.example..."
    cp .env.example .env
fi

# Backend-Abhängigkeiten
echo "Installiere Backend-Abhängigkeiten..."
pip3 install -q -r backend/requirements.txt

# Frontend-Abhängigkeiten
echo "Installiere Frontend-Abhängigkeiten..."
cd frontend && npm install --silent && cd ..

# Verzeichnisse erstellen
mkdir -p storage external import database

# Backend starten
echo "Starte Backend auf Port 8000..."
python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Frontend starten
echo "Starte Frontend auf Port 5173..."
cd frontend && npm run dev -- --port 5173 &
FRONTEND_PID=$!
cd ..

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo ""
echo "Drücke Ctrl+C zum Beenden."

# Aufräumen bei Beendigung
cleanup() {
    echo ""
    echo "Fahre herunter..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait
}
trap cleanup EXIT INT TERM

# Warten auf Beendigung
wait
