---
zweck: "Die Bücherverwaltung des Hauses: Bibliothek mit Lesern für PDF und EPUB, Volltextsuche, Markierungen und Notizen; liefert Fundus die Bücher mit Seiten."
geraet: [pi]
abhaengigkeiten: [kellerwolke]
daten:
  - "Pi: Datenbank `/home/pi/BuecherFreunde/docker/database/buecherfreunde.db` (rund 575 MB, Bücher, Volltext, Markierungen, Notizen, Einstellungen)"
  - "Pi: Bücher-Speicher `/mnt/data/buecher` (rund 23 GB, je Buch ein Ordner mit Datei, Umschlag und Metadaten), Import-Ordner `docker/import`, Sammlung nur lesend `/mnt/data/calibre_sammlung`"
sicherung:
  - "die Datenbank sichert nur `update.sh` vor einem Update nach `docker/database/backups`; seit dem 22.03.2026 ist dort nichts Neues entstanden (Stand 24.10.2026). Das Werkzeug Sicherungen holt den Ordner nach `~/Sicherungen/buecherfreunde/pi` und meldet ihn als veraltet"
  - "der Bücher-Speicher wird nicht gesichert (Stand 24.10.2026)"
schluessel_orte:
  - "Pi: `/home/pi/BuecherFreunde/zugang/kellerwolke.schluessel`, Modus 0600 (App-Zugang der Kellerwolke) und `zugang/hausstelle.pem`"
  - "Pi: `/home/pi/BuecherFreunde/.env` (Ordner, Port, Adresse der Kellerwolke, Pfad zur Schlüsseldatei)"
einrichten: einrichten.sh
stand: 0d12e43
---

# BücherFreunde

## Zweck

BücherFreunde verwaltet die Bücher des Hauses: Bibliothek mit Filtern, Kategorien und Sammlungen, Leser für PDF (mit
Textschicht und Markierungen), EPUB und Markdown, Volltextsuche, Notizen mit Seitenangabe, Metadaten aus offenen
Quellen und Import gemeinfreier Bücher. Angemeldet wird mit dem Konto der [[Kellerwolke]]. Für [[Fundus]] ist sie die
Quelle der Bücher: Fundus holt sich Volltexte mit Dateiseite und gedruckter Seite und verweist zurück an die
Fundstelle im Leser.

Auf dem Pi laufen zwei Container aus `docker/docker-compose.yml`: das Backend (FastAPI) und die Oberfläche (nginx, Port
{{port:frontend}}), die `/api/` ans Backend reicht. Gearbeitet wird auf dem Zweig `dev`, auch auf dem Pi.

## Was sie braucht

- Pi nach [[Grundlage Pi]] mit Docker und Platz für die Bücher unter `/mnt/data`.
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
git clone -b dev {{repo}} /home/pi/BuecherFreunde
```

Probe: `git -C /home/pi/BuecherFreunde branch --show-current` meldet `dev`.

### 2. Zugang zur Kellerwolke

Aus der Sicherung den Ordner `zugang/` zurückspielen. Frisch auf dem Rechner der [[Kellerwolke]] den App-Zugang
anlegen (`tools/app_zugang.py --konto <konto> --app BücherFreunde --datei /home/pi/BuecherFreunde/zugang/kellerwolke.schluessel`
im Klon der Kellerwolke) und die Hausstelle als `zugang/hausstelle.pem` daneben legen.

Probe: `stat -c %a /home/pi/BuecherFreunde/zugang/kellerwolke.schluessel` meldet 600.

### 3. Einrichten und starten

`./einrichten.sh` ruft `./install.sh`: fragt Bücher-Speicher (`/mnt/data/buecher`), Import-Ordner, Datenbank-Ordner,
Sammlung (`/mnt/data/calibre_sammlung`), Port und Adresse der Kellerwolke ab und schreibt die `.env` (nur, wenn keine da
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
- Der Browser zeigt nach einem Update den alten Stand: die Startseite wird nie zwischengespeichert; einmal neu laden.
