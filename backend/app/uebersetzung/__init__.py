"""Bücher übersetzen (BF-71), Englisch nach Deutsch: die Fachschicht ohne Datenbank und ohne Netz.

- xhtml.py: XHTML und XML lesen, jede Stelle mit ihrem Ort in der Quelle
- marken.py: Vorlagen mit Marken (<t1>..</t1> Auszeichnung, <x2/> Unantastbares), lesen und prüfen; Text als Zeichen für das Modell
- codeabsaetze.py: Code in einfachen Absätzen erkennen (Zäune, Codezeilen, Festbreitenschrift)
- bloecke.py: Textläufe eines Dokuments als Blöcke mit Vorlage
- zerlegen_epub.py: ein EPUB in Kapitel und Blöcke mit fester Kennung
- zerlegen_pdf.py: ein PDF über ein englisches EPUB mit demselben Aufbau in dieselben Blöcke, mit Seite und Lage im Original
  (pdf_lesen.py: Seiten, Zeilen, Code, Tabellen, Abbildungen, Lesefolge; pdf_aufbau.py: Überschriften, Absätze, Listen,
  Fußnoten, Kapitel; pdf_epub.py: das EPUB mit Seitenmarken)
- werk.py: EPUB und PDF hinter einer Schnittstelle (zerlegen, Blöcke, setzen)
- setzen.py: die deutsche Fassung, in denselben Dateien mit demselben Markup, nur der Text tauscht
- zahlen.py, zeichen.py, sprache.py, anrede.py: Bausteine der festen Prüfungen
- pruefen.py: die zehn festen Prüfungen je Block
- begriffe.py: Begriffsliste je Buch (Regeln, KI-Vorschlag) und wie Begriffe im Text gefunden werden
- anweisungen.py: Anweisungen und Antwortformen für die KI
- uebersetzen.py: Portionen, Übersetzen mit Halbieren, Nacharbeit
- pruefer.py: die zweite KI als Prüfer

Die KI kommt von außen als `Anfrage` (modelle.py); Lauf, Tabellen und Ablage stehen in services/."""
