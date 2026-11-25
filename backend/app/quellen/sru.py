"""Gemeinsamer Weg zu Katalogen mit SRU und MARC 21: nach ISBN und nach Titel, der beste Satz gewinnt."""

from __future__ import annotations

import re
from typing import Any

from backend.app.quellen import isbn as nummern
from backend.app.quellen import marc
from backend.app.quellen.abruf import Frage, hole
from backend.app.quellen.modelle import Angaben
from backend.app.quellen.regeln import Regel


def wort(text: str) -> str:
    """Text für eine Anfrage in Anführungszeichen: ohne Zeichen, die dort etwas bedeuten."""
    return re.sub(r"\s+", " ", re.sub(r'["\\()*?^]', " ", text or "")).strip()


class Katalog:
    def __init__(self, regel: Regel, format_: str) -> None:
        self.regel, self._format = regel, format_

    def frage(self, anfrage: str, hoechstens: int) -> Frage:
        felder = (("version", "1.1"), ("operation", "searchRetrieve"), ("query", anfrage), ("recordSchema", self._format), ("maximumRecords", str(hoechstens)))
        return Frage(self.regel.adresse, felder, kopf=(("Accept", "application/xml, text/xml"),), lies=self._lies, ist_leer=lambda w: not w)

    def _lies(self, inhalt: bytes) -> list[dict[str, Any]]:
        return [marc.angaben(s, self.regel.kennung).model_dump(exclude_defaults=True) for s in marc.saetze(inhalt) if marc.ist_buch(s)]

    async def funde(self, anfrage: str, hoechstens: int = 5, probe: bool = False) -> list[Angaben]:
        return [Angaben(**f) for f in await hole(self.regel, self.frage(anfrage, hoechstens), probe=probe) or []]


def _traegt(a: Angaben, isbn: str) -> bool:
    return any(nummern.gleich(n, isbn) for n in a.isbns)


def vollstaendigster(funde: list[Angaben], isbn: str) -> Angaben | None:
    """Von den Sätzen, die diese ISBN selbst tragen, der mit den meisten Angaben; was ihm fehlt, kommt aus den übrigen."""
    eigene = [a for a in funde if _traegt(a, isbn)]
    if not eigene:
        return None
    eigene.sort(key=lambda a: (sum(map(bool, (a.titel, a.autoren, a.verlag, a.jahr, a.seiten, a.sprache, a.beschreibung, a.untertitel))), len(a.kategorien)), reverse=True)
    bester, uebrige = eigene[0], eigene[1:]
    dazu = {"beschreibung": bester.beschreibung or next((a.beschreibung for a in uebrige if a.beschreibung), ""),
            "kategorien": bester.kategorien or next((a.kategorien for a in uebrige if a.kategorien), []),
            "personen": {k: w for a in (*uebrige, bester) for k, w in a.personen.items()}}
    return bester.model_copy(update={**dazu, "fund": "isbn"})
