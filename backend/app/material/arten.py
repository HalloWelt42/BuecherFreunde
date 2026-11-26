"""Arten des Begleitmaterials nach der Endung (Daten in material/arten.json): Name, Zeichen, ob es in der App öffnet und ob
sein Text in die Suche kommt."""

from __future__ import annotations

import json
import mimetypes
from functools import cache
from pathlib import Path

from pydantic import BaseModel

DATEI = Path(__file__).with_name("arten.json")
MEDIEN = {"md": "text/markdown; charset=utf-8", "markdown": "text/markdown; charset=utf-8", "txt": "text/plain; charset=utf-8",
          "epub": "application/epub+zip"}


class Materialart(BaseModel):
    art: str
    name: str
    zeichen: str
    endungen: list[str]
    oeffnen: bool
    lesbar: bool


@cache
def alle() -> list[Materialart]:
    return [Materialart(**a) for a in json.loads(DATEI.read_text(encoding="utf-8"))["arten"]]


def endung(name: str) -> str:
    return Path(name).suffix.lower().lstrip(".")


def von(name: str) -> Materialart:
    """Die Art einer Datei nach ihrer Endung; was keine kennt, ist die letzte (Datei)."""
    e = endung(name)
    return next((a for a in alle() if e and e in a.endungen), alle()[-1])


def nach_art(art: str) -> Materialart:
    return next((a for a in alle() if a.art == art), alle()[-1])


def medientyp(name: str) -> str:
    e = endung(name)
    return MEDIEN.get(e) or mimetypes.guess_type(f"x.{e}")[0] or "application/octet-stream"
