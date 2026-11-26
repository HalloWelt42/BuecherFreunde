"""EPUB zerlegen und setzen (BF-71): Blöcke mit fester Kennung, Rundlauf ohne Übersetzung (Dateien gleich bis auf die
Sprache), nur der Text tauscht, Marken für Stellen im Original, Hinweisblatt. Das Probebuch ist erfunden (tests/uebersetzung_probe.py)."""

import io
import re
import zipfile

import pytest
from lxml import etree

from backend.app.uebersetzung.modelle import pruefsumme
from backend.app.uebersetzung.setzen import ORIGINAL_ANDERS, Hinweis, Satz, Uebersetzt, mit_sprache, setzen
from backend.app.uebersetzung.xhtml import lesen
from backend.app.uebersetzung.zerlegen_epub import NichtLesbar, zerlegen
from tests.uebersetzung_probe import DATEIEN, KAPITEL_1, dateien, probe_epub

NIE = frozenset({"programlisting"})
KAPITEL1 = "OEBPS/text/kapitel 1.xhtml"
DEUTSCH = {
    "2.1": "Erste Schritte",
    "2.2": "Eine kleine Maschine kann <t1>16.000</t1> Pflanzen in 1,5 Stunden gießen, das sind etwa 3\u00a0GB Protokolle.<x2/>",
    "2.3": "Rufe <x1/> auf, bevor du die <t2>Pumpe</t2> startest, &amp; lies im <t3>nächsten Kapitel</t3> die Einzelheiten.",
    "2.8": "Prüfe den <t1>Filter <t2>zweimal</t2></t1> pro Woche.",
    "2.15": "<x1/> Gemessen an einem trockenen Tag.",
    "5.1": "Erste Schritte",
}


def satz(deutsch: dict[str, str], zerlegung, **weiter) -> Satz:
    vorlagen = {b.kennung: b.vorlage for b in zerlegung.bloecke()}
    return Satz(deutsch={k: Uebersetzt(pruefsumme=pruefsumme(vorlagen[k]), text=t) for k, t in deutsch.items()}, **weiter)


def ohne_sprache(daten: bytes) -> bytes:
    """Eine Datei mit neutralisierter Angabe der Sprache (lang, xml:lang, dc:language)."""
    text = daten.decode("utf-8")
    text = re.sub(r'((?:xml:)?lang)="[a-z-]+"', r'\1="?"', text)
    return re.sub(r"<dc:language>[^<]*</dc:language>", "<dc:language>?</dc:language>", text).encode("utf-8")


# -- Zerlegen -----------------------------------------------------------------------------------------------------------------

def test_zerlegen_in_kapitel_und_bloecke():
    z = zerlegen(probe_epub(), NIE)
    assert z.sprache == "en" and z.abbildungen == 2 and z.nicht_lesbar == []
    assert [(d.kapitel, d.rolle, d.titel, len(d.laeufe)) for d in z.dokumente] == [
        (1, "inhalt", "Cover", 0), (2, "inhalt", "Getting Started", 15), (3, "inhalt", "Watering the Beds", 5),
        (4, "verzeichnis", "Inhaltsverzeichnis", 3), (5, "ncx", "Inhaltsverzeichnis", 2)]
    bloecke = {b.kennung: b for b in z.bloecke()}
    assert [(k, bloecke[k].art, bloecke[k].stufe) for k in ("2.1", "2.2", "2.5", "2.9", "2.10", "2.13", "2.15", "3.1", "3.3", "5.1")] == [
        ("2.1", "ueberschrift", 1), ("2.2", "absatz", 0), ("2.5", "listenpunkt", 0), ("2.9", "bildunterschrift", 0),
        ("2.10", "tabellenzelle", 0), ("2.13", "bildunterschrift", 0), ("2.15", "fussnote", 0), ("3.1", "ueberschrift", 2),
        ("3.3", "listenpunkt", 0), ("5.1", "listenpunkt", 0)]
    assert bloecke["2.2"].vorlage == "A small machine can water <t1>16,000</t1> plants in 1.5 hours, which is about 3\u00a0GB of logs.<x2/>"
    assert bloecke["2.3"].vorlage == "Call <x1/> before you start the <t2>pump</t2> &amp; check the <t3>next chapter</t3> for details."
    assert bloecke["2.4"].vorlage == "The garden\u2019s soil is <x1/> in our notes."           # translate="no" als Platzhalter
    assert [bloecke[k].vorlage for k in ("2.5", "2.6", "2.7", "2.8")] == [                     # verschachtelte Liste, Absatz im Punkt
        "Fill the tank", "use clean water", "before the first run", "Check the <t1>filter <t2>twice</t2></t1> a week."]
    assert bloecke["2.14"].vorlage == "Visit <x1/>"                                         # eine Adresse als Text bleibt Adresse
    assert bloecke["2.15"].vorlage == "<x1/> Measured on a dry day."                         # Rückverweis der Fußnote
    alle = " ".join(b.vorlage for b in z.bloecke())
    assert "pump.start" not in alle and "stays as it is" not in alle and "Litres" in alle      # Code und Listing nie
    assert bloecke["2.2"].woerter == 17 and z.bloecke() == zerlegen(probe_epub(), NIE).bloecke()   # feste Kennungen


def test_klassen_die_nie_uebersetzt_werden_sind_einstellbar():
    mit = " ".join(b.vorlage for b in zerlegen(probe_epub(), frozenset()).bloecke())
    assert 'print("stays as it is")' in mit or "stays as it is" in mit


def test_nicht_lesbar():
    with pytest.raises(NichtLesbar, match="kein EPUB"):
        zerlegen(b"keine Datei", NIE)
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
    with pytest.raises(NichtLesbar, match="container.xml"):
        zerlegen(puffer.getvalue(), NIE)


# -- Rundlauf -----------------------------------------------------------------------------------------------------------------

def test_rundlauf_ohne_uebersetzung_ergibt_dasselbe_epub():
    original = probe_epub()
    z = zerlegen(original, NIE)
    gesetzt = setzen(original, z, Satz())
    vorher, nachher = dateien(original), dateien(gesetzt)
    assert list(vorher) == list(nachher)
    with zipfile.ZipFile(io.BytesIO(gesetzt)) as archiv:
        erste = archiv.infolist()[0]
        assert erste.filename == "mimetype" and erste.compress_type == zipfile.ZIP_STORED
        assert [i.compress_type for i in archiv.infolist()] == [zipfile.ZIP_STORED] + [zipfile.ZIP_DEFLATED] * len(DATEIEN)
    geaendert = {p for p in vorher if vorher[p] != nachher[p]}
    assert geaendert == {"OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/toc.ncx", "OEBPS/text/cover.xhtml", KAPITEL1,
                         "OEBPS/text/kap2.xhtml"}
    for p in vorher:
        assert ohne_sprache(vorher[p]) == ohne_sprache(nachher[p]) if p in geaendert else vorher[p] == nachher[p], p
    assert b'lang="de" xml:lang="de"' in nachher[KAPITEL1] and b"<dc:language>de</dc:language>" in nachher["OEBPS/content.opf"]


def _gleich(a: etree._Element, b: etree._Element) -> None:
    """Gleicher Baum: Namen, Attribute ohne Sprache, Text bis auf Leerraum."""
    rein = lambda t: " ".join((t or "").split())                                                   # noqa: E731
    ohne = lambda el: {k: v for k, v in el.attrib.items() if not k.endswith("lang")}              # noqa: E731
    assert (a.tag, ohne(a), rein(a.text), rein(a.tail)) == (b.tag, ohne(b), rein(b.text), rein(b.tail))
    assert len(a) == len(b)
    for x, y in zip(a, b):
        _gleich(x, y)


def test_rundlauf_mit_der_vorlage_als_uebersetzung_ergibt_dasselbe_markup():
    """Jeder Block geht durch Lesen der Marken und Darstellen; heraus kommt derselbe Baum (Zeichenreferenzen dürfen als
    Zeichen dastehen, Leerraum im Absatz wird ein Leerzeichen)."""
    original = probe_epub()
    z = zerlegen(original, NIE)
    gesetzt = dateien(setzen(original, z, satz({b.kennung: b.vorlage for b in z.bloecke()}, z)))
    for pfad in (KAPITEL1, "OEBPS/text/kap2.xhtml", "OEBPS/nav.xhtml", "OEBPS/toc.ncx"):
        _gleich(etree.fromstring(DATEIEN[pfad].encode("utf-8")), etree.fromstring(gesetzt[pfad]))


# -- Setzen -------------------------------------------------------------------------------------------------------------------

def test_nur_der_text_tauscht():
    original = probe_epub()
    z = zerlegen(original, NIE)
    k1 = dateien(setzen(original, z, satz(DEUTSCH, z, im_original={"2.4": "Im Original: noch nicht übersetzt"})))[KAPITEL1].decode()
    assert '<h1 id="h1">Erste Schritte</h1>' in k1
    assert ('<p>Eine kleine Maschine kann <em>16.000</em> Pflanzen in 1,5 Stunden gießen, das sind etwa 3\u00a0GB Protokolle.'
            '<a epub:type="noteref" href="#fn1" id="r1">1</a></p>') in k1
    assert ('<p>Rufe <code>water_all()</code> auf, bevor du die <strong>pump</strong>' not in k1
            and '<p>Rufe <code>water_all()</code> auf, bevor du die <strong>Pumpe</strong> startest, &amp; lies im '
                '<a href="kap2.xhtml#teil">nächsten Kapitel</a> die Einzelheiten.</p>' in k1)
    assert "<li><p>Prüfe den <b>Filter <i>zweimal</i></b> pro Woche.</p></li>" in k1
    assert '<p><a epub:type="backlink" href="#r1">1</a> Gemessen an einem trockenen Tag.</p>' in k1
    assert ('<p><span class="bf-original" lang="en" xml:lang="en" title="Im Original: noch nicht übersetzt" '
            'style="background-color: rgba(255, 196, 0, 0.18)">The garden&#8217;s soil is <span translate="no">Erdreich</span> '
            'in our notes.</span></p>') in k1
    assert '<pre><code>pump.start(speed=3)  # never translated</code></pre>' in k1     # Code bleibt Zeichen für Zeichen
    assert "<!-- ein Kommentar zwischen den Absätzen -->" in k1
    vorher = KAPITEL_1
    for stueck in ('<link rel="stylesheet" type="text/css" href="../stil.css"/>', '<tr><td>Tomato</td><td>2</td></tr>',
                   '<figure><img src="../bilder/garten.png" alt="A garden"/>'):
        assert stueck in vorher and stueck in k1


def test_verzeichnis_der_ncx_wird_deutsch_ohne_marke():
    original = probe_epub()
    z = zerlegen(original, NIE)
    ncx = dateien(setzen(original, z, satz({"5.1": "Erste Schritte"}, z, im_original={"5.2": "noch nicht"})))["OEBPS/toc.ncx"].decode()
    assert "<navLabel><text>Erste Schritte</text></navLabel>" in ncx and "<navLabel><text>Watering the Beds</text></navLabel>" in ncx
    assert "<docTitle><text>Gardening with Small Machines</text></docTitle>" in ncx and "bf-original" not in ncx


def test_hinweisblatt_vor_dem_ersten_kapitel_mit_text():
    original = probe_epub()
    z = zerlegen(original, NIE)
    h = Hinweis(modell="qwen/qwen3-next-80b", pruefmodell="qwen/qwen3-coder-next", datum="26.11.2026", im_original=2)
    gesetzt = dateien(setzen(original, z, satz(DEUTSCH, z, hinweis=h)))
    assert list(gesetzt)[-1] == "OEBPS/bf-uebersetzung.xhtml"
    blatt = gesetzt["OEBPS/bf-uebersetzung.xhtml"].decode()
    assert "<p>Von uns übersetzt aus dem Englischen.</p>" in blatt
    assert "<p>Übersetzt mit qwen/qwen3-next-80b, geprüft mit qwen/qwen3-coder-next, am 26.11.2026.</p>" in blatt
    assert "2 Stellen stehen noch im Original; sie sind hell hinterlegt." in blatt
    etree.fromstring(gesetzt["OEBPS/bf-uebersetzung.xhtml"])                                  # wohlgeformt
    opf = etree.fromstring(gesetzt["OEBPS/content.opf"])
    ns = {"o": "http://www.idpf.org/2007/opf"}
    assert opf.xpath("//o:item[@id='bf-uebersetzung']/@href", namespaces=ns) == ["bf-uebersetzung.xhtml"]
    assert opf.xpath("//o:itemref/@idref", namespaces=ns) == ["umschlag", "bf-uebersetzung", "kap1", "kap2"]


def test_passt_die_vorlage_nicht_mehr_bleibt_der_block_im_original():
    original = probe_epub()
    z = zerlegen(original, NIE)
    s = Satz(deutsch={"2.1": Uebersetzt(pruefsumme=pruefsumme("Something else"), text="Erste Schritte")})
    k1 = dateien(setzen(original, z, s))[KAPITEL1].decode()
    assert f'title="{ORIGINAL_ANDERS}"' in k1 and ">Getting Started</span></h1>" in k1


# -- XHTML lesen --------------------------------------------------------------------------------------------------------------

def test_nicht_wohlgeformtes_wird_geduldet_und_bleibt_wie_es_war():
    kaputt = ('<?xml version="1.0" encoding="utf-8"?>\n<html xmlns="http://www.w3.org/1999/xhtml" lang="en">\n<body>\n'
              "<p>First line<br>second line with an <em>unclosed tag</p>\n</div>\n<p>Rain&nbsp;falls on &quot;beds&quot;.</p>\n</body></html>")
    original = probe_epub({KAPITEL1: kaputt})
    z = zerlegen(original, NIE)
    assert [b.vorlage for b in z.bloecke() if b.kapitel == 2] == [
        "First line<x1/>second line with an <t2>unclosed tag</t2>", "Rain\u00a0falls on \"beds\"."]
    nachher = dateien(setzen(original, z, Satz()))[KAPITEL1]
    assert ohne_sprache(nachher) == ohne_sprache(kaputt.encode("utf-8"))
    gesetzt = dateien(setzen(original, z, satz({"2.2": "Regen\u00a0fällt auf \"Beete\"."}, z)))[KAPITEL1].decode()
    assert "<p>Regen\u00a0fällt auf \"Beete\".</p>" in gesetzt and "</div>" in gesetzt


def test_kodierung_und_byte_order_mark_bleiben():
    latin = ('<?xml version="1.0" encoding="iso-8859-1"?>\n<html xmlns="http://www.w3.org/1999/xhtml" lang="en"><body>'
             "<p>The garden is green.</p></body></html>").encode("iso-8859-1")
    mit_bom = b"\xef\xbb\xbf" + DATEIEN["OEBPS/text/kap2.xhtml"].encode("utf-8")
    original = probe_epub({KAPITEL1: latin, "OEBPS/text/kap2.xhtml": mit_bom})
    z = zerlegen(original, NIE)
    gesetzt = dateien(setzen(original, z, satz({"2.1": "Der Garten ist grün \u2013 \u201eschön\u201c \u2713.", "3.1": "Die Beete gießen"}, z)))
    assert "Der Garten ist grün &#8211; &#8222;schön&#8220; &#10003;.".encode("iso-8859-1") in gesetzt[KAPITEL1]
    assert gesetzt["OEBPS/text/kap2.xhtml"].startswith(b"\xef\xbb\xbf") and "Die Beete gießen".encode() in gesetzt["OEBPS/text/kap2.xhtml"]


def test_lesen_kennt_die_stellen_in_der_quelle():
    quelle = '<p class="a">Ein <em>kurzer</em> Satz<br/>.</p>'
    p = next(lesen(quelle).elemente())
    em = p.erstes("em")
    assert quelle[p.anfang:p.kopf_ende] == '<p class="a">' and quelle[p.fuss_anfang:p.ende] == "</p>"
    assert quelle[em.anfang:em.ende] == "<em>kurzer</em>" and p.erstes("br").leer
    assert mit_sprache('<html xmlns="x">', "de") == '<html xmlns="x" lang="de" xml:lang="de">'
    assert mit_sprache("<html lang='en' xml:lang='en'>", "de") == "<html lang='de' xml:lang='de'>"
    assert mit_sprache('<ncx version="1">', "de", hinzufuegen=False) == '<ncx version="1">'
