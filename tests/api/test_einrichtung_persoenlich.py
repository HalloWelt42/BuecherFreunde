"""Persönliches in der Kellerwolke (BF-82): Notizen, Markierungen, Etiketten, Lesestand, Vorlesestelle, privat und Freigaben je Buch
und Profil im eigenen kleinen Begleiter `persoenlich`, laufend und gebündelt nachgeführt; der Auszug mit Volltext und Umschlag
bleibt dabei unberührt. Die Profile als eigene Datei ohne PIN. Einschalten und Ausschalten mit Entfernen nur mit Folgen. Nur gegen
die Attrappe der Kellerwolke; alle Namen sind erfunden."""

from __future__ import annotations

import io
import json
import random
import zipfile

import pytest

from backend.app.ablage import auszug, persoenlich
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.einrichtung import nachfuehren as nachfuehren_modul
from backend.app.einrichtung.nachfuehren import nachfuehren
from backend.app.services.storage import save_cover, save_fulltext
from tests.api.conftest import buch_erstellen, verwaltung
from tests.api.einrichtung_hilfen import laufend, orte  # noqa: F401 - Fixtures
from tests.api.kellerwolke_attrappe import Kellerwolke

pytestmark = pytest.mark.asyncio
KIND = "0f5a1c2e-7b3d-4e8f-9a10-1b2c3d4e5f60"


async def _buch_in_der_wolke(test_db, w: Kellerwolke, titel: str, h: str) -> tuple[int, str]:
    buch = await buch_erstellen(test_db, title=titel, hash=h, file_name=f"{titel}.pdf")
    knoten = w.datei(f"Apps/BücherFreunde/Bücher/P/{titel} [{buch}].pdf", f"%PDF {titel}".encode())
    await db.execute("INSERT INTO ablage_datei(hash, knoten, name, pfad) VALUES (?, ?, ?, ?)", (h, knoten, f"{titel} [{buch}].pdf", w.pfad(knoten)))
    await db.commit()
    return buch, knoten


def _begleiter(w: Kellerwolke, knoten: str, rolle: str = "persoenlich") -> dict | None:
    return next((b for b in w.begleiter(knoten) if b["rolle"] == rolle), None)


def _persoenlich(w: Kellerwolke, knoten: str) -> persoenlich.Begleiter:
    return persoenlich.lesen(w.inhalt[_begleiter(w, knoten)["id"]])


@pytest.fixture
def wolke(laufend, monkeypatch) -> Kellerwolke:
    w = Kellerwolke()
    w.einhaengen(monkeypatch)
    return w


async def test_persoenliches_je_profil_im_eigenen_begleiter_der_auszug_bleibt(wolke, test_db):
    buch, knoten = await _buch_in_der_wolke(test_db, wolke, "Probeband", "a" * 64)
    ich = await verwaltung(test_db)
    await db.execute("INSERT INTO profil(id, name, rolle, stufe, pin) VALUES (?, 'Lotte Probe', 'kind', 'schule', 'scrypt$geheim')", (KIND,))
    for n in range(3):
        await db.execute("INSERT INTO book_notes(profil_id, book_id, content) VALUES (?, ?, ?)", (ich, buch, f"Notiz {n}"))
    await db.execute("INSERT INTO book_highlights(profil_id, book_id, cfi_range, text_snippet) VALUES (?, ?, 'epubcfi(/6/2)', 'markiert')", (ich, buch))
    await db.execute("INSERT INTO book_labels(profil_id, book_id, name) VALUES (?, ?, 'Probe')", (ich, buch))
    await db.execute("INSERT INTO user_book_data(profil_id, book_id, reading_position) VALUES (?, ?, 'percent:40')", (KIND, buch))
    await db.execute("INSERT INTO freigabe(profil_id, art, ziel_id) VALUES (?, 'buch', ?)", (KIND, buch))
    await db.commit()
    assert (await db.fetch_one("SELECT COUNT(*) AS n FROM nachfuehren WHERE art = 'buch'"))["n"] == 1, "viele Änderungen, eine Marke"

    assert await nachfuehren.runde(sofort=True) == 1
    b = _persoenlich(wolke, knoten)
    assert (b.art, b.buch, b.hash) == ("buecherfreunde-persoenlich/1", buch, "a" * 64)
    assert [n.content for n in b.profile[ich].notizen] == ["Notiz 0", "Notiz 1", "Notiz 2"]
    assert b.profile[ich].markierungen[0].text_snippet == "markiert" and b.profile[ich].etiketten[0].name == "Probe"
    assert b.profile[KIND].lesestand.reading_position == "percent:40" and b.profile[KIND].freigegeben
    assert _begleiter(wolke, knoten)["name"] == f"Probeband [{buch}].persoenlich.json"
    assert [r for r, _ in wolke.geschrieben] == ["persoenlich"], "kein Auszug geschrieben"
    assert await nachfuehren.runde(sofort=True) == 0, "nichts geändert, nichts geschrieben"
    datei = json.loads(wolke.inhalt[next(k for k, z in wolke.knoten.items() if z["name"] == "profile.json")]) if any(
        z["name"] == "profile.json" for z in wolke.knoten.values()) else None
    assert datei and {p["name"] for p in datei["profile"]} >= {"Lotte Probe"}
    assert "pin" not in json.dumps(datei).lower() and "scrypt" not in json.dumps(datei)


async def test_zehnmal_lesestand_ist_ein_kleines_schreiben(wolke, test_db, monkeypatch):
    """Beim Lesen ändert sich der Lesestand laufend: nach einer ruhigen Weile wird einmal geschrieben, ein paar hundert Byte, während
    der Auszug mit seinem Volltext mehrere Megabyte hätte."""
    buch, knoten = await _buch_in_der_wolke(test_db, wolke, "Dickes Buch", "b" * 64)
    zufall = random.Random(82)                                 # ein Volltext wie aus einem Buch, nicht beliebig gut zu packen
    silben = ["leucht", "turm", "kai", "wind", "see", "ber", "gen", "haus", "licht", "nacht", "wel", "le", "sand", "boot", "ge", "fahr"]
    save_fulltext("b" * 64, " ".join("".join(zufall.choices(silben, k=zufall.randint(1, 4))) for _ in range(300_000)))
    save_cover("b" * 64, zufall.randbytes(150_000))
    ich = await verwaltung(test_db)
    monkeypatch.setattr(settings, "persoenlich_ruhe_s", 3600)
    for seite in range(1, 11):
        await db.execute("INSERT INTO user_book_data(profil_id, book_id, reading_position) VALUES (?, ?, ?) "
                         "ON CONFLICT(profil_id, book_id) DO UPDATE SET reading_position = excluded.reading_position", (ich, buch, f"page:{seite}"))
        await db.commit()
        assert await nachfuehren.runde() == 0, "noch nicht ruhig"
    monkeypatch.setattr(settings, "persoenlich_ruhe_s", 0)
    assert await nachfuehren.runde() == 1
    assert wolke.geschrieben == [("persoenlich", wolke.geschrieben[0][1])], "zehn Änderungen, ein Schreiben"
    groesse = wolke.geschrieben[0][1]
    assert _persoenlich(wolke, knoten).profile[ich].lesestand.reading_position == "page:10"
    ganzer_auszug = len(await auszug.bauen(buch, "b" * 64))
    assert groesse < 1024 and ganzer_auszug > 1000 * groesse, (groesse, ganzer_auszug)
    assert _begleiter(wolke, knoten, "auszug") is None, "der Auszug wurde nicht angefasst"


async def test_ruhige_weile_bevor_geschrieben_wird(wolke, test_db, monkeypatch):
    buch, _ = await _buch_in_der_wolke(test_db, wolke, "Wartband", "c" * 64)
    monkeypatch.setattr(settings, "persoenlich_ruhe_s", 3600)
    await db.execute("INSERT INTO book_notes(profil_id, book_id, content) VALUES (?, ?, 'frisch')", (await verwaltung(test_db), buch))
    await db.commit()
    assert await nachfuehren.runde() == 0 and (await nachfuehren.stand()).stand == "wartet"


async def test_einmal_nachtragen_nur_buecher_mit_persoenlichem(wolke, test_db):
    mit, _ = await _buch_in_der_wolke(test_db, wolke, "Mit Notiz", "d" * 64)
    await _buch_in_der_wolke(test_db, wolke, "Ohne alles", "e" * 64)
    ich = await verwaltung(test_db)
    await db.execute("INSERT INTO book_notes(profil_id, book_id, content) VALUES (?, ?, 'schon da')", (ich, mit))
    await db.commit()
    await db.execute("DELETE FROM nachfuehren")                # wie beim ersten Start: die Daten gab es vor den Triggern
    await db.commit()
    await nachfuehren.beim_start()
    marken = {(z["art"], z["ziel"]) for z in await db.fetch_all("SELECT art, ziel FROM nachfuehren")}
    assert marken == {("buch", mit), ("profile", 0)}, "nur Bücher mit Persönlichem, dazu einmal die Profile"
    assert (await db.fetch_one("SELECT value FROM app_settings WHERE key = 'persoenlich_nachgetragen'"))["value"] == "1"
    assert await nachfuehren.runde(sofort=True) == 1 and [r for r, _ in wolke.geschrieben] == ["persoenlich"]
    await nachfuehren.beim_start()                             # ein zweiter Start trägt nichts nach
    assert not await db.fetch_one("SELECT 1 FROM nachfuehren")


async def test_ausschalten_mit_folgen_und_entfernen(wolke, client, test_db):
    buch, knoten = await _buch_in_der_wolke(test_db, wolke, "Geheimband", "f" * 64)
    ich = await verwaltung(test_db)
    await nachfuehren_modul.merken("buch")                     # die Datei der Profile entsteht
    await db.execute("INSERT INTO book_notes(profil_id, book_id, content) VALUES (?, ?, 'nur für mich')", (ich, buch))
    await db.execute("INSERT INTO buch_privat(profil_id, book_id) VALUES (?, ?)", (ich, buch))
    await db.commit()
    alter_auszug = io.BytesIO()                                # ein Auszug aus der Zeit vor BF-82, mit Persönlichem darin
    with zipfile.ZipFile(alter_auszug, "w") as z:
        z.writestr("angaben.json", json.dumps({"art": auszug.FORM, "buch": {"id": buch}, "notizen": [{"content": "alt", "profil_id": ich}]}))
    k = wolke._neu("datei", f"Geheimband [{buch}].auszug.zip", wolke.knoten[knoten]["parent_id"], alter_auszug.getvalue())
    wolke.knoten[k] |= {"haupt_id": knoten, "rolle": "auszug"}
    await nachfuehren.runde(sofort=True)
    assert _persoenlich(wolke, knoten).profile[ich].privat and any(z["name"] == "profile.json" for z in wolke.knoten.values())

    assert (await client.get("/api/kellerwolke/einstellungen")).json() == {"persoenlich": True, "sicherungen_ablegen": True}
    f = (await client.get("/api/kellerwolke/persoenlich/folgen")).json()
    assert (f["buecher"], f["notizen"], f["private"], [p["buecher"] for p in f["profile"]], f["profile_datei"]) == (
        1, 1, 1, [1], "Apps/BücherFreunde/profile.json")
    assert (await client.put("/api/kellerwolke/einstellungen", json={"persoenlich": False, "entfernen": True})).status_code == 422
    await db.execute("INSERT INTO book_notes(profil_id, book_id, content) VALUES (?, ?, 'noch eine')", (ich, buch))
    await db.commit()
    r = await client.put("/api/kellerwolke/einstellungen", json={"persoenlich": False, "entfernen": True, "stand": f["stand"]})
    assert r.status_code == 409, "seit der Vorschau geändert"
    f = (await client.get("/api/kellerwolke/persoenlich/folgen")).json()
    r = await client.put("/api/kellerwolke/einstellungen", json={"persoenlich": False, "entfernen": True, "stand": f["stand"]})
    assert r.status_code == 200 and r.json()["persoenlich"] is False
    assert await nachfuehren.runde(sofort=True) == 1
    assert _begleiter(wolke, knoten) is None and f"Geheimband [{buch}].persoenlich.json" in wolke.im_papierkorb(), "im Papierkorb, zurückzuholen"
    assert "profile.json" in wolke.im_papierkorb()
    neu = auszug.lesen(wolke.inhalt[_begleiter(wolke, knoten, "auszug")["id"]])
    assert neu.angaben.persoenliches() == {} and neu.angaben.buch["title"] == "Geheimband", "der alte Auszug trägt nichts Persönliches mehr"
    assert (await db.fetch_one("SELECT COUNT(*) AS n FROM book_notes"))["n"] == 2, "in der App bleibt alles"

    await db.execute("INSERT INTO book_notes(profil_id, book_id, content) VALUES (?, ?, 'danach')", (ich, buch))
    await db.commit()
    assert await nachfuehren.runde(sofort=True) == 0 and _begleiter(wolke, knoten) is None, "ausgeschaltet geht nichts hinaus"
    r = await client.put("/api/kellerwolke/einstellungen", json={"persoenlich": True})
    assert r.status_code == 422, "Einschalten nur mit den Folgen"
    f = (await client.get("/api/kellerwolke/persoenlich/folgen")).json()
    assert (await client.put("/api/kellerwolke/einstellungen", json={"persoenlich": True, "stand": f["stand"]})).status_code == 200
    assert {z["ziel"] for z in await db.fetch_all("SELECT ziel FROM nachfuehren WHERE art = 'buch'")} == {buch}
    assert await nachfuehren.runde(sofort=True) == 1 and len(_persoenlich(wolke, knoten).profile[ich].notizen) == 3


async def test_ausschalten_ohne_entfernen_laesst_die_kellerwolke(wolke, client, test_db):
    buch, knoten = await _buch_in_der_wolke(test_db, wolke, "Bleibeband", "9" * 64)
    await db.execute("INSERT INTO book_notes(profil_id, book_id, content) VALUES (?, ?, 'bleibt')", (await verwaltung(test_db), buch))
    await db.commit()
    await nachfuehren.runde(sofort=True)
    vorher = {k: dict(z) for k, z in wolke.knoten.items()}
    assert (await client.put("/api/kellerwolke/einstellungen", json={"persoenlich": False})).status_code == 200
    assert await nachfuehren.runde(sofort=True) == 0
    assert {k: dict(z) for k, z in wolke.knoten.items()} == vorher and wolke.im_papierkorb() == []


async def test_alte_auszuege_werden_gelesen(test_db):
    """Auszüge bis BF-81 und aus tools/umzug tragen Zeilen der Tabellen; sie gehören dem Profil darin oder dem ersten."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr("angaben.json", json.dumps({"art": "buecherfreunde-angaben/1", "buch": {"id": 7, "title": "Altband"}, "kategorien": ["Probe"],
                                               "lesen": [{"book_id": 7, "reading_position": "page:3", "is_favorite": 1}],
                                               "notizen": [{"id": 1, "book_id": 7, "content": "alt", "profil_id": KIND}], "markierungen": [], "labels": []}))
        z.writestr("fulltext.txt", "Text")
    g = auszug.lesen(puffer.getvalue())
    je = g.angaben.persoenliches()
    assert je[""].lesestand.reading_position == "page:3" and je[KIND].notizen[0].content == "alt"
    assert set(g.dateien) == {"fulltext.txt"}


async def test_seitenangaben_als_freier_text_wie_in_alten_bestaenden(wolke, test_db):
    """Ältere Bestände halten die Seite einer Notiz als Text ("S.19", "2%") in einer Spalte mit Zahl als Art."""
    buch, knoten = await _buch_in_der_wolke(test_db, wolke, "Seitenband", "c" * 64)
    ich = await verwaltung(test_db)
    for seite in ("S.19", "2%", 19, None):
        await db.execute("INSERT INTO book_notes(profil_id, book_id, content, page_reference) VALUES (?, ?, 'Notiz', ?)", (ich, buch, seite))
    await db.commit()
    assert await nachfuehren.runde(sofort=True) == 1
    assert [n.page_reference for n in _persoenlich(wolke, knoten).profile[ich].notizen] == ["S.19", "2%", "19", None]


async def test_ein_buch_mit_fehler_haelt_die_uebrigen_nicht_auf(wolke, test_db, monkeypatch):
    gut, k_gut = await _buch_in_der_wolke(test_db, wolke, "Gutband", "d" * 64)
    schlecht, _ = await _buch_in_der_wolke(test_db, wolke, "Schlechtband", "e" * 64)
    ich = await verwaltung(test_db)
    for buch in (schlecht, gut):
        await db.execute("INSERT INTO book_notes(profil_id, book_id, content) VALUES (?, ?, 'Notiz')", (ich, buch))
    await db.commit()
    echt = persoenlich.schreiben

    async def schreiben(original: str, buch: int, file_hash: str) -> int:
        if buch == schlecht:
            raise ValueError("unerwartete Daten")
        return await echt(original, buch, file_hash)

    monkeypatch.setattr(persoenlich, "schreiben", schreiben)
    assert await nachfuehren.runde(sofort=True) == 1
    assert _begleiter(wolke, k_gut) is not None
    zurueck = await db.fetch_one("SELECT grund FROM nachfuehren WHERE art = 'fehler' AND ziel = ?", (schlecht,))
    assert zurueck and "unerwartete Daten" in zurueck["grund"]
    assert not await db.fetch_one("SELECT 1 FROM nachfuehren WHERE art = 'buch'"), "keine Marke bleibt hängen"
    assert "1 Buch übersprungen" in (await nachfuehren.stand()).grund
    assert await nachfuehren.runde(sofort=True) == 0, "ohne neue Änderung kein neuer Versuch"
