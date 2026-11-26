# Bücher übersetzen (BF-71): Plan

Ein englisches Buch bekommt auf Wunsch eine deutsche Fassung. Sie erscheint nicht als zweites Buch in der Bibliothek,
sondern als wählbare Fassung in der Detailansicht (abgerundete Flaggenlabels). Vorrang hat die Güte: Aufbau, Code und
Fachbegriffe bleiben erhalten, jede Stelle durchläuft feste Prüfungen und eine zweite KI als Prüfer. Gerechnet wird lokal,
KI nur über die Leitstelle, Texterkennung als Werkzeug ohne Modell am Mac.

## Abmachungen

| Frage | Entscheidung |
|---|---|
| Was wird übersetzt | je Buch auf Wunsch, nie der ganze Bestand von selbst |
| PDF auf Deutsch | fließender Text mit gleichem Aufbau und Marken für die Seiten des Originals; EPUB bleibt EPUB |
| Fachbegriffe | fest: Code, Bezeichner, Abkürzungen, Produktnamen; dazu eine Begriffsliste je Buch, von der KI vorgeschlagen, jederzeit änderbar |
| Prüfung | feste Prüfungen immer, dazu eine zweite KI als Prüfer Satz für Satz, bis zu zwei Nacharbeiten, Rest wird gezeigt |
| Texterkennung | Seiten ohne Textschicht zuerst erkennen; Schrift in Abbildungen erkennen, übersetzen, über das Bild legen, Umschalter Englisch und Deutsch |
| Lesestand und Notizen | Lesestand gemeinsam; Notizen und Markierungen hängen am Absatz und erscheinen in beiden Fassungen |
| Start und Stand | auf der Buchseite "Ins Deutsche übersetzen", Lauf als Auftrag, fertige Kapitel sofort lesbar |
| Erste Probe | drei Arten: Fachbuch als EPUB mit Code, technisches PDF mit Tabellen und Abbildungen, Scan ohne Textschicht |

## Aufbau

```
Original (EPUB, PDF, Scan)
  -> Texterkennung (nur Scans und Abbildungen)            Stellwerk am Mac, Werkzeug ohne Modell
  -> Zerlegen in Blöcke mit fester Kennung               backend/app/uebersetzung/zerlegen_epub.py, zerlegen_pdf.py
  -> Begriffsliste je Buch (Regeln, dann KI-Vorschlag)    uebersetzung/begriffe.py
  -> Übersetzen in Portionen (Leitstelle, JSON-Schema)    uebersetzung/uebersetzen.py
  -> Prüfkette: feste Prüfungen, KI-Prüfer, Nacharbeit    uebersetzung/pruefen.py
  -> Zusammensetzen zur deutschen Fassung (EPUB)          uebersetzung/setzen.py
  -> Ablage in der Kellerwolke neben dem Original         services/fassungen.py, Tabelle fassung
     (Lauf services/uebersetzungslauf.py, Stand services/fassungsstand.py, Ablage services/fassung_ablage.py,
      Begriffsliste services/begriffsliste.py, Wege api/uebersetzung.py)
  -> Lesen: Flaggenlabels, gemeinsamer Lesestand          Oberfläche nach Entwurf
```

Der ganze Lauf ist ein fortsetzbarer Auftrag: Jeder Block wird mit Ergebnis, Befunden und Stand in der Datenbank
gespeichert, ein Hintergrundlauf (wie Einordnen und Umschlagprüfung) nimmt nach einem Neustart oder Ausrollen jede Fassung
mit Stand "läuft" wieder auf und setzt am ersten offenen Block fort. Dafür braucht es keinen neuen Appkern-Stand.

## Blöcke

Beide Fassungen bestehen aus denselben Blöcken mit derselben Kennung: Überschrift (mit Stufe), Absatz, Listenpunkt,
Tabellenzelle, Bildunterschrift, Fußnote, Beschriftung im Bild. Code, Formeln, Verweise und Bilder sind keine Blöcke zum
Übersetzen, sie stehen als Marken im Block (`<x3/>`) und gehen nie ans Modell. Auszeichnungen im Satz (kursiv, fett,
Verweis) werden Klammermarken (`<t1>..</t1>`). Die Kennung eines Blocks verbindet Original und Übersetzung: an ihr hängen
Lesestand, Notizen, Markierungen und die Seitenmarken des PDF.

- **EPUB:** je XHTML-Datei des Buchs die Blöcke wie in Nachschlag (zerlegen.py); `pre`, `code`, `math` und alles mit
  `translate="no"` bleibt draußen. Die Liste der Klassen, die nie übersetzt werden, ist einstellbar. Zusammengesetzt wird
  in dieselbe Datei mit demselben Markup, `lang="de"`, nur der Text tauscht.
- **PDF:** Blöcke aus der Seitenstruktur: Überschriften nach Schriftgröße und Gewicht, Code nach der vorhandenen Erkennung
  der Codestellen (Festbreite, BF-29), Tabellen nach Zellen, Abbildungen mit Bildunterschrift, Kopf- und Fußzeilen und
  Seitenzahlen fallen weg, Silbentrennung am Zeilenende wird aufgelöst. Jeder Block merkt sich Seite und Lage. Die deutsche
  Fassung wird ein EPUB mit Marken "Seite 33" an den Stellen der Seitenwechsel.
- **Scan:** erst Texterkennung je Seite mit Lage der Zeilen, dann wie PDF.

## Begriffsliste

Je Buch eine Liste im Format `begriffe`, `einheiten`, `regeln` (wie in den Buchprojekten), dazu eine allgemeine für alle
Bücher.

1. **Regeln:** Inline-Code, Bezeichner (CamelCase, snake_case, Aufrufe `name()`), Abkürzungen in Großbuchstaben,
   Dateinamen, Befehle, Versionen und Produktnamen (gleich geschrieben über das ganze Buch, groß am Satzanfang und mitten
   im Satz) bleiben.
2. **KI-Vorschlag:** Aus Inhaltsverzeichnis, Stichwortverzeichnis und Stichproben schlägt die KI Fachbegriffe vor, je mit
   "bleibt englisch" oder "auf Deutsch: ..." und kurzem Grund (Thread bleibt, Listing bleibt, Event Loop bleibt).
3. **Pflege:** Die Liste ist an der Buchseite einsehbar und änderbar. Eine Änderung markiert nur die betroffenen Blöcke zum
   Neuübersetzen.

## Übersetzen

- Portionen bis etwa 2.500 Zeichen oder 30 Blöcke, immer an Blockgrenzen; im Auftrag stehen Kapitelüberschrift, die
  Begriffsliste für diese Portion und die letzten zwei Sätze davor als Zusammenhang.
- Antwort als JSON-Schema mit genau so vielen Texten wie Blöcken, temperature 0, Priorität Hintergrund.
- Passt die Antwort nicht (Anzahl, Format), wird die Portion halbiert, dann einzeln versucht.
- Zwischenspeicher je Block über die Prüfsumme aus Text, Begriffsliste und Fassung der Anweisung: Wiederkehrendes
  (Kopfzeilen, gleiche Absätze) wird einmal übersetzt.

## Prüfkette

**Feste Prüfungen** je Block, alle müssen bestehen:

| Prüfung | bestanden, wenn |
|---|---|
| Marken | jede Marke genau einmal, gleiche Schachtelung, keine fremde Auszeichnung |
| Zahlen | dieselben Zahlen, nach Angleichen der Tausender- und Dezimalzeichen (16,000 = 16.000; 1.5 = 1,5) |
| Einheiten | dieselben Einheiten, keine von selbst zugefügte Umrechnung |
| Bezeichner | Inline-Code, Bezeichner, Adressen und Dateinamen unverändert |
| Begriffe | jeder Begriff mit "bleibt" steht unverändert da, jeder mit Übersetzung in der vereinbarten Form |
| Sprache | kein englischer Satz übrig (Stoppwörter je Satz, Begriffe und Code ausgenommen) |
| Länge | Verhältnis Deutsch zu Englisch zwischen 0,8 und 1,8 je Block |
| Vollständigkeit | gleiche Zahl an Sätzen, nichts ausgelassen, nichts hinzugefügt (Abweichung höchstens eins) |
| Zeichen | echte Umlaute, gerade Anführungszeichen, keine Sonderstriche |

**KI-Prüfer:** Nach den festen Prüfungen bekommt eine zweite Anfrage, nach Möglichkeit mit einem anderen Modell, Original
und Übersetzung satzweise und urteilt je Block: in Ordnung, oder Mangel mit Art (Sinn, ausgelassen, hinzugefügt, Begriff,
Grammatik) und Grund. Ein Mangel schickt den Block mit dem Grund im Auftrag zur Nacharbeit; eine Korrektur gilt erst, wenn
sie die festen Prüfungen wieder besteht. Nach zwei Nacharbeiten bleibt der Block im Original (`lang="en"`, sichtbar
markiert) und erscheint im Prüfbericht. Beanstandetes wird nie still eingesetzt.

**Prüfbericht** je Kapitel: Blöcke gesamt, bestanden, nachgearbeitet, offen; je offener Stelle Original, Übersetzung,
Befund. Offene Stellen lassen sich annehmen, neu übersetzen oder von Hand ändern.

## Abbildungen

Texterkennung je Abbildung mit Lage jedes Worts. Zusammengehörige Wörter werden zu Beschriftungen, jede Beschriftung ein
Block (übersetzt und geprüft wie Text, mit Begriffsliste). Die deutsche Fassung zeigt das Originalbild mit einer Ebene
darüber: Die deutsche Beschriftung deckt die englische ab, in Schriftgröße und Farbe an das Bild angepasst. Ein Umschalter
je Bild und einer für das ganze Buch wechselt zwischen Englisch und Deutsch. Schrift, die zu klein, gedreht oder unsicher
erkannt ist, bleibt englisch und steht im Bericht.

## Ablage und Kennzeichnung

- Tabelle `fassung`: Buch, Sprache, aus Sprache, Stand (läuft, teilweise, fertig, Fehler), Datei in der Kellerwolke,
  Modell für Übersetzen und Prüfen, Fassung der Anweisung, angelegt, geändert, Zahlen aus dem Prüfbericht.
- Tabelle `uebersetzung_block`: Fassung, Kennung, Prüfsumme des Originals, Übersetzung, Stand, Befunde, Versuche.
- Die Datei liegt in der Kellerwolke neben dem Original unter `Fassungen/de/`. Ohne Kellerwolke liegt sie im lokalen
  Bestand (wie die Begleiter).
- Jede deutsche Fassung trägt sichtbar "Von uns übersetzt aus dem Englischen" mit Modell und Datum; das Original ist mit
  einem Tipp erreichbar.

## Lesen

- Detailansicht: Flaggenlabels für jede Fassung (Original, Deutsch), dazu der Stand (etwa "Deutsch, 7 von 12 Kapiteln").
- Lesestand gemeinsam: gespeichert als Blockkennung und Anteil im Block; beim Wechsel steht man am selben Absatz, im PDF auf
  der Seite des Blocks.
- Notizen und Markierungen hängen an Block und Textstelle. In der anderen Fassung erscheint die Marke am ganzen Absatz, mit
  Hinweis "entstanden in der englischen Fassung".

## Prüfen der Arbeit

Die Prüfungen sind penibel und laufen automatisch; die Probe mit echten Büchern bleibt privat, die Tests im Repo nutzen
nur erfundene Texte.

1. Einheitstests je feste Prüfung mit Gut- und Schlechtfällen (Zahlenformate, verschachtelte Marken, Begriffe am
   Satzanfang, Code im Satz, Einheiten).
2. Rundlauf: Zerlegen und Zusammensetzen ohne Übersetzung ergibt dasselbe EPUB (Text, Markup, Dateien byte-gleich bis auf
   `lang`).
3. Erzeugte Probe-PDF mit Überschriften, Spalten, Tabellen, Code, Fußnoten, Abbildungen mit Beschriftung: jeder Block an
   seiner Stelle, nichts doppelt, nichts fehlt.
4. Attrappe der Leitstelle: falsche Anzahl, fehlende Marke, geänderte Zahl, englischer Satz, Mangel des Prüfers; jeweils
   Halbieren, Nacharbeit, Verbleib im Original und Bericht.
5. Fortsetzen: Auftrag mitten im Kapitel abbrechen, neu starten, keine Portion doppelt, keine verloren.
6. Probe mit drei echten Büchern (siehe Abmachungen): Prüfberichte und Stichproben nebeneinander zur Abnahme, erst dann
   gibt es die Taste für alle.

## Schnittstelle

| Weg | Inhalt |
|---|---|
| `GET /api/books/{id}/fassungen` | `[{id, sprache, original, stand, kapitel_fertig, kapitel_gesamt, fertig_gegen, modell, pruefmodell, angelegt, geaendert}]`; das Original steht immer zuerst (`id` null, `original` true) |
| `GET /api/books/{id}/fassungen/de/folgen` | Rückfrage vor dem Start: `{seiten, kapitel, bloecke, begriffe, abbildungen, dauer_s, fertig_gegen, tempo_s_je_seite, ablage: {ort, pfad}, geht, grund}`; `ort` kellerwolke oder geraet; `geht` false mit Grund, wenn das Buch nicht englisch ist oder das Format noch nicht übersetzt wird |
| `POST /api/books/{id}/fassungen/de` | startet (oder setzt fort), Antwort Stand |
| `GET /api/fassungen/{fid}/stand` | `{id, stand, begonnen, bisher_s, noch_s, fertig_gegen, tempo_s_je_seite, kapitel_jetzt, block_jetzt, stationen: [{name, stand, text}], kapitel: [{nr, titel, stand, dauer_s, geschaetzt, bloecke, fertig, geprueft, nachgearbeitet, offen}], zahlen: {bloecke, uebersetzt, bestanden, nachgearbeitet, offen}, grund}`; Stationen in fester Folge: Zerlegen, Begriffe, Übersetzen, Prüfen, Nacharbeit, Setzen; Stand je Station: wartet, laeuft, fertig |
| `POST /api/fassungen/{fid}/pause`, `.../fortsetzen`, `.../abbrechen` | Stand; Abbrechen behält Fertiges, die Fassung bleibt "teilweise" |
| `GET /api/fassungen/{fid}/bericht` | `{zahlen, offen: [{kennung, kapitel, ort, seite_original, original, deutsch, befunde: [{art, quelle, text, stelle}]}]}`; `quelle` pruefung oder ki; `stelle` das beanstandete Stück im deutschen Text |
| `POST /api/fassungen/{fid}/bloecke/{kennung}` | `{aktion: "neu" \| "annehmen" \| "setzen", text?}`; "setzen" nimmt deinen Text, wenn er die festen Prüfungen besteht, sonst 422 mit Befunden |
| `GET /api/books/{id}/begriffe`, `POST`, `PATCH /api/begriffe/{bid}`, `DELETE` | Begriffsliste je Buch `[{id, englisch, deutsch, bleibt, herkunft, stellen, grund, art}]`; `art` begriff oder einheit, `herkunft` regel, ki, hand oder vorgabe; `GET /api/begriffe` und `POST /api/begriffe` die Liste für alle Bücher |
| `GET /api/fassungen/{fid}/datei` | die deutsche Fassung als EPUB für den Leser, auch teilweise (offene Blöcke im Original mit Marke) |

Geschätzt wird aus dem Tempo dieses Rechners: vor dem ersten Lauf aus einer festen Vorgabe (`UEBERSETZEN_S_JE_SEITE`,
Vorgabe 30 mit Prüfung), danach aus dem gleitenden Mittel der letzten Läufe, im Lauf aus dem Tempo dieses Laufs.

## Reihenfolge

1. Fortsetzbarer Lauf über eigene Tabellen und einen Hintergrundlauf.
2. EPUB: Zerlegen, Begriffsliste, Übersetzen, Prüfkette, Zusammensetzen, Tests 1, 2, 4, 5.
3. Probe mit dem EPUB-Fachbuch, Prüfbericht zur Abnahme.
4. PDF: Blöcke aus der Seitenstruktur, Seitenmarken, Test 3, Probe mit dem technischen PDF.
5. Texterkennung am Mac (Engine nach Messung auf Probeseiten), Scans, Abbildungen mit Umschalter, Probe mit dem Scan.
6. Oberfläche nach Entwurf: Flaggenlabels, Übersetzen, Auftrag, Prüfbericht, Begriffsliste, Bildbeschriftungen.
7. Lesestand und Notizen über beide Fassungen.

## Offen, wird gemessen

- Texterkennung: Güte und Tempo auf Probeseiten, das Werkzeug wie im Dokumentwerk gegen die Texterkennung des Systems am
  Mac.
- KI-Prüfer: welches zweite Modell die Leitstelle anbietet, sonst dasselbe Modell mit eigener Anweisung.
- Tempo: gemessen 7,3 Sekunden für rund 200 Wörter mit Code und Tabelle (qwen3-next-80b), also etwa 15 Sekunden je Seite
  für einen Durchgang, mit Prüfer etwa das Doppelte.
- Gemeinsamer Baustein mit Nachschlag im Appkern (Zerlegen, Portionieren, Prüfkette, Begriffsliste, Zwischenspeicher),
  sobald der EPUB-Teil steht (BF-72).
