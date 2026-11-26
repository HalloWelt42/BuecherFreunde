"""Aus dem Aufbau eines PDF (pdf_aufbau.py) ein englisches EPUB 3 (BF-71): eine XHTML-Datei je Kapitel, das
Inhaltsverzeichnis, die Bilder und ein Stylesheet. Dieses EPUB zerlegt und setzt dieselbe Kette wie jedes andere
(zerlegen_epub.py, setzen.py), so wird die deutsche Fassung eines PDF ein EPUB mit demselben Aufbau.

- Elemente: Überschrift h1 bis h6 mit Anker, Absatz p, Liste ul oder ol mit dem gedruckten Zeichen in
  `<span class="bf-zeichen" translate="no">` (geht als Platzhalter durch), Tabelle mit thead, th und colspan, Code als pre (je
  Seite ein Teil), Abbildung als figure mit img und figcaption (oben oder unten wie im PDF), Fußnote als aside mit
  epub:type="footnote" und Rückverweis, Kasten als aside.
- Im Satz: fett b, kursiv i, hochgestellt sup, Festbreitenschrift `<span class="bf-festbreit">` (ob das Code ist, entscheidet
  die Erkennung beim Zerlegen), Fußnotenzeichen `<a epub:type="noteref">`.
- Seitenmarken: `<span class="bf-seite" epub:type="pagebreak" id="seite-N" title="33">Seite 33</span>` vor dem ersten Element
  einer Seite und mitten im Absatz an der Stelle des Wechsels, für jede Seite des PDF; mit der gedruckten Seitenzahl, wenn
  sie bekannt ist, sonst der Seite im PDF (N ist immer die Seite im PDF). Jedes Element mit Text trägt `data-bf-seite`
  (Seite im PDF) und `data-bf-lage` (seine Fläche dort in Punkten: links oben rechts unten).
- Bilder: ein Bild der Datei, das allein die Abbildung ist, kommt unverändert hinein (PNG, JPEG, GIF); alles andere als
  Ausschnitt der Seite (PNG). Eine Seite ohne Textschicht kommt ganz als Bild hinein.

Alles ist fest: dasselbe PDF ergibt dasselbe EPUB, Byte für Byte."""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from html import escape

import fitz

from backend.app.uebersetzung import pdf_aufbau as A

ZOOM = 2.0                                           # Ausschnitte in 144 dpi
UNVERAENDERT = {"png": "image/png", "jpeg": "image/jpeg", "jpg": "image/jpeg", "gif": "image/gif"}
ZEIT = (2000, 1, 1, 0, 0, 0)
STIL = """body { line-height: 1.5; }
section > .bf-seite, aside > .bf-seite { display: block; width: fit-content; margin: 1em 0 0.4em auto; }
.bf-seite { font-family: sans-serif; font-size: 0.7em; color: #777; border: 1px solid #bbb; border-radius: 2px;
  padding: 0 0.35em; margin: 0 0.2em; white-space: nowrap; }
.bf-festbreit, pre { font-family: monospace; }
pre.bf-code { white-space: pre-wrap; background: rgba(128, 128, 128, 0.1); padding: 0.5em; margin: 0.8em 0 0; }
pre.bf-weiter { margin-top: 0; }
ul.bf-liste, ol.bf-liste { list-style: none; padding-left: 1.6em; }
.bf-zeichen { display: inline-block; min-width: 1.2em; margin-left: -1.4em; }
figure { margin: 1em 0; text-align: center; }
figure img { max-width: 100%; }
figure.bf-listing { text-align: left; }
figcaption, caption { font-size: 0.9em; font-style: italic; }
table { border-collapse: collapse; margin: 1em 0; }
th, td { border: 1px solid #999; padding: 0.2em 0.5em; vertical-align: top; }
aside.bf-fussnote { font-size: 0.85em; border-top: 1px solid #bbb; margin-top: 0.8em; padding-top: 0.2em; }
aside.bf-kasten { border: 1px solid #999; padding: 0.4em 1em; margin: 1em 0; }
"""


@dataclass
class Bild:
    pfad: str                                        # im EPUB, etwa "bilder/s0003-1.png"
    art: str                                         # Medientyp
    daten: bytes


@dataclass
class _Lauf:
    """Was beim Schreiben eines Kapitels mitläuft: die zuletzt markierte Seite, die Bilder, wo jeder Anker steht."""
    doc: fitz.Document
    gedruckt: Callable[[int], str]
    datei: str = ""
    zuletzt: int = 0
    bilder: list[Bild] = field(default_factory=list)
    je_seite: dict[int, int] = field(default_factory=dict)
    anker: dict[str, str] = field(default_factory=dict)        # Anker -> Datei

    def marken(self, bis: int) -> str:
        """Die Marken aller Seiten bis `bis`, die noch keine haben."""
        aus = []
        while self.zuletzt < bis:
            self.zuletzt += 1
            n, beschriftung = self.zuletzt, escape(self.gedruckt(self.zuletzt))
            self.anker[f"seite-{n}"] = self.datei
            aus.append(f'<span class="bf-seite" epub:type="pagebreak" role="doc-pagebreak" id="seite-{n}" title="{beschriftung}">'
                       f"Seite {beschriftung}</span>")
        return "".join(aus)


def _lage(e: A.Element) -> str:
    r = e.lage
    return f' data-bf-seite="{e.seite}" data-bf-lage="{r.x0:.1f} {r.y0:.1f} {r.x1:.1f} {r.y1:.1f}"' if e.seite else ""


# -- Satz -----------------------------------------------------------------------------------------------------------------

def _lauf(l: A.Lauf, festbreit: bool) -> str:
    """Ein Lauf mit seinen Auszeichnungen; Leerraum am Rand steht außerhalb."""
    kern = l.text.strip()
    if not kern:
        return escape(l.text, quote=False)
    vorn, hinten = l.text[:len(l.text) - len(l.text.lstrip())], l.text[len(l.text.rstrip()):]
    s = escape(kern, quote=False)
    if l.stil.hoch:
        s = f"<sup>{s}</sup>"
    if l.stil.festbreit and festbreit:
        s = f'<span class="bf-festbreit">{s}</span>'
    if l.stil.kursiv:
        s = f"<i>{s}</i>"
    if l.stil.fett:
        s = f"<b>{s}</b>"
    return escape(vorn, quote=False) + s + escape(hinten, quote=False)


def satz(inhalt: A.Inhalt, lauf: _Lauf, festbreit: bool = True) -> str:
    aus = []
    for t in inhalt:
        if isinstance(t, A.Lauf):
            aus.append(_lauf(t, festbreit))
        elif isinstance(t, A.Seitenwechsel):
            aus.append(lauf.marken(t.seite))
        else:
            lauf.anker[t.anker] = lauf.datei
            aus.append(f'<sup><a epub:type="noteref" role="doc-noteref" href="#{t.fussnote}" id="{t.anker}">{escape(t.zeichen)}</a></sup>')
    return "".join(aus).strip()


# -- Bilder ---------------------------------------------------------------------------------------------------------------

def _bild(lauf: _Lauf, a: A.Abbildung) -> Bild:
    q = a.quelle
    nr = lauf.je_seite[q.seite] = lauf.je_seite.get(q.seite, 0) + 1
    if q.bild is not None:
        try:
            roh = lauf.doc.extract_image(q.bild)
        except Exception:  # noqa: BLE001 - dann als Ausschnitt der Seite
            roh = None
        if roh and roh.get("ext") in UNVERAENDERT and not roh.get("smask"):
            b = Bild(f"bilder/s{q.seite:04d}-{nr}.{roh['ext']}", UNVERAENDERT[roh["ext"]], roh["image"])
            lauf.bilder.append(b)
            return b
    seite = lauf.doc[q.seite - 1]
    ausschnitt = (q.rechteck + (-2, -2, 2, 2)) & seite.rect
    png = seite.get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), clip=ausschnitt, alpha=False).tobytes("png")
    b = Bild(f"bilder/s{q.seite:04d}-{nr}.png", "image/png", png)
    lauf.bilder.append(b)
    return b


# -- Elemente -------------------------------------------------------------------------------------------------------------

def _unterschrift(u: A.Absatz | None, lauf: _Lauf, element: str) -> str:
    return f"<{element}{_lage(u)}>{satz(u.inhalt, lauf)}</{element}>" if u is not None else ""


def _oben(u: A.Absatz | None, e: A.Element) -> bool:
    return u is not None and u.seite == e.seite and u.lage.y1 <= e.lage.y0 + 2


def element(e: A.Element, lauf: _Lauf) -> str:
    vorher = lauf.marken(e.seite)
    return vorher + _element(e, lauf)


def _element(e: A.Element, lauf: _Lauf) -> str:
    if isinstance(e, A.Ueberschrift):
        lauf.anker[e.anker] = lauf.datei
        return f'<h{e.stufe} id="{e.anker}"{_lage(e)}>{satz(e.inhalt, lauf)}</h{e.stufe}>'
    if isinstance(e, A.Absatz):
        klasse = ' class="bf-festbreit"' if e.festbreit else ""
        return f"<p{klasse}{_lage(e)}>{satz(e.inhalt, lauf, festbreit=not e.festbreit)}</p>"
    if isinstance(e, A.Liste):
        art = "ol" if e.geordnet else "ul"
        punkte = "".join(f'<li{_lage(p)}>{lauf.marken(p.seite)}<span class="bf-zeichen" translate="no">{escape(p.zeichen)}</span> '
                         f"{satz(p.inhalt, lauf)}</li>" for p in e.punkte)
        return f'<{art} class="bf-liste">{punkte}</{art}>'
    if isinstance(e, A.Tabelle):
        return _tabelle(e, lauf)
    if isinstance(e, A.Code):
        teile = []
        for i, (seite, code) in enumerate(e.teile):
            weiter = " bf-weiter" if i else ""
            teile.append(f'{lauf.marken(seite) if i else ""}<pre class="bf-code{weiter}"{_lage(e) if i == 0 else ""}>'
                         f"{escape(code, quote=False)}</pre>")
        if e.unterschrift is None:
            return "".join(teile)
        u = _unterschrift(e.unterschrift, lauf, "figcaption")
        return f'<figure class="bf-listing">{u}{"".join(teile)}</figure>'
    if isinstance(e, A.Abbildung):
        b = _bild(lauf, e)
        klasse = "bf-formel" if e.quelle.formel else "bf-abbildung"
        img = f'<img src="../{b.pfad}" alt=""/>'
        u = _unterschrift(e.unterschrift, lauf, "figcaption")
        return f'<figure class="{klasse}"{_lage(e)}>{u + img if _oben(e.unterschrift, e) else img + u}</figure>'
    if isinstance(e, A.Fussnote):
        lauf.anker[e.anker] = lauf.datei
        if e.verweis:
            zeichen = f'<a epub:type="backlink" role="doc-backlink" href="#{e.verweis}">{escape(e.zeichen)}</a>'
        else:
            zeichen = f'<span class="bf-zeichen" translate="no">{escape(e.zeichen)}</span>' if e.zeichen else ""
        return (f'<aside epub:type="footnote" role="doc-footnote" class="bf-fussnote" id="{e.anker}">'
                f"<p{_lage(e)}>{zeichen} {satz(e.inhalt, lauf)}</p></aside>")
    if isinstance(e, A.Kasten):
        return f'<aside class="bf-kasten"{_lage(e)}>{"".join(element(x, lauf) for x in e.elemente)}</aside>'
    raise TypeError(f"Unbekanntes Element: {type(e).__name__}")


def _tabelle(t: A.Tabelle, lauf: _Lauf) -> str:
    def reihe(zellen: list[A.Zelle]) -> str:
        teile = []
        for z in zellen:
            tag = "th" if z.kopf else "td"
            spalten = f' colspan="{z.spalten}"' if z.spalten > 1 else ""
            teile.append(f"<{tag}{spalten}{_lage(z) if z.inhalt else ''}>{satz(z.inhalt, lauf)}</{tag}>")
        return f"<tr>{''.join(teile)}</tr>"

    kopf = [r for r in t.reihen[:1] if r and all(z.kopf for z in r)]
    rumpf = t.reihen[len(kopf):]
    u = _unterschrift(t.unterschrift, lauf, "caption")
    thead = f"<thead>{reihe(kopf[0])}</thead>" if kopf else ""
    return f"<table{_lage(t)}>{u}{thead}<tbody>{''.join(reihe(r) for r in rumpf)}</tbody></table>"


# -- Dateien --------------------------------------------------------------------------------------------------------------

def _xhtml(titel: str, sprache: str, koerper: str, stil: str = "../stil.css") -> str:
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="{sprache}" xml:lang="{sprache}">\n'
            f'<head>\n<meta charset="utf-8"/>\n<title>{escape(titel)}</title>\n<link rel="stylesheet" type="text/css" href="{stil}"/>\n'
            f"</head>\n<body>\n{koerper}\n</body>\n</html>\n")


def _kapitel(k: A.Kapitel, nr: int, lauf: _Lauf, sprache: str, seiten_bis: int | None) -> str:
    teile = [element(e, lauf) for e in k.elemente]
    if seiten_bis is not None:
        teile.append(lauf.marken(seiten_bis))                 # leere Seiten am Ende des Buchs
    inhalt = "\n".join(t for t in teile if t)
    return _xhtml(k.titel, sprache, f'<section epub:type="chapter" role="doc-chapter" id="k{nr}">\n{inhalt}\n</section>')


def _verzeichnis(buch: A.Buch, dateien: list[str], lauf: _Lauf, sprache: str, seiten: int) -> str:
    def ziel(e: A.Eintrag) -> str:
        datei = dateien[e.kapitel]
        if not e.anker:
            return datei
        return f"{lauf.anker.get(e.anker, datei)}#{e.anker}"

    zeilen: list[str] = []
    tiefe = 0
    for e in buch.verzeichnis:
        stufe = min(e.stufe, tiefe + 1)
        if stufe > tiefe:
            zeilen.append("<ol>" * (stufe - tiefe))
        else:
            zeilen.append("</li>" + "</ol></li>" * (tiefe - stufe))
        zeilen.append(f'<li><a href="text/{ziel(e)}">{escape(e.titel, quote=False)}</a>')
        tiefe = stufe
    if tiefe:
        zeilen.append("</li>" + "</ol></li>" * (tiefe - 1) + "</ol>")
    seitenliste = "".join(f'<li><a href="text/{lauf.anker.get(f"seite-{n}", dateien[0])}#seite-{n}">{escape(lauf.gedruckt(n))}</a></li>'
                          for n in range(1, seiten + 1))
    koerper = (f'<nav epub:type="toc" role="doc-toc" id="toc">\n<h1>Contents</h1>\n{"".join(zeilen)}\n</nav>\n'
               f'<nav epub:type="page-list" role="doc-pagelist" id="seiten" hidden="hidden" translate="no">\n<ol>{seitenliste}</ol>\n</nav>')
    return _xhtml("Contents", sprache, koerper, stil="stil.css")


def _paket(titel: str, autor: str, sprache: str, kennung: str, dateien: list[str], bilder: list[Bild]) -> str:
    eintraege = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                 '<item id="stil" href="stil.css" media-type="text/css"/>']
    eintraege += [f'<item id="k{i}" href="text/{d}" media-type="application/xhtml+xml"/>' for i, d in enumerate(dateien, 1)]
    eintraege += [f'<item id="b{i}" href="{b.pfad}" media-type="{b.art}"/>' for i, b in enumerate(bilder, 1)]
    folge = "".join(f'<itemref idref="k{i}"/>' for i in range(1, len(dateien) + 1))
    autor_zeile = f"\n    <dc:creator>{escape(autor)}</dc:creator>" if autor else ""
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            f'<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="kennung" xml:lang="{sprache}">\n'
            '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
            f'    <dc:identifier id="kennung">urn:bf:pdf:{kennung}</dc:identifier>\n'
            f"    <dc:title>{escape(titel or 'PDF')}</dc:title>{autor_zeile}\n"
            f"    <dc:language>{sprache}</dc:language>\n"
            '    <meta property="dcterms:modified">2000-01-01T00:00:00Z</meta>\n'
            "  </metadata>\n"
            "  <manifest>\n    " + "\n    ".join(eintraege) + "\n  </manifest>\n"
            f"  <spine>{folge}</spine>\n"
            "</package>\n")


CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def epub(doc: fitz.Document, buch: A.Buch, gedruckt: Callable[[int], str], titel: str, autor: str, sprache: str,
         kennung: str) -> bytes:
    """Das EPUB des Aufbaus; `gedruckt` nennt zu jeder Seite im PDF ihre Beschriftung für die Marken."""
    lauf = _Lauf(doc, gedruckt)
    dateien = [f"k{i:03d}.xhtml" for i in range(1, len(buch.kapitel) + 1)]
    texte = []
    for i, k in enumerate(buch.kapitel):
        lauf.datei = dateien[i]
        texte.append(_kapitel(k, i + 1, lauf, sprache, doc.page_count if i == len(buch.kapitel) - 1 else None))
    nav = _verzeichnis(buch, dateien, lauf, sprache, doc.page_count)
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        def schreiben(pfad: str, daten: bytes | str, gepackt: bool = True) -> None:
            z.writestr(zipfile.ZipInfo(pfad, date_time=ZEIT), daten, compress_type=zipfile.ZIP_DEFLATED if gepackt else zipfile.ZIP_STORED)

        schreiben("mimetype", "application/epub+zip", gepackt=False)
        schreiben("META-INF/container.xml", CONTAINER)
        schreiben("OEBPS/content.opf", _paket(titel, autor, sprache, kennung, dateien, lauf.bilder))
        schreiben("OEBPS/nav.xhtml", nav)
        schreiben("OEBPS/stil.css", STIL)
        for d, t in zip(dateien, texte):
            schreiben(f"OEBPS/text/{d}", t)
        for b in lauf.bilder:
            schreiben(f"OEBPS/{b.pfad}", b.daten, gepackt=False)
    return puffer.getvalue()


def kennung_von(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()[:32]
