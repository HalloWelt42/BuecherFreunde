# Autorenkatalog (BF-99)

Nutzerwunsch (27.11.2026): "kümmere dich um das integrieren der autorenkataloge. dazu war schon eine lösung da. im alten
katalog gibts autoren und daten wie auch wege ggf optimierst du das noch", "min ein menüpunkt muss rein. ähnlich geschriebene
autoren würden assoziiert werden damit 10 schreibweisen nicht zu 10 autoren führen", "lokales wiki und externes kann dabei
helfen, je nachdem was erreichbar ist, lokales steckt in nachschlag der zimdaten", "deutsche und englische wikipedia".

## Befund (27.11.2026, nur gelesen)

- Die Autorendaten der Altfassung stecken schon vollständig im Neubau, gleich bis auf die Prüfsummen (Autoren, Biografien,
  Werke, Verknüpfungen, Fotos). Zu übernehmen gibt es nichts.
- Die Wege der Altfassung (Liste, Kennzahlen, Neubilden aus den Büchern, Abgleich mit dem Lexikon über alle, Autorenseite mit
  Vergleich und Übernehmen, Fotos, Werke mit "im Bestand", Bewertung) gibt es im Neubau; dazu Normdaten (GND über die ISBN),
  Verweise auf VIAF, ISNI und ORCID und die Herkunft je Feld.
- Verknüpft ist fast nichts: 9 von rund 3600 Büchern mit Autorenfeld hängen an einem Autor. Den Bestand hat nie jemand neu
  gebildet; neue Bücher verknüpft die Annahme.
- Schreibweisen: aus 2371 genauen Schreibweisen würden heute 2364 Autoren. Mit Umlauten, Reihenfolge der Namensteile,
  Initialen und Tippfehlern bleiben geschätzt 2323 Personen: 41 Gruppen mit 89 Schreibweisen, 353 Buchnennungen. 7 Paare sind
  heikel (gleicher Nachname, anderer Vorname). 18 Felder der Form "zwei Nachnamen, Vorname" zerlegt die App falsch in zwei
  Autoren; dazu 286 Namen aus einem Wort und 6 Platzhalter wie "unbekannt".
- Lokale Wikipedia: der Nachschlag hält die deutsche und die englische Wikipedia (Titelindex, Volltext, Bilder). Heute ist
  dort nur die deutsche fest eingetragen, und die App nimmt entweder den Nachschlag oder das Netz, nie beide. Lokal fehlen
  Wikidata-Kennung, strukturierte Lebensdaten und Werklisten; die liefern Wikidata und die Normdaten im Netz.

## Vorschläge zu den offenen Entscheidungen (zur Abnahme)

1. **Neubilden ergänzt nur:** fehlende Autoren anlegen und verknüpfen, nichts löschen. Löschen nur mit Folgenvorschau und
   ausdrücklicher Bestätigung.
2. **Zusammenführen ordnet zu, schreibt nicht um:** die Schreibweise am Buch bleibt, wie sie in der Datei steht; der Autor
   bekommt sie als weitere Namensform. Rückgängig machen geht jederzeit.
3. **Welcher Name bleibt:** Vorschlag ist der Name aus Normdaten oder Wikidata, sonst der häufigste; je Gruppe änderbar.
4. **Menüpunkt:** in der Seitenleiste unter Autoren ein Punkt "Schreibweisen" mit der Zahl offener Vorschläge.
5. **Nie still:** jede Gruppe ist ein Vorschlag mit Folgen (welche Bücher, welcher Name). Zusammenführen oder Getrennt lassen;
   Getrennt lassen wird gemerkt und kommt nicht wieder. Auch das bisher stille Zusammenlegen beim Übernehmen wird ein Vorschlag.
   Starke Belege (gleiche GND- oder Wikidata-Kennung) stehen oben, heikle Paare sind gekennzeichnet.
6. **Schichten für Angaben:** erst die lokale Wikipedia im Nachschlag (deutsch, dann englisch), dann Wikidata und Wikipedia im
   Netz, dazu die Normdaten; je nachdem, was erreichbar ist. Welche Wikipedia-Bücher des Nachschlags gelten, steht in den
   Einstellungen, nicht im Code.
7. **Automatisch übernehmen** bleibt nur für Angaben mit Sicherheit "hoch" an einem schon verknüpften Autor; Zusammenführen
   ist nie automatisch.
8. **Namen aus einem Wort und Platzhalter** werden nie automatisch zugeordnet; "unbekannt" und "anonym" sind kein Autor.
9. **Später:** Herausgeber und Übersetzer als eigene Rolle; Fotos zuerst aus der lokalen Wikipedia, sonst Commons.

## Reihenfolge des Baus

1. Zerlegung "zwei Nachnamen, Vorname" richten; Neubilden ergänzt nur.
2. Namensformen je Autor als eigene Tabelle; Annahme und Neubilden ordnen über sie zu.
3. Vorschläge für Schreibweisen mit Stufen und Belegen; Zusammenführen und Getrennt lassen mit Folgenvorschau.
4. Personenlexikon als Schnittstelle mit zwei Umsetzungen (Nachschlag de und en, Netz), Wahl nach Erreichbarkeit.
5. Menüpunkt und Ansicht "Schreibweisen" nach Entwurf.
6. Abgleich über alle als sichtbarer Auftrag, im Betrieb prüfen.
