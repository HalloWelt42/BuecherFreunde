"""Vorlesen mit einem Sprechdienst: Stimmen zur Wahl und der Text als Ton, Satz für Satz. Spricht die Vertonung (`VORLESEN_URL`);
ohne sie fehlt nur diese Fähigkeit, vorgelesen wird dann mit den Stimmen des Geräts (Oberfläche)."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncIterator

import httpx

from backend.app.ablage.wolke import _pruefung, app_kopf
from backend.app.core.config import settings

logger = logging.getLogger("buecherfreunde.vorlesen")
TEIL = 7_500                     # so viel Text nimmt die Vertonung je Aufruf (höchstens 8000 Zeichen)
KATALOG = "katalog:"
GRUPPEN = (("privat", "eigene"), ("fremd", "weitere"), ("katalog", "eingebaut"))
_client: httpx.AsyncClient | None = None


class VorlesenFehler(Exception):
    def __init__(self, meldung: str, status: int = 503) -> None:
        super().__init__(meldung)
        self.meldung, self.status = meldung, status


def _verbindung() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=settings.vorlesen_url.rstrip("/"), verify=_pruefung(), timeout=httpx.Timeout(120.0, connect=4.0),
                                    headers=app_kopf())
    return _client


async def schliessen() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _meldung(status: int, inhalt: bytes) -> str:
    try:
        grund = json.loads(inhalt).get("detail")
    except (ValueError, AttributeError):
        grund = None
    return grund if isinstance(grund, str) else f"Der Sprechdienst meldet {status}"


async def stimmen() -> dict:
    """`{da, stimmen: [{id, name, gruppe}], hinweis}`; eigene Stimmen nur, wenn der Sprechdienst sie dieser App freigibt."""
    if not settings.vorlesen_url:
        return {"da": False, "stimmen": [], "hinweis": ""}
    alle, hinweis = [], ""
    try:
        for bereich, gruppe in GRUPPEN:
            r = await _verbindung().get("/api/v1/stimmen", params={"bereich": bereich}, timeout=10)
            if r.status_code in (401, 403):
                hinweis = "Eigene Stimmen gibt der Sprechdienst dieser App noch nicht frei" if bereich == "privat" else hinweis
                continue
            r.raise_for_status()
            alle += [{"id": str(s["id"]), "name": str(s["name"]), "gruppe": gruppe} for s in r.json()]
    except (httpx.HTTPError, ValueError, KeyError) as f:
        logger.info("Stimmen nicht geholt: %s", f)
        return {"da": False, "stimmen": [], "hinweis": "Der Sprechdienst antwortet nicht"}
    return {"da": True, "stimmen": alle, "hinweis": hinweis}


def teile(text: str, hoechstens: int = TEIL) -> list[str]:
    """Der Text in Teilen bis `hoechstens` Zeichen, an Absätzen und Satzenden, notfalls an Wortgrenzen."""
    aus: list[str] = []
    for stueck in re.split(r"(?<=[.!?:;])\s+|\n{2,}", text):
        while len(stueck) > hoechstens:
            schnitt = stueck.rfind(" ", 0, hoechstens)
            schnitt = schnitt if schnitt > 0 else hoechstens
            aus.append(stueck[:schnitt])
            stueck = stueck[schnitt:].lstrip()
        if not stueck.strip():
            continue
        if aus and len(aus[-1]) + len(stueck) + 1 <= hoechstens:
            aus[-1] += " " + stueck
        else:
            aus.append(stueck)
    return [a.strip() for a in aus]


def _wahl(stimme: str) -> dict | None:
    if not stimme:
        return None
    return {"art": "katalog", "name": stimme.removeprefix(KATALOG)} if stimme.startswith(KATALOG) else {"art": "klon", "knoten_id": stimme}


async def strom(text: str, stimme: str, sitzung: str) -> AsyncIterator[bytes]:
    """Zeilen `{art: satz, nr, text, ton}` (Ton als Base64-WAV), am Ende `{art: ende}`. Was vor dem ersten Satz scheitert, ist
    ein `VorlesenFehler`; danach kommt eine Zeile `fehler`. Hört der Browser auf zu lesen, wird nichts mehr gesprochen."""
    if not settings.vorlesen_url:
        raise VorlesenFehler("Es ist kein Sprechdienst angeschlossen")
    koerper = {"ausschreiben": True} | ({"stimme": w} if (w := _wahl(stimme)) else {})
    kopf = {"X-Kellerwolke-Sitzung": sitzung} if sitzung else {}
    nr = 0
    try:
        for teil in teile(text):
            async with _verbindung().stream("POST", "/api/v1/sprechen/strom", json={**koerper, "text": teil}, headers=kopf) as r:
                if r.status_code >= 400:
                    raise VorlesenFehler(_meldung(r.status_code, await r.aread()), 502 if r.status_code >= 500 else 400)
                async for roh in r.aiter_lines():
                    z = json.loads(roh) if roh.strip() else {}
                    if z.get("art") == "satz":
                        yield json.dumps({"art": "satz", "nr": nr, "text": z.get("text", ""), "ton": z.get("ton", "")}, ensure_ascii=False).encode() + b"\n"
                        nr += 1
                    elif z.get("art") == "fehler":
                        raise VorlesenFehler(str(z.get("meldung") or "Vorlesen brach ab"), 502)
        yield b'{"art": "ende"}\n'
    except (VorlesenFehler, httpx.HTTPError) as f:
        meldung = f.meldung if isinstance(f, VorlesenFehler) else "Der Sprechdienst antwortet nicht"
        if not nr:
            raise VorlesenFehler(meldung, getattr(f, "status", 503)) from f
        yield json.dumps({"art": "fehler", "meldung": meldung}, ensure_ascii=False).encode() + b"\n"
