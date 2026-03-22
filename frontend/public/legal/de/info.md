# BücherFreunde -- Technische Informationen

Dieses Dokument erklärt die wichtigsten Konzepte, Fachbegriffe und technischen Grundlagen von BücherFreunde.

---

## Architektur

BücherFreunde besteht aus zwei Komponenten:

- **Backend** (Python FastAPI) -- REST-API, Datenbankzugriff, Dateiverarbeitung
- **Frontend** (Svelte 5) -- Single-Page-Application im Browser

Die Kommunikation erfolgt über eine REST-API mit Bearer-Token-Authentifizierung. Das Frontend ist austauschbar -- jede Anwendung, die die API anspricht, kann als Frontend dienen.

---

## Hash-basierter Speicher

Jede importierte Datei wird per SHA-256 gehasht. Der Hash bestimmt den Speicherpfad:

```
storage/a1/b2/a1b2c3d4e5f6.../
  original.pdf      -- Originaldatei
  metadata.json     -- Extrahierte + angereicherte Metadaten
  cover.jpg          -- Cover (max 800x1200)
  fulltext.txt       -- Volltext für Suchindex
```

Vorteile:
- **Duplikaterkennung:** Identische Dateien werden automatisch erkannt
- **Keine Namenskonflikte:** Der Pfad ist immer eindeutig
- **rsync-freundlich:** Die Ordnerstruktur kann direkt gesichert werden

---

## Volltextsuche (FTS5)

BücherFreunde nutzt SQLite FTS5 für die Volltextsuche. Der Index enthält Titel, Autor und die ersten ~100.000 Zeichen des Volltexts. Unterstützt werden:

- **Phrasensuche:** "exakter Ausdruck"
- **Präfixsuche:** Anfang*
- **Boolesche Operatoren:** AND, OR, NOT
- **BM25-Ranking:** Relevanz-basierte Sortierung
- **Snippet-Hervorhebung:** Fundstellen werden mit Kontext angezeigt

Der vollständige Text liegt zusätzlich als `fulltext.txt` im Hash-Verzeichnis.

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

## KI-Kategorisierung (LM Studio)

Optional kann ein lokales LLM über LM Studio Bücher automatisch kategorisieren. Die KI analysiert Titel, Autor und einen Textauszug und schlägt Kategorien mit Konfidenzwerten vor.

- OpenAI-kompatible API
- Konfigurierbare URL, Modell, Temperatur und System-Prompt
- Läuft vollständig lokal -- keine Daten an externe KI-Dienste

---

## Datenverteilung

| Speicherort | Inhalt |
|-------------|--------|
| SQLite (DATABASE_DIR) | Metadaten, Kategorien, Sammlungen, Notizen, Highlights, Lesefortschritt, FTS-Index |
| Hash-Ordner (STORAGE_DIR) | Buchdateien (original.pdf/epub), Cover (cover.jpg), Volltext (fulltext.txt), Metadaten-Sidecar (metadata.json) |
| .env | Pfade, Token, externe Dienste, Ports |
| Browser (localStorage) | API-Token, UI-Einstellungen |

---

## Sicherheit

### Mount-Schutz
Beim ersten Start legt das Backend eine Marker-Datei `.buecherfreunde` im Storage- und Datenbank-Verzeichnis an. Bei jedem weiteren Start wird geprüft, ob die Verzeichnisse korrekt gemountet sind. Fehlt die Marker-Datei, startet das Backend nicht -- das verhindert, dass bei nicht gemounteter Festplatte eine leere Datenbank auf der SD-Karte angelegt wird.

### Token-Authentifizierung
Jeder API-Aufruf vom Frontend trägt einen Bearer-Token. Das Token wird beim ersten Start generiert und in der .env-Datei gespeichert.

---

## Externe Quellen

- [AGPL-3.0 Lizenz](https://www.gnu.org/licenses/agpl-3.0.html)
- [Project Gutenberg](https://www.gutenberg.org/) -- Gemeinfreie Bücher
- [Gutendex API](https://gutendex.com/) -- JSON-API für Gutenberg
- [Open Library](https://openlibrary.org/) -- Offene Bibliotheksdatenbank
- [SQLite FTS5](https://www.sqlite.org/fts5.html) -- Volltextsuche
- [PyMuPDF](https://pymupdf.readthedocs.io/) -- PDF-Verarbeitung
- [foliate-js](https://github.com/nicolo-ribaudo/foliate-js) -- EPUB-Reader

---

*Basiert auf der technischen Dokumentation von [RadioHub](https://github.com/HalloWelt42/RadioHub) von HalloWelt42.*
