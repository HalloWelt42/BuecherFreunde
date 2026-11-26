# Neue Schnittstellen des Neubaus (BF-7 bis BF-10)

Alle Wege brauchen die Anmeldung (`Authorization: Bearer` oder `X-Kellerwolke-Sitzung`). Bilder, Dateien und Ereignisströme lesen sie aus dem Inhalts-Cookie von `POST /api/anmeldung/zugang`; in Adressen steht sie nie.
Fehler kommen als `{"detail": "deutscher Satz"}`. Die vorhandenen Wege bleiben unverändert.

## Annahme (Hochladen)

Ein Eintrag je Datei:

```
{ "id": 7, "name": "Buch.epub", "groesse": 50541233, "sha256": "...", "empfangen": 31457280, "teil_groesse": 4194304,
  "stand": "laedt", "schritt": 1, "anteil": 0.62, "text": "Wird in der Kellerwolke abgelegt, 30,0 von 48,2 MB",
  "buch_id": null, "angelegt_am": "2026-11-25T21:00:00Z", "geaendert_am": "..." }
```

`stand`: `wartet`, `laedt`, `angehalten`, `liest`, `angaben`, `regal`, `wissen` (in der Bibliothek, Bedeutung folgt),
`fertig`, `ohne_text` (in der Bibliothek, kein Text gefunden), `da` (gibt es schon, `buch_id` gesetzt), `format` (nicht
möglich), `kaputt` (leer oder unlesbar, nicht eingetragen), `fehler` (mit Grund in `text`, erneut möglich).
`schritt` 0 bis 6: Prüfen, Wolke, Lesen, Angaben, Regal, Wissen, alles fertig.

| Weg | Zweck |
|---|---|
| `GET /api/annahme` | `{eintraege: [...], zaehler: {alle, laeuft, klaeren, da, fertig}}`, neueste zuerst |
| `POST /api/annahme` `{name, groesse, sha256}` | anlegen; antwortet sofort mit `da`, `format` oder `kaputt`, wenn nichts hochzuladen ist |
| `PATCH /api/annahme/{id}` Kopf `Upload-Offset`, Körper roh | nächstes Teil; 409 `{detail, empfangen}` nennt den wahren Stand |
| `GET /api/annahme/{id}` | Stand, sagt wo es weitergeht |
| `POST /api/annahme/{id}/erneut` | Auswertung noch einmal |
| `DELETE /api/annahme/{id}` | Eintrag entfernen, laufenden Upload abbrechen; ein eingetragenes Buch bleibt |
| `POST /api/annahme/ausblenden` | fertige und schon vorhandene ausblenden (bleiben im Verlauf) |
| `GET /api/annahme/eingangsordner` | `{bereit, pfad, dateien: [{name, groesse, stand, text, buch_id}]}`, was im Eingangsordner der Kellerwolke liegt |
| `POST /api/annahme/eingangsordner` | jetzt nachsehen, sonst jede Minute; `{neu}` |
| `GET /api/annahme/ereignisse` | Ereignisstrom, je Änderung `data: {eintraege, zaehler}` |

Der Browser rechnet den sha256 stückweise (npm `hash-wasm`), schickt Teile zu `teil_groesse` nacheinander, höchstens zwei
Dateien zugleich, und setzt nach Verbindungsverlust am Stand des Servers fort. Wer die Seite neu lädt, wählt die Datei
erneut; gleicher sha256 und Name findet den angefangenen Eintrag wieder (POST liefert ihn mit `empfangen`).

## Suche nach Bedeutung

`GET /api/suche/bedeutung?q=&n=20&buch=` liefert
`{verfuegbar, grund, treffer: [{buch_id, titel, autor, seite, gedruckt, auszug, naehe: "sehr nah" | "verwandt", wert}]}`.
Ist der Rechner aus, gilt `verfuegbar: false` mit `grund`; die Suche nach Wörtern geht weiter.

## Verbindungen, Orte, Ablage eines Buchs

- `GET /api/verbindungen` -> `[{kennung, name, stand: "gut" | "warn" | "schlecht", text}]` (kellerwolke, fundus, rechner,
  codeschmiede, leitstelle)
- `GET /api/orte` -> `[{kennung, name, pfad, belegt, frei, stand}]` (bestand, suche, texte, umschlaege, zwischen)
- `GET /api/books/{id}/ablage` -> `{wolke: {pfad, groesse, sha256}, volltext: {seiten, zeichen}, wissen: {stand, text}}`
- `GET /api/config/oberflaeche` -> `{assistent: "https://..."}` Adresse des Assistenten für "Im Assistenten fragen"

## Quellen für Angaben (BF-23)

Alle fremden Quellen fragt der Server über einen gemeinsamen Abruf (`backend/app/quellen/abruf.py`): Vorrat in der Datenbank
(Treffer lange, leere Antworten kürzer, Fehler zwei Minuten), gleiche laufende Anfragen werden eine, je Rechner eine Anfrage
zugleich mit Abstand und Grenze je Minute (Wikimedia zählt über alle Wikis), Rückzug bei 429/503/403 mit Retry-After und
wachsender Pause, Sicherung nach vier Ausfällen hintereinander, Tagesgrenze je Quelle für Hintergrundläufe. Wer wartet, kommt
vor Hintergrundläufen dran. Der Stand je Quelle übersteht einen Neustart.

Kennungen: `google_books` (nur mit `GOOGLE_BOOKS_API_KEY`), `open_library`, `dnb`, `k10plus`, `crossref`, `wikipedia`, `gnd`,
`gutenberg`. In der Oberfläche heißen sie Verzeichnis 1 bis 5, Lexikon, Normdatei, Gutenberg.

| Weg | Zweck |
|---|---|
| `POST /api/metadata/buch/{id}/anreichern?quelle=` | Vorschlag einer Quelle, `alle` (je Feld die beste) oder ohne Angabe die erste mit Treffer; `vorschlag.herkunft` nennt je Feld die Quelle, `vorschlag.fund` den Weg (`isbn`, `doi`, `titel`), `hinweise` Quellen, die gerade nicht antworten. Ohne Treffer `{angereichert: false, grund}` |
| `POST /api/metadata/buch/{id}/uebernehmen` | wie bisher; holt den Umschlag vor dem Schreiben, nur von Rechnern der Quellen; `hinweis`, wenn das Bild fehlt |
| `GET /api/metadata/quellen` | je Quelle der gemerkte Stand `{kennung, name, anbieter, art, aktiv, bereit, stand, wort, grund, anfragen_heute, hintergrund_heute, tagesgrenze, gemerkt}`; fragt keine Quelle |
| `POST /api/metadata/quellen/{kennung}/pruefen` | echte Probe, höchstens einmal in der Minute je Quelle |
| `GET /api/metadata/verbindungsstatus`, `GET /api/gutenberg/status` | wie bisher, aber aus dem Gemerkten |
| `POST /api/authors/{id}/anreichern` | Vorschlag aus Normdatei und Lexikon mit `verweise` (gnd, viaf, isni, orcid) und `herkunft` je Feld |
| `POST /api/authors/{id}/anreichern/uebernehmen` | nimmt auch `verweise`; ein anderer Autor mit derselben Wikidata- oder GND-Kennung wird zusammengelegt |
| `GET /api/authors/{id}` | dazu `verweise: [{art, kennung, adresse}]` |
| `GET /api/authors/scanner/events` | wie bisher; neues Ereignis `ruht` mit `grund`, wenn eine Quelle Pause macht (der Lauf endet dann) |
| `GET /api/books/rescan/status` | dazu `grund`, wenn keine Angaben mehr ergänzt werden (alle Verzeichnisse ruhen) |

## Codestellen ausführen (BF-29)

`GET /api/ausfuehren`, `POST /api/ausfuehren`, `GET /api/ausfuehren/funktionen/php`, `GET /api/books/{id}/codestellen`,
`GET /api/ausfuehren/vorpruefung` mit `.../anhalten` und `.../fortsetzen`: Felder und Bedeutung in [AUSFUEHREN.md](AUSFUEHREN.md).
