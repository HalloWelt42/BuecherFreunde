#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== BücherFreunde Update ==="
echo ""

# Aktuelle Version
ALTE_VERSION=$(cat VERSION 2>/dev/null || echo "unbekannt")
echo "Aktuelle Version: $ALTE_VERSION"

# Ungespeicherte Änderungen prüfen
if ! git diff --quiet 2>/dev/null; then
    echo "WARNUNG: Lokale Änderungen gefunden"
    git status --short
    echo ""
    read -rp "Lokale Änderungen verwerfen und updaten? (j/n) [n]: " CONFIRM
    if [[ ! "$CONFIRM" =~ ^[jJyY] ]]; then
        echo "Abgebrochen."
        exit 0
    fi
    git stash
fi

# Updates holen
echo "Hole Updates von GitHub..."
git pull --ff-only origin main
if [ $? -ne 0 ]; then
    echo "FEHLER: git pull fehlgeschlagen. Möglicherweise Konflikte."
    echo "Manuelle Lösung: git fetch origin && git reset --hard origin/main"
    exit 1
fi

NEUE_VERSION=$(cat VERSION 2>/dev/null || echo "unbekannt")
echo "Neue Version: $NEUE_VERSION"
echo ""

if [ "$ALTE_VERSION" = "$NEUE_VERSION" ]; then
    echo "Bereits auf dem neuesten Stand."
    read -rp "Container trotzdem neu bauen? (j/n) [n]: " REBUILD
    if [[ ! "$REBUILD" =~ ^[jJyY] ]]; then
        exit 0
    fi
fi

# Backup vor Update
if command -v sqlite3 &>/dev/null; then
    source .env 2>/dev/null || true
    DB_PATH="${DATABASE_DIR:-./database}/buecherfreunde.db"
    if [ -f "$DB_PATH" ]; then
        BACKUP_DIR="${DATABASE_DIR:-./database}/backups"
        mkdir -p "$BACKUP_DIR"
        BACKUP_FILE="$BACKUP_DIR/pre-update-${ALTE_VERSION}-$(date +%Y%m%d_%H%M%S).db"
        echo "Erstelle Datenbank-Backup: $BACKUP_FILE"
        sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"
    fi
fi

# Container neu bauen
echo ""
echo "Baue und starte Container neu..."
cd docker
docker compose --env-file ../.env up -d --build --force-recreate

echo ""
echo "=== Update abgeschlossen ==="
echo "Version: $ALTE_VERSION -> $NEUE_VERSION"
echo ""

# Healthcheck abwarten
echo "Warte auf Backend..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
        echo "Backend läuft."
        break
    fi
    sleep 1
done

echo ""
echo "Zugriff: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):${EXTERNAL_PORT:-8160}"
