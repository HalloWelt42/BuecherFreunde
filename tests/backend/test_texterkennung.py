"""Texterkennung (BF-109): TSV des Programms in PDF-Punkten, Ablage nur angehängt, eine Textschicht für alle Leser, und was die
Textansicht aus einer erkannten Seite macht (Absätze, Trennung, Überschriften, Listen, Kopf- und Fußzeilen, Bilder). Das Programm
selbst als Attrappe (ein eigener Prozess) und, wo es auf dem Gerät ist, echt. Alle Seiten und Texte sind erfunden."""

from __future__ import annotations

import asyncio

import fitz
import pytest

from backend.app.codestellen.erkennung import erkennen as codestellen_erkennen
from backend.app.core.config import settings
from backend.app.services.seiten import pdf_seitentexte
from backend.app.services.textansicht import seiten_lesen, seitenaufbau
from backend.app.texterkennung import ablage, werkzeug
from backend.app.texterkennung.erkennen import aus_tsv, seite_erkennen
from backend.app.texterkennung.textschicht import erkannter_text, ist_scan, ohne_lesbaren_text, schicht_aus
from tests.texterkennung_hilfen import ECHT, Probezeile, attrappe_anlegen, braucht_programm, erkennung, scan_pdf, tsv

LINKS, RECHTS = 72.0, 523.0
SATZ = ("Am Rand der kleinen Insel steht ein Leuchtturm, der den Schiffen in jeder Nacht den Weg zum Hafen zeigt, auch "
        "wenn der Nebel dicht ist.")


@pytest.fixture(autouse=True)
def frisch():
    werkzeug.vergessen()
    yield
    werkzeug.vergessen()


def volle_zeilen(text: str, basis: float, groesse: float = 11.0, schritt: float = 14.0, block: int = 2) -> list[Probezeile]:
    """Wörter auf Zeilen bis zum rechten Rand verteilt (jede Zeile voll, wie im Blocksatz)."""
    zeilen, laufend = [], ""
    for wort in text.split():
        probe = f"{laufend} {wort}".strip()
        if laufend and fitz.get_text_length(probe, fontname="helv", fontsize=groesse) > RECHTS - LINKS:
            zeilen.append(laufend)
            laufend = wort
        else:
            laufend = probe
    zeilen.append(laufend)
    return [Probezeile(z, LINKS, basis + i * schritt, groesse, block=block) for i, z in enumerate(zeilen)]


def leere_seite_mit_bild(pfad) -> fitz.Document:
    return fitz.open(scan_pdf(pfad, [""]))


# -- Programm und TSV --------------------------------------------------------------------------------------------------------

def test_tsv_wird_zu_zeilen_in_pdf_punkten():
    zeilen = [Probezeile("Erste Zeile", 72, 100), Probezeile("ganz " + chr(0xFB01) + "nster", 72, 114, block=1, absatz=2)]
    erkannt, flaechen = aus_tsv(tsv(zeilen, flaechen=[(100, 300, 400, 500)]), fitz.Rect(0, 0, 595, 842), 300)
    assert [[w.text for w in z.woerter] for z in erkannt] == [["Erste", "Zeile"], ["ganz", "finster"]]   # Ligatur als Buchstaben
    assert [(z.block, z.absatz) for z in erkannt] == [(1, 1), (1, 2)]
    erstes = erkannt[0].woerter[0]
    assert erstes.lage[0] == pytest.approx(72, abs=0.5) and erstes.lage[3] == pytest.approx(100, abs=0.5) and erstes.sicherheit == 96
    assert [tuple(round(v) for v in f) for f in flaechen] == [(100, 300, 400, 500)]     # Blöcke ohne Wort sind Flächen


async def test_ohne_programm_ruht_die_erkennung_mit_grund(monkeypatch):
    monkeypatch.setattr(settings, "texterkennung_programm", "gibt-es-hier-nicht-0815")
    stand = await werkzeug.bereitschaft()
    assert not stand.bereit and stand.grund == werkzeug.NICHT_EINGERICHTET
    with pytest.raises(werkzeug.WerkzeugFehlt):
        await werkzeug.tsv(b"\x89PNG", 300)


async def test_fehlende_sprachdaten_werden_genannt(tmp_path, monkeypatch):
    attrappe_anlegen(tmp_path / "programm", monkeypatch)
    monkeypatch.setenv("ATTRAPPE_SPRACHEN", "eng osd")
    stand = await werkzeug.bereitschaft()
    assert not stand.bereit and "deu" in stand.grund and "eng" not in stand.grund


async def test_eine_seite_ueber_den_prozess(tmp_path, monkeypatch):
    a = attrappe_anlegen(tmp_path / "programm", monkeypatch)
    monkeypatch.setattr(settings, "texterkennung_kerne", 2)
    a.liefert([Probezeile("Hallo Leuchtturm", 72, 120)])
    e = await seite_erkennen(scan_pdf(tmp_path / "scan.pdf", ["Hallo Leuchtturm"]), 1)
    assert (e.seite, e.herkunft, e.werkzeug, e.fassung, e.sprachen, e.dpi) == (1, "klassisch", "tesseract", "5.3.0", "deu+eng", 300)
    assert erkannter_text(e) == "Hallo Leuchtturm" and e.erkannt_am.endswith("Z") and e.dauer_s >= 0
    aufruf = a.aufrufe()[-1]
    assert "stdin stdout --dpi 300 -l deu+eng --psm 3 tsv" in aufruf and "OMP=2" in aufruf and "PNG=True" in aufruf


async def test_frist_und_abbruch_geben_einen_grund(tmp_path, monkeypatch):
    attrappe_anlegen(tmp_path / "programm", monkeypatch)
    pfad = scan_pdf(tmp_path / "scan.pdf", ["x"])
    monkeypatch.setattr(settings, "texterkennung_frist_s", 0.3)
    monkeypatch.setenv("ATTRAPPE_SCHLAF", "5")
    with pytest.raises(werkzeug.Erkennungsfehler, match="länger als 0.3 s"):
        await seite_erkennen(pfad, 1)
    monkeypatch.setenv("ATTRAPPE_SCHLAF", "0")
    monkeypatch.setenv("ATTRAPPE_CODE", "3")
    with pytest.raises(werkzeug.Erkennungsfehler, match="brach ab"):
        await seite_erkennen(pfad, 1)
    with pytest.raises(IndexError):
        await seite_erkennen(pfad, 9)


# -- Ablage ----------------------------------------------------------------------------------------------------------------

def test_ablage_haengt_nur_an_und_die_juengste_zeile_gilt(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "texte")
    alt, neu = erkennung(3, [Probezeile("alter Text", 72, 100)]), erkennung(3, [Probezeile("neuer Text", 72, 100)])
    for e in (alt, erkennung(4, [Probezeile("vier", 72, 100)]), neu):
        ablage.anhaengen("abhash01", e)
    with ablage.pfad("abhash01").open("a", encoding="utf-8") as f:
        f.write('{"seite": 5, "abgebrochen\n')
    gelesen = ablage.lesen("abhash01")
    assert sorted(gelesen) == [3, 4] and erkannter_text(gelesen[3]) == "neuer Text"
    assert len(ablage.pfad("abhash01").read_text(encoding="utf-8").splitlines()) == 4          # nichts überschrieben
    assert ablage.pfad("abhash01").parent == ablage.pfad("abhash01").parent.parent / "abhash01"
    assert ablage.lesen("gibtsnicht") == {}


# -- Eine Textschicht ------------------------------------------------------------------------------------------------------

def test_regel_seite_ohne_lesbaren_text(monkeypatch):
    salat = "".join(chr(c) for c in (0x19, 0x12, 0x13, 0x10, 0x06, 0x01, 0x14, 0x16, 0x0E)) * 5
    assert ohne_lesbaren_text("") and ohne_lesbaren_text("  17  ") and ohne_lesbaren_text(salat)
    assert ohne_lesbaren_text("Kapitel 3") and not ohne_lesbaren_text(SATZ)
    monkeypatch.setattr(settings, "texterkennung_mindestzeichen", 5)
    assert not ohne_lesbaren_text("Kapitel 3")


def test_scan_nach_anteil_der_seiten_ohne_text(monkeypatch):
    assert ist_scan(10, 10) and ist_scan(5, 10) and not ist_scan(4, 10) and not ist_scan(0, 10)
    monkeypatch.setattr(settings, "texterkennung_scan_anteil", 0.0)
    assert ist_scan(1, 300) and not ist_scan(0, 300)


def test_erkennung_gilt_nur_fuer_eine_seite_ohne_lesbaren_text():
    e = erkennung(1, [Probezeile(SATZ, 72, 100)])
    assert schicht_aus(SATZ, e).art == "pdf"                              # eigene Textschicht: die Erkennung zählt nicht
    gilt = schicht_aus("", e)
    assert (gilt.art, gilt.text, gilt.erkennung) == ("erkannt", SATZ, e)
    unsicher = erkennung(1, [Probezeile("Rauschen im Bild", 72, 100)], sicherheit=5)
    assert schicht_aus("", unsicher).art == "ohne" and schicht_aus("", None).art == "ohne"


def test_volltext_nimmt_fuer_scans_die_erkennung(tmp_path):
    doc = fitz.open(scan_pdf(tmp_path / "scan.pdf", ["", ""]))
    doc[1].insert_textbox(fitz.Rect(72, 90, 523, 780), SATZ, fontname="helv", fontsize=11)      # Seite 2 mit Textschicht
    doc.save(tmp_path / "gemischt.pdf")
    erkannt = {1: erkennung(1, [Probezeile("Erkannt auf Seite eins mit genug Wörtern.", 72, 100)]),
               2: erkennung(2, [Probezeile("Diese Erkennung zählt nicht.", 72, 100)])}
    texte = pdf_seitentexte(tmp_path / "gemischt.pdf", erkannt)
    assert texte[0] == "Erkannt auf Seite eins mit genug Wörtern." and "Leuchtturm" in texte[1]
    assert pdf_seitentexte(tmp_path / "gemischt.pdf")[0] == ""


# -- Textansicht einer erkannten Seite -------------------------------------------------------------------------------------

def _erkannte_seite() -> list[Probezeile]:
    zeilen = [Probezeile("3 Kapitel über den Leuchtturm", 72, 40, 9, block=1)]                       # Kopfzeile
    zeilen.append(Probezeile("3.1 Die Insel vor Beispielhausen", LINKS, 110, 18, block=2))                     # Überschrift
    absatz = volle_zeilen(SATZ + " Die Wärterin steigt jeden Abend die hundert Stufen hinauf und putzt das Glas der Lam-",
                          140, block=3)
    absatz.append(Probezeile("pe, bevor es dunkel wird.", LINKS, absatz[-1].basis + 14, block=3))
    liste = [Probezeile(chr(0xAB) + " Erstens prüft sie den Docht.", LINKS, absatz[-1].basis + 30, block=4),
             Probezeile("+ Zweitens füllt sie das Öl nach.", LINKS, absatz[-1].basis + 44, block=4)]
    return zeilen + absatz + liste + [Probezeile("17", 290, 815, 9, block=9)]                       # Fußzeile


def test_erkannte_seite_wird_absaetze_ueberschrift_und_liste(tmp_path):
    seite = leere_seite_mit_bild(tmp_path / "scan.pdf")[0]
    e = erkennung(1, _erkannte_seite(), flaechen=[(150, 450, 450, 650), (72, 60, 523, 61)])
    bausteine = seitenaufbau(seite, erkennung=e)
    assert [b.art for b in bausteine] == ["ueberschrift", "absatz", "absatz", "absatz", "bild"]
    assert bausteine[0].text == "3.1 Die Insel vor Beispielhausen"
    assert bausteine[1].text.startswith("Am Rand der kleinen Insel") and bausteine[1].text.endswith("Glas der Lampe, bevor es dunkel wird.")
    assert [b.text for b in bausteine[2:4]] == [chr(0x2022) + " Erstens prüft sie den Docht.", chr(0x2022) + " Zweitens füllt sie das Öl nach."]
    assert bausteine[4].rechteck.width < 320                     # eine Bildfläche der Erkennung, nicht das Seitenbild
    assert not any("Kapitel über" in b.text or b.text == "17" for b in bausteine)                     # Kopf- und Fußzeile weg


def test_ohne_erkennung_bleibt_das_seitenbild_wie_bisher(tmp_path):
    seite = leere_seite_mit_bild(tmp_path / "scan.pdf")[0]
    assert [b.art for b in seitenaufbau(seite)] == ["bild"]
    pfad = tmp_path / "scan.pdf"
    _, seiten = seiten_lesen(pfad, 1, 1, erkennungen={1: erkennung(1, _erkannte_seite())})
    assert seiten[0].schicht == "erkannt" and seiten[0].bausteine[0].art == "ueberschrift"
    _, seiten = seiten_lesen(pfad, 1, 1)
    assert seiten[0].schicht == "ohne"


def test_codestellen_lesen_erkannte_seiten(tmp_path):
    pfad = scan_pdf(tmp_path / "scan.pdf", [""])
    code = ["anzahl = 3", "for i in range(anzahl):", "    print(i * 2)", "summe = sum(range(anzahl))"]
    zeilen = volle_zeilen(SATZ, 120) + [Probezeile(z, LINKS + (20 if z.startswith(" ") else 0), 200 + i * 14, block=5 + i)
                                        for i, z in enumerate(code)]
    for z in zeilen[-4:]:
        z.text = z.text.strip()
    begleiter = codestellen_erkennen(pfad, "pdf", {1: erkennung(1, zeilen)})
    assert begleiter.grund == "" and len(begleiter.stellen) == 1
    assert begleiter.stellen[0].code.splitlines()[0] == "anzahl = 3" and begleiter.stellen[0].teile[0].seite == 1
    assert codestellen_erkennen(pfad, "pdf").stellen == []                                          # ohne Erkennung kein Code


# -- Mit dem echten Programm -----------------------------------------------------------------------------------------------

@braucht_programm
async def test_echte_erkennung_einer_erfundenen_seite(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "texterkennung_programm", ECHT)
    vorlage = fitz.open()
    s = vorlage.new_page(width=595, height=842)
    s.insert_text((72, 110), "Die Insel vor Beispielhausen", fontname="helv", fontsize=20)
    s.insert_textbox(fitz.Rect(72, 130, 523, 400), SATZ + " " + SATZ, fontname="helv", fontsize=11)
    scan = fitz.open()
    seite = scan.new_page(width=595, height=842)
    seite.insert_image(seite.rect, pixmap=s.get_pixmap(dpi=150, colorspace=fitz.csGRAY))
    scan.save(tmp_path / "echt.pdf")
    e = await seite_erkennen(tmp_path / "echt.pdf", 1)
    text = erkannter_text(e)
    assert "Leuchtturm" in text and "Nebel" in text
    bausteine = seitenaufbau(fitz.open(tmp_path / "echt.pdf")[0], erkennung=e)
    assert [b.art for b in bausteine] == ["ueberschrift", "absatz"] and bausteine[0].text == "Die Insel vor Beispielhausen"
    assert "Leuchtturm, der den Schiffen" in bausteine[1].text


@braucht_programm
async def test_echte_erkennung_haelt_die_frist(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "texterkennung_programm", ECHT)
    monkeypatch.setattr(settings, "texterkennung_frist_s", 0.001)
    with pytest.raises(werkzeug.Erkennungsfehler, match="länger als"):
        await seite_erkennen(scan_pdf(tmp_path / "frist.pdf", [SATZ]), 1)
    await asyncio.sleep(0)
