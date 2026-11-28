"""Eine Seite nachbessern (BF-118): über die Leitstelle an das Modell `TEXTERKENNUNG_KI_MODELL`, die Antwort als Markdown
(texterkennung/markdown.py) in einer `Seitenerkennung` mit Herkunft ki. Welchen Weg es nimmt, sagt das Modell selbst, wie die
Leitstelle es beschreibt:

- **Bild**, wenn es Bilder lesen kann (Fähigkeit bild_beschreiben): das Seitenbild in Graustufen, die längste Kante höchstens
  `TEXTERKENNUNG_KI_KANTE` Bildpunkte, als JPEG; Anweisung in nachbessern.md.
- **Text** sonst: der klassisch erkannte Text der Seite, Block für Block mit seiner Lage auf der Seite (daraus liest das Modell
  Spalten und Kästen), die Bildflächen dazwischen; Anweisung in nachbessern_text.md. Ohne klassische Erkennung gibt es keinen.

So gilt ein Textmodell, das gerade geladen ist (Nutzer 28.11.2026: "wir nutzen erstmal nur 80b was gerade da ist"), und ein
Bildmodell, sobald es eingestellt ist, ohne zweite Einstellung. Die Flächen (Bilder der Seite) übernimmt die Nachbesserung in
beiden Wegen aus der klassischen Erkennung, damit die Bilder ihren Ausschnitt behalten. Eine Seite darf höchstens
`TEXTERKENNUNG_KI_FRIST_S` dauern, Laden des Modells eingeschlossen."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import fitz

from backend.app.core.config import settings
from backend.app.services import pdfseite
from backend.app.services.ki import KiFehler, ki
from backend.app.texterkennung import markdown
from backend.app.texterkennung.modelle import Lage, Seitenerkennung, Wort
from backend.app.texterkennung.textschicht import traegt_text

ANWEISUNG = {"bild": Path(__file__).with_name("nachbessern.md"), "text": Path(__file__).with_name("nachbessern_text.md")}
BILD = "bild_beschreiben"
GUETE = 85                                       # JPEG: so liest das Modell Schrift ohne Kanten, bei einem Viertel der Größe von PNG
TITEL = "Seite nachbessern"
OHNE_ERKENNUNG = "Diese Seite hat keine klassische Erkennung, die sich nachbessern ließe"


class Nachbesserungsfehler(Exception):
    """Die Seite ließ sich nicht nachbessern; der Text ist der Grund in Worten."""


@cache
def anweisung(weg: str) -> str:
    return ANWEISUNG[weg].read_text(encoding="utf-8").strip()


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


def seitenrahmen(pfad: Path, seite: int) -> fitz.Rect:
    """Die Dateiseite in PDF-Punkten; IndexError, wenn es sie nicht gibt."""
    with fitz.open(str(pfad)) as doc:
        if not 1 <= seite <= doc.page_count:
            raise IndexError(seite)
        return fitz.Rect(doc[seite - 1].rect)


SPALTENLUECKE = 0.03     # so breit (Anteil der Seitenbreite) ist eine Lücke zwischen zwei Wörtern einer Zeile mindestens, die
                         # Spalten trennt (gemessen: Wortabstand unter 1 %, Rinne eines Schulbuchs um 5 %)
RINNE_ANTEIL = 0.3       # so viele Zeilen mit Text müssen dieselbe Lücke haben, damit die Seite Spalten hat
RINNE_FELD = (0.3, 0.7)  # dort, in Anteilen der Seitenbreite, liegt eine Rinne
RAUSCHEN_UNTER = 50      # mittlere Sicherheit, unter der ein Stück Zeile als Rauschen gilt (gemessen am 28.11.2026: Text in Fotos
                         # 25 bis 48, Zeilen mit Code ab 56, Fließtext über 80)
BILD_AB = 0.05           # so groß (Anteil von Breite und Höhe) muss eine Bildfläche sein, damit sie zählt


@dataclass(frozen=True)
class _Stueck:
    """Ein Stück einer erkannten Zeile: ganz, oder eine Seite der Rinne."""
    y0: float
    x0: float
    text: str


def _lage(x0: float, y0: float, x1: float, y1: float, rahmen: fitz.Rect) -> str:
    b, h = max(rahmen.width, 1), max(rahmen.height, 1)
    return (f"links {(x0 - rahmen.x0) / b:.0%}, oben {(y0 - rahmen.y0) / h:.0%}, Breite {(x1 - x0) / b:.0%}, "
            f"Höhe {(y1 - y0) / h:.0%}")


def _rinne(zeilen: list[list[Wort]], rahmen: fitz.Rect) -> float | None:
    """Die Mitte der Lücke, die viele Zeilen gemeinsam haben (zwei Spalten), sonst None. Gezählt wird je Zeile ihre größte Lücke
    im Feld der Rinne, gesammelt in Fächern von zwei Hundertsteln der Seitenbreite."""
    breite = max(rahmen.width, 1)
    faecher: dict[int, int] = {}
    for woerter in zeilen:
        luecken = [(b.lage[0] - a.lage[2], (a.lage[2] + b.lage[0]) / 2) for a, b in zip(woerter, woerter[1:])]
        luecken = [(g, m) for g, m in luecken if g >= SPALTENLUECKE * breite and RINNE_FELD[0] <= (m - rahmen.x0) / breite <= RINNE_FELD[1]]
        if luecken:
            fach = round((max(luecken)[1] - rahmen.x0) / breite * 50)
            faecher[fach] = faecher.get(fach, 0) + 1
    if not faecher:
        return None
    fach, zahl = max(faecher.items(), key=lambda f: f[1])
    zahl += faecher.get(fach - 1, 0) + faecher.get(fach + 1, 0)
    return rahmen.x0 + fach / 50 * breite if zahl >= RINNE_ANTEIL * len(zeilen) else None


def _stueck(woerter: list[Wort]) -> _Stueck | None:
    if not woerter or sum(w.sicherheit for w in woerter) / len(woerter) < RAUSCHEN_UNTER:
        return None
    return _Stueck(min(w.lage[1] for w in woerter), min(w.lage[0] for w in woerter), " ".join(w.text for w in woerter))


def seite_als_text(e: Seitenerkennung, rahmen: fitz.Rect) -> str:
    """Der Text einer klassischen Erkennung für ein Textmodell, mit der Lage, aus der es Spalten und Kästen liest.

    Hat die Seite zwei Spalten (eine gemeinsame Rinne in vielen Zeilen, `_rinne`), wird jede Zeile dort geteilt, denn die klassische
    Erkennung liest Zeilen oft über beide Spalten hinweg; dann kommt erst die linke Spalte von oben nach unten, dann die rechte.
    Sonst Block für Block, wie das Programm sie abgrenzt, je Block seine Lage in Prozent der Seite. Ein Stück Zeile mit niedriger
    mittlerer Sicherheit (Text in Fotos) fällt weg; in den übrigen bleiben auch unsichere Wörter, denn oft ist es genau das falsch
    gelesene Wort, das das Modell richtigstellen soll. Bildflächen ab einer Größe stehen an ihrem Ort."""
    zeilen = [z.woerter for z in e.zeilen if z.woerter]
    flaechen = [f for f in e.flaechen if f[2] - f[0] >= BILD_AB * rahmen.width and f[3] - f[1] >= BILD_AB * rahmen.height]
    rinne = _rinne(zeilen, rahmen)
    if rinne is not None:
        spalten: dict[str, list[_Stueck]] = {"links": [], "rechts": []}
        for woerter in zeilen:
            for seite, teil in (("links", [w for w in woerter if (w.lage[0] + w.lage[2]) / 2 < rinne]),
                                ("rechts", [w for w in woerter if (w.lage[0] + w.lage[2]) / 2 >= rinne])):
                if (s := _stueck(teil)) is not None:
                    spalten[seite].append(s)
        for f in flaechen:
            spalten["links" if (f[0] + f[2]) / 2 < rinne else "rechts"].append(_Stueck(f[1], f[0], f"[Bildfläche, {_lage(*f, rahmen)}]"))
        return "\n\n".join(f"Spalte {seite}:\n" + "\n".join(s.text for s in sorted(liste, key=lambda s: (s.y0, s.x0)))
                            for seite, liste in spalten.items() if liste)
    bloecke: dict[int, list] = {}
    for z in e.zeilen:
        bloecke.setdefault(z.block, []).append(z)
    teile: list[tuple[float, float, str]] = []
    for nr, zs in bloecke.items():
        stuecke = [s for z in zs if (s := _stueck(z.woerter)) is not None]
        if not stuecke:
            continue
        woerter = [w for z in zs for w in z.woerter]
        x0, y0 = min(w.lage[0] for w in woerter), min(w.lage[1] for w in woerter)
        x1, y1 = max(w.lage[2] for w in woerter), max(w.lage[3] for w in woerter)
        teile.append((y0, x0, f"Block {nr} ({_lage(x0, y0, x1, y1, rahmen)}):\n" + "\n".join(s.text for s in stuecke)))
    for f in flaechen:
        teile.append((f[1], f[0], f"Bildfläche ({_lage(*f, rahmen)})"))
    hoehe = max(rahmen.height, 1)
    return "\n\n".join(t for _y, _x, t in sorted(teile, key=lambda t: (round(t[0] / hoehe, 2), t[1])))


async def _mit_frist(aufruf: Awaitable[tuple[str, str]]) -> tuple[str, str]:
    try:
        return await asyncio.wait_for(aufruf, settings.texterkennung_ki_frist_s)
    except KiFehler as f:
        raise Nachbesserungsfehler(f.grund) from f
    except TimeoutError as f:
        minuten = round(settings.texterkennung_ki_frist_s / 60)
        raise Nachbesserungsfehler(f"Die Leitstelle hat binnen {minuten} Minuten nicht geantwortet") from f


async def _mit_bild(pfad: Path, seite: int, modell: str) -> tuple[str, str, int]:
    bild, dpi = await asyncio.to_thread(seitenbild, pfad, seite, settings.texterkennung_ki_kante)
    antwort, name = await _mit_frist(ki.bildantwort(anweisung("bild"), bild, modell=modell, titel=TITEL, temperature=0,
                                                    max_tokens=settings.texterkennung_ki_token))
    return antwort, name, dpi


async def _mit_text(pfad: Path, seite: int, modell: str, klassisch: Seitenerkennung | None) -> tuple[str, str, int]:
    if klassisch is None or not traegt_text(klassisch):
        raise Nachbesserungsfehler(OHNE_ERKENNUNG)
    eingabe = seite_als_text(klassisch, await asyncio.to_thread(seitenrahmen, pfad, seite))

    async def fragen() -> tuple[str, str]:
        return await ki.antwort(anweisung("text"), eingabe, titel=TITEL, modell=modell, temperature=0,
                                max_tokens=settings.texterkennung_ki_token), modell

    antwort, name = await _mit_frist(fragen())
    return antwort, name, klassisch.dpi


async def seite_nachbessern(pfad: Path, seite: int, klassisch: Seitenerkennung | None) -> Seitenerkennung:
    """Die Dateiseite `seite` nachbessern. Wirft `Nachbesserungsfehler` mit Grund (Leitstelle, Modell, Frist, keine klassische
    Erkennung für den Weg über den Text, Antwort ohne lesbaren Text) und IndexError, wenn es die Seite nicht gibt."""
    beginn = time.monotonic()
    modell = settings.texterkennung_ki_modell
    try:
        weg = "bild" if BILD in await ki.faehigkeiten(modell) else "text"
    except KiFehler as f:
        raise Nachbesserungsfehler(f.grund) from f
    antwort, name, dpi = await (_mit_bild(pfad, seite, modell) if weg == "bild" else _mit_text(pfad, seite, modell, klassisch))
    md = markdown.bereinigt(antwort)
    if not pdfseite.lesbar(markdown.schlichter_text(md)):
        raise Nachbesserungsfehler("Die KI lieferte für diese Seite keinen lesbaren Text")
    flaechen: list[Lage] = list(klassisch.flaechen) if klassisch else []
    return Seitenerkennung(seite=seite, herkunft="ki", werkzeug=name, fassung=f"{modell} ({weg})", sprachen="", dpi=dpi,
                           erkannt_am=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           dauer_s=round(time.monotonic() - beginn, 2), flaechen=flaechen, markdown=md)
