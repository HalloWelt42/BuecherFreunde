"""Code in der Textansicht, wo die Erkennung der Codestellen keinen gefunden hat (BF-103): Tafeln mit Code, Zeilen in
Festbreite und lose Codezeilen, die das Buch wie Fließtext setzt. Der Code bleibt in Zeilen, mit Einrückung."""

from __future__ import annotations

import re
import statistics

import fitz

from backend.app.services.pdfseite import gerade
from backend.app.services.textansicht.modelle import Baustein, Codeteil
from backend.app.services.textansicht.zeilen import UEBERSCHRIFT_FAKTOR, WORT, Block, Zeile, satz, ueberdecken_x

KASTEN_TEXT_AB = 120            # Zeichen in einem Absatz: ab hier umschließt eine Fläche Fließtext (ein Kasten)
TAFEL_FESTBREITE = 0.5          # Anteil der Zeichen in Festbreite, ab dem eine Tafel Code trägt
TAFEL_SAETZE = 0.5              # Anteil der Zeichen in Sätzen, ab dem eine Tafel Fließtext trägt (ein Kasten)
LEERZEILEN_HOECHSTENS = 1       # so viele Leerzeilen entstehen höchstens aus einem großen Abstand im Code
RAND_TAFEL = 2.0                # Punkte: so weit darf eine Zeichnung über die Tafel ragen und gehört doch zu ihr
LOSE_WOERTER = 8                # so viele Wörter aus Buchstaben hat eine lose Codezeile höchstens
LOSE_ANFANG = "'\"#0123456789"  # so beginnt eine lose Zeile, die zu Code gehören kann ("# Kommentar", "'Text'", "42")
CODEZEICHEN = re.compile(r"[=(){}\[\]<>#;'\"_*/\\^+|~$%&@]")
NUR_ZAHLEN = re.compile(r"^[\d\s.,+\-]+$")
# Zuweisung, Aufruf, Index, Klammern, Kommentar, Rechnen mit Abstand ("7 ** 2"), Eingabezeile, Eintrag eines Wörterbuchs
CODEMUSTER = re.compile(r"=|\w\(|\w\[|[{}]|^#|[\d)\]]\s+(\*\*|//|[-+*/%^])\s+[\w(]|^(>>>|\$)\s"
                        r"|^(?P<q>['\"])[^'\"]*(?P=q)\s*:")


def codezeilen(zeilen: list[Zeile]) -> list[str]:
    """Zeilen als Code, wie gedruckt: Einrückung aus der Lage, Leerzeilen nur aus einem Abstand deutlich über dem kleinsten
    Schritt. Zeilennummern nimmt die Codestelle selbst ab (codestellen/modelle.py); dieser Code ist keine Codestelle, eine
    Zahl am Anfang ("7 ** 2") gehört hier zum Code."""
    zeilen = sorted(zeilen, key=lambda z: (z.basis, z.rechteck.x0))
    links = min(z.rechteck.x0 for z in zeilen)
    breite = statistics.median(z.zeichenbreite for z in zeilen) or 1.0
    schritte = [b.basis - a.basis for a, b in zip(zeilen, zeilen[1:]) if b.basis - a.basis > 0]
    schritt = min(schritte) if schritte else 0.0
    aus: list[str] = []
    for i, z in enumerate(zeilen):
        if i and schritt:
            leer = round((z.basis - zeilen[i - 1].basis) / schritt) - 1
            aus += [""] * max(0, min(leer, LEERZEILEN_HOECHSTENS))
        aus.append(" " * max(0, round((z.rechteck.x0 - links) / breite)) + z.text.strip())
    return aus


def codebaustein(zeilen: list[Zeile]) -> Baustein:
    """Ein Baustein "code" ohne Kennung (keine erkannte Codestelle)."""
    r = fitz.Rect(zeilen[0].rechteck)
    for z in zeilen[1:]:
        r |= z.rechteck
    return Baustein("code", r.y0, r.x0, code=Codeteil(r, "", None, "", 0, 1, codezeilen(zeilen)))


# -- Tafeln --------------------------------------------------------------------------------------------------------------

def _eigene(flaeche: fitz.Rect, zeichnungen: list[dict]) -> list[dict]:
    weit = flaeche + (-RAND_TAFEL, -RAND_TAFEL, RAND_TAFEL, RAND_TAFEL)
    return [d for d in zeichnungen if weit.contains(d["rect"])]


def kastenrest(flaeche: fitz.Rect, zeichnungen: list[dict], bilder: list[fitz.Rect]) -> bool:
    """Das Ende eines Kastens von der Seite davor (oder sein Anfang vor der nächsten): Rechtecke und gerade Linien, ohne
    Bild, über den Rand der Seite hinaus. Ohne Text darauf ist das keine Abbildung."""
    eigene = _eigene(flaeche, zeichnungen)
    return (any(d.get("beschnitten") for d in eigene) and all(gerade(d) for d in eigene)
            and not any(flaeche.intersects(r) for r in bilder))


def tafel(flaeche: fitz.Rect, bloecke: list[Block], zeichnungen: list[dict], bilder: list[fitz.Rect]) -> bool:
    """Eine Fläche aus Rechtecken und geraden Linien, ohne Bild, deren Zeilen auf einer Füllung untereinander stehen? Ein
    Zierstück ohne Text darauf (Schieber, Symbol) stört nicht."""
    if not bloecke or any(flaeche.intersects(r) for r in bilder):
        return False
    eigene = _eigene(flaeche, zeichnungen)
    zeilen = [z for b in bloecke for z in b.zeilen]
    if any(not gerade(d) and any(fitz.Rect(d["rect"]).intersects(z.rechteck) for z in zeilen) for d in eigene):
        return False                                       # Grafik unter dem Text
    fuellungen = [fitz.Rect(d["rect"]) for d in eigene if gerade(d) and d.get("fill") is not None]
    if not all(any(f.contains(z.mitte) for f in fuellungen) for z in zeilen):
        return False
    return not any(a.rechteck.y0 < b.rechteck.y1 - 1 and b.rechteck.y0 < a.rechteck.y1 - 1
                   and not ueberdecken_x(a.rechteck, b.rechteck) for i, a in enumerate(zeilen) for b in zeilen[i + 1:])


def _codeartig(text: str) -> bool:
    return bool(CODEZEICHEN.search(text) or NUR_ZAHLEN.match(text.strip()))


def tafelart(bloecke: list[Block], grund: float) -> str:
    """Was eine Tafel trägt: "text" (nur große Schrift, ein Band hinter einer Überschrift), "code" oder "kasten"."""
    zeilen = [z for b in bloecke for z in b.zeilen]
    if grund and all(z.groesse >= grund * UEBERSCHRIFT_FAKTOR for z in zeilen):
        return "text"
    zeichen = sum(len(z.text.strip()) for z in zeilen) or 1
    if sum(len(z.text.strip()) * z.festbreit for z in zeilen) >= TAFEL_FESTBREITE * zeichen:
        return "code"
    saetze = sum(len(b.text) for b in bloecke if satz(b.text))
    if saetze >= TAFEL_SAETZE * sum(len(b.text) for b in bloecke) or any(len(b.text) >= KASTEN_TEXT_AB for b in bloecke):
        return "kasten"
    return "code" if any(_codeartig(z.text) for z in zeilen) else "kasten"


def tafelcode(bloecke: list[Block], codeteile: list[Codeteil]) -> list[Baustein]:
    """Der Code einer Tafel; liegt darin eine erkannte Codestelle, steht der Code davor und danach je für sich."""
    zeilen = sorted((z for b in bloecke for z in b.zeilen), key=lambda z: (z.basis, z.rechteck.x0))
    gruppen: dict[int, list[Zeile]] = {}
    for z in zeilen:
        davor = sum(1 for c in codeteile if c.rechteck.y1 <= z.rechteck.y0 + RAND_TAFEL and ueberdecken_x(c.rechteck, z.rechteck))
        gruppen.setdefault(davor, []).append(z)
    return [codebaustein(g) for _, g in sorted(gruppen.items())]


# -- Lose Codezeilen -----------------------------------------------------------------------------------------------------

def codezeile(text: str) -> bool:
    """Sieht eine Zeile im Fließtext nach Code aus (CODEMUSTER, oder ein Doppelpunkt am Ende einer kleingeschriebenen
    Zeile wie "else:")? Kein Satz, höchstens LOSE_WOERTER Wörter."""
    t = text.strip()
    kopfzeile = t.endswith(":") and t[:1].islower()
    return not satz(t) and len(WORT.findall(t)) <= LOSE_WOERTER and (kopfzeile or bool(CODEMUSTER.search(t)))


def _lose_zeile(b: Block) -> bool:
    """Kann die Zeile in einem Lauf loser Codezeilen stehen? Eine einzelne Zeile ohne Satz, die nach Code aussieht oder
    klein, mit einem Anführungszeichen, einer Ziffer oder einem Kommentarzeichen beginnt ("return True")."""
    t = b.text.strip()
    return (len(b.zeilen) == 1 and not satz(t) and len(WORT.findall(t)) <= LOSE_WOERTER
            and (codezeile(t) or t[:1].islower() or t[:1] in LOSE_ANFANG))


def lose_codezeilen(bausteine: list[Baustein], quelle: dict[int, Block]) -> list[Baustein]:
    """Code, den das Buch wie Fließtext setzt (Zeile für Zeile als Absatz, ohne Festbreite): ein Lauf solcher Absätze wird
    ein Codebaustein, wenn mindestens die Hälfte seiner Zeilen nach Code aussieht. `quelle`: Absatz -> sein Block."""
    aus: list[Baustein] = []
    lauf: list[Block] = []

    def schliessen() -> None:
        code = sum(codezeile(b.text) for b in lauf)
        if lauf and code and 2 * code >= len(lauf):
            aus.append(codebaustein([z for b in lauf for z in b.zeilen]))
        else:
            aus.extend(Baustein("absatz", b.rechteck.y0, b.rechteck.x0, text=b.text) for b in lauf)
        lauf.clear()

    for b in bausteine:
        block = quelle.get(id(b))
        if b.art == "absatz" and block is not None and _lose_zeile(block):
            lauf.append(block)
            continue
        schliessen()
        aus.append(b)
    schliessen()
    return aus
