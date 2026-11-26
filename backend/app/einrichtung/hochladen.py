"""Eine Sicherung in Teilen hochladen (BF-82), wie Dateien bei der Annahme: anmelden mit Name, Größe und Prüfsumme, dann Teile zu
`TEIL` Byte nacheinander mit `Upload-Offset`. Kein Teil braucht länger, als der Vorbau eine Anfrage offen hält; nach einem Abbruch
geht es am Stand des Servers weiter, gleicher Name und gleiche Prüfsumme finden den angefangenen wieder. Ist alles da, prüft der
Server die Prüfsumme; erst dann lässt sich die Sicherung einspielen (einrichtung/wiederherstellen.py).

Alles liegt im eigenen Ordner neben dem Bestand (`ablage()`), nie in der Datenbank, damit es den Tausch des Bestands übersteht:
je Sicherung `<id>.json` (Name, Größe, Prüfsumme) und `<id>.teil` (was angekommen ist; seine Länge ist der Stand)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from backend.app.annahme.dienst import TEIL
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.einrichtung.zustand import Einrichtungsfehler
from backend.app.services.storage import compute_hash


def ablage() -> Path:
    """Der Ordner für Sicherungen auf dem Weg hinein, neben dem Bestand (eine neue Installation hat dort Platz)."""
    return db.db_path.parent / ".wiederherstellen"


def _ordner() -> Path:
    return ablage() / "hochladen"


class Hochladen(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    groesse: int = Field(ge=1)
    sha256: Annotated[str, StringConstraints(to_lower=True, pattern=r"^[0-9a-f]{64}$")]


class Hochladestand(BaseModel):
    id: str
    name: str
    groesse: int
    sha256: str
    empfangen: int
    teil_groesse: int = TEIL
    fertig: bool                      # alles da und die Prüfsumme stimmt


class _Merker(BaseModel):
    id: str
    name: str
    groesse: int
    sha256: str
    geprueft: bool = False


class Versatz(Einrichtungsfehler):
    """Das Teil beginnt nicht am Stand des Servers; `empfangen` sagt, wo es weitergeht."""

    status = 409

    def __init__(self, empfangen: int) -> None:
        super().__init__(f"Weiter ab Byte {empfangen}")
        self.empfangen = empfangen


def _merker(kennung: str) -> _Merker:
    if not kennung.replace("-", "").isalnum():
        raise Einrichtungsfehler("Nicht gefunden", 404)
    try:
        return _Merker.model_validate_json((_ordner() / f"{kennung}.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Einrichtungsfehler("Diese Sicherung wird nicht hochgeladen", 404) from None


def _teil(kennung: str) -> Path:
    return _ordner() / f"{kennung}.teil"


def _stand(m: _Merker) -> Hochladestand:
    t = _teil(m.id)
    return Hochladestand(id=m.id, name=m.name, groesse=m.groesse, sha256=m.sha256, empfangen=t.stat().st_size if t.exists() else 0, fertig=m.geprueft)


def _speichern(m: _Merker) -> None:
    (_ordner() / f"{m.id}.json").write_text(m.model_dump_json(), encoding="utf-8")


def _anmelden(h: Hochladen) -> Hochladestand:
    if h.groesse > settings.wiederherstellen_mb_hoechstens * 1024 * 1024:
        raise Einrichtungsfehler("Größe: die Sicherung ist zu groß", 413)
    _ordner().mkdir(parents=True, exist_ok=True)
    for f in _ordner().glob("*.json"):
        m = _Merker.model_validate_json(f.read_text(encoding="utf-8"))
        if (m.name, m.sha256, m.groesse) == (h.name, h.sha256, h.groesse):
            return _stand(m)                                   # angefangen oder fertig: dort geht es weiter
    m = _Merker(id=str(uuid.uuid4()), name=h.name, groesse=h.groesse, sha256=h.sha256)
    _teil(m.id).touch()
    _speichern(m)
    return _stand(m)


async def anmelden(h: Hochladen) -> Hochladestand:
    return await asyncio.to_thread(_anmelden, h)


async def stand(kennung: str) -> Hochladestand:
    return _stand(_merker(kennung))


def _anhaengen(m: _Merker, versatz: int, daten: bytes) -> Hochladestand:
    t = _teil(m.id)
    if t.stat().st_size != versatz:                           # dazwischen kam ein anderes Teil
        raise Versatz(t.stat().st_size)
    with t.open("ab") as f:
        f.write(daten)
    if versatz + len(daten) == m.groesse:
        if compute_hash(t) != m.sha256:
            t.write_bytes(b"")
            raise Einrichtungsfehler("Die Prüfsumme stimmt nicht; bitte die Sicherung noch einmal hochladen", 422)
        m.geprueft = True
        _speichern(m)
    return _stand(m)


async def teil(kennung: str, versatz: int, strom: AsyncIterator[bytes], laenge: int) -> Hochladestand:
    """Ein Teil an den Stand; kommt es nicht ganz an, gilt nur, was vorher da war."""
    m = _merker(kennung)
    s = _stand(m)
    if m.geprueft:
        return s
    if versatz != s.empfangen:
        raise Versatz(s.empfangen)
    if laenge > TEIL:
        raise Einrichtungsfehler("Das Teil ist größer als vereinbart", 413)
    if versatz + laenge > m.groesse:
        raise Einrichtungsfehler("Mehr Daten als die angesagte Größe der Sicherung", 413)
    stuecke, n = [], 0
    async for stueck in strom:
        n += len(stueck)
        if n > laenge:
            raise Einrichtungsfehler("Mehr Daten als angesagt", 413)
        stuecke.append(stueck)
    if n != laenge:
        raise Einrichtungsfehler("Das Teil kam nicht vollständig an", 400)
    return await asyncio.to_thread(_anhaengen, m, versatz, b"".join(stuecke))


def datei(kennung: str) -> tuple[Path, str]:
    """Die fertig hochgeladene Sicherung und ihr Name; sonst 409."""
    m = _merker(kennung)
    if not m.geprueft:
        raise Einrichtungsfehler("Die Sicherung ist noch nicht ganz hochgeladen")
    return _teil(m.id), m.name
