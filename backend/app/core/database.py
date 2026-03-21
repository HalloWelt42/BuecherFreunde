"""SQLite-Datenbank mit FTS5 Volltextsuche."""

import logging
import sqlite3
from pathlib import Path

import aiosqlite

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.db")

SCHEMA_VERSION = 3

SCHEMA_SQL = """
-- Buecher
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
    fts_content TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_books_hash ON books(hash);
CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
CREATE INDEX IF NOT EXISTS idx_books_format ON books(file_format);

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
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_categories_parent ON categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_categories_slug ON categories(slug);

-- Buch-Kategorien (n:m)
CREATE TABLE IF NOT EXISTS book_categories (
    book_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY (book_id, category_id),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

-- Tags
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    color TEXT DEFAULT '#6b7280',
    icon TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tags_slug ON tags(slug);

-- Buch-Tags (n:m)
CREATE TABLE IF NOT EXISTS book_tags (
    book_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (book_id, tag_id),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
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

-- Buch-Sammlungen (n:m)
CREATE TABLE IF NOT EXISTS book_collections (
    book_id INTEGER NOT NULL,
    collection_id INTEGER NOT NULL,
    sort_order INTEGER DEFAULT 0,
    PRIMARY KEY (book_id, collection_id),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE
);

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

-- Schema-Version
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- FTS5 Volltextsuche (External Content)
CREATE VIRTUAL TABLE IF NOT EXISTS books_fts USING fts5(
    title,
    author,
    fts_content,
    content='books',
    content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

-- Trigger fuer automatische FTS-Synchronisation
CREATE TRIGGER IF NOT EXISTS books_ai AFTER INSERT ON books BEGIN
    INSERT INTO books_fts(rowid, title, author, fts_content)
    VALUES (new.id, new.title, new.author, new.fts_content);
END;

CREATE TRIGGER IF NOT EXISTS books_ad AFTER DELETE ON books BEGIN
    INSERT INTO books_fts(books_fts, rowid, title, author, fts_content)
    VALUES ('delete', old.id, old.title, old.author, old.fts_content);
END;

CREATE TRIGGER IF NOT EXISTS books_au AFTER UPDATE ON books BEGIN
    INSERT INTO books_fts(books_fts, rowid, title, author, fts_content)
    VALUES ('delete', old.id, old.title, old.author, old.fts_content);
    INSERT INTO books_fts(rowid, title, author, fts_content)
    VALUES (new.id, new.title, new.author, new.fts_content);
END;
"""


class Database:
    """Asynchrone SQLite-Datenbank-Verbindung."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.database_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Verbindung herstellen und Schema initialisieren."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(str(self.db_path))
        self._connection.row_factory = aiosqlite.Row

        # WAL-Modus fuer bessere Performance
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")
        await self._connection.execute("PRAGMA busy_timeout=5000")

        await self._init_schema()
        logger.info("Datenbank verbunden: %s", self.db_path)

    async def disconnect(self) -> None:
        """Verbindung trennen."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("Datenbank getrennt")

    async def _init_schema(self) -> None:
        """Schema erstellen falls nicht vorhanden."""
        assert self._connection is not None

        # Pruefen ob Schema bereits existiert
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

    async def _migrate(self, from_version: int) -> None:
        """Fuehrt Schema-Migrationen durch."""
        assert self._connection is not None

        if from_version < 2:
            # v2: color, icon, description fuer Kategorien; icon fuer Tags
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
            # Standard-Prompts einfuegen
            await self._connection.execute("""
                INSERT OR IGNORE INTO ai_prompts (schluessel, name, beschreibung, system_prompt, temperatur, max_tokens)
                VALUES (
                    'kategorisierung',
                    'Buch-Kategorisierung',
                    'Analysiert Titel, Autor und Textauszug und schlaegt passende Kategorien vor.',
                    'Du bist ein Bibliothekar der Buecher kategorisiert.
Analysiere den gegebenen Buchtitel, Autor und Textauszug.
Schlage 3-5 passende Kategorien vor.

Antworte ausschliesslich als JSON-Array mit Objekten:
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
                    'Du bist ein Bibliothekar. Erstelle eine praegnante Zusammenfassung des Buches in 2-3 Saetzen auf Deutsch. Basiere dich auf den gegebenen Informationen. Antworte nur mit der Zusammenfassung, ohne Einleitung.',
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

Antworte ausschliesslich als JSON-Array mit Strings:
["Schlagwort1", "Schlagwort2", ...]

Verwende deutsche Begriffe. Sei spezifisch, nicht zu allgemein.',
                    0.3,
                    200
                )
            """)
            await self._connection.commit()
            logger.info("Schema-Migration v3 abgeschlossen: ai_prompts Tabelle")

    @property
    def connection(self) -> aiosqlite.Connection:
        """Gibt die aktive Datenbankverbindung zurueck."""
        if self._connection is None:
            raise RuntimeError("Datenbank ist nicht verbunden")
        return self._connection

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """SQL ausfuehren und Cursor zurueckgeben."""
        return await self.connection.execute(sql, params)

    async def execute_many(self, sql: str, params_list: list[tuple]) -> None:
        """SQL mehrfach ausfuehren."""
        await self.connection.executemany(sql, params_list)

    async def fetch_one(self, sql: str, params: tuple = ()) -> dict | None:
        """Eine Zeile abfragen und als dict zurueckgeben."""
        cursor = await self.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetch_all(self, sql: str, params: tuple = ()) -> list[dict]:
        """Alle Zeilen abfragen und als Liste von dicts zurueckgeben."""
        cursor = await self.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def commit(self) -> None:
        """Transaktion bestaetigen."""
        await self.connection.commit()


# Globale Datenbankinstanz
db = Database()
