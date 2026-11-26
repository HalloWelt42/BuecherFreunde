"""Markierungen sind sofort gebucht (BF-4): was die Schnittstelle meldet, sieht auch eine zweite Verbindung zur Datenbank,
nach dem Anlegen, Ändern und Löschen; keine Änderung bleibt in einer offenen Buchung hängen."""

import sqlite3

from backend.app.core.database import db
from tests.api.conftest import buch_erstellen


def zweite_verbindung() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db.db_path}?mode=ro", uri=True)


async def test_markierungen_sind_sofort_gebucht(client, test_db):
    buch = await buch_erstellen(test_db)
    r = await client.post(f"/api/books/{buch}/highlights", json={"cfi_range": "epubcfi(/6/4!/4/2,/1:0,/1:12)", "text_snippet": "Probe"})
    assert r.status_code == 200
    nr = r.json()["id"]
    mit = zweite_verbindung()
    try:
        assert mit.execute("SELECT text_snippet, color FROM book_highlights WHERE id = ?", (nr,)).fetchone() == ("Probe", "#FFEE58")
        assert (await client.patch(f"/api/highlights/{nr}", json={"color": "#90CAF9", "label_name": "Wichtig"})).status_code == 200
        assert mit.execute("SELECT color, label_name FROM book_highlights WHERE id = ?", (nr,)).fetchone() == ("#90CAF9", "Wichtig")
        assert (await client.delete(f"/api/highlights/{nr}")).status_code == 200
        assert mit.execute("SELECT COUNT(*) FROM book_highlights WHERE id = ?", (nr,)).fetchone()[0] == 0
    finally:
        mit.close()
