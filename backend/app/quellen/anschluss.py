"""Die eine Schnittstelle, hinter der jede Quelle für Bücher steckt."""

from __future__ import annotations

from typing import Protocol

from backend.app.quellen.modelle import Angaben, Buchfrage
from backend.app.quellen.regeln import Regel


class Buchquelle(Protocol):
    regel: Regel

    async def nach_isbn(self, isbn: str) -> Angaben | None:
        """Das Buch mit genau dieser ISBN (auch in der anderen Länge) oder None."""

    async def nach_titel(self, frage: Buchfrage) -> Angaben | None:
        """Der Fund, der zu Titel und Autor am besten passt, oder None."""

    async def nach_doi(self, doi: str) -> Angaben | None:
        """Nur für Quellen, die DOI kennen; sonst None."""

    async def probe(self) -> None:
        """Eine kleine echte Anfrage; wirft QuelleFehler, wenn die Quelle nicht antwortet."""


class OhneDoi:
    async def nach_doi(self, doi: str) -> Angaben | None:
        return None
