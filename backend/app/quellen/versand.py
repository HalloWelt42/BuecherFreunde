"""Eine Anfrage wirklich hinausschicken. Wer fragt, sagt ehrlich, wer er ist; einen Kontakt nennt die App nur, wenn der
Betreiber einen eingetragen hat (QUELLEN_KONTAKT). Eine große Datei geht auf Wunsch gleich in eine Datei statt in den Speicher
(`Dateiziel`), Stück für Stück mit Fortschritt und nach einem Abbruch ab dem Stand fortgesetzt (Range)."""

from __future__ import annotations

import asyncio
import http.cookiejar
import re
import threading
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import requests

from backend.app.core.config import settings
from backend.app.quellen.fehler import Ausgefallen

VERBINDEN_S = 5.0
STUECK = 65536
NICHT_RECHTZEITIG = "antwortet nicht rechtzeitig"
NICHT_ERREICHBAR = "nicht erreichbar"
ZU_GROSS = "die Antwort ist zu groß"
_GESAMT = re.compile(r"/(\d+)\s*$")
_sitzungen = threading.local()


def _nichts(*_: object) -> None:
    return None


@dataclass(frozen=True)
class Dateiziel:
    """Der Inhalt geht in `pfad` statt in den Speicher. Mit `versatz` wird ab dort fortgesetzt (Range); antwortet die Gegenstelle
    mit der ganzen Datei (200), beginnt sie von vorn. `beginn` erfährt Status und Kopf, sobald die Antwort beginnt, `stand` nach
    jedem Stück, wie viel Byte da sind und wie viele es insgesamt werden (None, wenn unbekannt)."""

    pfad: Path
    versatz: int = 0
    beginn: Callable[[int, dict[str, str]], None] = _nichts
    stand: Callable[[int, int | None], None] = _nichts


@dataclass(frozen=True)
class Anfrage:
    adresse: str
    methode: Literal["GET", "HEAD"] = "GET"
    felder: tuple[tuple[str, str], ...] = ()
    kopf: dict[str, str] = field(default_factory=dict)
    zeit_s: float = 15.0
    hoechstens: int = 8_000_000
    ziel: Dateiziel | None = None


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


def gesamt_aus(kopf: dict[str, str], beginn: int) -> int | None:
    """Wie groß die ganze Datei ist: aus Content-Range ("bytes 100-199/300"), sonst Content-Length und dem Beginn."""
    if m := _GESAMT.search(kopf.get("content-range", "")):
        return int(m.group(1))
    laenge = kopf.get("content-length", "")
    return beginn + int(laenge) if laenge.isdigit() else None


def in_datei(ziel: Dateiziel, status: int, kopf: dict[str, str], stuecke: Iterable[bytes], hoechstens: int) -> Rohantwort:
    """Den Inhalt in die Zieldatei, ab dem Versatz, wenn die Gegenstelle fortsetzt (206), sonst von vorn. Bricht die Verbindung
    ab, bleibt, was schon da ist, für das Fortsetzen liegen. Auch die Attrappe der Tests schreibt hierüber."""
    beginn = ziel.versatz if status == 206 else 0
    gesamt = gesamt_aus(kopf, beginn)
    ziel.beginn(status, kopf)
    ziel.pfad.parent.mkdir(parents=True, exist_ok=True)
    with ziel.pfad.open("r+b" if beginn and ziel.pfad.exists() else "wb") as datei:
        datei.seek(beginn)
        datei.truncate()
        da = beginn
        ziel.stand(da, gesamt)
        for stueck in stuecke:
            da += len(stueck)
            if da > hoechstens:
                raise Ausgefallen(ZU_GROSS)
            datei.write(stueck)
            ziel.stand(da, gesamt)
    return Rohantwort(status, kopf, b"")


def _abschicken(a: Anfrage) -> Rohantwort:
    kopf = {"User-Agent": ausweis(), "Accept": "application/json", **a.kopf}
    if a.ziel is not None:
        kopf["Accept-Encoding"] = "identity"                       # die Byte der Datei selbst, damit ein Versatz stimmt
        if a.ziel.versatz:
            kopf["Range"] = f"bytes={a.ziel.versatz}-"
    try:
        with _sitzung().request(a.methode, a.adresse, params=list(a.felder), headers=kopf, timeout=(VERBINDEN_S, a.zeit_s),
                                allow_redirects=a.methode == "GET", stream=True) as r:
            antwortkopf = {k.lower(): v for k, v in r.headers.items()}
            if a.ziel is not None and r.status_code in (200, 206):
                return in_datei(a.ziel, r.status_code, antwortkopf, r.iter_content(STUECK), a.hoechstens)
            inhalt = bytearray()
            for stueck in r.iter_content(STUECK):
                inhalt += stueck
                if len(inhalt) > a.hoechstens:
                    raise Ausgefallen(ZU_GROSS)
            return Rohantwort(r.status_code, antwortkopf, bytes(inhalt))
    except requests.Timeout as f:
        raise Ausgefallen(NICHT_RECHTZEITIG) from f
    except requests.RequestException as f:
        raise Ausgefallen(NICHT_ERREICHBAR) from f


async def ueber_netz(a: Anfrage) -> Rohantwort:
    return await asyncio.to_thread(_abschicken, a)
