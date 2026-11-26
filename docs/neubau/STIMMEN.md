# Stimmen über die Vertonung (BF-14)

Nutzerwunsch (26. und 27.11.2026): "weiterhin vermisse ich die auswahl der ki stimmen, eigentlich übermittelt leitstelle alle
einstellmöglichkeiten" und "die stimmen selber fehlen, es sind nur die internen modelle da, das stimmenkloning fehlt komplett
mit privaten stimmen usw".

## Befund (27.11.2026)

- BücherFreunde spricht heute direkt mit dem Sprechdienst `klangwerk-sprechen` der Leitstelle (Qwen3-TTS CustomVoice). Er
  kennt nur die neun eingebauten Stimmen; seine Beschreibung nennt dazu Sprache (11, auch automatisch), Tempo (0,1 bis 4),
  eine Sprechweise als Anweisung und Feinheiten (Temperatur, Top-k, Top-p, Wiederholungsstrafe).
- Der Klon-Dienst `klangwerk-klonen` (Qwen3-TTS Base) ist in der Leitstelle bereit, für BücherFreunde aber nicht freigegeben.
- Im Haus gilt: Vorlesen läuft über die Vertonung. Sie hält die Stimmen und ihre Freigaben (privat, fremd, eingebaut),
  spricht auch Klonstimmen und ruft dafür die Dienste hinter der Leitstelle. Apps nutzen dafür den gemeinsamen Baustein
  `appkern.vorlesen` mit `appkern.verbund` (App-Schlüssel der Kellerwolke, im Auftrag der Person). Welche App private Stimmen
  bekommt, legt der Nutzer in der Vertonung unter "Private Stimmen für" fest.
- BücherFreunde nutzt den Appkern 0.40.2 (Stand vom 22.10.2026), den gemeinsamen Baustein gibt es erst danach.

## Entscheidungen (27.11.2026, im Gespräch)

1. **Über die Vertonung:** Katalog, private (für BücherFreunde freigegebene) und fremde Stimmen samt Klonen kommen aus der
   Vertonung. Eine Wahrheit für alle Stimmen. Vorlesen im Leser und die festen Ansagen der Kinder laufen beide darüber.
2. **Appkern auf den aktuellen Stand:** BücherFreunde zieht seinen Appkern nach und nutzt den gemeinsamen Baustein für
   Vorlesen und Verbund, keine zweite Umsetzung der Schnittstelle.
3. **Einstellungen aus der Beschreibung des Dienstes:** Was die Vertonung zu einer Stimme anbietet (etwa Tempo, Sprechweise,
   Sprache), zeigt BücherFreunde aus dieser Beschreibung, nicht aus einer festen Liste. Deutsche Namen kommen aus einer
   Datei, Unbekanntes steht unter "Mehr".
4. **Je Profil:** Jedes Erwachsenenprofil wählt seine Vorlesestimme im Leser. Für Kinder stellen die Eltern Stimme und
   Einstellungen im Elternbereich ein, für Vorlesen und Ansagen gemeinsam; dazu die Stimme der Familie.

## Folgen

- Die Stimmenwahl zeigt die Bereiche der Vertonung: private Stimmen, fremde Stimmen, eingebaut. Ohne Freigabe der privaten
  Stimmen nennt sie den Grund und den Weg dorthin ("in der Vertonung unter Private Stimmen für").
- Die festen Ansagen entstehen mit der gewählten Stimme über die Vertonung; ändert sich die Stimme, entstehen sie neu.
- Ohne Vertonung (eine Installation ohne die Dienste des Hauses) bleibt die Stimme des Geräts als ausdrückliche Wahl.
- In Bildern und Tests nur Katalogstimmen, nie eigene Stimmen.

## Reihenfolge des Baus

1. Appkern nachziehen, alle Tests grün, an einer isolierten Prüfinstallation geprüft.
2. Vorlesen und Ansagen über die Vertonung, Stimmenwahl mit Bereichen und Probe, Einstellungen aus der Beschreibung.
3. Entwurf zur Abnahme, falls neue Bedienelemente nötig sind (Tempo, Sprechweise), dann Bau.
4. Ausrollen, im Betrieb prüfen: der Nutzer gibt BücherFreunde in der Vertonung private Stimmen frei.
