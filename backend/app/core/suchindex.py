"""Suchindex als eigene Datenbankdatei (Ort "suche"), getrennt vom Bestand: groß, jederzeit neu zu bauen, für sich umziehbar.

Die Datei wird an die Verbindung des Bestands gehängt (Schema `suche`). `buch_text` hält Titel, Autor und Suchtext je Buch,
`buch_fts` ist der Volltextindex darüber. Änderungen am Bestand ziehen flüchtige Trigger nach (TEMP, weil nur sie über zwei
Dateien hinweg schreiben dürfen); der Suchtext kommt einmal über `books.fts_content` herein und wird dort danach geleert."""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger("buecherfreunde.suchindex")
SUCHTEXT_ZEICHEN = 100_000        # so viel Text je Buch steht im Index (wie bisher)

SCHEMA = """
CREATE TABLE IF NOT EXISTS suche.buch_text(id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT '', author TEXT NOT NULL DEFAULT '', inhalt TEXT NOT NULL DEFAULT '');
CREATE VIRTUAL TABLE IF NOT EXISTS suche.buch_fts USING fts5(title, author, inhalt, content='buch_text', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS suche.buch_text_neu AFTER INSERT ON buch_text BEGIN
    INSERT INTO buch_fts(rowid, title, author, inhalt) VALUES (new.id, new.title, new.author, new.inhalt);
END;
CREATE TRIGGER IF NOT EXISTS suche.buch_text_weg AFTER DELETE ON buch_text BEGIN
    INSERT INTO buch_fts(buch_fts, rowid, title, author, inhalt) VALUES ('delete', old.id, old.title, old.author, old.inhalt);
END;
CREATE TRIGGER IF NOT EXISTS suche.buch_text_anders AFTER UPDATE ON buch_text BEGIN
    INSERT INTO buch_fts(buch_fts, rowid, title, author, inhalt) VALUES ('delete', old.id, old.title, old.author, old.inhalt);
    INSERT INTO buch_fts(rowid, title, author, inhalt) VALUES (new.id, new.title, new.author, new.inhalt);
END;
"""

FLUECHTIG = """
CREATE TEMP TRIGGER IF NOT EXISTS suche_buch_neu AFTER INSERT ON main.books BEGIN
    INSERT INTO buch_text(id, title, author, inhalt) VALUES (new.id, new.title, new.author, COALESCE(new.fts_content, ''));
END;
CREATE TEMP TRIGGER IF NOT EXISTS suche_buch_weg AFTER DELETE ON main.books BEGIN
    DELETE FROM buch_text WHERE id = old.id;
END;
CREATE TEMP TRIGGER IF NOT EXISTS suche_buch_name AFTER UPDATE OF title, author ON main.books
WHEN new.title IS NOT old.title OR new.author IS NOT old.author BEGIN
    UPDATE buch_text SET title = new.title, author = new.author WHERE id = new.id;
END;
CREATE TEMP TRIGGER IF NOT EXISTS suche_buch_text AFTER UPDATE OF fts_content ON main.books
WHEN COALESCE(new.fts_content, '') <> '' BEGIN
    UPDATE buch_text SET inhalt = new.fts_content WHERE id = new.id;
END;
"""


async def anhaengen(v: aiosqlite.Connection, ordner: Path) -> None:
    ordner.mkdir(parents=True, exist_ok=True)
    await v.execute("ATTACH DATABASE ? AS suche", (str(ordner / "suche.db"),))
    await v.execute("PRAGMA suche.journal_mode=WAL")
    await v.executescript(SCHEMA)
    await v.executescript(FLUECHTIG)
    await _uebernehmen(v)


async def verbinden(v: aiosqlite.Connection, ordner: Path) -> None:
    """Für jede weitere Verbindung (eine je Anfrage): die Suchdatei anhängen und die flüchtigen Trigger setzen, die es je
    Verbindung gibt. Schema und Übernahme hat die erste Verbindung schon erledigt."""
    await v.execute("ATTACH DATABASE ? AS suche", (str(ordner / "suche.db"),))
    await v.executescript(FLUECHTIG)


async def _uebernehmen(v: aiosqlite.Connection) -> None:
    """Alter Index im Bestand (bis 0.13) oder eine frische Suchdatei: füllen, danach den alten Index entfernen."""
    alt = await (await v.execute("SELECT 1 FROM main.sqlite_master WHERE name = 'books_fts'")).fetchone()
    fehlt = (await (await v.execute("SELECT COUNT(*) FROM books WHERE id NOT IN (SELECT id FROM suche.buch_text)")).fetchone())[0]
    if fehlt:
        logger.info("Suchindex: %d Bücher werden aufgenommen", fehlt)
        await v.execute("INSERT INTO buch_text(id, title, author, inhalt) SELECT id, title, author, COALESCE(fts_content, '') FROM books "
                        "WHERE id NOT IN (SELECT id FROM buch_text)")
        await v.commit()
    if alt:
        for t in ("books_ai", "books_ad", "books_au"):
            await v.execute(f"DROP TRIGGER IF EXISTS main.{t}")
        await v.execute("DROP TABLE IF EXISTS main.books_fts")
    await v.execute("DELETE FROM buch_text WHERE id NOT IN (SELECT id FROM books)")
    await v.execute("UPDATE books SET fts_content = '' WHERE COALESCE(fts_content, '') <> ''")
    await v.commit()
    if alt:
        await v.execute("VACUUM main")
        logger.info("Suchindex aus dem Bestand gelöst, Bestand verkleinert")
    if fehlt or alt:
        for schema in ("main", "suche"):
            await v.execute(f"PRAGMA {schema}.wal_checkpoint(TRUNCATE)")      # das Protokoll der Übernahme ist so groß wie der Index


async def neu_bauen(v: aiosqlite.Connection, text_von) -> int:
    """Index aus Angaben und Volltexten neu aufbauen. `text_von(hash)` liefert den Volltext eines Buchs oder ""."""
    zeilen = await (await v.execute("SELECT id, hash, title, author FROM books")).fetchall()
    await v.execute("DELETE FROM buch_text")
    for z in zeilen:
        await v.execute("INSERT INTO buch_text(id, title, author, inhalt) VALUES (?, ?, ?, ?)",
                        (z["id"], z["title"], z["author"], (text_von(z["hash"]) or "")[:SUCHTEXT_ZEICHEN]))
    await v.execute("INSERT INTO buch_fts(buch_fts) VALUES('optimize')")
    await v.commit()
    return len(zeilen)
