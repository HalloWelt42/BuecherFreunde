"""Eine Seite erkennen: das Seitenbild mit PyMuPDF in Graustufen gerendert (`TEXTERKENNUNG_DPI`), vom Programm erkannt
(werkzeug.py), die TSV-Ausgabe als `Seitenerkennung` in PDF-Punkten.

Aus der TSV zählen die Wörter (Ebene 5) mit ihrer Gliederung in Block, Absatz und Zeile und ihrer Sicherheit; ein Block ohne
ein einziges Wort ist eine Fläche (ein Bild, eine Linie). Ligaturzeichen ("fi" als ein Zeichen) kommen als ihre Buchstaben, wie
in der Textschicht (services/pdfseite.py)."""

from __future__ import annotations

import asyncio
import csv
import io
import time
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import fitz

from backend.app.core.config import settings
from backend.app.texterkennung import werkzeug
from backend.app.texterkennung.modelle import ErkannteZeile, Lage, Seitenerkennung, Wort

WORT, BLOCK = "5", "2"                          # Ebenen der TSV
LIGATUREN = range(0xFB00, 0xFB07)               # ff, fi, fl, ffi, ffl, langes st, st


@dataclass(frozen=True)
class Seitenbild:
    png: bytes
    rahmen: fitz.Rect                           # die Seite in PDF-Punkten (wie die Textschicht)
    dpi: int


def seitenbild(pfad: Path, seite: int, dpi: int) -> Seitenbild:
    """Die Dateiseite (ab 1) als PNG in Graustufen; IndexError, wenn es sie nicht gibt."""
    with fitz.open(str(pfad)) as doc:
        if not 1 <= seite <= doc.page_count:
            raise IndexError(seite)
        blatt = doc[seite - 1]
        bild = blatt.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
        bild.set_dpi(dpi, dpi)
        return Seitenbild(bild.tobytes("png"), fitz.Rect(blatt.rect), dpi)


def _ohne_ligaturen(text: str) -> str:
    if not any(ord(c) in LIGATUREN for c in text):
        return text
    return "".join(unicodedata.normalize("NFKC", c) if ord(c) in LIGATUREN else c for c in text)


def _zahl(feld: str) -> float:
    try:
        return float(feld)
    except ValueError:
        return 0.0


def _eintraege(ausgabe: str) -> Iterator[dict[str, str]]:
    yield from csv.DictReader(io.StringIO(ausgabe), delimiter="\t", quoting=csv.QUOTE_NONE)


def aus_tsv(ausgabe: str, rahmen: fitz.Rect, dpi: int) -> tuple[list[ErkannteZeile], list[Lage]]:
    """Zeilen und Flächen aus der TSV des Programms, umgerechnet von Bildpunkten in PDF-Punkte der Seite."""
    faktor = 72.0 / dpi

    def lage(e: dict[str, str]) -> Lage:
        x, y, b, h = (_zahl(e[k]) for k in ("left", "top", "width", "height"))
        return (round(rahmen.x0 + x * faktor, 2), round(rahmen.y0 + y * faktor, 2),
                round(rahmen.x0 + (x + b) * faktor, 2), round(rahmen.y0 + (y + h) * faktor, 2))

    zeilen: dict[tuple[int, int, int], ErkannteZeile] = {}
    bloecke: dict[int, Lage] = {}
    for e in _eintraege(ausgabe):
        block = int(_zahl(e.get("block_num", "0")))
        if e.get("level") == BLOCK:
            bloecke[block] = lage(e)
        if e.get("level") != WORT or not (e.get("text") or "").strip():
            continue
        schluessel = (block, int(_zahl(e["par_num"])), int(_zahl(e["line_num"])))
        zeile = zeilen.setdefault(schluessel, ErkannteZeile(block=schluessel[0], absatz=schluessel[1], zeile=schluessel[2], woerter=[]))
        sicherheit = max(0, min(100, round(_zahl(e.get("conf", "0")))))
        zeile.woerter.append(Wort(text=_ohne_ligaturen(e["text"].strip()), lage=lage(e), sicherheit=sicherheit))
    mit_text = {z.block for z in zeilen.values()}
    return list(zeilen.values()), [r for b, r in bloecke.items() if b not in mit_text]


def _jetzt() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


async def seite_erkennen(pfad: Path, seite: int) -> Seitenerkennung:
    """Die Dateiseite `seite` (ab 1) erkennen. Wirft `werkzeug.WerkzeugFehlt` ohne Programm und `werkzeug.Erkennungsfehler`
    mit Grund, wenn diese Seite scheitert (auch ein Seitenbild, das sich nicht rendern lässt)."""
    stand = await werkzeug.bereitschaft()
    if not stand.bereit:
        raise werkzeug.WerkzeugFehlt(stand.grund)
    beginn = time.monotonic()
    dpi = settings.texterkennung_dpi
    try:
        bild = await asyncio.to_thread(seitenbild, pfad, seite, dpi)
    except IndexError:
        raise
    except Exception as f:                              # noqa: BLE001 - eine kaputte Seite hält die übrigen nie auf
        raise werkzeug.Erkennungsfehler(f"Das Seitenbild ließ sich nicht rendern: {type(f).__name__}"[:200]) from f
    ausgabe = await werkzeug.tsv(bild.png, dpi)
    zeilen, flaechen = aus_tsv(ausgabe, bild.rahmen, dpi)
    return Seitenerkennung(seite=seite, werkzeug=stand.werkzeug, fassung=stand.fassung, sprachen=settings.texterkennung_sprachen,
                           dpi=dpi, erkannt_am=_jetzt(), dauer_s=round(time.monotonic() - beginn, 2), zeilen=zeilen,
                           flaechen=flaechen)
