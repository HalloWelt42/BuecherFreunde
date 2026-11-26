"""Dateien je Buch (BF-80): der Umbau beim Start gibt jedem vorhandenen Buch genau eine Datei, mit Sicherung davor, und ein
zweiter Lauf ändert nichts; neue Bücher bekommen ihre Datei von der Datenbank selbst. Alles erfunden."""

from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest

from backend.app.ablage import formate_umbau
from backend.app.core.database import Database

BUCH = ("INSERT INTO books (hash, title, file_format, file_size, file_name, storage_path) VALUES (?, ?, ?, ?, ?, '')")


async def _bestand(pfad) -> None:
    """Ein Bestand wie vor BF-80: Bücher ohne Zeilen in buch_datei."""
    d = Database(db_path=pfad)
    await d.connect()
    await d.disconnect()
    with closing(sqlite3.connect(pfad)) as v:
        v.executemany(BUCH, [("h1", "Erstes Probebuch", "pdf", 10, "eins.pdf"), ("h2", "Zweites Probebuch", "epub", 20, "zwei.epub"),
                             ("h3", "Drittes Probebuch", "txt", 30, "drei.txt")])
        v.execute("DELETE FROM buch_datei")
        v.commit()


def _dateien(pfad) -> list[tuple]:
    with closing(sqlite3.connect(pfad)) as v:
        return v.execute("SELECT b.hash, d.format, d.name, d.groesse, d.haupt FROM buch_datei d JOIN books b ON b.id = d.buch_id ORDER BY b.hash").fetchall()


async def test_umbau_mit_sicherung_und_ein_zweiter_lauf_aendert_nichts(tmp_path):
    pfad = tmp_path / "bestand.db"
    await _bestand(pfad)
    bericht = formate_umbau.umbauen(pfad)
    assert bericht is not None and (bericht.nachgetragen, bericht.buecher) == (3, 3)
    assert bericht.sicherung.exists() and bericht.sicherung.name.startswith("bestand.vor-dateien-")
    with closing(sqlite3.connect(bericht.sicherung)) as v:                 # die Sicherung ist der Stand davor
        assert v.execute("SELECT COUNT(*) FROM buch_datei").fetchone()[0] == 0
    assert _dateien(pfad) == [("h1", "pdf", "eins.pdf", 10, 1), ("h2", "epub", "zwei.epub", 20, 1), ("h3", "txt", "drei.txt", 30, 1)]
    vorher = sorted(p.name for p in tmp_path.iterdir())
    assert formate_umbau.umbauen(pfad) is None
    assert _dateien(pfad) == [("h1", "pdf", "eins.pdf", 10, 1), ("h2", "epub", "zwei.epub", 20, 1), ("h3", "txt", "drei.txt", 30, 1)]
    assert sorted(p.name for p in tmp_path.iterdir()) == vorher            # keine zweite Sicherung


async def test_beim_verbinden_und_fuer_neue_buecher(tmp_path):
    pfad = tmp_path / "bestand.db"
    await _bestand(pfad)
    d = Database(db_path=pfad)
    await d.connect()                                                    # der Umbau läuft beim Verbinden
    try:
        await d.execute(BUCH, ("h4", "Viertes Probebuch", "md", 40, "vier.md"))
        await d.commit()
        z = await d.fetch_one("SELECT format, name, haupt, length(id) AS l FROM buch_datei WHERE hash = 'h4'")
        assert (z["format"], z["name"], z["haupt"], z["l"]) == ("md", "vier.md", 1, 36)
        await d.execute("UPDATE books SET file_name = 'vier neu.md' WHERE hash = 'h4'")
        await d.commit()
        assert (await d.fetch_one("SELECT name FROM buch_datei WHERE hash = 'h4'"))["name"] == "vier neu.md"
    finally:
        await d.disconnect()
    assert len(_dateien(pfad)) == 4


async def test_stimmt_die_zahl_nicht_rollt_alles_zurueck(tmp_path, monkeypatch):
    pfad = tmp_path / "bestand.db"
    await _bestand(pfad)
    monkeypatch.setattr(formate_umbau, "_nachtragen", lambda v: 0)       # trägt nichts nach: die Prüfung muss es merken
    with pytest.raises(formate_umbau.UmbauFehler):
        formate_umbau.umbauen(pfad)
    assert _dateien(pfad) == []
