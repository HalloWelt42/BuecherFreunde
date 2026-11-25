"""K10plus, der gemeinsame Katalog der Bibliotheksverbünde: auch englische Fachbücher, ältere und vergriffene Bücher, oft mit
Inhaltsangabe. Ohne Anmeldung, Angaben unter CC0."""

from __future__ import annotations

from backend.app.quellen import isbn as nummern
from backend.app.quellen import regeln, sru
from backend.app.quellen.abgleich import bester, haupttitel, nachname, suchbar
from backend.app.quellen.anschluss import OhneDoi
from backend.app.quellen.modelle import Angaben, Buchfrage

TITEL_HOECHSTENS = 8


class Verbundkatalog(OhneDoi):
    regel = regeln.K10PLUS

    def __init__(self) -> None:
        self._katalog = sru.Katalog(self.regel, "marcxml")

    async def nach_isbn(self, isbn: str) -> Angaben | None:
        formen = nummern.formen(isbn)
        if not formen:
            return None
        return sru.vollstaendigster(await self._katalog.funde(" or ".join(f"pica.isb={n}" for n in formen)), isbn)

    async def nach_titel(self, frage: Buchfrage) -> Angaben | None:
        titel = sru.wort(haupttitel(frage.titel))
        if not suchbar(titel):
            return None
        teile = [f'pica.tit="{titel}"']
        if frage.autoren and (name := sru.wort(nachname(frage.autoren[0]))):
            teile.append(f'pica.per="{name}"')
        return bester(frage, await self._katalog.funde(" and ".join(teile), TITEL_HOECHSTENS))

    async def probe(self) -> None:
        await self._katalog.funde("pica.isb=9783257229530", 1, probe=True)
