"""Das Deckblatt ist das Bild, das das Buch als Umschlag nennt, nie ein großes Bild aus dem Inneren."""

import io
import zipfile

import fitz
import pytest
from PIL import Image, ImageDraw

from backend.app.services import deckblatt

ROT, BLAU, GRUEN = (200, 20, 20), (20, 20, 200), (20, 160, 20)


def einfarbig(farbe, breite=300, hoehe=450) -> Image.Image:
    return Image.new("RGB", (breite, hoehe), farbe)


def bild(farbe, breite=300, hoehe=450, art="PNG") -> bytes:
    """Eine Fläche in der Farbe mit einem schmalen schwarzen Balken, damit sie nicht leer ist."""
    b = einfarbig(farbe, breite, hoehe)
    ImageDraw.Draw(b).rectangle((0, 0, breite, hoehe // 25), fill=(0, 0, 0))
    p = io.BytesIO()
    b.save(p, format=art)
    return p.getvalue()


def epub(ordner, verzeichnis: str, dateien: dict[str, bytes | str]):
    f = ordner / "buch.epub"
    with zipfile.ZipFile(f, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OEBPS/b.opf"/></rootfiles></container>')
        z.writestr("OEBPS/b.opf", verzeichnis)
        for n, d in dateien.items():
            z.writestr("OEBPS/" + n, d)
    return f


def farbe(daten: bytes | None) -> tuple[int, int, int]:
    assert daten and daten[:2] == b"\xff\xd8", "immer JPEG"
    return Image.open(io.BytesIO(daten)).convert("RGB").resize((1, 1)).getpixel((0, 0))


def nah(a, b) -> bool:
    return all(abs(x - y) < 12 for x, y in zip(a, b))


INNEN = {"img/gross.png": bild(BLAU, 1200, 1600)}


@pytest.mark.parametrize(("verzeichnis", "dateien"), [
    ('<package><manifest><item id="c" href="img/a.png" properties="cover-image"/><item id="g" href="img/gross.png"/></manifest></package>', {}),
    ('<package><metadata><meta name="cover" content="c"/></metadata><manifest><item id="c" href="img/a.png"/></manifest></package>', {}),
    ('<package><metadata><meta name="cover" content="a.png"/></metadata><manifest/></package>', {}),
    ('<package><manifest><item id="u" href="t/u.xhtml"/></manifest><guide><reference type="cover" href="t/u.xhtml"/></guide></package>', {"t/u.xhtml": '<body><svg><image xlink:href="../img/a.png"/></svg></body>'}),
    ('<package><manifest><item id="u" href="t/u.xhtml"/></manifest><spine><itemref idref="u"/></spine></package>', {"t/u.xhtml": '<body><img src="../img/a.png"/></body>'}),
])
def test_genannter_umschlag_gewinnt(tmp_path, verzeichnis, dateien):
    f = epub(tmp_path, verzeichnis, {**INNEN, "img/a.png": bild(ROT), **dateien})
    assert nah(farbe(deckblatt.von_datei(f)), ROT)


def test_breites_oder_winziges_bild_ist_kein_umschlag(tmp_path):
    f = epub(tmp_path, '<package><metadata><meta name="cover" content="q"/></metadata><manifest><item id="q" href="img/quer.png"/><item id="u" href="t/u.xhtml"/></manifest><guide><reference type="cover" href="t/u.xhtml"/></guide></package>',
             {"img/quer.png": bild(BLAU, 1000, 400), "img/a.png": bild(GRUEN), "t/u.xhtml": '<body><img src="../img/a.png"/></body>'})
    assert nah(farbe(deckblatt.von_datei(f)), GRUEN)


def test_ohne_genannten_umschlag_die_erste_seite(tmp_path):
    f = epub(tmp_path, '<package version="2.0"><metadata/><manifest><item id="u" href="u.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="u"/></spine></package>',
             {"u.xhtml": "<html xmlns='http://www.w3.org/1999/xhtml'><body><h1>Amerika</h1><p>" + "Wort " * 200 + "</p></body></html>", **INNEN})
    daten = deckblatt.von_datei(f)
    assert daten and not nah(farbe(daten), BLAU)


def test_pdf_zeigt_die_erste_seite(tmp_path):
    d = fitz.open()
    seite = d.new_page(width=300, height=450)
    seite.draw_rect(fitz.Rect(0, 0, 300, 450), fill=(0.8, 0.1, 0.1), color=None)
    seite.insert_text((30, 60), "Titel", fontsize=24, color=(1, 1, 1))
    d.new_page()
    (tmp_path / "b.pdf").write_bytes(d.tobytes())
    r, g, b = farbe(deckblatt.von_datei(tmp_path / "b.pdf"))
    assert r > 150 and g < 60 and b < 60


def test_kaputte_datei_ohne_deckblatt(tmp_path):
    (tmp_path / "b.epub").write_bytes(b"kein zip")
    assert deckblatt.von_datei(tmp_path / "b.epub") is None


def test_leere_flaeche_ist_kein_deckblatt(tmp_path):
    # BF-17: das genannte Bild fehlt in der Datei, die gezeichnete erste Seite bleibt leer
    f = epub(tmp_path, '<package version="2.0"><metadata><meta name="cover" content="c"/></metadata><manifest><item id="c" href="img/fehlt.jpg"/>'
             '<item id="u" href="u.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="u"/></spine></package>',
             {"u.xhtml": "<html xmlns='http://www.w3.org/1999/xhtml'><head><style>body { margin: 0; background-color: rgb(0, 0, 7) }</style></head>"
                         "<body><div><img alt='Umschlag' src='img/fehlt.jpg' style='height: 100%'/></div></body></html>"})
    assert deckblatt.von_datei(f) is None
    leer = io.BytesIO()
    einfarbig((5, 5, 10)).save(leer, format="JPEG")
    assert deckblatt.taugt(leer.getvalue()) is None


# -- Schlicht (BF-59): fast weiß und farblos bekommt ein gestaltetes Deckblatt ----------------------------------------------

def titelseite(papier=(255, 255, 255), dunkel_anteil=0.1, art="JPEG") -> bytes:
    """Eine Seite in der Farbe des Papiers, oben ein schwarzer Block für den Titel mit dem Anteil an der Fläche."""
    b = einfarbig(papier)
    ImageDraw.Draw(b).rectangle((0, 0, b.width - 1, round(b.height * dunkel_anteil) - 1), fill=(0, 0, 0))
    p = io.BytesIO()
    b.save(p, format=art, quality=95)
    return p.getvalue()


def streifen(weisse_spalten: int) -> bytes:
    """Genau in der Größe des Befunds: links weiße Spalten, rechts schwarze (so zählt jeder Bildpunkt)."""
    b = Image.new("RGB", deckblatt.SCHLICHT_GROESSE, (0, 0, 0))
    ImageDraw.Draw(b).rectangle((0, 0, weisse_spalten - 1, b.height - 1), fill=(255, 255, 255))
    p = io.BytesIO()
    b.save(p, format="PNG")
    return p.getvalue()


@pytest.mark.parametrize(("daten", "erwartet"), [
    pytest.param(titelseite(), True, id="weiß mit Titel"),
    pytest.param(titelseite(art="PNG"), True, id="weiß mit Titel, PNG"),
    pytest.param(titelseite((235, 235, 235)), True, id="hellgrau"),
    pytest.param(titelseite((255, 240, 240)), True, id="ein Hauch Farbe"),              # mittlere Sättigung 0,06
    pytest.param(titelseite(dunkel_anteil=0.2), False, id="zu viel Dunkles"),
    pytest.param(titelseite((225, 225, 225)), False, id="nicht hell genug"),
    pytest.param(titelseite((255, 225, 225)), False, id="hell, aber rosa"),             # mittlere Sättigung 0,1
    pytest.param(titelseite((255, 250, 200)), False, id="hell und gelb"),
    pytest.param(bild(ROT), False, id="rot"),
    pytest.param(b"kein Bild", True, id="unlesbar wie fehlend"),
])
def test_schlicht(daten, erwartet):
    assert deckblatt.schlicht(daten) is erwartet


def test_schlicht_ab_85_prozent_weiss():
    breite = deckblatt.SCHLICHT_GROESSE[0]
    assert deckblatt.schlicht(streifen(round(breite * 0.85)))         # 51 von 60 Spalten
    assert not deckblatt.schlicht(streifen(round(breite * 0.85) - 1))
