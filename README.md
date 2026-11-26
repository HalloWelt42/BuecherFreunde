# BücherFreunde

Selbst gehostete Buchverwaltung für 50.000+ Bücher. Läuft per Docker auf Raspberry Pi 5 und Mac.

## Features

- **Bibliothek**: Grid/Listenansicht mit Filtern, Kategorien, Tags, Sammlungen
- **Formate**: PDF, EPUB, MOBI, TXT, Markdown
- **Reader**: PDF mit TextLayer (Textauswahl, Markierungen), EPUB mit foliate-js, Markdown
- **Suche**: FTS5 Volltextsuche mit Snippets und Hervorhebung
- **Markierungen**: Farbige Textmarkierungen mit Notizen (PDF + EPUB)
- **Notizen**: Buchnotizen mit Seitenreferenz, Schnellnotiz-Pad
- **Gutenberg**: Gemeinfreie Bücher direkt von Project Gutenberg importieren
- **Metadaten**: Open Library, Google Books, Wikipedia/Wikidata
- **KI**: Einordnen in Regale (freiwillig, jede Schnittstelle unter /v1)
- **Vorlesen**: mit den Stimmen des Geräts oder einem Sprechdienst, Stimme wählbar
- **Läuft allein**: ohne Wolke, ohne KI, ohne weitere Dienste; was angeschlossen ist, kommt dazu
- **Backup**: DB + Metadaten als ZIP, Buchmaterial per rsync
- **Dark Mode**: Vier Papier-Modi im Reader (Normal, Sepia, Dunkel, Kontrast)
- **Telefon**: Eigene Ansicht zum Suchen und Lesen mit Vollansicht

## Voraussetzungen

- Docker und Docker Compose
- Für Raspberry Pi: 64-bit OS (Raspberry Pi OS Lite empfohlen)
- Für Mac: Docker Desktop

## Installation

### Raspberry Pi

```bash
git clone https://github.com/HalloWelt42/BuecherFreunde.git
cd BuecherFreunde
./install.sh
```

Das Skript fragt interaktiv nach:
- Pfad für Bücher-Verzeichnis (Storage)
- Pfad für Import-Verzeichnis
- Pfad für Datenbank
- Pfad für externen Scan-Ordner (optional)
- Port (Standard: 8160)
- Adresse der Leitstelle für die KI (optional)

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
# .env anpassen (Pfade; alles andere ist freiwillig)
./start.sh
```

`start.sh` startet Backend und Frontend im Entwicklungsmodus (ohne Docker).

## Konfiguration

Alle Einstellungen stehen in der `.env` Datei im Projektverzeichnis:

```
# Server
EXTERNAL_PORT=8160              # Port für den Zugriff

# Kellerwolke, freiwillig: leer = eigenes Konto und Bücher auf diesem Gerät
KELLERWOLKE_URL=                                          # Adresse der Kellerwolke
KELLERWOLKE_CA=/app/zugang/hausstelle.pem                 # Zertifikatsstelle des Heimnetzes
KELLERWOLKE_SCHLUESSEL_DATEI=/app/zugang/kellerwolke.schluessel   # eigener App-Zugang (Modus 0600)
ANMELDUNG_KONTEN=                                         # weitere Konten außer dem Besitzer (kommagetrennt)
FUNDUS_APPS=Fundus                                        # Apps, die den Bestand über fundus/* lesen dürfen

# Pfade
STORAGE_DIR=/pfad/zu/buechern   # Arbeitsverzeichnis mit Hash-Ordnern
EXTERNAL_DIR=/pfad/zum/scannen  # Scan-Ordner (read-only, kann leer sein)
IMPORT_DIR=/pfad/zum/import     # Upload-Ziel
DATABASE_DIR=/pfad/zur/db       # SQLite + Backups

# Quellen für Angaben (alle freiwillig, ohne Schlüssel; jede einzeln abschaltbar)
DNB_ENABLED=true                # Deutsche Nationalbibliothek
K10PLUS_ENABLED=true            # Verbundkatalog K10plus
OPENLIBRARY_ENABLED=true        # Open Library
OPENLIBRARY_RATE_LIMIT=1        # Anfragen pro Sekunde
CROSSREF_ENABLED=true           # Fachartikel und Fachbücher mit DOI
WIKIPEDIA_ENABLED=true          # Wikipedia und Wikidata
GND_ENABLED=true                # Gemeinsame Normdatei (Autoren)
GUTENBERG_ENABLED=true          # gemeinfreie Bücher
GOOGLE_BOOKS_API_KEY=           # ohne eigenen Schlüssel wird Google Books nie gefragt
QUELLEN_KONTAKT=                # freiwillig: Seite oder Mail im Ausweis der App; Wikimedia und Open Library erlauben damit mehr
QUELLEN_HINTERGRUND_TAG=500     # höchstens so viele Anfragen je Quelle und Tag in Hintergrundläufen
QUELLEN_VORRAT_MB=32            # gemerkte Antworten in der Datenbank

# KI über die Leitstelle (optional): Einordnen, Vorprüfung der Codestellen, Vorlesen
LEITSTELLE_ADRESSE=             # leer: ohne KI
LEITSTELLE_SCHLUESSEL_DATEI=    # Schlüssel der Anwendung als Datei, Modus 0600
KI_MODELL=qwen/qwen3-next-80b   # Modellwahl der App
SPRECHDIENST=klangwerk-sprechen # Vorlesen über diesen Dienst der Leitstelle
```

### Anschlüsse

Alles hier ist freiwillig. Fehlt ein Anschluss, fehlt nur seine Fähigkeit, und die Oberfläche zeigt sie nicht.

| Anschluss | Einstellung | Ohne ihn |
|---|---|---|
| Kellerwolke (Ablage und Anmeldung) | `KELLERWOLKE_URL` und App-Zugang | Bücher liegen auf dem Gerät; beim ersten Öffnen legt man ein eigenes Konto an |
| Fundus (Suche nach Bedeutung) | `FUNDUS_URL`, `FUNDUS_SAMMLUNG` | Suche nach Wörtern |
| Assistent | `ASSISTENT_URL` | kein Gespräch über Stellen |
| Nachschlag (Lexika, Handbücher) | `NACHSCHLAG_URL` | Nachschlagen im öffentlichen Lexikon im Netz (`WIKIPEDIA_ENABLED`), abgeschaltet keins |
| Codeschmiede (Sandbox) | `CODESCHMIEDE_URL`, dazu `CODESTELLEN_JE_RUNDE`, `VORPRUEFUNG_ABSTAND_S` | Codestellen werden erkannt, aber nicht ausgeführt (docs/neubau/AUSFUEHREN.md) |
| Leitstelle (KI und Stimme) | `LEITSTELLE_ADRESSE`, `LEITSTELLE_SCHLUESSEL_DATEI`, `KI_MODELL`, `SPRECHDIENST` | Einordnen von Hand, Vorprüfung der Codestellen nur per Lauf, vorgelesen wird mit den Stimmen des Geräts (docs/LEITSTELLE.md) |
| Verzeichnisse, Lexikon, Normdatei | `DNB_ENABLED`, `K10PLUS_ENABLED`, `OPENLIBRARY_ENABLED`, `CROSSREF_ENABLED`, `WIKIPEDIA_ENABLED`, `GND_ENABLED`, `GOOGLE_BOOKS_API_KEY` | Angaben aus den Dateien |

Der Port ist im Heimnetz offen (`BINDUNG=0.0.0.0`). Von außen erreichbar macht man die App nur hinter einem Vorbau mit HTTPS
(dann `BINDUNG=127.0.0.1`).

### Konfiguration ändern

```bash
./setup.sh                      # Interaktives Menü
# oder direkt:
nano .env
cd docker && docker compose restart
```

## Updates

### Update-Hinweis im Frontend

Die Sidebar zeigt automatisch an, wenn eine neue Version auf GitHub verfügbar ist.

### Update ausführen

```bash
cd ~/BuecherFreunde
./update.sh
```

Das Skript:
1. Holt den neuen Code von GitHub (`git pull` des Zweigs, auf dem der Klon steht)
2. Baut die Docker-Container neu
3. Sichert die Datenbank, wenn die jüngste Sicherung älter als 24 Stunden ist und sich seitdem etwas geändert hat
4. Startet neu; DB-Schema-Migrationen laufen automatisch beim Start

### Was passiert mit den Daten?

| Daten | Beim Update | Sicher? |
|-------|-------------|---------|
| Bücher (Storage) | Unverändert (Volume) | Ja |
| Datenbank | Auto-Migration + Sicherung vorher (nach der Sicherungsregel) | Ja |
| Notizen, Markierungen | In der DB, migriert mit | Ja |
| .env Konfiguration | Unverändert | Ja |

### Rollback

```bash
# Datenbank aus der jüngsten Sicherung zurückspielen (im Ordner docker; gehören die Dateien root, mit sudo)
cd docker && docker compose --env-file ../.env stop backend
unzip -o -j "$(ls -t database/backups/buecherfreunde_backup_*.zip | head -1)" database/buecherfreunde.db -d database
rm -f database/buecherfreunde.db-wal database/buecherfreunde.db-shm
docker compose --env-file ../.env start backend
```

## Datensicherheit

### Schutz vor Datenverlust

Beim ersten Start legt das Backend eine Marker-Datei `.buecherfreunde` im Storage- und Datenbank-Verzeichnis an. Bei jedem weiteren Start wird geprüft:

- **Festplatte nicht gemountet**: Backend startet nicht (statt leere DB auf SD-Karte anzulegen)
- **Marker-Datei fehlt**: Backend startet nicht (falscher Mount-Punkt?)
- **Externer Scan-Ordner fehlt**: Wird übersprungen, Backend startet normal

Docker startet den Container automatisch neu (`restart: unless-stopped`), sobald die Platte wieder verfügbar ist.

### Backup

**Anwendungsdaten** (DB, Metadaten, Notizen) als ZIP in `DATABASE_DIR/backups`, nach der Sicherungsregel
(`SICHERUNG_ABSTAND_TAGE=7`, `SICHERUNG_VOR_AUSROLLEN_AB_STUNDEN=24`, `SICHERUNG_BEHALTEN=3`, in der `.env` änderbar):
- Regelmäßig: `python -m backend.app.services.sicherung regelmaessig` im Backend-Container, etwa täglich per cron;
  neu nur, wenn die jüngste älter als 7 Tage ist
- Vor jedem Update (`update.sh`): neu nur, wenn die jüngste älter als 24 Stunden ist
- Über die Einstellungen-Seite oder API: `POST /api/backup/create`, sofort
- Nie ohne Änderung der Datenbank; es bleiben höchstens drei

**Buchmaterial** (die Dateien selbst):
```bash
rsync -av /mnt/festplatte/ebooks/ /backup/ebooks/
```

## Datenverteilung

| Wo | Was |
|----|-----|
| SQLite (DATABASE_DIR) | Metadaten, Kategorien, Sammlungen, Notizen, Highlights, Lesefortschritt, FTS-Index |
| Hash-Ordner (STORAGE_DIR) | Buchdateien (original.pdf/epub), Cover (cover.jpg), Volltext (fulltext.txt), Metadaten-Sidecar (metadata.json) |

## Gutenberg-Import

Unter **Import > Gutenberg** können gemeinfreie Bücher von Project Gutenberg importiert werden:

- Suche nach Titel, Autor oder Thema
- Sprachfilter (z.B. `de` für Deutsch, `en` für Englisch, `de,en` für beides)
- Vorschau mit Cover, Format und Download-Anzahl
- Mehrfachauswahl und Batch-Import mit Fortschrittsbalken
- Automatische Kategorie "Gutenberg" für alle importierten Bücher
- Duplikat-Erkennung per SHA-256 Hash und Gutenberg-ID

## Architektur

```
BücherFreunde/
 ├── frontend/          # Svelte 5 + Vite
 ├── backend/           # Python FastAPI + SQLite
 ├── docker/            # docker-compose.yml + nginx.conf
 ├── .env               # Konfiguration (nicht im Git)
 ├── install.sh         # Erstinstallation
 ├── setup.sh           # Konfiguration ändern
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
| Metadaten | Deutsche Nationalbibliothek, K10plus, Open Library, Crossref, Wikidata und Wikipedia, GND (lobid.org), Google Books mit eigenem Schlüssel; ein gemeinsamer Abruf mit Takt, Vorrat und Pausen (`backend/app/quellen`) |
| Gutenberg | Gutendex-API (gutendex.com), Dateien von den Spiegeln |
| KI | über die Leitstelle des Hauses (optional, docs/LEITSTELLE.md) |
| Container | Docker Compose (python:3.12-slim, nginx:alpine) |

### API

Ohne Kellerwolke hat die App eigene Konten (`POST /api/anmeldung/einrichten`, nur für das erste). Mit ihr: Anmeldung mit dem
Konto der Kellerwolke (Passwort oder Gerät mit Code koppeln) über den Anmeldebaustein des Appkern; Wege unter `/api/anmeldung`. Den App-Zugang legt man auf dem Rechner der Kellerwolke an
(`tools/app_zugang.py --konto <konto> --app BücherFreunde --datei <ordner>/zugang/kellerwolke.schluessel`); der
Ordner `zugang/` wird nach `/app/zugang` eingebunden. Anmelden darf das Konto, dem der Zugang gehört.

Für Fundus gibt es den Anbieterweg `GET /api/v1/fundus/{steckbrief,suche,inhalt/{buch},bestand,umschlag/{buch}}`,
nur mit dem App-Schlüssel der Kellerwolke einer App aus `FUNDUS_APPS`.

Alle anderen Endpunkte unter `/api/` brauchen eine Anmeldung (Kopf `Authorization: Bearer` oder `X-Kellerwolke-Sitzung`):

- `GET /api/health` - Healthcheck (ohne Auth)
- `GET /api/books` - Bücher auflisten (paginiert, filterbar)
- `GET /api/search?q=...` - Volltextsuche
- `GET /api/config` - Öffentliche Konfiguration
- `GET /api/config/update-check` - Update-Prüfung
- `GET /api/gutenberg/suche` - Gutenberg-Suche
- `POST /api/gutenberg/import` - Gutenberg-Bücher importieren
- `POST /api/backup/create` - Backup erstellen

Vollständige API-Dokumentation: `http://localhost:8160/docs`

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
docker compose --env-file ../.env up -d --build --force-recreate
```

## Ports

| Dienst | Port | Beschreibung |
|--------|------|-------------|
| Frontend (Nginx) | 8160 (konfigurierbar) | Externer Zugang |
| Backend (Uvicorn) | 8000 (intern) | Nur via Nginx erreichbar |
