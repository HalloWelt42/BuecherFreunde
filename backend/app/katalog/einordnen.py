"""Einordnen (BF-69): ein Lauf über den Bestand in Stapeln (`KATALOG_STAPEL`, Vorgabe 500 Titel), Werk für Werk in die
Kategorien des Katalogs, immer als Vorschlag.

Dran sind die Werke, die in keiner Kategorie stehen und keinen offenen Vorschlag haben, der Nummer nach. Je Stapel:

1. Regeln für jedes Werk und jede sichtbare Kategorie, die für seine Art gilt (`arten` ihres Bereichs).
2. Die KI in Anfragen zu `katalog_ki_je_anfrage` Werken einer Art, mit den Kategorien, die für diese Art gelten.
3. Regel und KI zusammen (katalog/vorschlaege.py) als offene Vorschläge, in einer Einheit mit dem Stand des Laufs.

Vor dem ersten Stapel fragt der Lauf die KI nach den alten Regalen, zu denen keine Regel passt (katalog/alt.py).
Antwortet die KI zu einer Anfrage nicht brauchbar, bleibt es für diese Werke bei den Regeln. Kann sie gar nicht (weg,
abgelehnt), pausiert der Lauf mit dem Grund und wird fortgesetzt, wenn der Mensch es will. Ohne Leitstelle ordnen nur die
Regeln ein."""

from __future__ import annotations

import asyncio
import math
from collections import defaultdict
from collections.abc import Sequence

from backend.app.core.database import db
from backend.app.katalog import alt, einstellungen, kategorien, lauf, merkmale, vorschlaege
from backend.app.katalog.ki_fragen import (
    SYSTEM_ALT, SYSTEM_EINORDNEN, KiFund, alt_aus, anfrage_alt, anfrage_einordnen, einordnung_aus, schema_alt, schema_einordnen,
)
from backend.app.katalog.lauf import Hintergrundlauf
from backend.app.katalog.merkmale import Buchmerkmale
from backend.app.katalog.modelle import Einordnungskategorie, Fund, Laufstand
from backend.app.katalog.regeln import Pruefer, Regeltreffer
from backend.app.services.ki import KiFehler, ki

# Dran: in keiner Kategorie des Katalogs und ohne offenen Vorschlag
DRAN = f"""NOT {merkmale.IN_KATEGORIE}
           AND NOT EXISTS (SELECT 1 FROM katalog_vorschlag v WHERE v.book_id = b.id AND v.stand = 'offen')"""
OHNE_KI = "Ohne KI: Keine Leitstelle eingetragen; eingeordnet nur nach Regeln"
TOKEN_JE_BUCH = 120


class KeinKatalog(Exception):
    pass


def teile(folge: Sequence, groesse: int) -> list[Sequence]:
    return [folge[i:i + groesse] for i in range(0, len(folge), groesse)]


def regelfunde(buecher: Sequence[Buchmerkmale], pruefer: Sequence[tuple[Einordnungskategorie, Pruefer]]) -> dict[tuple[int, int], list[Regeltreffer]]:
    """Je Werk und Kategorie seiner Art die Regeln, die treffen."""
    aus = {}
    for b in buecher:
        t = b.suchtext()
        for k, p in pruefer:
            if b.typ in k.arten and (tr := p.treffer(t)):
                aus[(b.id, k.id)] = tr
    return aus


class Einordner(Hintergrundlauf):
    art = "einordnen"
    kennung = "bf-katalog"

    # -- Bedienung -------------------------------------------------------------------------------------------------------
    async def beginnen(self, stapel_groesse: int | None = None) -> Laufstand:
        """Ein neuer Lauf; läuft schon einer oder ist er pausiert, bleibt es bei ihm."""
        z = await lauf.juengster(self.art)
        if z is not None and z.stand in ("laeuft", "pause"):
            return z.laufstand()
        if not await kategorien.zum_einordnen():
            raise KeinKatalog("Es gibt noch keinen Katalog mit sichtbaren Kategorien")
        nr = await lauf.anlegen(self.art, stapel_groesse or (await einstellungen.lesen()).stapel)
        await db.commit()                                  # die Aufgabe liest den Lauf über die gemeinsame Verbindung
        await self._starten(nr)
        return (await lauf.lesen(nr)).laufstand()

    async def pausieren(self) -> Laufstand:
        z = await lauf.juengster(self.art)
        if z is not None and await lauf.wechseln(z.id, "pause", "Pausiert", aus=("laeuft",)):
            await db.commit()
            self._halten()
        return await self.stand()

    async def fortsetzen(self) -> Laufstand:
        z = await lauf.juengster(self.art)
        if z is not None and await lauf.wechseln(z.id, "laeuft", "", aus=("pause",)):
            await db.commit()
            await self._starten(z.id)
        return await self.stand()

    # -- Arbeit ----------------------------------------------------------------------------------------------------------
    async def arbeiten(self, nr: int) -> None:
        kats = await kategorien.zum_einordnen()
        pruefer = [(k, Pruefer(k.regeln)) for k in kats]
        if not self.ki.bereit:
            await lauf.setzen(nr, grund=OHNE_KI)
        try:
            if (await lauf.lesen(nr)).stapel == 0 and self.ki.bereit:
                await self._alte_regale(nr, kats, pruefer)
            while await self._naechster_stapel(nr, kats, pruefer):
                pass
        except KiFehler as f:
            await lauf.wechseln(nr, "pause", f"Die KI kann gerade nicht: {f.grund}", aus=("laeuft",))

    async def _naechster_stapel(self, nr: int, kats: list[Einordnungskategorie], pruefer: list[tuple[Einordnungskategorie, Pruefer]]) -> bool:
        """Einen Stapel einordnen; False, wenn keiner mehr dran ist (dann ist der Lauf fertig)."""
        self.weiter_oder_halt()
        z = await lauf.lesen(nr)
        rest = await db.fetch_one(f"SELECT COUNT(*) AS n FROM books b WHERE {DRAN} AND b.id > ?", (z.nach_buch,))
        buecher = await merkmale.laden(f"{DRAN} AND b.id > ?", (z.nach_buch,), anzahl=z.stapel_groesse) if rest["n"] else []
        if not buecher:
            await lauf.wechseln(nr, "fertig", aus=("laeuft",))
            await lauf.setzen(nr, schritt="")
            return False
        stapel, gesamt = z.stapel + 1, z.stapel + math.ceil(rest["n"] / z.stapel_groesse)
        await lauf.setzen(nr, stapel_gesamt=gesamt, schritt=f"Stapel {stapel} von {gesamt}: Regeln")
        regeln = await asyncio.to_thread(regelfunde, buecher, pruefer)
        ki_funde = await self._ki(nr, stapel, gesamt, buecher, kats) if self.ki.bereit else {}
        await self._merken(nr, buecher, vorschlaege.zusammenfuehren(regeln, ki_funde))
        return True

    async def _ki(self, nr: int, stapel: int, gesamt: int, buecher: list[Buchmerkmale],
                  kats: list[Einordnungskategorie]) -> dict[tuple[int, int], KiFund]:
        """Die KI je Art der Werke in Anfragen zu `ki_je_anfrage`; was sie nicht brauchbar beantwortet, bleibt bei den Regeln."""
        je_anfrage = (await einstellungen.lesen()).ki_je_anfrage
        je_art: dict[str, list[Buchmerkmale]] = defaultdict(list)
        for b in buecher:
            je_art[b.typ].append(b)
        anfragen = [(art, t) for art, bs in je_art.items() for t in teile(bs, je_anfrage)]
        aus: dict[tuple[int, int], KiFund] = {}
        for i, (art, teil) in enumerate(anfragen, 1):
            passend = [k for k in kats if art in k.arten]
            if not passend:
                continue
            await lauf.setzen(nr, schritt=f"Stapel {stapel} von {gesamt}: KI, Anfrage {i} von {len(anfragen)}")
            nummern = {k.schluessel: k.id for k in passend}
            try:
                roh = await self.frage(SYSTEM_EINORDNEN, anfrage_einordnen(passend, teil), "katalog_einordnen", schema_einordnen(list(nummern)),
                                       titel=f"Katalog einordnen: Stapel {stapel}, Anfrage {i}", max_tokens=TOKEN_JE_BUCH * len(teil) + 200)
                gelesen = einordnung_aus(roh, len(teil), set(nummern))
            except KiFehler as f:
                if f.art != "einzeln":
                    raise
                await lauf.setzen(nr, grund=f"Stapel {stapel}, Anfrage {i}: {f.grund}; dort nur nach Regeln")
                continue
            for nummer, funde in gelesen.items():
                for f in funde:
                    aus[(teil[nummer - 1].id, nummern[f.schluessel])] = f
        return aus

    @staticmethod
    async def _merken(nr: int, buecher: list[Buchmerkmale], funde: list[Fund]) -> None:
        """Die Vorschläge des Stapels und der Stand des Laufs zusammen: so geht es nach einem Neustart hinter ihm weiter."""
        async with db.einheit():
            gemerkt = await vorschlaege.merken(funde, nr)
            mit = {f.buch_id for f in gemerkt}
            await lauf.zaehlen(nr, stapel=1, regeln=sum(f.quelle != "ki" for f in gemerkt), ki=sum(f.quelle != "regel" for f in gemerkt),
                               ohne_vorschlag=sum(b.id not in mit for b in buecher))
            await lauf.setzen(nr, nach_buch=buecher[-1].id)

    async def _alte_regale(self, nr: int, kats: list[Einordnungskategorie], pruefer: list[tuple[Einordnungskategorie, Pruefer]]) -> None:
        """Die KI zu den alten Regalen, zu denen keine Regel passt."""
        offen = await alt.ohne_regelvorschlag(pruefer)
        nummern = {k.schluessel: k.id for k in kats}
        anfragen = teile(offen, (await einstellungen.lesen()).ki_je_anfrage)
        for i, teil in enumerate(anfragen, 1):
            await lauf.setzen(nr, schritt=f"Alte Regale: KI, Anfrage {i} von {len(anfragen)}")
            try:
                roh = await self.frage(SYSTEM_ALT, anfrage_alt(kats, [n for _, n in teil]), "katalog_alte_regale", schema_alt(list(nummern)),
                                       titel=f"Alte Regale zuordnen: Anfrage {i}", max_tokens=80 * len(teil) + 200)
                gelesen = alt_aus(roh, len(teil), set(nummern))
            except KiFehler as f:
                if f.art != "einzeln":
                    raise
                await lauf.setzen(nr, grund=f"Alte Regale, Anfrage {i}: {f.grund}")
                continue
            await alt.ki_merken({teil[n - 1][0]: (nummern.get(s), satz) for n, (s, satz) in gelesen.items()})


einordner = Einordner(ki)
