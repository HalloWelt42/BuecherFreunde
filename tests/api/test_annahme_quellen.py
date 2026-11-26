"""Eine Auftragsliste für alle Quellen (BF-8): Ordner auf dem Gerät und gemeinfreie Bücher laufen durch dieselbe Annahme wie
das Hochladen; Dateien aus Ordnern bleiben, wo sie sind; wartende Aufträge gehen nach einem Neustart weiter."""

import fitz
import pytest

from backend.app.annahme import gemeinfrei
from backend.app.annahme.dienst import annahme
from backend.app.core.config import settings
from tests.api.test_annahme_api import pdf, warten


@pytest.fixture
def einlese_ordner(tmp_path, monkeypatch):
    ordner = tmp_path / "einlesen"
    (ordner / "unter").mkdir(parents=True)
    monkeypatch.setattr(settings, "import_dir", ordner)
    return ordner


async def test_ordner_ueber_die_annahme(annahme_dienst, auth_headers, einlese_ordner):
    (einlese_ordner / "Erstes Buch.pdf").write_bytes(pdf("Ordner Eins"))
    (einlese_ordner / "unter" / "Zweites Buch.pdf").write_bytes(pdf("Ordner Zwei"))
    (einlese_ordner / "notiz.docx").write_bytes(b"kein Buch")
    r = (await annahme_dienst.post("/api/import/scan", headers=auth_headers)).json()
    assert r == {"gefunden": 2, "neu": 2}
    liste = (await annahme_dienst.get("/api/annahme", headers=auth_headers)).json()["eintraege"]
    assert {e["name"] for e in liste} == {"Erstes Buch.pdf", "Zweites Buch.pdf"} and {e["quelle"] for e in liste} == {"ordner"}
    for e in liste:
        z = await warten(annahme_dienst, auth_headers, e["id"])
        assert z["stand"] == "fertig" and z["buch_id"] and z["sha256"]
    assert (einlese_ordner / "Erstes Buch.pdf").exists()                     # die Datei bleibt im Ordner
    assert (await annahme_dienst.post("/api/import/scan", headers=auth_headers)).json() == {"gefunden": 2, "neu": 0}
    vorschau = (await annahme_dienst.get("/api/import/vorschau", headers=auth_headers)).json()
    assert vorschau["gesamt"] == 2 and vorschau["duplikate"] == 2
    for weg in ("/api/import/upload", "/api/import/upload-mehrere", "/api/import/status"):
        assert (await annahme_dienst.post(weg, headers=auth_headers)).status_code in (404, 405)


async def test_gleicher_inhalt_im_ordner_ist_schon_da(annahme_dienst, auth_headers, einlese_ordner):
    inhalt = pdf("Zweimal")
    (einlese_ordner / "a.pdf").write_bytes(inhalt)
    (einlese_ordner / "unter" / "b.pdf").write_bytes(inhalt)
    await annahme_dienst.post("/api/import/scan", headers=auth_headers)
    staende = []
    for e in (await annahme_dienst.get("/api/annahme", headers=auth_headers)).json()["eintraege"]:
        staende.append((await warten(annahme_dienst, auth_headers, e["id"]))["stand"])
    assert sorted(staende) == ["da", "fertig"]


async def test_gemeinfreie_buecher_ueber_die_annahme(annahme_dienst, auth_headers, test_db, tmp_path, monkeypatch):
    async def holen(nummer, adresse):
        assert (nummer, adresse) == (1342, "https://www.gutenberg.org/ebooks/1342.txt.utf-8")
        datei = tmp_path / "geholt.txt"
        datei.write_text("Stolz und Vorurteil\n\nEs ist eine allgemein anerkannte Wahrheit, dass ein Junggeselle im Besitz eines "
                         "schönen Vermögens nichts dringender braucht als eine Frau.\n" * 20, encoding="utf-8")
        return datei

    async def kein_umschlag(_adresse):
        return None

    monkeypatch.setattr(gemeinfrei, "download_buch", holen)
    monkeypatch.setattr(gemeinfrei, "download_cover", kein_umschlag)
    buch = {"gutenberg_id": 1342, "titel": "Stolz und Vorurteil", "download_url": "https://www.gutenberg.org/ebooks/1342.txt.utf-8",
            "cover_url": "https://www.gutenberg.org/cache/epub/1342/cover.jpg"}
    r = (await annahme_dienst.post("/api/gutenberg/import", headers=auth_headers, json={"buecher": [buch, {"gutenberg_id": 7, "titel": "Ohne Datei"}]})).json()
    assert r == {"gestartet": True, "anzahl": 2}
    eintraege = {e["name"]: e for e in (await annahme_dienst.get("/api/annahme", headers=auth_headers)).json()["eintraege"]}
    assert eintraege["Ohne Datei.epub"]["stand"] == "fehler"
    z = await warten(annahme_dienst, auth_headers, eintraege["Stolz und Vorurteil.txt"]["id"])
    assert z["stand"] == "fertig" and z["quelle"] == "gemeinfrei"
    zeile = await test_db.fetch_one("SELECT gutenberg_id FROM books WHERE id = ?", (z["buch_id"],))
    regal = await test_db.fetch_one("SELECT c.slug FROM categories c JOIN book_categories x ON x.category_id = c.id WHERE x.book_id = ? AND c.slug = 'gutenberg'",
                                    (z["buch_id"],))
    assert zeile["gutenberg_id"] == 1342 and regal
    nochmal = (await annahme_dienst.post("/api/gutenberg/import", headers=auth_headers, json={"buecher": [buch]})).json()
    assert nochmal == {"gestartet": True, "anzahl": 1}
    neu = (await annahme_dienst.get("/api/annahme", headers=auth_headers)).json()["eintraege"][0]
    assert neu["stand"] == "da" and neu["buch_id"] == z["buch_id"]
    for weg in ("/api/gutenberg/import/status", "/api/gutenberg/import/reset"):
        assert (await annahme_dienst.get(weg, headers=auth_headers)).status_code in (404, 405)


async def test_wartende_auftraege_gehen_nach_dem_start_weiter(client, auth_headers, tmp_path, monkeypatch, einlese_ordner):
    for ort in ("storage_dir", "umschlaege_dir", "zwischen_dir"):
        monkeypatch.setattr(settings, ort, tmp_path / ort)
    (einlese_ordner / "Wartet.pdf").write_bytes(pdf("Wartet"))
    await client.post("/api/import/scan", headers=auth_headers)                 # die Annahme läuft noch nicht: der Auftrag wartet
    eintrag = (await client.get("/api/annahme", headers=auth_headers)).json()["eintraege"][0]
    assert eintrag["stand"] == "liest"
    annahme.starten()                                                         # wie nach einem Neustart
    try:
        assert (await warten(client, auth_headers, eintrag["id"]))["stand"] == "fertig"
    finally:
        await annahme.stoppen()


def test_pdf_hilfe_ist_lesbar():
    assert fitz.open(stream=pdf("x"), filetype="pdf").page_count == 2
