"""Der ganze Weg einer Aufnahme ohne Kellerwolke (Entwicklung): prüfen, Teile hochladen, lesen, Regal."""

import asyncio
import hashlib

import fitz
import pytest


def pdf(worte: str, seiten: int = 2) -> bytes:
    d = fitz.open()
    for n in range(seiten):
        d.new_page().insert_text((60, 80), f"{worte} Seite {n + 1}")
    return d.tobytes()


async def hochladen(client, kopf, name: str, inhalt: bytes, teil: int = 4000) -> dict:
    r = await client.post("/api/annahme", headers=kopf, json={"name": name, "groesse": len(inhalt), "sha256": hashlib.sha256(inhalt).hexdigest()})
    assert r.status_code == 200, r.text
    z = r.json()
    while z["stand"] in ("wartet", "laedt") and z["empfangen"] < len(inhalt):
        stueck = inhalt[z["empfangen"]: z["empfangen"] + teil]
        r = await client.patch(f"/api/annahme/{z['id']}", headers={**kopf, "Upload-Offset": str(z["empfangen"])}, content=stueck)
        assert r.status_code == 200, r.text
        z = r.json()
    return z


async def warten(client, kopf, nr: int, bestaetigen: bool = True) -> dict:
    """Bis die Aufnahme nicht mehr läuft; wartet sie auf die Bestätigung (BF-80), wird ihre Vorschau übernommen, außer
    `bestaetigen` ist aus."""
    for _ in range(300):
        z = (await client.get(f"/api/annahme/{nr}", headers=kopf)).json()
        if z["stand"] == "bestaetigen" and bestaetigen:
            r = await client.post(f"/api/annahme/vorschau/{z['vorschau']}/uebernehmen", headers=kopf, json={"ids": [nr]})
            assert r.status_code == 200, r.text
            continue
        if z["stand"] not in ("wartet", "laedt", "liest", "angaben", "regal", "entpacken"):
            return z
        await asyncio.sleep(.1)
    raise AssertionError(z)


@pytest.mark.asyncio
async def test_aufnahme_bis_ins_regal(annahme_dienst, auth_headers):
    inhalt = pdf("Glaswelt Probe")
    z = await hochladen(annahme_dienst, auth_headers, "Glaswelt Probe.pdf", inhalt)
    z = await warten(annahme_dienst, auth_headers, z["id"])
    assert z["stand"] == "fertig" and z["buch_id"], z            # ohne Fundus ist sie mit dem Regal am Ziel
    buch = (await annahme_dienst.get(f"/api/books/{z['buch_id']}", headers=auth_headers)).json()
    assert buch["page_count"] == 2
    treffer = (await annahme_dienst.get("/api/search", params={"q": "Glaswelt"}, headers=auth_headers)).json()
    assert str(z["buch_id"]) in str(treffer), treffer
    assert treffer.get("gesamt", treffer.get("total")) == 1, treffer
    doppelt = await hochladen(annahme_dienst, auth_headers, "Anderer Name.pdf", inhalt)
    assert doppelt["stand"] == "da" and doppelt["buch_id"] == z["buch_id"]


@pytest.mark.asyncio
async def test_was_nicht_geht_wird_gesagt(annahme_dienst, auth_headers):
    z = await hochladen(annahme_dienst, auth_headers, "Comic.cbz", b"x" * 10)
    assert z["stand"] == "format" and "PDF" in z["text"]
    z = await hochladen(annahme_dienst, auth_headers, "leer.pdf", b"")
    assert z["stand"] == "kaputt"
    z = await hochladen(annahme_dienst, auth_headers, "kaputt.pdf", b"%PDF-1.7 kein echtes PDF")
    assert (await warten(annahme_dienst, auth_headers, z["id"]))["stand"] == "kaputt"
    zaehler = (await annahme_dienst.get("/api/annahme", headers=auth_headers)).json()["zaehler"]
    assert zaehler["klaeren"] == 3


@pytest.mark.asyncio
async def test_fortsetzen_am_stand_des_servers(annahme_dienst, auth_headers):
    inhalt = pdf("Fortsetzen", 3)
    r = await annahme_dienst.post("/api/annahme", headers=auth_headers, json={"name": "Fortsetzen.pdf", "groesse": len(inhalt), "sha256": hashlib.sha256(inhalt).hexdigest()})
    nr = r.json()["id"]
    await annahme_dienst.patch(f"/api/annahme/{nr}", headers={**auth_headers, "Upload-Offset": "0"}, content=inhalt[:1000])
    r = await annahme_dienst.patch(f"/api/annahme/{nr}", headers={**auth_headers, "Upload-Offset": "0"}, content=inhalt[:1000])
    assert r.status_code == 409 and r.json()["empfangen"] == 1000
    z = await hochladen(annahme_dienst, auth_headers, "Fortsetzen.pdf", inhalt)          # nach Neuladen: derselbe Eintrag geht weiter
    assert z["id"] == nr
    assert (await warten(annahme_dienst, auth_headers, nr))["stand"] == "fertig"


@pytest.mark.asyncio
async def test_notiz_ist_sofort_gebucht(annahme_dienst, auth_headers):
    import sqlite3

    from backend.app.core.config import settings
    z = await hochladen(annahme_dienst, auth_headers, "Notiz.pdf", pdf("Notiz"))
    z = await warten(annahme_dienst, auth_headers, z["id"])
    r = await annahme_dienst.post(f"/api/books/{z['buch_id']}/notes", headers=auth_headers, json={"content": "Probe", "page_reference": "1"})
    assert r.status_code == 200
    from backend.app.core.database import db
    c = sqlite3.connect(f"file:{db.db_path}?mode=ro", uri=True)
    assert c.execute("SELECT COUNT(*) FROM book_notes").fetchone()[0] == 1
    r = await annahme_dienst.get(f"/api/books/{z['buch_id']}/volltext-suche", params={"q": "Notiz"}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["gesamt"] >= 1


@pytest.mark.asyncio
async def test_mit_fundus_wartet_sie_auf_die_bedeutung(annahme_dienst, auth_headers, monkeypatch):
    from backend.app.core.config import settings

    monkeypatch.setattr(settings, "fundus_url", "https://fundus.test")
    z = await hochladen(annahme_dienst, auth_headers, "Mit Bedeutung.pdf", pdf("Mit Bedeutung"))
    assert (await warten(annahme_dienst, auth_headers, z["id"]))["stand"] == "wissen"
