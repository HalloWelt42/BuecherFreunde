"""Der Ausschnitt einer Abbildung eng um ihren Inhalt (BF-103): Rand in der Farbe des Hintergrunds und ein dünner Rahmen
ringsum fallen weg, gemessen an einem kleinen Graubild des Ausschnitts. So stimmt das Seitenverhältnis des Bausteins mit dem
ausgelieferten Bild überein, und am Telefon steht keine große leere Fläche."""

from __future__ import annotations

from collections import Counter

import fitz

BILDPUNKTE = 400                # so viele Bildpunkte hat die längere Seite des Bilds, an dem der Rand gemessen wird
ZOOM = 2.0                      # höchstens so viele Bildpunkte je Punkt der Seite (kleine Abbildungen)
LUFT = 2.0                      # Punkte Luft um den Inhalt
HINTERGRUND_ABSTAND = 12        # Grauwerte: so weit weicht ein Bildpunkt vom Hintergrund ab, um Inhalt zu sein
INHALT_ANTEIL = 0.004           # Anteil einer Bildzeile: so viele Bildpunkte Inhalt braucht sie (gegen Rauschen)
RAHMEN_DECKUNG = 0.9            # Anteil: so weit reicht eine Rahmenlinie über ihre Kante
RAHMEN_BAND = 0.04              # Anteil der Kante: in diesem Band außen liegt ein Rahmen
RAHMEN_INNEN_FREI = 0.5         # Anteil: so wenig Inhalt trägt die Bildzeile gleich innen am Rahmen höchstens


def _profil(pix: fitz.Pixmap, x0: int, y0: int, x1: int, y1: int) -> tuple[list[int], list[int]]:
    """Bildpunkte mit Inhalt je Zeile und je Spalte im Bereich; Hintergrund ist der häufigste Grauwert am Rand des Bereichs."""
    b, s = pix.width, pix.samples
    rand = s[y0 * b + x0:y0 * b + x1] + s[(y1 - 1) * b + x0:(y1 - 1) * b + x1] + bytes(
        s[y * b + x] for y in range(y0, y1) for x in (x0, x1 - 1))
    hinter = Counter(rand).most_common(1)[0][0]
    tafel = bytes(1 if abs(v - hinter) > HINTERGRUND_ABSTAND else 0 for v in range(256))
    zeilen = [s[y * b + x0:y * b + x1].translate(tafel).count(1) for y in range(y0, y1)]
    spalten = [s[y0 * b + x::b][:y1 - y0].translate(tafel).count(1) for x in range(x0, x1)]
    return zeilen, spalten


def _rahmen(werte: list[int], laenge: int) -> tuple[int, int] | None:
    """Wo innen eine dünne Rahmenlinie vorn und hinten endet: im äußeren Band über fast die ganze Kante, und gleich dahinter
    fast leer (sonst ist es Inhalt, der bis an den Rand reicht). None ohne solchen Rahmen."""
    band = max(2, round(len(werte) * RAHMEN_BAND))
    voll = [n >= RAHMEN_DECKUNG * laenge for n in werte]

    def innen_ab(reihe: list[int]) -> int | None:
        linie = next((k for k in range(min(band, len(reihe))) if voll[reihe[k]]), None)
        if linie is None:
            return None
        while linie + 1 < len(reihe) and voll[reihe[linie + 1]]:
            linie += 1
        frei = linie + 1
        if linie < band and frei < len(reihe) and werte[reihe[frei]] < RAHMEN_INNEN_FREI * laenge:
            return reihe[frei]
        return None

    vorn = innen_ab(list(range(len(werte))))
    hinten = innen_ab(list(range(len(werte) - 1, -1, -1)))
    return (vorn, hinten + 1) if vorn is not None and hinten is not None and hinten + 1 > vorn else None


def inhalt(pix: fitz.Pixmap) -> fitz.IRect | None:
    """Wo im Graubild Inhalt steht: ohne Rand in der Farbe des Hintergrunds und ohne einen dünnen Rahmen, der ringsum über
    fast die ganze Kante läuft. None, wenn nichts darin steht."""
    b, h = pix.width, pix.height
    if b < 3 or h < 3:
        return None
    x0, y0, x1, y1 = 0, 0, b, h
    zeilen, spalten = _profil(pix, x0, y0, x1, y1)
    oben_unten, links_rechts = _rahmen(zeilen, b), _rahmen(spalten, h)
    if oben_unten and links_rechts and oben_unten[1] - oben_unten[0] > 2 and links_rechts[1] - links_rechts[0] > 2:
        (y0, y1), (x0, x1) = oben_unten, links_rechts
        zeilen, spalten = _profil(pix, x0, y0, x1, y1)
    ys = [y0 + i for i, n in enumerate(zeilen) if n > max(1, (x1 - x0) * INHALT_ANTEIL)]
    xs = [x0 + i for i, n in enumerate(spalten) if n > max(1, (y1 - y0) * INHALT_ANTEIL)]
    if not ys or not xs:
        return None
    return fitz.IRect(xs[0], ys[0], xs[-1] + 1, ys[-1] + 1)


def zuschnitt(seite: fitz.Page, r: fitz.Rect) -> fitz.Rect:
    """Der Ausschnitt einer Abbildung eng um ihren Inhalt, mit etwas Luft, nie größer als der Ausschnitt samt Luft."""
    weit = (r + (-LUFT, -LUFT, LUFT, LUFT)) & seite.rect
    if weit.is_empty or weit.width < 1 or weit.height < 1:
        return weit
    zoom = min(ZOOM, BILDPUNKTE / max(weit.width, weit.height))
    pix = seite.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=weit, colorspace=fitz.csGRAY, alpha=False)
    innen = inhalt(pix)
    if innen is None:
        return weit
    eng = fitz.Rect((pix.x + innen.x0) / zoom, (pix.y + innen.y0) / zoom, (pix.x + innen.x1) / zoom, (pix.y + innen.y1) / zoom)
    return (eng + (-LUFT, -LUFT, LUFT, LUFT)) & weit
