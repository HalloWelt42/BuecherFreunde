# BücherFreunde - Technische Informationen

Dieses Dokument erklärt die wichtigsten Konzepte, Fachbegriffe und technischen Grundlagen von BücherFreunde.

---

## Architektur

BücherFreunde besteht aus zwei Komponenten:

- **Backend** (Python FastAPI) - REST-API, Datenbankzugriff, Dateiverarbeitung
- **Frontend** (Svelte 5) - Single-Page-Application im Browser

Die Kommunikation erfolgt über eine REST-API. Angemeldet wird mit dem Konto der Kellerwolke oder, ohne sie, mit einem eigenen Konto der App; danach wählt jede Person ihr Profil.

---

## Wo die Bücher liegen

Im Betrieb liegen die Originale in der Kellerwolke unter `Apps/BücherFreunde/Bücher`. Beim Hochladen strömt jede Datei in Teilen direkt dorthin, ohne auf dem Gerät abgelegt zu werden. Neben jedem Original liegt ein Begleiter mit Umschlag, Volltext und allen Angaben, dazu, solange eingeschaltet, einer mit dem Persönlichen je Profil. Ohne Kellerwolke liegen die Originale auf dem Gerät.

Auf dem Gerät gibt es fünf Orte, jeder einzeln einstellbar:

| Ort | Inhalt |
|-----|--------|
| bestand | Datenbank mit Angaben, Regalen, Profilen, Notizen, Markierungen und Lesestand; Sicherungen und Hintergrundbilder |
| suche | Suchindex, jederzeit neu zu bilden |
| texte | Volltexte |
| umschlaege | Umschläge |
| zwischen | begrenzter Zwischenspeicher im Arbeitsspeicher |

- **Doppel:** Jede Datei wird vor dem Hochladen an ihrer SHA-256-Prüfsumme erkannt
- **Fortsetzen:** Ein abgebrochenes Hochladen geht an derselben Stelle weiter
- **Eingangsordner:** Was in `Apps/BücherFreunde/Eingangsordner` liegt, kommt von selbst in die Bibliothek

---

## Volltextsuche (FTS5)

BücherFreunde nutzt SQLite FTS5 für die Volltextsuche. Der Index enthält Titel, Autor und die ersten ~100.000 Zeichen des Volltexts. Unterstützt werden:

- **Phrasensuche:** "exakter Ausdruck"
- **Präfixsuche:** Anfang*
- **Boolesche Operatoren:** AND, OR, NOT
- **BM25-Ranking:** Relevanz-basierte Sortierung
- **Snippet-Hervorhebung:** Fundstellen werden mit Kontext angezeigt

Der vollständige Text jedes Buchs liegt zusätzlich bei den Volltexten.

### Suche nach Bedeutung

Fragen und Umschreibungen findet die Suche nach Bedeutung. Sie läuft über das Wissen im Haus, gerechnet wird auf einem eigenen Rechner. Schläft er, gelten die Wörter.

---

## Buchverarbeitung

### PDF (PyMuPDF)

- Textextraktion aus allen Seiten
- Cover-Generierung aus der ersten Seite
- Metadaten aus PDF-Properties (Titel, Autor, Erstellungsdatum)
- TextLayer im Reader für Textauswahl und Markierungen

### EPUB (EbookLib zum Einlesen, foliate-js im Leser)

- Metadaten aus OPF-Datei (Dublin Core)
- Cover-Extraktion aus Manifest
- Textextraktion für Suchindex
- Reader mit Kapitelnavigation und CFI-Leseposition

### MOBI (mobi zum Einlesen, foliate-js im Leser)

- Metadaten-Extraktion
- Textextraktion für Suchindex
- Reader wie bei EPUB

### Markdown / Text

- Direkter Text als Inhalt
- Markdown-Rendering mit svelte-markdown

---

## Angaben aus Quellen

Bis zu acht Quellen ergänzen Angaben zu Büchern und Autoren: Verzeichnisse von Bibliotheken und Verlagen, ein Lexikon, eine Normdatei für Autoren und eine Sammlung gemeinfreier Bücher; eine davon antwortet nur mit eigenem Schlüssel. Jede Quelle hat eigene Grenzen für Abstand und Menge, die App merkt sich ihre Antworten eine Zeit lang, und jede lässt sich abschalten. Welche es sind und was jede bekommt, steht im Datenschutz.

---

## KI

Die KI-Aufgaben der App laufen über die Leitstelle im Haus: Einordnen, Katalog, Sammlungen, Vorschau beim Hinzufügen, Vorprüfung von Code, Übersetzen. Das Modell wählt die App (`KI_MODELL`), die Leitstelle Rechner und Zeitpunkt; ohne Leitstelle wird von Hand eingeordnet. Das Gespräch über eine Stelle führt der Assistent, die Suche nach Bedeutung der Fundus. Vorgelesen wird über den Sprechdienst der Leitstelle oder mit den Stimmen des Geräts. Kinderprofile nutzen keine KI.

---

## Sicherheit

### Schutz vor falschen Laufwerken
In jedem der fünf Orte liegt eine Datei `.buecherfreunde`. Fehlt sie an einem Ort, der schon eingerichtet war, startet die App nicht. So entsteht nie eine leere Datenbank, wenn ein Laufwerk fehlt.

### Anmeldung
Jeder Aufruf trägt die Anmeldung des Kontos und das gewählte Profil. Andere Apps lesen den Bestand nur mit ihrem eigenen App-Zugang.

### Text aus Büchern
HTML aus Büchern wird vor der Anzeige entschärft.

---

## Externe Quellen

- [Project Gutenberg](https://www.gutenberg.org/) - Gemeinfreie Bücher
- [Gutendex API](https://gutendex.com/) - JSON-API für Gutenberg
- [Open Library](https://openlibrary.org/) - Offene Bibliotheksdatenbank
- [SQLite FTS5](https://www.sqlite.org/fts5.html) - Volltextsuche
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF-Verarbeitung
- [foliate-js](https://github.com/johnfactotum/foliate-js) - EPUB-Reader

