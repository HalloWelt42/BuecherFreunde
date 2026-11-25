"""Deutsche Nationalbibliothek (SRU, MARC 21): deutschsprachige Bücher seit 1913 mit Sachgruppen, Schlagworten, Auflage und der
Kennung des Autors in der Normdatei. Ohne Anmeldung, Angaben unter CC0. Umschläge gibt sie nicht zur Nachnutzung frei."""

from __future__ import annotations

from backend.app.quellen import isbn as nummern
from backend.app.quellen import regeln, sru
from backend.app.quellen.abgleich import bester, haupttitel, nachname, suchbar
from backend.app.quellen.anschluss import OhneDoi
from backend.app.quellen.modelle import Angaben, Buchfrage

TITEL_HOECHSTENS = 10


class Nationalbibliothek(OhneDoi):
    regel = regeln.DNB

    def __init__(self) -> None:
        self._katalog = sru.Katalog(self.regel, "MARC21-xml")

    async def nach_isbn(self, isbn: str) -> Angaben | None:
        formen = nummern.formen(isbn)
        if not formen:
            return None
        return sru.vollstaendigster(await self._katalog.funde(" or ".join(f"NUM={n}" for n in formen)), isbn)

    async def nach_titel(self, frage: Buchfrage) -> Angaben | None:
        titel = sru.wort(haupttitel(frage.titel))
        if not suchbar(titel):
            return None
        teile = [f'TIT="{titel}"', "MAT=books"]
        if frage.autoren and (name := sru.wort(nachname(frage.autoren[0]))):
            teile.append(f'PER="{name}"')
        if frage.sprache == "de":
            teile.append("SPR=ger")
        return bester(frage, await self._katalog.funde(" and ".join(teile), TITEL_HOECHSTENS))

    async def probe(self) -> None:
        await self._katalog.funde("NUM=9783257229530", 1, probe=True)
