# Hochladen mit Vorschau (BF-80)

Nutzerwunsch: Beim Hochladen einer ZIP mit vielen Dokumenten oder einzelner Dateien lässt sich alles zuordnen, und eine
Vorschau zeigt, was beim Bestätigen passiert. Erst die Bestätigung übernimmt.

## Entscheidungen (26.11.2026, im Gespräch geklärt)

1. **Wege:** Hochladen im Browser, einzeln, mehrere oder als ZIP, läuft immer über die Vorschau. Eingangsordner und Ordner
   auf dem Gerät laufen wie bisher von selbst ins Regal; je Weg lässt sich in den Einstellungen "erst bestätigen"
   einschalten.
2. **Doppel:** Dieselbe Datei (gleiche Prüfsumme) ist zum Weglassen vorgewählt. Dasselbe Buch in einem anderen Format
   (etwa das EPUB zu einem vorhandenen PDF) ist als weiteres Format zum vorhandenen Buch vorgewählt. Beides lässt sich in
   der Vorschau umstellen, etwa auf "als eigenes Buch".
3. **Ordner in der ZIP:** Ordnernamen sind Hinweise für die Zuordnung. Passt ein Name zu einer Kategorie des Katalogs oder
   zu einer Sammlung, ist sie vorgeschlagen, sonst ist er ein Vorschlag für ein Etikett. Alles ist änderbar.
4. **Dateien, die kein lesbares Buchformat sind:** Was zu einem Buch gehört (gleicher Name, etwa Umschlag, Beilage,
   Beispielcode), wird sein Begleitmaterial (BF-81). Alles andere steht in der Vorschau unter "nicht übernommen" mit Grund
   und Format. Nichts verschwindet still.
5. **Vorschläge:** Die Regeln des Katalogs schlagen Art und Kategorie sofort vor. Die KI prüft im Hintergrund und ergänzt,
   die Vorschau aktualisiert sich und zeigt je Feld, woher der Vorschlag kommt (Regel, KI, Ordner, Datei, Lücke).
   Bestätigen geht jederzeit, auch bevor die KI fertig ist. Was der Nutzer geändert hat, überschreibt die KI nie.
6. **Warten und Verwerfen:** Nicht bestätigte Dateien warten unter "Zum Bestätigen" bei den Aufträgen, auch über Tage und
   nach einem Neustart. Verwerfen zeigt vorher, welche Dateien aus der Kellerwolke entfernt werden, und löscht erst nach
   einem ausdrücklichen Ja.

## Abnahme des Entwurfs (26.11.2026)

Entwurf Runde 1 abgenommen ("Passt, bauen"), mit diesen Antworten:
- Die Vorschau ist eine eigene Ansicht: Auswahl und Fuß stehen fest, nur die Liste rollt. Am Telefon zeigt sie Karten.
- Nach "Übernehmen" bleiben die ZIP selbst, weggelassene Doppel und nicht übernommene Dateien im Eingang liegen. Ein
  Hinweis nennt sie ("3 Dateien blieben im Eingang"). Nichts wird von selbst weggeräumt.
- "Anleitung" wird eine eigene Art unter Besonderes, neben Dokument, Heft, Katalog und Broschüre. Regeln und KI erkennen
  sie, die Kategorie ordnet sie nach Bereich ein.
- Die Einstellungen stehen in einem neuen Reiter "Hinzufügen": "erst bestätigen" je Weg und die Suchadresse für fehlende
  Bände (BF-75).
- Verwerfen ohne Kellerwolke löscht endgültig. Vorher kommt eine Rückfrage, die jede Datei nennt und sagt, dass es
  endgültig ist.

## Was die Vorschau je Datei zeigt

Erkannte Art (Buch oder Besonderes mit Unterart, BF-77), Kategorie aus dem Katalog (BF-69), Sammlung und Band, auch in
eine Lücke (BF-75), Sprache, Doppel im Bestand, Begleitmaterial, das dazukommt, und den Ablageort. Jede Zuordnung ist
einzeln oder für alle angehakten Zeilen änderbar.

## Folgen für den Bau

- Die Annahme bekommt vor der Station Regal einen Halt "Zum Bestätigen". Bis zur Bestätigung ist nichts im Regal, in der
  Suche oder in den Zählern; die Datei liegt schon in der Kellerwolke (oder auf dem Gerät).
- Ein Buch kann mehrere Formate haben (weiteres Format zum vorhandenen Buch). Das ist eine Erweiterung des Datenmodells:
  Die Dateien eines Buchs stehen als eigene Zeilen neben dem Buch, das Lesen wählt das Format.
- ZIP: Entpacken auf dem Server, Teil für Teil, mit Grenzen für Anzahl, Größe und Tiefe; Pfade aus der ZIP werden nie als
  Pfade auf dem Gerät benutzt.

## Reihenfolge des Baus

1. Entwurf zur Abnahme, zusammen mit BF-75 (Lücken) und BF-81 (Begleitmaterial).
2. Server: Halt "Zum Bestätigen", Vorschau je Datei, ZIP, Doppel und Formate, Ordnerhinweise, Verwerfen mit Folgen.
3. Oberfläche nach dem Entwurf, danach BF-75 auf dieser Grundlage.
