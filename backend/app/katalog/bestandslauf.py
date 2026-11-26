"""Entwurf aus dem Bestand (BF-69): der Standard-Katalog, angepasst an die eigene Bibliothek, als Lauf im Hintergrund.

1. Regeln zählen: je Kategorie des Standards (und ihrer Teile) die Werke ihrer Art, die ihre Regeln treffen, über den
   ganzen Bestand, ohne KI.
2. Neu aus dem Bestand: häufige Schlagworte (ab `KATALOG_NEU_AB` Bücher), zu denen keine Kategorie passt, gibt der Lauf
   der KI; sie schlägt daraus höchstens fünf neue Kategorien vor (Herkunft neu). Ohne KI fällt der Schritt weg.
3. Der Entwurf (katalog/entwurf.py `aus_bestand`) ersetzt den bisherigen. Wer inzwischen einen anderen Weg gewählt hat,
   hat den Lauf ersetzt; dann bleibt dessen Entwurf."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Sequence

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.katalog import datei, einstellungen, entwurf, lauf, merkmale
from backend.app.katalog.ki_fragen import SYSTEM_NEU, NeueKategorie, anfrage_neu, neue_aus, schema_neu
from backend.app.katalog.lauf import Hintergrundlauf
from backend.app.katalog.merkmale import Buchmerkmale
from backend.app.katalog.modelle import Katalog, Katalogkategorie, Laufstand, Regeln
from backend.app.katalog.regeln import Pruefer, klein, suchtext
from backend.app.services.ki import KiFehler, ki

HAEUFIGE_HOECHSTENS = 30                       # so viele häufige Schlagworte bekommt die KI
OHNE_KI = "Ohne KI: Keine Leitstelle eingetragen; keine neuen Kategorien aus dem Bestand"
ERSETZT = "Ersetzt durch einen anderen Weg zum Entwurf"


def treffer_zaehlen(standard: Katalog, buecher: Sequence[Buchmerkmale]) -> dict[str, set[int]]:
    """Je Schlüssel (Kategorien und Teile) die Werke seiner Bereichsart, die seine Regeln treffen."""
    texte = [(b.id, b.typ, b.suchtext()) for b in buecher]
    aus: dict[str, set[int]] = {}
    for bereich, k in standard.kategorien():
        for kat in (k, *k.teile):
            p = Pruefer(kat.regeln)
            aus[kat.schluessel] = {nr for nr, typ, t in texte if typ in bereich.arten and p.trifft(t)}
    return aus


def haeufige_ohne_kategorie(standard: Katalog, buecher: Sequence[Buchmerkmale], ab: int) -> list[tuple[str, int]]:
    """Schlagworte, die keine Regel des Standards trifft, mit der Zahl ihrer Bücher, die häufigsten zuerst."""
    pruefer = [Pruefer(kat.regeln) for _, k in standard.kategorien() for kat in (k, *k.teile)]
    zahl: Counter = Counter()
    schreibweise: dict[str, Counter] = {}
    for b in buecher:
        for s in {klein(w): w for w in b.schlagworte}.values():
            schreibweise.setdefault(klein(s), Counter())[s] += 1
            zahl[klein(s)] += 1
    passt = {w for w in zahl if any(p.trifft(suchtext("", "", [w], merkmale.sachgruppen_aus([w]))) for p in pruefer)}
    haeufig = [(schreibweise[w].most_common(1)[0][0], n) for w, n in zahl.most_common() if n >= ab and w not in passt]
    return haeufig[:HAEUFIGE_HOECHSTENS]


def neue_kategorien(standard: Katalog, neue: Sequence[NeueKategorie]) -> list[tuple[str, Katalogkategorie]]:
    """Die Vorschläge der KI als Kategorien des Entwurfs, je mit freiem Schlüssel in ihrem Bereich."""
    vergeben = set(standard.schluessel())
    aus = []
    for n in neue:
        schluessel = datei.freier_schluessel(f"{n.bereich}/{datei.schluesselteil(n.name)}", vergeben)
        vergeben.add(schluessel)
        aus.append((n.bereich, Katalogkategorie(schluessel=schluessel, name=n.name, zeichen=n.zeichen, ki_beschreibung=n.ki_beschreibung,
                                                regeln=Regeln(schlagworte=n.schlagworte), herkunft="neu")))
    return aus


def treffer_der_neuen(standard: Katalog, neue: Sequence[tuple[str, Katalogkategorie]], buecher: Sequence[Buchmerkmale]) -> dict[str, set[int]]:
    arten = {b.schluessel: b.arten for b in standard.bereiche}
    texte = [(b.id, b.typ, b.suchtext()) for b in buecher]
    return {k.schluessel: {nr for nr, typ, t in texte if typ in arten[s] and Pruefer(k.regeln).trifft(t)} for s, k in neue}


class Bestandslauf(Hintergrundlauf):
    art = "bestand"
    kennung = "bf-katalog-bestand"

    async def beginnen(self) -> Laufstand:
        """Ein neuer Lauf; läuft schon einer, bleibt es bei ihm. Der bisherige Entwurf fällt weg."""
        z = await lauf.juengster(self.art)
        if z is not None and z.stand == "laeuft":
            return z.laufstand()
        await entwurf.verwerfen()
        nr = await lauf.anlegen(self.art)
        await lauf.setzen(nr, stapel_gesamt=1)
        await db.commit()                                  # die Aufgabe liest den Lauf über die gemeinsame Verbindung
        await self._starten(nr)
        return (await lauf.lesen(nr)).laufstand()

    async def ersetzen(self) -> None:
        """Ein anderer Weg zum Entwurf: ein laufender Lauf endet, sein Ergebnis wird nicht mehr gemerkt; ein fertiger hat
        zum neuen Entwurf nichts mehr zu sagen."""
        z = await lauf.juengster(self.art)
        if z is None or z.grund == ERSETZT:
            return
        if await lauf.wechseln(z.id, "fertig", ERSETZT, aus=("laeuft", "pause", "fertig", "fehler")) and z.stand == "laeuft":
            self._halten()

    async def zum_entwurf(self, hat_entwurf: bool) -> Laufstand | None:
        """Der Lauf, solange er zum Entwurf etwas zu sagen hat: er läuft, ist pausiert oder scheiterte, oder sein Entwurf
        steht noch da (dann mit dem Grund, etwa ohne KI). Ersetzte und angenommene zählen nicht mehr."""
        z = await lauf.juengster(self.art)
        if z is None or (z.stand == "fertig" and (not hat_entwurf or z.grund == ERSETZT)):
            return None
        return z.laufstand()

    async def arbeiten(self, nr: int) -> None:
        standard = datei.standard()
        await lauf.setzen(nr, schritt="Regeln zählen")
        buecher = await merkmale.laden()
        treffer = await asyncio.to_thread(treffer_zaehlen, standard, buecher)
        getroffen = set().union(*treffer.values()) if treffer else set()
        await lauf.setzen(nr, regeln=len(getroffen), ohne_vorschlag=len(buecher) - len(getroffen))
        self.weiter_oder_halt()
        neue, grund = await self._neue(nr, standard, buecher)
        treffer |= await asyncio.to_thread(treffer_der_neuen, standard, neue, buecher)
        e = entwurf.aus_bestand(standard, treffer, (await einstellungen.lesen()).teilen_ab, neue)
        async with db.einheit():
            if await lauf.wechseln(nr, "fertig", grund, aus=("laeuft",)):
                await lauf.setzen(nr, stapel=1, ki=len(neue), schritt="")
                await entwurf.speichern(e)

    async def _neue(self, nr: int, standard: Katalog, buecher: list[Buchmerkmale]) -> tuple[list[tuple[str, Katalogkategorie]], str]:
        """Neue Kategorien aus häufigen Schlagworten ohne Kategorie, und warum es keine gibt."""
        if not self.ki.bereit:
            return [], OHNE_KI
        haeufige = await asyncio.to_thread(haeufige_ohne_kategorie, standard, buecher, settings.katalog_neu_ab)
        if not haeufige:
            return [], ""
        await lauf.setzen(nr, schritt="KI schlägt neue Kategorien vor")
        zeichen = datei.zeichen_im_standard()
        bereiche = [(b.schluessel, b.name, [k.name for k in b.kategorien]) for b in standard.bereiche]
        vergeben = {b.schluessel: {kat.name.casefold() for k in b.kategorien for kat in (k, *k.teile)} for b in standard.bereiche}
        try:
            roh = await self.frage(SYSTEM_NEU, anfrage_neu(bereiche, haeufige, zeichen), "katalog_neue_kategorien",
                                   schema_neu([b.schluessel for b in standard.bereiche], zeichen), titel="Neue Kategorien aus dem Bestand",
                                   max_tokens=1500)
            neue = neue_aus(roh, {b.schluessel for b in standard.bereiche}, set(zeichen), [w for w, _ in haeufige], vergeben)
        except KiFehler as f:
            return [], f"Keine neuen Kategorien: {f.grund}"
        return neue_kategorien(standard, neue), ""


bestandslauf = Bestandslauf(ki)
