"""Art und Gattung aller Werke (BF-59, BF-77): erst feste Regeln, dann die lokale KI gebündelt gegen eine Attrappe der
Leitstelle; von Hand gewinnt, Ablehnung hält an. Dazu Bücher und Besonderes in Zählern und Bücherliste. Alle Werke sind
erfunden."""

import json
import re
from urllib.parse import unquote

import httpx
import pytest

from backend.app.core.config import settings
from backend.app.services.einordnung import einordner
from backend.app.services.storage import save_fulltext
from tests.api.conftest import buch_erstellen, sammlung_erstellen
from tests.api.test_ausfuehren import chat_antwort, leitstelle  # noqa: F401 - Attrappe der Leitstelle

ZEILE = re.compile(r"^(\d+)\. Titel: (.*?) \|", re.M)


@pytest.fixture
def orte(tmp_path, monkeypatch):
    for ort in ("storage_dir", "umschlaege_dir"):
        monkeypatch.setattr(settings, ort, tmp_path / ort)


@pytest.fixture
def ki_sagt(orte, leitstelle, monkeypatch):  # noqa: F811
    """Das Einordnen ohne Pausen; `werke` legt je Titel fest, was die KI sagt ({art, gattung}); `sonst` ersetzt die ganze
    Antwort (Text, Daten, httpx.Response oder eine Funktion, die eins davon liefert)."""
    monkeypatch.setattr(settings, "einordnen_abstand_s", 0)
    monkeypatch.setattr(settings, "einordnen_an", True)
    einordner.angehalten, einordner.grund = False, ""
    modelle = leitstelle.antwort
    leitstelle.werke, leitstelle.sonst = {}, None

    async def antwort(r: httpx.Request) -> httpx.Response:
        if r.url.path == "/v1/models":
            return modelle(r)
        a = leitstelle.sonst
        if callable(a):
            a = await a()
        if a is None:
            text = json.loads(r.content)["messages"][1]["content"]
            a = {"werke": [{"nummer": int(n), **leitstelle.werke.get(t, {"art": "unbekannt", "gattung": ""})} for n, t in ZEILE.findall(text)]}
        return a if isinstance(a, httpx.Response) else chat_antwort(a if isinstance(a, str) else json.dumps(a))

    leitstelle.antwort = antwort
    leitstelle.chats = lambda: [r for r in leitstelle.anfragen if r.url.path == "/v1/chat/completions"]
    yield leitstelle
    einordner.angehalten, einordner.grund = False, ""


async def werk(test_db, hash_: str, titel: str, **spalten) -> int:
    angaben = {k: spalten.pop(k) for k in ("isbn", "page_count", "file_name", "author", "publisher") if k in spalten}
    b = await buch_erstellen(test_db, hash=hash_, title=titel, **{"isbn": "", "page_count": 0, **angaben})
    if spalten:
        await test_db.execute(f"UPDATE books SET {', '.join(f'{k} = ?' for k in spalten)} WHERE id = ?", (*spalten.values(), b))
        await test_db.commit()
    return b


async def zeile(test_db, b: int) -> tuple:
    z = await test_db.fetch_one("SELECT typ, gattung, einordnung, einordnung_grund FROM books WHERE id = ?", (b,))
    return z["typ"], z["gattung"], z["einordnung"], z["einordnung_grund"]


def frage(r: httpx.Request) -> str:
    return unquote(r.headers["X-Leitstelle-Titel"]).split(": ", 1)[1]


# -- Regeln und KI ----------------------------------------------------------------------------------------------------------

async def test_erst_regeln_dann_die_ki_gebuendelt(client, test_db, ki_sagt, monkeypatch):
    monkeypatch.setattr(settings, "einordnen_je_anfrage", 2)
    buch = await werk(test_db, "r1", "Gärten im Wandel", isbn="9783000000001", page_count=230, umschlag_schlicht=0)
    protokoll = await werk(test_db, "r2", "Microsoft Word - Protokoll", page_count=12)
    zettel = await werk(test_db, "r3", "Einladung", page_count=1, umschlag_schlicht=1)
    krimi = await werk(test_db, "k1", "Mord im Pfarrhaus", author="Erna Beispiel", page_count=180, umschlag_schlicht=1, file_name="pfarrhaus.epub")
    roman = await werk(test_db, "k2", "Sommer am Deich", isbn="9783000000002", page_count=320, umschlag_schlicht=1)
    bunt = await werk(test_db, "k3", "Bunte Tage", page_count=200, umschlag_schlicht=0, gattung="roman")
    akte = await werk(test_db, "k4", "Akte Wasserwerk", page_count=30, umschlag_schlicht=0)
    raetsel = await werk(test_db, "k5", "Rätselhaft", page_count=50, umschlag_schlicht=0)
    ungeprueft = await werk(test_db, "k6", "Noch ohne Befund", page_count=90)            # wartet auf die Umschlagprüfung
    von_hand = await werk(test_db, "h1", "Mein Heft", typ="heft", einordnung="hand")
    frueher = await werk(test_db, "h2", "Altes Heft", typ="heft")                       # vor BF-59 von Hand gesetzt
    save_fulltext("k1", "Kapitel 1\fDie Leiche lag im Arbeitszimmer des Pfarrers. " + "Wort " * 1000)
    ki_sagt.werke = {"Mord im Pfarrhaus": {"art": "buch", "gattung": "krimi"},
                     "Sommer am Deich": {"art": "buch", "gattung": "liebesroman"},
                     "Bunte Tage": {"art": "buch", "gattung": "thriller"},            # nicht gefragt: die Gattung bleibt
                     "Akte Wasserwerk": {"art": "dokument", "gattung": "krimi"}}     # nur Bücher haben eine Gattung

    assert await einordner.runde() == 7
    assert await zeile(test_db, buch) == ("", "", "regel", "ISBN und 230 Seiten")
    assert await zeile(test_db, protokoll) == ("dokument", "", "regel", "Der Titel stammt aus einem Schreibprogramm")
    assert await zeile(test_db, zettel) == ("dokument", "", "regel", "1 Seite und keine ISBN")
    assert await zeile(test_db, krimi) == ("", "krimi", "ki", "")
    assert await zeile(test_db, roman) == ("", "liebesroman", "ki", "")                # schlicht: die Regel überlässt es der KI
    assert await zeile(test_db, bunt) == ("", "roman", "ki", "")
    assert await zeile(test_db, akte) == ("dokument", "", "ki", "")
    assert (await zeile(test_db, raetsel))[2] == ""                                    # unbrauchbar gesagt: bleibt offen
    assert await zeile(test_db, von_hand) == ("heft", "", "hand", "")
    assert await zeile(test_db, frueher) == ("heft", "", "", "")
    assert (await zeile(test_db, ungeprueft))[2] == "" and "Noch ohne Befund" not in str([r.content for r in ki_sagt.chats()])

    chats = ki_sagt.chats()
    assert len(chats) == 3                                                              # fünf Werke zu je zwei
    koerper = json.loads(chats[0].content)
    nutzer = koerper["messages"][1]["content"]
    assert "1. Titel: Mord im Pfarrhaus | Autor: Erna Beispiel | Verlag: Testverlag | Seiten: 180 | ISBN: nein | Datei: pfarrhaus.epub | Gattung gefragt" in nutzer
    assert "Anfang: Kapitel 1 Die Leiche lag im Arbeitszimmer" in nutzer and nutzer.count("Wort") < 80
    werke = koerper["response_format"]["json_schema"]["schema"]["properties"]["werke"]
    assert (werke["minItems"], werke["maxItems"]) == (2, 2)
    assert werke["items"]["properties"]["art"]["enum"] == ["buch", "dokument", "heft", "katalog", "broschuere"]
    bunt_anfrage = next(json.loads(r.content)["messages"][1]["content"] for r in chats if "Bunte Tage" in r.content.decode())
    assert "Titel: Bunte Tage" in bunt_anfrage and "Bunte Tage | Autor: Testautor | Verlag: Testverlag | Seiten: 200 | ISBN: nein | Datei: testbuch.pdf\n" in bunt_anfrage
    assert chats[0].headers["X-Leitstelle-Prioritaet"] == "hintergrund"
    assert chats[0].headers["X-Leitstelle-Arbeit"].startswith("bf-einordnen-")
    assert frage(chats[0]) == "Art und Gattung: 2 Werke ab Mord im Pfarrhaus"

    s = (await client.get("/api/einordnung/stand")).json()
    assert {k: s[k] for k in ("gesamt", "nach_regel", "durch_ki", "offen", "erledigt", "angehalten")} == {
        "gesamt": 11, "nach_regel": 3, "durch_ki": 4, "offen": 2, "erledigt": 4, "angehalten": False}
    assert "Zu 1 von" in s["grund"]
    b = (await client.get(f"/api/books/{buch}")).json()
    assert (b["einordnung"], b["einordnung_grund"]) == ("regel", "ISBN und 230 Seiten")

    ki_sagt.werke["Rätselhaft"] = {"art": "katalog", "gattung": ""}                      # später: erneut
    assert await einordner.runde() == 1 and (await zeile(test_db, raetsel))[:3] == ("katalog", "", "ki")
    await test_db.execute("UPDATE books SET umschlag_schlicht = 0 WHERE id = ?", (ungeprueft,))       # nun geprüft
    await test_db.commit()
    ki_sagt.werke["Noch ohne Befund"] = {"art": "buch", "gattung": "krimi"}
    assert await einordner.runde() == 1 and await zeile(test_db, ungeprueft) == ("", "", "ki", "")    # Gattung nicht gefragt
    assert await einordner.runde() == 0 and len(ki_sagt.chats()) == 5                    # nichts mehr offen


async def test_ohne_leitstelle_nur_die_regeln(client, test_db, orte, monkeypatch):
    monkeypatch.setattr(settings, "leitstelle_adresse", "")
    monkeypatch.setattr(settings, "einordnen_an", True)
    beleg = await werk(test_db, "o1", "Beleg Tankstelle")
    offen = await werk(test_db, "o2", "Irgendein Werk", page_count=90)
    assert await einordner.runde() == 1
    assert (await zeile(test_db, beleg))[:3] == ("dokument", "", "regel") and (await zeile(test_db, offen))[2] == ""
    s = (await client.get("/api/einordnung/stand")).json()
    assert (s["bereit"], s["nach_regel"], s["offen"]) == (False, 1, 1)


async def test_abgeschaltet_ordnet_niemand_ein(client, test_db, ki_sagt, monkeypatch):
    b = await werk(test_db, "a1", "Rechnung Juni")
    monkeypatch.setattr(settings, "einordnen_an", False)
    assert await einordner.runde() == 0 and (await zeile(test_db, b))[2] == ""
    s = (await client.get("/api/einordnung/stand")).json()
    assert (s["an"], s["bereit"], s["offen"]) == (False, False, 1)
    assert ki_sagt.chats() == []


async def test_unbrauchbare_antwort_laesst_offen(client, test_db, ki_sagt):
    b = await werk(test_db, "u1", "Erstes", page_count=100, umschlag_schlicht=0)
    ki_sagt.sonst = "Das weiß ich nicht."
    assert await einordner.runde() == 0 and not einordner.angehalten
    assert "kein JSON" in (await client.get("/api/einordnung/stand")).json()["grund"]
    ki_sagt.sonst = {"werke": "alle"}
    assert await einordner.runde() == 0 and "verlangten Form" in einordner.grund
    ki_sagt.sonst = None
    ki_sagt.werke = {"Erstes": {"art": "broschuere", "gattung": ""}}
    assert await einordner.runde() == 1 and (await zeile(test_db, b))[0] == "broschuere"


async def test_von_hand_gewinnt_auch_waehrend_die_ki_denkt(test_db, ki_sagt):
    b = await werk(test_db, "v1", "Umstritten", page_count=100, umschlag_schlicht=1)

    async def inzwischen_von_hand():
        await test_db.execute("UPDATE books SET typ = 'heft', einordnung = 'hand' WHERE id = ?", (b,))
        await test_db.commit()
        return {"werke": [{"nummer": 1, "art": "buch", "gattung": "thriller"}]}

    ki_sagt.sonst = inzwischen_von_hand
    assert await einordner.runde() == 0
    assert await zeile(test_db, b) == ("heft", "", "hand", "")


async def test_ablehnung_haelt_an_bis_fortgesetzt(client, test_db, ki_sagt, monkeypatch):
    monkeypatch.setattr(settings, "einordnen_je_anfrage", 1)
    for i in range(2):
        await werk(test_db, f"x{i}", f"Werk {i}", page_count=100, umschlag_schlicht=0)
    ki_sagt.sonst = httpx.Response(403, json={"error": {"code": "faehigkeit_nicht_erlaubt", "message": "Fähigkeit text fehlt"}})

    assert await einordner.runde() == 0 and len(ki_sagt.chats()) == 1                     # nie in einer Schleife
    s = (await client.get("/api/einordnung/stand")).json()
    assert s["angehalten"] and "Fähigkeit text fehlt" in s["grund"] and s["offen"] == 2
    assert await einordner.runde() == 0 and len(ki_sagt.chats()) == 1
    ki_sagt.sonst = None
    ki_sagt.werke = {"Werk 0": {"art": "heft", "gattung": ""}, "Werk 1": {"art": "heft", "gattung": ""}}
    s = (await client.post("/api/einordnung/fortsetzen")).json()
    assert not s["angehalten"] and s["grund"] == ""
    assert await einordner.runde() == 2


async def test_von_hand_leert_den_grund_der_regel(client, test_db, orte, monkeypatch):
    monkeypatch.setattr(settings, "leitstelle_adresse", "")
    b = await werk(test_db, "g1", "Datenblatt Lüfter")
    await einordner.runde()
    r = await client.patch(f"/api/books/{b}", json={"typ": "katalog"})
    assert (r.json()["einordnung"], r.json()["einordnung_grund"], r.json()["typ"]) == ("hand", "", "katalog")


# -- Bücher und Besonderes --------------------------------------------------------------------------------------------------

async def test_zaehler_und_buecherliste_nach_art(client, test_db):
    reihe = await sammlung_erstellen(test_db, name="Deichgeschichten")
    buecher = [await werk(test_db, f"b{i}", f"Deich {i}", sammlung_id=reihe, band_nummer=str(i)) for i in (1, 2)]
    einzeln = await werk(test_db, "b3", "Marschland")
    besonderes = [await werk(test_db, "d1", "Protokoll", typ="dokument"), await werk(test_db, "d2", "Vereinsheft", typ="heft")]

    s = (await client.get("/api/config/stats")).json()
    assert (s["buecher"], s["besonderes"], s["buecher_gesamt"]) == (3, 2, 5)
    assert "buecher_mit_isbn" in s and "dokumente" in s                                 # bleiben vorerst

    r = (await client.get("/api/books", params={"art": "buch", "pro_seite": 100})).json()
    assert {b["id"] for b in r["buecher"]} == {*buecher, einzeln}
    r = (await client.get("/api/books", params={"art": "besonderes", "pro_seite": 100})).json()
    assert {b["id"] for b in r["buecher"]} == set(besonderes)
    assert (await client.put("/api/collections/einstellungen", json={"als_eintrag_ab": 2})).status_code == 200
    r = (await client.get("/api/books", params={"art": "buch", "zusammenfassen": "true", "pro_seite": 100})).json()
    assert [(e["art"], e.get("sammlung", {}).get("anzahl")) for e in r["eintraege"]] == [("sammlung", 2), ("buch", None)]
    assert (r["gesamt"], r["gesamt_eintraege"]) == (3, 2)
    assert (await client.get("/api/books", params={"art": "dokument"})).status_code == 422
