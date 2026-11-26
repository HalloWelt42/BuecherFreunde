# Codestellen ausführen (BF-29)

In Lehrbüchern zur Informatik lassen sich Listings direkt ausführen und Schritt für Schritt ansehen. BücherFreunde rechnet
dabei nichts selbst: gerechnet wird in der Sandbox der Codeschmiede (ohne Netz, nur lesend, mit Grenzen), eingeschätzt von
der lokalen KI über die Leitstelle. Dieser Text beschreibt den Server; die Oberfläche (Taste am Codebeginn, schwebendes
Fenster mit Editor und Debugger) folgt.

## Aufbau

```
Buch (PDF, EPUB, Markdown, Text)
  -> Erkennung im Hintergrund, eigener Prozess        backend/app/codestellen/ (pdf.py, auszeichnung.py, sprache.py)
       Begleiter codestellen.json neben seiten.json    eine Wahrheit für Originalansicht und Textansicht
  -> Vorprüfung im Hintergrund, gedrosselt, anhaltbar  codestellen/vorpruefung.py
       1. Lauf in der Sandbox: läuft für sich (mit Ausgabe)?
       2. sonst lokale KI über die Leitstelle: "Auszug", kurzer Grund, was fehlt (nur ein Vorschlag, der Code bleibt)
  -> Schnittstelle /api/ausfuehren, /api/books/{id}/codestellen     api/ausfuehren.py
  -> Sandbox der Codeschmiede (CODESCHMIEDE_URL), App-Zugang der Kellerwolke    services/ausfuehren.py
  -> Leitstelle (LEITSTELLE_ADRESSE), eigener Schlüssel                       services/ki.py, docs/LEITSTELLE.md
```

## Erkennung

- PDF: eine Zeile ist Code, wenn mindestens 85 % ihrer Zeichen in Festbreitenschrift stehen. Festbreite zeigt der Name der
  Schrift (viele Bücher markieren ihre Codeschrift nicht als Festbreite), dazu das Merkmal und gleiche Zeichenbreite.
  Seiten ohne eine solche Schrift werden nicht gelesen.
- Zeilennummern links vom Code werden herausgenommen und gemerkt; sie liefern Leerzeilen und zeigen, ob ein Listing auf
  der nächsten Seite weitergeht. Kopf- und Fußzeilen und Fußnoten mit Adressen zählen nicht.
- Kästen: die Flächen um den Code (Zeilenhintergrund, Innenfläche, Rahmen). Liegen zwei Hüllen an einer Kante bündig, ist
  der Kasten dort geteilt und geht auf der Nachbarseite weiter. Titel auf der oberen Kante, sonst eine Beschriftung
  darüber ("Listing 4.2: ..."), Dateizeile darunter.
- Über Seitenwechsel: endet eine Seite mit Code und beginnt die nächste mit Code ohne Titel, gleicher Größe und in
  derselben Spalte, ist es eine Stelle, solange nichts widerspricht (zwei geschlossene Kästen, Nummern, die neu beginnen).
- Text: Einrückung aus der Lage jedes Stücks, Leerzeilen aus Nummern oder Abstand, umbrochene Zeilen (mit Umbruchzeichen
  oder, bei nummerierten Listings, ohne eigene Nummer) an die vorige gehängt.
- Sprache: was das Buch sagt (Dateiname, Kastentitel, Beschriftung), sonst der Inhalt nach gewichteten Merkmalen; Python,
  das sich lesen lässt, und JSON zählen mehr. Titel, die eine Ausgabe oder einen Befehl zeigen, ergeben `ausgabe` oder
  `shell`. Nennt das Buch eine Sprache, deren Merkmale im Code fehlen, gilt der Befund als unsicher.
- EPUB: `<pre>`-Blöcke, Sprache aus `language-*`, `lang-*` oder `data-lang`. Markdown und Text: umzäunte Codeblöcke.
- Grenzen: Schriften mit Ligaturen nennen manche Zeichenpaare nicht (`==`, `<=`, `>=` und `!=` kommen alle als `^=`);
  eindeutige Paare (`//`, `/*`, `*/`, `</`, `??`, `::`, `__`, `...`) werden zurückgewonnen, die übrigen bleiben sichtbar
  stehen. Ein Leerzeichen genau an einer Bruchstelle ist im PDF nicht zu sehen; mitten in einem Namen bricht kein Buch,
  dort wird es ergänzt.

Ein Buch wird einmal erkannt: wer es öffnet, zuerst; neue Bücher nach dem Ablegen; vorhandene in der Pflege, je Runde nur
`CODESTELLEN_JE_RUNDE` Bücher ohne Erkennung. Steigt die Fassung der Erkennung (`codestellen/modelle.py`), wird neu
erkannt.

## Begleiter codestellen.json

```
{ "fassung": 2, "format": "pdf", "grund": "",
  "stellen": [ { "kennung": "s1-664-3f2a9c1e",
                 "teile": [ {"seite": 1, "rechteck": [74.0, 640.0, 521.0, 790.0], "offen_oben": false, "offen_unten": true, "zeilen": 4},
                            {"seite": 2, "rechteck": [74.0, 70.0, 521.0, 120.0], "offen_oben": true, "offen_unten": false, "zeilen": 3} ],
                 "sprache": "python", "sicherheit": 0.95, "quelle": "datei", "titel": "Ausprobieren - kap01/summe.py",
                 "datei": "kap01/summe.py", "code": "def summe(zahlen): ...", "zeilennummern_ab": 1, "pruefsumme": "3f2a9c1e..." } ] }
```

- `teile`: PDF mit Dateiseite, Rechteck in Punkten der Seite (oben links, wie PyMuPDF) und der Zahl der Codezeilen dieses
  Teils (der Reihe nach); EPUB mit `kapitel` und `nr` (der wievielte Codeblock im Kapitel); Markdown und Text mit `zeile`.
- `kennung`: Lage des ersten Teils und Prüfsumme des Codes. `sicherheit` ab 0,6 gilt als sicherer Befund.

## Schnittstelle

Alle Wege brauchen die Anmeldung. Geht etwas nicht, kommt ein Grund statt eines Fehlers.

| Weg | Antwort |
|---|---|
| `GET /api/ausfuehren` | `{bereit, sprachen: [{sprache, fassungen, aufzeichnen}], grund}`; Fassungen nur bei PHP, neueste zuerst |
| `POST /api/ausfuehren` `{code, sprache, fassung, eingabe}` | `{aufzeichnung, grund}`; `aufzeichnung`: `{art, ausgabe, fehler, fehlerzeile, hinweise, gekuerzt, zeitueberschreitung, laufzeit_ms, schritte}` wie der Debugger der Codeschmiede sie liefert (ohne Aufzeichnung leere Schritte) |
| `GET /api/ausfuehren/funktionen/php` | je PHP-Fassung die eingebauten Funktionen; leer ohne Codeschmiede |
| `GET /api/books/{id}/codestellen?von=&bis=` | `{buch, stand, format, grund, anzahl, stellen}`; `stand`: `erkannt`, `ausstehend` (kommt sofort dran, später erneut fragen), `ohne` (Format ohne Codeblöcke); mit `von`/`bis` (Dateiseiten) nur Stellen, die hineinreichen, Ketten ganz |
| `GET /api/ausfuehren/vorpruefung` | `{bereit, ki, laeuft, angehalten, grund, geprueft, offen}` |
| `POST /api/ausfuehren/vorpruefung/anhalten`, `.../fortsetzen` | derselbe Stand |

Je Stelle in `stellen` dazu: `ausfuehrbar` (Sprache der Sandbox mit sicherem Befund, die Sandbox antwortet: hier gehört
die Taste hin) und `vorpruefung` (nur bei ausführbaren Stellen) `{stand: laeuft | auszug | offen, quelle: lauf | ki, ausgabe,
fehler, grund, fehlt, geprueft_am}`. `fehlt` nennt Wörter aus `import`, `paket`, `klasse`, `funktion`, `variable`,
`datei`, `eingabe`, `netz`, `datenbank`, `rahmenwerk`, `vorgaenger`, `sonstiges`.

Gründe der Sandbox: "Keine Codeschmiede eingetragen", "Sandbox gerade nicht erreichbar", "Diese App darf die Sandbox nicht
nutzen", "Die Sandbox rechnet gerade für BücherFreunde; gleich noch einmal", sonst die Meldung der Codeschmiede.

`GET /api/config/oberflaeche` nennt in `anschluesse.ausfuehren`, ob eine Codeschmiede eingetragen ist (ohne sie keine
Taste); `GET /api/verbindungen` zeigt Codeschmiede und Leitstelle mit Stand und Grund.

## Textansicht

`GET /api/books/{id}/textseiten` setzt für jeden Teil einer erkannten Codestelle einen Baustein `code` an ihren Ort, statt
Textblöcken und Ausschnitt: `{art: "code", titel, zeilen, sprache, kennung, teil, teile}`. `zeilen` sind die Zeilen dieses
Teils; aufeinanderfolgende Teile derselben `kennung` (Teil 0 bis `teile - 1`) ergeben am Stück den Code der Stelle, die
Seitenmarke gehört danach. Den Titel trägt nur Teil 0. Alles im Kasten (Titel auf der Kante, Zeilennummern, Rahmen) gehört
zum Baustein; die Abbildungen der Seite zählen ohne ihn (Bild-Endpunkt mit derselben Zählung). Ist ein Buch noch nicht
erkannt, bleibt die Seite wie bisher, und das Buch kommt sofort an die Reihe.

## Sandbox

- Die Codeschmiede nimmt je App einen Lauf zugleich an. BücherFreunde reiht seine Läufe ein: Menschen vor der Vorprüfung.
- Läufe werden aufgezeichnet, wo die Sprache es kann; sonst nur ausgeführt (Ausgabe, Hinweise, Fehler mit Zeile).
- PHP ohne `<?php` bekommt die Marke vor die erste Zeile, damit die Zeilen des Laufs zu denen im Buch passen.
- Höchstens 20.000 Zeichen Code. Das Angebot der Sandbox gilt zehn Minuten.
- Die Codeschmiede lässt nur Apps auf ihrer Liste "Sandbox für Apps" zu; verglichen wird der Name des App-Zugangs der
  Kellerwolke in Kleinschrift.

## Vorprüfung

- Je Stelle in einer Sprache der Sandbox mit sicherem Befund. Ergebnis gemerkt je Sprache und Prüfsumme des Codes (Tabelle
  `code_vorpruefung`), neu nur, wenn sich der Code ändert.
- Pause zwischen zwei Läufen (`VORPRUEFUNG_ABSTAND_S`); anhaltbar über die Schnittstelle.
- Sandbox oder Leitstelle gerade weg: weiter in der nächsten Runde (alle zehn Minuten und nach jeder Erkennung). Lehnt eine
  ab (nicht zugelassen, gesperrt, Schlüssel unbekannt): die Vorprüfung hält mit dem Grund an, bis ein Mensch sie fortsetzt.
- Ohne Leitstelle ist der Fehler des Laufs der Grund.

## Einstellungen

| Wert | Bedeutung |
|---|---|
| `CODESCHMIEDE_URL` | Adresse der Codeschmiede; leer: keine Taste, kein Aufruf, die Erkennung läuft trotzdem |
| `CODESTELLEN_JE_RUNDE` | so viele Bücher ohne Erkennung nimmt die Pflege je Runde (Vorgabe 3) |
| `VORPRUEFUNG_ABSTAND_S` | Pause zwischen zwei Vorprüfungen in Sekunden (Vorgabe 5) |
| `LEITSTELLE_ADRESSE`, `LEITSTELLE_SCHLUESSEL_DATEI`, `KI_MODELL` | KI über die Leitstelle (docs/LEITSTELLE.md); leer: Vorprüfung nur per Lauf |
