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
