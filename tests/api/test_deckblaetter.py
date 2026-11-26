"""Gestaltete Deckblätter (BF-59): Gattungen, Umschlagangaben an Liste und Buch, Einordnen von Hand, die Umschlagprüfung
mit kleinen Testbildern und das Einordnen mit der lokalen KI gegen eine Attrappe der Leitstelle."""

import asyncio
import json
import os
from urllib.parse import unquote

import httpx
import pytest

from backend.app.core.config import settings
from backend.app.models.book import GATTUNGEN, umschlag_zeigen
from backend.app.services import umschlagpruefung as pruefung_modul
from backend.app.services.einordnung import einordner
from backend.app.services.storage import get_sidecar_path, save_cover, save_fulltext
from backend.app.services.umschlagpruefung import Umschlagpruefung
from tests.api.conftest import buch_erstellen
from tests.api.test_ausfuehren import LEITSTELLE, chat_antwort, leitstelle  # noqa: F401 - Attrappe der Leitstelle
from tests.backend.test_deckblatt import bild, titelseite

ROT = (200, 20, 20)


@pytest.fixture
def orte(tmp_path, monkeypatch):
    """Eigene Orte für Umschläge und Volltexte je Test."""
    for ort in ("storage_dir", "umschlaege_dir"):
        monkeypatch.setattr(settings, ort, tmp_path / ort)


def umschlag(file_hash: str, daten: bytes, stand: int) -> None:
    """Ein Umschlag mit festem Stand (der Stand zählt in Sekunden: zweimal in derselben Sekunde wäre derselbe)."""
    os.utime(save_cover(file_hash, daten), (stand, stand))


async def zeile(test_db, buch: int) -> dict:
    return await test_db.fetch_one("SELECT typ, gattung, umschlag_wahl, umschlag_schlicht, umschlag_geprueft, einordnung, "
                                   "manuell_bearbeitet, updated_at FROM books WHERE id = ?", (buch,))


async def setzen(test_db, buch: int, **spalten) -> None:
    await test_db.execute(f"UPDATE books SET {', '.join(f'{k} = ?' for k in spalten)} WHERE id = ?", (*spalten.values(), buch))
    await test_db.commit()


# -- Gattungen, Umschlag an Liste und Buch ----------------------------------------------------------------------------------

async def test_gattungen_in_fester_reihenfolge(client):
    r = (await client.get("/api/collections/gattungen")).json()
    assert [g["id"] for g in r] == ["krimi", "thriller", "historisch", "fantasy", "liebesroman", "roman", "klassiker", "sachbuch",
                                    "ratgeber", "informatik", "mathematik", "fachbuch", "wirtschaft"]
    assert r == GATTUNGEN and r[2] == {"id": "historisch", "name": "Historischer Roman"} and r[-1]["name"] == "Wirtschaft und Recht"


@pytest.mark.parametrize(("wahl", "schlicht", "umschlag_"), [
    ("", False, "titelseite"), ("", True, "gestaltet"), ("titelseite", True, "titelseite"), ("gestaltet", False, "gestaltet"),
])
def test_umschlag_aus_wahl_und_befund(wahl, schlicht, umschlag_):
    assert umschlag_zeigen(wahl, schlicht) == umschlag_


async def test_liste_und_buch_tragen_die_umschlagangaben(client, test_db):
    ungeprueft = await buch_erstellen(test_db, hash="u1", title="A ungeprüft", author="Gleich")
    schlicht = await buch_erstellen(test_db, hash="s1", title="B schlicht", author="Gleich")
    gewaehlt = await buch_erstellen(test_db, hash="g1", title="C gewählt", author="Gleich")
    await setzen(test_db, schlicht, umschlag_schlicht=1)
    await setzen(test_db, gewaehlt, umschlag_schlicht=1, umschlag_wahl="titelseite", gattung="krimi")
    erwartet = {ungeprueft: ("", "", False, "titelseite"), schlicht: ("", "", True, "gestaltet"),
                gewaehlt: ("krimi", "titelseite", True, "titelseite")}

    def angaben(b: dict) -> tuple:
        return b["gattung"], b["umschlag_wahl"], b["umschlag_schlicht"], b["umschlag"]

    liste = (await client.get("/api/books")).json()["buecher"]
    assert {b["id"]: angaben(b) for b in liste} == erwartet
    for nr, werte in erwartet.items():
        assert angaben((await client.get(f"/api/books/{nr}")).json()) == werte
    aehnliche = (await client.get(f"/api/books/{ungeprueft}/aehnliche")).json()["vom_autor"]
    assert {b["id"]: angaben(b) for b in aehnliche} == {k: v for k, v in erwartet.items() if k != ungeprueft}


# -- Ändern von Hand ----------------------------------------------------------------------------------------------------------

async def test_typ_oder_gattung_setzen_heisst_von_hand(client, test_db):
    krimi = await buch_erstellen(test_db, hash="k1")
    akte = await buch_erstellen(test_db, hash="a1")
    r = await client.patch(f"/api/books/{krimi}", json={"gattung": "krimi"})
    assert r.status_code == 200 and r.json()["gattung"] == "krimi"
    assert (await client.patch(f"/api/books/{akte}", json={"typ": "dokument"})).json()["typ"] == "dokument"
    for nr in (krimi, akte):
        z = await zeile(test_db, nr)
        assert z["einordnung"] == "hand" and z["manuell_bearbeitet"] == 1


async def test_umschlag_waehlen_bearbeitet_keine_angabe(client, test_db):
    buch = await buch_erstellen(test_db, hash="w1")
    await setzen(test_db, buch, umschlag_schlicht=1, updated_at="2026-01-01 00:00:00")
    r = (await client.patch(f"/api/books/{buch}", json={"umschlag_wahl": "titelseite"})).json()
    assert r["umschlag_wahl"] == "titelseite" and r["umschlag"] == "titelseite"
    z = await zeile(test_db, buch)
    assert z["manuell_bearbeitet"] == 0 and z["updated_at"] == "2026-01-01 00:00:00" and z["einordnung"] == ""
    assert (await client.patch(f"/api/books/{buch}", json={"umschlag_wahl": ""})).json()["umschlag"] == "gestaltet"   # wieder automatisch
    await client.patch(f"/api/books/{buch}", json={"umschlag_wahl": "gestaltet", "title": "Neu"})
    z = await zeile(test_db, buch)
    assert z["umschlag_wahl"] == "gestaltet" and z["manuell_bearbeitet"] == 1 and z["einordnung"] == ""                # der Titel schon


async def test_typ_fuer_viele_heisst_von_hand(client, test_db):
    buecher = [await buch_erstellen(test_db, hash=f"v{i}") for i in range(2)]
    r = await client.post("/api/books/bulk", json={"book_ids": buecher, "aktion": "typ_setzen", "wert": "dokument"})
    assert r.json()["betroffen"] == 2
    assert [(await zeile(test_db, b))["einordnung"] for b in buecher] == ["hand", "hand"]


# -- Umschläge prüfen -------------------------------------------------------------------------------------------------------

async def test_umschlagpruefung(client, test_db, orte, monkeypatch):
    monkeypatch.setattr(pruefung_modul, "TEIL", 2)          # drei Bücher: zwei Teile
    monkeypatch.setattr(pruefung_modul, "PAUSE_S", 0)
    weiss = await buch_erstellen(test_db, hash="weiss1")
    bunt = await buch_erstellen(test_db, hash="bunt1")
    ohne = await buch_erstellen(test_db, hash="ohne1")
    umschlag("weiss1", titelseite(), 1_000_000)
    umschlag("bunt1", bild(ROT, art="JPEG"), 1_000_000)
    pruefung, gemeldet = Umschlagpruefung(), []
    pruefung.nach_runde.append(lambda: gemeldet.append(True))

    assert await pruefung.runde() == 3 and gemeldet == [True]
    befund = lambda z: (z["umschlag_schlicht"], z["umschlag_geprueft"])          # noqa: E731
    befunde = [befund(await zeile(test_db, b)) for b in (weiss, bunt, ohne)]
    assert befunde == [(1, 1_000_000), (0, 1_000_000), (1, 0)]                      # ohne Datei: schlicht
    assert (await client.get(f"/api/books/{bunt}")).json()["umschlag"] == "titelseite"

    assert await pruefung.runde() == 0 and gemeldet == [True]                       # nichts Neues, nichts zu tun
    umschlag("bunt1", titelseite(), 1_000_100)                                      # ein neuer Umschlag, gleich woher
    umschlag("ohne1", bild(ROT, art="JPEG"), 1_000_100)
    assert await pruefung.runde() == 2
    assert [befund(await zeile(test_db, b)) for b in (bunt, ohne)] == [(1, 1_000_100), (0, 1_000_100)]
    assert (await client.get(f"/api/books/{bunt}")).json()["umschlag"] == "gestaltet"
    get_sidecar_path("ohne1", "cover.jpg").unlink()                                 # Umschlag fort: wieder schlicht
    assert await pruefung.runde() == 1 and befund(await zeile(test_db, ohne)) == (1, 0)


async def test_umschlagpruefung_laeuft_gleich_beim_start(test_db, orte, monkeypatch):
    monkeypatch.setattr(pruefung_modul, "PAUSE_S", 0)
    buch = await buch_erstellen(test_db, hash="start1")
    pruefung, gemeldet = Umschlagpruefung(), asyncio.Event()
    pruefung.nach_runde.append(gemeldet.set)
    pruefung.starten()
    try:
        await asyncio.wait_for(gemeldet.wait(), 5)
    finally:
        await pruefung.stoppen()
    assert (await zeile(test_db, buch))["umschlag_schlicht"] == 1


# -- Einordnen mit der lokalen KI -------------------------------------------------------------------------------------------

@pytest.fixture
def einordnen(orte, leitstelle, monkeypatch):  # noqa: F811
    """Das Einordnen ohne Pausen; `sagt` legt fest, was die KI zu einem Titel antwortet (Text oder Antwort der Leitstelle)."""
    monkeypatch.setattr(settings, "einordnen_abstand_s", 0)
    monkeypatch.setattr(settings, "einordnen_an", True)
    einordner.angehalten, einordner.grund = False, ""
    modelle, antworten = leitstelle.antwort, {}

    async def antwort(r: httpx.Request):
        if r.url.path == "/v1/models":
            return modelle(r)
        titel = unquote(r.headers["X-Leitstelle-Titel"]).split("Art und Gattung: ", 1)[1]
        a = antworten[titel]
        a = await a() if callable(a) else a
        return a if isinstance(a, httpx.Response) else chat_antwort(a if isinstance(a, str) else json.dumps(a))

    leitstelle.antwort = antwort
    leitstelle.sagt = antworten.update
    leitstelle.chats = lambda: [r for r in leitstelle.anfragen if r.url.path == "/v1/chat/completions"]
    yield leitstelle
    einordner.angehalten, einordner.grund = False, ""


async def test_einordnen_schlichter_buecher(client, test_db, einordnen):
    krimi = await buch_erstellen(test_db, hash="e1", title="Mord im Pfarrhaus", author="Agatha", isbn="", year=1930)
    akte = await buch_erstellen(test_db, hash="e2", title="Bedienungsanleitung Waschmaschine", isbn="")
    bunt = await buch_erstellen(test_db, hash="e3", title="Bunter Roman")
    von_hand = await buch_erstellen(test_db, hash="e4", title="Mein Heft")
    frueher = await buch_erstellen(test_db, hash="e5", title="Altes Heft")
    for b in (krimi, akte, von_hand, frueher):
        await setzen(test_db, b, umschlag_schlicht=1)
    await setzen(test_db, bunt, umschlag_schlicht=0)
    await setzen(test_db, von_hand, typ="heft", einordnung="hand")
    await setzen(test_db, frueher, typ="heft")                         # vor BF-59 von Hand gesetzt, einordnung noch leer
    save_fulltext("e1", "Kapitel 1\fDie Leiche lag im Arbeitszimmer des Pfarrers. " + "Wort " * 1000)
    einordnen.sagt({"Mord im Pfarrhaus": {"art": "buch", "gattung": "krimi"},
                    "Bedienungsanleitung Waschmaschine": {"art": "dokument", "gattung": "krimi"}})     # Gattung nur bei Büchern

    assert await einordner.runde() == 2
    z = {b: await zeile(test_db, b) for b in (krimi, akte, bunt, von_hand, frueher)}
    assert (z[krimi]["typ"], z[krimi]["gattung"], z[krimi]["einordnung"]) == ("", "krimi", "ki")
    assert (z[akte]["typ"], z[akte]["gattung"], z[akte]["einordnung"]) == ("dokument", "", "ki")
    assert (z[bunt]["einordnung"], z[von_hand]["typ"], z[von_hand]["einordnung"]) == ("", "heft", "hand")   # nicht angefasst
    assert (z[frueher]["typ"], z[frueher]["einordnung"]) == ("heft", "")
    assert all(x["manuell_bearbeitet"] == 0 for x in z.values())

    chats = einordnen.chats()
    assert len(chats) == 2
    anfrage = chats[0]
    koerper = json.loads(anfrage.content)
    nutzer = koerper["messages"][1]["content"]
    assert "Titel: Mord im Pfarrhaus" in nutzer and "Autor: Agatha" in nutzer and "Jahr: 1930" in nutzer and "Format: pdf" in nutzer
    assert "Kapitel 1 Die Leiche lag im Arbeitszimmer" in nutzer and len(nutzer) < 1800           # nur der Anfang des Volltexts
    schema = koerper["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["art"]["enum"] == ["buch", "dokument", "heft", "katalog", "broschuere"]
    assert schema["properties"]["gattung"]["enum"][:2] == ["", "krimi"]
    assert anfrage.headers["X-Leitstelle-Prioritaet"] == "hintergrund"
    assert anfrage.headers["X-Leitstelle-Arbeit"].startswith("bf-einordnen-")

    assert await einordner.runde() == 0 and len(einordnen.chats()) == 2                           # nichts mehr offen
    s = (await client.get("/api/einordnung/stand")).json()
    assert s == {"an": True, "bereit": True, "laeuft": False, "angehalten": False, "grund": "", "offen": 0, "erledigt": 2}


async def test_fehler_der_ki_ueberspringt_das_buch(client, test_db, einordnen):
    erstes = await buch_erstellen(test_db, hash="f1", title="Erstes")
    zweites = await buch_erstellen(test_db, hash="f2", title="Zweites")
    for b in (erstes, zweites):
        await setzen(test_db, b, umschlag_schlicht=1)
    einordnen.sagt({"Erstes": "Das weiß ich nicht.", "Zweites": {"art": "buch", "gattung": "roman"}})

    assert await einordner.runde() == 1 and not einordner.angehalten
    assert (await zeile(test_db, erstes))["einordnung"] == "" and (await zeile(test_db, zweites))["gattung"] == "roman"
    s = (await client.get("/api/einordnung/stand")).json()
    assert s["offen"] == 1 and s["erledigt"] == 1 and "kein JSON" in s["grund"]
    einordnen.sagt({"Erstes": {"art": "katalog", "gattung": ""}})                                   # später: erneut
    assert await einordner.runde() == 1 and (await zeile(test_db, erstes))["typ"] == "katalog"
    assert einordner.grund == ""


async def test_von_hand_gewinnt_auch_waehrend_die_ki_denkt(test_db, einordnen):
    buch = await buch_erstellen(test_db, hash="h1", title="Umstritten")
    await setzen(test_db, buch, umschlag_schlicht=1)

    async def inzwischen_von_hand():
        await setzen(test_db, buch, typ="heft", einordnung="hand")
        return {"art": "buch", "gattung": "thriller"}

    einordnen.sagt({"Umstritten": inzwischen_von_hand})
    assert await einordner.runde() == 0
    z = await zeile(test_db, buch)
    assert (z["typ"], z["gattung"], z["einordnung"]) == ("heft", "", "hand")


async def test_ablehnung_haelt_an_bis_fortgesetzt(client, test_db, einordnen):
    for i in range(2):
        await setzen(test_db, await buch_erstellen(test_db, hash=f"x{i}", title=f"Buch {i}"), umschlag_schlicht=1)
    abgelehnt = httpx.Response(403, json={"error": {"code": "faehigkeit_nicht_erlaubt", "message": "Fähigkeit text fehlt"}})
    einordnen.sagt({"Buch 0": abgelehnt, "Buch 1": abgelehnt})

    assert await einordner.runde() == 0 and len(einordnen.chats()) == 1                           # nie in einer Schleife
    s = (await client.get("/api/einordnung/stand")).json()
    assert s["angehalten"] and "Fähigkeit text fehlt" in s["grund"] and s["offen"] == 2
    assert await einordner.runde() == 0 and len(einordnen.chats()) == 1
    einordnen.sagt({"Buch 0": {"art": "heft", "gattung": ""}, "Buch 1": {"art": "heft", "gattung": ""}})
    s = (await client.post("/api/einordnung/fortsetzen")).json()
    assert not s["angehalten"] and s["grund"] == ""
    assert await einordner.runde() == 2


async def test_abgeschaltet_oder_ohne_leitstelle_fragt_niemand(client, test_db, einordnen, monkeypatch):
    await setzen(test_db, await buch_erstellen(test_db, hash="o1", title="Offen"), umschlag_schlicht=1)
    monkeypatch.setattr(settings, "einordnen_an", False)
    assert await einordner.runde() == 0
    s = (await client.get("/api/einordnung/stand")).json()
    assert (s["an"], s["bereit"], s["offen"]) == (False, False, 1)
    monkeypatch.setattr(settings, "einordnen_an", True)
    monkeypatch.setattr(settings, "leitstelle_adresse", "")
    assert await einordner.runde() == 0 and not (await client.get("/api/einordnung/stand")).json()["bereit"]
    assert einordnen.chats() == []
