# Texterkennung für gescannte Bücher (BF-109)

Nutzerwunsch (27.11.2026): "dieses buch lässt sich garnicht in text umwandeln", Entscheidungen: "Erst klassisch, KI als
Nachbesserung", "nachbesserung aber behalten, damit es nicht immer neu durchläuft", "und nur für ein paar seiten auf den man
gerade ist".

## Befund (27.11.2026, nur gelesen, private Probe)

- 35 von 2528 PDF-Büchern haben keine Textschicht, 35 weitere sehr wenig (unter 100 Zeichen je Seite). Beispiel Buch 3899:
  204 Seiten, je Seite ein Bild mit 860 mal 1222 Bildpunkten (96 dpi), keine Schrift.
- Klassische Erkennung (Tesseract 5, deutsch und englisch) liest an diesem Buch Fließtext, Überschriften, Aufzählungen und
  Silbentrennung fast fehlerfrei, etwa 1,2 Sekunden je Seite am Mac. Schwach sind Tabellen aus Strichen und Code in Kästen;
  dort hilft die Nachbesserung.

## Entwurf der Lösung

1. **Erkennen** (`backend/app/texterkennung/`): je Seite das Seitenbild in Graustufen (`TEXTERKENNUNG_DPI`, 300) an Tesseract
   (`TEXTERKENNUNG_SPRACHEN`, deu+eng), Ausgabe TSV mit Wörtern, Lage, Sicherheit, Block, Absatz und Zeile; ein Kern
   (`TEXTERKENNUNG_KERNE`, 1), Frist je Seite (`TEXTERKENNUNG_FRIST_S`). Ohne Tesseract auf dem Gerät ruht die Erkennung mit
   Grund; die App läuft ohne sie weiter (Rückfallschicht, SCHICHTEN.md).
2. **Ablage**: je Buch `erkennung.jsonl` im Ort texte, eine Zeile je Seite und Fassung mit Herkunft (`klassisch` oder `ki`),
   Werkzeug und Zeit; nur angehängt, die jüngste Zeile einer Seite gilt. Als Begleiter in der Kellerwolke, damit sie einen
   Neuaufbau übersteht. Neu erkannt wird nur, was keine Zeile hat, oder auf ausdrücklichen Wunsch.
3. **Eine Textschicht**: Textansicht, Volltext, Suche, Vorlesen und Codestellen lesen eine Seite über dieselbe Stelle. Hat die
   PDF-Seite keinen lesbaren Text, aber eine Erkennung, gilt die Erkennung, mit dem Merkmal "erkannt": keine Festbreite aus
   Schriftmaßen, das Seitenbild selbst ist keine Abbildung. Das Original bleibt unverändert.
4. **Auftrag "Texte erkennen"** (sichtbar, anhalten, fortsetzen, nach Neustart weiter): je Seite ohne Text ein Stück, Vorrang
   für die Seiten, auf denen jemand gerade liest (die aktuelle und `TEXTERKENNUNG_VORRANG_SEITEN` danach), dann der Rest Buch
   für Buch. Ist ein Buch fertig, entstehen Volltext, Suchindex, Seiten und Codestellen neu.
5. **Nachbesserung** (Schritt 2, später): nur auf Wunsch und nur für die paar Seiten, auf denen man gerade liest, über die
   Leitstelle; das Ergebnis bleibt als Zeile mit Herkunft `ki` und läuft nie wieder von selbst.
6. **Oberfläche**: keine neue Gestalt. Wo die Textansicht heute auf die Originalansicht hinweist, steht "Text wird erkannt"
   mit drehendem Zeichen, bis die Seite da ist.

## Reihenfolge des Baus

1. Tesseract im Abbild, Erkennen einer Seite, Ablage mit Tests (erfundene Seitenbilder).
2. Textschicht für erkannte Seiten in Textansicht, Volltext und Suche.
3. Auftrag mit Vorrang, Weg für den Vorrang aus dem Leser, Anzeige in den Aufträgen.
4. Im Betrieb an Buch 3899 prüfen, dann den Bestand laufen lassen.
5. Nachbesserung über die Leitstelle (eigener Schritt).

## Stand des Baus (Schritte 1 bis 3, 27.11.2026)

Gebaut: Tesseract im Abbild, das Paket `backend/app/texterkennung` (Programm, Erkennen, Ablage, Textschicht, Auftrag mit Wache),
der Weg für den Vorrang, `schicht` je Seite in der Textansicht, "Text wird erkannt" im Leser. Wege und Auftrag in
[SCHNITTSTELLE.md](SCHNITTSTELLE.md#texterkennung-gescannter-bücher-bf-109).

Abweichend vom Entwurf: erkannt werden nur die Seiten ohne Text eines Scans (`TEXTERKENNUNG_SCAN_ANTEIL`, 0,5 der Seiten ohne
lesbaren Text). Sonst bekämen fast alle PDF mit einem Umschlagbild auf Seite 1 eine Erkennung, und die Textansicht zeigte dort
erkannte Wörter statt des Umschlags; mit 0 gilt wieder jede Seite ohne Text.

Messung an der privaten Probe (vier Seiten aus Buch 3899, 860 mal 1222 Bildpunkte, 96 dpi, Mac, ein Kern):

| | |
|---|---|
| Rendern in Graustufen, 300 dpi | 0,06 bis 0,09 s je Seite |
| Erkennen, deu+eng | 0,8 bis 1,5 s je Seite (Mittel 1,1 s); mit 200 dpi etwa ein Fünftel schneller, etwas mehr unsichere Wörter |
| Speicher des Programms | höchstens 140 MB je Seite |
| Ablage | etwa 17 KB je Seite in `erkennung.jsonl` |
| Textansicht aus der Erkennung | 0,04 s für vier Seiten |

Was die Textansicht daraus macht: alle vier Kapitelüberschriften als Überschrift (Größe aus der Höhe der Wörter), Fließtext als
Absätze mit aufgelöster Trennung ("Softwareentwick-" und "lungsmethoden"), die elf Punkte zweier Listen je als eigener Listenpunkt
(neun kleine Aufzählungspunkte liest das Programm als Doppelwinkel oder Plus, sie werden wieder Punkte; zwei als "-", die bleiben), Kopf-
und Fußzeilen fallen weg, Fotos und eine Tabelle als Ausschnitt der Seite. Schwach bleiben, wie erwartet, eine Tabelle aus Strichen in einem Codekasten (wird ein
Absatz), farbiger Code (teils falsch gelesen) und Text, der um ein Symbol fließt (in Zeilen geteilt); hier hilft die
Nachbesserung.

Offen: Nachbesserung über die Leitstelle (Schritt 5); die Übersetzung liest Scans noch nicht über die Textschicht; Prüfung im
Betrieb an Buch 3899 (Schritt 4).
