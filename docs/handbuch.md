---
zweck: "Die Bücherverwaltung des Hauses: Bibliothek mit Lesern für PDF und EPUB, Volltextsuche, Markierungen und Notizen; liefert Fundus die Bücher mit Seiten."
geraet: [pi]
abhaengigkeiten: [kellerwolke]
daten:
  - "Pi: Datenbank `{{umgebung:DATABASE_DIR}}/buecherfreunde.db` (rund 575 MB, Bücher, Volltext, Markierungen, Notizen, Einstellungen)"
  - "Pi: Bücher-Speicher `{{umgebung:STORAGE_DIR}}` (rund 23 GB, je Buch ein Ordner mit Datei, Umschlag und Metadaten), Import-Ordner `{{umgebung:IMPORT_DIR}}`, Sammlung nur lesend `{{umgebung:EXTERNAL_DIR}}`"
sicherung:
  - "die Datenbank sichert nur `update.sh` vor einem Update nach `docker/database/backups`; seit dem 22.03.2026 ist dort nichts Neues entstanden (Stand 24.10.2026). Das Werkzeug Sicherungen holt den Ordner nach `~/Sicherungen/buecherfreunde/pi` und meldet ihn als veraltet"
  - "der Bücher-Speicher wird nicht gesichert (Stand 24.10.2026)"
schluessel_orte:
  - "Pi: `{{wurzel}}/zugang/kellerwolke.schluessel`, Modus 0600 (App-Zugang der Kellerwolke) und `zugang/hausstelle.pem`"
  - "Pi: `{{wurzel}}/.env` (Ordner, Port, Adresse der Kellerwolke, Pfad zur Schlüsseldatei)"
einrichten: einrichten.sh
stand: 476af81
---

# BücherFreunde

## Zweck

BücherFreunde verwaltet die Bücher des Hauses: Bibliothek mit Filtern, Kategorien und Sammlungen, Leser für PDF (mit
Textschicht und Markierungen), EPUB und Markdown, Volltextsuche, Notizen mit Seitenangabe, Metadaten aus offenen
Quellen und Import gemeinfreier Bücher. Auf Telefon und Tablet (hoch und quer, am Rechner im Fenster bis 700 px) zeigt sie eine eigene, schlanke Ansicht:
Suche mit Weiterlesen und Suchverlauf, Buchseite und Leser mit Vollansicht; Verwaltung, Import und Einstellungen bleiben
am Rechner. Angemeldet wird mit dem Konto der [[Kellerwolke]]. Für [[Fundus]] ist sie die
Quelle der Bücher: Fundus holt sich Volltexte mit Dateiseite und gedruckter Seite und verweist zurück an die
Fundstelle im Leser.

Auf dem Pi laufen zwei Container aus `docker/docker-compose.yml`: das Backend (FastAPI) und die Oberfläche (nginx, Port
{{port:frontend}}), die `/api/` ans Backend reicht. Gearbeitet wird auf dem Zweig `dev`, auch auf dem Pi.

## Was sie braucht

- Pi nach [[Grundlage Pi]] mit Docker und Platz für den Bücher-Speicher `{{umgebung:STORAGE_DIR}}`.
- [[Kellerwolke]]: Konto zum Anmelden und ein App-Zugang für BücherFreunde, als Datei `zugang/kellerwolke.schluessel`
  mit der Hausstelle `zugang/hausstelle.pem`.
- Ohne sie läuft sie weiter, ihr fehlt nur die Fähigkeit: LM Studio für die Einordnung nach Kategorien, Open Library und
  andere Quellen für Metadaten.

## Neu einrichten

Zwei Wege. Aus der Sicherung: Datenbank und Bücher-Speicher zurückspielen, dann sind Bibliothek, Markierungen und
Notizen wie vorher. Frisch: leere Datenbank; die Bücher werden über den Import-Ordner neu eingelesen (die Dateien selbst
liegen im Bücher-Speicher oder in der Sammlung).

### 1. Klon auf dem Pi

```
git clone -b dev {{repo}} {{wurzel}}
```

Probe: `git -C {{wurzel}} branch --show-current` meldet `dev`.

### 2. Zugang zur Kellerwolke

Aus der Sicherung den Ordner `zugang/` zurückspielen. Frisch auf dem Rechner der [[Kellerwolke]] den App-Zugang
anlegen (`tools/app_zugang.py --konto <konto> --app BücherFreunde --datei {{wurzel}}/zugang/kellerwolke.schluessel`
im Klon der Kellerwolke) und die Hausstelle als `zugang/hausstelle.pem` daneben legen.

Probe: `stat -c %a {{wurzel}}/zugang/kellerwolke.schluessel` meldet 600.

### 3. Einrichten und starten

`./einrichten.sh` ruft `./install.sh`: fragt Bücher-Speicher (`{{umgebung:STORAGE_DIR}}`), Import-Ordner, Datenbank-Ordner,
Sammlung (`{{umgebung:EXTERNAL_DIR}}`), Port und Adresse der Kellerwolke ({{umgebung:KELLERWOLKE_URL}}) ab und schreibt die `.env` (nur, wenn keine da
ist; aus der Sicherung die alte `.env` vorher zurücklegen), baut und startet die Container und bietet den systemd-Dienst
`buecherfreunde` für den Start mit dem Pi an. Aus der Sicherung die Datenbank vor dem ersten Start in den
Datenbank-Ordner legen.

Probe: `curl -s http://127.0.0.1:{{port:frontend}}/api/health` auf dem Pi antwortet, und die Oberfläche zeigt nach der
Anmeldung mit dem Kellerwolke-Konto die Bibliothek.

### 4. Fundus anbinden

In [[Fundus]] unter Einstellungen die Adresse der Bücherverwaltung eintragen; BücherFreunde erlaubt Fundus über
`FUNDUS_APPS` in der `.env`.

Probe: in Fundus erscheint die Quelle Bücher, und eine Suche nennt Treffer mit Seite.

## Sicherung und Rückspielen

Eine regelmäßige Sicherung gibt es nicht (Stand 24.10.2026). `update.sh` legt vor einem Update eine Kopie der Datenbank
nach `docker/database/backups`; die jüngste dort stammt vom 22.03.2026. Das Werkzeug Sicherungen holt den Ordner
täglich nach `~/Sicherungen/buecherfreunde/pi` und führt ihn in `~/Sicherungen/LIESMICH.md` als veraltet. Der
Bücher-Speicher (rund 23 GB) wird nicht gesichert; die Sammlung ist nur gelesen und gehört nicht der App.

Von Hand: Container anhalten (`cd docker && docker compose --env-file ../.env stop backend`), die Datenbank kopieren
(`sqlite3 database/buecherfreunde.db ".backup '<ziel>'"` im Ordner `docker`), wieder starten. Zurückspielen umgekehrt:
anhalten, Kopie als `buecherfreunde.db` ablegen (alte `-wal` und `-shm` entfernen), starten; Probe wie in Schritt 3.

## Wenn etwas klemmt

- `update.sh` holt den Zweig `main`, gearbeitet wird aber auf `dev`. Auf dem Pi deshalb von Hand:
  `git pull --ff-only origin dev && cd docker && docker compose --env-file ../.env up -d --build --force-recreate`.
- Die Datenbank gehört root (der Container schreibt als root); Kopien und Rückspielen auf dem Pi mit `sudo`.
- Anmelden geht nicht: der App-Zugang fehlt (`zugang/kellerwolke.schluessel`) oder die Adresse der Kellerwolke in der
  `.env` stimmt nicht; das Backend meldet beim Start "Kein App-Zugang der Kellerwolke".
- Nach einem Update lädt die Seite die neue Fassung von selbst (Vergleich mit `/api/config/version`; nie während
  Vorlesen oder Hochladen). Dafür müssen Backend und Oberfläche zusammen neu gebaut werden, sonst meldet das Backend
  die alte Fassung und die Seite zeigt nur das Band "Jetzt neu laden".
- Das Symbol entsteht aus `frontend/public/symbol.svg`; nach einer Änderung `python3 tools/symbole.py` (braucht
  cairosvg und Pillow auf dem Mac) und die erzeugten Bilder mit einchecken.
