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
Gemeinfreie Bücher halten nur, wenn sie in eine Lücke geholt werden (BF-98, `POST /api/gutenberg/luecke`). Beim Halt ist die Datei schon gelesen (Angaben, Text, Umschlag); im Regal, in der Suche und in
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
| `hinweise` | `[{text, herkunft}]`: kurze Sätze, etwa "Die Datei ist englisch, die Lücke deutsch" (`luecke`, siehe Lücken) oder "Im Bestand gibt es X schon als PDF, aus einer anderen Datei" (`bestand`) |
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

### Gemeinfreie Bücher mit eigenem Katalog (BF-98)

Gutendex ist oft überlastet. Darum gibt es den eigenen Katalog (`quellen/gutenberg_katalog.py`): die Katalogdatei des Project
Gutenberg von den Spiegeln (`GUTENBERG_KATALOG_PFAD`), als SQLite mit Volltextindex im Ort Suchindex (`gutenberg_katalog.db`), nur
Einträge der Art Text. Holen ist ein Auftrag mit Fortschritt in Byte; nach einem Abbruch geht es am Stand weiter (Range mit
If-Range), gebaut wird neben dem alten Katalog und erst ganz fertig getauscht. Beim Erneuern fragt der Auftrag, ob sich die Datei
geändert hat (If-None-Match); die nächtliche Pflege erneuert, wenn er älter ist als `GUTENBERG_KATALOG_TAGE`. Ein Fund aus dem
Katalog nennt die Datei und den Umschlag auf dem Spiegel (`pg<Nr>-images-3.epub`, `pg<Nr>.cover.medium.jpg`); `download_count` ist 0.

| Weg | Zweck |
|---|---|
| `GET /api/gutenberg/vorschlaege?q=&sprache=&seite=` | beim Tippen, nur der eigene Katalog, keine Anfrage ins Netz; ohne Wort oder Katalog leer. Seiten zu 32 wie bei Gutendex |
| `GET /api/gutenberg/suche?q=&sprache=&topic=&seite=` | ausdrücklich bei Gutendex, wartet bis zu `GUTENBERG_SUCHE_GEDULD_S` Sekunden. Dazu `herkunft` (`gutendex` oder `katalog`) und `hinweis`: antwortet Gutendex nicht, kommen die Treffer aus dem Katalog und `hinweis` sagt in Klartext warum; ohne Katalog 502 mit dem Grund als Satz, nie als Nummer |
| `GET /api/gutenberg/katalog` | `{da, anzahl, stand, geholt_am, alter_tage, faellig, erneuern_tage, laeuft, schritt, erledigt, gesamt, grund, suche_geduld_s}`; `schritt` ist `holen` oder `bauen`, `erledigt` und `gesamt` sind Byte |
| `POST /api/gutenberg/katalog` | holen oder erneuern; läuft es schon, bleibt es bei diesem Lauf. 409, wenn die gemeinfreien Bücher abgeschaltet sind |
| `POST /api/gutenberg/luecke` `{buch, sammlung_id, band, sprache}` | in die Lücke holen: wie `POST /api/gutenberg/import`, aber mit Halt in einer neuen Vorschau, die Sammlung, Band und Sprache vorgibt (`{vorschau}`); 422 ohne Sammlung, 409, wenn das Buch gerade schon geholt wird |

Die Lücken einer Sammlung nennen je fehlendem Band mit Titel `gemeinfrei`: das Buch des Katalogs, das nach ganzem Titel und Autor
sicher derselbe Band ist, in der Sprache der Lücke (nur lokal abgeglichen, ohne Rücksicht auf Groß und klein, Satzzeichen und
Umlautschreibweise); sonst `null`.

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
| `GET /api/collections/vorschlaege` | offene Vorschläge, die größten zuerst: `[{id, name, autor, anzahl, wege: [str], ki, ki_geprueft, luecken, buecher: [<wie in buecher> + band]}]`; nur Bücher, die noch in keiner Sammlung sind, nach Band; `luecken` siehe Lücken (BF-75) |
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

## Lücken (BF-75)

Plan und Entscheidungen in [LUECKEN.md](LUECKEN.md); gebaut in `backend/app/luecken/` (`bandnummer.py` liest Nummern, `rechnen.py`
rechnet ohne Datenbank, `speicher.py` liest und schreibt die Tabellen, `dienst.py` baut die Ansicht, `suchadresse.py` füllt die
Vorlage, `nachschlagen.py` ist der Auftrag, Formen in `modelle.py`), die Kataloge in `backend/app/quellen/reihen.py`, Wege in
`backend/app/api/luecken.py`.

**Rechte**: alle Wege brauchen die Fähigkeit `luecken` (in `familie/stufen.json` für Verwaltung und Erwachsen, keine Stufe eines
Kindes; eine Stufe, die sie nennt, darf sehen, sonst 403). Ändern (Zahl, Platzhalter, Ausblenden, Zurückholen, Neu nachschlagen)
braucht dazu `bearbeiten`, die Suchadresse setzen `einstellungen`. Gerechnet wird nur mit Büchern, die das Profil sieht
(`familie/sichtbar.py`): ein Band, den ein anderes Profil privat hat oder der einem Kind nicht freigegeben ist, ist für dieses
Profil eine Lücke und erscheint nie als vorhanden. Ein Kind bekommt eine Sammlung ohne freigegebenes Buch als 404. Ausgeblendetes,
Zahlen und Platzhalter gelten für die Sammlung, also für alle Profile.

**Bandnummern** (`books.band_nummer`, auch "Bd. 3" aus einem Katalog): eine ganze Zahl ("3", "03", "Band 3", "Bd. 3", "3.", "[3]",
"3. Band", "3.0") belegt ihren Platz der Zählung; ein Doppelband ("1-2", "1/2", "1+2", höchstens 20 auseinander) belegt alle von
bis; ein Zwischenband ("3.5", "3,5", "3a") steht hinter seinem Band, belegt keinen Platz, füllt also keine Lücke, und sein Fehlen
ist keine; Band 0 steht vor 1 und belegt nichts (die Zählung beginnt bei 1); ohne Zahl ("Sonderband") hinter allen Nummern, ohne
Band ganz am Ende. Nummern über 9999 zählen nicht (etwa die Nummer einer Verlagsreihe).

**Sprachen**: jede Sprache hat ihre eigene Zählung. Die Sprache eines Buchs ist das Kürzel aus `books.language` ("ger",
"Deutsch", "de-DE" sind `de`); ohne Angabe zählt es zur Hauptsprache der Sammlung (die häufigste ihrer Bücher, gleich wer sie
sieht); leer bleibt sie nur, wenn kein Buch eine nennt. Die Reihen stehen mit der Hauptsprache zuerst, dann nach Namen.

**Lücken**: gilt eine Zahl der Bände, fehlt jeder Platz von 1 bis zu ihr, den kein Band belegt; ohne Zahl nur Plätze zwischen dem
ersten und dem letzten belegten. Ausgeblendete fehlen nie; eine Sprache ohne Band mit Nummer hat keine Lücken. Die Zahl: die
eigene Angabe gewinnt immer (`wahl` `eigene`), `keine` heißt ausdrücklich ohne Zahl (auch wenn die Quelle eine kennt), sonst die
der Quelle (`quelle`, Vorgabe).

**Nachschlagen** (Auftrag "Lücken nachschlagen", `luecken/nachschlagen.py`): je Sammlung und Sprache höchstens eine Abfrage, im
Hintergrund über den gemeinsamen Abruf (Vorrat, Takt, Pausen, Tagesgrenze für Hintergrundläufe, siehe Quellen), mit
`LUECKEN_ABSTAND_S` (10) Sekunden zwischen zwei echten Abfragen. Gefragt werden nur Sammlungen mit Platzhaltern und nur Sprachen,
in denen ein Band eine Nummer hat. Deutsch und ohne Sprache fragt die Nationalbibliothek (Verzeichnis 3, `TIT`, `PER`,
`MAT=books`, `SPR=ger`), ist sie abgeschaltet, der Verbundkatalog; jede andere Sprache der Verbundkatalog K10plus (Verzeichnis 4,
`pica.tit`, `pica.per`, die Sprache prüft der Abgleich), jeweils höchstens 100 Sätze. Gefragt wird nach dem Namen der Reihe, den
die Titel der Bände dieser Sprache am häufigsten nennen (wie beim Finden von Sammlungen, etwa "Lighthouse Quay, Book 2"), sonst
nach dem Namen der Sammlung, und nach ihrem häufigsten Autor; private Bücher gehen nie in eine Frage. Aus der Antwort zählen nur
Sätze, deren Reihe (490, 800/810/811 `$t`, 830, sonst 245 `$a` mit `$n`) gleich heißt (ohne Artikel, Groß und Klein, Umlaute und
Satzzeichen gleich) und deren Sprache nicht widerspricht. Die Zahl der Quelle ist der höchste Platz, den ein Band belegt; je Band
gilt der Satz mit ISBN und Titel, der neueste zuerst (Doppel- und Zwischenbände geben keine Angaben für einen Platz).

Nach der Antwort (auch ohne Fund) und nach einem Fehler wird diese Sammlung in dieser Sprache nie wieder von selbst gefragt.
Macht die Quelle Pause oder ist die Tagesgrenze erreicht, bleibt das Offene offen und der Auftrag ruht mit Grund. Angestoßen beim
Start, wenn jemand die Lücken einer Sammlung mit Offenem ansieht und im Takt `LUECKEN_TAKT_S` (600); nach einem Neustart geht er mit
dem Offenen weiter. Nach einem Fehler oder einem neuen Namen fragt `POST .../nachschlagen` auf Wunsch neu; eine gleiche Frage
beantwortet der Vorrat, ohne die Quelle zu fragen.

**Suchadresse**: eine Vorlage in `app_settings` (`luecken_suchadresse`), anfangs leer (dann im Feld nur Kopieren). Platzhalter:
`{titel}` (ohne bekannten Titel "Reihe Band n", etwa "Leuchtfeuerkai Band 9"), `{autor}` (der Quelle, sonst der häufigste der
Bände dieser Sprache, sonst der Sammlung), `{isbn}` (nur Ziffern, unbekannt leer), `{band}`, `{reihe}` (Name der Reihe in dieser
Sprache, `Reihe.reihe`), `{sprache}` (Kürzel); `{nummer}` und
`{sammlung}` gelten als andere Namen für `{band}` und `{reihe}`. Erlaubt: http oder https mit Rechner, geschweifte Klammern nur um
einen bekannten Platzhalter (sonst 422 mit Grund). Die Werte werden für eine Adresse kodiert (Leerzeichen `%20`, Umlaute in UTF-8,
`&`, `/`, `#`, `+`, `%` als `%26`, `%2F`, `%23`, `%2B`, `%25`); in den festen Teilen der Vorlage nur, was in einer Adresse nicht
stehen darf.

| Weg | Zweck |
|---|---|
| `GET /api/collections/{id}/luecken` | die Lücken der Sammlung, wie das Profil sie sieht: `Sammlungsluecken`; stößt das Nachschlagen an, wenn etwas offen ist. Unbekannt 404 |
| `PATCH /api/collections/{id}/luecken` `{an?, gesamt?: [{sprache, wahl, zahl?}]}` | Platzhalter an oder aus; je Sprache die Zahl: `wahl` `quelle`, `eigene` (mit `zahl` 1 bis 9999) oder `keine` (ohne `zahl`), sonst 422. Antwort wie `GET` |
| `POST /api/collections/{id}/luecken/ausblenden` `{sprache, nummer, grund}` | `grund` `gibt_es_nicht` oder `brauche_ich_nicht`; der Platzhalter verschwindet (nochmal: neuer Grund). Antwort wie `GET` |
| `POST /api/collections/{id}/luecken/zurueckholen` `{sprache, nummer}` | holt ihn zurück; war er nicht ausgeblendet: 404 `"Diese Lücke ist nicht ausgeblendet"`. Antwort wie `GET` |
| `POST /api/collections/{id}/luecken/nachschlagen` | alle Sprachen der Sammlung wieder offen, der Auftrag fragt sie (einmal). Antwort wie `GET` |
| `GET /api/luecken/einstellungen` | `{suchadresse, platzhalter: [{name, bedeutung}]}`; `platzhalter` in der Folge zum Anbieten, ohne die anderen Namen |
| `PUT /api/luecken/einstellungen` `{suchadresse}` | setzen (leer: keine Suche), Fähigkeit `einstellungen`; 422 mit Grund, etwa `"Suchadresse: unbekannter Platzhalter {titl}, erlaubt sind ..."`. Antwort wie `GET` |
| `POST /api/luecken/suchadresse/probe` `{suchadresse}` | `{adresse, sammlung, luecke}`: die fertige Adresse mit dieser Vorlage für einen fehlenden Band, den das Profil sieht (der erste mit bekanntem Titel, sonst der erste); merkt nichts. Ohne Lücke oder ohne Vorlage `adresse` null |
| `GET /api/luecken/stand` | der Auftrag: `{was: "Lücken nachschlagen", stand, gesamt, fertig, offen, aktuell, grund, begonnen, geaendert, fertig_am}`; `stand` `wartet` (Offenes, noch nicht dran), `laeuft`, `ruht` (Offenes, aber Pause, Tagesgrenze oder keine Quelle eingeschaltet, Grund in `grund`), `fertig`; `gesamt` und `fertig` zählen Sammlung und Sprache des letzten Laufs, `offen` alles, was noch nie gefragt wurde; `aktuell` etwa `"Leuchtfeuerkai, Deutsch"` |

```
Sammlungsluecken: { sammlung_id, name, autor, an, reihen: [Reihe], ausgeblendet: [Ausgeblendet] }
Reihe:        { sprache, name, reihe, gesamt, herkunft, quelle_gesamt, eigene, nachschlagen, buecher, belegt, fehlen: [int], zeile, eintraege: [Platz] }
Nachschlagen: { stand, quelle, quelle_name, reihe, grund, am }
Platz:        { art: "buch" | "luecke", band, nummer, zwischen, buch_id, buch: <wie in buecher> | null, luecke: Luecke | null }
Luecke:       { sprache, nummer, titel, autor, isbn, jahr, quelle, kopieren, suchadresse }
Ausgeblendet: { sprache, name, nummer, grund, grund_text, titel, am }
```

| Feld | Bedeutung |
|---|---|
| `autor` | der häufigste erste Autor der Bücher, die das Profil sieht ("Vorname Nachname"), leer ohne |
| `an` | Platzhalter im Regal; aus: keine Lücken (`fehlen` leer, nur Bücher in `eintraege`), die Bücher stehen weiter je Sprache, die Zahlen bleiben fürs Formular. Auch als `luecken` (1 oder 0) in `GET /api/collections` und `GET /api/collections/{id}` |
| `reihen` | je Sprache der Bücher, die das Profil sieht |
| `sprache`, `name` | Kürzel (leer: kein Buch nennt eine) und Name zum Anzeigen ("Deutsch", "Englisch", "Sprache unbekannt") |
| `reihe` | Name der Reihe in dieser Sprache: den die Titel der Bände, die das Profil sieht, am häufigsten nennen (ohne private), sonst der der Sammlung; so steht sie in `kopieren` und `{reihe}` |
| `gesamt`, `herkunft` | die Zahl, die gilt, und woher: `quelle`, `eigene`, `keine` (ausdrücklich ohne), leer (es gibt keine) |
| `quelle_gesamt`, `eigene` | was die Quelle sagt (auch wenn die eigene Angabe gilt) und die eigene Angabe |
| `nachschlagen.stand` | `offen` (wird gefragt; `grund`, wenn keine Quelle eingeschaltet ist), `fertig` (gefragt; ohne Fund `grund` `"Die Quelle kennt die Reihe nicht"`), `fehler` (gefragt, keine Antwort, `grund` von der Quelle), `nicht` (wird nicht gefragt: Platzhalter aus oder kein Band dieser Sprache mit Nummer) |
| `nachschlagen.quelle`, `quelle_name`, `reihe`, `am` | wer gefragt wird oder wurde (`dnb`, Verzeichnis 3), nach welchem Namen, wann |
| `buecher`, `belegt` | Bücher dieser Sprache, die das Profil sieht, und die Plätze der Zählung, die sie belegen (für "8 von 12") |
| `fehlen`, `zeile` | die fehlenden Nummern und der Satz dazu, etwa `"es fehlen 4, 9, 11 und 12"` (drei und mehr in Folge als "6 bis 9"); leer ohne Lücke |
| `eintraege` | Bücher und Lücken in der Folge der Bände (Zwischenbände hinter ihrem Band, ohne Zahl dahinter, ohne Band zuletzt; gleiche Nummer nach Titel) |
| `Platz.band`, `nummer`, `zwischen` | die Nummer, wie sie am Buch steht (bei einer Lücke die Zahl), der erste Platz (leer: ohne Zahl), ob es ein Zwischenband ist |
| `Luecke.titel`, `autor`, `isbn`, `jahr`, `quelle` | Angaben der Quelle zum Band, so weit bekannt (`titel` leer: unbekannt; `autor` sonst der häufigste der Bände dieser Sprache, sonst der Sammlung; `isbn` mit Strichen, wenn gültig; `quelle` leer: nur aus den eigenen Nummern) |
| `Luecke.kopieren` | eine Zeile zum Kopieren: `"Der stille Kai, Henrike Sandvoss, Leuchtfeuerkai Band 4, ISBN 978-3-99999-004-0"`, ohne Titel `"Leuchtfeuerkai Band 9, Henrike Sandvoss"` |
| `Luecke.suchadresse` | die fertige Adresse nach der Vorlage, null ohne Vorlage |
| `Ausgeblendet` | zum Zurückholen: `grund` und `grund_text` ("Gibt es nicht", "Brauche ich nicht"), `titel` aus der Quelle, wenn bekannt |

**Sammlungsvorschläge**: `luecken` in `GET /api/collections/vorschlaege` ist eine kurze Zeile nur aus den erkannten Bandnummern der
Bücher des Vorschlags, ohne Abfrage einer Quelle: `"vorhanden 1 bis 5 und 8, es fehlen 6 und 7"` (Lücken nur zwischen dem ersten
und dem letzten Band). Je Sprache gezählt; bei mehreren Sprachen je Sprache mit Lücken ein Teil mit ihrem Namen, getrennt durch
Semikolon (`"Deutsch: vorhanden 1 bis 3 und 5, es fehlt 4; Englisch: vorhanden 1 und 3, es fehlt 2"`). Leer ohne Lücke und für
Profile ohne die Fähigkeit `luecken`.

**Hochladen in eine Lücke**: über die Vorschau (BF-80) mit `POST /api/annahme/vorschau` `{name, vorgabe: {sammlung_id, band,
sprache}}`; Sammlung, Band und Sprache stehen dann mit Herkunft `luecke` in den Feldern (die Sprache der Datei geht vor, Herkunft
`datei`). Passt die Datei nicht zur Lücke, steht ein Hinweis mit Herkunft `luecke` in `felder.hinweise`: andere Sprache (`"Die
Datei ist englisch, die Lücke deutsch"`), ein anderer Band im Titel oder Dateinamen (`"Die Datei nennt Band 5, die Lücke ist Band
4"`), ein anderer Titel als der, den die Quelle für die Lücke kennt (`"Die Datei heißt X, die Lücke Y"`; verglichen wie bei den
Quellen, auch ohne Reihe und Band vorn im Titel). Ändern lässt sich alles; erst die Bestätigung übernimmt. Ein Stapel in die
Sammlung (`vorgabe` mit `sammlung_id`, ohne `band`): der Band kommt aus Reihe und Nummer im Titel oder Dateinamen (`regel`,
`datei`), sonst aus dem Titel, wenn die Quelle einen Band dieser Sprache sicher so nennt (`luecke`, Grund `"Band 4 heißt in den
Quellen so"`); sonst bleibt er leer und das Buch kommt beim Übernehmen hinten an.

Tabellen: `collections.luecken` (1 an, Vorgabe), `reihe_sprache` (`sammlung_id`, `sprache`, `wahl`, `eigene`, `quelle_gesamt`,
`quelle`, `gefragt`, `stand` offen/fertig/fehler, `grund`, `nachgeschlagen_am`), `reihe_band` (`sammlung_id`, `sprache`, `nummer`,
`titel`, `autor`, `isbn`, `jahr`, `quelle`), `luecke_ausgeblendet` (`sammlung_id`, `sprache`, `nummer`, `grund`, `am`); alle gehen
mit der Sammlung.

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

## Vorlesen über die Vertonung (BF-14)

Plan und Entscheidungen in [STIMMEN.md](STIMMEN.md); gebaut in `backend/app/vorlesen/` (`zugang.py` Adresse und Verbund, `stimmen.py`,
`sprechen.py`, `beschreibung.py` mit den deutschen Namen in `beschriftungen.json`, Formen in `modelle.py`), Wege in
`backend/app/api/vorlesen.py`. Gesprochen wird nur von der Vertonung (`VERTONUNG_URL` oder Anschlüsse, Vertonung), angemeldet mit dem
App-Zugang der Kellerwolke über den Verbund des Appkerns (`appkern.verbund`); Form der Stimmen, Teile und Zeilen kommen aus dem
Baustein `appkern.vorlesen`. Ohne Vertonung bleibt die Stimme des Geräts als ausdrückliche Wahl, die spricht die Oberfläche selbst.

**Stimmen** heißen, wie die Vertonung sie schreibt: `katalog:<name>` (eingebaut) oder die Kennung einer Klonstimme (UUID, privat oder
fremd). Dazu `geraet` (die Stimme des Geräts, für Ansagen und Kinder) und im Leser `geraet:<Name der Stimme im Browser>`. Frühere
Werte `katalog:<name>` gelten unverändert, die Vertonung schreibt ihre eingebauten Stimmen genauso.

| Weg | Zweck |
|---|---|
| `GET /api/vorlesen/stimmen` | `Stimmenliste`, jedes Mal neu aus der Vertonung (`GET /api/v1/stimmen` je Bereich) |
| `GET /api/vorlesen/beschreibung` | `Beschreibung`: was die Vertonung zum Sprechen anbietet |
| `POST /api/vorlesen` `{text, stimme}` | der Strom Satz für Satz (NDJSON), mit den Werten des aktiven Profils |
| `PATCH /api/familie/ich/vorlesen` `{stimme?, werte?}` | ein Erwachsener wählt im Leser seine Stimme und seine Werte, was fehlt, bleibt; Antwort `Vorlesestand`; Kinder 403 |

```
Stimmenliste:  { da, stimmen: [Stimme], bereiche: [Bereichsstand], hinweis }
Stimme:        { id, name, bereich: "privat" | "fremd" | "katalog", sprache }
Bereichsstand: { bereich, frei, hinweis }
Beschreibung:  { da, felder: [Feld], hinweis }
Feld:          { schluessel, name, art: "zahl" | "ganzzahl" | "schalter" | "text" | "wahl", von, bis, vorgabe, werte: [{wert, name}],
                 erklaerung, mehr }
Vorlesestand:  { stimme, werte, eigene_wahl }
```

- **Bereiche** in der Folge der Vertonung: privat, fremd, katalog. Gibt sie BücherFreunde keine privaten Stimmen frei (401 oder 403 nur
  für diesen Bereich), steht `privat` mit `frei` false und `hinweis` da: ihr Grund und "Freigabe in der Vertonung unter Private
  Stimmen für"; die übrigen Bereiche kommen trotzdem. Antwortet sie nicht, `da` false mit `hinweis`; ohne eingetragene Vertonung `da`
  false ohne Hinweis. `sprache` ist die Sprache der Probe einer Klonstimme.
- **Strom**: der Text geht in Teilen bis 7500 Zeichen an Satzgrenzen an `POST /api/v1/sprechen/strom` (die Vertonung nimmt 8000), mit
  `ausschreiben` true, den Werten des Profils und der Stimme (`{art: katalog, name}` oder `{art: klon, knoten_id}`; ohne Stimme ihre
  Stimme ab Werk). Zeilen `{art: satz, nr, text, gesprochen, von_zeichen, bis_zeichen, dauer_ms, ton}` (Ton als Base64-WAV, `nr`
  über alle Teile), zuletzt `{art: ende, saetze, dauer_ms}`. Was vor dem ersten Satz scheitert, ist eine Antwort mit Grund: 403, wenn
  die Vertonung ablehnt (nie 401), 503 ohne Vertonung oder wenn sie nicht erreichbar ist, 400 für eine Stimme, die sie nicht spricht
  (auch `geraet`); danach eine Zeile `{art: fehler, meldung}`.
- **Kurze Texte** (feste Ansagen, Probe) gehen an `POST /api/v1/sprechen` und kommen als eine WAV.
- **Beschreibung**: aus dem Schema der Vertonung (`GET /api/v1/schnittstelle`, Modell der Anfrage an den Strom); jedes Feld außer
  `text` und `stimme` ist eine Einstellung mit Art, Grenzen (`minimum`, `maximum`) und Vorgabe. Namen aus `vorlesen/beschriftungen.json`;
  ein Feld, das dort fehlt, behält den Namen der Vertonung und hat `mehr` true. Listen und Objekte bleiben weg. Zeigt die Vertonung ihr
  Schema nicht (heute nur Menschen in ihrer Oberfläche, 403 für Apps), ist `da` false mit Hinweis.
- **Je Profil** in `profil.einstellungen.vorlesen` `{stimme, werte}`: Werte gelten nur, wenn sie zur Beschreibung passen (422 sonst, auch
  ohne Beschreibung); leer geht immer. Ein Kind hat dort keine Stimme (422), seine steht in `lesehilfen.stimme`; seine Werte setzen die
  Eltern mit `PATCH /api/familie/profile/{id}` `{einstellungen: {vorlesen: {werte}}}`. Die Werte gehen mit jedem Strom des Profils an
  die Vertonung; für die festen Ansagen gelten sie noch nicht. Bedienelemente für die Werte gibt es erst mit einem Entwurf.
- **Verbindungen**: `GET /api/verbindungen` nennt die Vertonung (`kennung` vertonung): `gut` mit der Zahl der Stimmen, `warn` mit dem
  Hinweis, wenn private Stimmen nicht frei sind, `schlecht`, wenn sie nicht antwortet.

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
  lesezeile, schrift, schrift_wahl, hinweise_sprechen, tasten_ansagen, stimme}, lesezeit: {an, minuten, ruhe_an, ruhe_von, ruhe_bis, vorlesen_zaehlt}, katze: {an, name, schnurren,
  name_eingabe}, gestaltung, uhr, vorlesen: {stimme, werte}}` (`vorlesen` siehe Vorlesen über die Vertonung); ohne Wahl der Eltern gelten die Lesehilfen, Katze, Gestaltung und Uhr der Stufe und die
  Lesezeit nach dem Alter. Beim Anlegen und Ändern ersetzt jeder genannte Teil von `einstellungen` den gespeicherten, die übrigen
  bleiben. `schrift`: klein, mittel, gross (Anteil an der Größe der Stufe, `gestaltung.schriftgroessen`). `GET /api/familie/profile/{id}` gibt ein Profil einzeln.
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
  Der Schnellfilter der Liste (`suche=`) und die Suche im Buch brauchen `suche`. Lücken in Sammlungen (BF-75) brauchen `luecken`,
  das nur Verwaltung und Erwachsen haben; keine Stufe eines Kindes nennt es.
- **Fertig gelesen** (eine Regel, `familie/lesestand.py`): ein Buch ist fertig, sobald sein Lesestand das Ende erreicht oder
  `lesestand.fertig_ab` aus `stufen.json` (0,99), oder wenn es mit `PATCH /api/books/{id}/gelesen` markiert ist; es bleibt
  fertig, auch wenn man zurückblättert, bis die Markierung zurückgenommen wird. Gelesen wird der Anteil wie in der Oberfläche
  (Seite durch Seiten, sonst Prozent, sonst Anteil des Rollens; eine Stelle nur mit CFI sagt nichts). Am Buch steht
  `fertig_am` (leer: noch nicht); es gilt für den Filter `gelesen`, den Zähler `gelesen` in `GET /api/config/stats`, den
  Rückblick des Kindes und den Einblick der Eltern (`fertig`, dann Fortschritt 1). `last_read_at` bleibt der Zeitpunkt des
  letzten Lesens. Beim Start bekam jeder bisherige Lesestand `fertig_am` nach der Regel; als gelesen markiert galt dabei ein
  Buch mit Zeitpunkt ohne Lesestand.
- **Gestaltung (BF-88)**: der Kinderbereich hat zwei Gestaltungen, `gestaltung` `klein` (verspielt, große Tasten) und `gross`
  (ruhig im Stil der App). Vorgabe je Stufe in `stufen.json`: klein für Vorlesen und Erstes Lesen, groß für Lesen und Lernen und
  Schule; Jugend hat keine (null) und liest in der Oberfläche der App, dort wirkt keine Wahl. Die Eltern stellen sie je Kind um
  (`einstellungen.gestaltung`); was das Kind darf, bleibt an der Stufe. In Groß sind Katze (`katze_an` der Stufe) und Ansagen
  anfangs aus. `uhr`: die Uhr im Kopf der Gestaltung groß, `zeiger` oder `zahl`, Vorgabe Zeiger für Lesen und Lernen, Zahl für
  Schule (`einstellungen.uhr`). `lesehilfen.schrift_wahl`: `normal` (Schriftart und Abstände aus `gestaltung.normalschrift`,
  die gut lesbare serifenlose Leseschrift mit normalen Abständen) oder `kinderschrift` (die Darstellung der Stufe); Vorgabe
  Kinderschrift in Klein, normal in Groß. `darstellung` in `GET /api/familie/ich` ist damit schon eingerechnet.
  `PATCH /api/familie/ich/schrift {schrift_wahl}`: das Kind schaltet beim Lesen selbst um, nur in der Gestaltung groß (sonst 403,
  dann wählen die Eltern); es ändert nur die Leseschrift und antwortet mit dem neuen Ich.
- **Hinweise sprechen, Tasten ansagen**: `lesehilfen.hinweise_sprechen` und `lesehilfen.tasten_ansagen`, Vorgabe an in Vorlesen
  und Erstes Lesen, aus ab Lesen und Lernen (Gestaltung groß); die Eltern ändern beides. `lesehilfen.stimme`: eine Stimme der Vertonung
  (`katalog:<name>` oder die Kennung einer Klonstimme, privat oder fremd, aus `GET /api/vorlesen/stimmen`), `geraet` für die Stimme des
  Geräts (nur für Installationen ohne Vertonung, immer eine ausdrückliche Wahl, nie ein stiller Rückfall) oder leer: die Vorlesestimme
  der Familie. Sie gilt für die Ansagen und das Vorlesen des Kindes. Gibt es keine, schweigen die Ansagen und der Elternbereich zeigt
  "Stimme wählen".
- **Feste Ansagen** (`familie/ansagen.json`, `familie/ansagen.py`): vorab gesprochen über die Vertonung mit der gewählten Stimme und dauerhaft im
  Ort texte unter `ansagen/<ordner der stimme>/<schluessel>-<pruefsumme>.wav` (Prüfsumme aus Fassung und Text: ein geänderter
  Text gibt einen neuen Ton). Die Schlüssel heißen `gruppe.name`:
  - `tasten.<name>`: weiter, zurueck, pause, vorlesen, silben_an, silben_aus, zeile_an, zeile_aus, mein_regal, lieblinge,
    gelesen, schloss, zum_regal, stift_an, stift_aus, gemerkt, lesezeichen_weg, notiz, lieblingsbuch, kein_lieblingsbuch, fertig,
    kinderschrift_an, kinderschrift_aus;
  - `hinweise.<name>`: lesezeit_gleich_um, lesezeit_um, bild_pin ("Tippe drei Bilder an.", die Zahl aus `zugang`),
    bild_pin_falsch, katze_benennen, frag_eltern, wer_liest, buch_fertig, regal_leer, lieblinge_leer, gelesen_leer, suche_leer;
  - Bausteine der Uhr, Zahlen als deutsche Wörter: `uhr.1` bis `uhr.12` ("Es ist vier Uhr"), `minute.1` bis `minute.59`
    ("fünfunddreißig"), `noch.1` bis `noch.120` ("Noch eine Minute", "Noch fünfundzwanzig Minuten"), `heute.1` bis
    `heute.120`; die Uhrzeit setzt die Oberfläche daraus zusammen;
  - aus den Dingen: `titel.<buch>` für jedes Buch, das das Kind sieht (erst nach der Freigabe), `katze` (der Name seiner Katze),
    `katze.<vorschlag>` im Vorlesealter (die Vorschläge aus `stufen.json`, `katze.vorschlaege`), `ruhezeit` ("Jetzt ist
    Ruhezeit. Ab sechs Uhr dreißig kannst du wieder lesen.", mit dem Ende seiner Ruhezeit), `profil.<profil>` (die Namen für
    "Wer liest?", in der Stimme der Familie); `probe` ist der Probesatz.
- **Ansagen erstellen** (`familie/ansagelauf.py`): ein Auftrag im Hintergrund über die Vertonung (`POST /api/v1/sprechen`), je
  Stimme nur, was fehlt; angestoßen nach der Wahl einer Stimme, nach Freigaben, dem Namen der Katze, Anlegen, Ändern und
  Löschen von Profilen und einem neuen Titel, beim Start und im Takt `ANSAGEN_TAKT_S` (600). Nach einem Neustart geht er mit dem
  weiter, was fehlt. Wechselt ein Hörer (ein Kind oder die Profilwahl) die Stimme, entstehen seine Ansagen in der neuen; bis sie
  ganz sind, gilt je Ansage der Ton der bisherigen (Tabelle `ansage_hoerer`: je Hörer die Stimme, die er zuletzt ganz hatte). Alte
  Töne einer Stimme räumt er erst weg, wenn die neuen fertig sind und niemand sie mehr braucht; die Probe bleibt. Ohne Vertonung
  steht der Grund am Auftrag.
- **Wege der Ansagen**:
  - `GET /api/familie/ansagen`: `{stimme, fertig, gesamt, laeuft, eintraege: {schluessel: {text, url}}}` für das aktive
    Profil, ohne Profil für die Profilwahl (Hinweise, Tasten, Uhr, `profil.<id>`); nur fertige Einträge, nach einem Wechsel der
    Stimme je Eintrag auch der Ton der bisherigen, bis die neue ihn ersetzt. Mit der Stimme des Geräts alle Texte mit `url` null,
    ohne Stimme keine.
  - `GET /api/familie/ansagen/ton/{ordner}/{datei}`: der Ton (`audio/wav`, `Cache-Control` ein Jahr, `immutable`, `ETag`, 304
    auf `If-None-Match`), ohne Kopf über die Cookies der Anmeldung und der Wahl. Ein Kind nur für seine Stimme, die Profilwahl
    nur für die der Familie, beide bis zum Ersatz auch für die bisherige; Erwachsene jede (403 sonst).
  - `POST /api/familie/ansagen/probe {stimme}` für Erwachsene mit `profile` oder `freigeben`: `{text, url}` des Probesatzes
    ("Hallo, ich lese dir vor. Tippe auf ein Buch."), gesprochen von der Vertonung und abgelegt wie die Ansagen; mit `geraet` nur
    der Text; ohne Vertonung 503 mit Grund.
  - `GET /api/familie/ansagen/stand?stimme=`: `[{was: "Ansagen erstellen", stimme, stand (wartet, laeuft, fertig, fehler),
    gesamt, fertig, grund, begonnen, geaendert, fertig_am}]`, ebenso nur für Erwachsene mit `profile` oder `freigeben`.
- **GET /api/familie/ich**: `{profil, faehigkeiten, darstellung, lesehilfen, lesezeit, katze, einblick, gestaltung, uhr, vorlesen}`
  (`vorlesen`: Stimme und Werte, mit denen das Profil vorgelesen bekommt, siehe Vorlesen über die Vertonung); für
  Erwachsene `darstellung` `{}`, `lesehilfen` null, `lesezeit.an` false, `katze.an` false, `einblick` leer, `gestaltung` und `uhr`
  null. `lesezeit`: `{an, heute_s, grenze_s, rest_s, hinweis_ab_s, ruht, ruhe_bis}`. `PATCH /api/familie/ich/katze {name}`
  antwortet mit der Katze, `PATCH /api/familie/ich/schrift {schrift_wahl}` mit dem Ich (Gestaltung).
- **GET /api/familie/stufen**: `{stufen: [{schluessel, name, alter, alter_von, alter_bis, faehigkeiten, einblick, darstellung,
  lesezeichen_je_buch, vorgaben: {lesehilfen, lesezeit, katze, gestaltung, uhr}}], lesezeit: [{alter_von, alter_bis, minuten, an}], rollen,
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

## Ersteinrichtung (BF-82)

Plan und Entscheidungen in [EINRICHTUNG.md](EINRICHTUNG.md); gebaut in `backend/app/einrichtung/` (`zustand.py` Zustand und
Schritte aus `schritte.json`, `zugang.py` wer darf, `orte.py`, `anschluesse.py`, `katalog_schritt.py`, `wartung.py` Änderungen
erst nach Bestätigung, `wiederherstellen.py`, `pruefung.py`, `neuaufbau.py`, `profildatei.py`, `umzug.py`, `kopieren.py`,
`nachfuehren.py`, `hochladen.py`, `auftrag.py`, Formen in `modelle.py`, Tabellen in `schema.py`), der Schlüsselbund in
`core/schluessel.py`, der Auszug in `ablage/auszug.py`, der Begleiter mit dem Persönlichen in `ablage/persoenlich.py`, Sicherungen in
der Kellerwolke in `ablage/sicherungen.py`, Wege in `backend/app/api/einrichtung.py` (und `api/backup.py` für das Zurückspielen).

**Neu oder laufend**: neu ist eine Installation nur, wenn beim ersten Start der Bestand leer war und keine Markerdatei trug
(`ablage/orte.py`); gemerkt einmal in der Tabelle `einrichtung` (`modus` `neu`). Jede andere bekommt beim ersten Start mit dieser
Fassung `aus` und sieht den Assistenten nie von selbst; Wege, die nur die Ersteinrichtung kennt, antworten dort 409.

**Wer darf**: solange eine neue Installation kein Konto hat (kein eigenes Konto angelegt, keine Kellerwolke mit App-Zugang
eingetragen), sind die Wege unter `/api/einrichtung` ohne Anmeldung erreichbar, wie das Anlegen des ersten Kontos. Danach braucht
jeder Weg die Anmeldung mit Profil und die Fähigkeit `einstellungen` (401, 403). `GET /api/einrichtung` geht immer; ohne Anmeldung
und auf einer eingerichteten Installation kommt nur `{modus: "aus", zeigen: false}`.

**Wege, die eine Adresse ansprechen** (`.../anschluesse/{art}/pruefen`, `PUT .../anschluesse/{art}`, `.../konto/kellerwolke`,
`.../umzug/verbinden`), nehmen vor dem ersten Konto nur `https` mit einem Namen an: keine IP-Adresse, nicht `localhost` oder
`*.localhost`, kein Port unter 1024 außer 443 (422 `"Adresse: ..."`), und höchstens `EINRICHTUNG_PRUEFUNGEN_JE_MINUTE` (6) in der
Minute (429 mit `Retry-After`). Nach dem ersten Konto gelten sie nur angemeldet, ohne diese Grenzen.

**Schritte** (`schritte.json`, eine Datei, keine Regeln im Code):

| Ausgangslage | Schritte |
|---|---|
| `neu` (Neu beginnen) | `konto`, `orte`, `anschluesse`, `katalog`, `familie`, `buecher`, `abschluss` |
| `sicherung` (Aus Sicherung wiederherstellen) | `orte`, `sicherung`, `pruefung`, `abschluss` |
| `kellerwolke` (Ablage in der Kellerwolke übernehmen) | `konto`, `orte`, `ordner`, `neuaufbau`, `abschluss` |
| `umzug` (Umzug von einer anderen Installation) | `verbinden`, `orte`, `originale`, `pruefung`, `abschluss` |
| Wartung (wieder geöffnet) | `orte`, `anschluesse`, `katalog`, `familie`, `buecher`, `abschluss` |

Pflicht sind `konto`, `orte`, `sicherung`, `ordner`, `neuaufbau`, `verbinden`, `originale`, `pruefung` und `abschluss`; die übrigen
lassen sich überspringen. `konto` ist erledigt, sobald es ein Konto gibt. Beim Wiederherstellen und beim Umzug gibt es keinen
Schritt Konto: Konto und Profile kommen aus der Sicherung (bringt sie keins mit, verlangt der Abschluss eins, 409). `originale`
entfällt mit Kellerwolke (`stand` `entfaellt`). `sicherung` und `verbinden` sind erledigt, wenn der Auftrag "Sicherung einspielen"
fertig ist, `ordner` und `originale`, sobald sie gelaufen sind; `pruefung` und `neuaufbau` erst, wenn ihr Auftrag fertig ist und man
Weiter wählt.

```
Einrichtung: { modus: "neu" | "wartung" | "aus", zeigen, ausgangslage, schritt, schritte: [Schritt], ausgangslagen: [Ausgangslage],
               konto, anmeldung: "eigen" | "kellerwolke", aenderungen, begonnen_am, abgeschlossen_am }
Schritt:     { schluessel, name, pflicht, stand: "offen" | "erledigt" | "uebersprungen" | "entfaellt", text, weiter, grund }
Ausgangslage:{ schluessel, name, beschreibung, schritte: [str] }
```

`zeigen`: die Oberfläche öffnet den Assistenten statt der Anmeldung (neue Installation) oder als Bühne (Wartung). `schritt`: der
erste offene Schritt, dort geht es nach einem Neustart weiter. `weiter` false mit `grund`, wenn Weiter gesperrt ist (etwa eine
Platte fehlt). `text` sagt, was eingerichtet ist ("Leer begonnen") oder dass übersprungen wurde, für die Übersicht am Ende.

| Weg | Zweck |
|---|---|
| `GET /api/einrichtung` | der Zustand (siehe oben) |
| `POST /api/einrichtung/ausgangslage` `{ausgangslage}` | wählen; wechseln geht, solange nichts aus Sicherung, Umzug oder Kellerwolke übernommen ist und keine Bücher da sind (sonst 409) |
| `POST /api/einrichtung/schritte/{schritt}` `{aktion: "erledigt" \| "ueberspringen"}` | Weiter oder Überspringen; Pflicht überspringen 422, gesperrtes Weiter 409 mit Grund, `konto` und `abschluss` von Hand 422, ein Schritt außerhalb der Ausgangslage 404 |
| `POST /api/einrichtung/abschliessen` | nur, wenn jede Pflicht erledigt ist (sonst 409 "Noch offen: ..."); danach `modus` `aus`. Mit Katalog "aus dem Bestand" und Büchern beginnt der Entwurf aus dem Bestand |
| `GET /api/einrichtung/uebersicht` | `[Schritt]`: was eingerichtet und was übersprungen ist, auch nach dem Abschluss |
| `GET /api/einrichtung/orte` | `{orte: [{kennung, name, pfad, belegt, frei, stand, dauerhaft, marker, text}], weiter, grund}`; misst jedes Mal neu ("Neu suchen"). `stand` `schlecht` mit `text`: Ordner fehlt, nicht schreibbar, ohne Markerdatei. Die Pfade kommen aus der Einrichtung (.env), ändern sich nur mit einem Neustart |
| `POST /api/einrichtung/konto/kellerwolke` `{adresse, schluessel}` | Schritt Konto mit der Kellerwolke: prüft den App-Zugang, trägt Adresse und Schlüssel ein und stellt die Anmeldung auf die Kellerwolke um (ohne Neustart); Antwort `{anmeldung, app, besitzer}`. Danach meldet man sich mit `POST /api/anmeldung` an. Nur ohne Konto (sonst 409); Prüfung gescheitert 422 `"Verbindung: ..."`. Das eigene Konto legt wie bisher `POST /api/anmeldung/einrichten` an |

### Anschlüsse

```
Anschluss: { art: "kellerwolke" | "leitstelle" | "vertonung" | "nachschlag", name, adresse, herkunft: "app" | "einrichtung" | "",
             schluessel: { eingetragen, herkunft: "app" | "einrichtung" | "", vorgemerkt } | null, hinweis, pruefung: Verbindungspruefung | null }
Verbindungspruefung: { ok, text, grund, am }
```

`herkunft` der Adresse: `app` in der App eingetragen (`app_settings` `anschluss_<art>`, gilt vor der .env), `einrichtung` aus der
.env, leer keine. `schluessel` null: dieser Anschluss hat keinen (Vertonung und Nachschlag; sie kennen die App über ihren Zugang der
Kellerwolke). Die Prüfung der Vertonung fragt ihre Stimmen je Bereich wie das Vorlesen.
`hinweis` bei der Kellerwolke: dass Persönliches je Buch dort liegt und wer die Kellerwolke verwaltet, es lesen könnte. `pruefung`:
die letzte Prüfung seit dem Start; `text` etwa `"BücherFreunde, Konto mira"`, `"KI mit 2 Modellen"`, `"Stimmen: 9 eingebaut, 2 fremd"`
(dazu der Hinweis, wenn private Stimmen nicht frei sind), `"12 Lexika und Handbücher"`, `grund` etwa `"Die Kellerwolke kennt diesen
App-Zugang nicht"`.

| Weg | Zweck |
|---|---|
| `GET /api/einrichtung/anschluesse` | `[Anschluss]`, nie ein Schlüssel |
| `POST /api/einrichtung/anschluesse/{art}/pruefen` `{adresse?, schluessel?}` | "Verbindung prüfen" mit den genannten Werten, sonst den eingetragenen; merkt nichts als das Ergebnis |
| `PUT /api/einrichtung/anschluesse/{art}` `{adresse, schluessel?}` | eintragen: erst prüfen, nur bei Erfolg gilt es (sonst 422 `"Verbindung: <grund>"`, der alte Schlüssel bleibt). Ohne `schluessel` gilt der eingetragene; der Nachschlag nimmt keinen (422). Antwort `Vorgemerkt` |

**Schlüsseldatei** (`core/schluessel.py`): ein Schlüssel aus der App liegt in der eigenen Schlüsseldatei des Servers
(`SCHLUESSEL_DATEI`, ohne Angabe `schluessel.json` beim Bestand; JSON, Modus 0600, geschrieben über eine Teildatei, nie in einer
Sicherung) und gilt vor der Datei aus der Einrichtung (`KELLERWOLKE_SCHLUESSEL_DATEI`, `LEITSTELLE_SCHLUESSEL_DATEI`). Ohne Eintrag
in der App gilt die Datei der Einrichtung wie bisher; Kellerwolke, Anmeldung und Leitstelle lesen beide über dieselbe Stelle. Kein
Weg gibt einen Schlüssel zurück, die Oberfläche zeigt nur "eingetragen" und "Ersetzen".

### Katalog und Familie

| Weg | Zweck |
|---|---|
| `POST /api/einrichtung/katalog` `{wahl: "standard" \| "leer" \| "bestand"}` | der mitgelieferte Katalog, leer, oder der mitgelieferte mit Entwurf aus dem Bestand nach dem Abschluss; angenommen wie unter Einstellungen, Katalog (gleicher Schlüssel ändert, gelöscht wird nichts) |
| `POST /api/einrichtung/familie/profile` | wie `POST /api/familie/profile` (`ProfilNeu`); PIN und Bild-PIN danach über `PUT /api/familie/profile/{id}/pin` |
| `PUT /api/einrichtung/familie/stimme` `{stimme}` | wie `PUT /api/familie/stimme` |

Die drei brauchen das Konto (sonst 409). Erste Bücher kommen über die vorhandenen Wege (Vorschau, Eingangsordner, Ordner,
gemeinfreie Bücher); der Schritt wird mit `.../schritte/buecher` erledigt oder übersprungen.

`Vorgemerkt`: `{angewandt, aenderung: Aenderung | null}`; auf einer neuen Installation gilt alles sofort (`angewandt` true), unter
Wartung nur vorgemerkt (siehe Wartung).

### Wiederherstellen aus Sicherung

In der Ersteinrichtung nur in den Ausgangslagen `sicherung` und `umzug` und bei leerem Bestand (sonst 409); überschrieben wird nie
ein Buch, gelöscht nichts. Immer erst die Folgen, dann mit ihrem `stand` der Auftrag "Sicherung einspielen"; das Einspielen läuft
nie in der Anfrage. Eine Sicherung trägt seit BF-82 `inhalt.json` (Fassung, Zahl der Bücher und Profile); ältere werden zum Zählen
einmal ausgepackt. Abschnitte des Auftrags: `holen`, `pruefen` (ZIP, Datenbank, `integrity_check`, Tabelle `books`, in die Form
dieser Fassung gebracht in einem eigenen Ordner neben dem Bestand), `vorher` (nur beim Ersetzen: Sicherung des jetzigen Stands),
`einspielen` (über die Sicherung von SQLite in den laufenden Bestand, dazu die Angaben je Buch aus `metadata/`; der Stand der
Einrichtung bleibt der dieses Geräts), `danach` (Suchindex neu, Anschlüsse der Sicherung anwenden). Danach beginnt der Auftrag
"Originale prüfen" (beim Umzug ohne Kellerwolke erst nach der Wahl, wie die Originale kommen).

```
Sicherung:            { quelle: "datei" | "geraet" | "kellerwolke", kennung, name, groesse, angelegt_am, buecher, profile, version }
Hochladestand:        { id, name, groesse, sha256, empfangen, teil_groesse, fertig }
Wiederherstellfolgen: { sicherung: Sicherung, ersetzt: [Satz], vorher_sichern, stand }
```

| Weg | Zweck |
|---|---|
| `GET /api/einrichtung/sicherungen?quelle=geraet\|kellerwolke` | `{quelle, bereit, grund, sicherungen: [Sicherung]}`, neueste zuerst; `kennung` ist auf dem Gerät der Name, in der Kellerwolke der Knoten. Ohne Kellerwolke `bereit` false mit Grund |
| `POST /api/einrichtung/sicherungen/hochladen` `{name, groesse, sha256}` | eine Sicherung in Teilen hochladen, wie bei der Annahme; gleicher Name, Größe und Prüfsumme finden den angefangenen Stand wieder. Antwort `Hochladestand`; zu groß 413 (`WIEDERHERSTELLEN_MB_HOECHSTENS`) |
| `PATCH /api/einrichtung/sicherungen/hochladen/{id}` Kopf `Upload-Offset`, Körper roh | das nächste Teil (höchstens `teil_groesse`); 409 `{detail, empfangen}` nennt den wahren Stand, 413 bei mehr Daten als angesagt, 400 wenn das Teil nicht ganz ankam (dann gilt, was vorher da war). Beim letzten Teil prüft der Server die Prüfsumme: stimmt sie nicht, 422 und der Stand ist wieder 0 |
| `GET /api/einrichtung/sicherungen/hochladen/{id}` | der Stand, dort geht es weiter |
| `GET /api/einrichtung/wiederherstellen/folgen?quelle=datei\|geraet\|kellerwolke&kennung=` | was die Sicherung enthält und was sie ersetzt, als Sätze: gibt es schon ein eigenes Konto, `"Das Konto X wird durch das aus der Sicherung ersetzt"`, gibt es schon mehrere Profile, auch sie. `kennung` bei `datei` ist die `id` des Hochladens (409, solange es nicht fertig ist) |
| `POST /api/einrichtung/wiederherstellen` `{quelle, kennung, stand}` | nur mit dem `stand` der Folgen (422 ohne, 409, wenn sich seither etwas geändert hat); Antwort der `Auftragsstand` von "Sicherung einspielen" |
| `GET /api/einrichtung/wiederherstellen` | `{auftrag, ergebnis: {name, buecher, profile, version, vorher} \| null}` |

**Zurückspielen unter Einstellungen** (`api/backup.py`, Fähigkeit `einstellungen`, nicht während der Ersteinrichtung): dieselben
Folgen und derselbe Auftrag, die Sicherung ersetzt dann einen Bestand. `GET /api/backup/restore/folgen?quelle=&kennung=` nennt dazu
den Bestand (`"Der Bestand mit N Büchern, M Profilen, ... wird durch den der Sicherung ersetzt"`) und dass vorher eine Sicherung des
jetzigen Stands entsteht (`vorher_sichern` true); `POST /api/backup/restore` `{quelle, kennung, stand}` beginnt den Auftrag und
antwortet mit seinem Stand. Eine Datei kommt vorher in Teilen über `.../sicherungen/hochladen`. Die frühere Form (multipart, die
Datenbank sofort überschrieben) gibt es nicht mehr; die Oberfläche nutzte sie nicht.

**Sicherungen in der Kellerwolke**: jede neue Sicherung (regelmäßig, von Hand, beim Umzug) kommt auch nach
`Apps/BücherFreunde/Sicherung`, solange eingeschaltet (`sicherungen_ablegen`, Vorgabe `SICHERUNG_IN_KELLERWOLKE`), mit Bücher,
Profile und Fassung in den Feldern der Datei. Dort wird nie etwas gelöscht.

### Aufträge, Prüfung der Originale, Neuaufbau

```
Auftragsstand: { art, was, stand: "" | "wartet" | "laeuft" | "pause" | "fertig" | "fehler", gesamt, fertig,
                 teile: [{schluessel, name, gesamt, fertig}], aktuell, grund, begonnen, geaendert, fertig_am }
```

Jeder Auftrag arbeitet ein Stück nach dem anderen ab (`EINRICHTUNG_ABSTAND_S` Pause), lässt sich anhalten und fortsetzen und geht
nach einem Neustart am nächsten offenen Stück weiter. Antwortet eine Gegenstelle nicht, ruht er (`pause`) mit Grund. `stand` leer:
noch nie gelaufen. `teile` je Auftrag:

| `art` | `was` | `teile` |
|---|---|---|
| `einspielen` | Sicherung einspielen | `holen`, `pruefen`, `vorher` (nur beim Ersetzen), `einspielen`, `danach` |
| `pruefung` | Originale prüfen | `erreichbar`, `wiedergefunden`, `fehlt`, `texte` (Volltext oder Umschlag kamen aus dem Auszug) |
| `neuaufbau` | Neuaufbau aus der Kellerwolke | `buecher`, `angaben`, `volltext`, `umschlaege`, `persoenliches` |
| `kopieren` | Originale kopieren | `dateien`, `groesse` (Bytes), `fehler` (Prüfsumme stimmt nicht) |
| `nachfuehren` | Persönliches nachführen | `buecher`, `bytes` (so viel ging seit dem Start hinaus) |

| Weg | Zweck |
|---|---|
| `GET /api/einrichtung/auftraege` | alle fünf |
| `POST /api/einrichtung/auftraege/{art}/pause`, `.../fortsetzen` | für `einspielen`, `pruefung`, `neuaufbau`, `kopieren`; fortgesetzt wird an derselben Stelle (beim Einspielen am nächsten Abschnitt) |
| `POST /api/einrichtung/pruefung` `{pruefsummen}` | Prüfung von vorn (der alte Bericht fällt weg, Bücher bleiben); `pruefsummen` liest auch Originale auf dem Gerät ganz. Nur in der Ersteinrichtung (sonst 409), weil sie wiedergefundene Orte einträgt |
| `GET /api/einrichtung/pruefung/bericht?herunterladen=` | `{auftrag, erreichbar, wiedergefunden, fehlt, texte, eintraege: [{buch_id, titel, autor, ergebnis, ort, pfad, text}]}`; `eintraege` nur wiedergefundene und fehlende, nur Bücher, die das Profil sieht; mit `herunterladen` als `pruefbericht.json` |
| `POST /api/einrichtung/neuaufbau/ordner` `{pfad}` | Ordner der Bücher unter dem Ordner der App (Vorgabe `Bücher`): `{pfad, buecher, mit_auszug, ohne_auszug, mit_persoenlichem, schon_da, groesse, profile: [Namen aus der Datei der Profile], profile_datei}`; legt die Liste für den Auftrag an, in der Kellerwolke ändert sich nichts; unbekannter Ordner 404 |
| `POST /api/einrichtung/neuaufbau` | den Neuaufbau beginnen (braucht das Konto und eine geprüfte Liste) |
| `GET /api/einrichtung/neuaufbau/bericht` | `{auftrag, buecher, mit_auszug, ohne_auszug: [{buch_id, name, pfad}], fehler: [...], profile}` |

**Prüfung**: in der Kellerwolke zählt der Knoten mit derselben Prüfsumme (nichts wird geladen), auf dem Gerät die Datei. Fehlt ein
Original am alten Ort, sucht der Auftrag es über `GET /api/v1/ablage/pruefsumme/{sha256}` der Kellerwolke und trägt den neuen Ort
in `ablage_datei` ein (`wiedergefunden`). Fehlen auf dem Gerät Volltext, Umschlag oder Angaben, kommen sie aus dem Auszug zurück,
der Volltext auch in die Suche. Fehlende Bücher bleiben im Bestand; ihr Befund steht in `original_befund`, und `GET /api/books/{id}`
trägt dann `original: {text, geprueft_am}` (sonst `null`), damit die Buchseite den Hinweis zeigt.

**Neuaufbau**: Original ist jede Buchdatei ohne Rolle, ihre Begleiter `auszug` und `persoenlich`. Zuerst kommen die Profile aus
`Apps/BücherFreunde/profile.json` (ohne PIN und Bild-PIN; das Profil Verwaltung des Kontos übernimmt das erste Verwaltungsprofil der
Datei, sein Name bleibt der des Kontos), ohne Katalog der mitgelieferte. Je Buch dann aus dem Auszug: die Zeile in `books` (die
Nummer bleibt, wenn sie frei ist), Volltext, Seiten, Umschlag, Angaben, Regale nach Namen (fehlende als Regal); aus dem Begleiter
`persoenlich` das Persönliche je Profil, ohne ihn, was ein alter Auszug davon trägt (nur für Profile, die es gibt; Daten ohne Profil
aus alten Auszügen gehören dem ersten Profil Verwaltung). Ein Original ohne
Auszug kommt mit Titel, Autor und Nummer aus seinem Namen (`Titel - Autor [Nummer]`); Volltext und Angaben entstehen dann über
"Bibliothek ergänzen". Ein Buch mit derselben Prüfsumme bleibt, wie es ist. Am Ende die Freigaben ganzer Kategorien aus der Datei.

### Umzug mit Einmalcode

Altes Gerät (`/api/umzug`, Fähigkeit `einstellungen`, außer den Wegen für das neue Gerät):

| Weg | Zweck |
|---|---|
| `POST /api/umzug/vorbereiten` | frische Sicherung (auch in der Kellerwolke, wenn eingeschaltet) und Einmalcode: `{code: "ABCD-EFGH", gilt_bis, sicherung, groesse}`; der Code steht nur hier, gemerkt ist seine Prüfsumme. Ein früher vorbereiteter Umzug gilt danach nicht mehr |
| `GET /api/umzug` | `{vorbereitet, gilt_bis, versuche_frei, sicherung, eingeloest_am, sitzung_bis, gesperrt}` |
| `DELETE /api/umzug` | Code und Sitzung gelten nicht mehr; Bestand und Sicherung bleiben |
| `POST /api/umzug/einloesen` `{code}` | für das neue Gerät, ohne Konto: einmal, nur `UMZUG_CODE_GILT_MIN` Minuten, `UMZUG_VERSUCHE` falsche Codes, dann gesperrt; jeder Fehler 403 mit Grund (`"Der Code stimmt nicht"`, `"... schon eingelöst"`, `"... abgelaufen ..."`, `"Zu viele falsche Codes ..."`). Antwort `{sitzung, sitzung_bis, sicherung, groesse, sha256, schluessel: {kellerwolke?, leitstelle?}, anschluesse: {art: adresse}, originale: {ort, anzahl, groesse}}` |
| `GET /api/umzug/sicherung`, Kopf `X-Umzug-Sitzung` | die Sicherung des Umzugs |
| `GET /api/umzug/originale`, Kopf `X-Umzug-Sitzung` | `[{hash, name, groesse}]`: die Originale auf dem Gerät |
| `GET /api/umzug/originale/{pruefsumme}`, Kopf `X-Umzug-Sitzung` | ein Original, mit Bereichen (`Range`) |

Die Sitzung gilt `UMZUG_SITZUNG_STUNDEN`; ohne gültige 403. Das alte Gerät behält Bestand, Schlüssel und Einstellungen.

Neues Gerät (Ausgangslage `umzug`):

| Weg | Zweck |
|---|---|
| `POST /api/einrichtung/umzug/verbinden` `{adresse, code}` | nur über https (`UMZUG_NUR_HTTPS`, sonst 422), Zertifikat geprüft wie bei der Kellerwolke (`KELLERWOLKE_CA`); gibt es schon ein Konto, 409 (das Konto kommt vom alten Gerät). Löst den Code ein, holt die Sicherung gestreamt mit Prüfsumme, legt die Schlüssel und die Sitzung nur in die Schlüsseldatei und beginnt den Auftrag "Sicherung einspielen"; nach dem Tausch trägt er die Adressen der Anschlüsse ein, wo die Sicherung keine nennt. Antwort `{sicherung, einstellungen: [art], schluessel: [art], originale: {ort, anzahl, groesse}, einspielen: Auftragsstand}`; mit Kellerwolke folgt danach gleich die Prüfung der Originale. Fehler des alten Geräts 403 oder 502 mit Grund |
| `POST /api/einrichtung/originale` `{weg: "kopieren" \| "ort"}` | ohne Kellerwolke: `kopieren` holt jedes Original mit Prüfsumme (Auftrag `kopieren`, eine unterbrochene Datei setzt an ihrem Ende fort, danach die Prüfung); `ort` prüft nur den übernommenen Ort mit Prüfsummen (Auftrag `pruefung`). Mit Kellerwolke 409 |

### Wartung: wieder öffnen

Unter Einstellungen, Wartung (Fähigkeit `einstellungen`). Der Assistent zeigt nur die Schritte von "Neu beginnen" ohne Konto. Was
`PUT .../anschluesse/{art}`, `POST .../katalog`, `POST .../familie/profile` und `PUT .../familie/stimme` dort ändern würden, wird nur
vorgemerkt (`Vorgemerkt.angewandt` false), ein neuer Schlüssel vorgemerkt in der Schlüsseldatei; je Ziel gilt die neueste.

```
Aenderung: { id, schritt, art: "anschluss" | "katalog" | "profil" | "stimme", was, alt, neu }
```

| Weg | Zweck |
|---|---|
| `POST /api/einrichtung/oeffnen` | öffnet unter Wartung (während der Ersteinrichtung 409) |
| `GET /api/einrichtung/aenderungen` | `{aenderungen: [Aenderung], unveraendert: [Name des Schritts], stand}`; `was` ist ein Satz wie `"Leitstelle: Adresse https://... und neuer Schlüssel"` |
| `POST /api/einrichtung/uebernehmen` `{stand, ids}` | wendet nur die genannten an, nur mit dem `stand` der Liste (409 sonst, 404 für eine unbekannte); die übrigen fallen weg, der Assistent ist danach geschlossen. Antwort `{uebernommen: [Aenderung], verworfen}` |
| `POST /api/einrichtung/schliessen` | ohne Übernehmen; alles Vorgemerkte fällt weg, auch vorgemerkte Schlüssel |

Gelöscht oder ersetzt wird dabei nur, was die Liste nennt und angehakt ist; Bücher, Profile und Daten bleiben.

### Persönliches in der Kellerwolke und die Datei der Profile

Das Persönliche je Buch steht in einem eigenen kleinen Begleiter des Originals (`ablage/persoenlich.py`): Rolle `persoenlich`, Name
wie das Original mit `.persoenlich.json`, Form `buecherfreunde-persoenlich/1` `{art, buch, hash, profile: {<profil_id>: {lesestand,
vorlesestelle, notizen, markierungen, etiketten, privat, freigegeben}}}` (`freigegeben`: einem Kind einzeln freigegeben). Ein paar
hundert Byte; der Auszug mit Volltext und Umschlag wird dafür nie neu geschrieben. Der Auszug bleibt in Form `buecherfreunde-angaben/1`
(`buch`, `kategorien`; `lesen`, `notizen`, `markierungen`, `labels` leer); was ältere Auszüge darin an Persönlichem tragen, wird
weiter gelesen.

Trigger merken jede Änderung am Persönlichen eines Buchs (`nachfuehren`, art `buch`); der Auftrag "Persönliches nachführen" schreibt
nach einer ruhigen Weile ohne neue Änderung (`PERSOENLICH_RUHE_S`, 30) den Begleiter einmal neu, höchstens `PERSOENLICH_JE_RUNDE`
(50) je Runde mit `PERSOENLICH_ABSTAND_S` Pause, im Takt `PERSOENLICH_TAKT_S`. Ein Lesestand, der sich beim Lesen zehnmal ändert,
ist so ein Schreiben (gemessen: 370 Byte gegen etwa 880 KB für einen Auszug mit 3 MB Volltext). Ein Begleiter, dessen Persönliches
ganz entfernt wurde, bekommt eine leere neue Fassung. Beim ersten Start mit dieser Fassung werden einmal nur die Bücher vorgemerkt,
zu denen es schon Persönliches gibt, dazu die Datei der Profile (Merker `persoenlich_nachgetragen` in `app_settings`, nie
wiederholt); alle Bücher schreibt kein Start.

Die Profile stehen in `Apps/BücherFreunde/profile.json` (`buecherfreunde-profile/1`: `profile` mit id, name, zeichen, farbe, rolle,
geburtsjahr, stufe, einstellungen, sortierung; `freigaben` ganzer Kategorien mit Schlüssel und Name; `stimme` der Familie), nie
PIN oder Bild-PIN; neu geschrieben nach jeder Änderung an Profilen, Freigaben von Kategorien oder der Stimme. Titel und andere Angaben
im Auszug führt die Pflege nachts nach wie bisher.

| Weg | Zweck |
|---|---|
| `GET /api/kellerwolke/einstellungen` | `{persoenlich, sicherungen_ablegen}` (Vorgaben `PERSOENLICH_IN_KELLERWOLKE`, `SICHERUNG_IN_KELLERWOLKE`) |
| `PUT /api/kellerwolke/einstellungen` `{persoenlich?, sicherungen_ablegen?, entfernen?, stand?}` | Einschalten nur mit `stand` aus den Folgen; es schreibt den Begleiter jedes Buchs mit Persönlichem und die Datei der Profile, keine anderen. Ausschalten lässt in der Kellerwolke alles, wie es ist; mit `entfernen` (ebenso nur mit `stand`) kommen die Begleiter und die Datei der Profile in den Papierkorb der Kellerwolke (dort zurückzuholen), alte Auszüge mit Persönlichem darin werden ohne neu geschrieben. Ohne `stand` 422, geändert seit der Vorschau 409 |
| `GET /api/kellerwolke/persoenlich/folgen` | `{buecher, profile_datei, profile: [{id, name, buecher}], lesestaende, vorlesestellen, notizen, markierungen, etiketten, private, freigaben, stand}`: was Einschalten schreibt und Ausschalten mit Entfernen wegnimmt; in der App bleibt alles |
| `GET /api/kellerwolke/persoenlich/stand` | der Auftrag "Persönliches nachführen" |

Tabellen: `einrichtung`, `einrichtung_schritt`, `einrichtung_aenderung`, `einrichtung_auftrag`, `original_befund`, `neuaufbau_datei`,
`umzug` (altes Gerät), `umzug_kopie` (neues Gerät), `nachfuehren` (`einrichtung/schema.py`).
