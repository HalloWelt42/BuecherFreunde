#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== BücherFreunde Installation ==="
echo ""

# Docker prüfen
if ! command -v docker &>/dev/null; then
    echo "Docker nicht gefunden. Installiere Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    echo "Docker installiert. Bitte neu einloggen und erneut starten."
    exit 0
fi

# Docker Compose prüfen
if ! docker compose version &>/dev/null; then
    echo "FEHLER: Docker Compose nicht verfügbar"
    exit 1
fi

# .env erstellen falls nicht vorhanden
if [ ! -f .env ]; then
    echo "Erstelle .env aus .env.example..."
    cp .env.example .env
    echo "WICHTIG: Bitte .env anpassen (API_TOKEN ändern!)"
fi

# Verzeichnisse erstellen
echo "Erstelle Verzeichnisse..."
mkdir -p storage external import database

# Container bauen und starten
echo "Baue und starte Container..."
cd docker
docker compose up -d --build

echo ""
echo "BücherFreunde läuft auf Port ${EXTERNAL_PORT:-8160}"
echo "Zugriff: http://$(hostname -I | awk '{print $1}'):${EXTERNAL_PORT:-8160}"
echo ""

# Systemd-Service einrichten (optional)
if command -v systemctl &>/dev/null; then
    SERVICE_FILE="/etc/systemd/system/buecherfreunde.service"
    if [ ! -f "$SERVICE_FILE" ]; then
        echo "Richte systemd-Service ein..."
        sudo tee "$SERVICE_FILE" > /dev/null <<UNIT
[Unit]
Description=BücherFreunde Buchverwaltung
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR/docker
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
UNIT
        sudo systemctl daemon-reload
        sudo systemctl enable buecherfreunde
        echo "Systemd-Service eingerichtet und aktiviert."
    fi
fi
