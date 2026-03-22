# BuecherFreunde

Selbst gehostete Buchverwaltung fuer 50.000+ Buecher. Laeuft per Docker auf Raspberry Pi 5 und Mac.

## Features

- **Bibliothek**: Grid/Listenansicht mit Filtern, Kategorien, Tags, Sammlungen
- **Formate**: PDF, EPUB, MOBI, TXT, Markdown
- **Reader**: PDF mit TextLayer (Textauswahl, Markierungen), EPUB mit foliate-js, Markdown
- **Suche**: FTS5 Volltextsuche mit Snippets und Hervorhebung
- **Markierungen**: Farbige Textmarkierungen mit Notizen (PDF + EPUB)
- **Notizen**: Buchnotizen mit Seitenreferenz, Schnellnotiz-Pad
- **Metadaten**: Open Library, Google Books, Wikipedia/Wikidata
- **KI**: Kategorisierung ueber LM Studio (optional, lokal)
- **Backup**: DB + Metadaten als ZIP, Buchmaterial per rsync
- **Dark Mode**: Vier Papier-Modi im Reader (Normal, Sepia, Dunkel, Kontrast)

## Voraussetzungen

- Docker und Docker Compose
- Fuer Raspberry Pi: 64-bit OS (Raspberry Pi OS Lite empfohlen)
- Fuer Mac: Docker Desktop

## Installation

### Raspberry Pi

```bash
git clone https://github.com/HalloWelt42/BuecherFreunde.git
cd BuecherFreunde
./install.sh
```

Das Skript fragt interaktiv nach:
- Pfad fuer Buecher-Verzeichnis (Storage)
- Pfad fuer Import-Verzeichnis
- Pfad fuer Datenbank
- Pfad fuer externen Scan-Ordner (optional)
- Port (Standard: 8160)
- LM Studio Einstellungen (optional)

Danach werden die Docker-Container gebaut und gestartet.

### Beispiel: Pi mit externer Festplatte

```bash
# .env nach install.sh anpassen:
STORAGE_DIR=/mnt/festplatte/ebooks
IMPORT_DIR=/mnt/festplatte/ebooks/import
DATABASE_DIR=/mnt/festplatte/ebooks/.db
EXTERNAL_DIR=/mnt/festplatte/scan-ordner
```

### Mac (Entwicklung)

```bash
git clone https://github.com/HalloWelt42/BuecherFreunde.git
cd BuecherFreunde
cp .env.example .env
# .env anpassen (Token, Pfade, LM Studio)
./start.sh
```

`start.sh` startet Backend und Frontend im Entwicklungsmodus (ohne Docker).

## Konfiguration

Alle Einstellungen stehen in der `.env` Datei im Projektverzeichnis:

```
# Server
EXTERNAL_PORT=8160              # Port fuer den Zugriff

# Authentifizierung
API_TOKEN=dein-token-hier       # Bearer Token (Frontend <-> Backend)

# Pfade
STORAGE_DIR=/pfad/zu/buechern   # Arbeitsverzeichnis mit Hash-Ordnern
EXTERNAL_DIR=/pfad/zum/scannen  # Scan-Ordner (read-only, kann leer sein)
IMPORT_DIR=/pfad/zum/import     # Upload-Ziel
DATABASE_DIR=/pfad/zur/db       # SQLite + Backups

# Open Library
OPENLIBRARY_ENABLED=true        # Metadaten-Anreicherung
OPENLIBRARY_RATE_LIMIT=1        # Anfragen pro Sekunde

# LM Studio (optional)
LM_STUDIO_ENABLED=false         # KI-Kategorisierung
LM_STUDIO_URL=http://ip:1234/v1
LM_STUDIO_MODEL=qwen2.5
```

### Konfiguration aendern

```bash
./setup.sh                      # Interaktives Menue
# oder direkt:
nano .env
cd docker && docker compose restart
```

## Updates

### Update-Hinweis im Frontend

Die Sidebar zeigt automatisch an, wenn eine neue Version auf GitHub verfuegbar ist.

### Update ausfuehren

```bash
cd ~/BuecherFreunde
./update.sh
```

Das Skript:
1. Erstellt ein Datenbank-Backup
2. Holt den neuen Code von GitHub (`git pull`)
3. Baut die Docker-Container neu
4. DB-Schema-Migrationen laufen automatisch beim Start

### Was passiert mit den Daten?

| Daten | Beim Update | Sicher? |
|-------|-------------|---------|
| Buecher (Storage) | Unveraendert (Volume) | Ja |
| Datenbank | Auto-Migration + Backup vorher | Ja |
| Notizen, Markierungen | In der DB, migriert mit | Ja |
| .env Konfiguration | Unveraendert | Ja |

### Rollback

```bash
# DB-Backup wiederherstellen
cp database/backups/pre-update-*.db database/buecherfreunde.db
cd docker && docker compose restart backend
```

## Datensicherheit

### Schutz vor Datenverlust

Beim ersten Start legt das Backend eine Marker-Datei `.buecherfreunde` im Storage- und Datenbank-Verzeichnis an. Bei jedem weiteren Start wird geprueft:

- **Festplatte nicht gemountet**: Backend startet nicht (statt leere DB auf SD-Karte anzulegen)
- **Marker-Datei fehlt**: Backend startet nicht (falscher Mount-Punkt?)
- **Externer Scan-Ordner fehlt**: Wird uebersprungen, Backend startet normal

Docker startet den Container automatisch neu (`restart: unless-stopped`), sobald die Platte wieder verfuegbar ist.

### Backup

**Anwendungsdaten** (DB, Metadaten, Notizen):
- Ueber die Einstellungen-Seite oder API: `POST /api/backup/create`
- Automatisches Backup vor jedem Update

**Buchmaterial** (die Dateien selbst):
```bash
rsync -av /mnt/festplatte/ebooks/ /backup/ebooks/
```

## Architektur

```
BuecherFreunde/
 ├── frontend/          # Svelte 5 + Vite
 ├── backend/           # Python FastAPI + SQLite
 ├── docker/            # docker-compose.yml + nginx.conf
 ├── .env               # Konfiguration (nicht im Git)
 ├── install.sh         # Erstinstallation
 ├── setup.sh           # Konfiguration aendern
 ├── update.sh          # Updates einspielen
 └── start.sh           # Entwicklungsmodus (ohne Docker)
```

### Tech-Stack

| Bereich | Technologie |
|---------|-------------|
| Frontend | Svelte 5 + Vite |
| PDF-Viewer | pdfjs-dist (Canvas + TextLayer) |
| EPUB/MOBI | foliate-js |
| Backend | Python FastAPI + Uvicorn |
| Datenbank | SQLite + FTS5 |
| Metadaten | Open Library, Google Books |
| KI | LM Studio (lokal, optional) |
| Container | Docker Compose (python:3.12-slim, nginx:alpine) |

### API

Alle Endpunkte unter `/api/` mit Bearer-Token-Authentifizierung:

- `GET /api/health` - Healthcheck (ohne Auth)
- `GET /api/books` - Buecher auflisten (paginiert, filterbar)
- `GET /api/search?q=...` - Volltextsuche
- `GET /api/config` - Oeffentliche Konfiguration
- `GET /api/config/update-check` - Update-Pruefung
- `POST /api/backup/create` - Backup erstellen

Vollstaendige API-Dokumentation: `http://localhost:8160/docs`

## Docker-Befehle

```bash
cd docker

# Status
docker compose ps

# Logs
docker compose logs -f
docker compose logs -f backend    # Nur Backend

# Neustart
docker compose restart
docker compose restart backend    # Nur Backend

# Stoppen
docker compose down

# Komplett neu bauen
docker compose up -d --build
```

## Ports

| Dienst | Port | Beschreibung |
|--------|------|-------------|
| Frontend (Nginx) | 8160 (konfigurierbar) | Externer Zugang |
| Backend (Uvicorn) | 8000 (intern) | Nur via Nginx erreichbar |
| LM Studio | 1234 (extern) | Optional, auf separatem Rechner |
