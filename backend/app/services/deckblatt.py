"""Das Deckblatt eines Buchs: ein Weg für Aufnahme, "Umschlag neu" und "Bibliothek ergänzen".

PDF: die erste Seite. EPUB: das Bild, das das Buch selbst als Umschlag nennt (Kennzeichen im Verzeichnis, Verweis "cover",
Umschlagseite), nie ein beliebiges großes Bild aus dem Inneren; nennt es keins, wird die erste Seite gezeichnet. Eine leere
Fläche ist nie ein Deckblatt, dann bleibt der gezeichnete Ersatz. Immer JPEG. Dazu der Befund, ob ein Umschlag schlicht ist
(`schlicht`, BF-59)."""

from __future__ import annotations

import base64
import io
import logging
import posixpath
import re
import zipfile
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup
from PIL import Image, ImageStat

logger = logging.getLogger("buecherfreunde.deckblatt")
BREITE, HOEHE = 800, 1200
HOCH_MINDESTENS, BREIT_MINDESTENS = 200, 140
VERHAELTNIS = (0.4, 1.35)              # Breite zu Höhe; breiter ist es ein Bild aus dem Buch, kein Umschlag
BILD = (".jpg", ".jpeg", ".png", ".gif", ".webp")
SEITE = (420, 600)                     # so groß wird eine gezeichnete erste Seite gesetzt
LEER_STREUUNG = 2.0                    # streut die Helligkeit weniger, ist die Fläche leer
# Schlicht (BF-59): ein fast weißer Umschlag ohne Farbe, etwa die erste Seite eines PDFs mit nur dem Titel darauf. Solche
# Bücher bekommen in der Oberfläche ein gestaltetes Deckblatt. Gemessen trifft das im Bestand 754 von 4.731 Umschlägen.
SCHLICHT_GROESSE = (60, 90)            # so klein wird der Umschlag für den Befund
SCHLICHT_HELL_UEBER = 230              # Helligkeit (0 bis 255), über der ein Bildpunkt als weiß gilt
SCHLICHT_HELL_ANTEIL = 0.85            # so viele Bildpunkte müssen mindestens weiß sein
SCHLICHT_SAETTIGUNG_UNTER = 0.08       # mittlere Sättigung (HSV, 0 bis 1), unter der der Umschlag als farblos gilt


def von_datei(datei: Path, format_: str = "") -> bytes | None:
    art = (format_ or datei.suffix).lower().lstrip(".")
    try:
        if art == "pdf":
            return erste_seite(datei)
        if art == "epub":
            return _aus_epub(datei) or erste_seite(datei)
        if art == "mobi":
            return erste_seite(datei)
    except Exception as f:                                  # noqa: BLE001 - ohne Deckblatt bleibt der gezeichnete Ersatz
        logger.info("Kein Deckblatt aus %s: %s", datei.name, f)
    return None


def erste_seite(datei: Path) -> bytes | None:
    import fitz

    fitz.TOOLS.mupdf_display_errors(False)                  # fehlende Schriften eines Buchs gehören in kein Protokoll
    with fitz.open(str(datei)) as doc:
        if doc.is_reflowable:
            doc.layout(width=SEITE[0], height=SEITE[1], fontsize=13)
        if not len(doc):
            return None
        bild = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    seite = Image.frombytes("RGB", (bild.width, bild.height), bild.samples)
    return None if leer(seite) else _jpeg(seite)


def _jpeg(bild: Image.Image) -> bytes:
    bild = bild.convert("RGB")
    bild.thumbnail((BREITE, HOEHE), Image.Resampling.LANCZOS)
    puffer = io.BytesIO()
    bild.save(puffer, format="JPEG", quality=85, optimize=True)
    return puffer.getvalue()


def leer(bild: Image.Image) -> bool:
    """Eine Fläche fast ohne Inhalt, etwa eine gezeichnete Seite, deren Bild in der Datei fehlt (BF-17)."""
    return ImageStat.Stat(bild.convert("L")).stddev[0] < LEER_STREUUNG


def schlicht(daten: bytes) -> bool:
    """Ob der Umschlag fast weiß und farblos ist. Ein Bild, das sich nicht lesen lässt, gilt wie ein fehlendes als schlicht."""
    try:
        with Image.open(io.BytesIO(daten)) as bild:
            bild.draft("RGB", (max(1, bild.width // 4), max(1, bild.height // 4)))     # JPEG: gleich kleiner lesen
            klein = bild.convert("RGB").resize(SCHLICHT_GROESSE, Image.Resampling.BICUBIC)
    except Exception:                                       # noqa: BLE001 - kein lesbares Bild
        return True
    helligkeit = klein.convert("L").histogram()
    weiss = sum(helligkeit[SCHLICHT_HELL_UEBER + 1:]) / (SCHLICHT_GROESSE[0] * SCHLICHT_GROESSE[1])
    saettigung = ImageStat.Stat(klein.convert("HSV")).mean[1] / 255
    return weiss >= SCHLICHT_HELL_ANTEIL and saettigung < SCHLICHT_SAETTIGUNG_UNTER


def taugt(daten: bytes) -> Image.Image | None:
    """Das Bild, wenn es nach Größe, Form und Inhalt ein Umschlag sein kann."""
    try:
        bild = Image.open(io.BytesIO(daten))
        bild.load()
    except Exception:                                       # noqa: BLE001 - kein lesbares Bild
        return None
    passt = bild.height >= HOCH_MINDESTENS and bild.width >= BREIT_MINDESTENS and VERHAELTNIS[0] <= bild.width / bild.height <= VERHAELTNIS[1]
    return bild if passt and not leer(bild) else None


def _aus_epub(datei: Path) -> bytes | None:
    with zipfile.ZipFile(datei) as z:
        for daten in _genannt(z):
            if bild := taugt(daten):
                return _jpeg(bild)
    return None


def _genannt(z: zipfile.ZipFile) -> Iterator[bytes]:
    """Bilder, die das Buch als Umschlag nennt, das sicherste zuerst."""
    namen = set(z.namelist())
    opf = _verzeichnis(z, namen)
    if not opf:
        return
    ordner = posixpath.dirname(opf)
    doc = BeautifulSoup(z.read(opf), "html.parser")
    teile = {t.get("id", ""): t for t in _alle(doc, "item")}

    def lies(weg: str) -> Iterator[bytes]:
        if weg in namen:
            yield z.read(weg)

    # 1. Kennzeichen im Verzeichnis, 2. Verweis "cover": Kennung oder Dateiname
    for t in teile.values():
        if "cover-image" in (t.get("properties") or "").split():
            yield from lies(_weg(ordner, t.get("href", "")))
    for m in _alle(doc, "meta"):
        if (m.get("name") or "").lower() == "cover" and (inhalt := m.get("content") or ""):
            if inhalt in teile:
                weg = _weg(ordner, teile[inhalt].get("href", ""))
                yield from (lies(weg) if weg.lower().endswith(BILD) else _auf_seite(z, namen, weg))
            yield from lies(_weg(ordner, inhalt))
            yield from (z.read(n) for n in namen if posixpath.basename(n) == posixpath.basename(inhalt) and n.lower().endswith(BILD))
    # 3. Umschlagseite laut Wegweiser, 4. die ersten Seiten, wenn sie fast nur ein Bild zeigen
    for r in _alle(doc, "reference"):
        if (r.get("type") or "").lower() in ("cover", "coverpage", "title-page"):
            yield from _auf_seite(z, namen, _weg(ordner, r.get("href", "").split("#")[0]))
    for s in _alle(doc, "itemref")[:2]:
        if (t := teile.get(s.get("idref", ""))) is not None:
            yield from _auf_seite(z, namen, _weg(ordner, t.get("href", "")), nur_bild=True)
    # 5. Dateien, die Umschlag heißen
    for n in sorted(namen):
        if n.lower().endswith(BILD) and re.search(r"(^|[^a-z])(cover|umschlag|titelbild|title)([^a-z]|$)", posixpath.basename(n).lower()):
            yield z.read(n)


def _verzeichnis(z: zipfile.ZipFile, namen: set[str]) -> str:
    if "META-INF/container.xml" in namen:
        wurzel = BeautifulSoup(z.read("META-INF/container.xml"), "html.parser").find("rootfile")
        if wurzel and wurzel.get("full-path") in namen:
            return wurzel["full-path"]
    return next((n for n in namen if n.lower().endswith(".opf")), "")


def _alle(doc: BeautifulSoup, name: str) -> list:
    return doc.find_all(lambda t: t.name.split(":")[-1] == name)


def _weg(ordner: str, href: str) -> str:
    return posixpath.normpath(posixpath.join(ordner, unquote(href or "")))


def _auf_seite(z: zipfile.ZipFile, namen: set[str], weg: str, nur_bild: bool = False) -> Iterator[bytes]:
    """Das erste Bild einer Seite; `nur_bild`: nur wenn kaum Text daneben steht."""
    if weg not in namen:
        return
    doc = BeautifulSoup(z.read(weg), "html.parser")
    if nur_bild and len((doc.body or doc).get_text(strip=True)) > 200:
        return
    for t in doc.find_all(["img", "image"])[:2]:
        quelle = t.get("src") or t.get("xlink:href") or t.get("href") or ""
        if quelle.startswith("data:"):
            try:
                yield base64.b64decode(quelle.split(",", 1)[1])
            except ValueError:
                continue
        elif (ziel := _weg(posixpath.dirname(weg), quelle)) in namen:
            yield z.read(ziel)
