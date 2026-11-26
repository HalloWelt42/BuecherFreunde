# Neue Schnittstellen des Neubaus (BF-7 bis BF-10)

Alle Wege brauchen die Anmeldung (`Authorization: Bearer` oder `X-Kellerwolke-Sitzung`). Bilder, Dateien und Ereignisströme lesen sie aus dem Inhalts-Cookie von `POST /api/anmeldung/zugang`; in Adressen steht sie nie.
Fehler kommen als `{"detail": "deutscher Satz"}`, auf allen Wegen (BF-50, `core/fehlerantworten.py`):

- 422 bei ungültiger Eingabe nennt Feld und Grund, mehrere durch Semikolon getrennt, etwa
  `"Titel: darf nicht leer sein; Jahr: höchstens 2027"`. Die Grenzen stehen an einer Stelle (`models/grenzen.py`).
- 404, wenn es das Genannte nicht gibt: auch beim Ändern und Löschen, auch zu einem fehlenden Buch, und für eine Nummer im
  Pfad, die keine sein kann (`"Nicht gefunden"`).
- 409, wenn ein Name schon vergeben ist (Regal, Autor).

## Annahme (eine Auftragsliste für alle Quellen)

Ein Eintrag je Datei, gleich woher sie kommt (`quelle`): `hochladen` (Browser), `eingangsordner` (Kellerwolke), `ordner`
(Einlese-Ordner auf dem Gerät, `POST /api/import/scan`), `extern` (externe Sammlung, `POST /api/import/externes-verzeichnis`),
`gemeinfrei` (`POST /api/gutenberg/import`). Dateien aus Ordnern bleiben, wo sie sind; gemeinfreie Bücher werden beim Lesen
geholt und kommen ins Regal "Gutenberg". Wartende Einträge gehen nach einem Neustart weiter.

```
{ "id": 7, "name": "Buch.epub", "groesse": 50541233, "sha256": "...", "empfangen": 31457280, "teil_groesse": 4194304,
  "stand": "laedt", "schritt": 1, "anteil": 0.62, "text": "Wird in der Kellerwolke abgelegt, 30,0 von 48,2 MB",
  "buch_id": null, "quelle": "hochladen", "angelegt_am": "2026-11-25T21:00:00Z", "geaendert_am": "..." }
```

`stand`: `wartet`, `laedt`, `angehalten`, `liest`, `angaben`, `regal`, `wissen` (in der Bibliothek, Bedeutung folgt),
`fertig`, `ohne_text` (in der Bibliothek, kein Text gefunden), `da` (gibt es schon, `buch_id` gesetzt), `format` (nicht
möglich), `kaputt` (leer oder unlesbar, nicht eingetragen), `fehler` (mit Grund in `text`, erneut möglich).
`schritt` 0 bis 6: Prüfen, Wolke, Lesen, Angaben, Regal, Wissen, alles fertig.

| Weg | Zweck |
|---|---|
| `GET /api/annahme` | `{eintraege: [...], weitere, zaehler: {alle, laeuft, klaeren, da, fertig}, quellen: {<quelle>: {gesamt, laeuft, fertig, da, gescheitert}}}`, neueste zuerst; die Liste hat höchstens 300 Einträge (`weitere` sagt, wie viele darüber hinaus da sind), die Zähler zählen alle sichtbaren |
| `POST /api/annahme` `{name, groesse, sha256}` | anlegen; antwortet sofort mit `da`, `format` oder `kaputt`, wenn nichts hochzuladen ist |
| `PATCH /api/annahme/{id}` Kopf `Upload-Offset`, Körper roh | nächstes Teil; 409 `{detail, empfangen}` nennt den wahren Stand, 413 bei mehr Daten als angesagt |
| `GET /api/annahme/{id}` | Stand, sagt wo es weitergeht |
| `POST /api/annahme/{id}/erneut` | Auswertung noch einmal |
| `DELETE /api/annahme/{id}` | Eintrag entfernen, laufenden Upload abbrechen; ein eingetragenes Buch bleibt |
| `DELETE /api/annahme?quelle=ordner&stand=fertig&stand=da` | viele auf einmal, wie einzeln; nach Quelle, Stand (mehrfach) oder beidem, eins davon muss sein; `{entfernt, ...wie GET}` |
| `POST /api/annahme/ausblenden` | fertige und schon vorhandene ausblenden (bleiben im Verlauf) |
| `GET /api/annahme/eingangsordner` | `{bereit, ort, pfad, dateien: [{name, groesse, stand, text, buch_id}]}`, was im Eingangsordner liegt; `ort`: `kellerwolke` oder `geraet` |
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
- `GET /api/books/{id}/file` das Original, zum Ansehen im Browser inline; `?herunterladen=true` als Anhang
- `GET /api/books/{id}/loeschfolgen` -> `{titel, autor, notizen, markierungen, etiketten, lesestand, vorlesestelle, regale,
  datei: {pfad, groesse, papierkorb} | null, abschnitte}` was beim Löschen verloren geht (BF-60); die Sätze bildet die Oberfläche
- `DELETE /api/books/{id}` löscht das Buch mit allem, was daran hängt; die Datei geht in den Papierkorb der Kellerwolke (dort
  zurückzuholen), liegt sie nur auf dem Gerät, ist sie fort. Kommt sie nicht in den Papierkorb: 502, das Buch bleibt unverändert
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

## Gestaltete Deckblätter (BF-59)

Bücher mit schlichtem Umschlag (fast weiß, ohne Farbe, oft die Titelseite eines PDFs) bekommen in der Oberfläche ein
gestaltetes Deckblatt: Bücher nach Gattung, Dokumente, Hefte, Kataloge und Broschüren nach ihrer Art. Die gespeicherte
Titelseite bleibt und ist je Buch wählbar.

- Arten (`typ`, `GET /api/collections/typen`): leer ist ein Buch, dazu `dokument` (Handbuch, Arbeit, Skript oder Beleg),
  `heft`, `katalog`, `broschuere`.
- Gattungen (`gattung`, `GET /api/collections/gattungen` -> `[{id, name}]`, feste Reihenfolge): `krimi`, `thriller`,
  `historisch`, `fantasy`, `liebesroman`, `roman`, `klassiker`, `sachbuch`, `ratgeber`, `informatik`, `mathematik`,
  `fachbuch`, `wirtschaft`; leer: keine. Nur bei Büchern sinnvoll.

Alle Antworten mit Büchern (`GET /api/books`, `GET /api/books/{id}`, `.../recently-read`, `.../aehnliche`) tragen dazu:

| Feld | Bedeutung |
|---|---|
| `gattung` | eine der Gattungen oder leer |
| `umschlag_wahl` | Wahl des Nutzers: leer (automatisch), `gestaltet`, `titelseite` |
| `umschlag_schlicht` | Befund der Umschlagprüfung; `false`, solange nicht geprüft |
| `umschlag` | was gezeigt wird, `gestaltet` oder `titelseite`: `umschlag_wahl`, wenn gesetzt, sonst `gestaltet` bei schlichtem Umschlag, sonst `titelseite` |

`PATCH /api/books/{id}` nimmt zusätzlich `gattung` (geprüft wie `typ`, 422 `"Gattung: erlaubt ist leer oder krimi, ..."`)
und `umschlag_wahl` (nur `""`, `"gestaltet"`, `"titelseite"`). Wer `typ` oder `gattung` setzt (auch `typ_setzen` in
`POST /api/books/bulk`), hat von Hand eingeordnet: die KI fasst das Buch nie wieder an. `umschlag_wahl` ist eine Wahl der
Darstellung und zählt nicht als Bearbeitung der Angaben (setzt weder `manuell_bearbeitet` noch `updated_at`).

Zwei Läufe im Hintergrund, gestartet mit der App:

- Umschläge prüfen (`services/umschlagpruefung.py`): beim Start und dann alle `UMSCHLAEGE_PRUEFEN_TAKT_S` (600) Sekunden jedes
  Buch, dessen Befund fehlt oder zu einem älteren Umschlag gehört (Spalte `umschlag_geprueft` gegen den Stand des Umschlags).
  Schlicht heißt: auf 60 x 90 verkleinert haben mindestens 85 % der Bildpunkte eine Helligkeit über 230 und die mittlere
  Sättigung liegt unter 0,08 (`services/deckblatt.py`). Ohne Umschlagdatei gilt ein Buch als schlicht.
- Einordnen mit der lokalen KI (`services/einordnung.py`): für schlichte Bücher, die noch niemand eingeordnet hat und die
  noch keine Art haben (eine schon gesetzte Art stammt vom Nutzer und bleibt), schlägt die KI über die Leitstelle Art und
  Gattung vor (aus Titel, Autor, Verlag, Jahr, ISBN, Format und dem Anfang des Volltexts),
  ein Buch je Anfrage, mit `EINORDNEN_ABSTAND_S` (20) Sekunden Abstand, abschaltbar mit `EINORDNEN_AN` (true). Es sieht
  nach jeder Umschlagprüfung mit schlichten Umschlägen nach, sonst alle `EINORDNEN_TAKT_S` (600) Sekunden. Antwortet die KI
  zu einem Buch nichts Brauchbares, bleibt es offen und kommt in einer späteren Runde wieder dran; lehnt die Leitstelle ab,
  hält das Einordnen an, bis es fortgesetzt wird.

| Weg | Zweck |
|---|---|
| `GET /api/einordnung/stand` | `{an, bereit, laeuft, angehalten, grund, offen, erledigt}`: `bereit` heißt eingeschaltet und Leitstelle eingetragen, `offen` schlichte Bücher ohne Einordnung und ohne Art, `erledigt` von der KI eingeordnete, `grund` warum angehalten oder in der letzten Runde ein Buch offen blieb |
| `POST /api/einordnung/fortsetzen` | nach einer Ablehnung der Leitstelle weiter einordnen; antwortet mit dem Stand |

Spalten in `books`: `gattung`, `umschlag_wahl`, `umschlag_schlicht` (NULL noch nicht geprüft, 0, 1), `umschlag_geprueft`
(Stand des geprüften Umschlags), `einordnung` (leer offen, `ki`, `hand`).

- Wortsuche (`GET /api/search`), Suche nach Bedeutung und Autorenseite (`books`) tragen je Buch `deckblatt` bzw. dieselben Felder:
  `{typ, gattung, umschlag_wahl, umschlag_schlicht, umschlag, cover_path, file_format, year}` (services/deckblattangaben.py), damit
  überall dasselbe Deckblatt erscheint wie in der Bücherliste.

## Sammlungen: als ein Eintrag, Zuordnen, Finden (BF-66, BF-67)

Ein Buch gehört höchstens zu einer Sammlung (`sammlung_id`), seine Bandnummer (`band_nummer`, Text) gilt nur in ihr. Regale
sind `categories` mit `book_categories`; "Ungeordnet" (slug `ungeordnet`) zählt nie als Regal.

### Große Sammlungen als ein Eintrag

Einstellung `sammlung_als_eintrag_ab` in `app_settings`, Vorgabe 8, erlaubt 2 bis 1000 (`models/grenzen.py`).

| Weg | Zweck |
|---|---|
| `GET /api/collections/einstellungen` | `{als_eintrag_ab}` |
| `PUT /api/collections/einstellungen` `{als_eintrag_ab}` | setzen; außerhalb von 2 bis 1000: 422 |

`GET /api/books?zusammenfassen=true` (mit jedem Filter): die Bücher einer Sammlung, von der unter dem Filter mindestens
`als_eintrag_ab` Bücher dabei sind, erscheinen als ein Eintrag. Ohne `zusammenfassen` bleibt die Antwort wie bisher, die
neuen Felder sind dann `null`.

| Feld | Bedeutung |
|---|---|
| `eintraege` | die Seite in Anzeigereihenfolge: `{art: "buch", buch: <wie in buecher>}` oder `{art: "sammlung", sammlung: {id, name, anzahl, autor, umschlaege}}` |
| `sammlung.anzahl` | ihre Bücher unter dem Filter |
| `sammlung.autor` | ihr häufigster Autor unter dem Filter (ein leerer nur, wenn keiner dasteht) |
| `sammlung.umschlaege` | bis zu 3 Bücher wie in `buecher`, die ersten nach Band, für den Stapel |
| `buecher` | nur die einzeln gezeigten Bücher der Seite |
| `gesamt` | alle Bücher unter dem Filter, auch die zusammengefassten |
| `gesamt_eintraege` | Einträge unter dem Filter; danach richten sich Blättern und `seiten_gesamt` |
| `in_sammlungen` | Bücher in zusammengefassten Sammlungen |
| `sammlungen_zusammengefasst` | deren Zahl |

Ein Sammlungseintrag sortiert nach Titel unter seinem Namen, nach Datum unter seinem neuesten Buch, nach Autor unter seinem
häufigsten Autor, sonst unter seinem ersten Buch in der gewählten Ordnung; bei Gleichstand nach Name oder Titel.

### Bandfolge und Filter

- `sortierung=band`: natürliche Folge von `band_nummer` (Nummern der Zahl nach, Bände ohne Zahl dahinter, leere immer zuletzt),
  dann Titel. `richtung=desc` dreht nur die Nummern. Dieselbe Folge gilt für `books` in `GET /api/collections/{id}`.
- `ohne_sammlung=true`: nur Bücher ohne Sammlung (`false`: nur die in einer).
- `nicht_kategorie=<id>`: nur Bücher, die nicht in diesem Regal stehen.

### Zuordnen

`POST /api/books/bulk` `{book_ids, aktion, wert}`, Antwort `{betroffen, aktion}`:

| aktion | wert | Wirkung |
|---|---|---|
| `sammlung_zuweisen` | Sammlung | in die Sammlung; Bücher ohne Nummer in ihr kommen hinten an (bisher höchste Nummer + 1, in der Reihenfolge von `book_ids`), wer dort schon eine Nummer hat, bleibt; `betroffen` zählt geänderte |
| `sammlung_entfernen` | - | `sammlung_id` leer, `band_nummer` leer; `betroffen` zählt die, die in einer waren |
| `kategorie_zuweisen` | Regal | wie bisher |
| `kategorie_entfernen` | Regal | aus diesem Regal nehmen; fehlt `wert`: 400, unbekanntes Regal: 404 |

`PUT /api/collections/{id}/reihenfolge` `{book_ids: [...]}` setzt `band_nummer` 1 bis n in dieser Reihenfolge; nicht genannte
Bücher der Sammlung folgen in ihrer bisherigen Bandfolge (keine Nummer doppelt). Antwort wie `GET /api/collections/{id}`.
Gehört ein Buch nicht zur Sammlung: 400 `"Das Buch 12 gehört nicht zu dieser Sammlung"`; doppelt genannt: 400
`"Ein Buch steht mehr als einmal in der Reihenfolge"`.

### Sammlungen finden

Ein Lauf im Hintergrund (`services/sammlungsfinder.py`), nur auf Anstoß:

1. Regeln: aus dem Titel, sonst aus dem Dateinamen (ohne Endung, ohne Stücke, die nur der Autor sind) Reihe und Band lesen:
   `Reihe 01 - Titel`, `Reihe - 12 - Titel`, `Reihe Band 3 - Titel` (auch Bd., Teil, Folge, Buch, Vol., Nr., #),
   `Reihe 3. Titel`, `Titel (Reihe 4)`, `Titel (Reihe, Band 4)`, `Reihe, Band 2`. Zusammen gehört, was nach normiertem
   Reihennamen und normiertem ersten Autor gleich ist ("Nachname, Vorname" gleich "Vorname Nachname"; Groß und Klein,
   Umlaute, Akzente, Bindestriche und Satzzeichen gleich). Bücher in einer Sammlung zählen nicht. Ein Vorschlag braucht
   `SAMMLUNG_VORSCHLAG_AB` (3) Bücher mit mindestens zwei verschiedenen Bänden.
2. Lokale KI über die Leitstelle, nur wenn eingetragen: je Autor mit mehreren erkannten Reihen, welche Namen dieselbe Reihe
   sind und wie sie richtig heißt (auch kleine Funde, die erst zusammen reichen); danach je Kandidat, ob die Bücher wirklich
   eine Reihe bilden (verneint: kein Vorschlag). Antworten per JSON-Schema, Priorität Hintergrund, zwischen zwei Anfragen
   `SAMMLUNGEN_FINDEN_ABSTAND_S` (5) Sekunden. Ohne Leitstelle, bei einer unbrauchbaren Antwort oder wenn die Leitstelle nicht
   kann, bleiben die Regelfunde, `ki` sagt, dass die KI nicht geprüft hat. Kann sie nicht (weg, abgelehnt), geht in diesem Lauf
   keine weitere Anfrage hinaus.
3. Ein Lauf ersetzt die offenen Vorschläge. Angelegte und verworfene kommen nie wieder: kein späterer Lauf schlägt eine Reihe
   vor, deren Schlüssel (Reihe und Autor) zu einem angelegten oder verworfenen Vorschlag gehört.

| Weg | Zweck |
|---|---|
| `GET /api/collections/vorschlaege` | offene Vorschläge, die größten zuerst: `[{id, name, autor, anzahl, wege: [str], ki, ki_geprueft, buecher: [<wie in buecher> + band]}]`; nur Bücher, die noch in keiner Sammlung sind, nach Band |
| `POST /api/collections/vorschlaege/suchen` | startet den Lauf (läuft schon einer, bleibt es bei ihm), Antwort wie `.../stand` |
| `GET /api/collections/vorschlaege/stand` | `{laeuft, schritt, gefunden, grund}`: `schritt` was gerade geschieht, `gefunden` die offenen Vorschläge (im Lauf die bisher gefundenen), `grund` warum die KI nicht geprüft hat |
| `POST /api/collections/vorschlaege/{id}/anlegen` `{name?, book_ids?}` | legt die Sammlung an (ohne Angaben: Name und alle Bücher des Vorschlags), setzt `sammlung_id` und die erkannte `band_nummer`, Vorschlag `angelegt`; Antwort wie `GET /api/collections/{id}`. Ein Buch außerhalb des Vorschlags oder keins: 400 |
| `POST /api/collections/vorschlaege/{id}/verwerfen` | `{id, stand: "verworfen"}` |

Beide Entscheidungen gehen nur bei offenen Vorschlägen: sonst 409 `"Der Vorschlag ist schon angelegt"` oder `"... verworfen"`,
unbekannt 404. `wege` sind kurze Sätze wie `"Reihe und Band im Titel bei 3 Büchern"`, `"Name der Reihe in 2 Schreibweisen"`,
`"Die KI führt Sternenf und Sternenfahrer zusammen"`; `ki` ist der Satz der KI oder etwa
`"Die KI hat nicht geprüft: Keine Leitstelle eingetragen"`; `ki_geprueft` sagt, ob die KI die Reihe bestätigt hat.

Tabellen: `sammlung_vorschlag` (`schluessel` je Zeile ein Regelfund `reihe|autor` normiert, `name`, `autor`, `wege` als JSON,
`ki`, `ki_geprueft`, `stand` offen/angelegt/verworfen, `sammlung_id`, `gefunden_am`, `geaendert_am`) und
`sammlung_vorschlag_buch` (`vorschlag_id`, `buch_id`, `band`).
