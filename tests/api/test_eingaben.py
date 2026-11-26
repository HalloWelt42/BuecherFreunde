"""Eingabegrenzen und saubere Fehlerantworten (BF-50): Grenzen an den Modellen, 404 und 409 statt 500, 404 statt stummem
200, Meldungen bei 422 deutsch in einer Form."""

import hashlib

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from tests.api.conftest import buch_erstellen, kategorie_erstellen, sammlung_erstellen
from tests.api.test_annahme_api import hochladen, pdf, warten

ZU_GROSS = 2**63


@pytest.fixture
async def ohne_ausnahmen(test_db, auth_headers):
    """Wie der Browser: ein Fehler im Server kommt als Antwort 500, nicht als Ausnahme im Test."""
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver",
                           headers=auth_headers) as c:
        yield c


# -- Grenzen an den Modellen, Meldung in einer Form ---------------------------------------------------------------------

@pytest.mark.parametrize(("feld", "wert", "meldung"), [
    ("title", "   ", "Titel: darf nicht leer sein"),
    ("author", "", "Autor: darf nicht leer sein"),
    ("title", "x" * 501, "Titel: höchstens 500 Zeichen"),
    ("year", 99_999, "Jahr: höchstens"),
    ("year", 12, "Jahr: mindestens 1000"),
    ("page_count", -1, "Seiten: mindestens 0"),
    ("isbn", "keine ISBN", "ISBN: hat nicht die erwartete Form"),
    ("typ", "roman", "Typ: erlaubt ist leer oder dokument, heft, katalog, broschuere, anleitung"),
    ("gattung", "heft", "Gattung: erlaubt ist leer oder krimi, thriller, historisch"),
    ("umschlag_wahl", "bunt", 'Umschlag: erlaubt ist "", "gestaltet" oder "titelseite"'),
    ("sammlung_id", ZU_GROSS, "Sammlung: höchstens"),
])
async def test_buch_aendern_mit_grenzen(ohne_ausnahmen, test_db, feld, wert, meldung):
    buch = await buch_erstellen(test_db)
    r = await ohne_ausnahmen.patch(f"/api/books/{buch}", json={feld: wert})
    assert r.status_code == 422, r.text
    assert isinstance(r.json()["detail"], str) and r.json()["detail"].startswith(meldung), r.json()


async def test_leerzeichen_am_rand_gehen(ohne_ausnahmen, test_db):
    buch = await buch_erstellen(test_db)
    r = await ohne_ausnahmen.patch(f"/api/books/{buch}", json={"title": "  Neuer Titel  ", "year": None})
    assert r.status_code == 200 and r.json()["title"] == "Neuer Titel" and r.json()["year"] is None


@pytest.mark.parametrize(("weg", "daten", "meldung"), [
    ("/api/categories", {"name": " "}, "Name: darf nicht leer sein"),
    ("/api/categories", {"name": "Krimi", "color": "rot"}, "Farbe: keine Farbe wie #3366ff"),
    ("/api/categories", {"name": "Krimi", "sort_order": ZU_GROSS}, "Reihenfolge: höchstens 1000000"),
    ("/api/collections", {"name": ""}, "Name: darf nicht leer sein"),
    ("/api/collections", {}, "Name: fehlt"),
])
async def test_anlegen_mit_grenzen(ohne_ausnahmen, test_db, weg, daten, meldung):
    r = await ohne_ausnahmen.post(weg, json=daten)
    assert r.status_code == 422 and r.json() == {"detail": meldung}, r.text


async def test_notiz_markierung_etikett_mit_grenzen(ohne_ausnahmen, test_db):
    buch = await buch_erstellen(test_db)
    assert (await ohne_ausnahmen.post(f"/api/books/{buch}/notes", json={"content": "  "})).json() == {"detail": "Notiz: darf nicht leer sein"}
    r = await ohne_ausnahmen.post(f"/api/books/{buch}/highlights", json={"cfi_range": "epubcfi(/6/2)", "color": "gelb"})
    assert r.json() == {"detail": "Farbe: keine Farbe wie #3366ff"}
    r = await ohne_ausnahmen.post(f"/api/books/{buch}/labels", json={"position_percent": 140})
    assert r.json() == {"detail": "Position: höchstens 100"}
    r = await ohne_ausnahmen.patch(f"/api/books/{buch}/leseposition", json={"position": ""})
    assert r.json() == {"detail": "Leseposition: darf nicht leer sein"}


async def test_kaputtes_json_und_falsche_art(ohne_ausnahmen, test_db):
    r = await ohne_ausnahmen.post("/api/categories", content=b"{kein json", headers={"content-type": "application/json"})
    assert r.status_code == 422 and r.json()["detail"].endswith("ist kein gültiges JSON")
    r = await ohne_ausnahmen.get("/api/books", params={"seite": "zwei"})
    assert r.json() == {"detail": "Seite: keine ganze Zahl"}


# -- 404 und 409 statt 500 -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("weg", ["/api/books/9223372036854775808", "/api/books/abc", "/api/authors/9223372036854775808",
                                 "/api/collections/9223372036854775808", "/api/books/0"])
async def test_nummer_ausserhalb_ist_nicht_gefunden(ohne_ausnahmen, test_db, weg):
    r = await ohne_ausnahmen.get(weg)
    assert r.status_code == 404 and r.json() == {"detail": "Nicht gefunden"}


async def test_zahl_ausserhalb_im_koerper(ohne_ausnahmen, test_db):
    r = await ohne_ausnahmen.post("/api/books/bulk", json={"book_ids": [ZU_GROSS], "aktion": "favorit", "wert": True})
    assert r.status_code == 422 and r.json()["detail"].startswith("Bücher, Eintrag 1: höchstens")


async def test_zu_fehlendem_buch_nicht_gefunden(ohne_ausnahmen, test_db):
    for weg, daten in (("notes", {"content": "Hallo"}), ("highlights", {"cfi_range": "epubcfi(/6/2)"}), ("labels", {"name": "x"})):
        r = await ohne_ausnahmen.post(f"/api/books/999/{weg}", json=daten)
        assert r.status_code == 404 and r.json() == {"detail": "Buch nicht gefunden"}, (weg, r.text)


async def test_regal_auf_vorhandenen_namen(ohne_ausnahmen, test_db):
    await kategorie_erstellen(test_db, "Krimi")
    roman = await kategorie_erstellen(test_db, "Roman")
    r = await ohne_ausnahmen.patch(f"/api/categories/{roman}", json={"name": "krimi"})
    assert r.status_code == 409 and r.json() == {"detail": "Ein Regal mit diesem Namen gibt es schon"}
    assert (await ohne_ausnahmen.patch(f"/api/categories/{roman}", json={"name": "Roman"})).status_code == 200   # der eigene Name


async def test_unbekannte_sammlung_und_unbekanntes_regal(ohne_ausnahmen, test_db):
    buch = await buch_erstellen(test_db)
    r = await ohne_ausnahmen.patch(f"/api/books/{buch}", json={"sammlung_id": 999})
    assert r.status_code == 404 and r.json() == {"detail": "Sammlung nicht gefunden"}
    r = await ohne_ausnahmen.post("/api/books/bulk", json={"book_ids": [buch], "aktion": "sammlung_zuweisen", "wert": 999})
    assert r.status_code == 404 and r.json() == {"detail": "Sammlung nicht gefunden"}
    r = await ohne_ausnahmen.post(f"/api/categories/{buch}/zuordnen", json=[999])
    assert r.status_code == 404 and r.json() == {"detail": "Regal nicht gefunden: 999"}


async def test_datenbank_lehnt_ab_ohne_500(ohne_ausnahmen, test_db):
    """Die Grenze für alle Wege: ein fremder Schlüssel, den es nicht gibt, ist 404, nie 500."""
    buch = await buch_erstellen(test_db)
    r = await ohne_ausnahmen.post("/api/books/bulk", json={"book_ids": [buch, 999], "aktion": "favorit", "wert": True})
    assert r.status_code == 404 and r.json() == {"detail": "Ein genannter Eintrag fehlt"}


# -- 404 statt stummem 200 ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize(("art", "weg", "daten"), [
    ("patch", "/api/notes/999", {"content": "neu"}), ("delete", "/api/notes/999", None),
    ("patch", "/api/highlights/999", {"color": "#ffffff"}), ("delete", "/api/highlights/999", None),
    ("patch", "/api/labels/999", {"name": "x"}), ("delete", "/api/labels/999", None),
    ("patch", "/api/collections/999", {"name": "x"}), ("delete", "/api/collections/999", None),
    ("patch", "/api/categories/999", {"name": "x"}), ("delete", "/api/categories/999", None),
])
async def test_fehlendes_aendern_oder_loeschen(ohne_ausnahmen, test_db, art, weg, daten):
    r = await (ohne_ausnahmen.patch(weg, json=daten) if art == "patch" else ohne_ausnahmen.delete(weg))
    assert r.status_code == 404, (weg, r.status_code, r.text)
    assert isinstance(r.json()["detail"], str)


async def test_zuordnung_loesen_die_es_nicht_gibt(ohne_ausnahmen, test_db):
    buch = await buch_erstellen(test_db)
    regal = await kategorie_erstellen(test_db, "Lyrik")
    sammlung = await sammlung_erstellen(test_db)
    assert (await ohne_ausnahmen.delete(f"/api/categories/{regal}/books/{buch}")).status_code == 404
    assert (await ohne_ausnahmen.delete(f"/api/collections/{sammlung}/buch/{buch}")).status_code == 404


# -- Filter, letzte Notizen ----------------------------------------------------------------------------------------------

async def test_schalter_filtern_in_beide_richtungen(ohne_ausnahmen, test_db):
    lieb = await buch_erstellen(test_db, hash="a", title="Lieblingsbuch")
    anders = await buch_erstellen(test_db, hash="b", title="Anderes")
    await ohne_ausnahmen.patch(f"/api/books/{lieb}/favorit")
    await ohne_ausnahmen.patch(f"/api/books/{lieb}/zu-lesen")
    await ohne_ausnahmen.post(f"/api/books/{lieb}/highlights", json={"cfi_range": "epubcfi(/6/2)"})
    for schalter in ("favorit", "zu_lesen", "hat_highlights"):
        ja = [b["id"] for b in (await ohne_ausnahmen.get("/api/books", params={schalter: "true"})).json()["buecher"]]
        nein = [b["id"] for b in (await ohne_ausnahmen.get("/api/books", params={schalter: "false"})).json()["buecher"]]
        assert (ja, nein) == ([lieb], [anders]), schalter


async def test_letzte_notizen_nur_als_auszug(ohne_ausnahmen, test_db):
    buch = await buch_erstellen(test_db)
    lang = "Wort " * 200
    await ohne_ausnahmen.post(f"/api/books/{buch}/notes", json={"content": lang})
    await ohne_ausnahmen.post(f"/api/books/{buch}/notes", json={"content": "kurz"})
    notizen = {n["auszug"]: n for n in (await ohne_ausnahmen.get("/api/notes/recent")).json()}
    assert all("content" not in n for n in notizen.values())
    assert notizen["kurz"]["gekuerzt"] is False
    lange = next(n for n in notizen.values() if n["gekuerzt"])
    assert len(lange["auszug"]) <= 200 and lange["book_title"] == "Testbuch"


# -- Hochladen ------------------------------------------------------------------------------------------------------------

async def test_langer_dateiname_wird_gekuerzt(annahme_dienst, auth_headers):
    from backend.app.core.config import settings

    name = "Ä" * 199 + ".pdf"                               # 402 Byte, mehr als ein Dateisystem nimmt
    z = await hochladen(annahme_dienst, auth_headers, name, pdf("Lang"))
    assert z["stand"] != "fehler", z
    z = await warten(annahme_dienst, auth_headers, z["id"])
    assert z["stand"] == "fertig" and z["name"] == name, z
    eingang = settings.eingang_dir
    assert not eingang.exists() or not any(eingang.iterdir()), "der leere Ordner der Aufnahme bleibt nicht liegen"


async def test_nicht_mehr_als_angesagt(annahme_dienst, auth_headers):
    inhalt = pdf("Klein")
    r = await annahme_dienst.post("/api/annahme", headers=auth_headers, json={"name": "Klein.pdf", "groesse": 100, "sha256": hashlib.sha256(inhalt).hexdigest()})
    nr = r.json()["id"]
    r = await annahme_dienst.patch(f"/api/annahme/{nr}", headers={**auth_headers, "Upload-Offset": "0"}, content=inhalt)
    assert r.status_code == 413 and r.json() == {"detail": "Mehr Daten als die angesagte Größe der Datei"}
    assert (await annahme_dienst.get(f"/api/annahme/{nr}", headers=auth_headers)).json()["empfangen"] == 0


async def test_leere_ordner_beim_start(annahme_dienst, auth_headers):
    from backend.app.annahme.dienst import annahme
    from backend.app.core.config import settings

    leer, voll = settings.eingang_dir / "41", settings.eingang_dir / "42"
    leer.mkdir(parents=True)
    voll.mkdir(parents=True)
    (voll / "angefangen.pdf").write_bytes(b"%PDF")
    await annahme.stoppen()
    annahme.starten()
    assert not leer.exists() and (voll / "angefangen.pdf").exists()


# -- Annahme: Zähler je Quelle, viele auf einmal entfernen, Ort des Eingangsordners --------------------------------------

async def test_zaehler_je_quelle_und_aufraeumen(annahme_dienst, auth_headers, test_db):
    from backend.app.annahme import dienst

    for i in range(5):
        await test_db.execute("INSERT INTO aufnahme(name, groesse, stand, schritt, text, quelle, pfad) VALUES (?, 1, ?, 0, '', 'ordner', ?)",
                              (f"{i}.pdf", "fertig" if i < 3 else "kaputt", f"/ordner/{i}.pdf"))
    await test_db.execute("INSERT INTO aufnahme(name, groesse, stand, schritt, text, quelle) VALUES ('x.cbz', 1, 'format', 0, '', 'hochladen')")
    await test_db.commit()
    alt, dienst.LISTE = dienst.LISTE, 2
    try:
        stand = (await annahme_dienst.get("/api/annahme", headers=auth_headers)).json()
    finally:
        dienst.LISTE = alt
    assert len(stand["eintraege"]) == 2 and stand["weitere"] == 4
    assert stand["zaehler"]["alle"] == 6
    assert stand["quellen"]["ordner"] == {"gesamt": 5, "laeuft": 0, "bestaetigen": 0, "fertig": 3, "da": 0, "gescheitert": 2}
    assert stand["quellen"]["hochladen"]["gescheitert"] == 1

    r = await annahme_dienst.delete("/api/annahme", headers=auth_headers)
    assert r.status_code == 422
    r = await annahme_dienst.delete("/api/annahme", headers=auth_headers, params={"quelle": "ordner", "stand": ["kaputt", "fehler"]})
    assert r.status_code == 200 and r.json()["entfernt"] == 2
    assert r.json()["quellen"]["ordner"]["gesamt"] == 3 and r.json()["quellen"]["hochladen"]["gesamt"] == 1
    r = await annahme_dienst.delete("/api/annahme", headers=auth_headers, params={"stand": "unbekannt"})
    assert r.status_code == 422 and r.json()["detail"].startswith('Zustand, Eintrag 1: erlaubt ist "wartet", "laedt"'), r.json()


async def test_eingangsordner_nennt_seinen_ort(annahme_dienst, auth_headers, tmp_path, monkeypatch):
    from backend.app.core.config import settings

    monkeypatch.setattr(settings, "eingangsordner_dir", tmp_path / "eingangsordner")
    stand = (await annahme_dienst.get("/api/annahme/eingangsordner", headers=auth_headers)).json()
    assert stand["ort"] == "geraet" and stand["pfad"] == str(tmp_path / "eingangsordner")


# -- Datei: zum Ansehen inline, zum Herunterladen als Anhang -------------------------------------------------------------

async def test_datei_inline_oder_als_anhang(ohne_ausnahmen, test_db, tmp_path, monkeypatch):
    from backend.app.core.config import settings
    from backend.app.services.storage import get_storage_path

    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    buch = await buch_erstellen(test_db, hash="dateihash", file_name="Probe.pdf")
    ordner = get_storage_path("dateihash")
    ordner.mkdir(parents=True)
    (ordner / "Probe.pdf").write_bytes(pdf("Datei"))
    ansehen = await ohne_ausnahmen.get(f"/api/books/{buch}/file")
    laden = await ohne_ausnahmen.get(f"/api/books/{buch}/file", params={"herunterladen": "true"})
    assert ansehen.status_code == laden.status_code == 200
    assert ansehen.headers["content-disposition"].startswith("inline")
    assert laden.headers["content-disposition"].startswith("attachment")
