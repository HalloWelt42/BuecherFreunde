"""PDF zerlegen und setzen (BF-71, docs/neubau/UEBERSETZUNG.md, Prüfen der Arbeit 3) am erzeugten Probe-PDF
(tests/uebersetzung_probe_pdf.py): Überschriften in drei Stufen, Absätze über Seiten- und Spaltenwechsel, zwei Spalten, Liste,
Tabelle, Code, Fußnote, Abbildungen mit Bildunterschrift, Kopf- und Fußzeile mit Seitenzahl, Silbentrennung. Jeder Block an
seiner Stelle und in Lesefolge, nichts doppelt, nichts fehlt, Kopf und Fuß weg, Seitenmarken richtig; Rundlauf ohne
Übersetzung; Scan und unlesbare PDF."""

import re
from collections import Counter
from html import unescape

import fitz
import pytest
from lxml import etree

from backend.app.uebersetzung import marken, pdf_lesen, werk
from backend.app.uebersetzung.modelle import pruefsumme
from backend.app.uebersetzung.setzen import Hinweis, Satz, Uebersetzt
from backend.app.uebersetzung.zerlegen_epub import NichtLesbar
from backend.app.uebersetzung.zerlegen_pdf import TEXTERKENNUNG, OhneText
from tests.uebersetzung_probe import dateien
from tests.uebersetzung_probe_pdf import (
    ERSTE_GEDRUCKTE, IM_BILD, KOPF, LESEFOLGE, Blatt, probe_pdf, rasterbild, scan_pdf, umbrechen,
)

GEDRUCKT = [str(ERSTE_GEDRUCKTE + i) for i in range(5)]
X = "{http://www.w3.org/1999/xhtml}"
MARKE = re.compile(r'<span class="bf-seite"[^>]*>.*?</span>')
#: Elemente, die für sich stehen: zwischen ihnen steht im Lesetext ein Leerzeichen
FUER_SICH = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "caption", "figcaption", "pre", "aside", "section", "table",
             "tr", "figure", "ul", "ol", "nav", "div", "body"}
BUCHSTABE = re.compile(r"[^\W\d_]")


@pytest.fixture(scope="module")
def probe():
    daten = probe_pdf()
    return daten, list(LESEFOLGE), list(IM_BILD), werk.zerlegen(daten, "pdf", gedruckt=GEDRUCKT)


def blocktext(dok, lauf) -> str:
    """Der Text eines Blocks, wie der Leser ihn sieht (Platzhalter mit ihrem Inhalt), ohne Seitenmarken."""
    stueck = MARKE.sub("", dok.quelle.text[lauf.anfang:lauf.ende])
    return " ".join(unescape(re.sub(r"<[^>]+>", "", stueck)).split())


def inhalt(w):
    return [d for d in w.zerlegung.dokumente if d.rolle == "inhalt"]


def kapiteldateien(epub: bytes) -> list[tuple[str, etree._Element]]:
    """Die Kapitel in der Lesefolge des Pakets, gelesen als XML."""
    teile = dateien(epub)
    opf = etree.fromstring(teile["OEBPS/content.opf"])
    ns = {"o": "http://www.idpf.org/2007/opf"}
    hrefs = {i.get("id"): i.get("href") for i in opf.iterfind(".//o:manifest/o:item", ns)}
    return [(hrefs[r.get("idref")], etree.fromstring(teile[f"OEBPS/{hrefs[r.get('idref')]}"]))
            for r in opf.iterfind(".//o:spine/o:itemref", ns)]


def _text(el: etree._Element) -> str:
    if el.get("class") == "bf-seite":
        return ""
    t = (el.text or "") + "".join(_text(k) + (k.tail or "") for k in el)
    return f" {t} " if el.tag.removeprefix(X) in FUER_SICH else t


def lesetext(epub: bytes) -> str:
    """Der ganze Text der Kapitel wie für den Leser, ohne Seitenmarken und ohne das Blatt "Über diese Übersetzung"."""
    teile = [_text(baum.find(f"{X}body")) for pfad, baum in kapiteldateien(epub) if "bf-uebersetzung" not in pfad]
    return " ".join(" ".join(teile).split())


def seitenmarken(epub: bytes) -> list[tuple[str, str, str, str]]:
    return [(pfad.rsplit("/", 1)[-1], el.get("id"), el.get("title"), el.text) for pfad, baum in kapiteldateien(epub)
            for el in baum.iter(f"{X}span") if el.get("class") == "bf-seite"]


def pdf_woerter(daten: bytes, im_bild: list[tuple[int, fitz.Rect]]) -> Counter:
    """Die Wörter der Textschicht ohne Kopf- und Fußzeile und ohne die Wörter im Bild, Trennungen am Zeilenende verbunden."""
    folge = []
    with fitz.open(stream=daten, filetype="pdf") as doc:
        for seite in doc:
            for w in seite.get_text("words", sort=False):
                r = fitz.Rect(w[:4])
                if r.y1 < 50 or r.y0 > 800 or any(n == seite.number + 1 and r.intersects(f) for n, f in im_bild):
                    continue
                folge.append(w[4])
    verbunden = []
    for w in folge:
        if verbunden and verbunden[-1].endswith("-") and w[:1].islower():
            verbunden[-1] = verbunden[-1][:-1] + w
        else:
            verbunden.append(w)
    return Counter(verbunden)


# -- Blöcke -------------------------------------------------------------------------------------------------------------------

def test_bloecke_in_lesefolge_an_ihrer_stelle(probe):
    _, lesefolge, _, w = probe
    assert [(d.kapitel, d.rolle, d.titel) for d in w.zerlegung.dokumente] == [
        (1, "inhalt", "1 Getting Started"), (2, "inhalt", "2 Watering the Beds"), (3, "verzeichnis", "Inhaltsverzeichnis")]
    lagen = {b.kennung: b for b in w.bloecke()}
    gefunden = [(lagen[d.kennung(i)].art, lagen[d.kennung(i)].stufe, blocktext(d, l), lagen[d.kennung(i)].seite, lagen[d.kennung(i)].gedruckt)
                for d in inhalt(w) for i, l in enumerate(d.laeufe, 1)]
    erwartet = [(e.art, e.stufe, e.text, e.seite, str(ERSTE_GEDRUCKTE + e.seite - 1)) for e in lesefolge
                if e.art != "code" and BUCHSTABE.search(e.text)]                 # Zellen nur mit Zahlen sind keine Blöcke
    assert gefunden == erwartet                                              # an seiner Stelle, in Lesefolge, nichts fehlt
    texte = [t for _, _, t, _, _ in gefunden]
    assert len(set(texte)) == len(texte)                                     # nichts doppelt
    assert [b.kennung for b in w.bloecke() if b.kapitel == 2] == [f"2.{i}" for i in range(1, 7)]


def test_lage_jedes_blocks(probe):
    _, _, _, w = probe
    bloecke = {b.kennung: b for b in w.bloecke() if b.kapitel < 3}
    assert all(b.lage is not None and 0 <= b.lage[0] < b.lage[2] <= 595 and 0 <= b.lage[1] < b.lage[3] <= 842 for b in bloecke.values())
    spalten = {marken.klartext(b.vorlage)[:12]: b.lage for b in bloecke.values() if b.seite == 4}
    assert spalten["Many gardens"][0] == 72 and spalten["Many gardens"][2] < 300      # beginnt in der linken Spalte
    assert spalten["In winter th"][0] >= 305                                           # steht in der rechten
    assert spalten["Both columns"][2] > 400                                            # über die ganze Breite
    assert bloecke["1.9"].art == "fussnote" and bloecke["1.9"].lage[1] > 700           # die Fußnote am Fuß der Seite
    assert [b.kennung for b in w.bloecke() if b.seite is None] == [f"3.{i}" for i in range(1, 8)]   # das Verzeichnis hat keine Seite


def test_auszeichnungen_platzhalter_und_trennung(probe):
    _, _, _, w = probe
    v = {b.kennung: b.vorlage for b in w.bloecke()}
    assert v["1.2"] == ("A small garden robot can water <t1>sixteen</t1> beds in one hour. It needs only a <t2>charged battery</t2> "
                        "and a full tank.<x3/> Most owners start with one machine and add more later.")    # kursiv, fett, Fußnotenzeichen
    assert "less effective." in v["1.4"] and "effec" not in v["1.4"].replace("effective", "")     # Trennung am Zeilenende aufgelöst
    assert "Good irrigation<x1/> saves water" in v["1.20"]                    # Trennung am Seitenende, die Marke hinter dem Wort
    assert v["1.1"] == "1 Getting Started" and v["1.12"] == "Table 1: Daily water needs"   # Überschrift ohne fett, Unterschrift ohne kursiv
    assert v["1.5"] == "<x1/> Check the wheels before every run."                # das Aufzählungszeichen als Platzhalter


def test_code_bleibt_code(probe):
    _, lesefolge, _, w = probe
    [code] = [e.text for e in lesefolge if e.art == "code"]
    k1 = dateien(w.epub)["OEBPS/text/k001.xhtml"].decode()
    assert f'<pre class="bf-code" data-bf-seite="3"' in k1 and f">{code}</pre>" in k1
    assert '<figure class="bf-listing"><figcaption' in k1 and "Listing 1: Starting the pump</figcaption><pre" in k1
    alle = " ".join(b.vorlage for b in w.bloecke())
    assert "garden import" not in alle and "litres=2" not in alle


def test_kopf_fuss_und_seitenzahlen_fallen_weg(probe):
    _, _, _, w = probe
    text = lesetext(w.epub)
    assert KOPF not in text and "Chapter notes" not in text
    assert not re.search(r"(^|\s)1[1-5](\s|$)", text)                          # keine Seitenzahl als Text
    assert "Measured on a dry morning" in text                                 # die Fußnote im unteren Rand bleibt


def test_tabelle_nach_zellen(probe):
    _, _, _, w = probe
    [(_, baum)] = [(p, b) for p, b in kapiteldateien(w.epub) if p.endswith("k001.xhtml")]
    [tabelle] = baum.iter(f"{X}table")
    reihen = [[(z.tag.removeprefix(X), "".join(z.itertext())) for z in tr] for tr in tabelle.iter(f"{X}tr")]
    assert reihen == [[("th", "Plant"), ("th", "Litres"), ("th", "Rounds")], [("td", "Tomato"), ("td", "2"), ("td", "Morning")],
                      [("td", "Lettuce"), ("td", "1"), ("td", "Evening")]]
    assert tabelle.find(f"{X}caption").text == "Table 1: Daily water needs" and tabelle.find(f"{X}thead") is not None


def test_fussnote_mit_verweis_hin_und_zurueck(probe):
    _, _, _, w = probe
    k1 = dateien(w.epub)["OEBPS/text/k001.xhtml"].decode()
    assert '<sup><a epub:type="noteref" role="doc-noteref" href="#fn-1-1" id="fn-verweis-1">1</a></sup>' in k1
    assert ('<aside epub:type="footnote" role="doc-footnote" class="bf-fussnote" id="fn-1-1"><p data-bf-seite="1"' in k1
            and '<a epub:type="backlink" role="doc-backlink" href="#fn-verweis-1">1</a> Measured' in k1)
    # die Fußnote steht hinter dem letzten Absatz ihrer Seite, vor der Marke der nächsten
    assert k1.index("returns to its station") < k1.index('id="fn-1-1"') < k1.index('id="seite-2"')


def test_abbildungen_mit_unterschrift_das_bild_unveraendert(probe):
    daten, _, _, w = probe
    teile = dateien(w.epub)
    k1, k2 = teile["OEBPS/text/k001.xhtml"].decode(), teile["OEBPS/text/k002.xhtml"].decode()
    assert re.search(r'<figure class="bf-abbildung" data-bf-seite="3"[^>]*><img src="../bilder/s0003-1.png" alt=""/>'
                     r'<figcaption[^>]*>Figure 1: The pump and its hose.</figcaption></figure>', k1)
    assert teile["OEBPS/bilder/s0003-1.png"].startswith(b"\x89PNG")             # die Zeichnung als Ausschnitt der Seite
    with fitz.open(stream=daten, filetype="pdf") as doc:
        [info] = doc[4].get_image_info(xrefs=True)
        roh = doc.extract_image(info["xref"])["image"]
    assert teile["OEBPS/bilder/s0005-1.png"] == roh                            # das Rasterbild Byte für Byte
    assert '<img src="../bilder/s0005-1.png" alt=""/><figcaption' in k2 and "Figure 2: A bed at sunrise." in k2
    assert w.abbildungen == 2
    alle = " ".join(marken.klartext(b.vorlage) for b in w.bloecke())
    assert " hose " not in f" {alle} " and "pump and its hose" in alle          # die Beschriftung im Bild ist kein Text


# -- Seitenmarken ---------------------------------------------------------------------------------------------------------------

def test_seitenmarken_mit_gedruckten_seiten(probe):
    _, _, _, w = probe
    assert seitenmarken(w.epub) == [("k001.xhtml", f"seite-{n}", str(10 + n), f"Seite {10 + n}") for n in range(1, 5)] + [
        ("k002.xhtml", "seite-5", "15", "Seite 15")]
    k1 = dateien(w.epub)["OEBPS/text/k001.xhtml"].decode()
    assert '<section epub:type="chapter" role="doc-chapter" id="k1">\n<span class="bf-seite" epub:type="pagebreak" role="doc-pagebreak" id="seite-1"' in k1
    assert re.search(r'id="seite-2" title="12">Seite 12</span><h3 id="h3"', k1)            # vor dem ersten Element der Seite
    assert re.search(r'Good irrigation<span class="bf-seite"[^>]*id="seite-3"[^>]*>Seite 13</span> saves', k1)   # mitten im Absatz
    nav = dateien(w.epub)["OEBPS/nav.xhtml"].decode()
    assert '<nav epub:type="page-list" role="doc-pagelist" id="seiten" hidden="hidden" translate="no">' in nav
    assert '<li><a href="text/k001.xhtml#seite-3">13</a></li>' in nav and '<li><a href="text/k002.xhtml#seite-5">15</a></li>' in nav


def test_ohne_beschriftung_die_seiten_des_pdf():
    w = werk.zerlegen(probe_pdf(mit_beschriftungen=False), "pdf")
    assert [(i, t) for _, i, t, _ in seitenmarken(w.epub)] == [(f"seite-{n}", str(n)) for n in range(1, 6)]
    assert {b.gedruckt for b in w.bloecke() if b.seite} == {"1", "2", "3", "4", "5"}


# -- Rundlauf -------------------------------------------------------------------------------------------------------------------

def ohne_sprache(daten: bytes) -> bytes:
    text = daten.decode("utf-8")
    text = re.sub(r'((?:xml:)?lang)="[a-z-]+"', r'\1="?"', text)
    return re.sub(r"<dc:language>[^<]*</dc:language>", "<dc:language>?</dc:language>", text).encode("utf-8")


def test_rundlauf_ohne_uebersetzung(probe):
    """Ohne Übersetzung ist die Fassung das EPUB aus dem Aufbau bis auf die Sprache, und ihr Text ist der Text des PDF bis
    auf Kopf- und Fußzeilen und Trennungen: in Lesefolge, Wort für Wort (ohne die Beschriftung im Bild)."""
    daten, lesefolge, im_bild, w = probe
    gesetzt = w.setzen(Satz())
    vorher, nachher = dateien(w.epub), dateien(gesetzt)
    assert list(vorher) == list(nachher)
    for pfad in vorher:
        gleich = vorher[pfad] == nachher[pfad] or ohne_sprache(vorher[pfad]) == ohne_sprache(nachher[pfad])
        assert gleich, pfad
    text = lesetext(gesetzt)
    assert text == " ".join(" ".join(e.text for e in lesefolge).split())
    assert Counter(text.split()) == pdf_woerter(daten, im_bild)


def test_feste_kennungen_und_dasselbe_epub(probe):
    daten, _, _, w = probe
    noch = werk.zerlegen(daten, "pdf", gedruckt=GEDRUCKT)
    assert noch.epub == w.epub and noch.bloecke() == w.bloecke()


def test_ohne_verzeichnis_kapitel_aus_den_obersten_ueberschriften(probe):
    _, _, _, mit = probe
    w = werk.zerlegen(probe_pdf(mit_verzeichnis=False), "pdf", gedruckt=GEDRUCKT)
    assert [(d.titel, len(d.laeufe)) for d in inhalt(w)] == [(d.titel, len(d.laeufe)) for d in inhalt(mit)]
    assert [b.vorlage for b in w.bloecke() if b.kapitel < 3] == [b.vorlage for b in mit.bloecke() if b.kapitel < 3]
    nav = [marken.klartext(b.vorlage) for b in w.bloecke() if b.kapitel == 3]
    assert nav == ["Contents", "1 Getting Started", "1.1 The First Machine", "1.2 Two Columns", "2 Watering the Beds", "2.1 Morning Rounds"]


# -- Deutsche Fassung -----------------------------------------------------------------------------------------------------------

def test_deutsche_fassung_mit_marken_an_der_stelle_der_uebersetzung(probe):
    _, _, _, w = probe
    v = {b.kennung: b.vorlage for b in w.bloecke()}
    deutsch = {"1.1": "1 Erste Schritte",
               "1.20": "Wasser, das an der Oberfläche abläuft, geht den Pflanzen verloren. Gute Bewässerung<x1/> spart Wasser."}
    satz = Satz(deutsch={k: Uebersetzt(pruefsumme=pruefsumme(v[k]), text=t) for k, t in deutsch.items()},
                hinweis=Hinweis(modell="qwen/qwen3-next-80b", datum="26.11.2026"))
    teile = dateien(w.setzen(satz))
    k1 = teile["OEBPS/text/k001.xhtml"].decode()
    assert '<h1 id="h1" data-bf-seite="1"' in k1 and ">1 Erste Schritte</h1>" in k1 and 'lang="de" xml:lang="de"' in k1
    assert re.search(r'Gute Bewässerung<span class="bf-seite"[^>]*id="seite-3"[^>]*>Seite 13</span> spart Wasser.</p>', k1)
    hinweis = teile["OEBPS/bf-uebersetzung.xhtml"].decode()
    assert 'Das Original ist ein PDF. Marken wie "Seite 12" zeigen, wo dort eine neue Seite beginnt.' in hinweis


# -- Was sich nicht zerlegen lässt ----------------------------------------------------------------------------------------------

def test_scan_ohne_textschicht():
    with pytest.raises(OhneText, match=f"keine Textschicht \\(Scan\\): {TEXTERKENNUNG}"):
        werk.zerlegen(scan_pdf(), "pdf")
    with pytest.raises(NichtLesbar, match="kein lesbares PDF"):
        werk.zerlegen(b"kein PDF", "pdf")


def test_kaum_text_und_ueberwiegend_scan():
    doc = fitz.open()
    for _ in range(3):
        Blatt(doc, 1)                                                     # nur Kopf- und Fußzeile
    with pytest.raises(OhneText, match=f"kaum Text.*{TEXTERKENNUNG}"):
        werk.zerlegen(doc.tobytes(), "pdf")
    gemischt = fitz.open(stream=probe_pdf(), filetype="pdf")
    gemischt.insert_pdf(fitz.open(stream=scan_pdf(6), filetype="pdf"))
    with pytest.raises(OhneText, match=f"überwiegend aus Seiten ohne Textschicht.*{TEXTERKENNUNG}"):
        werk.zerlegen(gemischt.tobytes(), "pdf")


def test_seite_ohne_textschicht_kommt_als_bild(probe):
    _, _, _, w = probe
    doc = fitz.open(stream=probe_pdf(), filetype="pdf")
    doc.insert_pdf(fitz.open(stream=scan_pdf(1), filetype="pdf"))
    mit_scan = werk.zerlegen(doc.tobytes(), "pdf", gedruckt=GEDRUCKT)
    assert mit_scan.nicht_lesbar == ["Seite 6"] and mit_scan.seiten == 6
    assert [b.vorlage for b in mit_scan.bloecke()] == [b.vorlage for b in w.bloecke()]
    k2 = dateien(mit_scan.epub)["OEBPS/text/k002.xhtml"].decode()
    assert re.search(r'id="seite-6" title="6">Seite 6</span><figure class="bf-abbildung" data-bf-seite="6"[^>]*>'
                     r'<img src="../bilder/s0006-1.png"', k2)


def test_trennung_bleibt_bei_woertern_mit_bindestrich():
    """Am Zeilenende fällt der Bindestrich weg, außer das Dokument schreibt das Wort sonst mit ihm."""
    doc = fitz.open()
    b = Blatt(doc, 1, rahmen=False)
    b.zeilen([[("A well-known trick keeps the robot on its path, and every gardener uses the well-", "helv")],
              [("known trick in the morning before the first round of garden-", "helv")],
              [("ing begins with the beds near the fence.", "helv")]])
    w = werk.zerlegen(doc.tobytes(), "pdf")
    [absatz] = [b.vorlage for b in w.bloecke() if b.art == "absatz"]
    assert absatz == ("A well-known trick keeps the robot on its path, and every gardener uses the well-known trick in the morning "
                      "before the first round of gardening begins with the beds near the fence.")


def test_absatz_mit_einzug_und_abstand():
    """Ein neuer Absatz beginnt nach einem Abstand, eingerückt, oder wenn die vorige Zeile Platz für das nächste Wort hatte."""
    doc = fitz.open()
    b = Blatt(doc, 1, rahmen=False)
    b.zeilen([[("The robot waters the beds in the morning and returns to its station before the sun gets too", "helv")],
              [("strong.", "helv")]])
    b.zeile([("Later it checks the tank and the filter, and it writes a short note for the owner in the", "helv")], x=90)
    b.y += 13
    b.zeilen([[("garden.", "helv")]])
    b.y += 12
    b.zeilen([[("A new paragraph starts after the gap.", "helv")]])
    w = werk.zerlegen(doc.tobytes(), "pdf")
    assert [marken.klartext(x.vorlage) for x in w.bloecke() if x.art == "absatz"] == [
        "The robot waters the beds in the morning and returns to its station before the sun gets too strong.",
        "Later it checks the tank and the filter, and it writes a short note for the owner in the garden.",
        "A new paragraph starts after the gap."]


def test_verzeichnis_mit_buchtitel_darueber(probe):
    """Steht über den Kapiteln ein einzelner Eintrag (der Buchtitel), sind die Kapitel die Stufe darunter."""
    _, _, _, mit = probe
    doc = fitz.open(stream=probe_pdf(), filetype="pdf")
    doc.set_toc([[1, "Gardening with Small Machines", 1], [2, "1 Getting Started", 1], [3, "1.1 The First Machine", 1],
                 [3, "1.2 Two Columns", 4], [2, "2 Watering the Beds", 5], [3, "2.1 Morning Rounds", 5]])
    w = werk.zerlegen(doc.tobytes(), "pdf", gedruckt=GEDRUCKT)
    assert [d.titel for d in inhalt(w)] == ["1 Getting Started", "2 Watering the Beds"]
    assert [b.vorlage for b in w.bloecke() if b.kapitel < 3] == [b.vorlage for b in mit.bloecke() if b.kapitel < 3]
    nav = dateien(w.epub)["OEBPS/nav.xhtml"].decode()
    assert "Gardening with Small Machines" not in nav and '<a href="text/k001.xhtml#h4">1.2 Two Columns</a>' in nav


def _flaeche(x0: float, y0: float, x1: float, y1: float) -> pdf_lesen.Abbildung:
    return pdf_lesen.Abbildung(1, fitz.Rect(x0, y0, x1, y1))


def test_lesefolge_spalten_und_mittige_ueberschrift():
    kopf, l1, l2, r1, r2, fuss = (_flaeche(72, 80, 523, 100), _flaeche(72, 110, 290, 125), _flaeche(72, 130, 290, 145),
                                  _flaeche(305, 110, 523, 125), _flaeche(305, 130, 523, 145), _flaeche(72, 160, 523, 175))
    assert pdf_lesen.lesefolge([fuss, r2, l2, kopf, r1, l1]) == [kopf, l1, l2, r1, r2, fuss]
    mittig, kurz = _flaeche(250, 80, 345, 95), _flaeche(72, 110, 150, 125)       # eine mittige Überschrift über einer kurzen Zeile
    assert pdf_lesen.lesefolge([kurz, mittig]) == [mittig, kurz]


def test_text_auf_flaeche_und_im_rahmen_bleibt_text():
    """Eine Überschrift auf einem farbigen Band und ein kurzer Hinweis in einem Rahmen sind Text, keine Bilder; der Rahmen wird
    ein Kasten, das Band nicht."""
    doc = fitz.open()
    b = Blatt(doc, 1, rahmen=False)
    b.seite.draw_rect(fitz.Rect(60, 70, 535, 112), color=None, fill=(0.8, 0.9, 1))
    b.ueberschrift("3 Night Rounds", 1)
    b.absatz([("At night the robot moves slowly and uses its small lamp to find the beds near the fence.", "helv")])
    rahmen = fitz.Rect(72, b.y - 12, 400, b.y + 10)
    for p1, p2 in ((rahmen.tl, rahmen.tr), (rahmen.tr, rahmen.br), (rahmen.br, rahmen.bl), (rahmen.bl, rahmen.tl)):
        b.seite.draw_line(p1, p2, width=0.8)
    b.zeile([("Note: Never water at noon.", "helv")], x=80)
    b.y += 40
    b.absatz([("In the morning it returns to the station and writes a short report.", "helv")])
    w = werk.zerlegen(doc.tobytes(), "pdf")
    assert [(x.art, marken.klartext(x.vorlage)) for x in w.bloecke() if x.kapitel == 1] == [
        ("ueberschrift", "3 Night Rounds"), ("absatz", "At night the robot moves slowly and uses its small lamp to find the beds near the fence."),
        ("absatz", "Note: Never water at noon."), ("absatz", "In the morning it returns to the station and writes a short report.")]
    k1 = dateien(w.epub)["OEBPS/text/k001.xhtml"].decode()
    assert "bilder/" not in k1 and '<aside class="bf-kasten"' in k1 and k1.index('<aside class="bf-kasten"') > k1.index("<h1")


def test_kasten_mit_bild_und_titel_auf_dem_rahmen():
    doc = fitz.open()
    b = Blatt(doc, 1, rahmen=False)
    b.absatz([("The robot has a few rules that every owner should know before the first night in the garden.", "helv")])
    kasten = fitz.Rect(72, b.y + 4, 523, b.y + 110)
    b.seite.draw_rect(kasten, color=(0.3, 0.3, 0.3), fill=(0.95, 0.95, 0.9), width=0.8)
    b.zeile([("Safety first", "hebo")], x=84, groesse=10, y=kasten.y0 + 3)                          # Titel auf der Kante
    b.seite.insert_image(fitz.Rect(84, kasten.y0 + 14, 144, kasten.y0 + 54), pixmap=rasterbild())
    b.y = kasten.y0 + 72
    b.zeilen(umbrechen([("Never let the robot drive near the pond, and keep children away from the wheels while it works in "
                         "the beds.", "helv")], 420), x=84)
    b.y = kasten.y1 + 24
    b.absatz([("After these rules the owner can leave the robot alone.", "helv")])
    w = werk.zerlegen(doc.tobytes(), "pdf")
    assert [marken.klartext(x.vorlage) for x in w.bloecke() if x.kapitel == 1] == [
        "The robot has a few rules that every owner should know before the first night in the garden.", "Safety first",
        "Never let the robot drive near the pond, and keep children away from the wheels while it works in the beds.",
        "After these rules the owner can leave the robot alone."]
    k1 = dateien(w.epub)["OEBPS/text/k001.xhtml"].decode()
    aside = k1[k1.index('<aside class="bf-kasten"'):k1.index("</aside>")]
    assert "Safety first" in aside and '<img src="../bilder/s0001-1.png"' in aside and "Never let the robot" in aside


def test_diagramm_bleibt_abbildung_mit_seinen_beschriftungen():
    """Balken und Achsen sind mehr als ein Rahmen: das Diagramm bleibt ein Bild samt den Beschriftungen der Achse; sein Titel
    in ganzen Wörtern bleibt Text."""
    doc = fitz.open()
    b = Blatt(doc, 1, rahmen=False)
    b.absatz([("The robot keeps a log of the water it uses on every day of the week.", "helv")])
    oben = b.y
    b.seite.draw_line((100, oben + 120), (400, oben + 120), width=1)
    b.seite.draw_line((100, oben + 20), (100, oben + 120), width=1)
    for i, hoehe in enumerate((60, 80, 45, 90)):
        b.seite.draw_rect(fitz.Rect(120 + 60 * i, oben + 120 - hoehe, 150 + 60 * i, oben + 120), color=None, fill=(0.3, 0.5, 0.8))
        b.zeile([(("Mon", "Tue", "Wed", "Thu")[i], "helv")], x=122 + 60 * i, groesse=7, y=oben + 130)
    b.zeile([("Litres used by the robot each day", "helv")], x=140, groesse=8, y=oben + 14)
    b.y = oben + 160
    b.absatz([("Thursday was the hottest day of the week.", "helv")])
    w = werk.zerlegen(doc.tobytes(), "pdf")
    assert [marken.klartext(x.vorlage) for x in w.bloecke() if x.kapitel == 1] == [
        "The robot keeps a log of the water it uses on every day of the week.", "Litres used by the robot each day",
        "Thursday was the hottest day of the week."]
    assert w.abbildungen == 1 and "OEBPS/bilder/s0001-1.png" in dateien(w.epub)
