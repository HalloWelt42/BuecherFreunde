# Rückfallschichten (BF-94)

Nutzerwunsch (27.11.2026): "es muss immer fallbackschichten geben" und "oder aber der verzicht auf einzelne funktionen, so
dass die app nie ausfällt". Dazu: "direkte anbindeungen von ki sind unzulässig" und "das ist nur der default für leute die ki
und lm studio haben aber nciht unsere leitstelle".

## Grundsatz

Jede äußere Abhängigkeit hat eine Rückfallschicht, oder die einzelne Funktion entfällt mit Grund. Die App selbst fällt nie
aus: Start, Anmeldung, Regal und Lesen laufen, auch wenn jeder Dienst fehlt.

Welche Schicht gilt, folgt aus der Einrichtung, nicht aus einem Ausfall. Ist ein Dienst des Hauses eingetragen und gerade
weg, weicht die App nicht auf einen anderen Weg aus, der im Haus unzulässig ist (etwa eine direkte Anbindung der KI); sie
verzichtet dann auf die Funktion und nennt den Grund.

## Bestand (27.11.2026, nur gelesen)

| Abhängigkeit | Schichten heute | ohne Einrichtung | bei Ausfall |
|---|---|---|---|
| Kellerwolke, Anmeldung | Kellerwolke, sonst eigene Konten; bestätigte Anmeldung 24 h gemerkt | eigene Konten | neue Anmeldung 503 mit Grund |
| Kellerwolke, Ablage | Gerät und Zwischenspeicher zuerst, dann Kellerwolke; Volltext, Umschläge, Suche lokal | Ablage auf dem Gerät | Lesen eines Originals 503 mit Grund, Aufnahme "fehler" |
| Kellerwolke, Sicherungen und Profile | lokal immer, Kellerwolke zusätzlich | nur lokal | Pflege fängt den Fehler |
| Leitstelle, KI | Einordnen erst mit Regeln, dann KI; Vorprüfung erst Lauf, dann KI | Läufe ruhen mit Grund | Gründe in Worten, Hintergrund wartet |
| Sprechdienst | Sprechdienst, sonst Stimmen des Geräts; Ansagen als fertige Töne | Stimmen des Geräts | Fehler mit Grund |
| Nachschlag | Nachschlag, sonst Lexikon im Netz, sonst ausgeblendet | Lexikon im Netz oder ausgeblendet | Fehler mit Grund |
| Assistent | eine Schicht | ausgeblendet | Fehler mit Grund |
| Codeschmiede | Erkennung der Codestellen läuft immer | Taste und Editor fehlen | Grund |
| Fundus | Wortsuche bleibt | ausgeblendet | Grund |
| Quellen | jede abschaltbar; Vorrat, Pausen, Sicherung nach Ausfällen; nacheinander bis eine etwas weiß | Hinweis statt Angabe | Pause mit Grund |
| Texterkennung (BF-109) | Textschicht des PDF, für Seiten eines Scans ohne Text die klassische Erkennung auf dem Gerät | Auftrag ruht mit Grund, die Textansicht weist auf das Original hin | eine Seite bleibt mit Grund liegen, die übrigen laufen weiter |

## Lücken

1. Mit eingetragener Kellerwolke gibt es keinen Rückfall auf eigene Konten. Die gemerkte Anmeldung lebt nur im Speicher; ein
   Neustart während eines Ausfalls sperrt jede Anfrage.
2. Ein falscher Pfad in `KELLERWOLKE_CA` lässt den Start abbrechen; die Datei ersetzt die üblichen Stellen für alle Dienste.
3. Die Anmeldeseite meldet bei einem Ausfall "der App-Zugang fehlt" statt "nicht erreichbar".
4. Beim Hinzufügen gibt es mit eingerichteter, aber fehlender Kellerwolke keinen Puffer auf dem Gerät.
5. Scheitert die Ablage einer Sicherung in der Kellerwolke, endet die Sicherung von Hand und das Vorbereiten des Umzugs mit
   Fehler 500, obwohl die lokale Sicherung fertig ist; die nächtliche Pflege holt sie nicht nach.
6. KI ohne Leitstelle: keine Schicht am eigenen Modellläufer für Installationen ohne Leitstelle.
7. Kategorisieren fragt die Leitstelle ohne Lese-Zeitgrenze und kann hängen.
8. "ki", "vorlesen" und "ausfuehren" heißen nur "eingerichtet", nicht "erreichbar"; die Tasten bleiben während eines Ausfalls
   sichtbar, der Grund kommt erst beim Antippen.
9. Ist der Sprechdienst eingerichtet, aber weg, gibt es keine Stimme statt der Stimmen des Geräts; fehlt ein Ton einer
   Kinderansage, bleibt sie still.
10. Ist der Nachschlag eingetragen, aber weg, gibt es keinen Rückfall auf das Lexikon im Netz.
11. Im Antwortstrom des Assistenten werden Fehler nicht gefangen; die Antwort bricht ab statt mit Grund zu enden.
12. Die Ablage-Ansicht eines Buchs wartet bis 45 Sekunden auf den Fundus.
13. Bei den Lücken in Sammlungen gilt ein früher Ausfall einer Quelle als endgültig gescheitert.

Erledigt mit BF-92 (0.43.2): Assistent und Nachschlag werden unter den Verbindungen echt geprüft; die Verbindungen werden
zugleich geprüft, jede mit einer Frist von 8 Sekunden.

## Offen

Reihenfolge und Wahl der Schichten je Lücke klärt das Gespräch, eine Frage nach der anderen; neue Bedienelemente nur nach
Entwurf.
