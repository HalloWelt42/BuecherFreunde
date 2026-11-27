"""Vorlesen über die Vertonung (BF-14): Stimmen je Aufruf mit ihren Bereichen und dem Hinweis zur Freigabe privater Stimmen, der
Strom Satz für Satz über den Verbund des Appkerns mit dem App-Zugang der Kellerwolke, die Beschreibung der Einstellungen und die
Werte je Profil. Gegen eine Attrappe der Vertonung, ohne Netz; nur Katalogstimmen und erfundene Klonstimmen."""

import base64
import json

import httpx
from pydantic import Field

from backend.app.core.config import settings
from backend.app.vorlesen import sprechen
from tests.api.familie_hilfen import familie_anlegen
from tests.api.vertonung_hilfen import APP_ZUGANG, KLON, PRIVAT, VERTONUNG, WAV, schema_der_vertonung, vertonung  # noqa: F401 - Fixture

STROM = "/api/v1/sprechen/strom"


async def test_ohne_vertonung_die_stimme_des_geraets(client, monkeypatch):
    monkeypatch.setattr(settings, "vertonung_url", "")
    assert (await client.get("/api/vorlesen/stimmen")).json() == {"da": False, "stimmen": [], "bereiche": [], "hinweis": ""}
    r = await client.post("/api/vorlesen", json={"text": "Hallo"})
    assert r.status_code == 503 and "Vertonung" in r.json()["detail"]
    assert (await client.get("/api/config/oberflaeche")).json()["anschluesse"]["vorlesen"] is False
    assert (await client.get("/api/vorlesen/beschreibung")).json() == {"da": False, "felder": [], "hinweis": ""}


async def test_stimmen_je_bereich_ohne_freigabe_privater(client, vertonung):
    s = (await client.get("/api/vorlesen/stimmen")).json()
    assert s["da"] is True and s["hinweis"] == ""
    assert [(x["id"], x["bereich"]) for x in s["stimmen"]] == [(KLON, "fremd"), ("katalog:serena", "katalog"), ("katalog:vivian", "katalog")]
    assert s["stimmen"][0] == {"id": KLON, "name": "Probesprecher", "bereich": "fremd", "sprache": "de"}
    privat = next(b for b in s["bereiche"] if b["bereich"] == "privat")
    assert privat["frei"] is False and "nicht erlaubt" in privat["hinweis"] and "in der Vertonung unter Private Stimmen für" in privat["hinweis"]
    assert {b["bereich"] for b in s["bereiche"] if b["frei"]} == {"fremd", "katalog"}
    wege = {(r.url.path, r.url.params.get("bereich")) for r in vertonung.anfragen}
    assert wege == {("/api/v1/stimmen", "privat"), ("/api/v1/stimmen", "fremd"), ("/api/v1/stimmen", "katalog")}
    assert all(r.headers["authorization"] == f"Bearer {APP_ZUGANG}" and r.url.host == "vertonung.probe.test" for r in vertonung.anfragen)
    assert (await client.get("/api/config/oberflaeche")).json()["anschluesse"]["vorlesen"] is True


async def test_vertonung_in_den_verbindungen(client, vertonung):
    v = next(x for x in (await client.get("/api/verbindungen")).json() if x["kennung"] == "vertonung")
    assert v["stand"] == "warn" and v["text"].startswith("liest vor mit 3 Stimmen; ") and "Private Stimmen für" in v["text"]
    vertonung.privat_frei = True
    v = next(x for x in (await client.get("/api/verbindungen")).json() if x["kennung"] == "vertonung")
    assert (v["stand"], v["text"]) == ("gut", "liest vor mit 4 Stimmen")


async def test_jedes_mal_neu_aus_der_vertonung(client, vertonung):
    await client.get("/api/vorlesen/stimmen")
    vertonung.privat_frei = True
    vertonung.katalog = ["serena"]
    s = (await client.get("/api/vorlesen/stimmen")).json()
    assert [x["id"] for x in s["stimmen"]] == [PRIVAT, KLON, "katalog:serena"] and all(b["frei"] for b in s["bereiche"])
    assert len(vertonung.anfragen) == 6                                                    # keine gemerkte Liste


async def test_nicht_erreichbar_mit_grund(client, vertonung, monkeypatch):
    from backend.app.vorlesen import zugang

    def weg(_r):
        raise httpx.ConnectError("kein Netz")

    monkeypatch.setattr(zugang.verbund, "transport", httpx.MockTransport(weg))
    await zugang.verbund.schliessen()
    s = (await client.get("/api/vorlesen/stimmen")).json()
    assert s["da"] is False and s["stimmen"] == [] and "nicht erreichbar" in s["hinweis"]
    r = await client.post("/api/vorlesen", json={"text": "Hallo.", "stimme": "katalog:serena"})
    assert r.status_code == 503 and "nicht erreichbar" in r.json()["detail"]


async def test_strom_satz_fuer_satz_ueber_die_vertonung(client, vertonung):
    r = await client.post("/api/vorlesen", json={"text": "Erster Satz hier. Zweiter Satz dort.", "stimme": "katalog:serena"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    zeilen = [json.loads(z) for z in r.text.splitlines()]
    assert [(z["art"], z.get("nr"), z.get("text")) for z in zeilen] == [("satz", 0, "Erster Satz hier."), ("satz", 1, "Zweiter Satz dort."),
                                                                         ("ende", None, None)]
    assert base64.b64decode(zeilen[0]["ton"]) == WAV and zeilen[-1] == {"art": "ende", "saetze": 2, "dauer_ms": 200}
    [koerper] = vertonung.koerper(STROM)
    assert koerper == {"ausschreiben": True, "stimme": {"art": "katalog", "name": "serena"}, "text": "Erster Satz hier. Zweiter Satz dort."}
    assert vertonung.anfragen[-1].url == httpx.URL(f"{VERTONUNG}{STROM}")


async def test_klonstimme_und_stimme_ab_werk(client, vertonung):
    await client.post("/api/vorlesen", json={"text": "Nur ein Satz.", "stimme": KLON})
    await client.post("/api/vorlesen", json={"text": "Nur ein Satz."})
    mit, ohne = vertonung.koerper(STROM)
    assert mit["stimme"] == {"art": "klon", "knoten_id": KLON} and "stimme" not in ohne


async def test_langer_text_in_teilen_durchgezaehlt(client, vertonung):
    satz = "Ein recht langer Satz zum Vorlesen mit vielen Wörtern darin. "
    text = satz * 300                                                                       # rund 18000 Zeichen
    zeilen = [json.loads(z) for z in (await client.post("/api/vorlesen", json={"text": text})).text.splitlines()]
    teile = vertonung.koerper(STROM)
    assert len(teile) == 3 and all(len(t["text"]) <= 7_500 for t in teile)
    assert [z["nr"] for z in zeilen if z["art"] == "satz"] == list(range(300)) and zeilen[-1]["saetze"] == 300


async def test_fehler_vor_dem_ersten_satz_ist_eine_antwort(client, vertonung):
    vertonung.ablehnen = (403, "Private Stimmen sind dieser App nicht erlaubt")
    r = await client.post("/api/vorlesen", json={"text": "Hallo.", "stimme": PRIVAT})
    assert r.status_code == 403 and "nicht erlaubt" in r.json()["detail"]
    vertonung.ablehnen = (401, "Anmeldung erforderlich")
    r = await client.post("/api/vorlesen", json={"text": "Hallo."})
    assert r.status_code == 403, "eine 401 der Vertonung meldet die Person nie ab"
    r = await client.post("/api/vorlesen", json={"text": "Hallo.", "stimme": "a1b2c3"})               # keine Stimme der Vertonung
    assert r.status_code == 400 and "aus der Liste" in r.json()["detail"]
    r = await client.post("/api/vorlesen", json={"text": "Hallo.", "stimme": "geraet"})
    assert r.status_code == 400


async def test_fehler_nach_dem_ersten_satz_ist_eine_zeile(client, vertonung):
    vertonung.fehler_nach = 1
    r = await client.post("/api/vorlesen", json={"text": "Eins. Zwei. Drei."})
    zeilen = [json.loads(z) for z in r.text.splitlines()]
    assert zeilen[0]["art"] == "satz" and zeilen[-1] == {"art": "fehler", "meldung": "Sprechen gescheitert: der Mac schläft"}


async def test_kurzer_text_als_ton(vertonung):
    assert await sprechen.ton("Weiter", "katalog:vivian") == WAV + b"Weiter"
    assert vertonung.koerper("/api/v1/sprechen") == [{"ausschreiben": True, "stimme": {"art": "katalog", "name": "vivian"}, "text": "Weiter"}]


# -- Beschreibung und Werte je Profil ---------------------------------------------------------------------------------------------

async def test_beschreibung_aus_dem_schema_der_vertonung(client, vertonung):
    vertonung.schema = schema_der_vertonung(lautheit=(float, Field(0.0, ge=-6, le=6, title="Lautheit")))
    b = (await client.get("/api/vorlesen/beschreibung")).json()
    assert b["da"] is True and [f["schluessel"] for f in b["felder"]] == ["tempo", "sprache", "ausschreiben", "lautheit"]
    tempo, sprache, ausschreiben, lautheit = b["felder"]
    assert (tempo["name"], tempo["art"], tempo["von"], tempo["bis"], tempo["vorgabe"], tempo["mehr"]) == ("Tempo", "zahl", 0.5, 2.0, 1.0, False)
    assert (sprache["name"], sprache["art"], sprache["vorgabe"]) == ("Sprache", "text", None)
    assert (ausschreiben["art"], ausschreiben["vorgabe"]) == ("schalter", True) and ausschreiben["name"].startswith("Zahlen")
    assert (lautheit["name"], lautheit["mehr"], lautheit["von"], lautheit["bis"]) == ("Lautheit", True, -6, 6)      # unbekannt: unter Mehr
    vertonung.schema = None                                                                 # die Vertonung zeigt Apps ihr Schema nicht
    b = (await client.get("/api/vorlesen/beschreibung")).json()
    assert b["da"] is False and b["felder"] == [] and "nicht für andere Apps" in b["hinweis"]


async def test_werte_je_profil_gehen_mit(client, test_db, vertonung):
    f = await familie_anlegen(client, test_db)
    r = await client.patch("/api/familie/ich/vorlesen", json={"stimme": "katalog:serena", "werte": {"tempo": 1.2}}, headers=f.kopf["ada"])
    assert r.status_code == 200 and r.json() == {"stimme": "katalog:serena", "werte": {"tempo": 1.2}, "eigene_wahl": True}
    assert (await client.get("/api/familie/ich", headers=f.kopf["ada"])).json()["vorlesen"]["stimme"] == "katalog:serena"
    assert (await client.get("/api/familie/ich", headers=f.kopf["bert"])).json()["vorlesen"] == {"stimme": "", "werte": {}, "eigene_wahl": True}
    await client.post("/api/vorlesen", json={"text": "Hallo.", "stimme": "katalog:serena"}, headers=f.kopf["ada"])
    assert vertonung.koerper(STROM)[-1]["tempo"] == 1.2
    r = await client.patch("/api/familie/ich/vorlesen", json={"stimme": "geraet:Probestimme des Browsers"}, headers=f.kopf["ada"])
    assert r.json() == {"stimme": "geraet:Probestimme des Browsers", "werte": {"tempo": 1.2}, "eigene_wahl": True}, "die Werte bleiben"
    for falsch, grund in (({"tempo": 5}, "bis 2"), ({"tempo": "schnell"}, "Zahl"), ({"stimmung": "froh"}, "nicht an"), ({"ausschreiben": 1}, "an oder aus")):
        r = await client.patch("/api/familie/ich/vorlesen", json={"werte": falsch}, headers=f.kopf["ada"])
        assert r.status_code == 422 and grund in r.json()["detail"], (falsch, r.text)
    vertonung.schema = None
    r = await client.patch("/api/familie/ich/vorlesen", json={"werte": {"tempo": 1.1}}, headers=f.kopf["ada"])
    assert r.status_code == 422 and "beschreibt" in r.json()["detail"]
    assert (await client.patch("/api/familie/ich/vorlesen", json={"werte": {}}, headers=f.kopf["ada"])).status_code == 200   # leer geht immer


async def test_kinder_hoeren_die_wahl_der_eltern(client, test_db, vertonung):
    f = await familie_anlegen(client, test_db)
    assert (await client.patch("/api/familie/ich/vorlesen", json={"stimme": "katalog:serena"}, headers=f.kopf["clara"])).status_code == 403
    assert (await client.get("/api/familie/ich", headers=f.kopf["clara"])).json()["vorlesen"] == {"stimme": "", "werte": {}, "eigene_wahl": False}
    await client.put("/api/familie/stimme", json={"stimme": "katalog:vivian"}, headers=f.kopf["ada"])
    assert (await client.get("/api/familie/ich", headers=f.kopf["clara"])).json()["vorlesen"]["stimme"] == "katalog:vivian"
    r = await client.patch(f"/api/familie/profile/{f.ids['clara']}", json={"einstellungen": {"lesehilfen": {"stimme": KLON}, "vorlesen": {"werte": {"tempo": 0.8}}}},
                           headers=f.kopf["ada"])
    assert r.status_code == 200 and r.json()["einstellungen"]["vorlesen"] == {"stimme": None, "werte": {"tempo": 0.8}}
    assert (await client.get("/api/familie/ich", headers=f.kopf["clara"])).json()["vorlesen"] == {"stimme": KLON, "werte": {"tempo": 0.8}, "eigene_wahl": False}
    r = await client.patch(f"/api/familie/profile/{f.ids['clara']}", json={"einstellungen": {"vorlesen": {"stimme": "katalog:serena"}}}, headers=f.kopf["ada"])
    assert r.status_code == 422 and "Lesehilfen" in r.json()["detail"]


async def test_hinweis_zur_freigabe_nennt_den_namen_der_app(monkeypatch):
    """Die Vertonung vergleicht den App-Namen der Kellerwolke ("BücherFreunde", mit ü); der Hinweis nennt genau diesen."""
    from backend.app.core.anmeldung import eigener_zugang
    from backend.app.vorlesen import stimmen

    monkeypatch.setattr(eigener_zugang, "name", "BücherFreunde")
    assert await stimmen.weg_zur_freigabe() == 'Freigabe in der Vertonung unter Private Stimmen für die App "BücherFreunde" eintragen'
    monkeypatch.setattr(eigener_zugang, "name", None)
    monkeypatch.setattr(eigener_zugang, "erfragen", lambda: _sofort(None))
    assert await stimmen.weg_zur_freigabe() == stimmen.WEG_ZUR_FREIGABE


async def _sofort(wert):
    return wert
