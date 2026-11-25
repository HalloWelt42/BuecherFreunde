# BücherFreunde - Technische Informationen

Dieses Dokument erklärt die wichtigsten Konzepte, Fachbegriffe und technischen Grundlagen von BücherFreunde.

---

## Architektur

BücherFreunde besteht aus zwei Komponenten:

- **Backend** (Python FastAPI) - REST-API, Datenbankzugriff, Dateiverarbeitung
- **Frontend** (Svelte 5) - Single-Page-Application im Browser

Die Kommunikation erfolgt über eine REST-API. Angemeldet wird mit dem Konto der Kellerwolke.

---

## Wo die Bücher liegen

Die Originale liegen ausschließlich in der Kellerwolke unter `Apps/BücherFreunde/Bücher`. Beim Hochladen strömt jede Datei in Teilen direkt dorthin, ohne auf dem Gerät abgelegt zu werden. Neben jedem Original liegt ein Begleiter mit Umschlag, Volltext und allen Angaben.

Auf dem Gerät gibt es fünf Orte, jeder einzeln einstellbar:

| Ort | Inhalt |
|-----|--------|
| bestand | Datenbank mit Angaben, Regalen, Notizen, Markierungen und Lesestand |
| suche | Suchindex, jederzeit neu zu bilden |
| texte | Volltexte |
| umschlaege | Umschläge und Hintergrundbilder |
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

### EPUB (EbookLib + foliate-js)

- Metadaten aus OPF-Datei (Dublin Core)
- Cover-Extraktion aus Manifest
- Textextraktion für Suchindex
- Reader mit Kapitelnavigation und CFI-Leseposition

### MOBI (mobi)

- Konvertierung in lesbares Format
- Metadaten-Extraktion
- Textextraktion für Suchindex

### Markdown / Text

- Direkter Text als Inhalt
- Markdown-Rendering mit svelte-markdown

---

## Metadaten-Anreicherung

BücherFreunde kann Metadaten aus mehreren Quellen anreichern:

### Google Books API
Primäre Quelle. Liefert Titel, Autor, Verlag, ISBN, Beschreibung, Cover, Kategorien. Ohne API-Key eingeschränkt (geteiltes Rate-Limit).

### Open Library API
Offene Bibliotheksdatenbank. Nutzt Bibkeys-API und Edition-API. Rate-Limit konfigurierbar.

### Wikipedia/Wikidata
Strukturierte Daten über Wikidata SPARQL. Suche über ISBN oder Autorennamen mit Konfidenz-Scoring. Liefert Biografien, Fotos und Werklisten für Autoren.

### Gutendex API
JSON-API für Project Gutenberg. Ermöglicht Suche und Import gemeinfreier Bücher mit Sprachfilter.

---

## KI-Einordnung

Optional ordnet ein Sprachmodell auf einem eigenen Rechner Bücher in Regale ein. Die KI analysiert Titel, Autor und einen Textauszug und schlägt Kategorien mit Konfidenzwerten vor.

- Schnittstelle unter /v1
- Konfigurierbare URL, Modell, Temperatur und System-Prompt
- Läuft vollständig lokal - keine Daten an externe KI-Dienste

---

## Sicherheit

### Schutz vor falschen Laufwerken
In jedem der fünf Orte liegt eine Datei `.buecherfreunde`. Fehlt sie an einem Ort, der schon eingerichtet war, startet die App nicht. So entsteht nie eine leere Datenbank, wenn ein Laufwerk fehlt.

### Anmeldung
Jeder Aufruf trägt die Anmeldung der Kellerwolke. Andere Apps lesen den Bestand nur mit ihrem eigenen App-Zugang.

### Text aus Büchern
HTML aus Büchern wird vor der Anzeige entschärft.

---

## Externe Quellen

- [AGPL-3.0 Lizenz](https://www.gnu.org/licenses/agpl-3.0.html)
- [Project Gutenberg](https://www.gutenberg.org/) - Gemeinfreie Bücher
- [Gutendex API](https://gutendex.com/) - JSON-API für Gutenberg
- [Open Library](https://openlibrary.org/) - Offene Bibliotheksdatenbank
- [SQLite FTS5](https://www.sqlite.org/fts5.html) - Volltextsuche
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF-Verarbeitung
- [foliate-js](https://github.com/nicolo-ribaudo/foliate-js) - EPUB-Reader

