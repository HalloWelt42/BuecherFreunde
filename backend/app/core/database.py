"""SQLite-Datenbank mit FTS5 Volltextsuche.

Transaktionen (BF-49): jede Anfrage und jeder Arbeitsschritt im Hintergrund, der mehr als eine Anweisung zusammen
schreibt, ist eine Einheit (`db.einheit()`) mit eigener Verbindung: gebucht wird beim eigenen `commit()` und am Ende, bei
einem Fehler (Ausnahme oder Antwort ab 400) wird zurückgerollt. Was außerhalb einer Einheit geschrieben wird, gilt sofort
(jede Anweisung für sich); so bleibt nie eine halbe Änderung offen, die ein fremder Aufruf mitbucht. Eine Einheit gehört
der Aufgabe (asyncio), die sie begonnen hat; Aufgaben, die daraus starten, schreiben nicht in sie hinein."""

import asyncio
import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from backend.app.core import suchindex
from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.db")

SCHEMA_VERSION = 17

SCHEMA_SQL = """
-- Bücher
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    isbn TEXT DEFAULT '',
    publisher TEXT DEFAULT '',
    year INTEGER DEFAULT NULL,
    language TEXT DEFAULT '',
    description TEXT DEFAULT '',
    file_format TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    file_name TEXT NOT NULL DEFAULT '',
    storage_path TEXT NOT NULL,
    cover_path TEXT DEFAULT '',
    page_count INTEGER DEFAULT 0,
    typ TEXT DEFAULT '',
    sammlung_id INTEGER DEFAULT NULL,
    band_nummer TEXT DEFAULT '',
    gutenberg_id INTEGER DEFAULT NULL,
    manuell_bearbeitet INTEGER NOT NULL DEFAULT 0,
    fts_content TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (sammlung_id) REFERENCES collections(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_books_hash ON books(hash);
CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
CREATE INDEX IF NOT EXISTS idx_books_format ON books(file_format);
CREATE INDEX IF NOT EXISTS idx_books_gutenberg ON books(gutenberg_id);

-- Kategorien (Baumstruktur)
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    color TEXT DEFAULT '#6b7280',
    icon TEXT DEFAULT '',
    parent_id INTEGER DEFAULT NULL,
    sort_order INTEGER DEFAULT 0,
    spezial INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_categories_slug ON categories(slug);

-- Buch-Kategorien (n:m)
CREATE TABLE IF NOT EXISTS book_categories (
    book_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    quelle TEXT NOT NULL DEFAULT 'manuell',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (book_id, category_id),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

-- Nutzerdaten pro Buch
CREATE TABLE IF NOT EXISTS user_book_data (
    book_id INTEGER PRIMARY KEY,
    is_favorite INTEGER DEFAULT 0,
    is_to_read INTEGER DEFAULT 0,
    rating INTEGER DEFAULT 0,
    reading_position TEXT DEFAULT '',
    last_read_at TEXT DEFAULT NULL,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

-- Sammlungen (Regale)
CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    color TEXT DEFAULT '#3b82f6',
    sort_order INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_books_sammlung ON books(sammlung_id);

-- Notizen
CREATE TABLE IF NOT EXISTS book_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_reference INTEGER DEFAULT NULL,
    cfi_reference TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notes_book ON book_notes(book_id);

-- Labels / Lesezeichen
CREATE TABLE IF NOT EXISTS book_labels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    color TEXT NOT NULL DEFAULT '#4FC3F7',
    name TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    page_reference TEXT DEFAULT '',
    position_percent REAL DEFAULT 0,
    cfi_reference TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_labels_book ON book_labels(book_id);

-- Textmarkierungen (Highlights) mit optionalen Label-Feldern
CREATE TABLE IF NOT EXISTS book_highlights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    cfi_range TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#FFEE58',
    text_snippet TEXT NOT NULL DEFAULT '',
    label_name TEXT NOT NULL DEFAULT '',
    label_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_highlights_book ON book_highlights(book_id);

-- Import-Aufgaben
CREATE TABLE IF NOT EXISTS import_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_path TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'wartend',
    progress_percent INTEGER DEFAULT 0,
    current_step TEXT DEFAULT '',
    error TEXT DEFAULT '',
    book_id INTEGER DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_import_status ON import_tasks(status);

-- Anwendungseinstellungen (Key-Value)
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- KI-Prompts
CREATE TABLE IF NOT EXISTS ai_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schluessel TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    beschreibung TEXT DEFAULT '',
    system_prompt TEXT NOT NULL DEFAULT '',
    temperatur REAL DEFAULT 0.3,
    max_tokens INTEGER DEFAULT 500,
    aktiv INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Autoren
CREATE TABLE IF NOT EXISTS authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    biography TEXT DEFAULT '',
    beschreibung TEXT DEFAULT '',
    birth_year INTEGER DEFAULT NULL,
    death_year INTEGER DEFAULT NULL,
    photo_path TEXT DEFAULT '',
    wikidata_id TEXT DEFAULT '',
    wikipedia_url TEXT DEFAULT '',
    website TEXT DEFAULT '',
    nationality TEXT DEFAULT '',
    quelle TEXT DEFAULT '',
    konfidenz TEXT DEFAULT '',
    score INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_authors_slug ON authors(slug);
CREATE INDEX IF NOT EXISTS idx_authors_name ON authors(name);

-- Autoren-Werke (aus Wikidata P800)
CREATE TABLE IF NOT EXISTS author_works (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_id INTEGER NOT NULL,
    wikidata_id TEXT DEFAULT '',
    titel TEXT NOT NULL,
    book_id INTEGER DEFAULT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE,
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_author_works_author ON author_works(author_id);

-- Buch-Autoren (n:m)
CREATE TABLE IF NOT EXISTS book_authors (
    book_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    role TEXT DEFAULT 'autor',
    sort_order INTEGER DEFAULT 0,
    PRIMARY KEY (book_id, author_id),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_book_authors_author ON book_authors(author_id);
CREATE INDEX IF NOT EXISTS idx_book_categories_category ON book_categories(category_id);

-- Schema-Version
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

"""

# Neubau: wo das Original eines Buchs in der Kellerwolke liegt, und die Aufnahmen (Hochladen) mit ihrem Stand.
# Der Volltextindex liegt in einer eigenen Datei (core/suchindex.py).
NEUBAU_SQL = """
CREATE TABLE IF NOT EXISTS ablage_datei (
    hash TEXT PRIMARY KEY,
    knoten TEXT NOT NULL,
    name TEXT NOT NULL,
    pfad TEXT NOT NULL DEFAULT '',
    groesse INTEGER NOT NULL DEFAULT 0,
    begleiter TEXT DEFAULT NULL,
    abgelegt_am TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS aufnahme (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    groesse INTEGER NOT NULL,
    sha256 TEXT NOT NULL DEFAULT '',
    upload TEXT DEFAULT NULL,
    knoten TEXT DEFAULT NULL,
    empfangen INTEGER NOT NULL DEFAULT 0,
    stand TEXT NOT NULL,
    schritt INTEGER NOT NULL DEFAULT 0,
    anteil REAL NOT NULL DEFAULT 0,
    text TEXT NOT NULL DEFAULT '',
    buch_id INTEGER DEFAULT NULL,
    versuche INTEGER NOT NULL DEFAULT 0,
    anreichern INTEGER NOT NULL DEFAULT 0,
    ausgeblendet INTEGER NOT NULL DEFAULT 0,
    angelegt_am TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    geaendert_am TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE TABLE IF NOT EXISTS nutzer (                -- eigene Konten, nur ohne Kellerwolke (core/eigene_anmeldung.py)
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    kennwort TEXT NOT NULL,
    angelegt_am TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS nutzer_sitzung (
    schluessel TEXT PRIMARY KEY,
    nutzer INTEGER NOT NULL REFERENCES nutzer(id) ON DELETE CASCADE,
    angelegt_am TEXT NOT NULL DEFAULT (datetime('now')),
    zuletzt_am TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS quelle_vorrat (         -- gemerkte Antworten fremder Quellen (quellen/vorrat.py), Zeiten als Unix-Zeit
    adresse TEXT PRIMARY KEY,
    quelle TEXT NOT NULL,
    art TEXT NOT NULL,                             -- treffer, leer, fehler
    inhalt BLOB DEFAULT NULL,                      -- gepackt
    grund TEXT NOT NULL DEFAULT '',
    geholt_am REAL NOT NULL,
    gilt_bis REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_quelle_vorrat_gilt ON quelle_vorrat(gilt_bis);
CREATE TABLE IF NOT EXISTS quelle_stand (          -- je Quelle letzter Erfolg, letzter Fehler, Pause, Anfragen heute (quellen/zustand.py)
    quelle TEXT PRIMARY KEY,
    erfolg_am REAL DEFAULT NULL,
    fehler_am REAL DEFAULT NULL,
    fehler TEXT NOT NULL DEFAULT '',
    ausfaelle INTEGER NOT NULL DEFAULT 0,
    stufe INTEGER NOT NULL DEFAULT 0,
    pause_bis REAL DEFAULT NULL,
    pause_grund TEXT NOT NULL DEFAULT '',
    geprueft_am REAL DEFAULT NULL,
    tag TEXT NOT NULL DEFAULT '',
    anfragen INTEGER NOT NULL DEFAULT 0,
    hintergrund INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS autor_verweis (         -- Kennungen eines Autors in Normdateien (gnd, viaf, isni, orcid)
    author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    art TEXT NOT NULL,
    kennung TEXT NOT NULL,
    PRIMARY KEY (author_id, art)
);
CREATE INDEX IF NOT EXISTS idx_autor_verweis_kennung ON autor_verweis(art, kennung);
CREATE TABLE IF NOT EXISTS codestellen (            -- Erkennung je Buch (codestellen/dienst.py); die Stellen stehen im Begleiter
    buch_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
    fassung INTEGER NOT NULL,
    anzahl INTEGER NOT NULL DEFAULT 0,
    grund TEXT NOT NULL DEFAULT '',
    erkannt_am TEXT NOT NULL,
    vorgeprueft TEXT NOT NULL DEFAULT ''           -- Sprachen der Sandbox, für die die Vorprüfung durch ist (kommagetrennt)
);
CREATE TABLE IF NOT EXISTS code_vorpruefung (       -- je Code (codestellen/vorpruefung.py); gilt, solange der Code gleich bleibt
    sprache TEXT NOT NULL,
    pruefsumme TEXT NOT NULL,
    stand TEXT NOT NULL,                           -- laeuft, auszug
    quelle TEXT NOT NULL DEFAULT '',               -- lauf, ki
    ausgabe TEXT NOT NULL DEFAULT '',
    fehler TEXT NOT NULL DEFAULT '',
    grund TEXT NOT NULL DEFAULT '',
    fehlt TEXT NOT NULL DEFAULT '[]',
    geprueft_am TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (sprache, pruefsumme)
);
CREATE TABLE IF NOT EXISTS vorlesestelle (          -- wo das Vorlesen je Buch stehen blieb (api/user_data.py); gilt auf jedem Gerät
    buch_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
    einheit INTEGER NOT NULL,                        -- Seite, Abschnitt oder Stück der Lesequelle, ab 0
    zeichen INTEGER NOT NULL,                        -- Anfang des Satzes in der Einheit
    bis_einheit INTEGER,                             -- Ende des gewählten Umfangs (ausschließlich); leer: bis zum Ende des Buchs
    bis_zeichen INTEGER,
    umfang TEXT NOT NULL DEFAULT '',                 -- was gewählt war, etwa "Dieses Kapitel"
    ort TEXT NOT NULL DEFAULT '',                    -- wie die Stelle heißt, etwa "Seite 12"
    gemerkt_am TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE TABLE IF NOT EXISTS sammlung_vorschlag (      -- gefundene Reihen (services/sammlungsfinder.py, BF-66)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schluessel TEXT NOT NULL UNIQUE,                 -- die Schlüssel der Regelfunde (Reihe|Autor, normiert), je Zeile einer
    name TEXT NOT NULL,
    autor TEXT NOT NULL DEFAULT '',
    wege TEXT NOT NULL DEFAULT '[]',                 -- JSON: wie die Reihe gefunden wurde, kurze deutsche Sätze
    ki TEXT NOT NULL DEFAULT '',                     -- Satz der KI, oder warum sie nicht geprüft hat
    ki_geprueft INTEGER NOT NULL DEFAULT 0,
    ki_zweifel INTEGER NOT NULL DEFAULT 0,           -- die KI hält es für keine Reihe; der Vorschlag bleibt sichtbar (BF-66)
    stand TEXT NOT NULL DEFAULT 'offen',             -- offen, angelegt, verworfen; angelegt und verworfen kommen nie wieder
    sammlung_id INTEGER DEFAULT NULL REFERENCES collections(id) ON DELETE SET NULL,
    gefunden_am TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    geaendert_am TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE TABLE IF NOT EXISTS sammlung_vorschlag_buch ( -- die Bücher eines Vorschlags mit erkannter Bandnummer
    vorschlag_id INTEGER NOT NULL REFERENCES sammlung_vorschlag(id) ON DELETE CASCADE,
    buch_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    band TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (vorschlag_id, buch_id)
);
CREATE INDEX IF NOT EXISTS idx_aufnahme_stand ON aufnahme(stand);
CREATE INDEX IF NOT EXISTS idx_aufnahme_sha ON aufnahme(sha256);
"""


# Spalten, die nach dem Anlegen einer Tabelle des Neubaus dazukamen: fehlen sie, kommen sie beim Verbinden dazu
NEUBAU_SPALTEN: tuple[tuple[str, str, str], ...] = (
    ("aufnahme", "quelle", "TEXT NOT NULL DEFAULT 'hochladen'"),   # hochladen, eingangsordner, ordner, extern, gemeinfrei
    ("aufnahme", "pfad", "TEXT DEFAULT NULL"),                     # die Datei auf dem Gerät (Ordner); bleibt, wo sie ist
    ("aufnahme", "herkunft", "TEXT DEFAULT NULL"),                 # JSON, etwa Nummer und Adresse eines gemeinfreien Buchs
    # Gestaltete Deckblätter (BF-59), Bedeutung in models/book.py
    ("books", "gattung", "TEXT NOT NULL DEFAULT ''"),              # eine aus GATTUNGEN, leer: keine
    ("books", "umschlag_wahl", "TEXT NOT NULL DEFAULT ''"),        # Wahl des Nutzers: leer automatisch, gestaltet, titelseite
    ("books", "umschlag_schlicht", "INTEGER DEFAULT NULL"),        # Befund der Umschlagprüfung: NULL noch nicht geprüft, 0, 1
    ("books", "umschlag_geprueft", "INTEGER NOT NULL DEFAULT 0"),  # der umschlag_stand, zu dem der Befund gehört
    ("books", "einordnung", "TEXT NOT NULL DEFAULT ''"),           # wer Art und Gattung bestimmt hat: leer offen, ki, hand
    ("sammlung_vorschlag", "ki_zweifel", "INTEGER NOT NULL DEFAULT 0"),  # die KI hält es für keine Reihe (BF-66)
)


@dataclass
class Einheit:
    aufgabe: asyncio.Task | None
    verbindung: aiosqlite.Connection | None
    verwerfen: bool = False              # am Ende zurückrollen, auch ohne Ausnahme (Antwort ab 400)


_EINHEIT: ContextVar[Einheit | None] = ContextVar("bf_einheit", default=None)
VORRAT = 8                               # so viele Verbindungen für Einheiten bleiben offen bereit


class Database:
    """Asynchrone SQLite-Datenbank-Verbindung."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.database_path
        self.suche_dir = db_path.parent if db_path else settings.suche_dir      # Tests: Suchindex neben der Probedatenbank
        self._connection: aiosqlite.Connection | None = None
        self._vorrat: list[aiosqlite.Connection] = []

    async def connect(self) -> None:
        """Verbindung herstellen und Schema initialisieren."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(str(self.db_path))
        self._connection.row_factory = aiosqlite.Row

        # WAL-Modus für bessere Performance
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        await self._connection.execute("PRAGMA busy_timeout=5000")

        await self._init_schema()
        await self._connection.executescript(NEUBAU_SQL)
        await self._spalten_nachziehen()
        await suchindex.anhaengen(self._connection, self.suche_dir)
        await self._connection.commit()
        await self._connection.close()
        # die gemeinsame Verbindung: außerhalb einer Einheit gilt jede Anweisung für sich
        self._connection = await self._oeffnen(isolation_level=None)
        logger.info("Datenbank verbunden: %s", self.db_path)

    async def _oeffnen(self, **art: object) -> aiosqlite.Connection:
        v = await aiosqlite.connect(str(self.db_path), **art)
        v.row_factory = aiosqlite.Row
        await v.execute("PRAGMA foreign_keys=ON")
        await v.execute("PRAGMA busy_timeout=5000")
        await suchindex.verbinden(v, self.suche_dir)
        return v

    async def vorrat_leeren(self) -> None:
        while self._vorrat:
            await self._vorrat.pop().close()

    @asynccontextmanager
    async def einheit(self) -> AsyncIterator[Einheit]:
        """Eine Transaktion mit eigener Verbindung für die laufende Aufgabe; innerhalb einer Einheit derselben Aufgabe
        dieselbe. Bucht am Ende, was noch offen ist; rollt zurück bei einer Ausnahme oder wenn `verwerfen` gesetzt ist."""
        aufgabe = asyncio.current_task()
        laufend = _EINHEIT.get()
        if laufend is not None and laufend.verbindung is not None and laufend.aufgabe is aufgabe:
            yield laufend
            return
        v = self._vorrat.pop() if self._vorrat else await self._oeffnen()
        e = Einheit(aufgabe, v)
        marke = _EINHEIT.set(e)
        gelungen = False
        try:
            yield e
            gelungen = True
        finally:
            _EINHEIT.reset(marke)
            e.verbindung = None
            try:
                if v.in_transaction:
                    await (v.commit() if gelungen and not e.verwerfen else v.rollback())
            except BaseException:
                await v.close()
                raise
            if len(self._vorrat) < VORRAT:
                self._vorrat.append(v)
            else:
                await v.close()

    async def _spalten_nachziehen(self) -> None:
        assert self._connection is not None
        for tabelle, spalte, art in NEUBAU_SPALTEN:
            vorhanden = {z[1] for z in await (await self._connection.execute(f"PRAGMA table_info({tabelle})")).fetchall()}
            if spalte not in vorhanden:
                await self._connection.execute(f"ALTER TABLE {tabelle} ADD COLUMN {spalte} {art}")
        await self._connection.commit()

    async def disconnect(self) -> None:
        """Verbindung trennen."""
        await self.vorrat_leeren()
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Datenbank getrennt")

    async def _init_schema(self) -> None:
        """Schema erstellen falls nicht vorhanden."""
        assert self._connection is not None

        # Prüfen ob Schema bereits existiert
        cursor = await self._connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        )
        exists = await cursor.fetchone()

        if not exists:
            await self._connection.executescript(SCHEMA_SQL)
            await self._connection.execute(
                "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            await self._connection.commit()
            logger.info("Datenbankschema v%d erstellt", SCHEMA_VERSION)
            # Standard-Daten einfügen (Prompts etc.)
            await self._insert_defaults()
        else:
            cursor = await self._connection.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            )
            row = await cursor.fetchone()
            current = row["version"] if row else 0
            if current < SCHEMA_VERSION:
                logger.info(
                    "Schema-Migration von v%d auf v%d", current, SCHEMA_VERSION
                )
                await self._migrate(current)
                await self._connection.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
                await self._connection.commit()
        # Sicherstellen, dass Standard-Daten vorhanden sind
        await self._insert_defaults()

    async def _migrate(self, from_version: int) -> None:
        """Führt Schema-Migrationen durch."""
        assert self._connection is not None

        if from_version < 2:
            # v2: color, icon, description für Kategorien; icon für Tags
            migrations = [
                "ALTER TABLE categories ADD COLUMN description TEXT DEFAULT ''",
                "ALTER TABLE categories ADD COLUMN color TEXT DEFAULT '#6b7280'",
                "ALTER TABLE categories ADD COLUMN icon TEXT DEFAULT ''",
                "ALTER TABLE tags ADD COLUMN icon TEXT DEFAULT ''",
            ]
            for sql in migrations:
                try:
                    await self._connection.execute(sql)
                except Exception as e:
                    # Spalte existiert bereits
                    if "duplicate column" not in str(e).lower():
                        logger.warning("Migration-Warnung: %s", e)
            await self._connection.commit()
            logger.info("Schema-Migration v2 abgeschlossen: color/icon/description Felder")

        if from_version < 3:
            # v3: app_settings + ai_prompts Tabellen
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS ai_prompts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schluessel TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    beschreibung TEXT DEFAULT '',
                    system_prompt TEXT NOT NULL DEFAULT '',
                    temperatur REAL DEFAULT 0.3,
                    max_tokens INTEGER DEFAULT 500,
                    aktiv INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            # Standard-Prompts einfügen
            await self._connection.execute("""
                INSERT OR IGNORE INTO ai_prompts (schluessel, name, beschreibung, system_prompt, temperatur, max_tokens)
                VALUES (
                    'kategorisierung',
                    'Buch-Kategorisierung',
                    'Analysiert Titel, Autor und Textauszug und schlägt passende Kategorien vor.',
                    'Du bist ein Bibliothekar der Bücher kategorisiert.
Analysiere den gegebenen Buchtitel, Autor und Textauszug.
Schlage 3-5 passende Kategorien vor.

Antworte ausschließlich als JSON-Array mit Objekten:
[{"kategorie": "Name", "konfidenz": 0.0-1.0}]

Verwende deutsche Kategorienamen. Beispiele:
Informatik, Belletristik, Geschichte, Philosophie, Naturwissenschaft,
Wirtschaft, Psychologie, Mathematik, Kunst, Musik, Religion, Politik,
Science-Fiction, Fantasy, Krimi, Biografie, Ratgeber, Sachbuch',
                    0.3,
                    500
                )
            """)
            await self._connection.execute("""
                INSERT OR IGNORE INTO ai_prompts (schluessel, name, beschreibung, system_prompt, temperatur, max_tokens)
                VALUES (
                    'zusammenfassung',
                    'Buch-Zusammenfassung',
                    'Erstellt eine kurze Zusammenfassung basierend auf dem Textauszug.',
                    'Du bist ein Bibliothekar. Erstelle eine prägnante Zusammenfassung des Buches in 2-3 Sätzen auf Deutsch. Basiere dich auf den gegebenen Informationen. Antworte nur mit der Zusammenfassung, ohne Einleitung.',
                    0.4,
                    300
                )
            """)
            await self._connection.execute("""
                INSERT OR IGNORE INTO ai_prompts (schluessel, name, beschreibung, system_prompt, temperatur, max_tokens)
                VALUES (
                    'schlagworte',
                    'Schlagwort-Extraktion',
                    'Extrahiert relevante Schlagworte/Tags aus dem Buchinhalt.',
                    'Du bist ein Bibliothekar. Extrahiere 5-10 relevante Schlagworte aus dem gegebenen Buch.

Antworte ausschließlich als JSON-Array mit Strings:
["Schlagwort1", "Schlagwort2", ...]

Verwende deutsche Begriffe. Sei spezifisch, nicht zu allgemein.',
                    0.3,
                    200
                )
            """)
            await self._connection.commit()
            logger.info("Schema-Migration v3 abgeschlossen: ai_prompts Tabelle")

        if from_version < 4:
            # v4: Autoren-Tabelle + Buch-Autoren (n:m) + Migration
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS authors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    biography TEXT DEFAULT '',
                    birth_year INTEGER DEFAULT NULL,
                    death_year INTEGER DEFAULT NULL,
                    photo_path TEXT DEFAULT '',
                    wikidata_id TEXT DEFAULT '',
                    wikipedia_url TEXT DEFAULT '',
                    website TEXT DEFAULT '',
                    nationality TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_authors_slug ON authors(slug)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_authors_name ON authors(name)"
            )
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS book_authors (
                    book_id INTEGER NOT NULL,
                    author_id INTEGER NOT NULL,
                    role TEXT DEFAULT 'autor',
                    sort_order INTEGER DEFAULT 0,
                    PRIMARY KEY (book_id, author_id),
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                    FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE
                )
            """)

            # Bestehende books.author-Strings migrieren
            await self._migrate_authors()
            await self._connection.commit()
            logger.info("Schema-Migration v4 abgeschlossen: Autoren-Tabelle + Migration")

        if from_version < 5:
            # v5: Sammlungen direkt auf books (1:1 statt n:m), Typ-Feld, Tags entfernen
            add_columns = [
                "ALTER TABLE books ADD COLUMN typ TEXT DEFAULT ''",
                "ALTER TABLE books ADD COLUMN sammlung_id INTEGER DEFAULT NULL REFERENCES collections(id) ON DELETE SET NULL",
                "ALTER TABLE books ADD COLUMN band_nummer TEXT DEFAULT ''",
            ]
            for sql in add_columns:
                try:
                    await self._connection.execute(sql)
                except Exception as e:
                    if "duplicate column" not in str(e).lower():
                        logger.warning("Migration-Warnung: %s", e)

            # Index für Sammlungs-FK
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_books_sammlung ON books(sammlung_id)"
            )

            # Bestehende book_collections migrieren (nur erste Zuordnung, da 1:1)
            try:
                cursor = await self._connection.execute(
                    "SELECT book_id, collection_id, sort_order FROM book_collections ORDER BY sort_order"
                )
                rows = await cursor.fetchall()
                migrated = set()
                for row in rows:
                    book_id = row[0]
                    if book_id not in migrated:
                        await self._connection.execute(
                            "UPDATE books SET sammlung_id = ? WHERE id = ?",
                            (row[1], book_id),
                        )
                        migrated.add(book_id)
                logger.info("Sammlungs-Migration: %d Bücher migriert", len(migrated))
            except Exception as e:
                logger.warning("book_collections Migration: %s", e)

            await self._connection.commit()
            logger.info("Schema-Migration v5 abgeschlossen: Typ + Sammlungs-FK auf books")

        if from_version < 6:
            # v6: Spezialkategorien-Flag
            try:
                await self._connection.execute(
                    "ALTER TABLE categories ADD COLUMN spezial INTEGER DEFAULT 0"
                )
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    logger.warning("Migration-Warnung: %s", e)

            # "Ungeordnet" als Spezialkategorie markieren
            await self._connection.execute(
                "UPDATE categories SET spezial = 1 WHERE LOWER(name) = 'ungeordnet'"
            )

            await self._connection.commit()
            logger.info("Schema-Migration v6 abgeschlossen: Spezialkategorien-Flag")

        if from_version < 7:
            # v7: "Ungeordnet" als Spezialkategorie markieren
            await self._connection.execute(
                "UPDATE categories SET spezial = 1 WHERE LOWER(name) = 'ungeordnet'"
            )
            await self._connection.commit()
            logger.info("Schema-Migration v7 abgeschlossen: Ungeordnet als Spezialkategorie")

        if from_version < 8:
            # v8: Erweiterte Autorendaten + Werke-Tabelle
            for col in [
                "ALTER TABLE authors ADD COLUMN beschreibung TEXT DEFAULT ''",
                "ALTER TABLE authors ADD COLUMN quelle TEXT DEFAULT ''",
                "ALTER TABLE authors ADD COLUMN konfidenz TEXT DEFAULT ''",
                "ALTER TABLE authors ADD COLUMN score INTEGER DEFAULT 0",
            ]:
                try:
                    await self._connection.execute(col)
                except Exception as e:
                    if "duplicate column" not in str(e).lower():
                        logger.warning("Migration-Warnung: %s", e)

            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS author_works (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_id INTEGER NOT NULL,
                    wikidata_id TEXT DEFAULT '',
                    titel TEXT NOT NULL,
                    book_id INTEGER DEFAULT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (author_id) REFERENCES authors(id) ON DELETE CASCADE,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE SET NULL
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_author_works_author ON author_works(author_id)"
            )

            await self._connection.commit()
            logger.info("Schema-Migration v8 abgeschlossen: Erweiterte Autorendaten + Werke")

        if from_version < 9:
            # v9: HTML-Beschreibungen in Markdown konvertieren
            await self._migrate_html_descriptions()
            await self._connection.commit()
            logger.info("Schema-Migration v9 abgeschlossen: HTML-Beschreibungen bereinigt")

        if from_version < 10:
            # v10: Quelle und Zeitstempel in book_categories + ai_-Kategorien bereinigen
            for col in [
                "ALTER TABLE book_categories ADD COLUMN quelle TEXT NOT NULL DEFAULT 'manuell'",
                "ALTER TABLE book_categories ADD COLUMN created_at TEXT NOT NULL DEFAULT (datetime('now'))",
            ]:
                try:
                    await self._connection.execute(col)
                except Exception as e:
                    if "duplicate column" not in str(e).lower():
                        logger.warning("Migration-Warnung: %s", e)

            # ai_-Prefix aus Kategorienamen entfernen, Quelle auf 'ki' setzen
            ai_cats = await self._connection.execute(
                "SELECT id, name, slug FROM categories WHERE name LIKE 'ai\\_%' ESCAPE '\\'"
            )
            rows = await ai_cats.fetchall()
            for row in rows:
                clean_name = row[1][3:]  # "ai_Foo" -> "Foo"
                clean_slug = row[2][3:] if row[2].startswith("ai_") else row[2]
                # Pruefen ob eine Kategorie mit dem bereinigten Namen existiert
                existing = await self._connection.execute(
                    "SELECT id FROM categories WHERE slug = ? AND id != ?",
                    (clean_slug, row[0]),
                )
                existing_row = await existing.fetchone()
                if existing_row:
                    # Zuordnungen auf bestehende Kategorie umziehen
                    await self._connection.execute(
                        "UPDATE OR IGNORE book_categories SET category_id = ?, quelle = 'ki' WHERE category_id = ?",
                        (existing_row[0], row[0]),
                    )
                    await self._connection.execute(
                        "DELETE FROM book_categories WHERE category_id = ?", (row[0],)
                    )
                    await self._connection.execute(
                        "DELETE FROM categories WHERE id = ?", (row[0],)
                    )
                else:
                    # Kategorie umbenennen
                    await self._connection.execute(
                        "UPDATE categories SET name = ?, slug = ? WHERE id = ?",
                        (clean_name, clean_slug, row[0]),
                    )
                    # Quelle auf 'ki' setzen
                    await self._connection.execute(
                        "UPDATE book_categories SET quelle = 'ki' WHERE category_id = ?",
                        (row[0],),
                    )

            await self._connection.commit()
            logger.info("Schema-Migration v10 abgeschlossen: Kategorie-Quellen + ai_-Bereinigung")

        if from_version < 11:
            # v11: Labels / Lesezeichen
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS book_labels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    color TEXT NOT NULL DEFAULT '#4FC3F7',
                    name TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    page_reference TEXT DEFAULT '',
                    position_percent REAL DEFAULT 0,
                    cfi_reference TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_labels_book ON book_labels(book_id)"
            )
            await self._connection.commit()
            logger.info("Schema-Migration v11 abgeschlossen: book_labels Tabelle")

        if from_version < 12:
            # v12: Textmarkierungen (Highlights)
            await self._connection.execute("""
                CREATE TABLE IF NOT EXISTS book_highlights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    cfi_range TEXT NOT NULL,
                    color TEXT NOT NULL DEFAULT '#FFEE58',
                    text_snippet TEXT NOT NULL DEFAULT '',
                    label_id INTEGER DEFAULT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
                    FOREIGN KEY (label_id) REFERENCES book_labels(id) ON DELETE SET NULL
                )
            """)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_highlights_book ON book_highlights(book_id)"
            )
            await self._connection.commit()
            logger.info("Schema-Migration v12 abgeschlossen: book_highlights Tabelle")

        if from_version < 13:
            # v13: Label-Felder direkt in Highlights, label_id entfernen
            # Neue Spalten hinzufügen
            try:
                await self._connection.execute(
                    "ALTER TABLE book_highlights ADD COLUMN label_name TEXT NOT NULL DEFAULT ''"
                )
            except Exception:
                pass  # Spalte existiert bereits
            try:
                await self._connection.execute(
                    "ALTER TABLE book_highlights ADD COLUMN label_note TEXT NOT NULL DEFAULT ''"
                )
            except Exception:
                pass  # Spalte existiert bereits
            # Bestehende Labels migrieren: label_id -> label_name/label_note
            await self._connection.execute("""
                UPDATE book_highlights SET
                    label_name = COALESCE((SELECT name FROM book_labels WHERE book_labels.id = book_highlights.label_id), ''),
                    label_note = COALESCE((SELECT note FROM book_labels WHERE book_labels.id = book_highlights.label_id), '')
                WHERE label_id IS NOT NULL
            """)
            await self._connection.commit()
            logger.info("Schema-Migration v13 abgeschlossen: Label-Felder in book_highlights integriert")

        if from_version < 14:
            # v14: Gutenberg-ID für importierte Gutenberg-Bücher
            try:
                await self._connection.execute(
                    "ALTER TABLE books ADD COLUMN gutenberg_id INTEGER DEFAULT NULL"
                )
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    logger.warning("Migration-Warnung: %s", e)
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_books_gutenberg ON books(gutenberg_id)"
            )
            await self._connection.commit()
            logger.info("Schema-Migration v14 abgeschlossen: gutenberg_id Spalte")

        if from_version < 15:
            # v15: manuell_bearbeitet Flag fuer Bücher
            try:
                await self._connection.execute(
                    "ALTER TABLE books ADD COLUMN manuell_bearbeitet INTEGER NOT NULL DEFAULT 0"
                )
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    logger.warning("Migration-Warnung: %s", e)
            await self._connection.commit()
            logger.info("Schema-Migration v15 abgeschlossen: manuell_bearbeitet Spalte")

        if from_version < 16:
            # v16: Indizes fuer haeufige JOINs auf Fremdschluessel
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_book_authors_author ON book_authors(author_id)"
            )
            await self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_book_categories_category ON book_categories(category_id)"
            )
            await self._connection.commit()
            logger.info("Schema-Migration v16 abgeschlossen: Indizes auf book_authors und book_categories")

    async def _migrate_html_descriptions(self) -> None:
        """Konvertiert bestehende HTML-Beschreibungen in Markdown."""
        from backend.app.services.html_utils import html_to_markdown

        assert self._connection is not None
        cursor = await self._connection.execute(
            "SELECT id, description FROM books WHERE description LIKE '%<%' AND description LIKE '%>%'"
        )
        rows = await cursor.fetchall()
        count = 0
        for row in rows:
            clean = html_to_markdown(row["description"])
            if clean != row["description"]:
                await self._connection.execute(
                    "UPDATE books SET description = ? WHERE id = ?",
                    (clean, row["id"]),
                )
                count += 1
        logger.info("HTML-Beschreibungen bereinigt: %d Bücher", count)

    async def _migrate_authors(self) -> None:
        """Migriert bestehende Autoren-Strings aus books.author in die authors-Tabelle."""
        import re

        assert self._connection is not None

        cursor = await self._connection.execute(
            "SELECT id, author FROM books WHERE author IS NOT NULL AND author != ''"
        )
        rows = await cursor.fetchall()

        for row in rows:
            book_id = row[0]
            author_str = row[1]

            # Autoren aufsplitten: Komma, Semikolon, " und ", " & "
            namen = re.split(r'\s*[,;]\s*|\s+und\s+|\s+&\s+', author_str)

            for i, name in enumerate(namen):
                name = name.strip()
                if not name or len(name) < 2:
                    continue

                slug = re.sub(r'[^\w\s-]', '', name.lower().strip())
                slug = re.sub(r'[-\s]+', '-', slug).strip('-')
                if not slug:
                    continue

                # Autor anlegen falls nicht vorhanden
                existing = await self._connection.execute(
                    "SELECT id FROM authors WHERE slug = ?", (slug,)
                )
                existing_row = await existing.fetchone()

                if existing_row:
                    author_id = existing_row[0]
                else:
                    cursor = await self._connection.execute(
                        "INSERT INTO authors (name, slug) VALUES (?, ?)",
                        (name, slug),
                    )
                    author_id = cursor.lastrowid

                # Verknüpfung anlegen
                await self._connection.execute(
                    "INSERT OR IGNORE INTO book_authors (book_id, author_id, sort_order) VALUES (?, ?, ?)",
                    (book_id, author_id, i),
                )

        count = await self._connection.execute("SELECT COUNT(*) FROM authors")
        count_row = await count.fetchone()
        logger.info("Autoren-Migration: %d Autoren aus Büchern extrahiert", count_row[0])

    @property
    def connection(self) -> aiosqlite.Connection:
        """Die Verbindung der laufenden Einheit dieser Aufgabe, sonst die gemeinsame (jede Anweisung für sich)."""
        e = _EINHEIT.get()
        if e is not None and e.verbindung is not None and e.aufgabe is asyncio.current_task():
            return e.verbindung
        if self._connection is None:
            raise RuntimeError("Datenbank ist nicht verbunden")
        return self._connection

    async def _insert_defaults(self) -> None:
        """Standard-Daten einfügen (Prompts etc.) falls Tabellen leer sind."""
        assert self._connection is not None
        cursor = await self._connection.execute(
            "SELECT COUNT(*) as n FROM ai_prompts"
        )
        row = await cursor.fetchone()
        if row and row["n"] > 0:
            return  # Bereits Prompts vorhanden

        logger.info("Füge Standard-KI-Prompts ein")
        await self._connection.execute("""
            INSERT OR IGNORE INTO ai_prompts (schluessel, name, beschreibung, system_prompt, temperatur, max_tokens)
            VALUES (
                'kategorisierung',
                'Buch-Kategorisierung',
                'Analysiert Titel, Autor und Textauszug und schlägt passende Kategorien vor.',
                'Du bist ein Bibliothekar der Bücher kategorisiert.
Analysiere den gegebenen Buchtitel, Autor und Textauszug.
Schlage 3-5 passende Kategorien vor.

Antworte ausschließlich als JSON-Array mit Objekten:
[{"kategorie": "Name", "konfidenz": 0.0-1.0}]

Verwende deutsche Kategorienamen. Beispiele:
Informatik, Belletristik, Geschichte, Philosophie, Naturwissenschaft,
Wirtschaft, Psychologie, Mathematik, Kunst, Musik, Religion, Politik,
Science-Fiction, Fantasy, Krimi, Biografie, Ratgeber, Sachbuch',
                0.3,
                500
            )
        """)
        await self._connection.execute("""
            INSERT OR IGNORE INTO ai_prompts (schluessel, name, beschreibung, system_prompt, temperatur, max_tokens)
            VALUES (
                'zusammenfassung',
                'Buch-Zusammenfassung',
                'Erstellt eine kurze Zusammenfassung basierend auf dem Textauszug.',
                'Du bist ein Bibliothekar. Erstelle eine prägnante Zusammenfassung des Buches in 2-3 Sätzen auf Deutsch. Basiere dich auf den gegebenen Informationen. Antworte nur mit der Zusammenfassung, ohne Einleitung.',
                0.4,
                300
            )
        """)
        await self._connection.execute("""
            INSERT OR IGNORE INTO ai_prompts (schluessel, name, beschreibung, system_prompt, temperatur, max_tokens)
            VALUES (
                'schlagworte',
                'Schlagwort-Extraktion',
                'Extrahiert relevante Schlagworte/Tags aus dem Buchinhalt.',
                'Du bist ein Bibliothekar. Extrahiere 5-10 relevante Schlagworte aus dem gegebenen Buch.

Antworte ausschließlich als JSON-Array mit Strings:
["Schlagwort1", "Schlagwort2", ...]

Verwende deutsche Begriffe. Sei spezifisch, nicht zu allgemein.',
                0.3,
                200
            )
        """)
        await self._connection.commit()
        logger.info("Standard-KI-Prompts eingefügt")

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """SQL ausführen und Cursor zurückgeben."""
        return await self.connection.execute(sql, params)

    async def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        """SQL mehrfach ausführen."""
        await self.connection.executemany(sql, params_list)

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Eine Zeile abfragen und als dict zurückgeben."""
        cursor = await self.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Alle Zeilen abfragen und als Liste von dicts zurückgeben."""
        cursor = await self.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def commit(self) -> None:
        """Transaktion bestätigen."""
        await self.connection.commit()


# Globale Datenbankinstanz
db = Database()
