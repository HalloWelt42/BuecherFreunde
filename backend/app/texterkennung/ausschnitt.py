"""Einen Ausschnitt einer gescannten Seite lesen (BF-123): jemand markiert im Original ein Rechteck, und hier wird sein Text.

Der Bereich ist in Anteilen der Seite angegeben (0 bis 1, unabhängig vom Zoom). Gelesen wird über die Leitstelle mit dem Modell
der Nachbesserung (TEXTERKENNUNG_KI_MODELL), auf demselben Weg wie dort (texterkennung/nachbessern.py): kann das Modell Bilder
lesen, bekommt es den Ausschnitt als Bild; sonst die Wörter der klassischen Erkennung, deren Mitte im Rechteck liegt, mit ihrer
Lage (`seite_als_text`). Heraus kommt schlichter Text für die Markierung, die Suche und das Vorlesen.

Antwortet die Leitstelle nicht oder liefert sie nichts Lesbares, kommt `Ausschnittsfehler` mit dem Grund und, wenn die klassische
Erkennung dort Wörter hat, ihrem Text als `notbehelf`: so geht nichts verloren, und ein späteres "Erneut lesen" bessert nach."""

from __future__ import annotations

import asyncio
from functools import cache
from pathlib import Path

import fitz
from pydantic import BaseModel, Field, model_validator

from backend.app.core.config import settings
from backend.app.services import pdfseite
from backend.app.services.ki import KiFehler, ki
from backend.app.texterkennung import markdown
from backend.app.texterkennung.modelle import ErkannteZeile, Seitenerkennung
from backend.app.texterkennung.nachbessern import BILD, GUETE, Nachbesserungsfehler, mit_frist, seite_als_text, seitenrahmen
from backend.app.texterkennung.textschicht import sichere_woerter

ANWEISUNG = {"bild": Path(__file__).with_name("ausschnitt_bild.md"), "text": Path(__file__).with_name("ausschnitt_text.md")}
TITEL = "Markierung lesen"
OHNE_TEXT = "Im Ausschnitt steht kein Text"
OHNE_ERKENNUNG = "Die Seite ist noch nicht erkannt; sie kommt bald dran, dann noch einmal lesen"


class Bereich(BaseModel, frozen=True):
    """Ein Rechteck auf einer Seite in Anteilen ihrer Breite und Höhe, links oben (x0, y0) bis rechts unten (x1, y1)."""
    x0: float = Field(ge=0, le=1)
    y0: float = Field(ge=0, le=1)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _richtig_herum(self) -> Bereich:
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            raise ValueError("Ein Bereich braucht Breite und Höhe")
        return self

    def in_punkten(self, rahmen: fitz.Rect) -> fitz.Rect:
        return fitz.Rect(rahmen.x0 + self.x0 * rahmen.width, rahmen.y0 + self.y0 * rahmen.height,
                         rahmen.x0 + self.x1 * rahmen.width, rahmen.y0 + self.y1 * rahmen.height)


class Ausschnittsfehler(Exception):
    """Der Ausschnitt ließ sich nicht lesen; der Text ist der Grund in Worten, `notbehelf` der Text der klassischen Erkennung."""

    def __init__(self, grund: str, notbehelf: str = "") -> None:
        super().__init__(grund)
        self.notbehelf = notbehelf


@cache
def anweisung(weg: str) -> str:
    return ANWEISUNG[weg].read_text(encoding="utf-8").strip()


def im_bereich(e: Seitenerkennung, rechteck: fitz.Rect) -> Seitenerkennung:
    """Die Erkennung, beschränkt auf die Wörter, deren Mitte im Rechteck liegt, und die Flächen, die es berührt."""
    zeilen = []
    for z in e.zeilen:
        woerter = [w for w in z.woerter if rechteck.contains(fitz.Point((w.lage[0] + w.lage[2]) / 2, (w.lage[1] + w.lage[3]) / 2))]
        if woerter:
            zeilen.append(ErkannteZeile(block=z.block, absatz=z.absatz, zeile=z.zeile, woerter=woerter))
    flaechen = [f for f in e.flaechen if fitz.Rect(f).intersects(rechteck)]
    return e.model_copy(update={"zeilen": zeilen, "flaechen": flaechen, "markdown": ""})


def klassischer_text(e: Seitenerkennung) -> str:
    """Die sicheren Wörter, Zeile für Zeile: der Notbehelf, wenn die Leitstelle nicht liest."""
    return "\n".join(t for z in e.zeilen if (t := " ".join(w.text for w in sichere_woerter(z))))


def ausschnittsbild(pfad: Path, seite: int, bereich: Bereich, kante: int) -> bytes:
    """Der Ausschnitt der Dateiseite (ab 1) als JPEG in Graustufen, die längere Kante höchstens `kante`, nie gröber als die
    Seite für die Erkennung; IndexError, wenn es die Seite nicht gibt."""
    with fitz.open(str(pfad)) as doc:
        if not 1 <= seite <= doc.page_count:
            raise IndexError(seite)
        blatt = doc[seite - 1]
        rechteck = bereich.in_punkten(blatt.rect)
        dpi = max(72, min(settings.texterkennung_dpi, int(kante * 72 / max(rechteck.width, rechteck.height, 1))))
        return blatt.get_pixmap(dpi=dpi, clip=rechteck, colorspace=fitz.csGRAY, alpha=False).tobytes("jpeg", jpg_quality=GUETE)


async def _frage(aufruf) -> str:
    try:
        antwort, _name = await mit_frist(aufruf)
    except Nachbesserungsfehler as f:
        raise Ausschnittsfehler(str(f)) from f
    return antwort


async def lies(pfad: Path, seite: int, bereich: Bereich, klassisch: Seitenerkennung | None) -> str:
    """Der Text des Bereichs auf der Dateiseite `seite`; leer, wenn dort keiner steht. Wirft `Ausschnittsfehler` (Leitstelle,
    Frist, nichts Lesbares, Seite noch nicht erkannt) und IndexError, wenn es die Seite nicht gibt."""
    rahmen = await asyncio.to_thread(seitenrahmen, pfad, seite)
    teil = im_bereich(klassisch, bereich.in_punkten(rahmen)) if klassisch else None
    notbehelf = klassischer_text(teil) if teil else ""
    modell = settings.texterkennung_ki_modell
    try:
        mit_bild = BILD in await ki.faehigkeiten(modell)
    except KiFehler as f:
        raise Ausschnittsfehler(f.grund, notbehelf) from f
    try:
        if mit_bild:
            bild = await asyncio.to_thread(ausschnittsbild, pfad, seite, bereich, settings.texterkennung_ki_kante)
            antwort = await _frage(ki.bildantwort(anweisung("bild"), bild, modell=modell, titel=TITEL, temperature=0,
                                                  max_tokens=settings.texterkennung_ki_token))
        else:
            if teil is None:
                raise Ausschnittsfehler(OHNE_ERKENNUNG)
            if not teil.zeilen:
                return ""
            antwort = await _frage(_textantwort(seite_als_text(teil, rahmen), modell))
    except Ausschnittsfehler as f:
        raise Ausschnittsfehler(str(f), f.notbehelf or notbehelf) from f
    text = markdown.schlichter_text(markdown.bereinigt(antwort)).strip()
    if text and not pdfseite.lesbar(text):
        raise Ausschnittsfehler("Die KI lieferte für den Ausschnitt keinen lesbaren Text", notbehelf)
    return text


async def _textantwort(eingabe: str, modell: str) -> tuple[str, str]:
    return await ki.antwort(anweisung("text"), eingabe, titel=TITEL, modell=modell, temperature=0,
                            max_tokens=settings.texterkennung_ki_token), modell
