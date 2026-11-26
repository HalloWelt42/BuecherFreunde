"""Familie (BF-78): Einzelbetrieb wie bisher, Profilwahl mit PIN und Bild-PIN samt Fehlversuchen, Rollen beim Anlegen und
Ändern, Gerätebindung, Löschen nach den Folgen, das letzte Profil Verwaltung. Alle Namen sind erfunden."""

from __future__ import annotations

from datetime import date

import pytest

from backend.app.core import auth
from backend.app.familie import pin
from tests.api.conftest import buch_erstellen, verwaltung
from tests.api.familie_hilfen import BILDER, GERAET, PIN_BERT, anlegen, familie_anlegen, waehlen


# -- Einzelbetrieb ----------------------------------------------------------------------------------------------------------------

async def test_einzelbetrieb_wie_bisher_und_name_aus_dem_konto(client, test_db):
    """Ein Profil Verwaltung ohne PIN: ohne X-Profil geht alles wie vor BF-78; der Name kommt aus dem Konto des Geräts."""
    f = (await client.get("/api/familie")).json()
    assert f["braucht_wahl"] is False and [p["rolle"] for p in f["profile"]] == ["verwaltung"]
    assert (await client.get("/api/books")).status_code == 200
    assert (await client.get("/api/familie")).json()["profile"][0]["name"] == "admin"        # Konto der Tests heißt admin
    ich = (await client.get("/api/familie/ich")).json()
    assert ich["profil"]["rolle"] == "verwaltung" and "profile" in ich["faehigkeiten"] and ich["einblick"] == []
    assert ich["lesezeit"]["an"] is False and ich["darstellung"] == {}


async def test_wahl_auch_im_einzelbetrieb(client, test_db):
    """Die Oberfläche holt sich auch mit einem Profil ohne PIN einen Schlüssel; ein zweites Profil sperrt sie dann nicht aus."""
    kopf = await waehlen(client, await verwaltung(test_db))
    await anlegen(client, kopf, name="Pia", rolle="kind", stufe="erstes_lesen")
    assert (await client.get("/api/books", headers=kopf)).status_code == 200


async def test_mehrere_profile_verlangen_eine_wahl(client, test_db):
    await anlegen(client, name="Pia", rolle="erwachsen")
    r = await client.get("/api/books")
    assert r.status_code == 401 and r.json()["code"] == "profil_waehlen" and r.headers["www-authenticate"] == "Profil"
    assert "Profil" in r.json()["detail"]
    r = await client.get("/api/books", headers={"X-Profil": "gibt-es-nicht"})
    assert r.status_code == 401 and r.json() == {"detail": "Das gewählte Profil gilt nicht mehr, bitte neu wählen", "code": "profil_waehlen"}
    assert (await client.get("/api/familie")).json()["braucht_wahl"] is True              # die Wahl selbst braucht kein Profil


async def test_eine_pin_allein_verlangt_schon_die_wahl(client, test_db):
    ada = await verwaltung(test_db)
    assert (await client.put(f"/api/familie/profile/{ada}/pin", json={"pin": "2468"})).status_code == 200
    assert (await client.get("/api/books")).status_code == 401
    assert (await client.post("/api/familie/wahl", json={"profil_id": ada})).status_code == 403
    kopf = await waehlen(client, ada, pin="2468")
    assert (await client.get("/api/books", headers=kopf)).status_code == 200


# -- PIN und Bild-PIN -------------------------------------------------------------------------------------------------------------

async def test_pin_mit_fehlversuchen_und_wartezeit(client, test_db, monkeypatch):
    f = await familie_anlegen(client, test_db)
    jetzt = [1000.0]
    monkeypatch.setattr(pin.versuche, "uhr", lambda: jetzt[0])
    for _ in range(5):
        r = await client.post("/api/familie/wahl", json={"profil_id": f.ids["bert"], "pin": "0000"})
        assert r.status_code == 403 and r.json()["detail"] == "Die PIN stimmt nicht"
    r = await client.post("/api/familie/wahl", json={"profil_id": f.ids["bert"], "pin": PIN_BERT})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0 and "warten" in r.json()["detail"]
    jetzt[0] += 31
    assert (await client.post("/api/familie/wahl", json={"profil_id": f.ids["bert"], "pin": PIN_BERT})).status_code == 200
    r = await client.post("/api/familie/wahl", json={"profil_id": f.ids["bert"], "pin": "0000"})
    assert r.status_code == 403                                                          # nach Erfolg wieder frei


async def test_bild_pin_in_ihrer_folge(client, test_db):
    f = await familie_anlegen(client, test_db)
    assert (await client.post("/api/familie/wahl", json={"profil_id": f.ids["clara"], "bild_pin": list(reversed(BILDER))})).status_code == 403
    assert (await client.post("/api/familie/wahl", json={"profil_id": f.ids["clara"]})).status_code == 403
    assert (await client.post("/api/familie/wahl", json={"profil_id": f.ids["clara"], "bild_pin": BILDER})).status_code == 200
    r = await client.put(f"/api/familie/profile/{f.ids['clara']}/pin", json={"bild_pin": ["sonne", "drache", "mond"]}, headers=f.kopf["ada"])
    assert r.status_code == 422 and "unbekannte Bilder" in r.json()["detail"]
    r = await client.put(f"/api/familie/profile/{f.ids['clara']}/pin", json={"pin": "12"}, headers=f.kopf["ada"])
    assert r.status_code == 422


async def test_pin_liegt_nur_als_scrypt(client, test_db):
    f = await familie_anlegen(client, test_db)
    z = await test_db.fetch_one("SELECT pin, bild_pin FROM profil WHERE id = ?", (f.ids["bert"],))
    # Die PIN steht nie als Klartext da; ein Vergleich als Teilstück wäre zufällig falsch, weil Prüfsummen und Kennungen
    # Ziffern enthalten
    assert z["pin"].startswith("scrypt$") and PIN_BERT not in z["pin"].split("$") and z["bild_pin"] == ""
    sitzungen = await test_db.fetch_all("SELECT pruefsumme FROM profil_sitzung")
    assert all(f.kopf[n]["X-Profil"] not in [s["pruefsumme"] for s in sitzungen] for n in f.kopf)
    antwort = await client.get("/api/familie")
    assert "scrypt" not in antwort.text and PIN_BERT not in _werte(antwort.json())


def _werte(daten: object) -> list[str]:
    """Alle Werte einer Antwort als Text, um Klartext genau zu finden."""
    if isinstance(daten, dict):
        return [w for v in daten.values() for w in _werte(v)]
    if isinstance(daten, list):
        return [w for v in daten for w in _werte(v)]
    return [str(daten)]


async def test_fremde_pin_setzt_nur_die_verwaltung_und_beendet_die_sitzungen(client, test_db):
    f = await familie_anlegen(client, test_db)
    r = await client.put(f"/api/familie/profile/{f.ids['ada']}/pin", json={"pin": "9999"}, headers=f.kopf["bert"])
    assert r.status_code == 403
    assert (await client.put(f"/api/familie/profile/{f.ids['bert']}/pin", json={"pin": "1357"}, headers=f.kopf["ada"])).status_code == 200
    assert (await client.get("/api/familie/ich", headers=f.kopf["bert"])).status_code == 401      # Bert wählt neu
    assert (await client.put(f"/api/familie/profile/{f.ids['dora']}/pin", json={"pin": "5555"}, headers=f.kopf["dora"])).status_code == 200


async def test_wechsel_beendet_den_alten_schluessel(client, test_db):
    f = await familie_anlegen(client, test_db)
    r = await client.post("/api/familie/wahl", json={"profil_id": f.ids["dora"]}, headers=f.kopf["emil"])
    assert r.status_code == 200
    assert (await client.get("/api/familie/ich", headers=f.kopf["emil"])).status_code == 401
    assert (await client.get("/api/familie/ich", headers={"X-Profil": r.json()["schluessel"]})).json()["profil"]["name"] == "Dora"


async def test_pin_vergessen_mit_erneuter_anmeldung(client, test_db, monkeypatch):
    f = await familie_anlegen(client, test_db)
    assert (await client.put(f"/api/familie/profile/{f.ids['ada']}/pin", json={"pin": "8642"}, headers=f.kopf["ada"])).status_code == 200
    from appkern.anmeldung import Abgelehnt, Konto

    class Anmeldung:
        abgemeldet: list[str] = []

        async def pruefen(self, token):
            return Konto(id="1", name="admin") if token == "test-sitzung" else None

        async def anmelden(self, kennung, passwort):
            if passwort != "richtig":
                raise Abgelehnt("Name oder Kennwort stimmt nicht")
            return "frisch", Konto(id="1", name="admin")

        async def abmelden(self, token):
            self.abgemeldet.append(token)

    schein = Anmeldung()
    monkeypatch.setattr(auth, "anmeldung", schein)
    weg = f"/api/familie/profile/{f.ids['ada']}/pin/vergessen"
    r = await client.post(weg, json={"kennung": "admin", "passwort": "falsch"})
    assert r.status_code == 403 and r.json() == {"detail": "Name oder Kennwort stimmt nicht"}    # nie 401: das hieße abmelden
    r = await client.post(weg, json={"kennung": "admin", "passwort": "richtig"})
    assert r.status_code == 200 and schein.abgemeldet == ["frisch"]
    assert next(p for p in r.json()["profile"] if p["id"] == f.ids["ada"])["hat_pin"] is False
    assert (await client.post(f"/api/familie/profile/{f.ids['bert']}/pin/vergessen", json={"kennung": "admin", "passwort": "richtig"})).status_code == 403


# -- Rollen -------------------------------------------------------------------------------------------------------------------

async def test_rollen_beim_anlegen_und_aendern(client, test_db):
    f = await familie_anlegen(client, test_db)
    bert, dora = f.kopf["bert"], f.kopf["dora"]
    assert (await client.post("/api/familie/profile", json={"name": "Gustav", "rolle": "erwachsen"}, headers=bert)).status_code == 403
    neu = await anlegen(client, bert, name="Hanna", rolle="kind", geburtsjahr=date.today().year - 8)
    assert neu["stufe"] == "lesen_lernen"                                            # Vorschlag aus dem Geburtsjahr
    assert (await client.post("/api/familie/profile", json={"name": "Ida", "rolle": "kind"}, headers=dora)).status_code == 403
    r = await client.post("/api/familie/profile", json={"name": "Jana", "rolle": "kind"}, headers=f.kopf["ada"])
    assert r.status_code == 422 and "Stufe" in r.json()["detail"]
    assert (await client.post("/api/familie/profile", json={"name": "bert", "rolle": "kind", "stufe": "schule"}, headers=f.kopf["ada"])).status_code == 409
    assert (await client.patch(f"/api/familie/profile/{f.ids['bert']}", json={"rolle": "verwaltung"}, headers=bert)).status_code == 403
    assert (await client.patch(f"/api/familie/profile/{f.ids['bert']}", json={"name": "Bertram"}, headers=bert)).status_code == 200
    assert (await client.patch(f"/api/familie/profile/{f.ids['ada']}", json={"name": "Adele"}, headers=bert)).status_code == 403
    r = await client.patch(f"/api/familie/profile/{f.ids['dora']}", json={"stufe": "jugend"}, headers=bert)
    assert r.status_code == 200 and r.json()["stufe"] == "jugend"
    assert (await client.patch(f"/api/familie/profile/{f.ids['dora']}", json={"name": "Dorothea"}, headers=dora)).status_code == 403
    r = await client.patch(f"/api/familie/profile/{f.ids['bert']}", json={"stufe": "schule"}, headers=f.kopf["ada"])
    assert r.status_code == 422                                                          # nur Kinder haben eine Stufe


async def test_einstellungen_teilweise_ersetzen_und_was_wirkt(client, test_db):
    f = await familie_anlegen(client, test_db)
    weg = f"/api/familie/profile/{f.ids['clara']}"
    vorher = (await client.get(weg, headers=f.kopf["ada"])).json()["einstellungen"]
    assert vorher["lesezeit"]["minuten"] == 30 and vorher["lesehilfen"]["schrift"] == "mittel"        # Vorgaben für das Alter
    r = await client.patch(weg, json={"einstellungen": {"lesehilfen": {"mitlesen": True, "tempo": 0.7, "silben": True, "lesezeile": False,
                                                                       "schrift": "gross"}}}, headers=f.kopf["ada"])
    assert r.status_code == 200
    e = r.json()["einstellungen"]
    assert e["lesehilfen"]["tempo"] == 0.7 and e["lesehilfen"]["schrift"] == "gross" and e["lesezeit"] == vorher["lesezeit"]
    ich = (await client.get("/api/familie/ich", headers=f.kopf["clara"])).json()
    assert ich["darstellung"]["groesse_px"] == round(32 * 1.2) and ich["lesehilfen"]["silben"] is True
    familie = (await client.get("/api/familie", headers=f.kopf["bert"])).json()
    assert next(p for p in familie["profile"] if p["id"] == f.ids["clara"])["einstellungen"] is not None
    assert next(p for p in familie["profile"] if p["id"] == f.ids["ada"])["geburtsjahr"] is None
    familie = (await client.get("/api/familie", headers=f.kopf["dora"])).json()
    assert next(p for p in familie["profile"] if p["id"] == f.ids["clara"])["einstellungen"] is None   # Dora ändert Clara nicht


# -- Gerätebindung ---------------------------------------------------------------------------------------------------------------

async def test_geraet_fest_auf_ein_kind(client, test_db):
    f = await familie_anlegen(client, test_db)
    geraet = {"X-Geraet": GERAET}
    r = await client.post("/api/familie/geraet", json={"profil_id": f.ids["clara"], "eltern_pin": "0000"}, headers=geraet)
    assert r.status_code == 403
    r = await client.post("/api/familie/geraet", json={"profil_id": f.ids["bert"], "eltern_pin": PIN_BERT}, headers=geraet)
    assert r.status_code == 422                                                          # nur auf ein Kind
    assert (await client.post("/api/familie/geraet", json={"profil_id": f.ids["clara"], "eltern_pin": PIN_BERT}, headers=geraet)).status_code == 204

    stand = (await client.get("/api/familie", headers=geraet)).json()
    assert [p["id"] for p in stand["profile"]] == [f.ids["clara"]] and stand["geraet"]["gebunden_an"] == f.ids["clara"]
    assert (await client.post("/api/familie/wahl", json={"profil_id": f.ids["ada"]}, headers=geraet)).status_code == 403
    assert (await client.get("/api/familie/ich", headers=f.kopf["ada"] | geraet)).status_code == 401
    r = await client.post("/api/familie/wahl", json={"profil_id": f.ids["clara"], "bild_pin": BILDER}, headers=geraet)
    clara = {"X-Profil": r.json()["schluessel"]} | geraet
    assert (await client.get("/api/familie/ich", headers=clara)).status_code == 200

    # verlassen nur mit der PIN der Eltern; dann ist die Wahl offen, die Bindung bleibt
    assert (await client.post("/api/familie/verlassen", json={}, headers=clara)).status_code == 403
    assert (await client.post("/api/familie/verlassen", json={"eltern_pin": PIN_BERT}, headers=clara)).status_code == 204
    offen = (await client.get("/api/familie", headers=geraet)).json()
    assert offen["geraet"] == {"gebunden_an": None, "fest_auf": f.ids["clara"], "offen": True} and len(offen["profile"]) == 5
    r = await client.post("/api/familie/wahl", json={"profil_id": f.ids["bert"], "pin": PIN_BERT}, headers=geraet)
    bert = {"X-Profil": r.json()["schluessel"]} | geraet
    assert (await client.get("/api/familie/ich", headers=bert)).status_code == 200            # gilt für diese Sitzung
    assert (await client.get("/api/familie", headers=geraet)).json()["geraet"]["offen"] is False   # nur einmal
    assert (await client.post("/api/familie/wahl", json={"profil_id": f.ids["dora"]}, headers=geraet)).status_code == 403

    # lösen: mit der PIN der Eltern oder als Verwaltung
    assert (await client.request("DELETE", "/api/familie/geraet", json={}, headers=bert)).status_code == 403
    assert (await client.request("DELETE", "/api/familie/geraet", json={}, headers=f.kopf["ada"] | geraet)).status_code == 204
    assert (await client.get("/api/familie", headers=geraet)).json()["geraet"]["fest_auf"] is None


async def test_binden_braucht_eine_pin_der_eltern(client, test_db):
    kopf = await waehlen(client, await verwaltung(test_db))
    kind = await anlegen(client, kopf, name="Pia", rolle="kind", stufe="vorlesen")
    r = await client.post("/api/familie/geraet", json={"profil_id": kind["id"], "eltern_pin": ""}, headers={"X-Geraet": GERAET})
    assert r.status_code == 409


# -- Löschen ------------------------------------------------------------------------------------------------------------------

async def test_loeschen_erst_nach_den_folgen(client, test_db):
    f = await familie_anlegen(client, test_db)
    bert = f.kopf["bert"]
    await client.post(f"/api/books/{f.buch['mond']}/notes", json={"content": "Schöne Stelle"}, headers=bert)
    await client.patch(f"/api/books/{f.buch['mond']}/favorit", headers=bert)
    weg = f"/api/familie/profile/{f.ids['bert']}"
    assert (await client.get(f"{weg}/loeschfolgen", headers=bert)).status_code == 403
    folgen = (await client.get(f"{weg}/loeschfolgen", headers=f.kopf["ada"])).json()
    assert {k: folgen[k] for k in ("notizen", "lesestaende", "private_buecher", "freigaben")} == {
        "notizen": 1, "lesestaende": 1, "private_buecher": 1, "freigaben": 0}
    assert (await client.delete(weg, headers=f.kopf["ada"])).status_code == 422          # ohne Stand der Folgen nicht
    assert (await client.delete(f"{weg}?stand=veraltet", headers=f.kopf["ada"])).status_code == 409
    await client.post(f"/api/books/{f.buch['stern']}/notes", json={"content": "Noch eine"}, headers=bert)
    assert (await client.delete(f"{weg}?stand={folgen['stand']}", headers=f.kopf["ada"])).status_code == 409   # inzwischen mehr
    folgen = (await client.get(f"{weg}/loeschfolgen", headers=f.kopf["ada"])).json()
    assert (await client.delete(f"{weg}?stand={folgen['stand']}", headers=f.kopf["ada"])).status_code == 204
    for tabelle in ("book_notes", "user_book_data", "buch_privat", "profil_sitzung"):
        assert (await test_db.fetch_one(f"SELECT COUNT(*) AS n FROM {tabelle} WHERE profil_id = ?", (f.ids["bert"],)))["n"] == 0
    assert (await client.get(f"/api/books/{f.buch['zebra']}", headers=f.kopf["ada"])).status_code == 200   # das Buch bleibt, für alle


async def test_das_letzte_profil_verwaltung_bleibt(client, test_db):
    f = await familie_anlegen(client, test_db)
    weg = f"/api/familie/profile/{f.ids['ada']}"
    folgen = (await client.get(f"{weg}/loeschfolgen", headers=f.kopf["ada"])).json()
    r = await client.delete(f"{weg}?stand={folgen['stand']}", headers=f.kopf["ada"])
    assert r.status_code == 409 and r.json()["detail"] == "Das letzte Profil Verwaltung bleibt"
    r = await client.patch(weg, json={"rolle": "erwachsen"}, headers=f.kopf["ada"])
    assert r.status_code == 409
    assert (await client.patch(f"/api/familie/profile/{f.ids['bert']}", json={"rolle": "verwaltung"}, headers=f.kopf["ada"])).status_code == 200
    assert (await client.patch(weg, json={"rolle": "erwachsen"}, headers=f.kopf["ada"])).status_code == 200   # jetzt gibt es zwei


@pytest.mark.parametrize("wer", ["bert", "dora"])
async def test_loeschen_nur_die_verwaltung(client, test_db, wer):
    f = await familie_anlegen(client, test_db)
    assert (await client.delete(f"/api/familie/profile/{f.ids['emil']}?stand=x", headers=f.kopf[wer])).status_code == 403


async def test_profil_und_buch_mit_nummern_unabhaengig(client, test_db):
    """Profile haben UUIDs; Bücher behalten ihre Nummern."""
    f = await familie_anlegen(client, test_db)
    assert all(len(i) == 36 for i in f.ids.values())
    assert await buch_erstellen(test_db, hash="fam99") > max(f.buch.values())


async def test_ohne_persoenliches_auch_vor_der_wahl(client, test_db):
    """Konfiguration, Oberfläche und Hintergründe zeigen nichts Persönliches: dafür reicht das Konto des Geräts."""
    await anlegen(client, name="Pia", rolle="erwachsen")
    for weg in ("/api/config", "/api/config/oberflaeche", "/api/config/design/hintergruende", "/api/familie", "/api/familie/stufen"):
        assert (await client.get(weg)).status_code == 200, weg
    assert (await client.get("/api/config/stats")).status_code == 401
