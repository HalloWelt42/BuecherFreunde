"""Eine Anfrage wirklich hinausschicken. Wer fragt, sagt ehrlich, wer er ist; einen Kontakt nennt die App nur, wenn der
Betreiber einen eingetragen hat (QUELLEN_KONTAKT)."""

from __future__ import annotations

import asyncio
import http.cookiejar
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

import requests

from backend.app.core.config import settings
from backend.app.quellen.fehler import Ausgefallen

VERBINDEN_S = 5.0
_sitzungen = threading.local()


@dataclass(frozen=True)
class Anfrage:
    adresse: str
    methode: Literal["GET", "HEAD"] = "GET"
    felder: tuple[tuple[str, str], ...] = ()
    kopf: dict[str, str] = field(default_factory=dict)
    zeit_s: float = 15.0
    hoechstens: int = 8_000_000


@dataclass(frozen=True)
class Rohantwort:
    status: int
    kopf: dict[str, str]                # Namen klein geschrieben
    inhalt: bytes


Versand = Callable[[Anfrage], Awaitable[Rohantwort]]


def ausweis() -> str:
    """Der User-Agent: Name, Fassung, wozu; nur Zeichen, die im Kopf einer Anfrage stehen dürfen."""
    kontakt = "".join(z for z in settings.quellen_kontakt if 32 <= ord(z) < 127 and z not in "()").strip()
    return f"BuecherFreunde/{settings.version} (self-hosted book library{f'; {kontakt}' if kontakt else ''})"


def _sitzung() -> requests.Session:
    if not hasattr(_sitzungen, "eine"):
        _sitzungen.eine = requests.Session()
        _sitzungen.eine.cookies.set_policy(http.cookiejar.DefaultCookiePolicy(allowed_domains=[]))     # keine Kekse behalten
    return _sitzungen.eine


def _abschicken(a: Anfrage) -> Rohantwort:
    kopf = {"User-Agent": ausweis(), "Accept": "application/json", **a.kopf}
    try:
        with _sitzung().request(a.methode, a.adresse, params=list(a.felder), headers=kopf, timeout=(VERBINDEN_S, a.zeit_s),
                                allow_redirects=a.methode == "GET", stream=True) as r:
            inhalt = bytearray()
            for stueck in r.iter_content(65536):
                inhalt += stueck
                if len(inhalt) > a.hoechstens:
                    raise Ausgefallen("die Antwort ist zu groß")
            return Rohantwort(r.status_code, {k.lower(): v for k, v in r.headers.items()}, bytes(inhalt))
    except requests.Timeout as f:
        raise Ausgefallen("antwortet nicht rechtzeitig") from f
    except requests.RequestException as f:
        raise Ausgefallen("nicht erreichbar") from f


async def ueber_netz(a: Anfrage) -> Rohantwort:
    return await asyncio.to_thread(_abschicken, a)
