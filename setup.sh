#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=== BücherFreunde Setup ==="
echo ""

if [ ! -f .env ]; then
    echo "Keine .env gefunden - starte install.sh für Ersteinrichtung."
    exec ./install.sh
fi

# Aktuelle Werte laden
source .env 2>/dev/null || true

echo "Aktuelle Konfiguration:"
echo "  Bücher-Verzeichnis:  ${STORAGE_DIR:-./storage}"
echo "  Import-Verzeichnis:  ${IMPORT_DIR:-./import}"
echo "  Datenbank:           ${DATABASE_DIR:-./database}"
echo "  Externer Scan:       ${EXTERNAL_DIR:-./external}"
echo "  Port:                ${EXTERNAL_PORT:-8160}"
echo "  LM Studio:           ${LM_STUDIO_ENABLED:-false} (${LM_STUDIO_URL:-nicht gesetzt})"
echo ""

echo "Was möchtest du ändern?"
echo ""
echo "  1) Bücher-Verzeichnis (Storage)"
echo "  2) Import-Verzeichnis"
echo "  3) Externer Scan-Ordner"
echo "  4) Datenbank-Verzeichnis"
echo "  5) Port"
echo "  6) API-Token neu generieren"
echo "  7) LM Studio Einstellungen"
echo "  8) .env direkt bearbeiten"
echo "  9) Alle Pfade anzeigen (Docker-Volumes)"
echo "  0) Beenden"
echo ""

read -rp "Auswahl [0]: " CHOICE
CHOICE="${CHOICE:-0}"

case "$CHOICE" in
    1)
        read -rp "Neuer Bücher-Pfad [${STORAGE_DIR:-./storage}]: " NEW
        if [ -n "$NEW" ]; then
            sed -i "s|^STORAGE_DIR=.*|STORAGE_DIR=$NEW|" .env
            echo "Geändert. Neustart nötig: cd docker && docker compose restart backend"
        fi
        ;;
    2)
        read -rp "Neuer Import-Pfad [${IMPORT_DIR:-./import}]: " NEW
        if [ -n "$NEW" ]; then
            sed -i "s|^IMPORT_DIR=.*|IMPORT_DIR=$NEW|" .env
            echo "Geändert. Neustart nötig: cd docker && docker compose restart backend"
        fi
        ;;
    3)
        read -rp "Neuer externer Scan-Pfad [${EXTERNAL_DIR:-./external}]: " NEW
        if [ -n "$NEW" ]; then
            sed -i "s|^EXTERNAL_DIR=.*|EXTERNAL_DIR=$NEW|" .env
            echo "Geändert. Neustart nötig: cd docker && docker compose restart backend"
        fi
        ;;
    4)
        echo "WARNUNG: Datenbank-Pfad ändern kann Datenverlust verursachen!"
        echo "Aktuelle DB: ${DATABASE_DIR:-./database}/buecherfreunde.db"
        read -rp "Trotzdem ändern? (j/n) [n]: " CONFIRM
        if [[ "$CONFIRM" =~ ^[jJyY] ]]; then
            read -rp "Neuer DB-Pfad [${DATABASE_DIR:-./database}]: " NEW
            if [ -n "$NEW" ]; then
                sed -i "s|^DATABASE_DIR=.*|DATABASE_DIR=$NEW|" .env
                echo "Geändert. Vergiss nicht die DB-Datei zu verschieben!"
            fi
        fi
        ;;
    5)
        read -rp "Neuer Port [${EXTERNAL_PORT:-8160}]: " NEW
        if [ -n "$NEW" ]; then
            sed -i "s|^EXTERNAL_PORT=.*|EXTERNAL_PORT=$NEW|" .env
            echo "Geändert. Neustart nötig: cd docker && docker compose up -d"
        fi
        ;;
    6)
        TOKEN="bf-$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | xxd -p)"
        sed -i "s|^API_TOKEN=.*|API_TOKEN=$TOKEN|" .env
        echo "Neuer Token: $TOKEN"
        echo "Neustart nötig: cd docker && docker compose restart"
        ;;
    7)
        read -rp "LM Studio aktivieren? (j/n) [${LM_STUDIO_ENABLED:-n}]: " ENABLED
        if [[ "$ENABLED" =~ ^[jJyY] ]]; then
            sed -i "s|^LM_STUDIO_ENABLED=.*|LM_STUDIO_ENABLED=true|" .env
            read -rp "LM Studio URL [${LM_STUDIO_URL:-http://localhost:1234/v1}]: " URL
            if [ -n "$URL" ]; then
                sed -i "s|^LM_STUDIO_URL=.*|LM_STUDIO_URL=$URL|" .env
            fi
            read -rp "Modell [${LM_STUDIO_MODEL:-qwen2.5}]: " MODEL
            if [ -n "$MODEL" ]; then
                sed -i "s|^LM_STUDIO_MODEL=.*|LM_STUDIO_MODEL=$MODEL|" .env
            fi
        else
            sed -i "s|^LM_STUDIO_ENABLED=.*|LM_STUDIO_ENABLED=false|" .env
        fi
        echo "Geändert. Neustart nötig: cd docker && docker compose restart backend"
        ;;
    8)
        ${EDITOR:-nano} .env
        echo "Nach Änderungen: cd docker && docker compose restart"
        ;;
    9)
        echo ""
        echo "Docker-Volume-Zuordnung:"
        echo "  Host: ${STORAGE_DIR:-./storage}  ->  Container: /app/storage"
        echo "  Host: ${IMPORT_DIR:-./import}    ->  Container: /app/import"
        echo "  Host: ${DATABASE_DIR:-./database} ->  Container: /app/database"
        echo "  Host: ${EXTERNAL_DIR:-./external} ->  Container: /app/external (nur lesen)"
        echo ""
        echo "Speicherplatz:"
        for DIR in "${STORAGE_DIR:-./storage}" "${DATABASE_DIR:-./database}"; do
            if [ -d "$DIR" ]; then
                SIZE=$(du -sh "$DIR" 2>/dev/null | cut -f1)
                echo "  $DIR: $SIZE"
            else
                echo "  $DIR: (nicht vorhanden)"
            fi
        done
        ;;
    0)
        echo "Keine Änderungen."
        ;;
    *)
        echo "Ungültige Auswahl."
        ;;
esac
