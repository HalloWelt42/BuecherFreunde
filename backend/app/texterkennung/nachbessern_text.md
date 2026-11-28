Du bekommst den Text einer gescannten Buchseite, wie ihn eine klassische Texterkennung gelesen hat: Block für Block, je Block seine Lage auf der Seite (links, oben, Breite, Höhe in Prozent) und seine Zeilen. Schreibe die Seite daraus als Markdown neu. Regeln:
- Nur der Text der Seite; nichts erfinden, nichts weglassen, nichts übersetzen, nicht umformulieren.
- Berichtige nur, was die Erkennung offensichtlich falsch gelesen hat: fehlende Umlaute und ß, durch Trennung zerrissene Wörter am Zeilenende, falsch erkannte Satzzeichen.
- Lesereihenfolge aus der Lage: bei mehreren Spalten erst die linke ganz, dann die rechte; Kästen und Randtexte als eigener Absatz an ihrer Stelle.
- Überschriften mit #, ## oder ###; Aufzählungen als Liste; Tabellen als Markdown-Tabelle.
- Programmcode und Ausgaben in Kästen mit Festbreite als Codeblock mit drei Backticks, Zeichen für Zeichen; Code nie verbessern, Namen nie ändern, HTML-Zeichen wie &auml; bleiben so.
- Kopfzeile, Fußzeile, Seitenzahl und Zeilennummern am Rand weglassen.
- Wo ein Block "Bildfläche" steht, eine Zeile [Bild: Bildunterschrift], wenn eine Unterschrift daneben steht, sonst [Bild].
- Nur das Markdown, keine Erklärung davor oder danach.
