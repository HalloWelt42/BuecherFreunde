"""Vorlesen über den Sprechdienst der Leitstelle (BF-14): derselbe Leitstellen-Anschluss wie die KI (services/ki.py), der
Dienst `SPRECHDIENST` (Vorgabe klangwerk-sprechen, Fähigkeit `stimme`), seine Stimmen aus dem Katalog (`GET /tts/voices`).

Der Text wird an Satzgrenzen geteilt, jeder Satz einzeln gesprochen (`POST /v1/audio/speech`, WAV) und als Zeile eines
Stroms geliefert, sobald er da ist; so beginnt die Wiedergabe nach dem ersten Satz. Der nächste Satz ist schon bestellt,
während der vorige klingt. Alle Sätze einer Vorlesung sind bei der Leitstelle eine Arbeit (das Modell bleibt dafür
stehen). Hört der Browser auf zu lesen, wird nichts mehr bestellt. Ohne Leitstelle fehlt nur diese Fähigkeit; vorgelesen
wird dann mit den Stimmen des Geräts (Oberfläche)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator

from appkern.leitstelle import KeinModell, LeitstellenFehler, NichtErlaubt, NichtGefunden, SchluesselUngueltig
from appkern.leitstelle.arbeit import LAUFENDE_ARBEIT

from backend.app.core.config import settings
from backend.app.services.ki import ki

logger = logging.getLogger("buecherfreunde.vorlesen")
KATALOG = "katalog:"                     # so beginnt die Kennung einer Stimme aus dem Katalog des Sprechdienstes
GRUPPE = "eingebaut"
KATALOG_GILT_S = 600
VORAUS = 2                               # so viele Sätze sind zugleich bestellt (die Leitstelle erlaubt der App zwei Aufträge)
SATZ_HOECHSTENS = 400                    # Zeichen; längere Sätze werden an Kommas, notfalls an Wörtern geteilt
SATZENDE = re.compile(r"(?<=[.!?:;…])\s+|\n\s*")
WORT = re.compile(r"\w")

_katalog: tuple[float, str, list[str]] | None = None


class VorlesenFehler(Exception):
    """Vorlesen geht gerade nicht, bevor etwas gesprochen ist; `status` für die Antwort (nie 401, sonst meldete die
    Oberfläche die Person ab)."""

    def __init__(self, meldung: str, status: int = 503) -> None:
        super().__init__(meldung)
        self.meldung, self.status = meldung, status


def bereit() -> bool:
    return ki.bereit and bool(settings.sprechdienst.strip())


def _grund(f: LeitstellenFehler) -> VorlesenFehler:
    dienst = settings.sprechdienst
    if isinstance(f, (NichtErlaubt, SchluesselUngueltig)):
        return VorlesenFehler(f"Die Leitstelle gibt BücherFreunde den Sprechdienst {dienst} nicht frei: {f.meldung}", 403)
    if isinstance(f, (KeinModell, NichtGefunden)):
        return VorlesenFehler(f"Die Leitstelle kennt den Sprechdienst {dienst} nicht (SPRECHDIENST)", 503)
    return VorlesenFehler(f"Vorlesen gerade nicht möglich: {f.meldung}", 503)


def saetze(text: str, hoechstens: int = SATZ_HOECHSTENS) -> list[str]:
    """Die Sätze des Texts, wie sie darin stehen; überlange an Kommas, notfalls an Wortgrenzen geteilt. Stücke ohne ein
    Wort (Aufzählungszeichen, Striche) fallen weg."""
    aus: list[str] = []
    for satz in (s.strip() for s in SATZENDE.split(text)):
        while len(satz) > hoechstens:
            schnitt = satz.rfind(", ", 0, hoechstens) + 1 or satz.rfind(" ", 0, hoechstens)
            schnitt = schnitt if schnitt > 0 else hoechstens
            aus.append(satz[:schnitt].strip())
            satz = satz[schnitt:].strip()
        aus.append(satz)
    return [s for s in aus if WORT.search(s)]


async def katalog() -> list[str]:
    """Die Stimmen des Sprechdienstes, eine Weile gemerkt."""
    global _katalog
    dienst = settings.sprechdienst
    if _katalog and _katalog[1] == dienst and time.monotonic() - _katalog[0] < KATALOG_GILT_S:
        return _katalog[2]
    antwort = await ki.leitstelle().dienst(dienst).json("GET", "/tts/voices", titel="Stimmen des Katalogs")
    stimmen = sorted(str(s) for s in (antwort.get("speakers") or []))
    _katalog = (time.monotonic(), dienst, stimmen)
    return stimmen


async def stimmen() -> dict:
    """`{da, stimmen: [{id, name, gruppe}], hinweis}`: die Stimmen aus dem Katalog des Sprechdienstes."""
    if not bereit():
        return {"da": False, "stimmen": [], "hinweis": ""}
    try:
        namen = await katalog()
    except LeitstellenFehler as f:
        logger.info("Stimmen nicht geholt: %s", f)
        return {"da": False, "stimmen": [], "hinweis": _grund(f).meldung}
    return {"da": True, "stimmen": [{"id": KATALOG + n, "name": n, "gruppe": GRUPPE} for n in namen], "hinweis": ""}


def _zeile(daten: dict) -> bytes:
    return json.dumps(daten, ensure_ascii=False).encode() + b"\n"


async def _sprechen(satz: str, stimme: str, arbeit: str, titel: str = "Vorlesen", prioritaet: str = "hoch") -> bytes:
    marke = LAUFENDE_ARBEIT.set(arbeit)
    try:
        antwort = await ki.leitstelle().dienst(settings.sprechdienst).anfrage(
            "POST", "/v1/audio/speech", titel=titel, prioritaet=prioritaet,
            json={"input": satz, "response_format": "wav", **({"voice": stimme} if stimme else {})})
    finally:
        LAUFENDE_ARBEIT.reset(marke)
    return antwort.content


def _pruefen(stimme: str) -> str:
    """Der Name der Stimme beim Sprechdienst; wirft, wenn es keinen Sprechdienst oder diese Stimme nicht gibt."""
    if not bereit():
        raise VorlesenFehler("Es ist kein Sprechdienst angeschlossen (Leitstelle)")
    if stimme and not stimme.startswith(KATALOG):
        raise VorlesenFehler("Diese Stimme gibt es über die Leitstelle nicht; bitte eine aus der Liste wählen", 400)
    return stimme.removeprefix(KATALOG)


async def satz(text: str, stimme: str, prioritaet: str = "hoch") -> bytes:
    """Ein kurzer Text als ein WAV, wie ein Satz im Strom (feste Ansagen, familie/ansagelauf.py; im Hintergrund mit
    `prioritaet` "hintergrund")."""
    name = _pruefen(stimme)
    try:
        return await _sprechen(text, name, f"bf-ansage-{uuid.uuid4().hex[:12]}", titel="Ansagen", prioritaet=prioritaet)
    except LeitstellenFehler as f:
        raise _grund(f) from f


async def strom(text: str, stimme: str) -> AsyncIterator[bytes]:
    """Zeilen `{art: satz, nr, text, ton}` (Ton als Base64-WAV), am Ende `{art: ende}`. Was vor dem ersten Satz scheitert,
    ist ein `VorlesenFehler`; danach kommt eine Zeile `fehler`. `stimme`: leer für die Vorgabe des Dienstes, sonst eine
    Stimme aus dem Katalog."""
    name = _pruefen(stimme)
    teile = saetze(text)
    arbeit = f"bf-vorlesen-{uuid.uuid4().hex[:12]}"
    bestellt: dict[int, asyncio.Task[bytes]] = {}

    def bestellen(i: int) -> None:
        if i < len(teile) and i not in bestellt:
            aufgabe = asyncio.create_task(_sprechen(teile[i], name, arbeit))
            aufgabe.add_done_callback(lambda a: a.cancelled() or a.exception())    # abgeholt, auch zurückgenommen
            bestellt[i] = aufgabe

    nr = 0
    try:
        for i in range(VORAUS):
            bestellen(i)
        for i, satz in enumerate(teile):
            try:
                wav = await bestellt.pop(i)
            except LeitstellenFehler as f:
                if not nr:
                    raise _grund(f) from f
                yield _zeile({"art": "fehler", "meldung": _grund(f).meldung})
                return
            bestellen(i + VORAUS)
            yield _zeile({"art": "satz", "nr": nr, "text": satz, "ton": base64.b64encode(wav).decode("ascii")})
            nr += 1
    finally:
        for aufgabe in bestellt.values():
            aufgabe.cancel()
    yield _zeile({"art": "ende"})
