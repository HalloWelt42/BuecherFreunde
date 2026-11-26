"""Übersetzen eines PDF über die Schnittstelle (BF-71): die Rückfrage für ein PDF und für einen Scan, der Lauf mit der
Attrappe der Leitstelle über das erzeugte Probe-PDF bis zum gesetzten deutschen EPUB (Seitenmarken mit den gedruckten Seiten
des Originals, Ablage, Datei für den Leser) und der Bericht mit der Seite im Original. Nur erfundene Texte."""

import re

from backend.app.core.config import settings
from backend.app.services import fassungen
from backend.app.services.ki import ki
from backend.app.services.uebersetzungslauf import Uebersetzungslauf
from backend.app.uebersetzung.zerlegen_pdf import TEXTERKENNUNG
from tests.api.test_ausfuehren import leitstelle  # noqa: F401 - Attrappe der Leitstelle
from tests.api.uebersetzer import DEUTSCH_PDF, orte, probebuch_pdf, uebersetzer  # noqa: F401 - Fixtures
from tests.uebersetzung_probe import dateien
from tests.uebersetzung_probe_pdf import scan_pdf

BLOECKE = 41
WASSER = ("Water that runs off the surface is lost for the plants. A slow drip close to the roots is better than a strong jet "
          "from above, and it also keeps the leaves and the stems quite dry for long hours. Good irrigation<x1/> saves water, "
          "time and power for the next round.")


async def test_folgen_fuer_ein_pdf(client, test_db, uebersetzer):
    buch = await probebuch_pdf(test_db)
    f = (await client.get(f"/api/books/{buch}/fassungen/de/folgen")).json()
    assert {k: f[k] for k in ("seiten", "kapitel", "bloecke", "abbildungen", "geht", "grund")} == {
        "seiten": 5, "kapitel": 3, "bloecke": BLOECKE, "abbildungen": 2, "geht": True, "grund": ""}   # zwei Kapitel und das Verzeichnis
    b = await fassungen.buch(buch)
    assert f["ablage"] == {"ort": "geraet", "pfad": str(settings.storage_dir / b.hash[:2] / b.hash[2:4] / b.hash / "Fassungen" / "de"
                                                         / "Garten.epub")}                         # die Fassung ist ein EPUB


async def test_folgen_fuer_einen_scan(client, test_db, uebersetzer):
    buch = await probebuch_pdf(test_db, pdf=scan_pdf())
    f = (await client.get(f"/api/books/{buch}/fassungen/de/folgen")).json()
    assert f["geht"] is False and f["grund"] == f"Das PDF hat keine Textschicht (Scan): {TEXTERKENNUNG}"
    r = await client.post(f"/api/books/{buch}/fassungen/de")
    assert r.status_code == 422 and r.json()["detail"].endswith(TEXTERKENNUNG)
    assert await fassungen.zum_buch(buch, "de") is None


async def test_lauf_ueber_das_probe_pdf_bis_zum_deutschen_epub(client, test_db, uebersetzer):
    u = uebersetzer
    buch = await probebuch_pdf(test_db)
    r = await client.post(f"/api/books/{buch}/fassungen/de")
    assert r.status_code == 200, r.text
    fid = r.json()["id"]
    assert await Uebersetzungslauf(ki).runde() == 1
    f = await fassungen.holen(fid)
    assert f.stand == "fertig" and f.datei_aktuell and f.zerlegt == fassungen.zerlegt_mit("pdf") and f.zerlegt.endswith(":pdf1")

    # jeder Block übersetzt und geprüft, mit Seite und Lage im Original
    zeilen = {z.kennung: z for z in await fassungen.bloecke(fid)}
    assert len(zeilen) == BLOECKE and {z.stand for z in zeilen.values()} == {"bestanden"}
    assert (zeilen["1.20"].vorlage, zeilen["1.20"].seite, zeilen["1.20"].seite_gedruckt) == (WASSER, 2, "12")
    assert zeilen["1.20"].lage == [72.0, 715.2, 512.8, 742.0]
    assert (zeilen["2.5"].seite, zeilen["2.5"].seite_gedruckt) == (5, "15") and zeilen["3.1"].seite is None
    gesendet = set(u.gesendet())
    assert "from garden import Pump" not in " ".join(gesendet) and _ohne_kopf_und_fuss(gesendet)

    stand = (await client.get(f"/api/fassungen/{fid}/stand")).json()
    assert stand["stationen"][0]["text"] == f"{BLOECKE} Blöcke in 3 Kapiteln"
    assert [(k["titel"], k["bloecke"]) for k in stand["kapitel"]] == [("1 Getting Started", 28), ("2 Watering the Beds", 6),
                                                                      ("Inhaltsverzeichnis", 7)]

    # die deutsche Fassung: ein EPUB neben dem Original, mit Marken für die Seiten des Originals
    b = await fassungen.buch(buch)
    datei = settings.storage_dir / b.hash[:2] / b.hash[2:4] / b.hash / "Fassungen" / "de" / "Garten.epub"
    assert f.datei == str(datei) and datei.is_file()
    epub = dateien(datei.read_bytes())
    k1, k2 = epub["OEBPS/text/k001.xhtml"].decode(), epub["OEBPS/text/k002.xhtml"].decode()
    assert 'lang="de" xml:lang="de"' in k1 and "<dc:language>de</dc:language>" in epub["OEBPS/content.opf"].decode()
    assert '<h1 id="h1" data-bf-seite="1" data-bf-lage="72.0 85.6 233.1 113.1">1 Erste Schritte</h1>' in k1
    assert re.findall(r'id="seite-(\d)" title="(\d+)">Seite (\d+)<', k1 + k2) == [(str(n), str(10 + n), str(10 + n)) for n in range(1, 6)]
    assert re.search(r'Gute Bewässerung<span class="bf-seite"[^>]*id="seite-3"[^>]*>Seite 13</span> spart Wasser', k1)
    assert "<li data-bf-seite=\"1\"" in k1 and '<span class="bf-zeichen" translate="no">\u2022</span> Prüfe die Räder vor jeder Fahrt.' in k1
    assert "<th" in k1 and ">Pflanze</th>" in k1 and "<caption" in k1 and "Tabelle 1: Täglicher Wasserbedarf</caption>" in k1
    assert ">from garden import Pump\n\npump = Pump(port=3)\n" in k1                                 # der Code bleibt Zeichen für Zeichen
    assert "Gemessen an einem trockenen Morgen im Frühsommer." in k1 and "Abbildung 2: Ein Beet bei Sonnenaufgang." in k2
    assert "<a href=\"text/k001.xhtml\">1 Erste Schritte</a>" in epub["OEBPS/nav.xhtml"].decode()
    hinweis = epub["OEBPS/bf-uebersetzung.xhtml"].decode()
    assert "Von uns übersetzt aus dem Englischen." in hinweis and 'Marken wie "Seite 12" zeigen' in hinweis
    assert sorted(p.name for p in datei.parents[2].iterdir()) == ["Fassungen", "Garten.pdf", "fulltext.txt", "seiten.json"]

    # der Leser bekommt die abgelegte Datei
    r = await client.get(f"/api/fassungen/{fid}/datei")
    assert r.status_code == 200 and r.headers["content-type"] == "application/epub+zip" and r.content == datei.read_bytes()
    assert await Uebersetzungslauf(ki).runde() == 0


def _ohne_kopf_und_fuss(gesendet: set[str]) -> bool:
    """Keine Kopf- oder Fußzeile und keine Seitenzahl ging ans Modell."""
    return not any("Gardening with Small Machines" in v or "Chapter notes" in v or re.fullmatch(r"1[1-5]", v) for v in gesendet)


async def test_bericht_nennt_die_seite_im_original(client, test_db, uebersetzer):
    u = uebersetzer
    u.tabelle[WASSER] = DEUTSCH_PDF[WASSER].replace("Bewässerung<x1/>", "Bewässerung")   # ohne Seitenmarke, auch in den Nacharbeiten
    buch = await probebuch_pdf(test_db)
    fid = (await client.post(f"/api/books/{buch}/fassungen/de")).json()["id"]
    await Uebersetzungslauf(ki).runde()
    [offen] = (await client.get(f"/api/fassungen/{fid}/bericht")).json()["offen"]
    assert {k: offen[k] for k in ("kennung", "ort", "seite_original", "seite_gedruckt", "original")} == {
        "kennung": "1.20", "ort": "1 Getting Started, Absatz 20", "seite_original": 2, "seite_gedruckt": "12", "original": WASSER}
    assert [b["art"] for b in offen["befunde"]] == ["marken"]
    # die Stelle steht im Original, markiert, mit ihrer Seitenmarke
    b = await fassungen.buch(buch)
    k1 = dateien((settings.storage_dir / b.hash[:2] / b.hash[2:4] / b.hash / "Fassungen" / "de" / "Garten.epub").read_bytes())[
        "OEBPS/text/k001.xhtml"].decode()
    assert re.search(r'<span class="bf-original" lang="en"[^>]*>Water that runs off.*?Good irrigation<span class="bf-seite"[^>]*>'
                     r"Seite 13</span> saves water", k1)
