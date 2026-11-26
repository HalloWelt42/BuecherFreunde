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
| Anrede | ein Buch bleibt durchgehend bei einer: vorbelegt "du" (`UEBERSETZEN_ANREDE`), je Buch beim Start wählbar, die Fassung speichert sie |
| Erste Probe | drei Arten: Fachbuch als EPUB mit Code, technisches PDF mit Tabellen und Abbildungen, Scan ohne Textschicht |

## Aufbau

```
Original (EPUB, PDF, Scan)
  -> Texterkennung (nur Scans und Abbildungen)            Stellwerk am Mac, Werkzeug ohne Modell
  -> Zerlegen in Blöcke mit fester Kennung               backend/app/uebersetzung/werk.py (EPUB und PDF), zerlegen_epub.py,
                                                          zerlegen_pdf.py (pdf_lesen.py, pdf_aufbau.py, pdf_epub.py)
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
- **Code in einfachen Absätzen** (codeabsaetze.py): Manche Bücher setzen Code als gewöhnliche Absätze, Zeile für Zeile,
  oft zwischen Zäunen aus Markdown ("```python" bis "```"). Solche Absätze werden keine Blöcke und bleiben Zeichen für
  Zeichen im Original. Merkmale: Zäune (ein Zaun mit Sprache schließt nie, das Ende ist "```"), Zeilen, die von vorn bis
  hinten Code sind (Zuweisung, Aufruf, Kopf eines Blocks, import, Befehl mit Argument, Pfad, JSON, die Merkmale der
  Codestellen mit Anker am Zeilenanfang), schwache Merkmale nur zwischen Code, Festbreitenschrift aus Klasse, CSS oder Stil.
  Prosa mit einzelnen Codewörtern bleibt Text (Satzzeichen am Ende, kleine englische Wörter, lange Wortfolgen).
- **Code in Backticks** (`` `print` ``) geht wie `code` als Platzhalter durch; ebenso Auszeichnungen mit Klassen für Code
  (literal, filename ...) und solche in Festbreitenschrift, deren Text wie Code aussieht.
- **Zeichen:** Das Modell sieht Text als Zeichen (`if age < 18`), nur die Marken sind Auszeichnung; die Antwort kommt
  wieder in die Schreibweise der Vorlagen (`&lt;`). Was darin wie eine Auszeichnung aussieht und nicht als Text im
  Original steht, bleibt roh und fällt in der Prüfung "Marken" auf.
- **PDF:** Aus der Seitenstruktur entsteht ein englisches EPUB mit demselben Aufbau (zerlegen_pdf.py), das dieselbe Kette
  zerlegt und setzt wie jedes EPUB; so sind Blöcke, Marken, Vorlagen und Prüfungen dieselben, und die deutsche Fassung ist
  ein EPUB.
  - Lesen (pdf_lesen.py): Zeilen mit ihren Schriften; Code nach der Erkennung der Codestellen (Festbreite, BF-29); Tabellen
    aus den Linien der Seite nach Zellen (Zeilen, Spalten, Kopfzeile, verbundene Zellen); Abbildungen aus Zeichnungen und
    Bildern, Text darin gehört zum Bild; Text in einem Rahmen oder auf einer Fläche bleibt Text (Kasten); Kopf- und
    Fußzeilen und Seitenzahlen fallen weg (im Rand, wiederkehrend über Seiten); Lesefolge nach Breuel, auch zweispaltig.
  - Aufbau (pdf_aufbau.py): Überschriften nach Größe und Gewicht, die Stufen aus der Verteilung im Dokument; Absätze über
    Zeilen, Spalten und Seiten hinweg (die nächste Zeile in derselben Schrift, nicht eingerückt, die vorige war voll);
    Trennung am Zeilenende aufgelöst (der Bindestrich bleibt, wo das Dokument das Wort sonst mit ihm schreibt); Listen mit
    dem gedruckten Zeichen als Platzhalter; Fußnoten am Fuß der Seite mit Verweis aus dem Text; Bildunterschriften
    ("Figure 1", "Table 2", "Listing 3") an ihrer Abbildung, Tabelle oder Codestelle; Kapitel aus dem Inhaltsverzeichnis
    des PDF (oberste Stufe mit mehr als einem Eintrag), sonst an den Überschriften der obersten Stufe.
  - EPUB (pdf_epub.py): eine Datei je Kapitel, das Verzeichnis mit Seitenliste, ein Rasterbild, das allein die Abbildung
    ist, unverändert, sonst ein Ausschnitt der Seite. An jedem Seitenwechsel eine Marke "Seite 33" mit der gedruckten
    Seitenzahl (wie BücherFreunde sie überall zeigt, services/seiten.py), sonst der Seite im PDF; mitten in einem Absatz
    steht sie als Platzhalter in der Vorlage, so setzt die Übersetzung sie an die passende Stelle. Jedes Element trägt
    `data-bf-seite` und `data-bf-lage`; daraus kennt jeder Block Seite und Lage im Original.
  - Nicht zerlegt wird ein PDF ohne Textschicht (Scan), mit unlesbarer Schrift oder mit kaum Text; die Rückfrage sagt dann
    `geht: false` mit dem Grund, dass die Texterkennung in der nächsten Stufe folgt. Einzelne Seiten ohne Textschicht in
    einem PDF mit Text kommen als Bild in die Fassung und stehen bei "Zerlegen" als nicht lesbar.
- **Scan:** erst Texterkennung je Seite mit Lage der Zeilen, dann wie PDF.

## Begriffsliste

Je Buch eine Liste im Format `begriffe`, `einheiten`, `regeln` (wie in den Buchprojekten), dazu eine allgemeine für alle
Bücher.

1. **Regeln:** Inline-Code, Bezeichner (CamelCase, snake_case, Aufrufe `name()`), Abkürzungen in Großbuchstaben,
   Dateinamen, Befehle, Versionen und Produktnamen bleiben. Namen kommen nur aus dem Fließtext: gleich geschrieben über das
   ganze Buch, nie klein, mindestens dreimal mitten im Satz groß (nicht gleich nach einem Doppelpunkt). Überschriften und
   Titelzeilen (Einträge im Verzeichnis, Tabellenköpfe, Zeilen aus lauter großen Wörtern ohne Punkt am Ende) zählen nicht,
   gewöhnliche Wörter (`alltagswoerter` in vorgaben.json) sind nie Namen.
2. **KI-Vorschlag:** Aus Inhaltsverzeichnis, Stichwortverzeichnis und Stichproben schlägt die KI Fachbegriffe vor, je mit
   "bleibt englisch" oder einer oder mehreren deutschen Formen und kurzem Grund. Fachbegriffe, die im deutschen Fachtext
   gebräuchlich englisch bleiben (Paging, Cache, Interrupt, Thread, Exception als Fachwort), bleiben englisch; eine deutsche
   Form nur, wenn sie im Fach üblich ist; hat ein Fachwort eine übliche deutsche Form (use case: Anwendungsfall, dependency:
   Abhängigkeit), bekommt es sie. Neben der deutschen Form gilt das englische Wort als erlaubte Form, außer die KI verbietet
   es (`nur_deutsch`). Verworfen wird: "bleibt englisch" aus lauter Alltagswörtern (auch feature und case: "features" und
   "use cases" werden übersetzt), eine deutsche Form für ein eingeführtes Fachwort aus `englisch_im_fach` (vorgaben.json,
   auch Wortgruppen wie game loop), wenn die vereinbarte Form es nicht trägt, und eine Überschrift statt eines Begriffs (steht
   nur in Überschriften und Titelzeilen).
3. **Pflege:** Die Liste ist an der Buchseite einsehbar und änderbar. Eine Änderung markiert nur die betroffenen Blöcke zum
   Neuübersetzen.
4. **Fragwürdig:** Ein Eintrag von Regel oder KI, der die Regeln von heute nicht besteht (beim Anlegen der Liste und bei jeder
   neuen Fassung der Prüfungen geprüft), wird mit Grund gekennzeichnet, nie gelöscht. Er gilt nicht (weder das Modell noch
   die Prüfung bekommt ihn), bis der Nutzer ihn ändert (dann gilt er, von Hand) oder entfernt; "Fragwürdige entfernen" in
   der Begriffsliste nennt vorher jeden mit Grund und fragt nach. Entfernen übersetzt nichts neu, er galt ja nicht.

Eine deutsche Form darf mehrere erlaubte Formen tragen, mit `|` getrennt ("KI | künstliche Intelligenz"); die erste ist die
vereinbarte, die das Modell bekommt, die Prüfung nimmt jede. Abkürzungen mit üblicher deutscher Entsprechung (AI: KI) stehen
in der Liste für alle Bücher; andere Abkürzungen bleiben. Liegt die Stelle eines Begriffs ganz in der eines längeren Begriffs
der Liste (paging in 5-level paging), zählt sie nur für den längeren, beim Auftrag an das Modell wie in der Prüfung.

## Übersetzen

- Portionen bis etwa 2.500 Zeichen oder 30 Blöcke, immer an Blockgrenzen; im Auftrag stehen Kapitelüberschrift, die
  Begriffsliste für diese Portion und die letzten zwei Sätze davor als Zusammenhang.
- Antwort als JSON-Schema mit genau so vielen Texten wie Blöcken, temperature 0, Priorität Hintergrund.
- Englisch bleiben nur Namen, Produkte, Code, die Begriffe der Liste, die englisch bleiben, und eingeführte Fachbegriffe
  (Cache, Thread, Paging); alles andere wird übersetzt, auch Fachwörter mit üblicher deutscher Form und Aufzählungen von
  Fähigkeiten.
- Jede Antwort wird vor den Prüfungen berichtigt, wo es eindeutig und verlustfrei geht (`pruefen.reparieren`): eine
  Auszeichnungsmarke (`<t1>..</t1>`), die doppelt steht, behält nur das Vorkommen, das zum Original passt (gleicher
  umschlossener Text, sonst das erste); die übrigen und jedes Stück ohne Gegenstück verlieren die Marke, der Text bleibt. Eine
  Auszeichnungsmarke, die es im Original nicht gibt, verliert sie auch. Platzhalter (`<x2/>`) werden nie erfunden oder
  entfernt: einer, der fehlt, bleibt ein Befund für die Nacharbeit, mit seiner Stelle im Original. Jede Reparatur steht als
  Hinweis am Block (`reparaturen`) und im Prüfbericht; eine neue Antwort bringt ihre eigenen mit, ein Text von Hand und neu
  Übersetzen nehmen sie weg.
- Passt die Antwort nicht (Anzahl, Format), wird die Portion halbiert, dann einzeln versucht.
- Kommt ein Block unverändert englisch zurück, wird er gleich einzeln mit eigener Anweisung neu angefragt ("kam eben
  unverändert englisch zurück, übersetze jeden Satz"). Verglichen wird mit geraden Zeichen, wie jede Antwort sie bekommt: ein
  abgeschriebener Absatz mit Gedankenstrich ist sonst nicht zeichengleich. In der Nacharbeit geht die Kopie des Originals
  nie als "frühere Übersetzung" mit, nur ihre Mängel und dieselbe Anweisung.
- Kommt eine Nacharbeit unverändert zurück, steht das als Befund dabei; so ist die nächste Nacharbeit (Temperatur 0) nicht
  wörtlich dieselbe Anfrage.
- Zwischenspeicher je Block über die Prüfsumme aus Text, Begriffsliste und Fassung der Anweisung: Wiederkehrendes
  (Kopfzeilen, gleiche Absätze) wird einmal übersetzt.

## Prüfkette

**Feste Prüfungen** je Block, alle müssen bestehen:

| Prüfung | bestanden, wenn |
|---|---|
| Marken | jede Marke genau einmal, gleiche Schachtelung, keine fremde Auszeichnung (nach der Reparatur); fehlt ein Platzhalter, nennt der Befund seine Stelle im Original |
| Zahlen | dieselben Zahlen, nach Angleichen der Tausender- und Dezimalzeichen (16,000 = 16.000; 1.5 = 1,5); Zahlwörter eins bis zwölf der anderen Seite zählen für eine übrige Zahl, auch vorn in einem Wort (4-level: vierstufig, zweifach, dreidimensional), nie für größere Zahlen (vierzehn, vierzig) und nie für Wörter aus `zahlwoerter.keine` (Zweig, Achtung); für sich fordern sie nichts |
| Einheiten | dieselben Einheiten, keine von selbst zugefügte Umrechnung; eine Zahl gleich hinter dem Satzende ist ein Fußnotenzeichen ("[bit 12].1 A logical": kein Ampere) |
| Bezeichner | Inline-Code, Bezeichner, Adressen und Dateinamen unverändert; eine Abkürzung nur, wenn sie keine deutsche Form in der Begriffsliste hat; Wörter aus zwei großen Wörtern in Überschriftzeilen (ein verlorener Bindestrich: CrossPlatform) nicht |
| Begriffe | jeder Begriff mit "bleibt" steht da, jeder mit Übersetzung in einer erlaubten Form, gebeugt (ansprechender Spiele) oder als Teil eines zusammengesetzten Worts (Spieleplattformen, Serverleistung); kurze Stämme nur an Wortgrenzen; Ziffern und Zeichen am Rand gehören zum Begriff (5-Level Paging, IA-32e mode, x86-64, C++, .NET) |
| Sprache | kein englischer Satz übrig (Stoppwörter je Satz, Begriffe, Code und Namen mit ihrer Abkürzung ausgenommen); ein unverändert gebliebener Block ist unübersetzt, wenn danach drei Wörter oder ein Alltagswort bleiben (5-Level Paging: Introduction); keine stehengebliebene englische Wortgruppe: mindestens zwei klein geschriebene Wörter, die genau so klein im Original stehen ("graphics rendering"), außer Begriffen, die englisch dastehen dürfen, eingeführten Fachwörtern, Bezeichnern, benannten Begriffen in unverändert übernommenen Marken, Text in Anführungszeichen und Wörtern aus `auch_deutsch` (in, so, null) |
| Länge | Verhältnis Deutsch zu Englisch zwischen 0,8 und 1,8 je Block |
| Vollständigkeit | gleiche Zahl an Sätzen, nichts ausgelassen, nichts hinzugefügt (Abweichung höchstens eins) |
| Zeichen | echte Umlaute, gerade Anführungszeichen, keine Sonderstriche, keine Zeichenreferenz als Text (`&lt;` statt `<`) |
| Anrede | durchgehend die Anrede der Fassung: bei du kein Sie, Ihnen, Ihr im Satzinneren (am Satzanfang nur, wenn das Original den Leser anspricht und ein Verb in der Mehrzahl folgt), bei Sie kein du, dich, dir, dein |

Ändert sich die Fassung der festen Prüfungen (`pruefen.FASSUNG`, mit den Grenzen der Länge in `fassung.geprueft_mit`),
prüft der nächste Durchgang zuerst die Begriffsliste nach den Regeln von heute (fragwürdige Einträge gelten nicht), dann
alles, was die KI übersetzt hat, ohne neue Anfrage noch einmal, mit derselben Reparatur der Marken: was besteht, bleibt; eine
offene Stelle, die nur an den festen Prüfungen oder an einem Einwand des Prüfers scheiterte, der nicht gilt oder nie
bestätigt wurde, geht mit vollen Nacharbeiten zum KI-Prüfer; was neu durchfällt, geht mit vollen Nacharbeiten in die
Nacharbeit. Texte und Annahmen des Nutzers bleiben. Eine fertige Fassung läuft dafür beim
Start wieder.

**KI-Prüfer:** Nach den festen Prüfungen bekommt eine zweite Anfrage, nach Möglichkeit mit einem anderen Modell, Original
und Übersetzung satzweise und urteilt je Block nur über den Inhalt: in Ordnung, oder Mangel mit Art und Grund. Ein Mangel
ist nur, was ein Leser des deutschen Texts anders verstünde: sinn (auch eine so falsch gebaute Wortgruppe, dass man sie
anders oder nicht versteht), ausgelassen, hinzugefuegt, englisch (Englisch stehen geblieben, wo das Deutsche eine übliche
Form hat). Kein Mangel: andere Wortwahl mit gleichem Sinn, Synonyme, ein englisch gebliebener eingeführter Fachbegriff, Name,
Produkt oder Code. Begriffe, Rechtschreibung, Zeichen und Anrede prüfen die festen Prüfungen; der Prüfer bekommt die
Begriffsliste darum nicht. Einwände anderer Art (Art "anderes", oder ein Grund, der sich auf eine Begriffsliste beruft) und
solche aus der Zeit, als er auch über Begriffe und Grammatik urteilte, gelten nicht: sie werden verworfen und im Bericht
gezählt (`zahlen.verworfen`).

**Mehrfachprüfung:** Jeder Einwand des Prüfers geht vor der Nacharbeit an eine zweite, unabhängige Anfrage (eigene
Anweisung, das Prüfmodell, Antwortform `bestaetigung`): sie bekommt Original, Übersetzung, Art und Stelle, nicht die
Begründung des ersten Prüfers, und entscheidet nur, ob an der Stelle ein echter Mangel ist, nach denselben Regeln. Die
Einwände einer Portion des Prüfers gehen zusammen hinaus, ohne Einwand gibt es keine zweite Anfrage. Nur ein bestätigter
Einwand gilt (`befund.bestaetigung` trägt den Grund der zweiten Prüfung) und schickt den Block mit dem Grund im Auftrag zur
Nacharbeit; ein nicht bestätigter wird verworfen und gezählt (`zahlen.verworfen`), der Block gilt als in Ordnung. Ein
Einwand "englisch", an dessen Stelle nichts Englisches aus dem Original steht, das übersetzt werden muss (alles ist Begriff
der Liste, eingeführtes Fachwort oder Bezeichner), wird ohne Anfrage verworfen: die Begriffsliste ist die eine Wahrheit
darüber, was englisch bleibt. Antwortet die zweite Prüfung zu einem einzelnen Einwand nicht brauchbar, bleibt er stehen.
Eine offene Stelle mit einem Einwand, der nicht gilt oder nie bestätigt wurde, geht beim Neuprüfen wieder zum Prüfer, mit
vollen Nacharbeiten: die bisherigen galten einem Mangel, den keine zweite Prüfung bestätigt hatte. Bestanden heißt im ersten
Versuch durch alle Prüfungen; wer mehr Versuche brauchte, zählt als nachgearbeitet.

Eine Korrektur gilt erst, wenn sie die festen Prüfungen wieder besteht. Nach zwei Nacharbeiten bleibt der Block im
Original (`lang="en"`, sichtbar markiert) und erscheint im Prüfbericht. Beanstandetes wird nie still eingesetzt.

**Prüfbericht** je Kapitel: Blöcke gesamt, bestanden, nachgearbeitet, offen, verworfene Einwände, reparierte Stellen; je
offener Stelle Original, Übersetzung, Befund (ein bestätigter Einwand mit "bestätigt") und Reparaturen. Offene Stellen
lassen sich annehmen, neu übersetzen oder von Hand ändern. Darunter jede Stelle mit berichtigten Marken (Original,
Übersetzung, Reparaturen), zum Ansehen.

## Abbildungen

Texterkennung je Abbildung mit Lage jedes Worts. Zusammengehörige Wörter werden zu Beschriftungen, jede Beschriftung ein
Block (übersetzt und geprüft wie Text, mit Begriffsliste). Die deutsche Fassung zeigt das Originalbild mit einer Ebene
darüber: Die deutsche Beschriftung deckt die englische ab, in Schriftgröße und Farbe an das Bild angepasst. Ein Umschalter
je Bild und einer für das ganze Buch wechselt zwischen Englisch und Deutsch. Schrift, die zu klein, gedreht oder unsicher
erkannt ist, bleibt englisch und steht im Bericht.

## Ablage und Kennzeichnung

- Tabelle `fassung`: Buch, Sprache, aus Sprache, Stand (läuft, teilweise, fertig, Fehler), Datei in der Kellerwolke,
  Modell für Übersetzen und Prüfen, Fassung der Anweisung, Anrede, womit fest geprüft ist, angelegt, geändert, Zahlen aus
  dem Prüfbericht.
- Tabelle `uebersetzung_block`: Fassung, Kennung, Prüfsumme des Originals, Übersetzung, Stand, Befunde, Reparaturen,
  Versuche; beim PDF Seite, gedruckte Seite und Lage im Original.
- Die Datei liegt in der Kellerwolke neben dem Original unter `Fassungen/de/` (die Fassung eines PDF als EPUB, mit dieser
  Endung). Ohne Kellerwolke liegt sie im lokalen Bestand (wie die Begleiter).
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
| `GET /api/books/{id}/fassungen` | `[{id, sprache, original, stand, kapitel_fertig, kapitel_gesamt, fertig_gegen, modell, pruefmodell, angelegt, geaendert, gewaehlt, anrede}]`; das Original steht immer zuerst (`id` null, `original` true, `anrede` null); `gewaehlt` die Fassung, die "Lesen" öffnet |
| `PUT /api/books/{id}/fassungen/wahl` | `{sprache}` (null: das Original) wählt, was "Lesen" öffnet, je Buch auf jedem Gerät (`user_book_data.fassung_wahl`); Antwort die Fassungen |
| `GET /api/fassungen` | Fassungen in Arbeit (läuft, Pause, Fehler) für die Aufträge: `[{id, buch_id, titel, sprache, stand, anteil, kapitel_fertig, kapitel_gesamt, fertig_gegen, grund}]` |
| `GET /api/books/{id}/fassungen/de/folgen` | Rückfrage vor dem Start: `{seiten, kapitel, bloecke, begriffe, abbildungen, dauer_s, fertig_gegen, tempo_s_je_seite, ablage: {ort, pfad}, anrede, geht, grund}`; `ort` kellerwolke oder geraet; `anrede` die der Fassung, ohne Fassung die Vorgabe; `seiten` beim PDF die Seiten des PDF; `geht` false mit Grund, wenn das Buch nicht englisch ist, das Format noch nicht übersetzt wird (EPUB und PDF werden es) oder ein PDF keinen Text zum Zerlegen hat (Scan: "Texterkennung folgt in der nächsten Stufe") |
| `POST /api/books/{id}/fassungen/de` | startet (oder setzt fort, auch eine fertige mit geänderten Prüfungen), Antwort Stand; Körper optional `{anrede: "du" \| "Sie"}` für eine neue Fassung, ohne Angabe die Vorgabe; eine andere Anrede für eine bestehende Fassung gibt 409 |
| `GET /api/fassungen/{fid}/stand` | `{id, stand, begonnen, bisher_s, noch_s, fertig_gegen, tempo_s_je_seite, kapitel_jetzt, block_jetzt, stationen: [{name, stand, text}], kapitel: [{nr, titel, stand, dauer_s, geschaetzt, bloecke, fertig, geprueft, nachgearbeitet, offen}], zahlen: {bloecke, uebersetzt, bestanden, nachgearbeitet, offen, verworfen, repariert}, grund}`; Stationen in fester Folge: Zerlegen, Begriffe, Übersetzen, Prüfen, Nacharbeit, Setzen; Stand je Station: wartet, laeuft, fertig |
| `POST /api/fassungen/{fid}/pause`, `.../fortsetzen`, `.../abbrechen` | Stand; Abbrechen behält Fertiges, die Fassung bleibt "teilweise" |
| `GET /api/fassungen/{fid}/bericht` | `{zahlen, offen: [{kennung, kapitel, ort, seite_original, seite_gedruckt, original, deutsch, reparaturen: [{art, text, stelle}], befunde: [{art, quelle, text, stelle, bestaetigung}]}], repariert: [{kennung, kapitel, ort, seite_original, seite_gedruckt, original, deutsch, reparaturen}], begriffe_fragwuerdig: [Begriff]}`; `quelle` pruefung oder ki; `stelle` das beanstandete Stück im deutschen Text; `bestaetigung` bei einem Einwand des Prüfers der Grund der zweiten Prüfung (leer: nicht bestätigt); beim PDF `seite_original` die Seite im PDF, `seite_gedruckt` ihre Beschriftung; `zahlen.verworfen` die Einwände des Prüfers, die nicht gelten (anderer Art oder nicht bestätigt); `repariert` (und `zahlen.repariert`) die Stellen, die deutsch in der Fassung stehen und deren Marken berichtigt sind, `reparaturen.art` marken, `reparaturen.stelle` der Text, der die Marke verlor; `begriffe_fragwuerdig` die fragwürdigen Einträge der Begriffsliste |
| `POST /api/fassungen/{fid}/bloecke/{kennung}` | `{aktion: "neu" \| "annehmen" \| "setzen", text?}`; "setzen" nimmt deinen Text (Marken wie im Bericht, Zeichen wie < und & dürfen roh stehen), wenn er die festen Prüfungen besteht, sonst 422 mit Befunden; "neu" und "setzen" nehmen die Reparaturen weg |
| `GET /api/books/{id}/begriffe`, `POST`, `PATCH /api/begriffe/{bid}`, `DELETE` | Begriffsliste je Buch `[{id, englisch, deutsch, bleibt, herkunft, stellen, grund, art, fragwuerdig}]`; `art` begriff oder einheit, `herkunft` regel, ki, hand oder vorgabe; `fragwuerdig` der Grund, warum ein Eintrag von Regel oder KI die Regeln nicht besteht (leer: er gilt); `PATCH` macht einen Eintrag zu einem von Hand, der gilt; `DELETE` eines fragwürdigen übersetzt nichts neu; `GET /api/begriffe` und `POST /api/begriffe` die Liste für alle Bücher |
| `POST /api/books/{id}/begriffe/fragwuerdige/entfernen` | `{ids}` (die, die die Vorschau zeigte) entfernt diese fragwürdigen Einträge; was inzwischen nicht mehr fragwürdig ist, bleibt; neu übersetzt wird nichts; Antwort `{entfernt: [id]}` |
| `GET /api/fassungen/{fid}/datei` | die deutsche Fassung als EPUB für den Leser, auch teilweise (offene Blöcke im Original mit Marke) |
| `GET`, `PATCH /api/fassungen/{fid}/leseposition` | `{position, gelesen_am}`, Body `{position}`: der Lesestand dieser Fassung, bis zum gemeinsamen Lesestand getrennt vom Original (Tabelle `fassung_lesestand`); Lesestand, Vorlesestelle, Notizen und Markierungen des Originals bleiben unberührt |

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
