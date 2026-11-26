"""Gestaltung des Kinderbereichs (BF-88): klein oder groß nach der Stufe, je Kind umstellbar; die Uhr im Kopf als Zeiger oder
Zahl; die Leseschrift normal oder Kinderschrift, in der Gestaltung groß wählt das Kind sie beim Lesen selbst. Alles erfunden."""

from __future__ import annotations

from backend.app.familie.stufen import stufenbuch
from tests.api.familie_hilfen import anlegen, familie_anlegen, waehlen


async def _ich(client, kopf: dict) -> dict:
    r = await client.get("/api/familie/ich", headers=kopf)
    assert r.status_code == 200, r.text
    return r.json()


async def _lena(client, f) -> dict:
    """Ein Kind der Stufe Lesen und Lernen dazu"""
    lena = (await anlegen(client, f.kopf["ada"], name="Lena", rolle="kind", stufe="lesen_lernen"))["id"]
    return await waehlen(client, lena)


async def test_die_gestaltung_folgt_der_stufe(client, test_db):
    f = await familie_anlegen(client, test_db)
    clara, dora, emil, ada = [await _ich(client, f.kopf[n]) for n in ("clara", "dora", "emil", "ada")]
    lena = await _ich(client, await _lena(client, f))
    assert (clara["gestaltung"], clara["uhr"], clara["katze"]["an"]) == ("klein", "zeiger", True)
    assert (lena["gestaltung"], lena["uhr"], lena["katze"]["an"]) == ("gross", "zeiger", False)
    assert (dora["gestaltung"], dora["uhr"], dora["katze"]["an"]) == ("gross", "zahl", False)
    assert emil["gestaltung"] is None and emil["profil"]["einstellungen"]["gestaltung"] is None       # Jugend: die Oberfläche der App
    assert ada["gestaltung"] is None and ada["uhr"] is None
    # Ansagen anfangs aus in Groß, an in Klein
    assert (clara["lesehilfen"]["hinweise_sprechen"], clara["lesehilfen"]["tasten_ansagen"]) == (True, True)
    assert (lena["lesehilfen"]["hinweise_sprechen"], lena["lesehilfen"]["tasten_ansagen"]) == (False, False)
    # Groß liest normal, Klein in der Kinderschrift der Stufe
    assert clara["lesehilfen"]["schrift_wahl"] == "kinderschrift" and clara["darstellung"]["schrift"] == "kinderschrift"
    normal = stufenbuch().gestaltung.normalschrift
    d = dora["darstellung"]
    assert dora["lesehilfen"]["schrift_wahl"] == "normal"
    assert (d["schrift"], d["buchstabe"], d["wort"], d["absatz"]) == (normal.schrift, normal.buchstabe, normal.wort, normal.absatz)
    assert d["groesse_px"] == stufenbuch().stufe("schule").darstellung.groesse_px                       # Größe und Zeilen bleiben


async def test_die_eltern_stellen_gestaltung_und_uhr_je_kind_um(client, test_db):
    f = await familie_anlegen(client, test_db)
    vorher = await _ich(client, f.kopf["clara"])
    r = await client.patch(f"/api/familie/profile/{f.ids['clara']}", json={"einstellungen": {"gestaltung": "gross", "uhr": "zahl"}},
                           headers=f.kopf["ada"])
    assert r.status_code == 200, r.text
    assert (r.json()["einstellungen"]["gestaltung"], r.json()["einstellungen"]["uhr"]) == ("gross", "zahl")
    clara = await _ich(client, f.kopf["clara"])
    assert (clara["gestaltung"], clara["uhr"]) == ("gross", "zahl")
    # Die Fähigkeiten bleiben an der Stufe, die übrigen Einstellungen bleiben, wie sie waren
    assert clara["faehigkeiten"] == vorher["faehigkeiten"] and clara["lesehilfen"] == vorher["lesehilfen"]
    assert clara["katze"] == vorher["katze"]
    # Nur das Genannte ändert sich
    await client.patch(f"/api/familie/profile/{f.ids['clara']}", json={"einstellungen": {"uhr": "zeiger"}}, headers=f.kopf["ada"])
    clara = await _ich(client, f.kopf["clara"])
    assert (clara["gestaltung"], clara["uhr"]) == ("gross", "zeiger")
    # Jugend bleibt in der Oberfläche der App
    await client.patch(f"/api/familie/profile/{f.ids['emil']}", json={"einstellungen": {"gestaltung": "gross"}}, headers=f.kopf["ada"])
    assert (await _ich(client, f.kopf["emil"]))["gestaltung"] is None
    for falsch in ({"gestaltung": "mittel"}, {"uhr": "sanduhr"}):
        r = await client.patch(f"/api/familie/profile/{f.ids['clara']}", json={"einstellungen": falsch}, headers=f.kopf["ada"])
        assert r.status_code == 422, falsch
    # Das Kind selbst stellt nichts davon um
    r = await client.patch(f"/api/familie/profile/{f.ids['dora']}", json={"einstellungen": {"gestaltung": "klein"}}, headers=f.kopf["dora"])
    assert r.status_code == 403


async def test_die_katze_ist_in_gross_anfangs_aus(client, test_db):
    f = await familie_anlegen(client, test_db)
    assert (await _ich(client, f.kopf["dora"]))["katze"]["an"] is False
    await client.patch(f"/api/familie/profile/{f.ids['dora']}", json={"einstellungen": {"katze": {"an": True, "name": "Kiesel"}}},
                       headers=f.kopf["ada"])
    katze = (await _ich(client, f.kopf["dora"]))["katze"]
    assert (katze["an"], katze["name"]) == (True, "Kiesel")


async def test_die_eltern_geben_die_schrift_vor(client, test_db):
    f = await familie_anlegen(client, test_db)
    wahl = {"schrift_wahl": "kinderschrift", "silben": True}
    r = await client.patch(f"/api/familie/profile/{f.ids['dora']}", json={"einstellungen": {"lesehilfen": wahl}}, headers=f.kopf["ada"])
    assert r.status_code == 200 and r.json()["einstellungen"]["lesehilfen"]["schrift_wahl"] == "kinderschrift"
    d = (await _ich(client, f.kopf["dora"]))["darstellung"]
    schule = stufenbuch().stufe("schule").darstellung
    assert (d["schrift"], d["buchstabe"], d["wort"], d["absatz"]) == ("kinderschrift", schule.buchstabe, schule.wort, schule.absatz)
    r = await client.patch(f"/api/familie/profile/{f.ids['dora']}", json={"einstellungen": {"lesehilfen": {"schrift_wahl": "fraktur"}}},
                           headers=f.kopf["ada"])
    assert r.status_code == 422


async def test_in_gross_schaltet_das_kind_die_schrift_selbst(client, test_db):
    f = await familie_anlegen(client, test_db)
    await client.patch(f"/api/familie/profile/{f.ids['dora']}", json={"einstellungen": {"lesehilfen": {"silben": True, "schrift": "gross"}}},
                       headers=f.kopf["ada"])
    r = await client.patch("/api/familie/ich/schrift", json={"schrift_wahl": "kinderschrift"}, headers=f.kopf["dora"])
    assert r.status_code == 200, r.text
    neu = r.json()
    assert neu["lesehilfen"]["schrift_wahl"] == "kinderschrift" and neu["darstellung"]["schrift"] == "kinderschrift"
    assert neu["lesehilfen"]["silben"] is True and neu["lesehilfen"]["schrift"] == "gross"            # die Wahl der Eltern bleibt
    assert (await _ich(client, f.kopf["dora"]))["darstellung"] == neu["darstellung"]                # gespeichert
    eltern = (await client.get(f"/api/familie/profile/{f.ids['dora']}", headers=f.kopf["ada"])).json()
    assert eltern["einstellungen"]["lesehilfen"]["schrift_wahl"] == "kinderschrift"                 # die Eltern sehen es
    r = await client.patch("/api/familie/ich/schrift", json={"schrift_wahl": "normal"}, headers=f.kopf["dora"])
    assert r.status_code == 200 and r.json()["darstellung"]["schrift"] == stufenbuch().gestaltung.normalschrift.schrift


async def test_die_schrift_waehlt_das_kind_nur_in_gross(client, test_db):
    f = await familie_anlegen(client, test_db)
    for wer in ("clara", "emil", "ada"):                                                            # Klein, Jugend, Erwachsene
        r = await client.patch("/api/familie/ich/schrift", json={"schrift_wahl": "normal"}, headers=f.kopf[wer])
        assert r.status_code == 403, wer
    assert (await _ich(client, f.kopf["clara"]))["lesehilfen"]["schrift_wahl"] == "kinderschrift"
    r = await client.patch("/api/familie/ich/schrift", json={"schrift_wahl": "fraktur"}, headers=f.kopf["dora"])
    assert r.status_code == 422
    r = await client.patch("/api/familie/ich/schrift", json={"schrift_wahl": "normal", "silben": True}, headers=f.kopf["dora"])
    assert r.status_code == 200 and r.json()["lesehilfen"]["silben"] is False                       # sonst nichts
    # Stellen die Eltern das Kind auf Klein, wählen wieder sie
    await client.patch(f"/api/familie/profile/{f.ids['dora']}", json={"einstellungen": {"gestaltung": "klein"}}, headers=f.kopf["ada"])
    r = await client.patch("/api/familie/ich/schrift", json={"schrift_wahl": "kinderschrift"}, headers=f.kopf["dora"])
    assert r.status_code == 403


async def test_vorgaben_der_gestaltung_fuer_die_oberflaeche(client, test_db):
    stufen = {s["schluessel"]: s["vorgaben"] for s in (await client.get("/api/familie/stufen")).json()["stufen"]}
    assert {k: (v["gestaltung"], v["uhr"], v["katze"]["an"], v["lesehilfen"]["schrift_wahl"]) for k, v in stufen.items()} == {
        "vorlesen": ("klein", "zeiger", True, "kinderschrift"),
        "erstes_lesen": ("klein", "zeiger", True, "kinderschrift"),
        "lesen_lernen": ("gross", "zeiger", False, "normal"),
        "schule": ("gross", "zahl", False, "normal"),
        "jugend": (None, "zahl", False, "normal"),
    }
