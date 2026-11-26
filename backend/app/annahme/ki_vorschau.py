"""Die KI ergänzt die Vorschau (BF-80) im Hintergrund: Art und Kategorie, wo die Regeln nichts vorschlagen
(annahme/zuordnen.py), über die Leitstelle mit Vorrang Hintergrund und gebündelt wie beim Einordnen: bis zu
`EINORDNEN_JE_ANFRAGE` Dateien je Anfrage für die Art (services/einordnung.py, dieselbe Anweisung, dieselbe Antwortform), für die
Kategorie je Art eine Anfrage mit den Kategorien dieser Art (katalog/ki_fragen.py), zwischen zwei Anfragen
`EINORDNEN_ABSTAND_S`.

Die KI setzt nur Felder ohne Vorschlag oder mit einem früheren der KI; was der Nutzer gesetzt hat, auch während einer
Anfrage, und was Regeln, Ordner, Datei, Lücke oder Bestand vorschlagen, bleibt. Übernehmen geht jederzeit, auch bevor die KI
fertig ist. Der Stand steht je Aufnahme in `ki_stand` (offen, fertig): nach einem Neustart geht es mit dem Offenen weiter."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from pathlib import Path

from backend.app.annahme.modelle import BUCH, Gelesen, Wert, Zuordnung
from backend.app.annahme.vorschau import gelesen_aus, zuordnung_aus
from backend.app.annahme.zuordnen import kategorie_nach_regeln, typ_als_art
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.katalog import kategorien
from backend.app.katalog.ki_fragen import SYSTEM_EINORDNEN, anfrage_einordnen, einordnung_aus, schema_einordnen
from backend.app.katalog.merkmale import BESCHREIBUNG_ZEICHEN, Buchmerkmale
from backend.app.services import einordnung
from backend.app.services.anhalten import Anhalter
from backend.app.services.artregeln import Werk
from backend.app.services.einordnung import Vorschlag
from backend.app.services.ki import Ki, KiFehler, ki

logger = logging.getLogger("buecherfreunde.annahme.ki")
OFFEN = "stand = 'bestaetigen' AND ki_stand = 'offen'"
VON_DER_KI = (None, "ki")                       # nur solche Felder setzt die KI
TOKEN_JE_BUCH = 120


class Angehalten(Exception):
    pass


def _werk(z: dict, g: Gelesen) -> Werk:
    return Werk(id=z["id"], hash=z["sha256"], title=g.titel, author=g.autor, publisher=g.verlag, year=g.jahr, isbn=g.isbn,
                file_format=Path(z["name"]).suffix.lower().lstrip("."), file_name=z["name"], page_count=g.seiten,
                umschlag_schlicht=None if g.umschlag_schlicht is None else int(g.umschlag_schlicht))


def _merkmale(z: dict, g: Gelesen, typ: str) -> Buchmerkmale:
    return Buchmerkmale(id=z["id"], titel=g.titel, autor=g.autor, verlag=g.verlag, typ=typ, beschreibung=g.beschreibung[:BESCHREIBUNG_ZEICHEN])


class KiVorschau:
    def __init__(self, ki_: Ki) -> None:
        self.ki = ki_
        self._anhalter = Anhalter()
        self._wecker = asyncio.Event()
        self._aufgabe: asyncio.Task | None = None
        self.laeuft = False
        self.grund = ""

    def starten(self) -> None:
        self._wecker = asyncio.Event()
        self._wecker.set()                                 # was vor einem Neustart offen blieb, geht gleich weiter
        self._aufgabe = asyncio.create_task(self._arbeiten())

    async def stoppen(self) -> None:
        self._anhalter.halte()
        if self._aufgabe is not None:
            self._aufgabe.cancel()
            self._aufgabe = None

    def anstossen(self) -> None:
        self._wecker.set()

    async def _arbeiten(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._wecker.wait(), settings.einordnen_takt_s)
            except TimeoutError:
                pass
            self._wecker.clear()
            try:
                await self.runde()
            except asyncio.CancelledError:
                raise
            except Exception:                              # noqa: BLE001 - die Vorschau darf nie still stehen bleiben
                logger.exception("KI der Vorschau")

    async def runde(self) -> int:
        """Alles Offene in Teilen; liefert, wie viele Aufnahmen die KI gesehen hat."""
        if not self.ki.bereit:
            return 0
        self._anhalter.beginne()
        self.laeuft, gesehen, gefragt = True, 0, False
        try:
            while zeilen := await db.fetch_all(f"SELECT * FROM aufnahme WHERE {OFFEN} ORDER BY id LIMIT ?", (settings.einordnen_je_anfrage,)):
                if gefragt:
                    await self._pause()
                gefragt = True
                await self._teil(zeilen)
                gesehen += len(zeilen)
        except Angehalten:
            pass
        except KiFehler as f:
            self.grund = f.grund
            logger.info("KI der Vorschau unterbrochen: %s", f.grund)
        finally:
            self.laeuft = False
        return gesehen

    async def _teil(self, zeilen: list[dict]) -> None:
        arten = await self._arten([(z, gelesen_aus(z), zuordnung_aus(z)) for z in zeilen])
        kats = await self._kategorien(zeilen, arten)
        async with db.einheit():
            for z in zeilen:
                await self._merken(z["id"], arten.get(z["id"]), kats.get(z["id"]))

    async def _arten(self, teil: list[tuple[dict, Gelesen | None, Zuordnung | None]]) -> dict[int, Vorschlag]:
        offen = [(z, g) for z, g, zo in teil if g and zo and zo.art.herkunft in VON_DER_KI]
        if not offen:
            return {}
        werke = [_werk(z, g) for z, g in offen]
        texte = await asyncio.to_thread(lambda: [einordnung.textanfang(w.hash) for w in werke])
        try:
            roh = await self.ki.json_antwort(einordnung.SYSTEM, einordnung.anfrage(werke, texte), "vorschau_art", einordnung.schema(len(werke)),
                                             titel=f"Vorschau, Art: {len(werke)} {'Datei' if len(werke) == 1 else 'Dateien'} ab {werke[0].file_name[:60]}",
                                             prioritaet="hintergrund", geduld=True, pruefen=self._pruefen, temperature=0.1,
                                             max_tokens=einordnung.TOKEN_JE_WERK * len(werke) + 200)
            return einordnung.vorschlaege_aus(roh, werke)
        except KiFehler as f:
            if f.art != "einzeln":
                raise
            logger.info("KI der Vorschau, Art: %s", f.grund)
            return {}

    async def _kategorien(self, zeilen: list[dict], arten: dict[int, Vorschlag]) -> dict[int, Wert[list[int]]]:
        """Je Art eine Anfrage für die Dateien ohne Kategorie; vorher die Regeln für eine Art, die erst die KI wusste."""
        aus: dict[int, Wert[list[int]]] = {}
        je_typ: dict[str, list[tuple[dict, Gelesen]]] = defaultdict(list)
        for z in zeilen:
            g, zo = gelesen_aus(z), zuordnung_aus(z)
            if not g or not zo or zo.kategorien.herkunft not in VON_DER_KI or zo.kategorien.wert:
                continue
            art = typ_als_art(arten[z["id"]].typ) if z["id"] in arten and zo.art.herkunft in VON_DER_KI else zo.art.wert
            if art in ("", "material"):
                continue
            typ = "" if art == BUCH else art
            if (regel := await kategorie_nach_regeln(g, typ)).wert:
                aus[z["id"]] = regel
            else:
                je_typ[typ].append((z, g))
        alle = await kategorien.zum_einordnen()
        for typ, teil in je_typ.items():
            kats = [k for k in alle if typ in k.arten]
            if not kats:
                continue
            await self._pause()
            buecher = [_merkmale(z, g, typ) for z, g in teil]
            schluessel = {k.schluessel: k.id for k in kats}
            try:
                roh = await self.ki.json_antwort(SYSTEM_EINORDNEN, anfrage_einordnen(kats, buecher), "vorschau_kategorie", schema_einordnen(list(schluessel)),
                                                 titel=f"Vorschau, Kategorie: {len(buecher)} {'Datei' if len(buecher) == 1 else 'Dateien'}",
                                                 prioritaet="hintergrund", geduld=True, pruefen=self._pruefen, temperature=0.1,
                                                 max_tokens=TOKEN_JE_BUCH * len(buecher) + 200)
                funde = einordnung_aus(roh, len(buecher), set(schluessel))
            except KiFehler as f:
                if f.art != "einzeln":
                    raise
                logger.info("KI der Vorschau, Kategorie: %s", f.grund)
                continue
            for nummer, liste in funde.items():
                if liste:
                    bester = max(liste, key=lambda k: k.sicherheit)
                    aus[teil[nummer - 1][0]["id"]] = Wert[list[int]](wert=[schluessel[bester.schluessel]], herkunft="ki", grund=bester.satz)
        return aus

    @staticmethod
    async def _merken(nr: int, art: Vorschlag | None, kats: Wert[list[int]] | None) -> None:
        """Frisch gelesen: was der Nutzer inzwischen gesetzt hat, bleibt; die Aufnahme muss noch warten."""
        z = await db.fetch_one("SELECT stand, zuordnung FROM aufnahme WHERE id = ?", (nr,))
        if z is None or z["stand"] != "bestaetigen" or not z["zuordnung"]:
            return
        zo = Zuordnung.model_validate_json(z["zuordnung"])
        if art is not None and zo.art.herkunft in VON_DER_KI:
            zo.art = Wert[str](wert=typ_als_art(art.typ), herkunft="ki")
            zo.gattung = art.gattung
        if kats is not None and zo.kategorien.herkunft in VON_DER_KI:
            zo.kategorien = kats
        await db.execute("UPDATE aufnahme SET zuordnung = ?, ki_stand = 'fertig', geaendert_am = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                         (zo.model_dump_json(), nr))

    async def _pause(self) -> None:
        await self._anhalter.bis(asyncio.sleep(settings.einordnen_abstand_s))
        if self._anhalter.gehalten:
            raise Angehalten

    async def _pruefen(self) -> None:
        if self._anhalter.gehalten:
            raise Angehalten


ki_vorschau = KiVorschau(ki)
