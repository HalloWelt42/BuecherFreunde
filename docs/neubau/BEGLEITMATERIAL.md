# Begleitmaterial (BF-81)

Nutzerwunsch: Begleitmaterial allgemein organisieren, je Buch über die Kellerwolke, und genauso in einer Installation
ohne Kellerwolke. Begleitmaterial ist alles, was zu einem Buch gehört, ohne das Buch selbst zu sein: Beispielcode,
Übungsdateien, Lösungen, Audio, Beilagen, Korrekturen.

## Entscheidungen (26.11.2026, im Gespräch geklärt)

1. **In der Kellerwolke: Begleitdateien am Original.** Jede Datei wird Begleiter des Originals, liegt daneben (Name aus
   dem Stamm des Originals und einem Zusatz, etwa `Titel - Autor [12].material.Beispielcode.zip`) und zieht beim
   Verschieben, Umbenennen und im Papierkorb mit. So hält die Kellerwolke die Gruppe zusammen ("zusammengehörige dateien
   immer beieinander ablegen"). Es ist kein Umzug der vorhandenen Originale nötig.
2. **Ohne Kellerwolke: im Buchordner auf dem Gerät.** Jedes Buch hat dort schon einen eigenen Ordner, in dem auch die
   Fassungen liegen. Das Material kommt unter `Material/` dazu, mit denselben Regeln. Kommt später eine Kellerwolke dazu,
   zieht es mit dem Original um.
3. **In der App:** Auf der Buchseite eine Liste "Begleitmaterial" mit Art, Name und Größe. PDF, EPUB, Bilder, Text und
   Markdown öffnen in der App, alles andere lädt herunter. Lesbares Material wird mit durchsucht, ein Treffer nennt das
   Buch. Hinzufügen, Umbenennen und Entfernen; Entfernen nur nach einer Folgenvorschau.
4. **Erkennen:** Liegt in der Kellerwolke eine Datei mit dem Namen des Buchs direkt neben dem Original (etwa vom Nutzer
   selbst abgelegt), bietet der Abgleich sie an: "Als Begleitmaterial zu diesem Buch nehmen?". Erst nach einem Ja wird sie
   Begleiter. Nichts wird still übernommen.

## Aufbau

- Eine Wahrheit: eine Tabelle für das Material je Buch (Kennung als UUID, Buch, Name, Art, Größe, Prüfsumme, Ort,
  Knoten oder Pfad, Herkunft, angelegt). Die Liste der Buchseite, die Suche und die Folgenvorschau lesen nur sie.
- Die Ablage steht hinter einer Schnittstelle mit zwei Umsetzungen: Kellerwolke (Begleiter mit eigener Rolle je Datei,
  da die Kellerwolke je Hauptdatei und Rolle höchstens einen Begleiter kennt) und Gerät (Buchordner). Der Rest der App
  kennt nur die Schnittstelle.
- Wege dazu: Buchseite (eine oder mehrere Dateien, auch eine ZIP), Hochladen mit Vorschau (BF-80: was in einer ZIP zu
  einem Buch gehört), Erkennen in der Kellerwolke (Punkt 4).
- Das Material folgt dem Buch: private Bücher und Freigaben für Kinder (BF-78) gelten auch für ihr Material. Das Löschen
  eines Buchs nennt sein Material in der Folgenvorschau.
- Der Auszug (Umschlag, Volltext, Angaben) bleibt ein eigener Begleiter der App und ist kein Begleitmaterial.

## Später

- Lesbares Begleitmaterial übersetzen wie ein Buch (BF-71).
- Beispielcode aus dem Material in der Ausführen-Umgebung öffnen.

## Reihenfolge des Baus

1. Entwurf zur Abnahme, zusammen mit BF-80 (Hochladen mit Vorschau) und BF-75 (Lücken).
2. Server: Tabelle, Ablage hinter der Schnittstelle, Wege auf der Buchseite, Suche, Erkennen in der Kellerwolke.
3. Oberfläche nach dem Entwurf.
