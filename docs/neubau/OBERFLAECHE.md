# Oberfläche Glaswelt (BF-9): Abhakliste alt zu neu

Maßstab ist der Entwurf `mockups/glaswelt`. "Geprüft" heißt: im Prüfbrowser bedient, mit Probedaten und dem Probe-Server. "Nachgebaut"
heißt: die Antwort des fremden Dienstes war gestellt, weil er im Probebetrieb fehlt. "Nein" ist gebaut, aber nicht durchgespielt.

Aufbau: `frontend/src/stil` (Marken, Glas, Schale, Teile, je Ansicht eine Datei, Breiten zuletzt), `lib/teile` (Bausteine),
`lib/schale` (Kopf, Leiste, Vorschau, Tafel, Felder), `lib/stand` (Zustand), `lib/annahme` (Hochladen ohne Oberfläche),
`lib/leser` (Lese-Logik ohne Oberfläche), `lib/api` (Schnittstelle), `ansichten/<bereich>`.

## 0 Querschnitt

| Funktion | Neu | Geprüft |
|---|---|---|
| Adressen /, /book/:id, /book/:id/read, /authors, /author/:id, /search, /collection/:id, /import, /settings, /settings/* | `App.svelte`, dazu /danke und eine Seite für Unbekanntes | ja |
| Alte Parameter der Bibliothek, der Suche und des Lesers | `stand/filter`, `stand/suche`, `leser/ziel` | ja |
| Verweise ohne Neuladen, Cmd, Strg, Umschalt, Alt, Mittelklick wie im Browser | `lib/router` | ja (Test) |
| Zurück und Vor, Rollhöhe bleibt | `lib/rollstand` | ja |
| Neue Fassung lädt selbst neu, nie bei Vorlesen oder Hochladen; Band mit Knopf | `lib/fassung`, `schale/Fassungsband` | Band nein |
| Anmeldung bei 401, gilt in allen Tabs | `App.svelte` | Abmelden ja, zweiter Tab nein |
| Hinweise, Klick schließt | `teile/Meldungen` | ja |
| Kopieren ohne https | `lib/polyfills` | nein |
| Gemerkte Werte unter denselben Schlüsseln | `lib/speicher` | ja |

## 1 Bibliothek

| Funktion | Neu | Geprüft |
|---|---|---|
| Trefferzahl, Nachladen 48 je Seite, Stand "x von y" | Werkzeugzeile, `Nachlader` | ja (139 Bücher, ohne Doppel) |
| Filter Regale (mehrere, Suche, erste 50), Sammlung, Format (5), Bewertung, Etiketten, Markierungen | Leiste und Feld "Mehr" | ja |
| Schalter Favoriten, Lesesofa, PDF, EPUB, Text | Chips | ja |
| Alle Filter entfernen, auch bei Filtern der Leiste (Fehler 27) | "Filter aufheben" | ja |
| gelesen, hat_isbn, hat_highlights, weiterlesen, hat_labels | Leiste, Feld, Adresse | ja |
| Sortierung mit Richtung, Spaltenköpfe ziehen mit (28), dazu Jahr, Bewertung, Verlag | Auswahl und Knopf | ja |
| Fünf Ansichten | Segment, Schlüssel `viewMode` | ja |
| Bearbeitungsmodus, endet beim Verlassen (29) | Knopf | ja |
| Alle geladenen wählen | Auswahlleiste | ja |
| Lädt, Fehler mit Erneut, leer, leer mit Filter (27) | `teile/Zustand` | leer mit Filter ja, Fehler nein |
| Nach Änderungen auffrischen ohne Doppel (7) | `bestand.beiAenderung` | ja |
| Letzte Filter nur beim Start wiederherstellen (26) | `filter.stelleWiederHer` | ja |
| Öffnen, Favorit, direkt lesen | Klick wählt, zweiter öffnet; Schnellgriffe | ja |
| Angaben an der Kachel | Titel, Autor, Format, Stand; alles Weitere in Vorschau, Hinweis und "Große Kacheln" | ja |
| Großes Bild beim Überfahren (Umschläge und Listen) | `Grossbild` | ja |
| Auswahl einzeln, Rechteck, Ziehen über Zeilen | `ziehauswahl.ts` | ja |
| Detailliste mit Seiten, Verlag, ISBN, allen Regalen, Favorit, Lesesofa | `Detailliste` | ja |
| Stapel: Favorit, Lesesofa, Regal zuweisen mit Suche | Auswahlleiste | Lesesofa, Regal ja |
| Entfernen mit Rückfrage und Folgen, Entf und Rücktaste nie im Textfeld (8) | Auswahlleiste | ja |
| Esc nimmt immer nur das zuletzt Geöffnete (8) | `lib/flucht` | ja |

## 2 bis 4 Leiste, Kopf, Aufträge

| Funktion | Neu | Geprüft |
|---|---|---|
| Alle, Bücher, Dokumente, Gelesen, Ungelesen, Weiterlesen, Favoriten, Lesesofa, Markiertes mit Zahlen | Leiste, kombinierbar, Gelesen und Ungelesen als zwei Einträge | ja |
| Regale mit Symbol, Farbe, Zahl, mehrere zugleich; Sammlungen, eine zugleich | Leiste | ja |
| Autoren, Einstellungen | Leiste | ja |
| Hinzufügen | Kopf, am Telefon Tafel | ja |
| Schnellnotiz mit Wortzahl, Abmelden | Kopf; schmal unter "Weiteres" | ja |
| Lämpchen | Leistenfuß aus /api/verbindungen, dazu KI | ja |
| Fassung, Hinweis nur auf höhere Fassung (46) | Leistenfuß | Test ja, Hinweis nein |
| Leiste ein und aus, Logo, Spenden, Suche, Hintergrundbild blättern, Licht | Kopf, Feld Darstellung | ja |
| Glas (klar, milchig, dicht, ohne), Dahinter (Regalwand, Licht, ruhig, eigenes Bild), vier Schriftstufen | Feld Darstellung, Einstellungen | ja |
| Aufträge: Aufnahmen, Einlesen mit Fehlern und Wartenden, Ergänzen, Autorenabgleich, gemeinfreie Bücher | Feld "Aufträge" | Aufnahmen, Einlesen ja; übrige siehe unten |
| Fertige bereinigen, Ergebnis der Ergänzung ausblendbar (41) | Feld "Aufträge" | nein |

## 5 Suche

| Funktion | Neu | Geprüft |
|---|---|---|
| Suchen mit Enter, Feld zeigt das Suchwort (31) | `Suchfeld` | ja |
| Vorschläge, Pfeile, Verlauf mit Entfernen und Leeren | `Suchvorschlaege`, `Suchanfang` | Vorschläge ja, Verlauf gesehen |
| Suchsprache vollständig (author, date, >=, <=, *, AND, OR, NOT) | `Suchhilfe` auf /search | ja |
| Treffer mit Umschlag, Auszug, Sprung | `Worttreffer`, Seite und Zahl der Stellen, sobald sichtbar | ja |
| Aktive Filter, jetzt herausnehmbar | Chips | ja |
| 20 je Seite, lädt beim Rollen nach | `Nachlader` | ja (110 Treffer) |
| Relevanz in Prozent | entfallen (30 war falsch), die Reihenfolge bleibt | - |
| Nur `<mark>` aus dem Text, sonst Text (9) | `lib/auszug` | ja (Test) |
| Neu: Bedeutung und Beides, ohne Rechner gelten die Wörter | `Suchlauf`, `Sinntreffer` | Ausfall ja, Treffer nachgebaut |
| Neu: im Assistenten fragen | `Antwort`, Adresse aus /api/config/oberflaeche mit `?frage=` | Verweis ja |

## 6 Buchseite

| Funktion | Neu | Geprüft |
|---|---|---|
| Hintergrund aus dem Umschlag | Licht der Kulisse | ja |
| Zurück zur Bibliothek samt Filter | Knopf | ja |
| Lesen, Weiterlesen, von vorn, Herunterladen | Buchkopf | ja, Herunterladen Verweis |
| Lesestand mit Papier, Ansicht, Schrift, Schriftprobe, auch für Text (24) | Buchkopf, `lib/lesestand` | ja |
| Autoren als Verweise, Verlag, Angaben, Datei | Buchkopf | ja |
| Bewertung, Favorit, Lesesofa, Gelesen | Buchkopf, Vorschau | ja |
| Buch löschen (BF-60): Taste mit Abstand hinter Gelesen, Rückfrage mit allen Folgen des Buchs vom Server, Datei in den Papierkorb der Kellerwolke, danach zurück zur Bibliothek samt Filter | Buchkopf, `buch/loeschen` | Tests, Betrieb mit eigenem Probebuch |
| Bearbeiten: alle Felder, Typ, Sammlung, Band; Eingaben bleiben bei Fehlern (5) | `BuchBearbeiten` | ja |
| Gestaltete Deckblätter (BF-59): Bücher mit fast weißer Titelseite (`umschlag` vom Server) zeigen ein Blatt nach Art und Gattung wie in der Stilprobe, Dokumente als Ordnerrücken; Titel eingepasst, alles aus den Daten maskiert, keine Kennungen im SVG. Dasselbe Blatt steht für reine Textdateien, wenn das Bild ausbleibt, und bei gemeinfreien Treffern; der gezeichnete Ersatz ist entfallen | `lib/umschlag` (`gestaltet`, `muster`, `satz`, `zuordnung`), `teile/Deckblatt`, `teile/Umschlag` | Tests, Blätter mit Grenzfällen gerendert; im Betrieb nein |
| Farben des Blatts für Licht und Regalwand (BF-59): das Blatt meldet seine drei Farben wie ein Bild beim Laden, es gilt, was zuletzt zu sehen war | `schale/regalfarben` (`nimm`), `stand/wahl` | Tests; im Betrieb nein |
| Umschlag wählen (BF-59): unter dem Umschlag "Gestaltet" oder "Titelseite", nur bei fast weißer Titelseite oder schon getroffener Wahl; frischt Buchseite, Liste und Vorschau | Buchkopf, `stand/merkmale` | Test; im Betrieb nein |
| Art und Gattung (BF-59): bei den Angaben; Bearbeiten mit Gattung, die Art kennt Dokument, das Blatt wechselt schon vor dem Speichern mit; beide Listen nur vom Server | Buchkopf, `BuchBearbeiten`, `Regalchips`, `stand/arten` | Test der Angaben; Bearbeiten im Betrieb nein |
| ISBN im Text suchen und übernehmen | `Isbnsuche` | Suche ja, Übernehmen nein (keine ISBN im Probebestand) |
| Einordnung durch die KI mit Prozenten | Fenster "Vorschlag der KI" | Fehlerweg ja, Vorschläge nein |
| Vergleich aus drei Quellen, Umschlag, Regale, "Alle Daten" | `Angabenvergleich`, `Vergleichstabelle` | nachgebaut |
| Beschreibung aus dem Buchtext | "Aus dem Buchtext" | Laden ja, Übernehmen nein |
| Umschlag neu aus der Datei | Knopf | ja |
| Regale: 5 und Rest, filtern, dazu, heraus; Sammlung, Typ | `Regalchips` | ja |
| Notizen: neu mit Seite, springen (12), löschen mit Rückfrage; dazu ändern | `Stellen`, `Notizzeile` | ja |
| Markierungen: springen (11), Name, Notiz, ganzer Text, löschen mit Rückfrage | `Markierungszeile` | ja, Löschen nein |
| Suche im Buch mit drei Schaltern, Trefferzahl, Sprung; dazu Bedeutung | `Buchsuche` | ja |
| Vom selben Autor, im selben Regal | `Verwandte` | ja |
| Neu: wo das Buch überall ist | `Ablageorte` | ja |

## 7 bis 9 Autoren, Autorenseite, Sammlungen

| Funktion | Neu | Geprüft |
|---|---|---|
| Zahlen, Suche, Sortierung, Richtung, Karten | Autoren | ja |
| Nachladen 36 je Seite | `Nachlader` | nein (nur 24 Autoren) |
| Abgleich mit Schaltern, Fortschritt, Anhalten, läuft nach Seitenwechsel weiter | Karte und Aufträge | ja |
| Ergebnisliste mit Sicherheit | Karte | nein (kein Lexikon im Probebetrieb) |
| Neu bilden, Verwaiste löschen, je mit Rückfrage | Knöpfe | ja |
| Steckbrief, Verweise, Konfidenz mit Erklärung | Autorkopf | Daten ja, Foto und Konfidenz nein |
| Bearbeiten, Eingaben bleiben bei Fehlern | `AutorBearbeiten` | ja |
| Vergleich je Feld und Foto, Werke im Bestand, nur Gewähltes senden (44) | `AutorVergleich` | nachgebaut |
| Werke, Bücher, Biografie | Karten | Bücher, Biografie ja |
| Sammlung mit fünf Ansichten, Band als Zahl sortiert (34), Verweise zum Filtern und Verwalten | /collection/:id | ja |
| Sammlungen verwalten | Einstellungen, Regale und Sammlungen | ja |

## 10 bis 14 Leser

| Funktion | Neu | Geprüft |
|---|---|---|
| PDF: zurück, am Telefon zur Herkunft | obere Leiste | ja |
| Seite vor und zurück, Seitenfeld, Balken zum Springen, Pos1, Pfeile | untere Leiste, Tasten | ja |
| Zoom in Stufen (21), 100 %, Tasten | Feld | ja |
| Fortlaufend, Seitenbreite, ganze Seite, Doppelseite, Einzelseite, nur Text | Feld | ja |
| Papier hell, Sepia, dunkel, Kontrast | Feld | ja |
| Fundstelle aus ?q und ?stelle, nie gespeichert | Textebene | ?q ja, ?stelle nein |
| Auswahlmenü: markieren (16 Farben), Kopieren, Vorlesen, Schnellnotiz, Buchnotiz neu, anhängen, ersetzen; schließt beim Abwählen (23) | `Auswahlmenue` | ja bis auf Vorlesen, Kopieren, Ersetzen |
| Vorlesen: siehe unten (BF-27) | Menü oben, am Telefon im Feld, im Vollbild am Zeichen oben rechts | ja, mit nachgestelltem Sprechdienst |
| Vollbild, mit Ersatz ohne Browservollbild: Blatt bis an alle Kanten, auch hinter Kerbe und Home-Balken, `theme-color` in Blattfarbe; nur das Zeichen zum Verlassen schwebt, 18 von links und 5 von oben, Tippfläche 44 (BF-21) | `Leserahmen`, `stand/blattgrund`, `stil/leser.css` | alle Formate, hell und dunkel, 390, 844 quer, 834, 1440; echtes Vollbild des Browsers nein |
| Innerer Rand 0 bis 120, je Gerät gemerkt, in PDF als Text, MD, TXT, EPUB und MOBI (BF-21) | `leser/blattrand`, `Randregler` | ja |
| Schriften (BF-22): zwölf an einer Stelle in drei Gruppen (mit Serifen, ohne Serifen, für leichteres Lesen), lokal über npm, nur lateinisch 400, 400 kursiv, 700; geladen erst, wenn gewählt oder die Auswahl offen ist, im EPUB nur die gewählte im Rahmen; gemerkte Wahl bleibt | `leser/schriften`, `Schriftwahl` | ja; Startseite 466,41 auf 466,99 kB (gzip +0,16 kB), CSS gleich |
| Tasten einer Gruppe gleich breit und gleich hoch (BF-21) | `.tastenraster` in `stil/leser.css` | gemessen 360, 390, 1440, sehr groß |
| Herunterladen, im Browser öffnen, Hinweis nach 4 Sekunden | Feld, `Ladehinweis` | nein |
| Stand merken, beim Verlassen sofort (19), Adresse geht mit, Telefon getrennt vom Rechner (20) | `leser/position` | ja |
| EPUB: blättern, Prozent, Kapitel, Verzeichnis, Themen, Schriften, ein- und zweispaltig (22), Suchtreffer (17), ?cfi, ?percent | `EpubLeser` | ja, Wischen und Transparenz nein |
| MOBI | wie EPUB | nein (keine Probedatei) |
| MD und TXT: Stand, Breiten, Themen, Verzeichnis, Hinweiskästen, Diagramme, Codefarben; ?page, ?percent, ?q (13) | `TextLeser` | ja |
| Markieren in MD und TXT (14), als `percent:N` in den Markierungen, damit die Buchseite sie kennt (15) | `TextLeser` | ja |
| Etiketten setzen, ändern, löschen | Feld Notizen und Markierungen | setzen, löschen ja |
| Textansicht: Größe, Schrift, Zeilen, Farbe, frühere Seiten, Abbildungen mit Lupe | `Textansicht`, `Bildlupe`, jetzt auf allen Geräten | ja, Scan-Hinweis und Lupe mit zwei Fingern nein |
| Markierungen und Buchnotizen im Leser: springen, Farbe, Name, Notiz, Text, kopieren, Schnellnotiz, löschen mit Rückfrage | Feld rechts statt verschiebbarer Fenster, wie im Entwurf | ja, Kopieren nein |
| "Von vorn" verwirft nur die Stelle (18) | `leser/ziel` | ja (Test) |

### Fokus und Lesehilfen am Rechner (BF-24)

Eigene Taste oben im Leser (Rechner und Tablet) mit dem Feld "Fokus und Hilfen", dazu die Tastenkürzel. Alles je Gerät gemerkt
(`leser/lesehilfen`), am Telefon nur Voreinstellungen und Blatt und Satz.

| Teil | Ort | Geprüft |
|---|---|---|
| Fokus als eine Schicht aus vier Streifen um ein klares Fenster, außen dunkel oder milchig (Hauch Papier, 2 px Unschärfe), Stärke, Übergang, Farbe; Klicks, Auswahl und Scrollen gehen durch, Leisten und Felder liegen darüber | `Fokusschicht`, `leser/fokus` | 1440 und 1920, hell und dunkel |
| Fenster: auf der Seite ziehen, an Kanten und Ecken fassen, Doppelklick stellt zurück (nur solange das Feld offen ist) | `Fokusschicht` | ja |
| Lineal: 1 bis 8 Zeilen, folgt der Maus, den Pfeilen (am Rand geht der Text weiter) und beim Vorlesen dem Satz | `Fokusschicht`, `Hilfensteuerung` | ja |
| Absatz: in Textansichten, MD, TXT, EPUB der Absatz unter der Maus, beim Vorlesen der gelesene; beim PDF als Bild nicht angeboten | `leser/fokus` | ja, beim Vorlesen gemessen |
| Ruhe: Leisten und Zeiger gehen nach 2,5 Sekunden, Bewegung holt sie; im Vollbild der Zeiger von selbst | `Hilfensteuerung` | ja |
| Von selbst lesen: Tempo in Zeilen je Minute, gescrollt ruhig in ganzen Bildpunkten, geblättert je Schirm; Leertaste hält an | `leser/selbstlauf` | ja |
| Blatt (Helligkeit, Kontrast, Wärme, Graustufen; Abbildungen) und Satz (Zeichen-, Wort-, Absatzabstand, Blocksatz, Silbentrennung); EPUB über die Regeln im Rahmen, PDF als Bild nur das Blatt | `Blattfeinheiten`, `stil/lesetext.css` | ja |
| Voreinstellungen Tag, Papier, Abend, Nacht und eigene: speichern, umbenennen, löschen mit Rückfrage, auf Wunsch je Buch gemerkt | `Blattfeinheiten`, `leser/lesehilfen` | Tests und Bedienwege |
| Tastenkürzel: F, Umschalt F, [ und ], Pfeile fürs Lineal, R, A, Leertaste, V, +/-, ? | `Tastenfeld`, `Hilfensteuerung` | ja |

### Marken am Rand (BF-28)

Nach dem abgenommenen Entwurf (Marken am Rand des Blatts): Notizen, Markierungen und Etiketten als bunte Streifen. Breit (34 x 46, Nummer)
für die offene Seite auf Höhe ihrer Stelle, sie gehen beim Rollen mit; schmal (15 x 26) für alle übrigen an festem Platz nach ihrem
Anteil im Buch. Dicht liegende rücken untereinander, bei sehr vielen fassen sie sich zusammen (Zahl), nie übereinander, auch nicht über
breite. Am Telefon 6 Pixel schmal (30 und 64 hoch) am Rand, Tippfläche 44, die nur ein Tippen genau dort fängt; Wischen und Auswählen gehen
durch. Überfahren oder Tippen klappt die Karte auf (Text, Art, Stelle), noch ein Tippen öffnet Notizen und Markierungen, schmale springen.
Aufgeklappt hat die Karte Bearbeiten und Löschen (BF-61), bei mehreren Einträgen "Alle zeigen"; Rechtsklick auf eine Marke zeigt das
eigene Menü mit Hinspringen, Bearbeiten und Löschen. Löschen fragt immer erst nach, wie im Feld Notizen und Markierungen.

| Teil | Ort | Geprüft |
|---|---|---|
| Einträge, Lage, Zusammenfassen | `leser/randmarken`, `Randmarken` | Tests, 1440 und 390, hell und dunkel |
| Wo eine Stelle steht, je Format (PDF Original und Text, EPUB, MOBI, MD, TXT; gerollt und geblättert) | `Randort` der Leser | PDF, MD, EPUB |
| Aus und an im Feld Darstellung, je Gerät gemerkt | `leser/randschalter` | ja |
| Buchseite: dieselbe Reihe am Umschlag | nicht gebaut: Stellen im EPUB haben ohne geöffnetes Buch keinen Anteil, der Umschlag gehört zu BF-17 | nein |

### Vorlesen (BF-27)

Vorgelesen wird aus einer Lesequelle je Leser (`lib/vorlesen/typen`: `Lesequelle`, `Buchquelle`): Einheiten mit Text erst bei Bedarf,
Name, Kapitelgrenzen, hervorheben, Ansicht führen. Die Folge (`vorlesen/folge`, `vorlesen/zulauf`) holt Stück für Stück in eigenen kurzen
Anfragen voraus (kein langer Strom, der an einer Grenze reißt), liest über das Ende einer Einheit hinaus und spielt über ein Tonelement,
das am gesperrten Telefon weiterläuft.

| Teil | Ort | Geprüft |
|---|---|---|
| Einheiten: PDF Seiten (Textauszug des Servers, sonst Textebene), EPUB und MOBI Abschnitte, MD und TXT Stücke ab jeder Überschrift | `pdf/lesequelle`, `epub/lesequelle`, `text/lesequelle` | ja |
| Umfang: Diese Seite, Dieses Kapitel (nur mit Verzeichnis), Ab hier, Ganzes Buch von vorn; begonnen wird am Anfang des Satzes | `Vorlesen` | ja, alle Formate |
| Spieler: Abschnitt und Satz zurück und vor, Pause, Stopp, Tempo ohne andere Tonhöhe, Stimme, Schlafuhr (Ende der Einheit, des Kapitels, 15, 30, 60 Minuten) | `Spieler`, `Vorlesen` | ja |
| Satz mitführen: hervorgehoben ohne jedes Element im Text (Hervorhebungs-Schnittstelle des Browsers, sonst Rechtecke dahinter); Markierungen und Suchtreffer ebenso | `leser/hervorhebung`, `text/markierung` | Zeilen bitgenau verglichen: MD, TXT, PDF als Text, EPUB, geblättert und gescrollt, 1440 und 390 |
| Mitlesen: gescrollt bleibt die Zeile zwischen oberem Fünftel und Mitte, Zeile um Zeile nachgeführt; geblättert wird am Ende des Schirms; wer selbst scrollt oder blättert, wird nicht zurückgezogen, "Zur Stelle" bringt hin | `leser/mitlauf`, `vorlesen/folge` | ja |
| Vollbild: Zeichen oben rechts (18 von rechts, 5 von oben) öffnet das Feld; ein schmaler Spieler erscheint bei Berührung oder Mausbewegung | `Leserahmen` | 390 hoch und quer, 1440, hell und dunkel |
| Sperrbildschirm und Kopfhörertasten (Titel, Umschlag, Tasten) | `vorlesen/mediensitzung` | gesetzt, an echtem Gerät nein |
| Abriss: zwei neue Versuche, dann steht es still mit klarer Meldung, Weiter setzt an derselben Stelle fort; beim Verlassen des Lesers Schluss | `vorlesen/zulauf`, `Leser` | ja (Probe-Server mit Fehlern) |

### Blättern oder Scrollen (BF-16)

Wahl oben im Feld "Schrift und Papier", in allen Formaten derselbe Baustein (`Leseartwahl`), je Gerät gemerkt (`leser/leseart`): einmal für
Blätter (PDF, MD, TXT, Vorgabe Scrollen), einmal für Bücher mit eigenem Umbruch (EPUB, MOBI, Vorgabe Blättern).

| Teil | Ort | Geprüft |
|---|---|---|
| Gemeinsame Schicht für fließenden Text: Schnittstelle `Lesefluss`, darunter `Blaetterfluss` (CSS-Spalten, ein Schirm) und `Scrollfluss`; die Stelle ist ein Zeichen im Text, kein Bildpunkt | `lib/leser/fluss` | Tests (Schirme, Anker, Nachladen vorn und hinten), Bedienwege |
| Keine halbe Zeile, Bilder, Tabellen und Kästen ungeteilt, wenn sie auf einen Schirm passen | `stil/lesetext.css` | ja, jede Zeile gemessen |
| Stelle bleibt beim Drehen, bei Schrift und Zeilen, beim Wechsel der Art, beim Nachladen | `Textfluss` | ja (MD, TXT, PDF als Text) |
| Wischen, Tippen am Rand (Mitte: Leisten aus und ein), Rad ein Schritt je Dreh, Pfeile, Bild- und Leertaste; Auswahl, Links und Felder gehen vor | `leser/blaettergesten`, `leser/blaettertasten` | ja |
| PDF als Text: Seiten vorn und hinten nachgeladen, Markieren und Fundstelle auch hier | `Textansicht`, `pdf/textseiten` | ja |
| PDF Original: eine Seite je Schirm, Nachbarn vorab gezeichnet; vergrößert erst schieben, dann blättern; Telefon quer in Abschnitten | `PdfSeiten`, `pdf/anzeige` | ja (390, 844 quer, 834, 1440) |
| EPUB und MOBI: scrollen, am Kapitelende weiterziehen | `epub/anzeige`, `epub/kapitelrand` | ja |
| Ansicht eines PDF, die für dieses Buch gewählt wurde, geht vor der Wahl des Geräts | `PdfLeser` | ja |
| Großer Text (2,7 MB) | `Schlichttext`, `text/bloecke` | steht nach 1,5 s, 15 ms je Schritt |

### Ausführen (BF-29)

Nach dem Entwurf `ausfuehren.html`: Listings aus dem Buch laufen in der Sandbox der Codeschmiede. Nur mit Anschluss (`anschluesse.ausfuehren`);
ohne ihn gibt es keine Taste, und Editor wie Debugger sind nicht im Bau der Startseite: das Fenster lädt sie erst beim ersten Öffnen
(`Schale` importiert `Ausfuehrfenster` bei Bedarf, darin `appkern-oberflaeche/code`). Die Marken des Appkerns stehen an einer Stelle für
die Glaswelt (`stil/ausfuehren.css`), die Farben des Editors bleiben die der Codeschmiede, gewählt nach dem Thema der App.

| Teil | Ort | Geprüft |
|---|---|---|
| Codestellen vom Server (`/api/books/{id}/codestellen`): im PDF in Fenstern von 40 Seiten, sonst fürs ganze Buch; läuft die Erkennung oder die Vorprüfung noch, fragt der Leser später wieder | `leser/codestellen` | Tests, Probe |
| Taste, wo der Code beginnt, mit Sprache und Vorprüfung als Punkt (grün: läuft für sich, sonst "Auszug" mit kurzem Grund); jeder weitere Teil "Fortsetzung von S. n" | `Codetaste` | ja |
| PDF Original: Ebene je Seite aus den Rechtecken des Servers, Streifen am offenen Listing; PDF als Text: Taste im Kopf des Codes (Feld `kennung`), Ring am offenen | `Codeebene`, `Textansicht` | 1440 und 390, hell und dunkel |
| MD, TXT, EPUB: eine Ebene über dem Buch, der Leser des Formats nennt die Blöcke auf dem Schirm (`Codeort` der Sitzung); im TXT die Zeile des Zauns | `Codetastenebene`, `text/codeorte` | MD, TXT, EPUB geblättert |
| Fenster: verschiebbar wie Nachschlagen, ein Tab je Listing, Kopie je Buch und Stelle (Zurücksetzen mit Rückfrage), Sprache und Fassung (PHP wie in Nachschlag), Ausführen mit Cmd/Strg Enter, als Leiste ablegen; nichts geht beim Blättern oder Seitenwechsel verloren | `Ausfuehrfenster`, `stand/ausfuehren`, `ausfuehren/fassungen` | ja |
| Debugger: Lauf aufzeichnen, Schritt vor und zurück, Haltepunkte, Zeitleiste, Variablen mit Art, Aufrufe, Ausgabe bis hier | `ausfuehren/arbeit`, `Debugansicht` | ja |
| Telefon: Blatt ohne Editor, ausführen und Schritte, fünf Zeilen um die gezeigte, Haltepunkt per Tippen auf die Nummer | `Telefonblatt`, `ausfuehren/zeilen` | 390 |
| Große Schrift: wird es eng, wird erst der Editor kleiner, dann rollt der Inhalt des Fensters; nichts abgeschnitten | `stil/ausfuehren.css` | Sehr groß, 1440 x 900 und 760, 390 |

## 15 und 16 Hinzufügen

| Funktion | Neu | Geprüft |
|---|---|---|
| Hochladen, mehrere, Ordner, Ziehen | `Ablage`, `lib/annahme` | Wählen und Ablegen ja, Ordner nein |
| Sechs Stationen, fortsetzbar, höchstens zwei zugleich, Prüfsumme vorab | `Hochlader` | ja (Tests und Probe-Server) |
| Abriss, Anhalten, Weiter, nach Neuladen Datei noch einmal wählen | `Hochlader`, `zeilen.ts` | ja |
| Schon da, nicht möglich, leer, kaputt, gescheitert | `Aufnahmezeile` | ja, gescheitert nein |
| Angaben ergänzen | Häkchen, geht als `anreichern` mit | Anzeige ja |
| Eingangsordner, alte Sammlung, mit Pfad und Vorschau | `Ordner` | Vorschau ja, Einlesen alte Sammlung ja |
| Bibliothek ergänzen: vier Arten mit Zahlen, Handbearbeitete, Regal oder ohne, Vorschau, Start | `Ergaenzen` | ja, Regalwahl und Anhalten nein |
| Aufgabenliste, "Schon da" richtig benannt (36), Buch öffnen | `Einleseliste` | Anzeige ja |
| Gemeinfreie Bücher: Suche, Auswahl über Seiten (42), Übernahme als Auftrag | `Gemeinfreie` | Suche und Auswahl nachgebaut, Übernahme nein |
| Eingangsordner in der Kellerwolke, wird beim Ablegen erkannt | `Eingangsordner` | siehe Betrieb |
| Aus der Kellerwolke wählen | braucht die Freigabe "Alles lesen" für den App-Zugang, noch nicht gebaut | - |

## 17, 18, 20, 21 Einstellungen, Anmeldung, Schnellnotiz, Hintergründe

| Funktion | Neu | Geprüft |
|---|---|---|
| Schlüssel ansehen und speichern | Verbindungen | ansehen ja |
| Hintergrundbilder hochladen, wählen, blättern, entfernen mit Rückfrage | Darstellung | ja |
| Dienste mit Stand und Feldern, "verbunden" nur nach Prüfung (45) | Verbindungen | ja |
| Neu: Verbindungen und Orte | Verbindungen | ja |
| Regale und Sammlungen verwalten, 24 Farben und eigene, Symbole mit Suche | Regale und Sammlungen | ja |
| KI: Stand, Adresse (mit /v1, 43), Modell, testen, Netz absuchen | KI, Rechtliches, Über | Testen ja, Absuchen nein |
| Anweisungen bearbeiten | Fenster | ja |
| Verzeichnisse, Bücherzahl, Suchindex neu aufbauen | Wartung, Verbindungen | ja |
| Sicherung anlegen, Liste, herunterladen | Wartung | ja, Herunterladen nein |
| Rechtliches, sechs Abschnitte; Über | KI, Rechtliches, Über | ja |
| Anmelden mit Passwort | Anmeldung | Form ja, Anmelden nein |
| Koppeln mit Code, Code aus dem Link | Anmeldung | Form ja, Erfolg nein |
| Schnellnotiz: schreiben, verschieben, Größe, kopieren, leeren mit Rückfrage | `Schnellnotiz` | ja, Kopieren nein |
| Spenden: Ko-fi, drei Währungen mit QR, Adresse kopieren | /danke | ja, Kopieren nein |

## 19 Telefon

Dieselben Bausteine in schmal, Tafel unten. Was am Telefon fehlte, ist jetzt da: Abmelden, Darstellung, Favorit, Lesesofa, Sterne, Filter,
Vorschläge, Suchsprache, Markieren, Notizen, Vorlesen.

| Funktion | Neu | Geprüft |
|---|---|---|
| Suche mit Auszügen, Weiterlesen (8), zuletzt gesucht (12) | /search | ja |
| Buch mit Lesen, von vorn, Herunterladen, Beschreibung | Buchseite | ja |
| Umschalter Text und Original in der unteren Leiste (BF-15), dieselbe Seite, je Gerät gemerkt | `Fussleiste`, `PdfLeser` | ja (360, 390, 430, sehr groß) |
| Telefon (BF-63, Entwurf Vorschlag A): Umschalter nur als Zeichen; vorige und nächste Stelle mit Notiz, Markierung oder Etikett (gesperrt ohne), danach klappt die Karte am Rand auf; Sprungbalken als Linie oben an der Leiste über die ganze Breite | `Fussleiste`, `Stellensprung`, `leser/stellensprung` | Tests, Betrieb am Telefon |
| Leser mit Original, nur Text, Zoom, Papier, Blättern, Verzeichnis; im Querformat gehört die Höhe dem Buch | Leser | ja |
| Tippziele 44, Eingaben ab 16, nichts unter 12 | `stil/breiten.css` | ja |

## Prüfstand

- Jede Ansicht in 1920, 1440, 1180, 834 und 390, hell und dunkel, dazu "Sehr groß" bei 390 und 1440 (216 Bilder am gebauten Stand), am
  Telefon zusätzlich 360 und 430: kein Überlauf, keine Konsolenfehler, keine Schrift unter 12 (außer im Text der Bücher).
- Bedienwege mit echten Maus- und Tastenereignissen: Bibliothek 53, Buchseite und Suche 32, Leser 36, Telefon und Adressen 23,
  Hinzufügen und Entfernen 10, Nachladen 7.
- `npm run build`, `npx vitest run` (114), `npx svelte-check` ohne Fehler und Warnungen.
