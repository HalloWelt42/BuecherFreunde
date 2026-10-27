"""Sichern von Hand über die Einstellungen: folgt der Sicherungsregel und sagt, wenn keine neue nötig war."""

import sqlite3

from backend.app.core.config import settings


async def test_von_hand_sichern_und_ohne_aenderung_keine_neue(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "database_dir", tmp_path / "database")
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    settings.database_dir.mkdir()
    with sqlite3.connect(settings.database_path) as v:
        v.execute("CREATE TABLE buch (titel TEXT)")

    erste = (await client.post("/api/backup/create")).json()
    zweite = (await client.post("/api/backup/create")).json()

    assert erste["neu"] is True and erste["message"] == "Backup erstellt"
    assert zweite["neu"] is False and zweite["filename"] == erste["filename"] and "unverändert" in zweite["message"]
    liste = (await client.get("/api/backup/list")).json()
    assert [b["filename"] for b in liste] == [erste["filename"]]
