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

# Updates holen, für den Zweig, auf dem der Klon steht
ZWEIG="$(git branch --show-current)"
echo "Hole Updates von GitHub ($ZWEIG)..."
git pull --ff-only origin "$ZWEIG"
if [ $? -ne 0 ]; then
    echo "FEHLER: git pull fehlgeschlagen. Möglicherweise Konflikte."
    echo "Manuelle Lösung: git fetch origin && git reset --hard origin/$ZWEIG"
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

# Container bauen; die laufenden arbeiten dabei weiter
echo ""
echo "Baue Container..."
cd docker
docker compose --env-file ../.env build

# Sicherung vor dem Update nach der Sicherungsregel der App (backend/app/services/sicherung.py, Werte in den
# Einstellungen): neu nur, wenn die jüngste älter ist als SICHERUNG_VOR_AUSROLLEN_AB_STUNDEN und sich die Datenbank
# seitdem geändert hat. Sie läuft mit dem neuen Abbild auf derselben Datenbank, bevor die neue Fassung startet;
# scheitert sie, bricht das Update ab und die laufende Fassung bleibt.
echo "Sicherung vor dem Update..."
docker compose --env-file ../.env run --rm --no-deps -T backend python -m backend.app.services.sicherung aktualisieren

echo "Starte Container neu..."
docker compose --env-file ../.env up -d --force-recreate

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
