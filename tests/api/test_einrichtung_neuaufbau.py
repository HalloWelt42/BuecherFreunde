"""Neuaufbau aus der Kellerwolke ohne Sicherung (BF-82): aus dem Auszug je Buch entstehen Bücher, Angaben, Volltext und Umschläge,
aus dem Begleiter `persoenlich` (sonst aus einem alten Auszug) das Persönliche je Profil, die Profile aus ihrer Datei ohne PIN. Der
Bericht nennt Bücher ohne Auszug. Nur gegen die Attrappe der Kellerwolke, mit eigenen Orten; alle Namen sind erfunden."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from backend.app.ablage import persoenlich
from backend.app.ablage.auszug import FORM
from backend.app.core.database import db
from backend.app.einrichtung.neuaufbau import neuaufbau
from backend.app.services.storage import get_sidecar_path
from tests.api.einrichtung_hilfen import als_verwaltung, neu, orte  # noqa: F401 - Fixtures
from tests.api.kellerwolke_attrappe import Kellerwolke

pytestmark = pytest.mark.asyncio
ALT = "9a8b7c6d-1111-4222-8333-444455556666"          # das Verwaltungsprofil des alten Bestands
KIND = "9a8b7c6d-2222-4222-8333-444455556666"


def _auszug(buch: dict, mit_dateien: bool = True, **alt) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        if mit_dateien:
            z.writestr("fulltext.txt", "Der Leuchtturm stand am Kai.")
            z.writestr("cover.jpg", b"\xff\xd8 Umschlag")
        z.writestr("angaben.json", json.dumps({"art": FORM, "buch": buch, "kategorien": ["Probe-Regal"], **alt}))
    return puffer.getvalue()


def _begleiter(w: Kellerwolke, haupt: str, rolle: str, zusatz: str, inhalt: bytes) -> None:
    k = w._neu("datei", w.knoten[haupt]["name"].rpartition(".")[0] + zusatz, w.knoten[haupt]["parent_id"], inhalt)
    w.knoten[k] |= {"haupt_id": haupt, "rolle": rolle}


@pytest.fixture
def wolke(neu, monkeypatch) -> Kellerwolke:
    w = Kellerwolke()
    w.einhaengen(monkeypatch)
    eins = w.datei("Apps/BücherFreunde/Bücher/P/Probeband eins - Ida Probe [41].pdf", b"%PDF eins")
    _begleiter(w, eins, "auszug", ".auszug.zip", _auszug(
        {"id": 41, "hash": "egal", "title": "Probeband eins", "author": "Ida Probe", "year": 2021, "file_format": "pdf", "file_size": 9,
         "file_name": "eins.pdf", "page_count": 12, "fts_content": "nie", "storage_path": "/alt"}))
    _begleiter(w, eins, "persoenlich", ".persoenlich.json", persoenlich.Begleiter(buch=41, hash="egal", profile={
        ALT: {"notizen": [{"content": "Notiz der Verwaltung"}]},
        KIND: {"lesestand": {"reading_position": "page:5"}, "freigegeben": True},
        "ffffffff-0000-4000-8000-000000000000": {"notizen": [{"content": "eines Profils, das es nicht gibt"}]}}).model_dump_json().encode())
    drei = w.datei("Apps/BücherFreunde/Bücher/A/Altband drei [43].pdf", b"%PDF drei")
    _begleiter(w, drei, "auszug", ".auszug.zip", _auszug({"id": 43, "title": "Altband drei"}, mit_dateien=False,
                                                         notizen=[{"id": 9, "book_id": 43, "content": "aus altem Auszug", "profil_id": KIND}]))
    w.datei("Apps/BücherFreunde/Bücher/Z/Zweiter Band - Ida Probe [42].epub", b"PK epub zwei")
    w.datei("Apps/BücherFreunde/Bücher/Z/Lies mich.jpg", b"kein Buch")
    w.datei("Apps/BücherFreunde/profile.json", json.dumps({"art": "buecherfreunde-profile/1", "stimme": "katalog:Probestimme",
        "profile": [{"id": ALT, "name": "Ida Probe", "rolle": "verwaltung", "zeichen": "eule", "farbe": "#336699"},
                    {"id": KIND, "name": "Lotte Probe", "rolle": "kind", "stufe": "schule", "geburtsjahr": 2016,
                     "einstellungen": {"lesehilfen": {"silben": True}}}],
        "freigaben": [{"profil": KIND, "schluessel": "", "name": "Probe-Regal"}]}).encode())
    return w


async def test_neuaufbau_aus_den_auszuegen_mit_profilen_ohne_pin(wolke, client, client_ohne_auth):
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "kellerwolke"})
    assert (await client_ohne_auth.post("/api/anmeldung/einrichten", json={"kennung": "Ida Probe", "passwort": "ein langes Kennwort"})).status_code == 201
    vorher = {k: dict(z) for k, z in wolke.knoten.items()}

    o = (await client.post("/api/einrichtung/neuaufbau/ordner", json={"pfad": "Bücher"})).json()
    assert (o["buecher"], o["mit_auszug"], o["ohne_auszug"], o["mit_persoenlichem"], o["schon_da"], o["profile_datei"]) == (3, 2, 1, 1, 0, True), o
    assert o["profile"] == ["Ida Probe", "Lotte Probe"]
    assert wolke.knoten == vorher, "Ordner prüfen ändert in der Kellerwolke nichts"
    assert (await client.post("/api/einrichtung/neuaufbau/ordner", json={"pfad": "Gibt es nicht"})).status_code == 404

    s = (await client.post("/api/einrichtung/neuaufbau")).json()
    assert s["art"] == "neuaufbau" and [t["schluessel"] for t in s["teile"]] == ["buecher", "angaben", "volltext", "umschlaege", "persoenliches"]
    await neuaufbau.warten()
    client.headers.update(await als_verwaltung(client))
    b = (await client.get("/api/einrichtung/neuaufbau/bericht")).json()
    assert b["auftrag"]["stand"] == "fertig" and (b["buecher"], b["mit_auszug"], b["profile"]) == (3, 2, 2)
    assert [(e["name"], e["buch_id"]) for e in b["ohne_auszug"]] == [("Zweiter Band - Ida Probe [42].epub", 42)]
    assert {t["schluessel"]: t["fertig"] for t in b["auftrag"]["teile"]} == {"buecher": 3, "angaben": 2, "volltext": 1, "umschlaege": 1, "persoenliches": 2}

    eins = await db.fetch_one("SELECT * FROM books WHERE id = 41")
    assert (eins["title"], eins["author"], eins["year"], eins["page_count"], eins["fts_content"]) == ("Probeband eins", "Ida Probe", 2021, 12, "")
    assert eins["hash"] == wolke.ansicht(next(k for k, z in wolke.knoten.items() if z["name"].endswith("[41].pdf")))["sha256"]
    assert get_sidecar_path(eins["hash"], "fulltext.txt").read_text() == "Der Leuchtturm stand am Kai."
    assert get_sidecar_path(eins["hash"], "cover.jpg").read_bytes() == b"\xff\xd8 Umschlag"
    zwei = await db.fetch_one("SELECT title, author, file_format FROM books WHERE id = 42")
    assert dict(zwei) == {"title": "Zweiter Band", "author": "Ida Probe", "file_format": "epub"}

    profile = {z["rolle"]: z for z in await db.fetch_all("SELECT * FROM profil")}
    assert len(profile) == 2, "das Profil des Kontos übernimmt das Verwaltungsprofil der Datei (sein Name bleibt der des Kontos)"
    kind, ich = profile["kind"], profile["verwaltung"]
    assert (kind["id"], kind["name"], kind["pin"], kind["bild_pin"]) == (KIND, "Lotte Probe", "", "")
    assert json.loads(kind["einstellungen"])["lesehilfen"]["silben"] is True
    assert ich["zeichen"] == "eule" and ich["id"] != ALT
    notiz = await db.fetch_one("SELECT profil_id, content FROM book_notes WHERE book_id = 41")
    assert (notiz["profil_id"], notiz["content"]) == (ich["id"], "Notiz der Verwaltung")
    assert (await db.fetch_one("SELECT COUNT(*) AS n FROM book_notes WHERE book_id = 41"))["n"] == 1, "Daten eines unbekannten Profils kommen nicht herein"
    alt = await db.fetch_one("SELECT profil_id, content FROM book_notes WHERE book_id = 43")
    assert (alt["profil_id"], alt["content"]) == (KIND, "aus altem Auszug"), "ohne Begleiter zählt, was ein alter Auszug trägt"
    assert (await db.fetch_one("SELECT reading_position FROM user_book_data WHERE profil_id = ? AND book_id = 41", (KIND,)))["reading_position"] == "page:5"
    freigaben = {(z["art"], z["ziel_id"]) for z in await db.fetch_all("SELECT art, ziel_id FROM freigabe WHERE profil_id = ?", (KIND,))}
    regal = (await db.fetch_one("SELECT id FROM categories WHERE name = 'Probe-Regal'"))["id"]
    assert freigaben == {("buch", 41), ("kategorie", regal)}
    assert (await db.fetch_one("SELECT value FROM app_settings WHERE key = 'familie_stimme'"))["value"] == "katalog:Probestimme"
    assert await db.fetch_one("SELECT 1 FROM book_categories WHERE book_id = 41 AND category_id = ?", (regal,))
    assert not await db.fetch_one("SELECT 1 FROM nachfuehren WHERE art = 'buch'"), "der Neuaufbau schreibt das Persönliche nicht gleich zurück"
    assert (await db.fetch_one("SELECT knoten, begleiter FROM ablage_datei WHERE hash = ?", (eins["hash"],)))["begleiter"]

    # ein zweiter Lauf ändert nichts an dem, was schon da ist
    await client.post("/api/einrichtung/neuaufbau")
    await neuaufbau.warten()
    assert (await db.fetch_one("SELECT COUNT(*) AS n FROM books"))["n"] == 3


async def test_neuaufbau_nur_in_seiner_ausgangslage(wolke, client_ohne_auth):
    await client_ohne_auth.post("/api/einrichtung/ausgangslage", json={"ausgangslage": "neu"})
    r = await client_ohne_auth.post("/api/einrichtung/neuaufbau/ordner", json={"pfad": "Bücher"})
    assert r.status_code == 409
