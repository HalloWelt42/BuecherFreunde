"""Der eine Abruf für alle Quellen. Reihenfolge: Vorrat, laufende gleiche Anfrage, Pause und Tagesgrenze, Takt des Rechners,
Anfrage, Auswertung (Erfolg, Rückzug, Sicherung), Vorrat. Die Anschlüsse je Quelle fragen nur hierüber."""

from __future__ import annotations

import asyncio
import email.utils
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, NoReturn
from urllib.parse import urlencode, urlsplit

from backend.app.quellen import versand, vorrang
from backend.app.quellen.fehler import Abgeschaltet, AnfrageFalsch, Ausgefallen, BitteWarten, Pausiert, QuelleFehler, Unlesbar
from backend.app.quellen.regeln import TAG_S, Regel
from backend.app.quellen.takt import Karte, Takt
from backend.app.quellen.versand import Anfrage, Rohantwort, Versand
from backend.app.quellen.vorrang import Vorrang
from backend.app.quellen.vorrat import Eintrag, Vorrat
from backend.app.quellen.zustand import ABGEWIESEN_S, Zustaende

logger = logging.getLogger("buecherfreunde.quellen")
AUFRAEUMEN_NACH = 200           # so viele neue Antworten, dann wird der Vorrat durchgesehen
ZU_VIEL, UEBERLAST, ABGEWIESEN = 429, 503, 403


@dataclass(frozen=True)
class Frage:
    """Was gefragt wird und wie die Antwort zu lesen ist."""

    adresse: str
    felder: tuple[tuple[str, str], ...] = ()
    beiwerk: tuple[tuple[str, str], ...] = ()          # geht mit, gehört aber nicht zum Schlüssel im Vorrat
    kopf: tuple[tuple[str, str], ...] = ()             # dito, etwa ein eigener Schlüssel
    methode: str = "GET"
    leer_bei: frozenset[int] = frozenset({404})        # Status, der "nichts gefunden" heißt
    lies: Callable[[bytes], Any] | None = None         # Rohdaten -> Wert (Vorgabe: JSON); wirft ValueError bei Unlesbarem
    pruefe: Callable[[Any], None] | None = None        # wirft BitteWarten oder Unlesbar
    ist_leer: Callable[[Any], bool] | None = None
    verdichte: Callable[[Any], Any] | None = None      # nur das Nötige behalten, als JSON-Wert
    abweisung: Callable[[Rohantwort], BitteWarten | None] | None = None   # 429/403 genauer deuten

    @property
    def schluessel(self) -> str:
        felder = urlencode(sorted(self.felder))
        return f"{'' if self.methode == 'GET' else self.methode + ' '}{self.adresse}{'?' + felder if felder else ''}"


@dataclass
class _Laufend:
    aufgabe: asyncio.Task
    takt: Takt
    karte: Karte


def wartezeit(kopf: dict[str, str], jetzt: float) -> float | None:
    """Retry-After: Sekunden (auch mit Komma) oder ein Zeitpunkt."""
    wert = kopf.get("retry-after", "").strip()
    if not wert:
        return None
    try:
        return max(0.0, float(wert))
    except ValueError:
        pass
    try:
        return max(0.0, email.utils.parsedate_to_datetime(wert).timestamp() - jetzt)
    except (TypeError, ValueError):
        return None


def als_json(inhalt: bytes) -> Any:
    return json.loads(inhalt)


def takt_nach(regel: Regel) -> Takt:
    return Takt(lambda: regel.abstand, lambda: regel.minute)


class Abruf:
    def __init__(self, senden: Versand = versand.ueber_netz, uhr: Callable[[], float] = time.time, takt: Callable[[Regel], Takt] = takt_nach) -> None:
        self._senden, self._uhr, self._takt_nach = senden, uhr, takt
        self.vorrat, self.zustaende = Vorrat(uhr), Zustaende(uhr)
        self._takte: dict[str, Takt] = {}
        self._laufend: dict[str, _Laufend] = {}
        self._neue = 0

    # -- Außen ---------------------------------------------------------------------------------------------------------
    async def hole(self, regel: Regel, frage: Frage, *, probe: bool = False) -> Any:
        """Der Wert der Antwort oder None, wenn es nichts gibt. Wirft QuelleFehler, wenn die Quelle nicht antwortet."""
        if regel.hindernis:
            raise Abgeschaltet(f"{regel.name} {regel.hindernis}")
        if not probe and (da := await self.vorrat.lies(frage.schluessel)) is not None:
            return self._aus_vorrat(regel, da)
        return await self._gemeinsam(regel, frage, probe)

    async def lade(self, regel: Regel, adresse: str, hoechstens: int, zeit_s: float | None = None) -> bytes:
        """Eine Datei (Bild, Buch), ohne Vorrat, aber mit Takt, Pausen und Zählung."""
        if regel.hindernis:
            raise Abgeschaltet(f"{regel.name} {regel.hindernis}")
        self._erlaubt(regel, adresse)
        anfrage = Anfrage(adresse, kopf={"Accept": "*/*"}, zeit_s=zeit_s or regel.zeit_s, hoechstens=hoechstens)
        takt, dran = self._takt(regel, adresse), vorrang.jetzt()
        antwort = await self._durch_den_takt(regel, anfrage, takt, takt.karte(dran), dran, False)
        if antwort.status == 404:
            raise AnfrageFalsch("die Datei gibt es dort nicht")
        await self._bewerte(regel, antwort, None)
        await self.zustaende.erfolg(regel)
        return antwort.inhalt

    async def merke(self, regel: Regel, frage: Frage, wert: Any) -> None:
        """Eine Antwort, die auf anderem Weg kam (Sammelanfrage), unter ihrer Einzelfrage ablegen."""
        leer = wert is None or bool(frage.ist_leer and frage.ist_leer(wert))
        if not leer and frage.verdichte:
            wert = frage.verdichte(wert)
        await self._ablegen(regel, frage, None if leer else wert)

    async def bekannt(self, frage: Frage) -> bool:
        return await self.vorrat.lies(frage.schluessel) is not None

    # -- Vorrat --------------------------------------------------------------------------------------------------------
    @staticmethod
    def _aus_vorrat(regel: Regel, e: Eintrag) -> Any:
        if e.art == "fehler":
            raise Ausgefallen(f"{regel.name}: {e.grund}")
        return None if e.art == "leer" else json.loads(e.inhalt)

    async def _ablegen(self, regel: Regel, frage: Frage, wert: Any) -> None:
        if wert is None:
            await self.vorrat.merke(frage.schluessel, regel.kennung, "leer", regel.leer_tage * TAG_S)
        else:
            await self.vorrat.merke(frage.schluessel, regel.kennung, "treffer", regel.treffer_tage * TAG_S, json.dumps(wert, ensure_ascii=False, separators=(",", ":")).encode())
        self._neue += 1
        if self._neue >= AUFRAEUMEN_NACH:
            self._neue = 0
            await self.vorrat.aufraeumen()

    # -- Gleiche Anfragen zusammenfassen -------------------------------------------------------------------------------
    async def _gemeinsam(self, regel: Regel, frage: Frage, probe: bool) -> Any:
        dran = vorrang.jetzt()
        laufend = self._laufend.get(frage.schluessel)
        if laufend is None:
            takt = self._takt(regel, frage.adresse)
            karte = takt.karte(dran)
            laufend = _Laufend(asyncio.create_task(self._wirklich(regel, frage, takt, karte, dran, probe)), takt, karte)
            self._laufend[frage.schluessel] = laufend
            laufend.aufgabe.add_done_callback(lambda a: self._fertig(frage.schluessel, a))
        else:
            await laufend.takt.vorziehen(laufend.karte, dran)
        return await asyncio.shield(laufend.aufgabe)

    def _fertig(self, schluessel: str, aufgabe: asyncio.Task) -> None:
        self._laufend.pop(schluessel, None)
        if not aufgabe.cancelled():
            aufgabe.exception()                             # wartet niemand mehr, gilt der Fehler als gesehen

    def _takt(self, regel: Regel, adresse: str) -> Takt:
        name = regel.kennung if regel.ein_takt else (urlsplit(adresse).hostname or regel.kennung)
        if name not in self._takte:
            self._takte[name] = self._takt_nach(regel)
        return self._takte[name]

    @staticmethod
    def _erlaubt(regel: Regel, adresse: str) -> None:
        teile = urlsplit(adresse)
        if teile.scheme != "https" or teile.hostname not in regel.rechner:
            raise AnfrageFalsch(f"{regel.name} liefert nichts von {teile.hostname or 'dort'}")

    # -- Anfrage und Auswertung ----------------------------------------------------------------------------------------
    async def _wirklich(self, regel: Regel, frage: Frage, takt: Takt, karte: Karte, dran: Vorrang, probe: bool) -> Any:
        self._erlaubt(regel, frage.adresse)
        anfrage = Anfrage(frage.adresse, frage.methode, frage.felder + frage.beiwerk, dict(frage.kopf), regel.zeit_s)
        try:
            wert = await self._frage_und_lies(regel, frage, anfrage, takt, karte, dran, probe)
        except Ausgefallen as f:
            await self.vorrat.merke(frage.schluessel, regel.kennung, "fehler", regel.fehler_s, grund=f.grund)
            raise Ausgefallen(f"{regel.name}: {f.grund}") from f
        await self.zustaende.erfolg(regel)
        await self._ablegen(regel, frage, wert)
        return wert

    async def _frage_und_lies(self, regel: Regel, frage: Frage, anfrage: Anfrage, takt: Takt, karte: Karte, dran: Vorrang, probe: bool) -> Any:
        antwort = await self._durch_den_takt(regel, anfrage, takt, karte, dran, probe)
        if antwort.status in frage.leer_bei:
            return None
        await self._bewerte(regel, antwort, frage.abweisung)
        if frage.methode == "HEAD":
            return True
        return await self._gelesen(regel, frage, antwort)

    async def _gelesen(self, regel: Regel, frage: Frage, antwort: Rohantwort) -> Any:
        try:
            wert = (frage.lies or als_json)(antwort.inhalt)
            if frage.pruefe:
                frage.pruefe(wert)
            if frage.ist_leer and frage.ist_leer(wert):
                return None
            return frage.verdichte(wert) if frage.verdichte else wert
        except BitteWarten as f:
            raise await self.zustaende.bitte_warten(regel, f.grund, max(f.sekunden, wartezeit(antwort.kopf, self._uhr()) or 0)) from f
        except (ValueError, LookupError, TypeError, AttributeError):
            return await self._ausgefallen(regel, "liefert Unlesbares", Unlesbar)

    async def _durch_den_takt(self, regel: Regel, anfrage: Anfrage, takt: Takt, karte: Karte, dran: Vorrang, probe: bool) -> Rohantwort:
        await self.zustaende.darf(regel, dran, probe)
        async with takt.an_der_reihe(karte):
            await self.zustaende.darf(regel, dran, probe)     # inzwischen kann eine Pause begonnen haben
            await self.zustaende.gefragt(regel, dran, probe)
            try:
                return await self._senden(anfrage)
            except Ausgefallen as f:
                await self._ausgefallen(regel, f.grund)

    async def _bewerte(self, regel: Regel, antwort: Rohantwort, deute: Callable[[Rohantwort], BitteWarten | None] | None) -> None:
        if antwort.status < 400:
            return
        vorgabe = wartezeit(antwort.kopf, self._uhr())
        if deute and (f := deute(antwort)) is not None:
            raise await self.zustaende.bitte_warten(regel, f.grund, max(f.sekunden, vorgabe or 0))
        if antwort.status == ZU_VIEL:
            raise await self.zustaende.bitte_warten(regel, "zu viele Anfragen", vorgabe)
        if antwort.status == UEBERLAST and vorgabe:
            raise await self.zustaende.bitte_warten(regel, "bittet um Ruhe", vorgabe)
        if antwort.status == ABGEWIESEN:
            raise await self.zustaende.bitte_warten(regel, "weist die Anfrage ab", vorgabe, ABGEWIESEN_S)
        if antwort.status >= 500:
            await self._ausgefallen(regel, f"antwortet mit Fehler {antwort.status}")
        raise AnfrageFalsch(f"{regel.name} versteht die Anfrage nicht ({antwort.status})")

    async def _ausgefallen(self, regel: Regel, grund: str, art: type[Ausgefallen] = Ausgefallen) -> NoReturn:
        logger.warning("%s: %s", regel.anbieter, grund)
        pause: Pausiert | None = await self.zustaende.ausfall(regel, grund)
        raise pause or art(grund)


_abruf = Abruf()


def abruf() -> Abruf:
    return _abruf


def einsetzen(neuer: Abruf) -> Abruf:
    """Einen anderen Abruf einsetzen (Tests); liefert den bisherigen."""
    global _abruf
    alter, _abruf = _abruf, neuer
    return alter


async def hole(regel: Regel, frage: Frage, *, probe: bool = False) -> Any:
    return await _abruf.hole(regel, frage, probe=probe)


async def oder_nichts(aufgabe: Any) -> Any:
    """Für Nebenwege: fällt die Quelle aus, fehlt nur dieser Teil."""
    try:
        return await aufgabe
    except QuelleFehler as f:
        logger.info("%s", f.grund)
        return None
