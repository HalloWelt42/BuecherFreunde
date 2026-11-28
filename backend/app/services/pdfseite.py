"""Gemeinsame Regeln zum Lesen einer PDF-Seite, für Textansicht, Codestellen, Volltext und Übersetzung (BF-104).

- Textschicht: PyMuPDF mit seinen üblichen Merkmalen, aber ohne TEXT_PRESERVE_LIGATURES; echte Ligaturzeichen ("fi" als ein
  Zeichen) kommen so als ihre Buchstaben.
- Fehlzeichen (gemessen an Büchern aus einer Textverarbeitung, Schrift Calibri): das PDF bildet die Glyphen seiner Ligaturen
  ("ti", "tt", "ft") in der ToUnicode-Tafel auf kein Zeichen ab (Wert 0). PyMuPDF gibt für eine solche Glyphe ihre
  Glyphennummer als Zeichen aus (TEXT_CID_FOR_UNKNOWN_UNICODE), etwa 415 als großes O mit Tilde; darum stehen im Text
  Buchstaben, die griechisch oder kyrillisch aussehen. Die eingebetteten Teilschriften tragen weder Glyphennamen (Tabelle
  post) noch Ligaturtafeln (GSUB); die Buchstaben je Glyphennummer sind darum an den Wörtern gemessen, in denen sie stehen
  (FEHLZEICHEN). Ersetzt wird nur, wo die Spur der Seite (get_texttrace) zeigt, dass gerade diese Glyphe in einer solchen
  Schrift ohne Zeichen im PDF steht, und nur an einem Buchstaben; groß, wo die Buchstaben daneben groß sind. Dasselbe
  Zeichen mit eigener Zuordnung (etwa ein echtes griechisches Theta in einer Formel) bleibt so stehen.
- Zeichnungen: "gerade" sind Rechtecke und waagerechte oder senkrechte Linien, wie Hintergründe, Rahmen und Bänder; Kurven
  und schräge Linien gehören zu Grafiken. Sichtbar sind Zeichnungen auf der Seite (auf sie beschnitten: ein Kasten, der über
  den Seitenwechsel geht, zählt mit), ohne den Hintergrund der Seite: eine Fläche über fast die ganze Seite, oder eine weiße
  ohne Rand über mindestens die halbe (aus E-Books gedruckte PDF legen eine solche über das ganze Kapitel).
- Grenze (BF-120): Zeichnungen liest nur, wer hier fragt (`zeichnungen`, `gruppen`), und nur bis zu einer Größe des Inhalts der
  Seite (`pdf_zeichnungen_bis_kb`, gepackt, mit den Formularen, die sie zeichnet). PyMuPDF legt je Zeichnung ein Objekt an; eine
  Abbildung aus 3,4 Millionen gefüllten Rechtecken (194 MB Inhalt) belegte so alle 16 GB des Rechners. Eine Seite darüber gilt
  als ohne Zeichnungen: ihr Text bleibt lesbar, Kästen und Tafeln darauf erkennt die Ansicht dann nicht.
- Lesbar (`lesbar`): ein Text trägt echte Zeichen, mindestens LESBAR_ANTEIL seiner sichtbaren Zeichen sind Buchstaben oder
  Ziffern; Zeichensalat aus Steuer- und Sonderzeichen (eine Schrift ohne Zeichenzuordnung) gilt nicht. Darauf baut auch die
  Regel der Texterkennung, welche Seite keinen lesbaren Text trägt (texterkennung/textschicht.py).
"""

from __future__ import annotations

import logging
import re

import fitz

from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.pdfseite")

TEXTART = fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_LIGATURES
TEXTART_ROH = fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_LIGATURES
TEXTART_SCHLICHT = fitz.TEXTFLAGS_TEXT & ~fitz.TEXT_PRESERVE_LIGATURES

# Glyphennummern der Ligaturen in Calibri, wie sie als Zeichen ankommen, und ihre Buchstaben: gemessen an den Wörtern, in
# denen sie stehen ("Funk?on", "Schri?", "o?")
FEHLZEICHEN: dict[str, str] = {
    "\u019f": "ti", "\u01a9": "tt", "\u014c": "ft", "\u019e": "tf", "\u0129": "fb", "\u01aa": "ttf", "\u0145": "fk",
    "\u012c": "fh", "\u01ab": "tti",
}
FEHLSCHRIFT = re.compile(r"(^|\+)calibri", re.IGNORECASE)   # Schriften, deren Ligaturen so ankommen (gemessen)
OHNE_ZEICHEN = (0, 0xFFFD)      # so steht eine Glyphe ohne Zeichenzuordnung in der Spur der Seite
_IM_WORT = re.compile(r"(?<=[^\W\d_])[" + "".join(FEHLZEICHEN) + r"](?=[^\W\d_])")
HINTERGRUND = 0.85              # Anteil der Seite: eine so große Zeichnung ist Hintergrund
WEISSER_HINTERGRUND = 0.5       # Anteil der Seite: so groß ist eine weiße Fläche ohne Rand Hintergrund
WEISS = 0.98                    # so hell in jedem Farbanteil ist eine Füllung weiß
LESBAR_ANTEIL = 0.5             # mindestens so viele der sichtbaren Zeichen müssen Buchstaben oder Ziffern sein


def fehlzeichen_aus_spuren(spuren: list[dict]) -> frozenset[str]:
    """Aus der Spur einer Seite (get_texttrace): die Fehlzeichen, deren Glyphe dort in einer Fehlschrift ohne Zeichen steht."""
    return frozenset(chr(c[1]) for s in spuren if FEHLSCHRIFT.search(s.get("font", "")) for c in s["chars"]
                     if c[0] in OHNE_ZEICHEN and chr(c[1]) in FEHLZEICHEN)


def fehlzeichen_der_seite(seite: fitz.Page) -> frozenset[str]:
    """Die Fehlzeichen, für die diese Seite eine Ligatur ohne Zeichen führt; ohne Fehlschrift auf der Seite gar keins (dann
    ohne den Weg über die Spur)."""
    if not any(FEHLSCHRIFT.search(f[3] or "") for f in seite.get_fonts()):
        return frozenset()
    return fehlzeichen_aus_spuren(seite.get_texttrace())


def _am_wort(text: str, i: int) -> bool:
    return (i > 0 and text[i - 1].isalpha()) or (i + 1 < len(text) and text[i + 1].isalpha())


def _buchstaben(text: str, i: int) -> str:
    """Die Buchstaben für das Fehlzeichen an Stelle i; groß, wenn die Buchstaben daneben groß sind ("FUNK?ON")."""
    nachbarn = [c for c in (text[i - 1] if i > 0 else "", text[i + 1] if i + 1 < len(text) else "") if c.isalpha()]
    ersatz = FEHLZEICHEN[text[i]]
    return ersatz.upper() if nachbarn and all(c.isupper() for c in nachbarn) else ersatz


def ligaturen_aufloesen(text: str, zeichen: frozenset[str]) -> str:
    """Die belegten Fehlzeichen, die an einem Buchstaben stehen, werden ihre Buchstaben."""
    if not zeichen or not any(c in text for c in zeichen):
        return text
    return "".join(_buchstaben(text, i) if c in zeichen and _am_wort(text, i) else c for i, c in enumerate(text))


def fehlzeichen_im_wort(text: str) -> int:
    """So oft steht ein Fehlzeichen mitten im Wort, zwischen zwei Buchstaben: ein gespeicherter Text, der noch mit falsch
    gelesenen Ligaturen gewonnen wurde. Ein einzelnes Zeichen (etwa in einer Formel) zählt nicht."""
    return len(_IM_WORT.findall(text)) if any(c in text for c in FEHLZEICHEN) else 0


def lesbar(text: str) -> bool:
    """Trägt der Text echte Zeichen? Zeichensalat aus Steuer- und Sonderzeichen gilt nicht."""
    sichtbar = [c for c in text if not c.isspace()]
    if not sichtbar:
        return False
    return sum(c.isalnum() for c in sichtbar) / len(sichtbar) >= LESBAR_ANTEIL


def seitentext(seite: fitz.Page) -> str:
    """Der schlichte Text einer Seite (Volltext), Ligaturen als Buchstaben."""
    text = seite.get_text("text", flags=TEXTART_SCHLICHT) or ""
    if any(c in text for c in FEHLZEICHEN):
        text = ligaturen_aufloesen(text, fehlzeichen_der_seite(seite))
    return text


def inhalt_kb(seite: fitz.Page) -> int:
    """Wie groß der Inhalt der Seite in der Datei ist (gepackt): ihre Inhaltsströme und die Formulare, die sie zeichnet."""
    doc = seite.parent
    xrefs = {*seite.get_contents(), *(x[0] for x in seite.get_xobjects())}
    return sum(len(doc.xref_stream_raw(x) or b"") for x in xrefs if x > 0) // 1024


def zeichnungen_lesbar(seite: fitz.Page) -> bool:
    groesse = inhalt_kb(seite)
    if groesse <= settings.pdf_zeichnungen_bis_kb:
        return True
    logger.info("Seite %d: %d KB Inhalt, über der Grenze von %d KB; Zeichnungen nicht gelesen", seite.number + 1, groesse,
                settings.pdf_zeichnungen_bis_kb)
    return False


def zeichnungen(seite: fitz.Page) -> list[dict]:
    """get_drawings, nur bis zur Grenze; darüber keine."""
    return seite.get_drawings() if zeichnungen_lesbar(seite) else []


def gruppen(seite: fitz.Page, gelesen: list[dict] | None = None) -> list[fitz.Rect]:
    """cluster_drawings über schon gelesene Zeichnungen, sonst über `zeichnungen` (nie ohne Grenze)."""
    liste = zeichnungen(seite) if gelesen is None else gelesen
    return seite.cluster_drawings(drawings=liste) if liste else []


def sichtbare_zeichnungen(seite: fitz.Page) -> list[dict]:
    """Die Zeichnungen der Seite (bis zur Grenze), auf die Seite beschnitten, ohne ihren Hintergrund; "beschnitten" sagt, ob
    eine Zeichnung über die Seite hinausreicht."""
    seitenflaeche = seite.rect.width * seite.rect.height
    aus = []
    for d in zeichnungen(seite):
        r = fitz.Rect(d["rect"]) & seite.rect
        if r.is_empty:
            continue
        anteil = r.width * r.height / seitenflaeche
        fuellung = d.get("fill")
        weiss = fuellung is not None and min(fuellung) >= WEISS and d.get("color") is None
        if anteil >= HINTERGRUND or (weiss and anteil >= WEISSER_HINTERGRUND):
            continue
        aus.append({**d, "rect": r, "beschnitten": r != fitz.Rect(d["rect"])})
    return aus


def gerade(zeichnung: dict) -> bool:
    """Besteht eine Zeichnung (aus get_drawings) nur aus Rechtecken und waagerechten oder senkrechten Linien?"""
    for item in zeichnung["items"]:
        if item[0] == "re":
            continue
        if item[0] == "l" and (abs(item[1].x - item[2].x) < 0.5 or abs(item[1].y - item[2].y) < 0.5):
            continue
        if item[0] == "qu" and item[1].is_rectangular:
            continue
        return False
    return True
