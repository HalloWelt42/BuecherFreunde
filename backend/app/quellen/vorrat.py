"""Der Vorrat: Antworten der Quellen in der Datenbank, damit dieselbe Frage nicht zweimal hinausgeht. Treffer gelten lange,
leere Antworten kürzer, Fehler ganz kurz. Er hat eine Obergrenze; was abläuft oder am ältesten ist, geht zuerst."""

from __future__ import annotations

import time
import zlib
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.database import db

Art = Literal["treffer", "leer", "fehler"]


class Eintrag(BaseModel):
    adresse: str
    quelle: str
    art: Art
    inhalt: bytes = b""
    grund: str = ""
    geholt_am: float
    gilt_bis: float


class Bestand(BaseModel):
    """Wie viel von einer Quelle im Vorrat liegt."""

    antworten: int = 0
    bytes: int = 0


class Vorrat:
    def __init__(self, uhr: Callable[[], float] = time.time) -> None:
        self._uhr = uhr

    async def lies(self, adresse: str) -> Eintrag | None:
        z = await db.fetch_one("SELECT * FROM quelle_vorrat WHERE adresse = ? AND gilt_bis > ?", (adresse, self._uhr()))
        if z is None:
            return None
        return Eintrag(**{k: z[k] for k in ("adresse", "quelle", "art", "grund", "geholt_am", "gilt_bis")}, inhalt=zlib.decompress(z["inhalt"]) if z["inhalt"] else b"")

    async def merke(self, adresse: str, quelle: str, art: Art, gilt_s: float, inhalt: bytes = b"", grund: str = "") -> None:
        jetzt = self._uhr()
        await db.execute("INSERT OR REPLACE INTO quelle_vorrat(adresse, quelle, art, inhalt, grund, geholt_am, gilt_bis) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (adresse, quelle, art, zlib.compress(inhalt, 6) if inhalt else None, grund, jetzt, jetzt + gilt_s))
        await db.commit()

    async def zahlen(self) -> dict[str, Bestand]:
        zeilen = await db.fetch_all("SELECT quelle, COUNT(*) AS n, COALESCE(SUM(LENGTH(inhalt)), 0) AS b FROM quelle_vorrat WHERE art != 'fehler' AND gilt_bis > ? GROUP BY quelle", (self._uhr(),))
        return {z["quelle"]: Bestand(antworten=z["n"], bytes=z["b"]) for z in zeilen}

    async def aufraeumen(self) -> int:
        """Abgelaufenes geht, danach das Älteste, bis die Obergrenze hält. Liefert, wie viele gingen."""
        c = await db.execute("DELETE FROM quelle_vorrat WHERE gilt_bis <= ?", (self._uhr(),))
        weg = c.rowcount
        grenze = settings.quellen_vorrat_mb * 1_000_000
        c = await db.execute(
            "DELETE FROM quelle_vorrat WHERE adresse IN (SELECT adresse FROM (SELECT adresse, SUM(LENGTH(COALESCE(inhalt, '')) + 200) "
            "OVER (ORDER BY geholt_am DESC, adresse) AS summe FROM quelle_vorrat) WHERE summe > ?)", (grenze,))
        await db.commit()
        return weg + c.rowcount
