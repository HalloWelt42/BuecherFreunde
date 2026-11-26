"""Umbau für die Familie (BF-78): eine alte Datenbank mit Notizen, Markierungen, Etiketten, Lesestand, Vorlesestelle und
Lesestand einer Fassung wird übernommen; zuerst entsteht eine Sicherung, nichts geht verloren, zweimal ändert nichts, und
stimmt eine Zahl nicht, bleibt alles, wie es war. Alles erfunden."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from backend.app.core.database import NEUBAU_SQL, SCHEMA_SQL, SCHEMA_VERSION, Database
from backend.app.familie import umbau
from backend.app.familie.schema import PERSOENLICH

# die persönlichen Tabellen, wie sie vor BF-78 aussahen (mit einer Spalte label_id aus einer frühen Fassung)
ALT = """
CREATE TABLE user_book_data (book_id INTEGER PRIMARY KEY, is_favorite INTEGER DEFAULT 0, is_to_read INTEGER DEFAULT 0, rating INTEGER DEFAULT 0,
    reading_position TEXT DEFAULT '', last_read_at TEXT DEFAULT NULL, fassung_wahl TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE);
CREATE TABLE book_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER NOT NULL, content TEXT NOT NULL, page_reference INTEGER DEFAULT NULL,
    cfi_reference TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE);
CREATE TABLE book_labels (id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER NOT NULL, color TEXT NOT NULL DEFAULT '#4FC3F7',
    name TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', page_reference TEXT DEFAULT '', position_percent REAL DEFAULT 0,
    cfi_reference TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')), FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE);
CREATE TABLE book_highlights (id INTEGER PRIMARY KEY AUTOINCREMENT, book_id INTEGER NOT NULL, cfi_range TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#FFEE58', text_snippet TEXT NOT NULL DEFAULT '', label_id INTEGER DEFAULT NULL, label_name TEXT NOT NULL DEFAULT '',
    label_note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE);
CREATE TABLE vorlesestelle (buch_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE, einheit INTEGER NOT NULL, zeichen INTEGER NOT NULL,
    bis_einheit INTEGER, bis_zeichen INTEGER, umfang TEXT NOT NULL DEFAULT '', ort TEXT NOT NULL DEFAULT '',
    gemerkt_am TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')));
CREATE TABLE fassung_lesestand (fassung_id INTEGER PRIMARY KEY REFERENCES fassung(id) ON DELETE CASCADE, position TEXT NOT NULL DEFAULT '',
    gelesen_am TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')));
"""


def _alte_datenbank(pfad: Path) -> None:
    with closing(sqlite3.connect(pfad)) as v:
        v.executescript(SCHEMA_SQL + NEUBAU_SQL + ALT)
        v.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        v.execute("INSERT INTO nutzer (name, kennwort) VALUES ('Ronja Probe', 'scrypt$00$00')")
        for nr in (1, 2, 3):
            v.execute("INSERT INTO books (id, hash, title, file_format, storage_path) VALUES (?, ?, ?, 'epub', '')", (nr, f"alt{nr}", f"Altes Buch {nr}"))
        v.execute("INSERT INTO fassung (id, buch_id, sprache, aus_sprache, stand) VALUES (5, 1, 'de', 'en', 'fertig')")
        v.executemany("INSERT INTO user_book_data (book_id, is_favorite, rating, reading_position, last_read_at, fassung_wahl) VALUES (?, ?, ?, ?, ?, ?)",
                      [(1, 1, 4, "percent:30", "2026-11-01 10:00:00", "de"), (2, 0, 0, "page:12", None, ""),
                       (3, 0, 0, "", "2026-10-02 08:00:00", "")])                  # als gelesen markiert, ohne Lesestand
        v.executemany("INSERT INTO book_notes (id, book_id, content) VALUES (?, ?, ?)", [(7, 1, "Gedanke eins"), (9, 2, "Gedanke zwei")])
        v.execute("DELETE FROM book_notes WHERE id = 9")                     # die Folge der Nummern steht danach auf 9
        v.executemany("INSERT INTO book_highlights (book_id, cfi_range, label_id, label_name) VALUES (?, ?, ?, ?)",
                      [(1, "epubcfi(/6/2)", 3, "Wichtig"), (3, "epubcfi(/6/4)", None, "")])
        v.execute("INSERT INTO book_labels (book_id, name, position_percent) VALUES (2, 'Merksatz', 12.5)")
        v.execute("INSERT INTO vorlesestelle (buch_id, einheit, zeichen, umfang, ort) VALUES (1, 4, 120, 'Dieses Kapitel', 'Seite 9')")
        v.execute("INSERT INTO fassung_lesestand (fassung_id, position) VALUES (5, 'epub:{\"cfi\":\"x\"}')")
        v.commit()


def _zahlen(pfad: Path) -> dict[str, int]:
    with closing(sqlite3.connect(pfad)) as v:
        return {f.tabelle: v.execute(f"SELECT COUNT(*) FROM {f.tabelle}").fetchone()[0] for f in PERSOENLICH}


def _sicherungen(pfad: Path) -> list[Path]:
    return sorted(pfad.parent.glob(f"{pfad.stem}.vor-familie-*{pfad.suffix}"))


async def test_alte_datenbank_wird_uebernommen_und_nichts_geht_verloren(tmp_path):
    pfad = tmp_path / "alt.db"
    _alte_datenbank(pfad)
    vorher = _zahlen(pfad)
    d = Database(db_path=pfad)
    await d.connect()
    try:
        profil = await d.fetch_one("SELECT id, name, rolle, pin, name_vom_konto FROM profil")
        assert (profil["name"], profil["rolle"], profil["pin"], profil["name_vom_konto"]) == ("Ronja Probe", "verwaltung", "", 0)
        assert _zahlen(pfad) == vorher
        for f in PERSOENLICH:
            assert (await d.fetch_one(f"SELECT COUNT(*) AS n FROM {f.tabelle} WHERE profil_id != ?", (profil["id"],)))["n"] == 0
        assert await d.fetch_one("SELECT is_favorite, rating, reading_position, fassung_wahl FROM user_book_data WHERE book_id = 1") == {
            "is_favorite": 1, "rating": 4, "reading_position": "percent:30", "fassung_wahl": "de"}
        assert (await d.fetch_one("SELECT id, content FROM book_notes")) == {"id": 7, "content": "Gedanke eins"}       # Nummern bleiben
        fertig = {z["book_id"]: z["fertig_am"] for z in await d.fetch_all("SELECT book_id, fertig_am FROM user_book_data")}
        assert fertig == {1: None, 2: None, 3: "2026-10-02 08:00:00"}                 # die Markierung Gelesen von früher bleibt
        assert (await d.fetch_one("SELECT label_id, label_name FROM book_highlights WHERE book_id = 1")) == {"label_id": 3, "label_name": "Wichtig"}
        assert (await d.fetch_one("SELECT umfang, ort FROM vorlesestelle")) == {"umfang": "Dieses Kapitel", "ort": "Seite 9"}
        assert (await d.fetch_one("SELECT position FROM fassung_lesestand"))["position"] == 'epub:{"cfi":"x"}'
        neu = await d.execute("INSERT INTO book_notes (profil_id, book_id, content) VALUES (?, 1, 'neu')", (profil["id"],))
        assert neu.lastrowid == 10                                           # nach der höchsten je vergebenen Nummer
        await d.commit()
    finally:
        await d.disconnect()
    [sicherung] = _sicherungen(pfad)
    with closing(sqlite3.connect(sicherung)) as v:                           # die Sicherung ist die alte Form, vollständig
        assert v.execute("SELECT COUNT(*) FROM book_notes").fetchone()[0] == 1
        assert "profil_id" not in {s[1] for s in v.execute("PRAGMA table_info(user_book_data)")}
    with closing(sqlite3.connect(pfad)) as v:
        assert v.execute("PRAGMA foreign_key_check").fetchall() == []
        assert v.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


async def test_zweimal_aendert_nichts(tmp_path):
    pfad = tmp_path / "alt.db"
    _alte_datenbank(pfad)
    for _ in range(2):
        d = Database(db_path=pfad)
        await d.connect()
        await d.disconnect()
    assert len(_sicherungen(pfad)) == 1
    with closing(sqlite3.connect(pfad)) as v:
        assert v.execute("SELECT COUNT(*) FROM profil").fetchone()[0] == 1
    assert umbau.umbauen(pfad) is None


async def test_stimmt_eine_zahl_nicht_bleibt_alles_wie_es_war(tmp_path, monkeypatch):
    pfad = tmp_path / "alt.db"
    _alte_datenbank(pfad)
    echt = umbau._zahl
    monkeypatch.setattr(umbau, "_zahl", lambda v, t: echt(v, t) - 1 if t == "book_labels" + umbau.NEU else echt(v, t))
    with pytest.raises(umbau.UmbauFehler, match="book_labels"):
        umbau.umbauen(pfad)
    with closing(sqlite3.connect(pfad)) as v:
        assert not v.execute("SELECT 1 FROM sqlite_master WHERE name = 'profil'").fetchone()
        assert "profil_id" not in {s[1] for s in v.execute("PRAGMA table_info(book_notes)")}
        assert not v.execute("SELECT 1 FROM sqlite_master WHERE name LIKE '%__familie'").fetchone()
    monkeypatch.setattr(umbau, "_zahl", echt)
    assert umbau.umbauen(pfad) is not None                                   # beim nächsten Start geht es
    assert _zahlen(pfad)["book_labels"] == 1


async def test_neue_datenbank_ohne_sicherung_mit_platzhalter_fuer_den_namen(tmp_path):
    d = Database(db_path=tmp_path / "neu.db")
    await d.connect()
    try:
        profil = await d.fetch_one("SELECT name, name_vom_konto FROM profil")
        assert profil == {"name": "Verwaltung", "name_vom_konto": 1}
    finally:
        await d.disconnect()
    assert _sicherungen(tmp_path / "neu.db") == []


async def test_spaeter_dazugekommene_spalte_wird_nachgezogen(tmp_path):
    """Eine Form bekommt eine Spalte (fertig_am): schon umgebaute Tabellen bekommen sie beim Start, mit nachgetragenem Stand."""
    pfad = tmp_path / "neu.db"
    d = Database(db_path=pfad)
    await d.connect()
    await d.disconnect()
    with closing(sqlite3.connect(pfad)) as v:
        profil = v.execute("SELECT id FROM profil").fetchone()[0]
        v.execute("ALTER TABLE user_book_data DROP COLUMN fertig_am")
        v.execute("INSERT INTO books (id, hash, title, file_format, storage_path, page_count) VALUES (1, 'n1', 'Probe', 'pdf', '', 40)")
        v.execute("INSERT INTO user_book_data (profil_id, book_id, reading_position, last_read_at) VALUES (?, 1, 'page:40', '2026-11-20 09:00:00')",
                  (profil,))
        v.commit()
    assert umbau.umbauen(pfad) is None                                       # kein Umbau, nur nachgezogen
    with closing(sqlite3.connect(pfad)) as v:
        assert v.execute("SELECT fertig_am FROM user_book_data").fetchone()[0] == "2026-11-20 09:00:00"
