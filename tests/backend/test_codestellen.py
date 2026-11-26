"""Codestellen erkennen (BF-29): Kästen, Zeilennummern, Fortsetzung über den Seitenwechsel, Einrückung, Sprache; dazu
Markdown und EPUB. Alle Dateien entstehen hier im Test, keine Buchkopien."""

import fitz

from backend.app.codestellen import pdf
from backend.app.codestellen.auszeichnung import text_bloecke
from backend.app.codestellen.erkennung import aus_auszeichnung, aus_pdf, erkennen
from backend.app.codestellen.sprache import bestimmen

FLIESSTEXT = ("Der folgende Code zählt die Zahlen einer Liste zusammen. Er zeigt, wie eine Schleife einen Wert Schritt für "
              "Schritt aufbaut, und gibt am Ende die Summe aus.")
GROESSE, LINKS = 8.2, 90.0
SPALTE = 0.6 * GROESSE                      # Courier: jedes Zeichen gleich breit


def kasten(seite: fitz.Page, r: fitz.Rect, offen_oben: bool = False, offen_unten: bool = False, titel: str = "") -> None:
    """Wie ein geteilter Kasten im Buch: außen der Rahmen, innen die Fläche; an offenen Kanten liegen beide bündig."""
    seite.draw_rect(r, color=None, fill=(0.2, 0.2, 0.3))
    seite.draw_rect(fitz.Rect(r.x0 + 0.6, r.y0 + (0 if offen_oben else 0.6), r.x1 - 0.6, r.y1 - (0 if offen_unten else 0.6)),
                    color=None, fill=(0.98, 0.98, 0.98))
    if titel:
        seite.insert_text((r.x0 + 24, r.y0 + 3.5), titel, fontname="helv", fontsize=10)


def code(seite: fitz.Page, y: float, text: str, nummer: int | None = None) -> None:
    einzug = len(text) - len(text.lstrip())
    if text.strip():
        seite.insert_text((LINKS + einzug * SPALTE, y), text.strip(), fontname="cour", fontsize=GROESSE)
    if nummer is not None:
        seite.insert_text((78, y), str(nummer), fontname="helv", fontsize=6)


def probebuch(pfad) -> None:
    doc = fitz.open()
    eins = doc.new_page(width=595, height=842)
    eins.insert_text((74, 45), "1 Kapitel über Schleifen", fontsize=9)
    eins.insert_textbox(fitz.Rect(74, 80, 521, 160), FLIESSTEXT, fontsize=10.9)
    kasten(eins, fitz.Rect(74, 640, 521, 790), offen_unten=True, titel="Ausprobieren - kap01/summe.py")
    for i, zeile in enumerate(["def summe(zahlen):", "    gesamt = 0", "    for z in zahlen:", "        gesamt += z"]):
        code(eins, 672 + i * 12.9, zeile, i + 1)
    eins.insert_text((290, 820), "7", fontsize=9)
    zwei = doc.new_page(width=595, height=842)
    zwei.insert_text((74, 45), "1 Kapitel über Schleifen", fontsize=9)
    kasten(zwei, fitz.Rect(74, 70, 521, 120), offen_oben=True)
    for i, (zeile, nr) in enumerate([("    return gesamt", 5), ("", 6), ("print(summe([1, 2, 3]))", 7)]):
        code(zwei, 84 + i * 12.9, zeile, nr)
    zwei.insert_textbox(fitz.Rect(74, 150, 521, 220), FLIESSTEXT, fontsize=10.9)
    for i, zeile in enumerate(["const zahlen = [1, 2, 3];", "const summe = zahlen.reduce((a, b) => a + b, 0);", "console.log(summe);"]):
        code(zwei, 260 + i * 12.9, zeile)
    zwei.insert_textbox(fitz.Rect(74, 320, 521, 380), FLIESSTEXT, fontsize=10.9)
    kasten(zwei, fitz.Rect(74, 420, 521, 460), titel="Ausgabe")
    code(zwei, 445, "6")
    zwei.insert_text((74, 760), "https://example.org/eine/lange/adresse", fontname="cour", fontsize=7)
    zwei.insert_text((290, 820), "8", fontsize=9)
    doc.save(pfad)


def test_kasten_ueber_den_seitenwechsel_mit_nummern_und_einrueckung(tmp_path):
    pfad = tmp_path / "buch.pdf"
    probebuch(pfad)
    stellen = aus_pdf(pfad)
    assert [s.sprache for s in stellen] == ["python", "javascript", "ausgabe"]
    summe = stellen[0]
    assert summe.code == "def summe(zahlen):\n    gesamt = 0\n    for z in zahlen:\n        gesamt += z\n    return gesamt\n\nprint(summe([1, 2, 3]))"
    assert [t.seite for t in summe.teile] == [1, 2]
    assert summe.teile[0].offen_unten and summe.teile[1].offen_oben and not summe.teile[0].offen_oben
    assert summe.titel == "Ausprobieren - kap01/summe.py" and summe.datei == "kap01/summe.py" and summe.quelle == "datei"
    assert summe.zeilennummern_ab == 1 and summe.sicher
    assert summe.kennung.startswith("s1-") and summe.kennung.endswith(summe.pruefsumme[:8])
    assert summe.teile[0].rechteck == [74.0, 640.0, 521.0, 790.0]


def test_ohne_kasten_sprache_aus_dem_inhalt_und_keine_fussnote(tmp_path):
    pfad = tmp_path / "buch.pdf"
    probebuch(pfad)
    js = aus_pdf(pfad)[1]
    assert js.code.splitlines()[1] == "const summe = zahlen.reduce((a, b) => a + b, 0);"
    assert js.quelle == "inhalt" and js.sicher and len(js.teile) == 1
    assert all("example.org" not in s.code for s in aus_pdf(pfad))


def test_unlesbare_datei_gibt_grund(tmp_path):
    kaputt = tmp_path / "kaputt.pdf"
    kaputt.write_bytes(b"kein PDF")
    b = erkennen(kaputt, "pdf")
    assert b.stellen == [] and b.grund.startswith("Datei nicht lesbar")


def zeile(*stuecke: tuple[float, str, bool]) -> pdf.Zeile:
    return pdf.Zeile([pdf.Spanne(x, x + len(t) * SPALTE, 0, 10, 9, GROESSE, t, mono) for x, t, mono in stuecke])


def test_umbrochene_zeilen_werden_angehaengt():
    vorher = zeile((LINKS, "$ini = '/etc/php/conf.d/opcache.", True))
    marke = zeile((LINKS, "↪", False), (LINKS + 1.8 * SPALTE, "ini';", True))
    wort = zeile((LINKS, "$text = 'eine Datei", True))
    weiter = zeile((LINKS, "↪", False), (LINKS + 1.8 * SPALTE, "gelesen';", True))
    for i, z in enumerate([vorher, marke, wort, weiter]):
        for s in z.spannen:
            s.basis = s.y1 = 10 + i * 12.9
    b = pdf.Block(1, [vorher, marke, wort, weiter], None, rand=LINKS)
    text, _ = pdf.text_der_kette([b])
    assert text == "$ini = '/etc/php/conf.d/opcache.ini';\n$text = 'eine Datei gelesen';"


def test_ligaturen_nur_wo_eindeutig():
    assert pdf.ligaturen("^/ Kommentar") == "// Kommentar"
    assert pdf.ligaturen("'<h1>Hallo^/h1>'") == "'<h1>Hallo</h1>'"
    assert pdf.ligaturen("class A { ^* ^^. ^/ }") == "class A { /* ... */ }"
    assert pdf.ligaturen("$a ^? $b; X^:y(); __init__") == "$a ?? $b; X::y(); __init__"
    assert pdf.ligaturen("if a ^= b:") == "if a ^= b:"             # ==, <=, >= oder !=: bleibt, wie es ist


def test_sprache():
    assert bestimmen("x", "Ausgabe").sprache == "ausgabe"
    assert bestimmen("x = 1", "Selbsttest von airtime.py", "airtime.py").sprache == "ausgabe"
    assert bestimmen("x", "python rechner.py --tabelle", "rechner.py").sprache == "shell"
    assert bestimmen("echo 1;", "PHP").sprache == "php"
    assert bestimmen("Ergebnis: 3 Zeilen\nDauer 2 s", "Liste", "liste.php").sicherheit < 0.6     # nennt PHP, zeigt keins
    assert bestimmen("import json\nprint(json.dumps({'a': 1}))").sprache == "python"
    assert bestimmen("$name = 'Ada';\necho \"Hallo $name\";").sprache == "php"
    assert bestimmen('{"a": 1,\n "b": [1, 2]}').sprache == "json"
    assert bestimmen("pip install mlx mlx-lm\ndocker run --rm -it php:8.4-cli").sprache == "shell"
    assert bestimmen("# Nur diese Ziele\nziele = [\"a\", \"b\"]\n[netz]\nerlaubt = true").sprache != "python" or \
        not bestimmen("# Nur diese Ziele\nziele = [\"a\", \"b\"]\n[netz]\nerlaubt = true").sicherheit >= 0.6


def test_markdown_zaeune():
    text = "Text\n\n```python\nprint(1)\n```\n\n~~~ js\nconsole.log(2)\n~~~\n\n```\nohne Angabe\n"
    bloecke = text_bloecke(text)
    assert [(b.sprache, b.code, b.zeile) for b in bloecke] == [("python", "print(1)", 3), ("javascript", "console.log(2)", 7),
                                                                (None, "ohne Angabe", 11)]


def epub_datei(pfad, kapitel: str) -> None:
    """Ein kleinstes EPUB von Hand, damit der Inhalt genau so in der Datei steht."""
    import zipfile

    opf = ('<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
           '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">probe</dc:identifier>'
           '<dc:title>Probe</dc:title><dc:language>de</dc:language></metadata>'
           '<manifest><item id="k1" href="kap1.xhtml" media-type="application/xhtml+xml"/></manifest>'
           '<spine><itemref idref="k1"/></spine></package>')
    container = ('<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
    with zipfile.ZipFile(pfad, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml", container)
        z.writestr("OEBPS/content.opf", opf)
        z.writestr("OEBPS/kap1.xhtml", kapitel)


def test_epub_codebloecke(tmp_path):
    pfad = tmp_path / "probe.epub"
    epub_datei(pfad, '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Listing 1: Hallo</p><pre><code class="language-python">'
                     "print('hallo')\nprint('welt')</code></pre><pre>ohne Sprache</pre></body></html>")
    stellen = aus_auszeichnung(pfad, "epub")
    assert [(s.sprache, s.teile[0].kapitel, s.teile[0].nr, s.titel) for s in stellen][0] == ("python", "kap1.xhtml", 0, "Listing 1: Hallo")
    assert stellen[0].code == "print('hallo')\nprint('welt')" and stellen[0].kennung.startswith("kap1.xhtml#0-")
    assert len(stellen) == 2 and stellen[1].teile[0].nr == 1
