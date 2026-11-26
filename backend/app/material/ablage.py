"""Wo Begleitmaterial liegt (BF-81), hinter einer Schnittstelle mit zwei Umsetzungen. Der Rest der App kennt nur sie.

- Kellerwolke: jede Datei ist Begleiter des Originals mit eigener Rolle (`material_<kennung>`, die Kellerwolke kennt je
  Hauptdatei und Rolle höchstens einen Begleiter) und dem Zusatz `.material.<name>` im Namen. So liegt sie neben dem Original
  und zieht beim Verschieben, Umbenennen und in den Papierkorb mit. Rolle und Zusatz erlaubt die Kellerwolke nur aus
  Kleinbuchstaben, Ziffern (nur im Zusatz), `_` und `-`; der Name in der App bleibt, wie er ist.
- Gerät (ohne Kellerwolke, oder solange das Original nur auf dem Gerät liegt): im Buchordner unter `Material/`.

Welche gilt, entscheidet der Ort des Originals; vorhandenes Material bleibt an dem Ort, den seine Zeile nennt."""

from __future__ import annotations

import asyncio
import posixpath
import re
import shutil
import tempfile
import unicodedata
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from backend.app.ablage.antwort import wolke_antwort
from backend.app.ablage.namen import dateiname
from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.material import arten
from backend.app.material.modelle import Ort
from backend.app.services.storage import get_storage_path

ORDNER = "Material"
ZUSATZ_VORN = ".material"
ZUSATZ_HOECHSTENS = 40                         # so lang darf ein Zusatz in der Kellerwolke sein
TEIL_HOECHSTENS = 20                           # je Teil des Zusatzes
VERSUCHE = 9                                   # so viele Namen probiert die Ablage, wenn einer neben dem Original vergeben ist
UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "ae", "Ö": "oe", "Ü": "ue"})
BUCHSTABEN = str.maketrans("0123456789abcdef", "abcdefghijklmnop")   # Kennung der Rolle: nur Buchstaben


class Buchort(BaseModel):
    """Das Original eines Buchs, neben dem das Material liegt."""

    buch_id: int
    hash: str
    knoten: str | None                         # in der Kellerwolke; leer: nur auf dem Gerät


class Abgelegt(BaseModel):
    ort: Ort
    knoten: str | None = None
    rolle: str = ""
    pfad: str


async def buchort(buch: int) -> Buchort | None:
    z = await db.fetch_one("SELECT b.id, b.hash, a.knoten FROM books b LEFT JOIN ablage_datei a ON a.hash = b.hash WHERE b.id = ?", (buch,))
    return Buchort(buch_id=z["id"], hash=z["hash"], knoten=z["knoten"]) if z else None


# -- Namen in der Kellerwolke -------------------------------------------------------------------------------------------------

def _teil(text: str, hoechstens: int) -> str:
    """Ein Teil des Zusatzes: klein, ohne Umlaute und Akzente, nur a-z, 0-9, _ und -."""
    t = unicodedata.normalize("NFKD", (text or "").translate(UMSCHRIFT))
    t = re.sub(r"[^a-z0-9_-]+", "-", "".join(z for z in t if not unicodedata.combining(z)).lower())
    return t.strip("-_")[:hoechstens].strip("-_")


def zusatz(name: str, nummer: int = 1) -> str:
    """`.material.<name>.<endung>`, etwa Lösungen.pdf: `.material.loesungen.pdf`; ab der zweiten Nummer mit `-2`."""
    stamm, endung = posixpath.splitext(name)
    e = _teil(endung, 10)
    teil_e = f".{e}" if e and e[0].isalnum() else ""
    nr = f"-{nummer}" if nummer > 1 else ""
    platz = min(TEIL_HOECHSTENS, ZUSATZ_HOECHSTENS - len(ZUSATZ_VORN) - 1 - len(teil_e)) - len(nr)
    s = _teil(stamm, platz) or "datei"                    # beginnt nach _teil immer mit Buchstabe oder Ziffer
    return f"{ZUSATZ_VORN}.{s}{nr}{teil_e}"


def rolle(nr: str) -> str:
    """Die Rolle am Original aus der Kennung des Materials (nur Buchstaben, wie die Kellerwolke es verlangt)."""
    return "material_" + nr.replace("-", "")[:12].lower().translate(BUCHSTABEN)


# -- Schnittstelle --------------------------------------------------------------------------------------------------------------

class Materialablage(ABC):
    ort: Ort
    papierkorb: bool                           # Entfernen legt in einen Papierkorb (sonst endgültig)

    @abstractmethod
    async def ablegen(self, buch: Buchort, nr: str, name: str, *, datei: Path | None = None, knoten: str | None = None,
                      behalten: bool = False) -> Abgelegt:
        """Eine Datei als Material des Buchs ablegen: vom Gerät (`datei`, `behalten`: die Quelle bleibt) oder aus der
        Kellerwolke (`knoten`)."""

    @abstractmethod
    async def umbenennen(self, buch: Buchort, zeile: dict, name: str) -> Abgelegt:
        """Den Namen ändern, die Endung bleibt in der App, wie sie ist."""

    @abstractmethod
    async def entfernen(self, zeile: dict) -> None: ...

    @abstractmethod
    async def antwort(self, request: Request, zeile: dict, herunterladen: bool) -> Response: ...

    @abstractmethod
    def lokal(self, zeile: dict) -> AsyncIterator[Path]:
        """Die Datei auf dem Gerät für die Dauer eines Blocks (etwa zum Lesen des Texts)."""


class Kellerwolke(Materialablage):
    ort: Ort = "kellerwolke"
    papierkorb = True

    async def ablegen(self, buch: Buchort, nr: str, name: str, *, datei: Path | None = None, knoten: str | None = None,
                      behalten: bool = False) -> Abgelegt:
        assert buch.knoten, "Material in der Kellerwolke braucht ein Original dort"
        r = rolle(nr)
        for nummer in range(1, VERSUCHE + 1):
            try:
                if knoten:
                    k = await wolke.begleiter_anhaengen(buch.knoten, r, knoten, zusatz(name, nummer))
                else:
                    assert datei is not None
                    k = await wolke.begleiter_schreiben(buch.knoten, r, zusatz(name, nummer), datei)
                break
            except WolkeFehler as f:
                if f.status != 409 or nummer == VERSUCHE:
                    raise
        if datei is not None and not behalten:
            datei.unlink(missing_ok=True)
        return Abgelegt(ort=self.ort, knoten=k["id"], rolle=r, pfad=k.get("pfad") or k["name"])

    async def umbenennen(self, buch: Buchort, zeile: dict, name: str) -> Abgelegt:
        """Neuer Zusatz hinter dem Stamm des Originals, im selben Ordner; der Begleiter bleibt in seiner Rolle."""
        k = await wolke.knoten(zeile["knoten"])
        haupt = await wolke.knoten(buch.knoten) if buch.knoten else {"name": k["name"]}
        stamm = posixpath.splitext(haupt["name"])[0]
        for nummer in range(1, VERSUCHE + 1):
            try:
                neu = await wolke.umziehen(zeile["knoten"], k["parent_id"], f"{stamm}{zusatz(name, nummer)}")
                break
            except WolkeFehler as f:
                if f.status != 409 or nummer == VERSUCHE:
                    raise
        return Abgelegt(ort=self.ort, knoten=zeile["knoten"], rolle=zeile["rolle"], pfad=neu.get("pfad") or neu["name"])

    async def entfernen(self, zeile: dict) -> None:
        await wolke.papierkorb(zeile["knoten"])            # schon fort: dann bleibt nur, die Zeile zu löschen

    async def antwort(self, request: Request, zeile: dict, herunterladen: bool) -> Response:
        return await wolke_antwort(request, zeile["knoten"], arten.medientyp(zeile["name"]), zeile["name"], herunterladen)

    @asynccontextmanager
    async def lokal(self, zeile: dict) -> AsyncIterator[Path]:
        ordner = settings.zwischen_dir / "material"
        ordner.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ordner) as hier:
            ziel = Path(hier) / dateiname(Path(zeile["name"]).name)
            await asyncio.to_thread(wolke.holen, zeile["knoten"], ziel)
            yield ziel


class Geraet(Materialablage):
    ort: Ort = "geraet"
    papierkorb = False

    @staticmethod
    def ordner(buch: Buchort) -> Path:
        return get_storage_path(buch.hash) / ORDNER

    @staticmethod
    def _frei(ordner: Path, name: str) -> Path:
        """Ein Name, der im Ordner noch frei ist: sonst mit (2), (3) und so fort vor der Endung."""
        ziel = ordner / dateiname(name)
        stamm, endung = posixpath.splitext(ziel.name)
        n = 2
        while ziel.exists():
            ziel = ordner / dateiname(f"{stamm} ({n}){endung}")
            n += 1
        return ziel

    async def ablegen(self, buch: Buchort, nr: str, name: str, *, datei: Path | None = None, knoten: str | None = None,
                      behalten: bool = False) -> Abgelegt:
        ordner = self.ordner(buch)
        ordner.mkdir(parents=True, exist_ok=True)
        ziel = self._frei(ordner, name)
        if knoten:                                          # aus der Kellerwolke, das Buch liegt aber nur hier
            await asyncio.to_thread(wolke.holen, knoten, ziel)
        else:
            assert datei is not None
            await asyncio.to_thread(shutil.copy2 if behalten else shutil.move, datei, ziel)
        return Abgelegt(ort=self.ort, pfad=str(ziel))

    async def umbenennen(self, buch: Buchort, zeile: dict, name: str) -> Abgelegt:
        alt = Path(zeile["pfad"])
        ziel = self._frei(alt.parent, name)
        await asyncio.to_thread(alt.rename, ziel)
        return Abgelegt(ort=self.ort, pfad=str(ziel))

    async def entfernen(self, zeile: dict) -> None:
        Path(zeile["pfad"]).unlink(missing_ok=True)

    async def antwort(self, request: Request, zeile: dict, herunterladen: bool) -> Response:
        pfad = Path(zeile["pfad"])
        if not pfad.is_file():
            raise HTTPException(404, "Die Datei liegt nicht mehr im Buchordner")
        return FileResponse(pfad, media_type=arten.medientyp(zeile["name"]), filename=zeile["name"], headers={"Accept-Ranges": "bytes"},
                            content_disposition_type="attachment" if herunterladen else "inline")

    @asynccontextmanager
    async def lokal(self, zeile: dict) -> AsyncIterator[Path]:
        yield Path(zeile["pfad"])


KELLERWOLKE, GERAET = Kellerwolke(), Geraet()


def fuer_buch(buch: Buchort) -> Materialablage:
    """Wohin neues Material kommt: neben das Original in der Kellerwolke, sonst in den Buchordner."""
    return KELLERWOLKE if wolke.bereit and buch.knoten else GERAET


def von(zeile: dict) -> Materialablage:
    """Wo vorhandenes Material liegt, nach seiner Zeile."""
    return KELLERWOLKE if zeile["ort"] == "kellerwolke" else GERAET
