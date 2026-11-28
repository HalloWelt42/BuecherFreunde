"""Eine Seite nachbessern (BF-118): das Seitenbild über die Leitstelle an ein Bildmodell (`TEXTERKENNUNG_KI_MODELL`, Fähigkeit
bild_beschreiben), die Antwort als Markdown (texterkennung/markdown.py) in einer `Seitenerkennung` mit Herkunft ki. Die Anweisung
steht in nachbessern.md neben dieser Datei.

Das Seitenbild: Graustufen, so fein, dass die längste Kante höchstens `TEXTERKENNUNG_KI_KANTE` Bildpunkte hat, als JPEG. Die
Flächen (Bilder der Seite) übernimmt die Nachbesserung aus der klassischen Erkennung, damit die Bilder ihren Ausschnitt behalten."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import fitz

from backend.app.core.config import settings
from backend.app.services import pdfseite
from backend.app.services.ki import KiFehler, ki
from backend.app.texterkennung import markdown
from backend.app.texterkennung.modelle import Seitenerkennung

ANWEISUNG = Path(__file__).with_name("nachbessern.md")
GUETE = 85                                       # JPEG: so liest das Modell Schrift ohne Kanten, bei einem Viertel der Größe von PNG
TITEL = "Seite nachbessern"


class Nachbesserungsfehler(Exception):
    """Die Seite ließ sich nicht nachbessern; der Text ist der Grund in Worten."""


@cache
def anweisung() -> str:
    return ANWEISUNG.read_text(encoding="utf-8").strip()


def seitenbild(pfad: Path, seite: int, kante: int) -> tuple[bytes, int]:
    """Die Dateiseite (ab 1) als JPEG in Graustufen und die Auflösung, mit der sie gerendert ist; IndexError, wenn es sie nicht
    gibt."""
    with fitz.open(str(pfad)) as doc:
        if not 1 <= seite <= doc.page_count:
            raise IndexError(seite)
        blatt = doc[seite - 1]
        dpi = max(36, min(300, int(kante * 72 / max(blatt.rect.width, blatt.rect.height, 1))))
        bild = blatt.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
        return bild.tobytes("jpeg", jpg_quality=GUETE), dpi


async def seite_nachbessern(pfad: Path, seite: int, klassisch: Seitenerkennung | None) -> Seitenerkennung:
    """Die Dateiseite `seite` nachbessern. Wirft `Nachbesserungsfehler` mit Grund (Leitstelle, Modell, Antwort ohne lesbaren
    Text) und IndexError, wenn es die Seite nicht gibt."""
    beginn = time.monotonic()
    bild, dpi = await asyncio.to_thread(seitenbild, pfad, seite, settings.texterkennung_ki_kante)
    try:
        antwort, modell = await ki.bildantwort(anweisung(), bild, modell=settings.texterkennung_ki_modell, titel=TITEL,
                                               temperature=0, max_tokens=settings.texterkennung_ki_token)
    except KiFehler as f:
        raise Nachbesserungsfehler(f.grund) from f
    md = markdown.bereinigt(antwort)
    if not pdfseite.lesbar(markdown.schlichter_text(md)):
        raise Nachbesserungsfehler("Die KI lieferte für diese Seite keinen lesbaren Text")
    return Seitenerkennung(seite=seite, herkunft="ki", werkzeug=modell, fassung=settings.texterkennung_ki_modell, sprachen="",
                           dpi=dpi, erkannt_am=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           dauer_s=round(time.monotonic() - beginn, 2), flaechen=list(klassisch.flaechen) if klassisch else [],
                           markdown=md)
