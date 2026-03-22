"""SQLite-Datenbank mit FTS5 Volltextsuche."""

import logging
import sqlite3
from pathlib import Path

import aiosqlite

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.db")

SCHEMA_VERSION = 14

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

-- Trigger für automatische FTS-Synchronisation
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

        # WAL-Modus für bessere Performance
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
        """Gibt die aktive Datenbankverbindung zurück."""
        if self._connection is None:
            raise RuntimeError("Datenbank ist nicht verbunden")
        return self._connection

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
