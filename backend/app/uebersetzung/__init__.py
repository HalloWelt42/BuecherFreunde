"""Bücher übersetzen (BF-71), Englisch nach Deutsch: die Fachschicht ohne Datenbank und ohne Netz.

- xhtml.py: XHTML und XML lesen, jede Stelle mit ihrem Ort in der Quelle
- marken.py: Vorlagen mit Marken (<t1>..</t1> Auszeichnung, <x2/> Unantastbares), lesen und prüfen
- bloecke.py: Textläufe eines Dokuments als Blöcke mit Vorlage
- zerlegen_epub.py: ein EPUB in Kapitel und Blöcke mit fester Kennung
- setzen.py: die deutsche Fassung, in denselben Dateien mit demselben Markup, nur der Text tauscht
- zahlen.py, zeichen.py, sprache.py: Bausteine der festen Prüfungen
- pruefen.py: die neun festen Prüfungen je Block
- begriffe.py: Begriffsliste je Buch (Regeln, KI-Vorschlag) und wie Begriffe im Text gefunden werden
- anweisungen.py: Anweisungen und Antwortformen für die KI
- uebersetzen.py: Portionen, Übersetzen mit Halbieren, Nacharbeit
- pruefer.py: die zweite KI als Prüfer

Die KI kommt von außen als `Anfrage` (modelle.py); Lauf, Tabellen und Ablage stehen in services/."""
