"""Umschläge und Autorenfotos holen und auf die Größen der App bringen. Nur von Rechnern, die zu einer Quelle gehören."""

from __future__ import annotations

import asyncio
import io
import logging
from urllib.parse import urlsplit

from PIL import Image

from backend.app.quellen.abruf import abruf
from backend.app.quellen.fehler import AnfrageFalsch
from backend.app.quellen.regeln import regel_fuer_rechner

logger = logging.getLogger("buecherfreunde.quellen.bilder")
HOECHSTENS = 25_000_000
PLATZHALTER_BIS = 1000              # kleinere Dateien sind leere Bilder
UMSCHLAG = (800, 1200, 85)
FOTOS = {"foto.jpg": (400, 600, 85), "foto_thumb.jpg": (120, 180, 80), "foto_mini.jpg": (48, 72, 75)}


async def _hole(adresse: str) -> bytes:
    regel = regel_fuer_rechner(urlsplit(adresse).hostname or "")
    if regel is None:
        raise AnfrageFalsch("Das Bild liegt bei keiner bekannten Quelle")
    return await abruf().lade(regel, adresse, HOECHSTENS)


def _jpeg(daten: bytes, groessen: dict[str, tuple[int, int, int]]) -> dict[str, bytes] | None:
    if len(daten) < PLATZHALTER_BIS:
        return None
    try:
        with Image.open(io.BytesIO(daten)) as bild:
            rgb = bild.convert("RGB")
    except (OSError, ValueError, Image.DecompressionBombError) as f:
        logger.warning("Bild unlesbar: %s", f)
        return None
    aus = {}
    for name, (breite, hoehe, guete) in groessen.items():
        klein = rgb.copy()
        klein.thumbnail((breite, hoehe), Image.LANCZOS)
        puffer = io.BytesIO()
        klein.save(puffer, format="JPEG", quality=guete, optimize=True)
        aus[name] = puffer.getvalue()
    return aus


async def umschlag(adresse: str) -> bytes | None:
    """Ein Umschlag als JPEG; None, wenn dort kein brauchbares Bild liegt. Wirft QuelleFehler."""
    bilder = await asyncio.to_thread(_jpeg, await _hole(adresse), {"cover.jpg": UMSCHLAG})
    return bilder["cover.jpg"] if bilder else None


async def autorenfoto(adresse: str) -> dict[str, bytes] | None:
    """Ein Foto in drei Größen; None, wenn dort kein brauchbares Bild liegt. Wirft QuelleFehler."""
    return await asyncio.to_thread(_jpeg, await _hole(adresse), FOTOS)
