"""Kinder (BF-78): keine KI auf keinem Weg, nur was die Stufe erlaubt, Lesezeit und Ruhezeit (Uhr gestellt), Einblick der
Eltern je Stufe, die Katze, ein Lesezeichen im Vorlesealter, und jedes Profil hat seine eigenen Daten. Alles erfunden."""

from __future__ import annotations

import re
from datetime import datetime

import pytest
from fastapi.routing import APIRoute

from backend.app.familie.lesezeit import uhr
from backend.app.main import app
from backend.app.familie.stufen import stufenbuch
from tests.api.familie_hilfen import anlegen, familie_anlegen, freigeben, waehlen


@pytest.fixture(autouse=True)
def uhr_zurueck():
    yield
    uhr.stellen(None)


def _braucht(route: APIRoute) -> set[str]:
    """Welche Fähigkeiten ein Weg verlangt, gelesen aus seinen Abhängigkeiten (core/auth.py, braucht)."""
    gefunden, offen = set(), [route.dependant]
    while offen:
        d = offen.pop()
        name = getattr(d.call, "__name__", "")
        if name.startswith("braucht_"):
            gefunden.add(name.removeprefix("braucht_"))
        offen += d.dependencies
    return gefunden


def _adresse(weg: str, buch: int) -> str:
    return re.sub(r"{(\w+)(?::\w+)?}", lambda m: {"sprache": "de", "kennung": "1.1", "pfad": "a", "chat": "c1", "zug": "z1"}.get(m.group(1), str(buch)), weg)


KI_WEGE = [(art, r.path) for r in app.routes if isinstance(r, APIRoute) and "ki" in _braucht(r) for art in sorted(r.methods)]


def test_alle_ki_wege_sind_erfasst():
    pfade = {p for _a, p in KI_WEGE}
    for weg in ("/api/ai/buch/{book_id}/kategorisieren", "/api/suche/bedeutung", "/api/gespraech", "/api/books/{buch_id}/fassungen/{sprache}",
                "/api/collections/vorschlaege/suchen", "/api/katalog/einordnen", "/api/einordnung/fortsetzen", "/api/ai/status"):
        assert weg in pfade


@pytest.mark.parametrize("kind", ["clara", "dora", "emil"])
async def test_keine_ki_fuer_kinder_auf_keinem_weg(client, test_db, kind):
    f = await familie_anlegen(client, test_db)
    for art, weg in KI_WEGE:
        r = await client.request(art, _adresse(weg, f.buch["mond"]), params={"q": "Mond"}, json={}, headers=f.kopf[kind])
        assert r.status_code == 403, f"{art} {weg}: {r.status_code}"


@pytest.mark.parametrize(("art", "weg", "daten"), [
    ("patch", "/api/books/{mond}", {"title": "Neu"}),
    ("delete", "/api/books/{mond}", None),
    ("post", "/api/annahme", {"name": "x.epub", "groesse": 1}),
    ("get", "/api/katalog", None),
    ("post", "/api/categories/{mond}/zuordnen", []),
    ("put", "/api/collections/einstellungen", {"als_eintrag_ab": 5}),
    ("post", "/api/backup/create", None),
    ("post", "/api/import/scan", None),
    ("get", "/api/config/paths", None),
    ("post", "/api/familie/profile", {"name": "Neu", "rolle": "kind", "stufe": "schule"}),
])
async def test_was_die_stufe_nicht_erlaubt(client, test_db, art, weg, daten):
    f = await familie_anlegen(client, test_db)
    adresse = weg.replace("{mond}", str(f.buch["mond"]))
    for kind in ("clara", "emil"):
        r = await client.request(art.upper(), adresse, json=daten, headers=f.kopf[kind])
        assert r.status_code == 403, f"{kind} {art} {weg}: {r.status_code}"


async def test_faehigkeiten_wachsen_mit_der_stufe(client, test_db):
    """Bis Lesen und Lernen keine Suche, keine Notizen, Markierungen und Lesezeichen; der Lesestand merkt sich von selbst.
    Lieblinge ab Lesen und Lernen, Suche, Notizen und Markierungen ab Schule."""
    f = await familie_anlegen(client, test_db)
    lena = (await anlegen(client, f.kopf["ada"], name="Lena", rolle="kind", stufe="lesen_lernen"))["id"]
    await freigeben(client, f.kopf["ada"], lena, "buch", [f.buch["mond"]])
    f.kopf["lena"] = await waehlen(client, lena)
    weg = f"/api/books/{f.buch['mond']}"
    klein = {"notiz": ("post", f"{weg}/notes", {"content": "Mein Gedanke"}), "markierung": ("post", f"{weg}/highlights", {"cfi_range": "epubcfi(/6/2)"}),
             "lesezeichen": ("post", f"{weg}/labels", {"position_percent": 10}), "suche": ("get", "/api/search?q=Mond", None),
             "im_buch_suchen": ("get", f"{weg}/volltext-suche?q=Mond", None), "schnellfilter": ("get", "/api/books?suche=Mond", None)}
    for kind in ("clara", "lena"):
        for was, (art, adresse, daten) in klein.items():
            r = await client.request(art.upper(), adresse, json=daten, headers=f.kopf[kind])
            assert r.status_code == 403, f"{kind}: {was} {r.status_code}"
        r = await client.patch(f"{weg}/leseposition", json={"position": "percent:20"}, headers=f.kopf[kind])
        assert r.status_code == 200                                                      # merkt sich von selbst
        assert (await client.put(f"{weg}/vorlesestelle", json={"einheit": 1, "zeichen": 0}, headers=f.kopf[kind])).status_code == 200
    assert (await client.patch(f"{weg}/favorit", headers=f.kopf["clara"])).status_code == 403
    assert (await client.patch(f"{weg}/favorit", headers=f.kopf["lena"])).status_code == 200        # Lieblinge ab Lesen und Lernen
    for was, (art, adresse, daten) in klein.items():
        r = await client.request(art.upper(), adresse, json=daten, headers=f.kopf["dora"])
        assert r.status_code == 200, f"dora: {was} {r.status_code}"                      # Schule
    assert (await client.patch(f"{weg}/zu-lesen", headers=f.kopf["dora"])).status_code == 403    # Lesesofa erst Jugend
    assert (await client.patch(f"{weg}/zu-lesen", headers=f.kopf["emil"])).status_code == 200
    ich = (await client.get("/api/familie/ich", headers=f.kopf["clara"])).json()
    assert ich["faehigkeiten"] == ["lesen", "vorlesen"] and ich["darstellung"]["woerter_je_zeile"] == 4
    assert (await client.get("/api/familie/ich", headers=f.kopf["lena"])).json()["faehigkeiten"] == ["favoriten", "gelesen", "lesen", "vorlesen"]
    for kind, status in (("clara", 403), ("lena", 200)):                                   # Rückblick Gelesen ab Lesen und Lernen
        assert (await client.get("/api/books", params={"gelesen": True}, headers=f.kopf[kind])).status_code == status
        assert (await client.patch(f"{weg}/gelesen", headers=f.kopf[kind])).status_code == status
    assert "ki" not in (await client.get("/api/familie/ich", headers=f.kopf["emil"])).json()["faehigkeiten"]


async def test_lesezeichen_mit_grenze_aus_den_stufen(client, test_db, monkeypatch):
    f = await familie_anlegen(client, test_db)
    weg = f"/api/books/{f.buch['mond']}/labels"
    assert (await client.post(weg, json={"name": "Lieblingsstelle"}, headers=f.kopf["dora"])).status_code == 403   # Etiketten erst Jugend
    monkeypatch.setattr(stufenbuch().stufe("schule"), "lesezeichen_je_buch", 1)       # die Grenze steht in stufen.json
    assert (await client.post(weg, json={"position_percent": 10}, headers=f.kopf["dora"])).status_code == 200
    r = await client.post(weg, json={"position_percent": 20}, headers=f.kopf["dora"])
    assert r.status_code == 409 and "1 Lesezeichen" in r.json()["detail"]
    for n in range(3):
        assert (await client.post(weg, json={"position_percent": n, "name": f"Stelle {n}"}, headers=f.kopf["emil"])).status_code == 200


async def test_jedes_profil_hat_seine_eigenen_daten(client, test_db):
    f = await familie_anlegen(client, test_db)
    weg = f"/api/books/{f.buch['mond']}"
    await client.patch(f"{weg}/favorit", headers=f.kopf["ada"])
    await client.patch(f"{weg}/leseposition", json={"position": "percent:50"}, headers=f.kopf["ada"])
    notiz = (await client.post(f"{weg}/notes", json={"content": "Adas Notiz"}, headers=f.kopf["ada"])).json()
    markierung = (await client.post(f"{weg}/highlights", json={"cfi_range": "epubcfi(/6/2)"}, headers=f.kopf["ada"])).json()
    await client.put(f"{weg}/vorlesestelle", json={"einheit": 3, "zeichen": 7}, headers=f.kopf["ada"])
    ada, bert = (await client.get(weg, headers=f.kopf["ada"])).json(), (await client.get(weg, headers=f.kopf["bert"])).json()
    assert (ada["is_favorite"], ada["reading_position"]) == (True, "percent:50")
    assert (bert["is_favorite"], bert["reading_position"]) == (False, "")
    assert (await client.get(f"{weg}/notes", headers=f.kopf["bert"])).json() == []
    assert (await client.get(f"{weg}/highlights", headers=f.kopf["bert"])).json() == []
    assert (await client.get(f"{weg}/vorlesestelle", headers=f.kopf["bert"])).json() is None
    assert (await client.patch(f"/api/notes/{notiz['id']}", json={"content": "fremd"}, headers=f.kopf["bert"])).status_code == 404
    assert (await client.delete(f"/api/highlights/{markierung['id']}", headers=f.kopf["bert"])).status_code == 404
    favoriten = (await client.get("/api/books", params={"favorit": True}, headers=f.kopf["bert"])).json()["gesamt"]
    assert favoriten == 0 and (await client.get("/api/books", params={"favorit": True}, headers=f.kopf["ada"])).json()["gesamt"] == 1


# -- Lesezeit -------------------------------------------------------------------------------------------------------------------

async def test_lesezeit_je_tag_nach_der_vorgabe(client, test_db):
    f = await familie_anlegen(client, test_db)
    uhr.stellen(datetime(2026, 11, 26, 10, 0))
    clara = f.kopf["clara"]
    stand = (await client.get("/api/familie/ich", headers=clara)).json()["lesezeit"]
    assert stand == {"an": True, "heute_s": 0, "grenze_s": 1800, "rest_s": 1800, "hinweis_ab_s": 1500, "ruht": False, "ruhe_bis": None}
    await client.post("/api/familie/lesezeit", json={"sekunden": 120}, headers=clara)
    stand = (await client.post("/api/familie/lesezeit", json={"sekunden": 60, "vorlesen": True}, headers=clara)).json()
    assert (stand["heute_s"], stand["rest_s"]) == (180, 1620)                            # Vorlesen zählt mit
    stand = (await client.post("/api/familie/lesezeit", json={"sekunden": 5000}, headers=clara)).json()
    assert stand["heute_s"] == 480                                                       # höchstens ein Takt (300 s) auf einmal
    uhr.stellen(datetime(2026, 11, 27, 10, 0))
    assert (await client.get("/api/familie/ich", headers=clara)).json()["lesezeit"]["heute_s"] == 0      # ein neuer Tag


async def test_ruhezeit_vor_dem_schlafen_und_ueber_mitternacht(client, test_db):
    f = await familie_anlegen(client, test_db)
    clara = f.kopf["clara"]
    for zeit, ruht in ((datetime(2026, 11, 26, 17, 59), False), (datetime(2026, 11, 26, 18, 0), True), (datetime(2026, 11, 27, 6, 0), True),
                       (datetime(2026, 11, 27, 6, 30), False)):
        uhr.stellen(zeit)
        stand = (await client.get("/api/familie/ich", headers=clara)).json()["lesezeit"]
        assert (stand["ruht"], stand["ruhe_bis"]) == (ruht, "06:30" if ruht else None), zeit


async def test_lesezeit_frei_aenderbar_oder_ganz_aus(client, test_db):
    f = await familie_anlegen(client, test_db)
    uhr.stellen(datetime(2026, 11, 26, 13, 0))
    weg = f"/api/familie/profile/{f.ids['clara']}"
    regel = {"an": True, "minuten": 10, "ruhe_an": True, "ruhe_von": "12:00", "ruhe_bis": "14:00", "vorlesen_zaehlt": False}
    assert (await client.patch(weg, json={"einstellungen": {"lesezeit": regel}}, headers=f.kopf["ada"])).status_code == 200
    stand = (await client.post("/api/familie/lesezeit", json={"sekunden": 60, "vorlesen": True}, headers=f.kopf["clara"])).json()
    assert (stand["heute_s"], stand["grenze_s"], stand["ruht"], stand["ruhe_bis"]) == (0, 600, True, "14:00")
    aus = regel | {"an": False, "ruhe_an": False}
    await client.patch(weg, json={"einstellungen": {"lesezeit": aus}}, headers=f.kopf["ada"])
    stand = (await client.get("/api/familie/ich", headers=f.kopf["clara"])).json()["lesezeit"]
    assert (stand["an"], stand["rest_s"], stand["ruht"]) == (False, None, False)
    assert (await client.patch(weg, json={"einstellungen": {"lesezeit": aus}}, headers=f.kopf["clara"])).status_code == 403   # nur Eltern


# -- Einblick -------------------------------------------------------------------------------------------------------------------

async def test_einblick_nach_stufe_und_fuer_das_kind_sichtbar(client, test_db):
    f = await familie_anlegen(client, test_db)
    for kind in ("clara", "dora", "emil"):
        await client.patch(f"/api/books/{f.buch['mond']}/leseposition", json={"position": "percent:40"}, headers=f.kopf[kind])
        await client.post("/api/familie/lesezeit", json={"sekunden": 90}, headers=f.kopf[kind])

    async def einblick(kind: str, wer: str = "ada") -> dict:
        r = await client.get(f"/api/familie/profile/{f.ids[kind]}/einblick", headers=f.kopf[wer])
        assert r.status_code == 200, r.text
        return r.json()

    clara = await einblick("clara")
    assert clara["sichtbar"] == ["titel", "lesezeit", "fortschritt"] and clara["lesezeit_heute_s"] == 90
    assert [(e["buch"]["title"], e["fortschritt"]) for e in clara["eintraege"]] == [("Mondfahrt mit Paula", 0.4)]
    dora = await einblick("dora", wer="bert")
    assert dora["sichtbar"] == ["titel", "grober_fortschritt"] and dora["lesezeit_heute_s"] is None
    assert dora["eintraege"][0]["fortschritt"] == 0.5                                     # grob: in Vierteln
    assert (await einblick("emil"))["eintraege"] == []                                   # ab 14 nur Geteiltes
    await client.put(f"/api/books/{f.buch['mond']}/geteilt", json={"geteilt": True}, headers=f.kopf["emil"])
    assert [e["buch"]["id"] for e in (await einblick("emil"))["eintraege"]] == [f.buch["mond"]]
    assert (await einblick("dora", wer="dora"))["sichtbar"] == ["titel", "grober_fortschritt"]   # das Kind sieht, was die Eltern sehen
    assert (await client.get(f"/api/familie/profile/{f.ids['dora']}/einblick", headers=f.kopf["emil"])).status_code == 403
    assert (await client.get("/api/familie/ich", headers=f.kopf["dora"])).json()["einblick"] == ["titel", "grober_fortschritt"]
    assert "notiz" not in str(clara).lower()


# -- Katze ----------------------------------------------------------------------------------------------------------------------

async def test_die_katze_bekommt_einen_namen(client, test_db):
    f = await familie_anlegen(client, test_db)
    r = await client.patch("/api/familie/ich/katze", json={"name": "Flocke"}, headers=f.kopf["clara"])
    assert r.status_code == 200 and r.json() == {"an": True, "name": "Flocke", "schnurren": False, "name_eingabe": "vorschlaege"}
    assert (await client.get("/api/familie/ich", headers=f.kopf["clara"])).json()["katze"]["name"] == "Flocke"
    assert (await client.get("/api/familie/ich", headers=f.kopf["dora"])).json()["katze"]["name"] == ""      # je Profil
    stufen = (await client.get("/api/familie/stufen")).json()
    assert "Samtpfote" in stufen["katze_vorschlaege"] and stufen["katze_nennung"] == "hallowelt42 / samtpfote"
    await client.patch(f"/api/familie/profile/{f.ids['clara']}", json={"einstellungen": {"katze": {"an": False, "name": "Flocke"}}},
                       headers=f.kopf["ada"])
    assert (await client.get("/api/familie/ich", headers=f.kopf["clara"])).json()["katze"]["an"] is False


async def test_stufen_fuer_die_oberflaeche(client, test_db):
    stufen = (await client.get("/api/familie/stufen")).json()
    assert [s["schluessel"] for s in stufen["stufen"]] == ["vorlesen", "erstes_lesen", "lesen_lernen", "schule", "jugend"]
    assert [(s["alter_von"], s["alter_bis"]) for s in stufen["stufen"]] == [(0, 5), (6, 7), (8, 9), (10, 13), (14, None)]
    assert [(v["alter_von"], v["minuten"]) for v in stufen["lesezeit"]][:3] == [(0, 30), (6, 45), (9, 60)]
    assert stufen["stufen"][0]["vorgaben"]["lesezeit"]["ruhe_von"] == "18:00"
    assert all("ki" not in s["faehigkeiten"] for s in stufen["stufen"]) and len(stufen["zugang"]["bilder"]) >= 9


async def test_schnellfilter_ist_suche(client, test_db):
    f = await familie_anlegen(client, test_db)
    assert (await client.get("/api/books", params={"suche": "Mond"}, headers=f.kopf["clara"])).status_code == 403
    assert (await client.get("/api/books", params={"suche": "Mond"}, headers=f.kopf["dora"])).json()["gesamt"] == 1


async def test_fertig_gelesen_nach_einer_regel(client, test_db):
    """Fertig ist ein Buch ab 99 % (oder am Ende) oder als gelesen markiert, und bleibt es; das gilt für den Filter, die Zähler
    und den Einblick."""
    f = await familie_anlegen(client, test_db)
    await test_db.execute("UPDATE books SET page_count = 50 WHERE id = ?", (f.buch["mond"],))
    await test_db.commit()
    weg, dora = f"/api/books/{f.buch['mond']}", f.kopf["dora"]

    async def fertig() -> bool:
        return (await client.get(weg, headers=dora)).json()["fertig_am"] is not None

    for stand, erwartet in (("page:49", False), ("percent:98.9", False), ("page:50", True), ("percent:10", True)):   # bleibt fertig
        await client.patch(f"{weg}/leseposition", json={"position": stand}, headers=dora)
        assert await fertig() is erwartet, stand
    gelesen = await client.get("/api/books", params={"gelesen": True}, headers=dora)
    assert [b["id"] for b in gelesen.json()["buecher"]] == [f.buch["mond"]]
    zahlen = (await client.get("/api/config/stats", headers=dora)).json()
    assert (zahlen["gelesen"], zahlen["ungelesen"]) == (1, 1)
    eintrag = (await client.get(f"/api/familie/profile/{f.ids['dora']}/einblick", headers=f.kopf["ada"])).json()["eintraege"][0]
    assert eintrag["fertig"] is True and eintrag["fortschritt"] == 1.0
    assert (await client.patch(f"{weg}/gelesen", headers=dora)).json()["gelesen"] is False      # zurückgenommen
    assert await fertig() is False and (await client.get(weg, headers=dora)).json()["reading_position"] == "percent:10"
    await client.patch(f"/api/books/{f.buch['stern']}/leseposition", json={"position": 'epub:{"cfi":"x","percent":99.5}'}, headers=dora)
    assert (await client.get(f"/api/books/{f.buch['stern']}", headers=dora)).json()["fertig_am"] is not None
