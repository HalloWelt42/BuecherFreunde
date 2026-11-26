"""Wo die deutsche Fassung liegt (BF-71): in der Kellerwolke neben dem Original unter `Fassungen/<sprache>/` mit dem Namen des
Originals; ohne Kellerwolke (oder solange das Original nur auf dem Gerät liegt) im lokalen Bestand im Ordner des Buchs, wie
die Begleiter, ebenfalls unter `Fassungen/<sprache>/`. Das Original bleibt unverändert.

Wird neu gesetzt, bekommt die Datei in der Kellerwolke eine neue Version (nur auf den zuletzt gelesenen Stand); ist sie dort
verschwunden, wird sie neu angelegt."""

from __future__ import annotations

import asyncio
import posixpath
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, Response

from backend.app.ablage.antwort import wolke_antwort
from backend.app.ablage.namen import ablageort, dateiname
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.models.fassung import Ablageort
from backend.app.services.fassungen import Buchangaben, FassungZeile
from backend.app.services.storage import get_storage_path

ORDNER = "Fassungen"
EPUB = "application/epub+zip"


async def ort(sprache: str, b: Buchangaben) -> Ablageort:
    ablage = await db.fetch_one("SELECT name, pfad FROM ablage_datei WHERE hash = ?", (b.hash,))
    if ablage is not None and wolke.bereit:
        pfad = ablage["pfad"] or ""
        if pfad:
            ordner, name = posixpath.dirname(pfad), posixpath.basename(pfad)
        else:
            fach, name = ablageort(b.id, b.title, b.author, b.file_name, b.file_format)
            ordner = f"{settings.ablage_ordner}/Bücher/{fach}"
        return Ablageort(ort="kellerwolke", pfad=f"{ordner}/{ORDNER}/{sprache}/{name}")
    name = dateiname(Path(b.file_name).name or f"{b.id}.epub")
    return Ablageort(ort="geraet", pfad=str(get_storage_path(b.hash) / ORDNER / sprache / name))


def _schreiben(ziel: Path, daten: bytes) -> None:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    teil = ziel.with_name(f".{ziel.name}.teil")
    teil.write_bytes(daten)
    teil.replace(ziel)


async def ablegen(f: FassungZeile, b: Buchangaben, daten: bytes) -> tuple[str, str | None]:
    """Die Datei an ihren Ort; gibt Pfad und Knoten (nur in der Kellerwolke) zurück."""
    o = await ort(f.sprache, b)
    if o.ort == "geraet":
        await asyncio.to_thread(_schreiben, Path(o.pfad), daten)
        return o.pfad, None
    zwischen = settings.zwischen_dir / "fassungen" / f"{f.id}.epub"
    await asyncio.to_thread(_schreiben, zwischen, daten)
    try:
        return o.pfad, await _in_die_wolke(o.pfad, zwischen, f.knoten)
    finally:
        zwischen.unlink(missing_ok=True)


async def _in_die_wolke(pfad: str, datei: Path, knoten: str | None) -> str:
    if knoten:
        try:
            k = await wolke.knoten(knoten)
            await wolke.inhalt_ersetzen(knoten, datei, k.get("etag") or "")
            return knoten
        except WolkeFehler as f:
            if f.status != 404:                              # fort: neu anlegen
                raise
    ordner = await wolke.ordner(posixpath.dirname(pfad))
    try:
        return (await wolke.datei_schreiben(pfad, datei))["id"]
    except WolkeFehler as f:
        if f.status not in (409, 412):
            raise
    name = posixpath.basename(pfad)                          # liegt schon da (etwa nach einem Halt vor dem Merken)
    async for k in wolke.kinder(ordner["id"]):
        if k.get("name") == name:
            await wolke.inhalt_ersetzen(k["id"], datei, k.get("etag") or "")
            return k["id"]
    raise WolkeFehler("Die Datei der Fassung ist in der Kellerwolke nicht zu finden")


def name_zum_lesen(b: Buchangaben, sprache: str) -> str:
    stamm = Path(b.file_name).stem or f"Buch {b.id}"
    return dateiname(f"{stamm} ({sprache}).epub")


async def antwort(request: Request, f: FassungZeile, b: Buchangaben, herunterladen: bool = False) -> Response | None:
    """Die abgelegte Datei, wenn sie den Stand der Blöcke zeigt; sonst None (dann wird sie frisch gesetzt)."""
    if not f.datei_aktuell:
        return None
    name = name_zum_lesen(b, f.sprache)
    if f.knoten and wolke.bereit:
        return await wolke_antwort(request, f.knoten, EPUB, name, herunterladen)
    pfad = Path(f.datei)
    if not f.knoten and pfad.is_file():
        return FileResponse(pfad, media_type=EPUB, filename=name, content_disposition_type="attachment" if herunterladen else "inline")
    return None
