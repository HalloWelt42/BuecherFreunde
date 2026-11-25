"""Das Lexikon als Quelle für Bücher: Wikidata kennt Ausgaben über die ISBN (dort mit Strichen) und Werke über Titel und Autor,
Wikipedia erzählt, worum es geht."""

from __future__ import annotations

from backend.app.quellen import isbn as nummern
from backend.app.quellen import regeln, wiki
from backend.app.quellen.abgleich import OHNE_AUTOR, haupttitel, namen_gleich, suchbar, titel_naehe
from backend.app.quellen.abruf import oder_nichts
from backend.app.quellen.anschluss import OhneDoi
from backend.app.quellen.modelle import Angaben, Buchfrage, Fund
from backend.app.quellen.sprache import kuerzel
from backend.app.quellen.wiki import Eintrag

KANDIDATEN = 6


def _zahl(texte: list[str]) -> int:
    return next((int(float(t)) for t in texte if t.replace(".", "", 1).isdigit()), 0)


class Lexikon(OhneDoi):
    regel = regeln.WIKIPEDIA

    async def nach_isbn(self, isbn: str) -> Angaben | None:
        formen = nummern.formen(isbn)
        if not formen:
            return None
        bedingungen = [f"P{212 if len(f) == 13 else 957}={schreibung}" for f in formen for schreibung in dict.fromkeys((nummern.mit_strichen(f), f)) if schreibung]
        treffer = await wiki.suche(f"haswbstatement:{'|'.join(bedingungen)}", 3)
        eintrag = next(iter((await wiki.eintraege(list(treffer)[:1])).values()), None)
        return await self._angaben(eintrag, "isbn") if eintrag else None

    async def nach_titel(self, frage: Buchfrage) -> Angaben | None:
        """Ein Werk mit diesem Titel, dessen Autor stimmt."""
        titel = haupttitel(frage.titel).replace('"', " ").strip()
        if not suchbar(titel) or not frage.autoren:
            return None
        kandidaten = await wiki.eintraege(list(await wiki.suche(f'"{titel}" haswbstatement:P50', KANDIDATEN)))
        passend = [e for e in kandidaten.values() if max(titel_naehe(frage.titel, n) for n in (e.name, e.erster("P1476") or e.name, *e.auch)) >= OHNE_AUTOR]
        namen = await wiki.namen([a for e in passend for a in e.texte("P50")]) if passend else {}
        eintrag = next((e for e in passend if any(namen_gleich(namen.get(a, ""), b) for a in e.texte("P50") for b in frage.autoren)), None)
        return await self._angaben(eintrag, "titel") if eintrag else None

    async def _angaben(self, e: Eintrag, fund: Fund) -> Angaben:
        bezuege = {p: e.texte(p) for p in ("P50", "P123", "P407", "P136", "P921", "P31")}
        werk = e.erster("P629")                               # Ausgabe: Artikel und Gattung hängen am Werk
        uebrige = await wiki.eintraege([*(n for liste in bezuege.values() for n in liste), *([werk] if werk else [])])
        namen = {n: w.name for n, w in uebrige.items()}
        genannt = {p: [namen[n] for n in liste if namen.get(n)] for p, liste in bezuege.items()}
        am_werk = uebrige.get(werk)
        artikel = e.artikel or (am_werk.artikel if am_werk else {})
        sprache = next(iter(artikel), "")
        text = await oder_nichts(wiki.artikel(sprache, artikel[sprache])) if sprache else ""
        isbns = [n for p in ("P212", "P957") for t in e.texte(p) if (n := nummern.sauber(t))]
        return Angaben(
            quelle=self.regel.kennung, fund=fund, titel=e.erster("P1476") or e.name, untertitel=e.erster("P1680"), autoren=genannt["P50"] or e.texte("P2093"), verlag=next(iter(genannt["P123"]), ""),
            jahr=e.jahr("P577"), seiten=_zahl(e.texte("P1104")), isbn=isbns[0] if isbns else "", isbns=isbns, sprache=kuerzel(next(iter(genannt["P407"]), "")),
            beschreibung=wiki.buchtext(text or "") or e.beschreibung, kategorien=list(dict.fromkeys(genannt["P136"] + genannt["P921"])),
            roh={k: w for k, w in {"wikidata_id": e.id, "kurzbeschreibung": e.beschreibung, "isbn13": e.texte("P212"), "isbn10": e.texte("P957"), "autoren": genannt["P50"], "verlage": genannt["P123"],
                                   "sprachen": genannt["P407"], "genres": genannt["P136"], "themen": genannt["P921"], "typen": genannt["P31"],
                                   "wikipedia_titel": artikel.get(sprache, ""), "sitelinks": artikel}.items() if w})

    async def probe(self) -> None:
        await wiki.eintraege(["Q311449"], probe=True)
