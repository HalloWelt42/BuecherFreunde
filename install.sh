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

# Interaktives Setup falls .env nicht existiert
if [ ! -f .env ]; then
    echo "Erstelle Konfiguration..."
    echo ""
    echo "Es werden vier Verzeichnisse benötigt:"
    echo ""
    echo "  1. BÜCHER-SPEICHER   Hier legt BücherFreunde alle Bücher ab."
    echo "                       Jedes Buch bekommt einen eigenen Unterordner"
    echo "                       mit Originaldatei, Cover und Metadaten."
    echo "                       -> Braucht viel Platz (externe Festplatte empfohlen)."
    echo ""
    echo "  2. IMPORT-ORDNER     Hier legst du neue Bücher rein, die importiert"
    echo "                       werden sollen. Nach dem Import bleiben die"
    echo "                       Originale hier liegen."
    echo ""
    echo "  3. DATENBANK         SQLite-Datenbank, Suchindex und Einstellungen."
    echo "                       Braucht wenig Platz, sollte auf schnellem"
    echo "                       Speicher liegen (z.B. SD-Karte oder SSD)."
    echo ""
    echo "  4. EXTERNER ORDNER   Optionaler Nur-Lese-Zugriff auf eine bestehende"
    echo "                       Büchersammlung (z.B. NAS-Freigabe). Bücher werden"
    echo "                       von hier erkannt aber nicht verändert."
    echo ""

    # Pfade abfragen
    read -rp "1. Bücher-Speicher [./storage]: " STORAGE
    STORAGE="${STORAGE:-./storage}"

    read -rp "2. Import-Ordner [./import]: " IMPORT
    IMPORT="${IMPORT:-./import}"

    read -rp "3. Datenbank-Ordner [./database]: " DATABASE
    DATABASE="${DATABASE:-./database}"

    read -rp "4. Externer Ordner (leer lassen zum Überspringen) [./external]: " EXTERNAL
    EXTERNAL="${EXTERNAL:-./external}"

    echo ""
    read -rp "Port für den Webzugriff [8160]: " PORT
    PORT="${PORT:-8160}"

    # Token generieren
    TOKEN="bf-$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | xxd -p)"

    # LM Studio
    echo ""
    read -rp "LM Studio aktivieren? (j/n) [n]: " LM_ENABLED
    LM_URL="http://localhost:1234/v1"
    LM_MODEL="qwen2.5"
    if [[ "$LM_ENABLED" =~ ^[jJyY] ]]; then
        LM_ENABLED="true"
        read -rp "LM Studio URL [http://localhost:1234/v1]: " LM_URL_INPUT
        LM_URL="${LM_URL_INPUT:-$LM_URL}"
        read -rp "LM Studio Modell [qwen2.5]: " LM_MODEL_INPUT
        LM_MODEL="${LM_MODEL_INPUT:-$LM_MODEL}"
    else
        LM_ENABLED="false"
    fi

    cat > .env <<ENVFILE
# BuecherFreunde Konfiguration
# Erstellt am $(date +%d.%m.%Y)

# Server
HOST=0.0.0.0
PORT=8000
EXTERNAL_PORT=$PORT

# Authentifizierung (Bearer Token fuer Frontend-Backend)
API_TOKEN=$TOKEN

# Pfade
STORAGE_DIR=$STORAGE
EXTERNAL_DIR=$EXTERNAL
IMPORT_DIR=$IMPORT
DATABASE_DIR=$DATABASE

# Open Library API
OPENLIBRARY_ENABLED=true
OPENLIBRARY_RATE_LIMIT=1

# LM Studio (KI-Kategorisierung)
LM_STUDIO_ENABLED=$LM_ENABLED
LM_STUDIO_URL=$LM_URL
LM_STUDIO_MODEL=$LM_MODEL

# Logging
LOG_LEVEL=info
ENVFILE

    echo ""
    echo "Konfiguration gespeichert in .env"
    echo ""
    echo "  Bücher-Speicher:  $STORAGE"
    echo "  Import-Ordner:    $IMPORT"
    echo "  Datenbank:        $DATABASE"
    echo "  Externer Ordner:  $EXTERNAL"
    echo "  Port:             $PORT"
    echo ""
    echo "  API-Token: $TOKEN"
    echo "  (wird für den Zugriff auf die Weboberfläche benötigt)"
    echo ""
else
    echo ".env existiert bereits - verwende vorhandene Konfiguration"
    echo "(Zum Neu-Konfigurieren: rm .env && ./install.sh)"
    echo ""
fi

# Pfade aus .env laden
source .env 2>/dev/null || true

# Verzeichnisse erstellen (nur wenn lokal)
for DIR in "${STORAGE_DIR:-./storage}" "${IMPORT_DIR:-./import}" "${DATABASE_DIR:-./database}"; do
    if [[ "$DIR" == ./* ]] || [[ "$DIR" == /* && -d "$(dirname "$DIR")" ]]; then
        mkdir -p "$DIR"
        echo "Verzeichnis erstellt: $DIR"
    fi
done

# External nur wenn erreichbar
EXT="${EXTERNAL_DIR:-./external}"
if [[ "$EXT" == ./* ]]; then
    mkdir -p "$EXT"
elif [[ -d "$(dirname "$EXT")" ]]; then
    mkdir -p "$EXT"
else
    echo "Hinweis: $EXT nicht erreichbar - wird beim Start übersprungen"
fi

# Container bauen und starten
echo ""
echo "Baue und starte Container..."
cd docker
docker compose --env-file ../.env up -d --build

echo ""
echo "=== BücherFreunde läuft ==="
echo "Zugriff: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):${EXTERNAL_PORT:-8160}"
echo ""
echo "Befehle:"
echo "  Status:    cd $PROJECT_DIR/docker && docker compose --env-file ../.env ps"
echo "  Logs:      cd $PROJECT_DIR/docker && docker compose --env-file ../.env logs -f"
echo "  Stoppen:   cd $PROJECT_DIR/docker && docker compose --env-file ../.env down"
echo "  Neustarten: cd $PROJECT_DIR/docker && docker compose --env-file ../.env restart"
echo ""

# Systemd-Service einrichten (optional)
if command -v systemctl &>/dev/null; then
    SERVICE_FILE="/etc/systemd/system/buecherfreunde.service"
    if [ ! -f "$SERVICE_FILE" ]; then
        read -rp "Systemd-Service einrichten (automatischer Start)? (j/n) [j]: " SYSTEMD
        if [[ ! "$SYSTEMD" =~ ^[nN] ]]; then
            sudo tee "$SERVICE_FILE" > /dev/null <<UNIT
[Unit]
Description=BücherFreunde Buchverwaltung
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR/docker
ExecStart=/usr/bin/docker compose --env-file $PROJECT_DIR/.env up -d
ExecStop=/usr/bin/docker compose --env-file $PROJECT_DIR/.env down

[Install]
WantedBy=multi-user.target
UNIT
            sudo systemctl daemon-reload
            sudo systemctl enable buecherfreunde
            echo "Systemd-Service eingerichtet und aktiviert."
        fi
    fi
fi
