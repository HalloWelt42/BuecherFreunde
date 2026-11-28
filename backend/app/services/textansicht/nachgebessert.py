"""Die Bausteine einer nachgebesserten Seite (BF-118): aus den Blöcken ihres Markdowns (texterkennung/markdown.py) statt aus
Zeilen mit Lage. Die Reihenfolge ist die der Nachbesserung; die Bilder der Seite kommen aus den Flächen der klassischen
Erkennung (in Lesereihenfolge von oben), je Zeile `[Bild: ...]` das nächste, mit der Unterschrift dahinter. Bleiben Flächen übrig,
stehen sie am Ende der Seite; nennt das Modell mehr Bilder als es Flächen gibt, bleibt nur die Unterschrift."""

from __future__ import annotations

import fitz

from backend.app.services.textansicht.erkannt import bilder_der_erkennung
from backend.app.services.textansicht.modelle import Baustein, Codeteil, Tabelle
from backend.app.services.textansicht.zuschnitt import zuschnitt
from backend.app.texterkennung import markdown
from backend.app.texterkennung.modelle import Seitenerkennung


def bausteine(seite: fitz.Page, erkennung: Seitenerkennung, zuschneiden: bool = True) -> list[Baustein]:
    """Die Bausteine in Lesereihenfolge; `oben` zählt nur die Folge (es gibt keine Lage auf der Seite). Bilder tragen ihre
    Nummer auf der Seite (Bild-Endpunkt), eng zugeschnitten wie auf jeder Seite; ihre Breite in Schriftgrößen gibt es ohne
    gemessene Schrift nicht."""
    bilder = iter(sorted(bilder_der_erkennung(erkennung), key=lambda r: (r.y0, r.x0)))
    aus: list[Baustein] = []

    def dazu(b: Baustein) -> None:
        b.oben = float(len(aus))
        aus.append(b)

    for b in markdown.bloecke(erkennung.markdown):
        if b.art == "bild":
            if (r := next(bilder, None)) is not None:
                dazu(Baustein("bild", 0, 0, rechteck=r))
            if b.text:
                dazu(Baustein("unterschrift", 0, 0, text=b.text))
        elif b.art == "code":
            dazu(Baustein("code", 0, 0, code=Codeteil(fitz.Rect(seite.rect), "", b.sprache, "", 0, 1, list(b.zeilen))))
        elif b.art == "tabelle":
            dazu(Baustein("tabelle", 0, 0, tabelle=Tabelle(list(b.kopf), [list(r) for r in b.reihen], list(b.zahlen))))
        else:
            dazu(Baustein(b.art, 0, 0, text=b.text))
    for r in bilder:
        dazu(Baustein("bild", 0, 0, rechteck=r))
    for nummer, b in enumerate(b for b in aus if b.art == "bild"):
        if zuschneiden:
            b.rechteck = zuschnitt(seite, b.rechteck)
        b.bild = nummer
    return aus
