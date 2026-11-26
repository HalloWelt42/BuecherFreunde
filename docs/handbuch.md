---
zweck: "Die Bücherverwaltung des Hauses: Bibliothek mit Lesern für PDF und EPUB, Volltextsuche, Suche nach Bedeutung, Markierungen und Notizen; die Dateien liegen in der Kellerwolke, Fundus holt sich die Bücher mit Seiten."
geraet: [pi5b]
abhaengigkeiten: [kellerwolke]
daten:
  - "pi5b: Datenbank `{{wurzel}}/daten/bestand/buecherfreunde.db` (Angaben, Notizen, Markierungen, Lesestände, Einstellungen)"
  - "pi5b: Suchindex `{{wurzel}}/daten/suche/suche.db` (jederzeit neu zu bauen), Volltexte `{{wurzel}}/daten/texte`, Umschläge `{{wurzel}}/daten/umschlaege` (beides auch im Begleiter jedes Buchs in der Kellerwolke)"
  - "Kellerwolke: Originale und je Buch ein Begleiter (Umschlag, Volltext, Angaben) unter `Apps/BücherFreunde`"
sicherung:
  - "die Datenbank als ZIP nach `{{wurzel}}/daten/bestand/backups`, nach der Sicherungsregel der Altfassung; der Dateipool der Kellerwolke wird nicht gesichert (Stand 25.11.2026)"
schluessel_orte:
  - "pi5b: `{{wurzel}}/zugang/kellerwolke.schluessel`, Modus 0600 (App-Zugang der Kellerwolke) und `zugang/hausstelle.pem`"
  - "pi5b: `{{wurzel}}/zugang/leitstelle.schluessel`, Modus 0600 (Schlüssel der Anwendung in der Leitstelle), wenn `LEITSTELLE_ADRESSE` gesetzt ist"
  - "pi5b: `{{wurzel}}/.env` (Orte, Port, Adresse der Kellerwolke, Pfad zur Schlüsseldatei)"
einrichten: einrichten.sh
stand: 979fe55
---

# BücherFreunde (Neubau)

## Zweck

BücherFreunde verwaltet die Bücher des Hauses. Der Neubau läuft auf pi5b neben der Altfassung, bis umgestellt wird.
Originale liegen in der [[Kellerwolke]]; auf dem Gerät liegen Datenbank, Suchindex, Volltexte und Umschläge. Für [[Fundus]]
ist die App die Quelle der Bücher; die Nummern der Bücher sind dieselben wie in der Altfassung.

Zwei Container aus `docker/pi5b.compose.yml`: das Backend (FastAPI) und die Oberfläche (nginx, Port
{{port:ziel/oberflaeche}}, nur am Gerät selbst). Im Heimnetz erreicht man sie über den [[Vorbau]] unter ihrem Namen (HTTPS);
die App meldet selbst an, mit dem Konto der [[Kellerwolke]].
Die Oberfläche setzt die Sicherheitsköpfe samt Content-Security-Policy aus `docker/sicherheit.conf` (im Bild unter
`/etc/nginx/snippets/`): Skripte nur von der App selbst, damit kein Skript aus einem Buch läuft.

`Apps/BücherFreunde/Eingangsordner` in der [[Kellerwolke]]: was dort liegt, nimmt die App jede Minute auf, die Datei zieht dabei
nach `Bücher` um. Doppel, fremde Formate und Unlesbares bleiben liegen und stehen unter "Hinzufügen".

## Was sie braucht

- Docker und die [[Kellerwolke]] mit einem App-Zugang als Datei `zugang/kellerwolke.schluessel`, dazu die Hausstelle als
  `zugang/hausstelle.pem`; Adresse der Kellerwolke `{{umgebung:KELLERWOLKE_URL}}`.
- Ohne sie läuft sie weiter, ihr fehlt nur die Fähigkeit: [[Fundus]] für die Suche nach Bedeutung, der Sprechdienst der
  [[Leitstelle]] zum Vorlesen (`SPRECHDIENST`, ohne ihn die Stimmen des Geräts), Nachschlag zum Nachschlagen im Leser (`NACHSCHLAG_URL`; ohne ihn schlägt der Leser im öffentlichen Lexikon
  im Netz nach, solange `WIKIPEDIA_ENABLED` an ist), Assistent für das Gespräch über eine Stelle (`ASSISTENT_URL`). Ohne [[Kellerwolke]] gelten eigene Konten und die Ablage auf dem Gerät; hier ist sie angeschlossen.
- Codestellen in Lehrbüchern erkennt die App selbst (im Hintergrund, je Buch einmal, Begleiter `codestellen.json` neben
  dem Volltext). Ausgeführt werden sie in der Sandbox der Codeschmiede (`CODESCHMIEDE_URL`; die Codeschmiede muss
  `bücherfreunde` in "Sandbox für Apps" führen), eingeschätzt von der lokalen KI über die Leitstelle (`LEITSTELLE_ADRESSE`,
  Schlüssel `zugang/leitstelle.schluessel`). Ohne Codeschmiede keine Taste, ohne Leitstelle prüft nur der Lauf vor.

## Neu einrichten

### 1. Ordner und Zugang

Den Stand nach `{{wurzel}}` legen, dazu `zugang/` und `.env` aus der Sicherung.

Probe: `stat -c %a {{wurzel}}/zugang/kellerwolke.schluessel` meldet 600.

### 2. Einrichten und starten

`./einrichten.sh` legt die Orte an, baut und startet die Container.

Probe: `curl -s http://127.0.0.1:{{port:ziel/oberflaeche}}/api/health` antwortet.

### 3. Orte festlegen

`ORT_BESTAND`, `ORT_SUCHE`, `ORT_TEXTE`, `ORT_UMSCHLAEGE` in der `.env`; der Zwischenspeicher liegt im Arbeitsspeicher
(`ZWISCHEN_GROESSE`). Jeder Ort trägt eine Markerdatei; fehlt sie, startet das Backend nicht (Platte nicht eingehängt).
Umziehen: Backend anhalten, Ordner kopieren, Wert in der `.env` ändern, starten. Datenbankdateien gehören nicht auf eine
Netzfreigabe (Sperren und WAL sind dort unsicher); eine Platte im NAS dafür als Blockgerät einhängen.

Probe: `/api/orte` nennt je Ort Pfad, freien Platz und `gut`.

## Sicherung und Rückspielen

Wie in der Altfassung über `backend/app/services/sicherung.py`. Der Suchindex wird nicht gesichert; er entsteht aus Angaben
und Volltexten neu. Fehlen Volltext oder Umschlag, kommen sie aus dem Begleiter des Buchs in der Kellerwolke zurück.

## Wenn etwas klemmt

- Ein Buch öffnet nicht: die Kellerwolke ist nicht erreichbar oder die Datei fehlt dort; `/api/verbindungen` sagt es.
- Das Backend startet nicht und nennt einen Ort: die Platte ist nicht eingehängt.
- Keine Taste an Codestellen: `/api/ausfuehren` nennt den Grund (Codeschmiede nicht erreichbar oder BücherFreunde nicht in
  "Sandbox für Apps"); `/api/ausfuehren/vorpruefung` sagt, ob und warum die Vorprüfung angehalten ist, `.../fortsetzen`
  nimmt sie wieder auf.
