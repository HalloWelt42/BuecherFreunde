"""Sichtbarkeit (BF-78) über alle Wege: ein Kind sieht nichts, was ihm nicht freigegeben ist, und kein Profil etwas, das ein
anderes privat markiert hat. Geprüft wird jeder Weg mit einem Buch oder einer Fassung im Pfad (aus der App selbst gelesen, damit
kein neuer Weg durchrutscht), jede Liste ohne Pfadangabe auf Spuren der verborgenen Bücher, und die Zähler genau.
Alle Namen und Titel sind erfunden."""

from __future__ import annotations

import re

import pytest
from fastapi.routing import APIRoute

from backend.app.main import app
from tests.api.conftest import FUNDUS_SCHLUESSEL, kategorie_erstellen, sammlung_erstellen
from tests.api.familie_hilfen import Familie, familie_anlegen, freigeben

BUCH_IM_PFAD = {"book_id", "buch_id", "buch"}
# Wege ohne Pfadangabe, die nicht in eine Liste gehören: Ströme ohne Ende, fremde Dienste, Dateien
NICHT_ALS_LISTE = {"/api/annahme/ereignisse", "/api/authors/scanner/events", "/api/config/update-check", "/api/gutenberg/suche",
                   "/api/gutenberg/status", "/api/verbindungen", "/api/backup/download", "/api/vorlesen/stimmen", "/api/nachschlag/suche",
                   "/api/nachschlag/artikel", "/api/config/design/hintergrund", "/api/katalog/datei", "/api/ausfuehren",
                   "/api/ausfuehren/funktionen/php", "/api/ai/status", "/api/ai/config"}
SPUREN = {"zebra": ("Zebrageheimnis", "Quirin Verborgen"), "steuer": ("Steuerkram", "Otto Amtlich")}


async def _bestand(client, test_db) -> tuple[Familie, dict]:
    f = await familie_anlegen(client, test_db)
    extra = {}
    for name, buecher in (("Rike Fantasia", ["mond", "stern"]), ("Quirin Verborgen", ["zebra"]), ("Otto Amtlich", ["steuer"])):
        c = await test_db.execute("INSERT INTO authors (name, slug) VALUES (?, ?)", (name, name.lower().replace(" ", "-")))
        extra[name] = c.lastrowid
        for b in buecher:
            await test_db.execute("INSERT INTO book_authors (book_id, author_id) VALUES (?, ?)", (f.buch[b], c.lastrowid))
    for b in ("zebra", "steuer", "mond"):
        c = await test_db.execute("INSERT INTO fassung (buch_id, sprache, aus_sprache, stand) VALUES (?, 'de', 'en', 'laeuft')", (f.buch[b],))
        extra[f"fassung_{b}"] = c.lastrowid
    extra["reihe"] = await sammlung_erstellen(test_db, name="Reihe der Probe")
    await test_db.execute("UPDATE books SET sammlung_id = ? WHERE id IN (?, ?, ?)", (extra["reihe"], f.buch["mond"], f.buch["zebra"], f.buch["steuer"]))
    extra["geheim"] = await kategorie_erstellen(test_db, name="Geheimfach")
    await test_db.execute("INSERT INTO book_categories (book_id, category_id) VALUES (?, ?)", (f.buch["zebra"], extra["geheim"]))
    await test_db.execute("INSERT INTO aufnahme (name, groesse, stand, buch_id) VALUES ('Zebrageheimnis.epub', 10, 'fertig', ?)", (f.buch["zebra"],))
    await test_db.commit()
    await client.patch(f"/api/books/{f.buch['zebra']}/leseposition", json={"position": "percent:40"}, headers=f.kopf["bert"])
    await client.post(f"/api/books/{f.buch['zebra']}/notes", json={"content": "Zebrageheimnis notiert"}, headers=f.kopf["bert"])
    await client.patch(f"/api/books/{f.buch['steuer']}/leseposition", json={"position": "percent:10"}, headers=f.kopf["ada"])
    return f, extra


def _wege_mit_buch() -> list[tuple[str, str]]:
    wege = []
    for r in app.routes:
        if isinstance(r, APIRoute) and not r.path.startswith("/api/v1/fundus"):
            namen = set(re.findall(r"{(\w+)(?::\w+)?}", r.path))
            if namen & (BUCH_IM_PFAD | {"fid"}):
                wege += [(art, r.path) for art in sorted(r.methods)]
    return wege


def _adresse(weg: str, buch: int, fassung: int) -> str:
    def ersetzen(m: re.Match) -> str:
        name = m.group(1)
        return str(buch) if name in BUCH_IM_PFAD else str(fassung) if name == "fid" else {"sprache": "de", "kennung": "1.1", "pfad": "a"}.get(name, "1")
    return re.sub(r"{(\w+)(?::\w+)?}", ersetzen, weg)


def test_es_gibt_genug_wege_mit_buch():
    assert len(_wege_mit_buch()) > 50                    # die Prüfung unten sieht wirklich alle


@pytest.mark.parametrize(("wer", "verborgen"), [("clara", "steuer"), ("clara", "zebra"), ("emil", "steuer"), ("ada", "zebra"), ("dora", "zebra")])
async def test_kein_weg_zeigt_ein_verborgenes_buch(client, test_db, wer, verborgen):
    f, extra = await _bestand(client, test_db)
    durch = []
    for art, weg in _wege_mit_buch():
        r = await client.request(art, _adresse(weg, f.buch[verborgen], extra[f"fassung_{verborgen}"]), json={}, headers=f.kopf[wer])
        if r.status_code not in (403, 404):
            durch.append(f"{art} {weg}: {r.status_code}")
    assert durch == []
    assert (await client.get(f"/api/books/{f.buch['mond']}", headers=f.kopf[wer])).status_code == 200     # Freigegebenes geht


async def test_der_eigene_private_weg_bleibt_offen(client, test_db):
    f, extra = await _bestand(client, test_db)
    r = await client.get(f"/api/books/{f.buch['zebra']}", headers=f.kopf["bert"])
    assert r.status_code == 200 and r.json()["privat"] is True
    assert (await client.get(f"/api/fassungen/{extra['fassung_zebra']}/leseposition", headers=f.kopf["bert"])).status_code == 200


@pytest.mark.parametrize("wer", ["clara", "dora", "ada", "bert"])
async def test_keine_liste_verraet_ein_verborgenes_buch(client, test_db, wer):
    f, _extra = await _bestand(client, test_db)
    verborgen = {"clara": ["zebra", "steuer"], "dora": ["zebra", "steuer"], "ada": ["zebra"], "bert": []}[wer]
    parameter = {"q": "Zebrageheimnis Steuerkram", "suche": "Zebrageheimnis"}
    for r in app.routes:
        if not isinstance(r, APIRoute) or "GET" not in r.methods or "{" in r.path or r.path in NICHT_ALS_LISTE:
            continue
        if not r.path.startswith("/api/") or r.path.startswith("/api/v1/fundus"):
            continue
        antwort = await client.get(r.path, params=parameter, headers=f.kopf[wer])
        assert antwort.status_code < 500, f"{r.path}: {antwort.status_code}"
        for b in verborgen:
            titel, autor = SPUREN[b]
            assert autor not in antwort.text, f"{r.path} verrät {autor}"
            assert titel not in antwort.text.replace('"anfrage":"Zebrageheimnis Steuerkram"', ""), f"{r.path} verrät {titel}"


async def test_zaehler_und_listen_zaehlen_nur_sichtbares(client, test_db):
    f, extra = await _bestand(client, test_db)

    async def zahl(wer: str) -> int:
        return (await client.get("/api/config/stats", headers=f.kopf[wer])).json()["buecher_gesamt"]

    assert (await zahl("clara"), await zahl("ada"), await zahl("bert")) == (2, 3, 4)
    ids = {b["id"] for b in (await client.get("/api/books", headers=f.kopf["clara"])).json()["buecher"]}
    assert ids == {f.buch["mond"], f.buch["stern"]}
    assert (await client.get("/api/config/stats", headers=f.kopf["ada"])).json()["weiterlesen"] == 1     # ihr eigener Lesestand
    assert (await client.get("/api/config/stats", headers=f.kopf["bert"])).json()["weiterlesen"] == 1

    sammlung = {s["id"]: s["buch_anzahl"] for s in (await client.get("/api/collections", headers=f.kopf["ada"])).json()}
    assert sammlung[extra["reihe"]] == 2                                     # Mondfahrt und Steuerkram, ohne das private
    assert {s["id"]: s["buch_anzahl"] for s in (await client.get("/api/collections", headers=f.kopf["clara"])).json()} == {extra["reihe"]: 1}
    regale = {c["name"]: c["buch_anzahl"] for c in (await client.get("/api/categories", headers=f.kopf["ada"])).json()}
    assert regale["Geheimfach"] == 0
    assert {c["name"] for c in (await client.get("/api/categories", headers=f.kopf["clara"])).json()} == {"Feen"}
    katalog = (await client.get("/api/katalog", headers=f.kopf["bert"])).json()
    assert next(r["anzahl"] for r in katalog["regale"] if r["name"] == "Geheimfach") == 1
    katalog = (await client.get("/api/katalog", headers=f.kopf["ada"])).json()
    assert next(r["anzahl"] for r in katalog["regale"] if r["name"] == "Geheimfach") == 0
    assert (await client.get("/api/katalog", headers=f.kopf["clara"])).status_code == 403

    autoren = {a["name"]: a["book_count"] for a in (await client.get("/api/authors", headers=f.kopf["clara"])).json()["autoren"]}
    assert autoren == {"Rike Fantasia": 2}
    assert (await client.get(f"/api/authors/{extra['Quirin Verborgen']}", headers=f.kopf["ada"])).status_code == 404
    assert (await client.get(f"/api/authors/{extra['Quirin Verborgen']}", headers=f.kopf["bert"])).status_code == 200
    assert (await client.get("/api/authors/statistik/uebersicht", headers=f.kopf["clara"])).json()["gesamt"] == 1


async def test_suche_findet_nur_sichtbares(client, test_db):
    f, _extra = await _bestand(client, test_db)

    async def treffer(wer: str, q: str) -> int:
        return (await client.get("/api/search", params={"q": q}, headers=f.kopf[wer])).json()["gesamt"]

    assert (await treffer("bert", "Zebrageheimnis"), await treffer("ada", "Zebrageheimnis")) == (1, 0)
    assert (await treffer("ada", "Steuerkram"), await treffer("dora", "Steuerkram")) == (1, 0)
    assert (await client.get("/api/search", params={"q": "x"}, headers=f.kopf["clara"])).status_code == 403    # Vorlesen: ohne Suche
    r = await client.get("/api/books", params={"suche": "Zebra"}, headers=f.kopf["ada"])
    assert r.json()["gesamt"] == 0


async def test_aufnahmen_und_fassungen_ohne_fremdes_privates(client, test_db):
    f, extra = await _bestand(client, test_db)
    assert [e["buch_id"] for e in (await client.get("/api/annahme", headers=f.kopf["ada"])).json()["eintraege"]] == []
    assert [e["buch_id"] for e in (await client.get("/api/annahme", headers=f.kopf["bert"])).json()["eintraege"]] == [f.buch["zebra"]]
    laeufe = {e["buch_id"] for e in (await client.get("/api/fassungen", headers=f.kopf["ada"])).json()}
    assert laeufe == {f.buch["steuer"], f.buch["mond"]}


async def test_andere_apps_sehen_nichts_privates(client, test_db):
    f, _extra = await _bestand(client, test_db)
    app_kopf = {"Authorization": f"Bearer {FUNDUS_SCHLUESSEL}"}
    bestand = (await client.get("/api/v1/fundus/bestand", headers=app_kopf)).json()
    assert {b["buch"] for b in bestand["buecher"]} == {f.buch["mond"], f.buch["stern"], f.buch["steuer"]} and bestand["gesamt"] == 3
    assert next(b for b in bestand["buecher"] if b["buch"] == f.buch["steuer"])["lesestand"] is True       # der Verwaltung
    for weg in ("inhalt", "umschlag", "datei"):
        assert (await client.get(f"/api/v1/fundus/{weg}/{f.buch['zebra']}", headers=app_kopf)).status_code == 404
    assert (await client.get("/api/v1/fundus/suche", params={"q": "Zebrageheimnis"}, headers=app_kopf)).json()["gesamt"] == 0


async def test_umschlag_mit_dem_cookie_der_wahl(client, test_db):
    """Bilder haben keinen Kopf: das Cookie der Wahl trägt das Profil, auch für die Sichtbarkeit."""
    f, _extra = await _bestand(client, test_db)
    r = await client.post("/api/familie/wahl", json={"profil_id": f.ids["dora"]})
    assert r.cookies.get("bf_profil")
    assert (await client.get(f"/api/books/{f.buch['steuer']}/cover")).status_code == 404
    assert (await client.get(f"/api/books/{f.buch['mond']}/cover")).status_code == 200
    await client.post("/api/familie/verlassen", json={})
    assert (await client.get(f"/api/books/{f.buch['mond']}/cover")).status_code == 401


# -- Freigaben ----------------------------------------------------------------------------------------------------------------

async def test_freigabe_nach_buch_und_kategorie_mit_unterkategorien(client, test_db):
    f = await familie_anlegen(client, test_db)
    clara, ada = f.kopf["clara"], f.kopf["ada"]
    assert (await client.get(f"/api/books/{f.buch['stern']}", headers=clara)).status_code == 200      # über Märchen, darin Feen
    frei = (await client.get(f"/api/familie/profile/{f.ids['clara']}/freigaben", headers=ada)).json()
    assert [k["name"] for k in frei["kategorien"]] == ["Märchen"] and frei["kategorien"][0]["anzahl"] == 1
    assert [b["id"] for b in frei["buecher"]] == [f.buch["mond"]] and "alter_von" in frei["buecher"][0]
    r = await client.request("DELETE", f"/api/familie/profile/{f.ids['clara']}/freigaben", json={"art": "kategorie", "ziel_ids": [f.kategorie["maerchen"]]},
                             headers=ada)
    assert r.status_code == 200 and r.json()["kategorien"] == []
    assert (await client.get(f"/api/books/{f.buch['stern']}", headers=clara)).status_code == 404
    assert (await client.get(f"/api/familie/profile/{f.ids['clara']}/freigaben", headers=clara)).status_code == 200   # das Kind selbst
    assert (await client.get(f"/api/familie/profile/{f.ids['clara']}/freigaben", headers=f.kopf["dora"])).status_code == 403
    r = await client.post(f"/api/familie/profile/{f.ids['clara']}/freigaben", json={"art": "buch", "ziel_ids": [f.buch["stern"]]}, headers=clara)
    assert r.status_code == 403                                                          # Kinder geben nichts frei


async def test_nichts_geht_von_selbst_frei_und_privat_geht_vor(client, test_db):
    f = await familie_anlegen(client, test_db)
    await test_db.execute("UPDATE books SET alter_von = 3, alter_bis = 6, alter_quelle = 'dnb' WHERE id = ?", (f.buch["steuer"],))
    await test_db.commit()
    assert (await client.get(f"/api/books/{f.buch['steuer']}", headers=f.kopf["clara"])).status_code == 404   # Alter ist keine Freigabe
    r = await client.post(f"/api/familie/profile/{f.ids['clara']}/freigaben", json={"art": "buch", "ziel_ids": [f.buch["zebra"]]},
                          headers=f.kopf["ada"])
    assert r.status_code == 404                                                          # Ada sieht es nicht, gibt es nicht frei
    await freigeben(client, f.kopf["bert"], f.ids["clara"], "buch", [f.buch["zebra"]])
    assert (await client.get(f"/api/books/{f.buch['zebra']}", headers=f.kopf["clara"])).status_code == 404    # privat geht vor


async def test_ein_geloeschtes_buch_nimmt_seine_freigaben_mit(client, test_db):
    f = await familie_anlegen(client, test_db)
    await test_db.execute("DELETE FROM books WHERE id = ?", (f.buch["mond"],))
    await test_db.commit()
    assert (await test_db.fetch_one("SELECT COUNT(*) AS n FROM freigabe WHERE art = 'buch'"))["n"] == 0


async def test_privat_braucht_die_faehigkeit(client, test_db):
    f = await familie_anlegen(client, test_db)
    assert (await client.put(f"/api/books/{f.buch['mond']}/privat", json={"privat": True}, headers=f.kopf["dora"])).status_code == 403
    assert (await client.put(f"/api/books/{f.buch['mond']}/privat", json={"privat": True}, headers=f.kopf["emil"])).status_code == 200
    assert (await client.get(f"/api/books/{f.buch['mond']}", headers=f.kopf["ada"])).status_code == 404     # Emils, nur für ihn
    assert (await client.put(f"/api/books/{f.buch['mond']}/privat", json={"privat": False}, headers=f.kopf["emil"])).status_code == 200
    assert (await client.get(f"/api/books/{f.buch['mond']}", headers=f.kopf["ada"])).status_code == 200


async def test_sammelaktion_behandelt_verborgenes_wie_fehlendes(client, test_db):
    f = await familie_anlegen(client, test_db)
    r = await client.post("/api/books/bulk", json={"book_ids": [f.buch["zebra"]], "aktion": "favorit", "wert": True}, headers=f.kopf["ada"])
    assert r.status_code == 404
    r = await client.post("/api/books/bulk", json={"book_ids": [f.buch["zebra"], f.buch["mond"]], "aktion": "typ_setzen", "wert": "heft"},
                          headers=f.kopf["ada"])
    assert r.json()["betroffen"] == 1
    assert (await test_db.fetch_one("SELECT typ FROM books WHERE id = ?", (f.buch["zebra"],)))["typ"] == ""


async def test_sammlung_nur_mit_fremden_privaten_buechern_bleibt_verborgen(client, test_db):
    f = await familie_anlegen(client, test_db)
    sid = (await test_db.execute("INSERT INTO collections (name) VALUES ('Geheime Reihe')")).lastrowid
    await test_db.execute("UPDATE books SET sammlung_id = ? WHERE id = ?", (sid, f.buch["zebra"]))
    await test_db.execute("INSERT INTO collections (name) VALUES ('Leere Reihe')")

    async def namen(wer: str) -> list[str]:
        return [s["name"] for s in (await client.get("/api/collections", headers=f.kopf[wer])).json()]

    assert "Geheime Reihe" not in await namen("ada")
    assert (await client.get(f"/api/collections/{sid}", headers=f.kopf["ada"])).status_code == 404
    assert "Geheime Reihe" in await namen("bert")                        # Bert sieht sein privates Buch darin
    assert "Leere Reihe" in await namen("ada")                           # leere Sammlungen bleiben zum Füllen da



async def test_es_gibt_keinen_weg_alle_buecher_zu_loeschen(client, test_db):
    """Ein Weg ohne Folgenvorschau, der alle Bücher löscht, gibt es nicht (er war unerreichbar und ist entfernt)."""
    f = await familie_anlegen(client, test_db)
    vorher = (await test_db.fetch_one("SELECT COUNT(*) AS n FROM books"))["n"]
    r = await client.delete("/api/books/alle", params={"bestaetigung": "ALLE LOESCHEN"}, headers=f.kopf["ada"])
    assert r.status_code in (404, 422)
    assert (await test_db.fetch_one("SELECT COUNT(*) AS n FROM books"))["n"] == vorher
