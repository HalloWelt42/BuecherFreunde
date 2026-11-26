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
  "buch_id": null, "quelle": "hochladen", "angelegt_am": "2026-11-25T21:00:00Z", "geaendert_am": "...",
  "vorschau": "3f2c...-uuid", "teil_von": null, "material_fuer": null }
```

`stand`: `wartet`, `laedt`, `angehalten`, `liest`, `angaben`, `entpacken` (eine ZIP wird ausgepackt), `bestaetigen` (wartet
vor dem Regal auf die Bestätigung, BF-80), `regal`, `wissen` (in der Bibliothek, Bedeutung folgt), `fertig`, `ohne_text` (in
der Bibliothek, kein Text gefunden), `da` (gibt es schon, `buch_id` gesetzt; auch weggelassen), `entpackt` (eine ZIP, deren
Teile eigene Aufnahmen sind; sie bleibt im Eingang), `format` (nicht möglich oder nicht übernommen, Grund in `text`),
`kaputt` (leer oder unlesbar, nicht eingetragen), `fehler` (mit Grund in `text`, erneut möglich), `verworfen` (BF-80, bleibt
im Verlauf). `schritt` 0 bis 6: Prüfen, Wolke, Lesen, Angaben, Regal, Wissen, alles fertig; wer wartet, steht bei 4 (Regal).
`vorschau`: die Vorschau, zu der die Aufnahme gehört (leer: ohne Halt); `teil_von`: die Aufnahme der ZIP, aus der sie
stammt; `material_fuer`: Begleitmaterial zu diesem Buch (BF-81).

| Weg | Zweck |
|---|---|
| `GET /api/annahme` | `{eintraege: [...], weitere, zaehler: {alle, laeuft, bestaetigen, klaeren, da, fertig}, quellen: {<quelle>: {gesamt, laeuft, bestaetigen, fertig, da, gescheitert}}, vorschauen: [Vorschau kurz]}`, neueste zuerst; die Liste hat höchstens 300 Einträge (`weitere` sagt, wie viele darüber hinaus da sind), die Zähler zählen alle sichtbaren; `vorschauen` sind die offenen ("Zum Bestätigen") |
| `POST /api/annahme` `{name, groesse, sha256, anreichern?, vorschau?}` | anlegen; antwortet sofort mit `da`, `format` oder `kaputt`, wenn nichts hochzuladen ist. PDF, EPUB, MOBI, TXT, MD und ZIP. Jede Datei aus dem Browser gehört zu einer Vorschau: `vorschau` nennt eine aus `POST /api/annahme/vorschau` (mehrere Dateien, eine Lücke), ohne bekommt jede Datei ihre eigene; unbekannt 404, erledigt 409 |
| `PATCH /api/annahme/{id}` Kopf `Upload-Offset`, Körper roh | nächstes Teil; 409 `{detail, empfangen}` nennt den wahren Stand, 413 bei mehr Daten als angesagt |
| `GET /api/annahme/{id}` | Stand, sagt wo es weitergeht |
| `POST /api/annahme/{id}/erneut` | Auswertung noch einmal |
| `DELETE /api/annahme/{id}` | Eintrag entfernen, laufenden Upload abbrechen; ein eingetragenes Buch bleibt |
| `DELETE /api/annahme?quelle=ordner&stand=fertig&stand=da` | viele auf einmal, wie einzeln; nach Quelle, Stand (mehrfach) oder beidem, eins davon muss sein; `{entfernt, ...wie GET}` |
| `POST /api/annahme/ausblenden` | fertige und schon vorhandene ausblenden (bleiben im Verlauf) |
| `GET /api/annahme/eingangsordner` | `{bereit, ort, pfad, dateien: [{name, groesse, stand, text, buch_id}]}`, was im Eingangsordner liegt; `ort`: `kellerwolke` oder `geraet` |
| `POST /api/annahme/eingangsordner` | jetzt nachsehen, sonst jede Minute; `{neu}` |
| `GET /api/annahme/ereignisse` | Ereignisstrom, je Änderung `data: {eintraege, zaehler, quellen, vorschauen}` |
| `GET /api/annahme/{id}/umschlag` | der Umschlag, den das Lesen fand (für die Vorschau, vor dem Übernehmen), über das Inhalts-Cookie; 404 ohne |

Der Browser rechnet den sha256 stückweise (npm `hash-wasm`), schickt Teile zu `teil_groesse` nacheinander, höchstens zwei
Dateien zugleich, und setzt nach Verbindungsverlust am Stand des Servers fort. Wer die Seite neu lädt, wählt die Datei
erneut; gleicher sha256 und Name findet den angefangenen Eintrag wieder (POST liefert ihn mit `empfangen`).

Ohne Kellerwolke liegt, was hochgeladen oder ausgepackt ist, im Eingang auf dem Gerät (`<STORAGE_DIR>/eingang/<id>/`,
dauerhaft, weil eine Vorschau über einen Neustart wartet); mit Kellerwolke in `Apps/BücherFreunde/Eingang` (Teile einer ZIP
in `Eingang/<id> <Name der ZIP>/`).

### Hochladen mit Vorschau (BF-80)

Plan und Entscheidungen in [HOCHLADEN.md](HOCHLADEN.md); gebaut in `backend/app/annahme/` (`vorschau.py`, `zuordnen.py`,
`ki_vorschau.py`, `entpacken.py`, `uebernehmen.py`, `verwerfen.py`, `einstellungen.py`, Formen in `modelle.py`).

**Halt "Zum Bestätigen"**: vor der Station Regal wartet jede Aufnahme, die zu einer Vorschau gehört (`stand` `bestaetigen`,
`schritt` 4), bis sie übernommen oder verworfen wird, auch über Tage und nach einem Neustart. Hochladen im Browser hält
immer; der Eingangsordner und Ordner auf dem Gerät (Einlese-Ordner und externe Sammlung) nur, wenn es in den Einstellungen
eingeschaltet ist, dann in der offenen Vorschau ihrer Quelle ("Eingangsordner", "Ordner auf dem Gerät", "Externe Sammlung").
Gemeinfreie Bücher halten nie. Beim Halt ist die Datei schon gelesen (Angaben, Text, Umschlag); im Regal, in der Suche und in
den Zählern steht nichts. Eine ZIP nimmt nur das Hochladen im Browser, im Eingangsordner und in Ordnern bleibt sie `format`.

**ZIP**: auf dem Server ausgepackt, Eintrag für Eintrag, jeder eine eigene Aufnahme derselben Vorschau (`teil_von`); nach
einer Unterbrechung geht es beim angefangenen Eintrag weiter. Die ZIP selbst steht danach auf `entpackt` und bleibt im
Eingang. Grenzen aus den Einstellungen (`zip`): mehr Einträge als `dateien` oder ausgepackt mehr als `gesamt_mb` macht die
ganze ZIP `kaputt`, mit Grund. Ein Eintrag über `datei_mb`, tiefer als `tiefe` Ordner, stärker gepackt als `verhaeltnis` zu 1
(ab 1 MB ausgepackt), verschlüsselt, eine Verknüpfung, eine Begleitdatei des Systems (`__MACOSX`, `.DS_Store`) oder mit einem
Pfad, der aus der ZIP herausführt (`..`, absolut), wird nicht ausgepackt und steht mit Grund da (`format`); wird er beim
Auspacken größer, als die ZIP sagt, bricht er ab. Pfade aus der ZIP sind nur Hinweise (`ordner` der Zeile), nie ein Pfad auf
dem Gerät. Eingeteilt wird so: lesbare Buchformate sind Werke; eine andere Datei, deren Name mit dem Stamm eines Werks im selben
Ordner beginnt und dann einen Trenner hat (` - `, `_`, `.`, `(`, `[`), wird sein Begleitmaterial, ebenso ein Buchformat, dessen
Rest keinen Band nennt ("Holz - Schaltpläne.pdf" zu "Holz.pdf"; "Holz - Band 2.pdf" ist ein eigenes Werk); der Rest wird nicht
übernommen ("Bild ohne Buch gleichen Namens") und lässt sich als Material wählen.

**Vorschau kurz** (in `GET /api/annahme` und `GET /api/annahme/vorschau`):

```
{ "id": "uuid", "name": "Werkstatt-Ablage.zip", "quelle": "hochladen", "stand": "offen", "dateien": 14, "warten": 13,
  "laeuft": 0, "ki": 1, "groesse": 43827200, "hinweis": "", "angelegt_am": "...", "geaendert_am": "..." }
```

`stand`: `offen`, `uebernommen`, `verworfen`. `dateien` ohne die ZIP selbst; `warten` stehen auf `bestaetigen`; `laeuft` werden
noch hochgeladen, gelesen oder ausgepackt; `ki` prüft die KI noch; `hinweis` nach dem Übernehmen, etwa "3 Dateien blieben im
Eingang" (aus Ordnern auf dem Gerät "im Ordner"). Ganz (`GET /api/annahme/vorschau/{id}`) dazu `vorgabe` (`{sammlung_id, band,
sprache}`), `zaehler` und `zeilen`:

```
zaehler: { gesamt, uebernehmen, buecher, besonderes, material, formate, weglassen, nicht, offen, laeuft, ki }
Zeile:   { id, name, groesse, ordner, stand, text, rolle, buch_id, umschlag, ki, material,
           gelesen: { titel, autor, isbn, verlag, jahr, sprache, beschreibung, seiten, umschlag, umschlag_schlicht,
                      alter_von, alter_bis, alter_quelle } | null,
           felder:  Zuordnung | null,
           ablage:  { ort: "kellerwolke" | "geraet" | "bleibt", ordner, name } | null }
```

`rolle`: `buch` (ein Werk, auch Besonderes und weiteres Format), `material`, `zip` (die ZIP selbst), `doppel` (weggelassen,
auch eine Datei, die es schon gibt), `rest` (nicht übernommen, Grund in `felder.nicht` oder `text`). `ki`: `offen` (die KI prüft
noch), `fertig`, leer (nicht gefragt). `material`: so viele Dateien dieser Vorschau kommen als Begleitmaterial zu diesem Werk
("+2"). `umschlag`: es gibt ein Bild unter `GET /api/annahme/{id}/umschlag`. `ablage`: wohin die
Datei beim Übernehmen kommt (Kellerwolke `Apps/BücherFreunde/Bücher/<Fach>`, neben dem Original bei Format und Material, auf dem
Gerät der Speicher oder der Buchordner unter `Material`); bei `bleibt` der Ort, an dem sie liegen bleibt.

**Zuordnung** (`felder`), je Feld `{wert, herkunft, grund}`; `herkunft`: `regel`, `ki`, `ordner` (Ordnername in der ZIP),
`datei` (Name oder Inhalt der Datei), `luecke` (Vorgabe einer Lücke, BF-75), `bestand` (das vorhandene Buch), `nutzer`; leer:
noch kein Vorschlag.

| Feld | Wert |
|---|---|
| `art` | `buch` (books.typ leer), `dokument`, `heft`, `katalog`, `broschuere`, `anleitung` (Besonderes) oder `material`; leer: offen, die App ordnet nach dem Übernehmen ein wie jedes Werk |
| `gattung` | nur von der KI, wo das gezeichnete Deckblatt sie braucht; nicht zu setzen |
| `kategorien` | Nummern von Kategorien des Katalogs |
| `etiketten` | Namen; beim Übernehmen Etiketten des Profils, das übernimmt |
| `sammlung`, `band` | Nummer einer Sammlung, Band als Text |
| `sprache` | Kürzel, etwa `de` |
| `doppel` | `{art: neu, gleich oder format, wahl: neu, weglassen, format oder eigenes, herkunft, grund}`; `grund` etwa "zu Sturmflut, EPUB" |
| `ziel` | `{buch_id, aufnahme, titel}` oder null: zu welchem Buch die Datei als weiteres Format oder Material gehört, eins im Bestand oder eine andere Aufnahme dieser Vorschau |
| `nicht` | warum nicht übernommen; leer: wird übernommen |
| `hinweise` | kurze Sätze, etwa "Die Datei ist englisch, die Lücke deutsch" oder "Im Bestand gibt es X schon als PDF, aus einer anderen Datei" |
| `bestaetigt`, `von_profil` | übernommen, von welchem Profil |

Vorschläge der Regeln, sofort nach dem Lesen: Art nach den festen Regeln (`services/artregeln.py`, wie im Bestand, mit dem Befund
des Umschlags); Kategorie aus einem Ordnernamen der ZIP, der wie eine Kategorie heißt, sonst die beste Regel des Katalogs für
die Art; Sammlung aus der Lücke, einem Ordnernamen wie eine Sammlung oder Reihe und Band im Titel (`regel`) oder Dateinamen
(`datei`), der Band ebenso; Ordnernamen, die weder Kategorie noch Sammlung sind, werden Etiketten; Sprache aus der Datei, sonst
aus der Lücke. Doppel: gibt es die Prüfsumme schon (als Buch oder weiteres Format), antwortet `POST` mit `da`, die Zeile ist ein
Doppel und wird weggelassen; dieselbe Datei noch einmal in derselben Vorschau ist `gleich` und `weglassen`. Dasselbe Buch in
einem anderen Format (gleiche ISBN, sonst gleicher Titel und erster Autor; nur Bücher, die niemand privat hat, und nur, wenn das
Buch das Format noch nicht hat) ist `format`, vorgewählt `format`, mit dem Buch als Ziel; die übrigen Felder zeigen es
(`bestand`). Derselbe Name in einem anderen Format im selben Ordner derselben Vorschau ist `format` zu der früheren Aufnahme
(`datei`).

KI im Hintergrund (`ki_vorschau.py`): was nach den Regeln offen ist (Art, sonst Kategorie), über die Leitstelle mit Vorrang
Hintergrund, gebündelt wie beim Einordnen (bis zu `EINORDNEN_JE_ANFRAGE` Dateien je Anfrage, die Kategorie je Art eine Anfrage,
dazwischen `EINORDNEN_ABSTAND_S`). Sie setzt nur Felder ohne Vorschlag oder mit einem früheren der KI, nie, was der Nutzer, eine
Regel, ein Ordner, die Datei, eine Lücke oder der Bestand vorschlägt. Übernehmen geht jederzeit, auch bevor die KI fertig ist.
Nach einem Neustart geht sie mit dem Offenen weiter.

| Weg | Zweck |
|---|---|
| `GET /api/annahme/vorschau` | die offenen Vorschauen, kurz, die neueste zuerst |
| `POST /api/annahme/vorschau` `{name, vorgabe?: {sammlung_id, band, sprache}}` | eine leere Vorschau für mehrere Dateien oder eine Lücke; Antwort wie `GET` einer; unbekannte Sammlung 422 |
| `GET /api/annahme/vorschau/{id}` | die ganze Vorschau; Aufnahmen zu Büchern, die das Profil nicht sieht, fehlen |
| `PATCH /api/annahme/vorschau/{id}` `{ids, felder: {art?, kategorien?, etiketten?, sammlung?, band?, sprache?, doppel?, ziel?}}` | Felder einer oder mehrerer Dateien setzen, Herkunft danach `nutzer`; `ziel` ist `{buch_id}` oder `{aufnahme}`, `sammlung` und `ziel` leert null. Geht eine nicht, ändert sich keine: 422 mit Feld und Grund (unbekannte Kategorie oder Sammlung, Material oder Format ohne Ziel, kein Buchformat, dieselbe Datei nur weglassen), 404 für eine fremde Aufnahme, 409 wenn sie nicht mehr wartet. Antwort die ganze Vorschau |
| `POST /api/annahme/vorschau/{id}/uebernehmen` `{ids?}` | übernimmt die genannten (ohne: alle wartenden): Werke ins Regal mit ihren Feldern, weitere Formate und Material zum Buch; Weggelassenes und Nicht-Übernommenes bleibt im Eingang (`da`, `format`, Grund in `text`). Gehört eine Datei zu einer anderen Aufnahme, die weder genannt noch im Regal ist: 422. Wird eine noch hochgeladen oder gelesen, geht sie danach ohne Halt weiter. Antwort `{weiter, vorschau}`; ist nichts mehr offen, ist die Vorschau `uebernommen`, mit `hinweis` |
| `GET /api/annahme/vorschau/{id}/folgen?ids=` | vor dem Verwerfen: `{vorschau, name, dateien: [{id, name, ordner, groesse, wirkung, pfad}], papierkorb, endgueltig, bleibt, stand}`; `wirkung`: `papierkorb` (Kellerwolke, dort zurückzuholen), `endgueltig` (auf dem Gerät, auch im Eingangsordner), `bleibt` (Einlese-Ordner und externe Sammlung gehören der App nicht), `nichts` (es gibt keine Datei) |
| `DELETE /api/annahme/vorschau/{id}?stand=&ids=` | verwerfen, nur mit `stand` aus den Folgen (422 ohne, 409 wenn sich seither etwas geändert hat); ins Regal kommt nichts, die Aufnahmen bleiben im Verlauf (`verworfen`), was die Vorschau zur Prüfsumme abgelegt hat, geht mit. Kommt eine Datei nicht in den Papierkorb: 502, was schon verworfen ist, bleibt es. Antwort `{verworfen, vorschau}` |

Beim Übernehmen schreibt die Zuordnung an das neue Buch: die Art mit `einordnung` wie beim Einordnen (`nutzer` wird `hand`,
`regel` mit Grund, `ki` mit Gattung; offen bleibt offen), Kategorien (`book_categories.quelle` `katalog-regel`, `katalog-ki`,
sonst `manuell`), Sammlung und Band (ohne Band hinten an), die Sprache nur, wenn der Nutzer oder die Lücke sie setzt, und die
Etiketten für das Profil, das übernimmt.

**Einstellungen** (Fähigkeit `einstellungen`, sonst 403):

| Weg | Zweck |
|---|---|
| `GET /api/annahme/einstellungen` | `{bestaetigen: {hochladen: true, eingangsordner, ordner}, zip: {dateien, datei_mb, gesamt_mb, tiefe, verhaeltnis}}` |
| `PUT /api/annahme/einstellungen` | dieselbe Form; `hochladen` ist fest `true` (sonst 422); Grenzen: 1 bis 100000 Dateien, 1 bis 1048576 MB, Tiefe 1 bis 64, Verhältnis 1 bis 10000 |

`ordner` gilt für Einlese-Ordner und externe Sammlung. Vorgaben der Einrichtung, solange nichts gemerkt ist:
`BESTAETIGEN_EINGANGSORDNER` (false), `BESTAETIGEN_ORDNER` (false), `ZIP_DATEIEN_HOECHSTENS` (2000), `ZIP_DATEI_MB_HOECHSTENS`
(2048), `ZIP_GESAMT_MB_HOECHSTENS` (16384), `ZIP_TIEFE_HOECHSTENS` (16), `ZIP_VERHAELTNIS_HOECHSTENS` (200).

### Dateien je Buch (BF-80)

Ein Buch kann mehrere Formate haben: die Dateien stehen in `buch_datei` (`id` UUID, `buch_id`, `hash`, `format`, `name`,
`groesse`, `haupt`), je Buch höchstens eine je Format. Das Original (`haupt`) ist `books.hash`, aus ihm stammen Text, Umschlag
und Angaben; seine Zeile hält die Datenbank selbst gleich (Trigger). Beim ersten Start mit dieser Fassung bekam jedes vorhandene
Buch genau seine eine Datei, nach einer Sicherung neben der Datenbank (`<name>.vor-dateien-<Zeit>.db`); ein zweiter Lauf ändert
nichts (`ablage/formate_umbau.py`). In der Kellerwolke liegt ein weiteres Format als Begleiter neben dem Original (Rolle
`format_<endung>`, Name wie das Original mit der anderen Endung) und zieht mit ihm um, auch in den Papierkorb; ohne Kellerwolke
liegt es im Speicher je Prüfsumme.

- `GET /api/books/{id}` trägt `dateien: [{id, format, name, groesse, haupt}]` (das Original zuerst) und `material` (Anzahl);
  die Bücherliste trägt `material`.
- `GET /api/books/{id}/file?format=epub` liest ein bestimmtes Format, ohne `format` das Original; ein Format, das das Buch
  nicht hat: 404.
- `GET /api/books/{id}/loeschfolgen` dazu `formate` und `material`, je `[{pfad, groesse, papierkorb}]`; `DELETE /api/books/{id}`
  nimmt beides mit (in der Kellerwolke mit dem Original in den Papierkorb, auf dem Gerät fort).

## Begleitmaterial (BF-81)

Plan und Entscheidungen in [BEGLEITMATERIAL.md](BEGLEITMATERIAL.md); gebaut in `backend/app/material/` (`dienst.py` führt die
Liste, `ablage.py` legt ab, `textlauf.py` bringt Text in die Suche, `suche.py` sucht, `erkennen.py` gleicht ab, `arten.json` kennt
die Arten), Wege in `backend/app/api/material.py`. Eine Tabelle `buch_material` (`id` UUID, `buch_id`, `name`, `art`, `groesse`,
`sha256`, `ort`, `knoten`, `rolle`, `pfad`, `herkunft`, `text_stand`, `text_seiten`, `angelegt_am`); Buchseite, Suche und Folgen
lesen nur sie. Der Auszug (Umschlag, Volltext, Angaben) bleibt ein eigener Begleiter und ist kein Material.

**Ablage** hinter einer Schnittstelle mit zwei Umsetzungen, nach dem Ort des Originals: in der Kellerwolke ist jede Datei
Begleiter des Originals mit eigener Rolle `material_<kennung>` (nur Buchstaben) und dem Zusatz `.material.<name>` im Namen,
etwa `Sensoren - Wendt, Lutz [4790].material.schaltplaene.pdf`; sie liegt neben dem Original und zieht beim Verschieben,
Umbenennen und in den Papierkorb mit. Rolle und Zusatz erlaubt die Kellerwolke nur aus Kleinbuchstaben, Ziffern, `_` und `-`
(Umlaute ausgeschrieben, höchstens 20 Zeichen je Teil); der Name in der App bleibt, wie er ist. Ohne Kellerwolke (oder solange
das Original nur auf dem Gerät liegt) liegt es im Buchordner unter `Material/`. Vorhandenes Material bleibt an dem Ort, den
seine Zeile nennt.

```
Material: { id, buch_id, name, art, art_name, zeichen, groesse, ort: "kellerwolke" | "geraet", pfad, herkunft, oeffnen, lesbar,
            text_stand, text_seiten, angelegt_am }
```

`art` nach der Endung (`material/arten.json`): `pdf`, `epub`, `text`, `markdown`, `bild`, `ton`, `video`, `tabelle`, `zip`, `archiv`,
`dokument`, `folien`, `code`, `mobi`, sonst `datei`; `art_name` zum Anzeigen (PDF, Bild, Tabelle ...), `zeichen` aus Font Awesome.
`oeffnen`: PDF, EPUB, Bilder, Text und Markdown öffnen in der App, alles andere lädt herunter. `lesbar`: PDF, EPUB, Text und
Markdown kommen in die Suche. `herkunft`: `buchseite`, `hochladen` (aus einer Vorschau, BF-80), `erkannt` (aus dem Abgleich).
`text_stand`: `offen` (wird gelesen), `fertig`, `ohne` (nicht lesbar oder ohne Text), `fehler`.

**Rechte**: das Material folgt dem Buch. Wer das Buch nicht sieht (privat eines anderen Profils, einem Kind nicht freigegeben),
bekommt 404 wie für ein Buch, das es nicht gibt; Kinder lesen das Material freigegebener Bücher nur. Lesen und Öffnen brauchen
`lesen`, Hinzufügen, Umbenennen und Funde entscheiden `bearbeiten`, Entfernen `loeschen` (sonst 403).

| Weg | Zweck |
|---|---|
| `GET /api/books/{id}/material` | `{material: [Material], funde: [Fund], ort, groesse}`; `ort`: wohin neues Material kommt; `groesse` alles zusammen |
| `POST /api/books/{id}/material` `{name, groesse, sha256, entpacken?}` | eine Datei anmelden (je Datei ein Aufruf), jedes Format; antwortet wie `POST /api/annahme` mit der Aufnahme (`material_fuer` gesetzt), die Teile gehen an `PATCH /api/annahme/{id}` (Fähigkeit `hinzufuegen`), der Fortschritt steht bei den Aufträgen. Gleiche Datei schon Material dieses Buchs: `da`. Eine ZIP bleibt eine Datei, mit `entpacken: true` wird jeder Eintrag eigenes Material (Grenzen wie beim Hochladen) |
| `PATCH /api/books/{id}/material/{mid}` `{name}` | umbenennen; die Endung bleibt (fehlt sie, kommt sie dazu); `/` und andere verbotene Zeichen 422; in der Kellerwolke bekommt der Begleiter den neuen Zusatz |
| `GET /api/books/{id}/material/{mid}/datei?herunterladen=` | die Datei mit Bereichen, inline zum Ansehen oder als Anhang; was nicht in der App öffnet, immer als Anhang; über das Inhalts-Cookie wie Buchdateien |
| `GET /api/books/{id}/material/{mid}/folgen` | vor dem Entfernen: `{id, name, buch_id, titel, ort, pfad, groesse, papierkorb, suche, seiten, stand}`; `papierkorb`: in den Papierkorb der Kellerwolke (sonst auf dem Gerät endgültig); `suche`: sein Text steht in der Suche (`seiten` Seiten) und fehlt danach |
| `DELETE /api/books/{id}/material/{mid}?stand=` | entfernen, nur mit `stand` aus den Folgen (422 ohne, 409 wenn sich seither etwas geändert hat); Buch und übriges Material bleiben; kommt die Datei nicht in den Papierkorb: 502 |
| `POST /api/books/{id}/material/funde/{knoten}/annehmen` | Ja: die Datei neben dem Original wird Begleiter des Originals und Material, in der App ohne den Namen des Buchs davor ("Lösungen.pdf"); Antwort Material |
| `POST /api/books/{id}/material/funde/{knoten}/ablehnen` | Nein: sie bleibt, wo sie ist, und wird nie wieder angeboten |
| `GET /api/material/stand` | `{abgleich: {bereit, laeuft, ordner, ordner_gesamt, gefunden, grund, zuletzt}, texte: {offen, fertig, ohne, fehler, laeuft}}` (Fähigkeit `bearbeiten`) |
| `POST /api/material/abgleich` | den Abgleich jetzt anstoßen (sonst im Takt `MATERIAL_ABGLEICH_TAKT_S`, Vorgabe einmal am Tag); Antwort wie `.../stand` |

`Fund`: `{knoten, buch_id, name, groesse, pfad, gefunden_am}`. **Erkennen**: der Abgleich sieht in der Kellerwolke jeden Ordner
mit Originalen einmal an; eine Datei, deren Name mit dem Stamm des Originals beginnt (mit oder ohne die Nummer des Buchs) und dann
einen Trenner hat (` - `, `_`, `.`, `(`, `[`), keine Begleiterin ist und keinem Buch gehört, wird ein Fund des Buchs mit dem
längsten passenden Namen. Ohne Kellerwolke gibt es nichts abzugleichen.

**Suche**: lesbares Material liest ein Auftrag im Hintergrund (im eigenen Prozess wie beim Aufnehmen, nach einem Neustart mit dem
Offenen weiter) und legt den Text je Seite in den Suchindex. `GET /api/search` trägt auf der ersten Seite dazu
`material: [{material_id, buch_id, titel, autor, name, seite, auszug, deckblatt}]`: ein Treffer nennt das Buch, die Datei und bei
einem PDF die Seite; nur Material von Büchern, die das Profil sieht.

**Folgen für das Buch**: `GET /api/books/{id}` und die Bücherliste (auch die Bücher der Freigaben) tragen `material` (Anzahl);
`PUT /api/books/{id}/privat` antwortet `{privat, material}`; die Löschfolgen nennen das Material (`material`, siehe Dateien je
Buch), und das Löschen nimmt es mit.

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
  `heft`, `katalog`, `broschuere` und seit BF-80 `anleitung` (Bedienungs-, Gebrauchs-, Montage- oder Bauanleitung eines Geräts).
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
- Einordnen (`services/einordnung.py`, seit BF-77 für alle Werke): offen ist jedes Werk, das noch niemand eingeordnet hat
  und das keine Art hat (eine schon gesetzte Art stammt vom Nutzer und bleibt). Eine Runde wendet erst feste Regeln an
  (`services/artregeln.py`, Herkunft `regel`, Begründung in `einordnung_grund`): ISBN und mehr als `EINORDNEN_BUCH_AB_SEITEN`
  (40) Seiten ist ein Buch, aber nur bei einem sicher nicht schlichten Umschlag (sonst braucht das Deckblatt die Gattung);
  ohne ISBN ist eine Anleitung (BF-80), was im Titel oder Dateinamen am Wortanfang Bedienungsanleitung, Gebrauchsanweisung,
  Gebrauchsanleitung, Montageanleitung, Aufbauanleitung, Bauanleitung, Kurzanleitung, Benutzerhandbuch, user manual, owner's
  manual, instruction manual, quick start guide oder installation guide nennt; sonst ein Dokument, was im Titel das Programm
  nennt, aus dem es stammt, eine Endung .docx, .pptx oder .xlsx im Titel oder Dateinamen trägt, dort am Wortanfang Rechnung,
  Beleg, Datenblatt, datasheet, Folien, slides oder lecture nennt oder höchstens `EINORDNEN_DOKUMENT_BIS_SEITEN` (4) Seiten
  hat. Den Rest bestimmt die KI über die Leitstelle, gebündelt: bis zu `EINORDNEN_JE_ANFRAGE` (40) Werke je Anfrage (Titel,
  Autor, Verlag, Seiten, ISBN ja oder nein, Dateiname, Anfang des Volltexts), Antwort als Liste fester Länge, mit
  `EINORDNEN_ABSTAND_S` (5) Sekunden Abstand. Die KI bekommt nur Werke mit geprüftem Umschlag und fragt die Gattung nur, wo
  das gezeichnete Deckblatt sie braucht (Umschlag schlicht), und nur bei Büchern. Abschaltbar mit `EINORDNEN_AN` (true).
  Eine Runde beginnt beim Start (was vor einem Neustart offen blieb, geht gleich weiter), nach jeder Runde der
  Umschlagprüfung, die Umschläge geprüft hat, und sonst alle `EINORDNEN_TAKT_S` (600) Sekunden. Was die KI zu einem Werk nicht brauchbar sagt, bleibt offen und kommt in
  einer späteren Runde wieder dran; lehnt die Leitstelle ab, hält das Einordnen an, bis es fortgesetzt wird. Von Hand
  (`hand`) fassen weder Regel noch KI ein Werk wieder an, auch nicht während einer Anfrage.

| Weg | Zweck |
|---|---|
| `GET /api/einordnung/stand` | `{an, bereit, laeuft, angehalten, grund, gesamt, nach_regel, durch_ki, offen, erledigt}`: `bereit` heißt eingeschaltet und Leitstelle eingetragen (die Regeln laufen auch ohne), `gesamt` alle Werke, `nach_regel` und `durch_ki` wer eingeordnet hat, `offen` Werke ohne Einordnung und ohne Art, `erledigt` wie `durch_ki` (bleibt vorerst), `grund` warum angehalten oder in der letzten Runde ein Werk offen blieb |
| `POST /api/einordnung/fortsetzen` | nach einer Ablehnung der Leitstelle weiter einordnen; antwortet mit dem Stand |

Spalten in `books`: `gattung`, `umschlag_wahl`, `umschlag_schlicht` (NULL noch nicht geprüft, 0, 1), `umschlag_geprueft`
(Stand des geprüften Umschlags), `einordnung` (leer offen, `regel`, `ki`, `hand`), `einordnung_grund` (bei `regel` warum).
`GET /api/books/{id}` trägt `einordnung` und `einordnung_grund`; wer Art oder Gattung setzt, leert den Grund.

### Bücher und Besonderes (BF-77)

Ein Werk ist ein Buch (`typ` leer) oder etwas Besonderes (`dokument`, `heft`, `katalog`, `broschuere`, `anleitung`).

- `GET /api/books?art=buch|besonderes` filtert danach (sonst 422), mit jedem anderen Filter und mit `zusammenfassen=true`.
- `GET /api/config/stats` zählt dazu `buecher` und `besonderes`; `buecher_mit_isbn` und `dokumente` bleiben vorerst für
  Stellen, die sie noch lesen.

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

## Katalog (BF-69)

Plan, Begriffe und alle Wege unter `/api/katalog` stehen in [KATALOG.md](KATALOG.md); gebaut im Paket `backend/app/katalog`
(Weg: `api/katalog.py`). Hier, was dort nicht steht oder genauer gilt:

- **Arten der Bereiche**: ein Bereich trägt `arten` (Werte von `books.typ`, `""` für Buch; Spalte `categories.arten` als JSON,
  Vorgabe `[""]`), in der Datei, in `GET /api/katalog` und in `POST`/`PATCH /api/katalog/bereiche`. Regeln und KI schlagen einem
  Werk nur Kategorien aus Bereichen seiner Art vor; die KI sieht je Anfrage nur Werke einer Art und deren Kategorien. Im
  Standard gilt `besonderes` für `dokument`, `heft`, `katalog`, `broschuere`, `anleitung`, alle anderen Bereiche für Bücher. Beim
  ersten Start mit BF-80 bekam jeder Bereich, der für `dokument` galt, auch `anleitung` (einmal je Bestand, danach entscheidet der
  Nutzer; gemerkt als `katalog_arten_anleitung` in `app_settings`).
- **Zeichen** heißen wie in Font Awesome ohne `fa-`; Eingaben mit `fa-` (Symbolwahl) werden ohne gespeichert.
- **Farbe einer Kategorie**: Antworten zeigen die Farbe, die gilt (die eigene oder die des Bereichs). Beim Schreiben (Entwurf,
  `POST`/`PATCH /api/katalog/kategorien`, die beide `farbe` nehmen) heißt leer oder die Farbe des Bereichs "erbt"; gespeichert
  wird dann leer, und die Kategorie folgt jeder neuen Farbe ihres Bereichs.
- **Datei**: das Format des Standards, dazu frei `verborgen`, `herkunft`, `arten` und `farbe` (Kategorie). `GET /api/katalog/datei`
  kommt als Anhang `katalog.json` ohne `anzahl`. Fehlt beim Laden die Herkunft, gilt: Schlüssel des Standards `standard`, einer
  seiner Teile `geteilt`, sonst `eigen`. Geprüft wird wie jede Eingabe (422 mit Feld und Grund), dazu Schlüssel im ganzen Katalog
  und Namen je Bereich eindeutig.
- **Entwurf**: `POST /api/katalog/entwurf` antwortet immer wie `GET` mit `{entwurf, lauf}`; bei `"bestand"` ist `entwurf` leer,
  bis der Lauf fertig ist. `lauf` steht da, solange er läuft oder scheiterte, und solange sein Entwurf steht (dann mit `grund`,
  etwa ohne KI); jeder andere Weg (standard, leer, Datei, `PUT`, `DELETE`) ersetzt ihn.
- **Teile**: zerfällt eine große Kategorie im Entwurf in ihre Teile, bleibt sie daneben stehen (Name und Herkunft standard,
  ohne `teile`) und fasst die Bücher, die zu keinem Teil passen; ohne solche ist sie verborgen. Jeder Teil nennt sie in
  `teil_von` (Spalte `categories.teil_von`, auch in der Datei und in `GET /api/katalog`). Beim Einordnen wird ein Teil
  vorgeschlagen, wenn das Werk zu ihm passt (Regel oder KI), sonst die große Kategorie; die KI liest das im Katalog mit.
- **Laufstand** dazu `stand` (`""` noch keiner, `laeuft`, `pause`, `fertig`, `fehler`); `schritt` nur, solange er läuft.
  Beim Einordnen zählen `regeln` die Vorschläge mit Regel (auch `beide`), `ki` die mit KI (auch `beide`); beim Entwurf aus dem
  Bestand `regeln` die Werke mit einem Treffer, `ki` die neuen Kategorien.
- **Einordnen**: `POST /api/katalog/einordnen` mit `{stapel?}` oder ohne Körper; läuft oder pausiert schon einer, bleibt es bei
  ihm; ohne sichtbare Kategorie 409 `"Es gibt noch keinen Katalog mit sichtbaren Kategorien"`. Dran sind Werke in keiner
  Kategorie und ohne offenen Vorschlag. Vor dem ersten Stapel fragt der Lauf die KI nach den alten Regalen ohne passende Regel.
  Kann die KI nicht (weg, abgelehnt), pausiert der Lauf mit Grund; eine unbrauchbare Antwort lässt nur die Regeln gelten.
  Pausieren hält sofort an, auch mitten in einer Anfrage; der angefangene Stapel wird beim Fortsetzen neu gesucht.
- **Vorschläge**: `auch` trägt je Eintrag die `id` des Vorschlags dort. Unbekannte `kategorie`: 404. Annehmen braucht genau eins
  von `ids` und `kategorie` (422 sonst); `beide` wird `katalog-regel`. Nicht offene oder unbekannte Nummern zählen nicht mit.
- **Löschfolgen**: `{name, buecher, vorschlaege, kategorien, titel}` (die ersten zehn Bücher), `DELETE` antwortet
  `{geloescht: true, id}`. Alte Regale: `GET /api/katalog/alt/{id}/loeschfolgen` `{id, name, buecher, ohne_kategorie, titel}`
  (`ohne_kategorie`: davon in keiner Kategorie), `DELETE` `{entfernt: true, id, buecher}`; nur Regale aus Importen (404 sonst).
  Übernehmen als Schlagwort vergibt ein Etikett mit dem Namen des Regals (nicht doppelt).
- **Treffer**: immer alle vier Arten in fester Folge; gezählt unter den Werken der Arten des Bereichs; `ki_vorschlaege` die offenen
  mit KI.
- **Einstellungen**: `GET`/`PUT /api/katalog/einstellungen` `{stapel, ki_je_anfrage, sicher_ab, teilen_ab}` (`app_settings`
  `katalog_*`, Vorgaben `KATALOG_STAPEL` 500, `KATALOG_KI_JE_ANFRAGE` 40, `KATALOG_SICHER_AB` 80, `KATALOG_TEILEN_AB` 300). Nur in
  der Einrichtung: `KATALOG_ABSTAND_S` (5, Pause zwischen zwei Anfragen an die KI), `KATALOG_NEU_AB` (3, ab so vielen Büchern ist
  ein Schlagwort ohne Kategorie häufig).
- **Bücher und Regale**: `GET /api/books?ohne_kategorie=true` nur Werke in keiner Kategorie des Katalogs (`false`: nur die in
  einer). Die Kategorien in `GET /api/books/{id}` tragen `{id, name, slug, art, zeichen, farbe, bereich}`, Kategorien zuerst;
  bei Regalen ist `bereich` leer. `GET /api/categories` liefert nur noch Regale, `PATCH`/`DELETE /api/categories/{id}` gehen nur
  für Regale (404 für Bereiche und Kategorien); ein Regal darf wie eine Kategorie heißen. Ein Buch in eine Kategorie und heraus
  geht wie bei Regalen (`POST`/`DELETE /api/categories/{id}/books/{buch}`, Quelle `manuell`).
- **Tabellen**: `katalog_lauf` dazu `nach_buch` (das letzte Buch des letzten fertigen Stapels; dahinter geht es nach einem
  Neustart weiter), `katalog_alt_vorschlag` (`regal_id`, `kategorie_id` leer für Schlagwort, `grund`, `geprueft_am`): was die
  KI je altem Regal vorschlägt.

## Familie (BF-78)

Plan und Grundform der Wege in `docs/neubau/FAMILIE.md` (Schnittstelle); hier, was dazukam oder genauer feststeht. Die Arbeit
tut `backend/app/familie/`, die Wege stehen in `backend/app/api/familie.py`, Stufen und Rechte in `backend/app/familie/stufen.json`.

- **Köpfe**: jede Anfrage trägt `X-Profil` (Profilschlüssel aus der Wahl) und `X-Geraet` (zufällige Kennung des Browsers, etwa
  eine UUID; 8 bis 100 Zeichen aus Buchstaben, Ziffern, `-` und `_`). Bilder, Dateien und Ströme haben keinen Kopf: die Wahl
  setzt dafür das Cookie `bf_profil` (HttpOnly, SameSite strict, Pfad `/api`), `POST /api/familie/verlassen` löscht es. Das
  Inhalts-Cookie der Anmeldung (`POST /api/anmeldung/zugang`) bleibt, wie es ist; zusammen gelten Sichtbarkeit und Kinderschutz
  auch für Umschläge, Dateien und Ereignisströme.
- **Einzelbetrieb**: gibt es genau ein Profil (Verwaltung) ohne PIN, gilt es ohne `X-Profil`; `POST /api/familie/wahl` ohne PIN
  geht trotzdem und gibt einen Schlüssel. Sonst antwortet jeder persönliche Weg ohne gültigen Schlüssel mit 401
  `{"detail": "Bitte zuerst ein Profil wählen", "code": "profil_waehlen"}` und `WWW-Authenticate: Profil` (auch bei einem
  Schlüssel, der nicht mehr gilt, oder einem Gerät, das fest auf ein anderes Profil gestellt ist). Das Konto bleibt angemeldet:
  nur 401 ohne `code` heißt abmelden. Ohne Profil gehen nur `GET /api/familie`, `/stufen`, `POST /wahl`, `/verlassen`,
  `/geraet`, `/profile/{id}/pin/vergessen`, `GET /api/config`, `/api/config/oberflaeche` und die Hintergründe der Gestaltung.
- **PIN**: falsche PIN oder Bild-PIN 403 `"Die PIN stimmt nicht"`; nach fünf Fehlversuchen 429 mit `Retry-After` (Sekunden) und
  `detail` (`"Zu viele Versuche, bitte N Sekunden warten"`), die Wartezeit verdoppelt sich bis 15 Minuten (`stufen.json`,
  `zugang`). Eine Bild-PIN sind drei Bildschlüssel aus `zugang.bilder` in ihrer Folge; die neun Bilder des Entwurfs in der Folge
  des Rasters 3 x 3: sonne, fisch, baum, stern, apfel, mond, auto, herz, wolke. PIN und Bild-PIN schließen sich aus.
  `POST /api/familie/profile/{id}/pin/vergessen` `{kennung, passwort}`: das Konto des Geräts meldet sich erneut an, dann fällt
  die PIN eines Profils Verwaltung weg (andere PINs setzt die Verwaltung zurück); stimmen Kennung oder Passwort nicht, 403 mit
  Grund (nie 401, das hieße abmelden). Setzt jemand eine fremde PIN, enden die Sitzungen dieses Profils.
- **Profil in Antworten** (`GET /api/familie`, Anlegen, Ändern, PIN): `{id, name, zeichen, farbe, rolle, stufe, hat_pin,
  hat_bild_pin, geburtsjahr, einstellungen}`; Geburtsjahr und Einstellungen nur für die, die das Profil ändern dürfen, und für
  das Profil selbst (sonst null). `einstellungen` (nur Kinder) ist, was wirkt: `{lesehilfen: {mitlesen, tempo, silben,
  lesezeile, schrift, hinweise_sprechen, tasten_ansagen, stimme}, lesezeit: {an, minuten, ruhe_an, ruhe_von, ruhe_bis, vorlesen_zaehlt}, katze: {an, name, schnurren,
  name_eingabe}}`; ohne Wahl der Eltern gelten die Lesehilfen der Stufe und die Lesezeit nach dem Alter. Beim Anlegen und Ändern
  ersetzt jeder genannte Teil von `einstellungen` den gespeicherten, die übrigen bleiben. `schrift`: klein, mittel, gross (Anteil
  an der Größe der Stufe, `gestaltung.schriftgroessen`). `GET /api/familie/profile/{id}` gibt ein Profil einzeln.
- **GET /api/familie** dazu `aktiv` (das Profil des Schlüssels, wenn er gilt), `geraet: {gebunden_an, fest_auf, offen}`
  (`fest_auf` ist die Bindung, `gebunden_an` nur, solange sie wirkt, dann nur dieses Profil in `profile`) und `stimme`, die
  Vorlesestimme der Familie (leer: keine). `PUT /api/familie/stimme {stimme}` setzt sie (Fähigkeit `profile`).
- **Gebundenes Gerät verlassen**: `POST /api/familie/verlassen {eltern_pin}` löst die Bindung nicht; die Profilwahl ist dann auf
  diesem Gerät zehn Minuten offen (`zugang.geraet_offen_s`, `geraet.offen` true, `gebunden_an` null) für eine Wahl. Diese Sitzung
  gilt auf dem Gerät, bis sie verlassen wird; danach öffnet es wieder das Kind. Lösen nur mit `DELETE /api/familie/geraet`
  `{eltern_pin}` oder ohne PIN als Verwaltung (mit ihrem `X-Profil`).
- **Fähigkeiten der Stufen** (`stufen.json`): Vorlesen und Erstes Lesen nur `lesen` und `vorlesen`; Lesen und Lernen dazu
  `favoriten` (Lieblinge) und `gelesen` (Rückblick auf fertig gelesene Bücher); ab Schule `lesezeichen`, `suche`,
  `markierungen`, `notizen`; Jugend dazu `sammeln`, `etiketten`, `privat`, `ausfuehren`. `GET /api/books?gelesen=` und
  `PATCH /api/books/{id}/gelesen` brauchen `gelesen`. Ohne Suche, Notizen, Markierungen und Lesezeichen merkt sich das Buch die Stelle von selbst: den
  Lesestand (`PATCH /api/books/{id}/leseposition`, auch in einer Fassung) braucht nur `lesen`, die Vorlesestelle `vorlesen`.
  Der Schnellfilter der Liste (`suche=`) und die Suche im Buch brauchen `suche`.
- **Fertig gelesen** (eine Regel, `familie/lesestand.py`): ein Buch ist fertig, sobald sein Lesestand das Ende erreicht oder
  `lesestand.fertig_ab` aus `stufen.json` (0,99), oder wenn es mit `PATCH /api/books/{id}/gelesen` markiert ist; es bleibt
  fertig, auch wenn man zurückblättert, bis die Markierung zurückgenommen wird. Gelesen wird der Anteil wie in der Oberfläche
  (Seite durch Seiten, sonst Prozent, sonst Anteil des Rollens; eine Stelle nur mit CFI sagt nichts). Am Buch steht
  `fertig_am` (leer: noch nicht); es gilt für den Filter `gelesen`, den Zähler `gelesen` in `GET /api/config/stats`, den
  Rückblick des Kindes und den Einblick der Eltern (`fertig`, dann Fortschritt 1). `last_read_at` bleibt der Zeitpunkt des
  letzten Lesens. Beim Start bekam jeder bisherige Lesestand `fertig_am` nach der Regel; als gelesen markiert galt dabei ein
  Buch mit Zeitpunkt ohne Lesestand.
- **Hinweise sprechen, Tasten ansagen**: `lesehilfen.hinweise_sprechen` und `lesehilfen.tasten_ansagen`, Vorgabe an bis Lesen und
  Lernen, aus ab Schule; die Eltern ändern beides. `lesehilfen.stimme`: eine Stimme aus dem Katalog des Sprechdienstes
  (`katalog:<name>`, aus `GET /api/vorlesen/stimmen`), `geraet` für die Stimme des Geräts (nur für Installationen ohne
  Sprechdienst, immer eine ausdrückliche Wahl, nie ein stiller Rückfall) oder leer: die Vorlesestimme der Familie. Gibt es keine,
  schweigen die Ansagen und der Elternbereich zeigt "Stimme wählen".
- **Feste Ansagen** (`familie/ansagen.json`, `familie/ansagen.py`): vorab gesprochen mit der eingebauten Stimme und dauerhaft im
  Ort texte unter `ansagen/<ordner der stimme>/<schluessel>-<pruefsumme>.wav` (Prüfsumme aus Fassung und Text: ein geänderter
  Text gibt einen neuen Ton). Die Schlüssel heißen `gruppe.name`:
  - `tasten.<name>`: weiter, zurueck, pause, vorlesen, silben_an, silben_aus, zeile_an, zeile_aus, mein_regal, lieblinge,
    gelesen, schloss, zum_regal, stift_an, stift_aus, gemerkt, lesezeichen_weg, notiz, lieblingsbuch, kein_lieblingsbuch, fertig;
  - `hinweise.<name>`: lesezeit_gleich_um, lesezeit_um, bild_pin ("Tippe drei Bilder an.", die Zahl aus `zugang`),
    bild_pin_falsch, katze_benennen, frag_eltern, wer_liest, buch_fertig, regal_leer, lieblinge_leer, gelesen_leer, suche_leer;
  - Bausteine der Uhr, Zahlen als deutsche Wörter: `uhr.1` bis `uhr.12` ("Es ist vier Uhr"), `minute.1` bis `minute.59`
    ("fünfunddreißig"), `noch.1` bis `noch.120` ("Noch eine Minute", "Noch fünfundzwanzig Minuten"), `heute.1` bis
    `heute.120`; die Uhrzeit setzt die Oberfläche daraus zusammen;
  - aus den Dingen: `titel.<buch>` für jedes Buch, das das Kind sieht (erst nach der Freigabe), `katze` (der Name seiner Katze),
    `katze.<vorschlag>` im Vorlesealter (die Vorschläge aus `stufen.json`, `katze.vorschlaege`), `ruhezeit` ("Jetzt ist
    Ruhezeit. Ab sechs Uhr dreißig kannst du wieder lesen.", mit dem Ende seiner Ruhezeit), `profil.<profil>` (die Namen für
    "Wer liest?", in der Stimme der Familie); `probe` ist der Probesatz.
- **Ansagen erstellen** (`familie/ansagelauf.py`): ein Auftrag im Hintergrund (Vorrang "hintergrund" bei der Leitstelle), je
  Stimme nur, was fehlt; angestoßen nach der Wahl einer Stimme, nach Freigaben, dem Namen der Katze, Anlegen, Ändern und
  Löschen von Profilen und einem neuen Titel, beim Start und im Takt `ANSAGEN_TAKT_S` (600). Nach einem Neustart geht er mit dem
  weiter, was fehlt. Alte Töne einer Stimme räumt er erst weg, wenn die neuen fertig sind; die Probe bleibt; eine Stimme, die
  niemand mehr hört, verliert ihre Töne. Ohne Sprechdienst steht der Grund am Auftrag.
- **Wege der Ansagen**:
  - `GET /api/familie/ansagen`: `{stimme, fertig, gesamt, laeuft, eintraege: {schluessel: {text, url}}}` für das aktive
    Profil, ohne Profil für die Profilwahl (Hinweise, Tasten, Uhr, `profil.<id>`); nur fertige Einträge. Mit der Stimme des
    Geräts alle Texte mit `url` null, ohne Stimme keine.
  - `GET /api/familie/ansagen/ton/{ordner}/{datei}`: der Ton (`audio/wav`, `Cache-Control` ein Jahr, `immutable`, `ETag`, 304
    auf `If-None-Match`), ohne Kopf über die Cookies der Anmeldung und der Wahl. Ein Kind nur für seine Stimme, die Profilwahl
    nur für die der Familie, Erwachsene jede (403 sonst).
  - `POST /api/familie/ansagen/probe {stimme}` für Erwachsene mit `profile` oder `freigeben`: `{text, url}` des Probesatzes
    ("Hallo, ich lese dir vor. Tippe auf ein Buch."), abgelegt wie die Ansagen; mit `geraet` nur der Text; ohne Sprechdienst
    503 mit Grund.
  - `GET /api/familie/ansagen/stand?stimme=`: `[{was: "Ansagen erstellen", stimme, stand (wartet, laeuft, fertig, fehler),
    gesamt, fertig, grund, begonnen, geaendert, fertig_am}]`, ebenso nur für Erwachsene mit `profile` oder `freigeben`.
- **GET /api/familie/ich**: `{profil, faehigkeiten, darstellung, lesehilfen, lesezeit, katze, einblick}`; für Erwachsene
  `darstellung` `{}`, `lesehilfen` null, `lesezeit.an` false, `katze.an` false, `einblick` leer. `lesezeit`:
  `{an, heute_s, grenze_s, rest_s, hinweis_ab_s, ruht, ruhe_bis}`. `PATCH /api/familie/ich/katze {name}` antwortet mit der Katze.
- **GET /api/familie/stufen**: `{stufen: [{schluessel, name, alter, alter_von, alter_bis, faehigkeiten, einblick, darstellung,
  lesezeichen_je_buch, vorgaben: {lesehilfen, lesezeit, katze}}], lesezeit: [{alter_von, alter_bis, minuten, an}], rollen,
  faehigkeiten, zugang: {pin_stellen_von, pin_stellen_bis, bild_pin_anzahl, bilder}, katze_vorschlaege, katze_nennung}`;
  `alter_bis` null: nach oben offen. Einblick-Arten: `titel`, `lesezeit`, `fortschritt`, `grober_fortschritt`, `zuletzt`,
  `geteiltes` (nur, was das Kind teilt).
- **Einblick**: `{sichtbar, lesezeit_heute_s, eintraege: [{buch: {id, title, author, typ, year, page_count, alter_von, alter_bis,
  alter_quelle}, fortschritt, seite, seiten, zuletzt}]}`; die Lesezeit zählt je Tag, nicht je Buch. Sehen dürfen ihn das Kind
  selbst und Erwachsene mit `freigeben`. `PUT /api/books/{id}/geteilt {geteilt}`: das Kind teilt ein Buch (ab Jugend sehen die
  Eltern nur Geteiltes).
- **Freigaben**: `{kategorien: [{id, name, zeichen, anzahl}], buecher: [Buch wie in der Liste]}`; `buecher` nur die einzeln
  freigegebenen, `anzahl` zählt auch Unterkategorien. Eine freigegebene Kategorie gibt alles darunter frei. Freigeben kann nur,
  wer das Buch sieht (sonst 404); ein privates Buch bleibt privat, auch wenn es freigegeben ist.
- **Profil löschen**: `GET .../loeschfolgen` `{profil, notizen, markierungen, etiketten, lesestaende, vorlesestellen,
  fassungen_gelesen, freigaben, private_buecher, lesezeit_tage, geraete, stand}`; `DELETE /api/familie/profile/{id}?stand=`
  braucht den `stand` daraus (422 ohne, 409, wenn sich seither etwas geändert hat). Kein Buch wird gelöscht; die privaten Bücher
  des Profils sind danach für alle sichtbar. Das letzte Profil Verwaltung bleibt (409).
- **Am Buch**: `privat`, `alter_von`, `alter_bis`, `alter_quelle` in Liste und Buch. `PATCH /api/books/{id}` mit `alter_von` und
  `alter_bis` (0 bis 99, null leert) setzt `alter_quelle` "hand". Aus den Quellen: MARC 21 (Deutsche Nationalbibliothek,
  K10plus) Feld 521 (Zielgruppe, etwa "ab 8 J.") oder 008/22; die Herkunft steht in `vorschlag.herkunft.alter`, übernommen wird
  mit `alter_von`, `alter_bis` in `POST /api/metadata/buch/{id}/uebernehmen`. `PUT /api/books/{id}/privat {privat}` braucht die
  Fähigkeit `privat`.
- **Rechte**: was ein Weg braucht, sagt `braucht("fähigkeit")` in `core/auth.py`; fehlt sie, 403 `"Das darf dieses Profil nicht:
  ..."`. Ein Buch oder eine Fassung im Pfad, die das Profil nicht sieht, ist 404 wie ein fehlendes. Sammelaktionen behandeln
  verborgene Bücher wie fehlende. Andere Apps (Fundus) sehen keine privaten Bücher; Lesestand und Notizen dort sind die des ersten
  Profils Verwaltung.
