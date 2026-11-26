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
  - "jede neue Sicherung auch in die Kellerwolke nach `Apps/BücherFreunde/Sicherung`, solange eingeschaltet (BF-82); dazu je Buch der kleine Begleiter `persoenlich` und `Apps/BücherFreunde/profile.json` für einen Neuaufbau ohne Sicherung"
schluessel_orte:
  - "pi5b: `{{wurzel}}/zugang/kellerwolke.schluessel`, Modus 0600 (App-Zugang der Kellerwolke) und `zugang/hausstelle.pem`"
  - "pi5b: `{{wurzel}}/zugang/leitstelle.schluessel`, Modus 0600 (Schlüssel der Anwendung in der Leitstelle), wenn `LEITSTELLE_ADRESSE` gesetzt ist"
  - "pi5b: `{{wurzel}}/daten/bestand/schluessel.json`, Modus 0600 (Schlüssel, die in der App eingetragen sind: Ersteinrichtung, Anschlüsse, Umzug; gelten vor den Dateien unter `zugang/`)"
  - "pi5b: `{{wurzel}}/.env` (Orte, Port, Adresse der Kellerwolke, Pfad zur Schlüsseldatei)"
einrichten: einrichten.sh
stand: af2e377
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

### 4. Ersteinrichtung in der App

Nach einer Neuinstallation erscheint statt der Anmeldung der Assistent, aber nur bei einer wirklich neuen Installation: der
Bestand war beim ersten Start leer und trug keine Markerdatei. Eine laufende Installation sieht ihn nie von selbst und wird durch
ihn nie verändert. Hell, Dunkel, System und die Schriftgröße stehen von Anfang an oben rechts. Pflicht sind nur Konto und
Speicherorte, beide mit Vorschlag; alles andere lässt sich überspringen und steht danach in den Einstellungen. Wer die Seite
schließt oder den Rechner neu startet, macht am ersten offenen Schritt weiter. Am Ende steht eine Übersicht, was eingerichtet und
was übersprungen ist, jede Zeile mit dem Weg in ihre Einstellung.

Probe: `curl -s http://127.0.0.1:{{port:ziel/oberflaeche}}/api/einrichtung` meldet auf einer laufenden Installation `"modus":"aus"`.

Neu beginnen, Schritt für Schritt:

1. **Konto**: ein eigenes Konto anlegen oder mit dem Konto der Kellerwolke anmelden. Mit der Kellerwolke trägt man hier gleich ihre
   Adresse und den App-Zugang ein; der Schritt Anschlüsse zeigt sie dann als verbunden. Das Konto wird das erste Profil Verwaltung.
2. **Speicherorte**: jeder Ort mit Platz und Lampe. Fehlt eine Platte, steht das rot da und Weiter ist gesperrt, bis "Neu suchen"
   sie findet. Die Orte selbst stellt man in der `.env` ein (siehe "Orte festlegen"); sie ändern sich mit einem Neustart.
3. **Anschlüsse**: Kellerwolke, Leitstelle (KI und Sprechdienst) und Nachschlag, je Adresse und "Verbindung prüfen". Den Schlüssel
   fügt man einmal ein; der Server prüft ihn und legt ihn in seiner eigenen Schlüsseldatei ab (`schluessel.json` beim Bestand,
   Modus 0600). Danach steht nur noch "eingetragen" und "Ersetzen" da; ein neuer Schlüssel gilt erst, wenn seine Prüfung besteht.
   Der Nachschlag braucht keinen. Ohne Anschlüsse läuft die App voll. Solange es noch kein Konto gibt, nimmt der Assistent nur
   Adressen mit https und Namen an (keine IP-Adresse, kein localhost, kein Port unter 1024 außer 443) und prüft höchstens wenige
   Male je Minute; nach dem Konto gilt das nicht mehr, dann braucht es die Anmeldung.
4. **Katalog**: der mitgelieferte, leer beginnen, oder der mitgelieferte mit einem Vorschlag aus dem Bestand nach dem Abschluss.
5. **Familie und Kinder**: allein oder Familie, Profile mit Rolle und PIN, für Kinder Stufe und Stimme der Ansagen, dazu die Stimme
   der Familie. Freigaben und Lesezeit stellt man danach im Elternbereich ein.
6. **Erste Bücher**: Hochladen mit Vorschau, Eingangsordner, Ordner auf dem Gerät, gemeinfreie Bücher.

Wieder öffnen: Unter Einstellungen, Wartung öffnet "Assistent öffnen" dieselben Schritte wie "Neu beginnen", ohne Konto und ohne die anderen
Ausgangslagen. Am Ende steht jede Änderung mit Haken; übernommen wird nur, was angehakt ist. Entfernt wird nichts.

Die anderen drei Ausgangslagen stehen unter "Sicherung und Rückspielen".

## Sicherung und Rückspielen

Wie in der Altfassung über `backend/app/services/sicherung.py`. Der Suchindex wird nicht gesichert; er entsteht aus Angaben
und Volltexten neu. Fehlen Volltext oder Umschlag, kommen sie aus dem Begleiter des Buchs in der Kellerwolke zurück (die Prüfung
der Originale holt sie). Jede neue Sicherung legt die App auch in der Kellerwolke unter `Apps/BücherFreunde/Sicherung` ab, solange
das unter Einstellungen eingeschaltet ist; von dort holt sie ein neues Gerät beim Wiederherstellen. Zurückgespielt wird auf einem
neuen Gerät über die Ersteinrichtung (siehe unten und "Neu einrichten", Schritt 4). Auf einer laufenden Installation geht es unter Einstellungen, Wartung und
Sicherung über dieselbe Rückfrage und denselben Auftrag: die Rückfrage nennt den Bestand, der ersetzt wird, und vorher entsteht eine
Sicherung des jetzigen Stands im Sicherungsordner.

### Aus Sicherung wiederherstellen

Zuerst stehen die Speicherorte fest; einen Schritt Konto gibt es hier nicht, das Konto, die Profile und die Einstellungen kommen
aus der Sicherung. Die Sicherung kommt aus einer hochgeladenen Datei (in Teilen, nach einer Unterbrechung geht es am Stand weiter,
auch hinter dem Vorbau), aus dem Sicherungsordner des Geräts oder aus der Kellerwolke (dort mit Adresse und Schlüssel wie bei den
Anschlüssen); die Liste nennt je Sicherung Datum, Größe, Bücher und Profile, die neueste zuerst. Vor dem Einspielen zeigt die
Rückfrage, was die Sicherung enthält und was sie ersetzt; gibt es schon ein eigenes Konto, steht dort, dass es durch das aus der
Sicherung ersetzt wird. Wiederhergestellt wird nur auf einem leeren Bestand. Das Einspielen läuft als Auftrag "Sicherung
einspielen" mit Fortschritt; danach prüft ein Auftrag jedes Original. Der Bericht nennt, was erreichbar ist, was über die
Prüfsumme in der Kellerwolke wiedergefunden wurde (der neue Ort ist dann eingetragen) und was fehlt. Fehlende Bücher bleiben im
Bestand und tragen auf ihrer Seite einen Hinweis; ihre Datei lässt sich später hochladen. Gelöscht wird nichts.

### Ablage in der Kellerwolke übernehmen

Ein Neuaufbau ohne Sicherung. Nach Konto und Orten wählt man in der Kellerwolke den Ordner der Bücher (Vorgabe
`Apps/BücherFreunde/Bücher`); "Ordner prüfen" zählt Bücher, Auszüge und Profile, ohne dort etwas zu ändern. Der Neuaufbau baut aus
dem Auszug je Buch Bücher, Angaben, Volltext, Umschläge und das Persönliche je Profil auf, die Profile aus ihrer Datei
`Apps/BücherFreunde/profile.json`. PINs und Bild-PINs kommen nie mit; sie werden danach neu gesetzt. Bücher ohne Auszug kommen mit
Titel und Autor aus ihrem Namen in den Bestand und stehen im Bericht; ihre Angaben und ihr Volltext entstehen über "Bibliothek
ergänzen" neu. Pause hält den Auftrag an, fortgesetzt wird an derselben Stelle.

### Umzug von einer anderen Installation

1. Auf dem alten Gerät unter Einstellungen, Wartung und Sicherung "Umzug vorbereiten": eine frische Sicherung entsteht und ein
   Einmalcode erscheint, gültig 15 Minuten (`UMZUG_CODE_GILT_MIN`), für einen Umzug, mit wenigen Versuchen.
2. Auf dem neuen Gerät die Adresse des alten (nur https mit Namen) und den Code eintragen. "Verbinden" holt Sicherung, Einstellungen
   und die Schlüssel für Kellerwolke und Leitstelle direkt; die Schlüssel gehen nur in die Schlüsseldatei des neuen Geräts. Das
   Konto kommt mit, darum vorher keins anlegen. Das Einspielen läuft danach als Auftrag mit Fortschritt.
3. Mit Kellerwolke bleiben die Originale, wo sie sind, und eine Prüfung sieht nach, ob jedes erreichbar ist. Ohne Kellerwolke wählt
   man "Originale kopieren" (ein Auftrag holt sie mit Prüfsummen über das Netz, nach einer Unterbrechung an derselben Stelle weiter)
   oder "Ort übernehmen" (die Platte des alten Geräts hängt am neuen als Ort Volltexte; geprüft wird nur, ob jedes Original da ist
   und seine Prüfsumme stimmt).

Das alte Gerät bleibt unverändert, bis man es selbst abschaltet.

### Persönliches in der Kellerwolke

Notizen, Markierungen, Etiketten, Lesestand und Freigaben stehen zusätzlich je Buch und Profil in der Kellerwolke, in einer kleinen
Datei neben dem Original (`<Name des Originals>.persoenlich.json`), damit ein Neuaufbau ohne Sicherung sie zurückholt. Nachgeführt
wird laufend und gebündelt: erst nach einer ruhigen Weile ohne neue Änderung, dann ein Schreiben von ein paar hundert Byte; der
Auszug mit Volltext und Umschlag bleibt dabei unberührt. Beim ersten Start mit dieser Version werden einmal nur die Bücher
nachgetragen, zu denen es schon Persönliches gibt. Wer die Kellerwolke verwaltet, könnte es lesen. Abschalten unter Einstellungen,
Verbindungen, Karte der Kellerwolke; die Folgenvorschau fragt, ob die vorhandenen Dateien in den Papierkorb der Kellerwolke gehen.
Wieder einschalten zeigt ebenso vorher, wie viele Bücher eine Datei bekommen. In der App bleibt dabei alles.

## Wenn etwas klemmt

- Ein Buch öffnet nicht: die Kellerwolke ist nicht erreichbar oder die Datei fehlt dort; `/api/verbindungen` sagt es.
- Das Backend startet nicht und nennt einen Ort: die Platte ist nicht eingehängt.
- Keine Taste an Codestellen: `/api/ausfuehren` nennt den Grund (Codeschmiede nicht erreichbar oder BücherFreunde nicht in
  "Sandbox für Apps"); `/api/ausfuehren/vorpruefung` sagt, ob und warum die Vorprüfung angehalten ist, `.../fortsetzen`
  nimmt sie wieder auf.
