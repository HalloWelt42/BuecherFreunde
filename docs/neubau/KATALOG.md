# Katalog (BF-69): Plan und Schnittstelle

Kategorien werden ein Katalog mit zwei Ebenen: Bereiche (etwa Technik) und Kategorien darunter (etwa Programmierung), je
mit Zeichen und Farbe. Ein Buch kann in mehreren Kategorien stehen. Der Katalog ist Daten, keine Vorgabe im Code:
BücherFreunde bringt einen Standard-Katalog für jede Bibliothek mit (Datei), an den eigenen Bestand angepasst wird er per
Vorschlag. Eingeordnet wird mit festen Regeln und der lokalen KI in Stapeln, immer als Vorschlag zum Bestätigen.
Abgenommener Entwurf: Runde 2 (privat, an der Karte BF-69).

## Begriffe

| Wort | Bedeutung |
|---|---|
| Bereich | oberste Ebene des Katalogs (`categories.art = 'bereich'`, `parent_id` leer) |
| Kategorie | zweite Ebene (`art = 'kategorie'`, `parent_id` = Bereich); Bücher stehen nur in Kategorien |
| Regal | alles Bisherige (`art = 'regal'`): eigene Regale wie Gutenberg und die Kategorien aus Importen |
| Standard-Katalog | `backend/app/katalog/standard.json`, für jede Bibliothek, Regeln auf Deutsch und Englisch |
| Entwurf | ein Katalog, der noch nicht gilt: aus dem Standard, an den Bestand angepasst, geladen oder leer |
| Vorschlag | ein Buch in einer Kategorie, gefunden von Regel oder KI, offen, angenommen oder abgelehnt |
| Lauf | das Einordnen über den Bestand, gegliedert in Stapel (Vorgabe 500 Titel) |

## Daten

`categories` bekommt über `NEUBAU_SPALTEN` (nie Daten löschen, nur Spalten ergänzen):

| Spalte | Art | Bedeutung |
|---|---|---|
| `art` | TEXT NOT NULL DEFAULT 'regal' | bereich, kategorie, regal |
| `schluessel` | TEXT NOT NULL DEFAULT '' | fester Schlüssel aus dem Katalog, etwa `technik/programmierung`; leer bei Regalen |
| `regeln` | TEXT NOT NULL DEFAULT '{}' | JSON `{sachgruppen, schlagworte, titelwoerter, verlage}`, je eine Liste von Texten |
| `ki_beschreibung` | TEXT NOT NULL DEFAULT '' | was in die Kategorie gehört, für die KI |
| `verborgen` | INTEGER NOT NULL DEFAULT 0 | 1: ohne Bücher, nicht in der Leiste |
| `herkunft` | TEXT NOT NULL DEFAULT '' | standard, geteilt, neu, eigen |

Farbe und Zeichen eines Bereichs stehen in `color`, `icon`; eine Kategorie hat ein eigenes Zeichen und erbt die Farbe ihres
Bereichs, wenn `color` leer ist. `book_categories.quelle` bekommt die Werte `katalog-regel`, `katalog-ki`, `manuell`.

Neue Tabellen:

- `katalog_vorschlag`: id, book_id, category_id, quelle (regel, ki, beide), gruende (JSON, kurze Sätze), sicherheit
  (0 bis 100), stand (offen, angenommen, abgelehnt), lauf_id, angelegt_am; UNIQUE(book_id, category_id). Abgelehnte
  Vorschläge kommen nie wieder.
- `katalog_lauf`: id, art (einordnen, bestand), stand (laeuft, pause, fertig, fehler), stapel, stapel_gesamt,
  stapel_groesse, regeln, ki, ohne_vorschlag, schritt, grund, begonnen, geaendert. Ein Neustart setzt einen laufenden Lauf
  am letzten fertigen Stapel fort.
- Der Entwurf liegt als JSON in `app_settings` (Schlüssel `katalog_entwurf`), bis er angenommen oder verworfen wird.

Einstellungen in `app_settings` mit Vorgaben in `config.py`: `katalog_stapel` (500), `katalog_ki_je_anfrage` (40 Bücher),
`katalog_sicher_ab` (80: so sichere Vorschläge sind vorab angehakt), `katalog_teilen_ab` (300 Bücher: eine Kategorie mit so
vielen Treffern wird im Entwurf in ihre Teile zerlegt, wenn der Standard Teile kennt).

## Standard-Katalog

Eine Datei, gültig für jede Bibliothek, ohne Bezug auf einen bestimmten Bestand:

```json
{ "fassung": 1,
  "bereiche": [
    { "schluessel": "technik", "name": "Technik", "zeichen": "microchip", "farbe": "#2f6fb3",
      "beschreibung": "Informatik, Elektronik, Ingenieurwesen, Handwerk",
      "kategorien": [
        { "schluessel": "technik/informatik", "name": "Informatik", "zeichen": "code",
          "ki_beschreibung": "Programmierung, Softwareentwicklung, Netzwerke, Betriebssysteme, Datenbanken",
          "regeln": { "sachgruppen": ["004", "005", "006"], "schlagworte": ["Informatik", "Programmierung",
                      "Computer science", "Programming"], "titelwoerter": ["Python", "Java", "programmier"], "verlage": [] },
          "teile": [ { "schluessel": "technik/programmierung", "name": "Programmierung", "zeichen": "code", "regeln": {} },
                     { "schluessel": "technik/netzwerke", "name": "Netzwerke und Systeme", "zeichen": "network-wired", "regeln": {} } ] } ] } ] }
```

Zehn Bereiche wie im Entwurf: Romane, Kinder und Jugend, Wissen, Technik, Wirtschaft und Recht, Kunst und Kultur, Leben,
Lernen, Comics, Dokumente; zusammen etwa 55 Kategorien. Sachgruppen sind die Nummern der Bibliotheken (Dezimal und die
Buchstabengruppen der Nationalbibliografie wie B für Belletristik, K für Kinder- und Jugendliteratur), Schlagworte und
Titelwörter jeweils auf Deutsch und Englisch. Zeichen sind Namen aus Font Awesome Free (solid).

## Einordnen

1. **Regeln** je Buch und Kategorie: Sachgruppe (Präfix der Nummer), Schlagwort (ganzes Wort, ohne Groß und klein, gegen
   Schlagworte der Quellen und die Namen der alten Regale des Buchs), Titelwort (Wortanfang im Titel), Verlag (enthalten).
   Sicherheit: Sachgruppe 90, Schlagwort 80, Titelwort 70, Verlag 60; mehrere Regeln heben auf höchstens 97.
2. **KI** in Stapeln: je Anfrage bis zu `katalog_ki_je_anfrage` Bücher (Nummer, Titel, Autor, Verlag, Schlagworte, Anfang der
   Beschreibung) und der ganze Katalog (Schlüssel, Name, KI-Beschreibung). Antwort als JSON-Schema: je Buch bis zu zwei
   Kategorien mit Sicherheit und einem kurzen deutschen Satz. Über `services/ki.py`, Priorität Hintergrund, mit Geduld.
   Unbekannte Schlüssel und Bücher fallen weg. Stimmen Regel und KI überein: Quelle `beide`, Sicherheit +5 (höchstens 99).
3. **Du** nimmst an oder lehnst ab, einzeln, angehakt oder alle einer Kategorie. Annehmen schreibt `book_categories` mit
   Quelle `katalog-regel` oder `katalog-ki`.

## Entwurf aus dem Bestand

`POST /api/katalog/entwurf {weg: "bestand"}` zählt die Treffer der Regeln je Kategorie des Standards über den ganzen Bestand
(schnell, ohne KI) und baut daraus den Entwurf: Kategorien ohne Treffer `verborgen` (Herkunft bleibt standard), Kategorien
über `katalog_teilen_ab` mit Teilen werden durch die Teile ersetzt (Herkunft `geteilt`), Bereiche ohne sichtbare
Kategorie verborgen. Die Zahlen im Entwurf sind die Treffer der Regeln. "Neu aus dem Bestand" (Herkunft `neu`) schlägt die
KI vor: aus häufigen Schlagworten ohne passende Kategorie, als zweiter Schritt desselben Laufs, höchstens fünf.

## Alte Kategorien

Kategorien aus Importen (Regale mit `art = 'regal'`, nicht `spezial`, nicht Ungeordnet) gehen im Katalog auf: Regeln und KI
schlagen je altem Regal eine Kategorie des Katalogs vor oder "Schlagwort am Buch" (wird ein Etikett). Übernehmen setzt die
Bücher in die Kategorie oder vergibt das Etikett. Das alte Regal wird erst nach einer Folgenvorschau und ausdrücklicher
Bestätigung entfernt, nie von selbst.

## Schnittstelle

Alle Wege unter `/api/katalog`, Anmeldung wie überall. Zahlen sind ganze Zahlen, Zeiten ISO.

| Weg | Inhalt |
|---|---|
| `GET /api/katalog` | `{bereiche: [Bereich], regale: [Regal], ohne_kategorie, hat_katalog}`; Bereich `{id, schluessel, name, zeichen, farbe, beschreibung, verborgen, anzahl, kategorien: [Kategorie]}`; Kategorie `{id, schluessel, name, zeichen, farbe, ki_beschreibung, regeln, verborgen, herkunft, anzahl}`; Regal `{id, name, zeichen, farbe, anzahl, spezial}` |
| `GET /api/katalog/standard` | der Standard als Entwurf (ohne `id`, `anzahl` null) |
| `POST /api/katalog/entwurf` | `{weg: "standard" \| "bestand" \| "leer"}`; "bestand" startet einen Lauf und antwortet mit `{lauf}` |
| `GET /api/katalog/entwurf` | `{entwurf: Entwurf \| null, lauf: Laufstand \| null}`; Entwurf `{bereiche: [...]}` wie oben ohne `id`, mit `anzahl` und `herkunft` |
| `PUT /api/katalog/entwurf` | geänderten Entwurf speichern, Antwort wie GET |
| `POST /api/katalog/entwurf/annehmen` | schreibt den Katalog (gleicher Schlüssel: ändern, sonst anlegen, nie löschen), Antwort `GET /api/katalog` |
| `DELETE /api/katalog/entwurf` | Entwurf verwerfen |
| `GET /api/katalog/datei` | der gültige Katalog als Datei (Format des Standards), zum Sichern und Teilen |
| `POST /api/katalog/datei` | eine Katalog-Datei hochladen (JSON im Körper), wird zum Entwurf |
| `POST /api/katalog/bereiche`, `PATCH /api/katalog/bereiche/{id}` | `{name, zeichen, farbe, beschreibung, verborgen}` |
| `POST /api/katalog/kategorien`, `PATCH /api/katalog/kategorien/{id}` | `{bereich_id, name, zeichen, ki_beschreibung, regeln, verborgen}` |
| `GET /api/katalog/{bereiche\|kategorien}/{id}/loeschfolgen` | `{buecher, vorschlaege, kategorien}` vor dem Löschen |
| `DELETE /api/katalog/{bereiche\|kategorien}/{id}` | nur nach den Folgen; ein Bereich nur ohne Kategorien |
| `GET /api/katalog/kategorien/{id}/treffer` | `{regeln: [{art, werte, treffer}], zusammen, ki_vorschlaege}` |
| `GET /api/katalog/alt` | `[{id, name, anzahl, vorschlag: {art: "kategorie" \| "schlagwort", kategorie_id, grund}}]` |
| `POST /api/katalog/alt/uebernehmen` | `{ids, ziel: {kategorie_id} \| {schlagwort: true}}`, Antwort `{buecher}` |
| `GET /api/katalog/alt/{id}/loeschfolgen`, `DELETE /api/katalog/alt/{id}` | altes Regal entfernen nach Folgenvorschau |
| `POST /api/katalog/einordnen` | Lauf starten (`{stapel?}`), Antwort Laufstand |
| `GET /api/katalog/einordnen/stand` | Laufstand `{laeuft, pause, stapel, stapel_gesamt, stapel_groesse, regeln, ki, ohne_vorschlag, schritt, grund}` |
| `POST /api/katalog/einordnen/pause`, `.../fortsetzen` | Laufstand |
| `GET /api/katalog/vorschlaege/uebersicht` | `[{kategorie_id, anzahl}]` offene je Kategorie |
| `GET /api/katalog/vorschlaege?kategorie=&seite=&pro_seite=` | `{gesamt, vorschlaege: [{id, buch, quelle, gruende, sicherheit, vorab, auch: [{kategorie_id, name, sicherheit}]}]}`; `buch` wie in der Bücherliste (mit Deckblattangaben); `vorab`: sicher genug zum Vorab-Haken |
| `POST /api/katalog/vorschlaege/annehmen` | `{ids}` oder `{kategorie}` (alle offenen), Antwort `{angenommen}` |
| `POST /api/katalog/vorschlaege/ablehnen` | `{ids}`, Antwort `{abgelehnt}` |

Die Bücherliste filtert weiter mit `kategorie` (kommagetrennt; ein Bereich ist die Liste seiner Kategorien). Die Kategorien
eines Buchs in `GET /api/books/{id}` tragen zusätzlich `zeichen`, `farbe` und `bereich` (Name).

## Oberfläche

Nach dem Entwurf Runde 2, mit den Stilen der App:

- **Einstellungen**, neuer Reiter "Katalog" (Zeichen `sitemap`, füllend nach BF-74): Katalog wählen (drei Wege als Kacheln,
  Laden und Sichern), der gültige Katalog oder der Entwurf als Bereichskacheln im Raster mit Herkunft je Kategorie, Kategorie
  bearbeiten im Fenster (Name, Bereich, Zeichen aus `Symbolwahl`, Farbe, Beschreibung für die KI, Regeln mit Treffern),
  Kategorien aus Importen, Einordnen mit Lauf (Pause) und den Vorschlägen je Kategorie.
- **Seitenleiste**: Abschnitt "Katalog" mit Bereichen (aufklappbar) und Kategorien mit Zeichen und Zahl; "Ohne Kategorie"
  darunter; ohne Katalog ein Verweis "Katalog einrichten"; eigene Regale bleiben unter "Regale".
- **Buchseite**: Kategorien als Chips mit Zeichen und Farbe, Entfernen am Chip, "+ Kategorie" wählt aus dem Katalog.
- Wortliste HELF-273 (Pause statt Anhalten), gleichartige Tasten im Raster, Schriftgröße darf nichts abschneiden, hell,
  dunkel und Telefon.
