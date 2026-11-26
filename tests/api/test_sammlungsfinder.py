"""Sammlungen finden (BF-66): ein ganzer Lauf ohne KI und mit einer Attrappe der Leitstelle, die Vorschläge, Anlegen und
Verwerfen. Titel, Autoren und Reihen sind erfunden."""

import json
from urllib.parse import unquote

import httpx
import pytest

from backend.app.core.config import settings
from backend.app.services.sammlungsfinder import UNBRAUCHBAR, sammlungsfinder
from tests.api.conftest import sammlung_erstellen
from tests.api.test_ausfuehren import LEITSTELLE, chat_antwort, leitstelle  # noqa: F401 - Attrappe der Leitstelle
from tests.api.test_sammlungen_liste import buch

OHNE_KI = "Die KI hat nicht geprüft: Keine Leitstelle eingetragen"


def frage(r: httpx.Request) -> str:
    """Was die App die KI fragt, ohne den Namen der App: etwa "Reihe prüfen: Mondgarten"."""
    return unquote(r.headers["X-Leitstelle-Titel"]).split(": ", 1)[1]


@pytest.fixture
def ohne_ki(monkeypatch):
    monkeypatch.setattr(settings, "leitstelle_adresse", "")


@pytest.fixture
def ki_sagt(leitstelle, monkeypatch):  # noqa: F811
    """Die Leitstelle ohne Pausen; `sagt` legt fest, was die KI auf eine Frage antwortet (Daten, Text oder Antwort)."""
    monkeypatch.setattr(settings, "sammlungen_finden_abstand_s", 0)
    modelle, antworten = leitstelle.antwort, {}

    def antwort(r: httpx.Request) -> httpx.Response:
        if r.url.path == "/v1/models":
            return modelle(r)
        a = antworten[frage(r)]
        return a if isinstance(a, httpx.Response) else chat_antwort(a if isinstance(a, str) else json.dumps(a))

    leitstelle.antwort = antwort
    leitstelle.sagt = antworten.update
    leitstelle.chats = lambda: [r for r in leitstelle.anfragen if r.url.path == "/v1/chat/completions"]
    return leitstelle


async def reihe(test_db, name: str, autor: str, baende: range, **spalten) -> list[int]:
    return [await buch(test_db, f"{name} {b} - Teilstück {b}", autor=autor, **spalten) for b in baende]


async def vorschlaege(client) -> list[dict]:
    r = await client.get("/api/collections/vorschlaege")
    assert r.status_code == 200, r.text
    return r.json()


# -- Lauf ohne KI -----------------------------------------------------------------------------------------------------------

async def test_ohne_ki_bleiben_die_regelfunde(client, test_db, ohne_ki):
    alt = await sammlung_erstellen(test_db, name="Schon geordnet")
    sterne = await reihe(test_db, "Sternenfahrer", "Erna Beispiel", range(1, 4))
    await reihe(test_db, "Sternenfahrer", "Erna Beispiel", range(4, 5), sammlung=alt, band="4")     # zählt nicht
    await reihe(test_db, "Mondgarten", "Otto Muster", range(1, 3))
    await reihe(test_db, "Mondgarten", "Otto Muster", range(3, 4), sammlung=alt, band="3")          # nur zwei frei: zu wenig
    await buch(test_db, "Ganz für sich", file_name="Beispiel, Erna - Wolkenstadt 1 - Anfang.epub")

    assert await sammlungsfinder.suchen() == 1
    [v] = await vorschlaege(client)
    assert {k: v[k] for k in ("name", "autor", "anzahl", "wege", "ki", "ki_geprueft")} == {
        "name": "Sternenfahrer", "autor": "Erna Beispiel", "anzahl": 3, "wege": ["Reihe und Band im Titel bei 3 Büchern"],
        "ki": OHNE_KI, "ki_geprueft": False}
    assert [(b["id"], b["band"], b["title"]) for b in v["buecher"]] == [
        (sterne[0], "1", "Sternenfahrer 1 - Teilstück 1"), (sterne[1], "2", "Sternenfahrer 2 - Teilstück 2"),
        (sterne[2], "3", "Sternenfahrer 3 - Teilstück 3")]
    assert v["buecher"][0]["sammlung"] is None and "cover_stand" in v["buecher"][0]
    s = (await client.get("/api/collections/vorschlaege/stand")).json()
    assert s == {"laeuft": False, "schritt": "", "gefunden": 1, "grund": OHNE_KI}


async def test_suchen_laeuft_im_hintergrund(client, test_db, ohne_ki):
    await reihe(test_db, "Sternenfahrer", "Erna Beispiel", range(1, 4))
    s = (await client.post("/api/collections/vorschlaege/suchen")).json()
    assert s["laeuft"] is True
    await sammlungsfinder.warten()
    assert (await client.get("/api/collections/vorschlaege/stand")).json() == {"laeuft": False, "schritt": "", "gefunden": 1,
                                                                               "grund": OHNE_KI}


# -- Lauf mit KI ------------------------------------------------------------------------------------------------------------

async def test_ki_fuehrt_zusammen_bestaetigt_und_lehnt_ab(client, test_db, ki_sagt):
    kurz = [await buch(test_db, f"Sternenf. {b} - Teilstück {b}", autor="Erna Beispiel") for b in (1, 2)]
    lang = await reihe(test_db, "Sternenfahrer", "Beispiel, Erna", range(3, 5))
    await reihe(test_db, "Mondgarten", "Otto Muster", range(1, 4))
    ki_sagt.sagt({"Reihen vergleichen: Erna Beispiel": {"reihen": [{"nummern": [1, 2], "name": "Die Sternenfahrer"}]},
                  "Reihe prüfen: Die Sternenfahrer": {"reihe": True, "name": "Die Sternenfahrer", "satz": "Vier Bände einer Weltraumreihe."},
                  "Reihe prüfen: Mondgarten": {"reihe": False, "name": "", "satz": "Das sind drei getrennte Gartenbücher."}})

    assert await sammlungsfinder.suchen() == 1
    [v] = await vorschlaege(client)
    assert (v["name"], v["autor"], v["anzahl"], v["ki"], v["ki_geprueft"]) == (
        "Die Sternenfahrer", "Erna Beispiel", 4, "Vier Bände einer Weltraumreihe.", True)
    assert [(b["id"], b["band"]) for b in v["buecher"]] == list(zip(kurz + lang, ["1", "2", "3", "4"], strict=True))
    assert v["wege"] == ["Reihe und Band im Titel bei 4 Büchern", "Name der Reihe in 2 Schreibweisen", "Autor in 2 Schreibweisen",
                         "Die KI führt Sternenf und Sternenfahrer zusammen", "Die KI nennt die Reihe Die Sternenfahrer"]

    chats = ki_sagt.chats()
    assert sorted(map(frage, chats)) == ["Reihe prüfen: Die Sternenfahrer", "Reihe prüfen: Mondgarten", "Reihen vergleichen: Erna Beispiel"]
    vergleich = next(r for r in chats if frage(r) == "Reihen vergleichen: Erna Beispiel")
    koerper = json.loads(vergleich.content)
    nutzer = koerper["messages"][1]["content"]
    assert "1. Sternenf (Band 1: Sternenf. 1 - Teilstück 1; Band 2: Sternenf. 2 - Teilstück 2)" in nutzer
    assert "2. Sternenfahrer (Band 3: Sternenfahrer 3 - Teilstück 3; Band 4: Sternenfahrer 4 - Teilstück 4)" in nutzer
    assert koerper["response_format"]["json_schema"]["name"] == "reihen_gleich"
    assert vergleich.headers["X-Leitstelle-Prioritaet"] == "hintergrund"
    assert vergleich.headers["X-Leitstelle-Arbeit"].startswith("bf-sammlungen-")
    assert (await client.get("/api/collections/vorschlaege/stand")).json()["grund"] == ""


async def test_unbrauchbare_antwort_laesst_die_regelfunde(client, test_db, ki_sagt):
    for b in (1, 2):
        await buch(test_db, f"Sternenf. {b} - Teilstück {b}", autor="Erna Beispiel")
    await reihe(test_db, "Sternenfahrer", "Erna Beispiel", range(3, 5))
    await reihe(test_db, "Mondgarten", "Otto Muster", range(1, 4))
    ki_sagt.sagt({"Reihen vergleichen: Erna Beispiel": "Das weiß ich nicht.",
                  "Reihe prüfen: Mondgarten": {"reihe": "ja", "name": "Mondgarten", "satz": "Sieht gut aus, finde ich."}})

    assert await sammlungsfinder.suchen() == 1                                    # nicht zusammengeführt: je zwei, zu wenig
    [v] = await vorschlaege(client)
    assert (v["name"], v["anzahl"], v["ki"], v["ki_geprueft"]) == ("Mondgarten", 3, UNBRAUCHBAR, False)
    assert len(ki_sagt.chats()) == 2
    assert (await client.get("/api/collections/vorschlaege/stand")).json()["grund"] == ""      # es ging weiter


async def test_ablehnung_der_leitstelle_fragt_nicht_weiter(client, test_db, ki_sagt):
    await reihe(test_db, "Mondgarten", "Otto Muster", range(1, 4))
    await reihe(test_db, "Wolkenstadt", "Berta Probe", range(1, 4))
    abgelehnt = httpx.Response(403, json={"error": {"code": "faehigkeit_nicht_erlaubt", "message": "Fähigkeit text fehlt"}})
    ki_sagt.sagt({"Reihe prüfen: Mondgarten": abgelehnt, "Reihe prüfen: Wolkenstadt": abgelehnt})

    assert await sammlungsfinder.suchen() == 2
    assert len(ki_sagt.chats()) == 1                                              # nie in einer Schleife
    grund = (await client.get("/api/collections/vorschlaege/stand")).json()["grund"]
    assert grund.startswith("Die KI hat nicht geprüft: ") and "Fähigkeit text fehlt" in grund
    assert {v["ki"] for v in await vorschlaege(client)} == {grund}


# -- Anlegen und Verwerfen --------------------------------------------------------------------------------------------------

async def test_anlegen_wie_vorgeschlagen(client, test_db, ohne_ki):
    sterne = await reihe(test_db, "Sternenfahrer", "Erna Beispiel", range(1, 4))
    await sammlungsfinder.suchen()
    [v] = await vorschlaege(client)

    r = await client.post(f"/api/collections/vorschlaege/{v['id']}/anlegen")
    assert r.status_code == 200, r.text
    neu = r.json()
    assert neu["name"] == "Sternenfahrer" and neu["color"] == "#2563eb"
    assert [(b["id"], b["band_nummer"]) for b in neu["books"]] == list(zip(sterne, ["1", "2", "3"], strict=True))
    z = await test_db.fetch_one("SELECT stand, sammlung_id FROM sammlung_vorschlag WHERE id = ?", (v["id"],))
    assert (z["stand"], z["sammlung_id"]) == ("angelegt", neu["id"])
    assert await vorschlaege(client) == []

    for weg in ("anlegen", "verwerfen"):
        r = await client.post(f"/api/collections/vorschlaege/{v['id']}/{weg}")
        assert r.status_code == 409 and r.json()["detail"] == "Der Vorschlag ist schon angelegt"
    assert (await client.post("/api/collections/vorschlaege/99999/anlegen")).status_code == 404

    await reihe(test_db, "Sternenfahrer", "Erna Beispiel", range(4, 7))           # später dazugekommen: kein neuer Vorschlag
    assert await sammlungsfinder.suchen() == 0


async def test_anlegen_angepasst(client, test_db, ohne_ki):
    sterne = await reihe(test_db, "Sternenfahrer", "Erna Beispiel", range(1, 5))
    fremd = await buch(test_db, "Fremd")
    await sammlungsfinder.suchen()
    [v] = await vorschlaege(client)
    weg = f"/api/collections/vorschlaege/{v['id']}/anlegen"

    r = await client.post(weg, json={"book_ids": [sterne[0], fremd]})
    assert r.status_code == 400
    assert r.json()["detail"] == f"Das Buch {fremd} gehört nicht zu diesem Vorschlag oder schon zu einer Sammlung"
    r = await client.post(weg, json={"book_ids": []})
    assert r.status_code == 400 and r.json()["detail"] == "Für die Sammlung ist kein Buch gewählt"
    assert (await client.post(weg, json={"name": "   "})).status_code == 422

    r = await client.post(weg, json={"name": "Meine Sternenfahrer", "book_ids": [sterne[2], sterne[0]]})
    neu = r.json()
    assert neu["name"] == "Meine Sternenfahrer"
    assert [(b["id"], b["band_nummer"]) for b in neu["books"]] == [(sterne[0], "1"), (sterne[2], "3")]       # Band wie erkannt
    frei = await test_db.fetch_all("SELECT id FROM books WHERE sammlung_id IS NULL ORDER BY id")
    assert [z["id"] for z in frei] == [sterne[1], sterne[3], fremd]


async def test_verworfenes_kommt_nicht_wieder(client, test_db, ohne_ki):
    await reihe(test_db, "Sternenfahrer", "Erna Beispiel", range(1, 4))
    mond = await reihe(test_db, "Mondgarten", "Otto Muster", range(1, 4))
    assert await sammlungsfinder.suchen() == 2
    sterne_v, mond_v = sorted(await vorschlaege(client), key=lambda v: v["name"] != "Sternenfahrer")

    r = await client.post(f"/api/collections/vorschlaege/{sterne_v['id']}/verwerfen")
    assert r.status_code == 200 and r.json() == {"id": sterne_v["id"], "stand": "verworfen"}
    assert [v["name"] for v in await vorschlaege(client)] == ["Mondgarten"]

    garten = await sammlung_erstellen(test_db, name="Garten")                     # inzwischen von Hand geordnet
    await client.post("/api/books/bulk", json={"book_ids": mond, "aktion": "sammlung_zuweisen", "wert": garten})
    assert await vorschlaege(client) == []                                        # ohne freie Bücher nicht mehr gezeigt
    assert await sammlungsfinder.suchen() == 0                                    # und vom nächsten Lauf entfernt
    assert await test_db.fetch_one("SELECT id FROM sammlung_vorschlag WHERE id = ?", (mond_v["id"],)) is None
    z = await test_db.fetch_one("SELECT stand FROM sammlung_vorschlag WHERE id = ?", (sterne_v["id"],))
    assert z["stand"] == "verworfen"
    assert (await client.get("/api/collections/vorschlaege/stand")).json()["gefunden"] == 0
