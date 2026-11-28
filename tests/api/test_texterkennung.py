"""Der Auftrag "Texte erkennen" (BF-109) in einer laufenden Probeinstallation: er sieht die Bücher durch, erkennt die Seiten der
Scans (die gelesenen zuerst, über den Weg aus dem Leser), zieht Volltext, Suche, Seiten, Seitenzahl und Codestellen nach, ruht
ohne Programm mit Grund und bleibt von Hand angehalten stehen. Das Programm ist eine Attrappe (eigener Prozess); alle Bücher,
Seiten und Texte sind erfunden."""

from __future__ import annotations

import asyncio
import io
import zipfile

import pytest

from backend.app.ablage import auszug
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.einrichtung.auftrag import ANGEHALTEN
from backend.app.familie import sichtbar
from backend.app.services.seiten import BEGLEITER, pdf_volltext
from backend.app.services.storage import get_sidecar_path, get_storage_path, ist_original, load_fulltext, save_fulltext
from backend.app.texterkennung import ablage, werkzeug
from backend.app.texterkennung.auftrag import erkennungswache, texterkennung
from tests.api.conftest import buch_erstellen
from tests.api.einrichtung_hilfen import laufend, orte  # noqa: F401 - Fixtures
from tests.api.familie_hilfen import familie_anlegen
from tests.texterkennung_hilfen import Probezeile, attrappe_anlegen, scan_pdf, text_pdf

pytestmark = pytest.mark.asyncio
WORT = "Leuchtturmwärterin"
ERKANNT = [Probezeile("Kapitel über die Insel", 72, 110, 18, block=1),
           Probezeile(f"Die {WORT} steigt am Abend die hundert Stufen zur Lampe hinauf und putzt das Glas.", 72, 140, block=2)]
SATZ = "Ein Buch mit eigener Textschicht, das keine Erkennung braucht, weil jede Seite genug lesbaren Text trägt."


@pytest.fixture(autouse=True)
async def sauber(monkeypatch):
    """Kein Auftrag läuft über einen Test hinaus; ohne Pausen."""
    monkeypatch.setattr(settings, "texterkennung_abstand_s", 0)
    monkeypatch.setattr(settings, "texterkennung_vorrang_seiten", 1)
    werkzeug.vergessen()
    yield
    await texterkennung.stoppen()
    werkzeug.vergessen()


@pytest.fixture
def programm(orte, monkeypatch):  # noqa: F811
    a = attrappe_anlegen(orte / "programm", monkeypatch)
    a.liefert(ERKANNT)
    return a


@pytest.fixture
def vorgemerkt(monkeypatch):
    """Welche Bücher die Codestellen neu erkennen sollen."""
    from backend.app.codestellen.dienst import codestellen

    liste: list[int] = []
    monkeypatch.setattr(codestellen, "vormerken", lambda buch, vorrang=False: liste.append(buch))
    return liste


async def _buch(test_db, kennung: str, pdf, seiten: list[str]) -> int:
    """Ein Buch wie nach dem Aufnehmen: Original auf dem Gerät, Volltext je Seite (bei einem Scan leere Seiten)."""
    nr = await buch_erstellen(test_db, hash=kennung, file_format="pdf", page_count=0, isbn="", fts_content="")
    pfad = pdf(get_storage_path(kennung) / "buch.pdf", seiten)
    save_fulltext(kennung, pdf_volltext(pfad))
    return nr


async def _seiten(buch: int) -> dict[int, str]:
    return {z["seite"]: z["stand"] for z in await db.fetch_all("SELECT seite, stand FROM texterkennung_seite WHERE book_id = ?", (buch,))}


def _reihenfolge(kennung: str) -> list[int]:
    return [int(z.split('"seite":')[1].split(",")[0]) for z in ablage.pfad(kennung).read_text(encoding="utf-8").splitlines()]


async def _alles() -> None:
    await erkennungswache.runde()
    await texterkennung.warten()


async def test_scan_wird_erkannt_und_alles_zieht_nach(laufend, test_db, client, programm, vorgemerkt):  # noqa: F811
    scan = await _buch(test_db, "erkennung00scan", scan_pdf, ["", "", ""])
    eigen = await _buch(test_db, "erkennung00eigen", text_pdf, [SATZ, SATZ])
    get_sidecar_path("erkennung00scan", BEGLEITER).write_text("{}", encoding="utf-8")
    vorher = (await db.fetch_one("SELECT updated_at FROM books WHERE id = ?", (scan,)))["updated_at"]
    wartet = (await client.get(f"/api/books/{scan}/textseiten", params={"ab": 1, "anzahl": 3})).json()["seiten"]
    assert [s["schicht"] for s in wartet] == ["wartet"] * 3            # noch nicht durchgesehen, laut Volltext ein Scan
    assert (await client.get(f"/api/books/{scan}")).json()["scan"] is False   # als Scan gilt es erst nach dem Durchsehen (BF-123)

    await asyncio.sleep(1.1)                                            # updated_at zählt Sekunden
    vorgemerkt.clear()                                                  # das Öffnen der Textansicht merkt selbst vor
    await _alles()

    assert await _seiten(scan) == {1: "erkannt", 2: "erkannt", 3: "erkannt"} and await _seiten(eigen) == {}
    befund = {z["book_id"]: (z["scan"], z["ohne_text"], z["fertig_am"] is not None)
              for z in await db.fetch_all("SELECT book_id, scan, ohne_text, fertig_am FROM texterkennung_buch")}
    assert befund == {scan: (1, 3, True), eigen: (0, 0, False)}
    # Der Leser zeigt einen Scan nur im Original (BF-123)
    assert [(await client.get(f"/api/books/{b}")).json()["scan"] for b in (scan, eigen)] == [True, False]
    assert len(programm.aufrufe()) == 3                                 # nur die Seiten des Scans
    text = load_fulltext("erkennung00scan")
    assert text.count("\f") == 2 and text.split("\f")[1].endswith("putzt das Glas.") and WORT in text.split("\f")[0]
    assert not get_sidecar_path("erkennung00scan", BEGLEITER).exists()  # die gedruckten Seiten ergeben sich neu
    zeile = await db.fetch_one("SELECT page_count, updated_at FROM books WHERE id = ?", (scan,))
    assert zeile["page_count"] == 3 and zeile["updated_at"] > vorher     # der Auszug geht nachts neu in die Kellerwolke
    treffer = await db.fetch_all(f"SELECT rowid FROM suche.buch_fts WHERE buch_fts MATCH '{WORT}'")
    assert [z["rowid"] for z in treffer] == [scan]
    assert vorgemerkt == [scan]

    seiten = (await client.get(f"/api/books/{scan}/textseiten", params={"ab": 1, "anzahl": 3})).json()["seiten"]
    assert [s["schicht"] for s in seiten] == ["erkannt"] * 3
    assert [b["art"] for b in seiten[0]["bausteine"]] == ["ueberschrift", "absatz"] and WORT in seiten[0]["bausteine"][1]["text"]
    eigene = (await client.get(f"/api/books/{eigen}/textseiten", params={"ab": 1, "anzahl": 2})).json()["seiten"]
    assert [s["schicht"] for s in eigene] == ["pdf", "pdf"]

    stand = next(a for a in (await client.get("/api/einrichtung/auftraege")).json() if a["art"] == "texterkennung")
    assert (stand["stand"], stand["was"], stand["gesamt"], stand["fertig"]) == ("fertig", "Texte erkennen", 3, 3)
    assert {t["schluessel"]: (t["fertig"], t["gesamt"]) for t in stand["teile"]} == {
        "buecher": (2, 2), "erkannt": (3, 3), "leer": (0, 3), "fehler": (0, 3)}

    await _alles()
    assert len(programm.aufrufe()) == 3 and len(_reihenfolge("erkennung00scan")) == 3   # nichts wird neu erkannt


async def test_vorrang_fuer_die_gelesenen_seiten(laufend, test_db, client, programm, vorgemerkt):  # noqa: F811
    scan = await _buch(test_db, "erkennung00vorrang", scan_pdf, [""] * 6)
    r = await client.post(f"/api/books/{scan}/texterkennung/vorrang", json={"seite": 4})
    assert r.status_code == 200, r.text
    assert r.json() == {"bereit": True, "grund": "", "von": 4, "bis": 5, "wartet": [4, 5]}
    await texterkennung.warten()
    assert _reihenfolge("erkennung00vorrang")[:2] == [4, 5]             # erst die gelesene und die nächste, dann Buch für Buch
    assert sorted(_reihenfolge("erkennung00vorrang")) == [1, 2, 3, 4, 5, 6]
    assert (await client.post(f"/api/books/{scan}/texterkennung/vorrang", json={"seite": 4})).json()["wartet"] == []
    assert await db.fetch_one("SELECT 1 FROM texterkennung_vorrang") is None   # erledigte Bitten fallen weg

    eigen = await _buch(test_db, "erkennung00epub", text_pdf, [SATZ])
    await db.execute("UPDATE books SET file_format = 'epub' WHERE id = ?", (eigen,))
    await db.commit()
    assert (await client.post(f"/api/books/{eigen}/texterkennung/vorrang", json={"seite": 1})).status_code == 422
    assert (await client.post("/api/books/999999/texterkennung/vorrang", json={"seite": 1})).status_code == 404
    assert (await client.post(f"/api/books/{scan}/texterkennung/vorrang", json={"seite": 0})).status_code == 422


async def test_vorrang_nur_fuer_buecher_die_das_profil_sieht(client, test_db, orte, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "texterkennung_programm", "gibt-es-hier-nicht-0815")
    f = await familie_anlegen(client, test_db)
    await sichtbar.privat_setzen(f.ids["bert"], f.buch["zebra"], True)
    await db.commit()
    weg = f"/api/books/{f.buch['zebra']}/texterkennung/vorrang"
    assert (await client.post(weg, json={"seite": 1}, headers=f.kopf["ada"])).status_code == 404
    assert (await client.post(weg, json={"seite": 1}, headers=f.kopf["bert"])).status_code == 200
    steuer = f"/api/books/{f.buch['steuer']}/texterkennung/vorrang"
    assert (await client.post(steuer, json={"seite": 1}, headers=f.kopf["clara"])).status_code == 404
    mond = f"/api/books/{f.buch['mond']}/texterkennung/vorrang"
    assert (await client.post(mond, json={"seite": 1}, headers=f.kopf["clara"])).status_code == 200


async def test_ohne_programm_ruht_er_mit_grund_und_geht_danach_weiter(laufend, test_db, client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "texterkennung_programm", "gibt-es-hier-nicht-0815")
    scan = await _buch(test_db, "erkennung00ohne", scan_pdf, ["", ""])
    await _alles()
    stand = await texterkennung.stand()
    assert (stand.stand, stand.grund, stand.gesamt, stand.fertig) == ("pause", werkzeug.NICHT_EINGERICHTET, 2, 0)
    seiten = (await client.get(f"/api/books/{scan}/textseiten", params={"ab": 1, "anzahl": 2})).json()["seiten"]
    assert [s["schicht"] for s in seiten] == ["ohne", "ohne"]          # der Hinweis von heute
    r = (await client.post(f"/api/books/{scan}/texterkennung/vorrang", json={"seite": 1})).json()
    assert (r["bereit"], r["grund"], r["wartet"]) == (False, werkzeug.NICHT_EINGERICHTET, [])

    attrappe_anlegen(laufend / "programm", monkeypatch).liefert(ERKANNT)
    await _alles()
    assert (await texterkennung.stand()).stand == "fertig" and await _seiten(scan) == {1: "erkannt", 2: "erkannt"}


async def test_von_hand_angehalten_bleibt_er_stehen_und_geht_nach_neustart_weiter(laufend, test_db, client, programm,  # noqa: F811
                                                                                  vorgemerkt, monkeypatch):
    monkeypatch.setattr(settings, "texterkennung_abstand_s", 0.3)       # Zeit zum Anhalten zwischen zwei Seiten
    scan = await _buch(test_db, "erkennung00halt", scan_pdf, [""] * 4)
    await erkennungswache.runde()
    while not (await _seiten(scan)) or "erkannt" not in (await _seiten(scan)).values():
        await asyncio.sleep(0.05)
    r = await client.post("/api/einrichtung/auftraege/texterkennung/pause")
    assert r.status_code == 200 and r.json()["grund"] == ANGEHALTEN
    await texterkennung.warten()
    erkannt = len(programm.aufrufe())
    await _alles()
    assert (await texterkennung.stand()).stand == "pause" and len(programm.aufrufe()) == erkannt
    seiten = (await client.get(f"/api/books/{scan}/textseiten", params={"ab": 1, "anzahl": 4})).json()["seiten"]
    assert "wartet" not in [s["schicht"] for s in seiten]              # angehalten: niemand wartet vergebens

    monkeypatch.setattr(settings, "texterkennung_abstand_s", 0)
    await texterkennung.fortsetzen()
    await texterkennung.stoppen()                                       # Neustart mitten im Lauf
    await db.execute("UPDATE einrichtung_auftrag SET stand = 'laeuft' WHERE art = 'texterkennung'")
    await db.commit()
    await texterkennung.nach_neustart()
    await texterkennung.warten()
    assert (await texterkennung.stand()).stand == "fertig" and set((await _seiten(scan)).values()) == {"erkannt"}
    assert sorted(set(_reihenfolge("erkennung00halt"))) == [1, 2, 3, 4]


async def test_seite_mit_fehler_bleibt_mit_grund_und_kommt_im_naechsten_lauf_wieder(laufend, test_db, programm,  # noqa: F811
                                                                                     vorgemerkt, monkeypatch):
    scan = await _buch(test_db, "erkennung00fehler", scan_pdf, ["", ""])
    monkeypatch.setenv("ATTRAPPE_CODE", "2")
    await _alles()
    zeilen = await db.fetch_all("SELECT stand, grund FROM texterkennung_seite WHERE book_id = ?", (scan,))
    assert {(z["stand"], z["grund"]) for z in zeilen} == {("fehler", "Die Texterkennung brach ab (Code 2)")}
    assert (await texterkennung.stand()).stand == "fertig"
    monkeypatch.setenv("ATTRAPPE_CODE", "0")
    await texterkennung.beginnen()
    await texterkennung.warten()
    assert await _seiten(scan) == {1: "erkannt", 2: "erkannt"}


async def test_erkennung_geht_mit_dem_auszug_in_die_kellerwolke(laufend, test_db, programm, vorgemerkt):  # noqa: F811
    scan = await _buch(test_db, "erkennung00wolke", scan_pdf, [""])
    await _alles()
    with zipfile.ZipFile(io.BytesIO(await auszug.bauen(scan, "erkennung00wolke"))) as z:
        assert "erkennung.jsonl" in z.namelist() and WORT in z.read("erkennung.jsonl").decode("utf-8")
    assert not ist_original(ablage.pfad("erkennung00wolke"))
    gelesen = auszug.lesen(await auszug.bauen(scan, "erkennung00wolke"))
    ablage.pfad("erkennung00wolke").unlink()
    assert auszug.dateien_ablegen("erkennung00wolke", gelesen) == ["erkennung.jsonl"]
    assert sorted(ablage.lesen("erkennung00wolke")) == [1]


async def test_ein_buch_zwischen_letzter_seite_und_nachziehen_wird_nachgezogen(laufend, test_db, programm, vorgemerkt):  # noqa: F811
    scan = await _buch(test_db, "erkennung00nach", scan_pdf, ["", ""])
    await _alles()
    await db.execute("UPDATE texterkennung_buch SET fertig_am = NULL WHERE book_id = ?", (scan,))     # Neustart genau dazwischen
    await db.commit()
    save_fulltext("erkennung00nach", "\f")
    vorgemerkt.clear()
    await _alles()
    assert WORT in load_fulltext("erkennung00nach") and vorgemerkt == [scan] and len(programm.aufrufe()) == 2


async def test_ein_kaputtes_seitenbild_haelt_die_uebrigen_nicht_auf(laufend, test_db, programm, vorgemerkt, monkeypatch):  # noqa: F811
    from backend.app.texterkennung import erkennen

    scan = await _buch(test_db, "erkennung00kaputt", scan_pdf, ["", "", ""])
    echt = erkennen.seitenbild

    def seitenbild(pfad, seite, dpi):
        if seite == 2:
            raise ValueError("kaputt")
        return echt(pfad, seite, dpi)

    monkeypatch.setattr(erkennen, "seitenbild", seitenbild)
    await _alles()
    assert await _seiten(scan) == {1: "erkannt", 2: "fehler", 3: "erkannt"} and (await texterkennung.stand()).stand == "fertig"
    assert load_fulltext("erkennung00kaputt").split("\f")[1] == ""
