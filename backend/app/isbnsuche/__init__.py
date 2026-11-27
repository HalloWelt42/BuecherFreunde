"""ISBN im Buch finden und einstufen (BF-111): die eine Stelle für alle, die eine ISBN aus dem Text eines Buchs brauchen, die
Annahme (Leser der Formate), der Lauf "ISBN" in Bibliothek ergänzen und die ISBN-Suche beim Bearbeiten.

- erkennung: jede ISBN im Text mit Wortgrenzen und Prüfziffer, mit Seite, Lage, Ausschnitt und dem Merkmal Druck oder E-Book
- fundort: wo im Buch sie steht (Impressum, Rückseite, Titelei, Text, Anmerkungen, Verlagsanzeige, Literaturliste)
- kandidaten: je ISBN ein Kandidat (10er und 13er Form, mit und ohne Striche zusammen), seine Stufe aus dem Text, die Rangfolge
- dienst: Suche in einem gespeicherten Buch und Prüfen bei den Quellen
- lauf: der Lauf "ISBN" je Buch: eintragen, was passt, sonst zur Wahl
- wahl: die ISBN zur Wahl, gemerkt in der Datenbank

Die Stufe selbst (passt, ähnlich, unbekannt, fremd) bestimmt quellen/abgleich.py, für Funde der Quellen wie für den Text."""
