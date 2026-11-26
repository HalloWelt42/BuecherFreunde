"""Wer die Wege der Einrichtung nutzen darf (BF-82): solange eine neue Installation noch kein Konto hat, jeder, der sie erreicht,
wie beim Anlegen des ersten Kontos (sonst ließe sich ohne Konto weder wiederherstellen noch umziehen); danach nur angemeldet und
mit der Fähigkeit `einstellungen`. Eine laufende Installation lässt so nie jemanden ohne Anmeldung hinein.

Wege, die eine Adresse ansprechen (Verbindung prüfen, Anschluss eintragen, Konto der Kellerwolke, Umzug verbinden), nehmen vor
dem ersten Konto nur `https` mit einem Namen an: keine IP-Adresse, kein localhost, kein Port unter 1024 außer 443; und höchstens
`EINRICHTUNG_PRUEFUNGEN_JE_MINUTE` solche Anfragen in der Minute. So lässt sich der Server ohne Konto nicht als Sprungbrett ins
Heimnetz benutzen."""

from __future__ import annotations

import ipaddress
import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from backend.app.core.auth import verify_token
from backend.app.core.config import settings
from backend.app.einrichtung import zustand
from backend.app.einrichtung.zustand import Einrichtungsfehler
from backend.app.familie import rechte
from backend.app.familie.modelle import Profil
from backend.app.familie.stufen import stufenbuch


@dataclass(frozen=True)
class Zugang:
    ohne_konto: bool                  # neue Installation ohne Konto: offen
    profil: Profil | None


async def zugang(request: Request) -> Zugang:
    if await zustand.modus() == "neu" and not await zustand.konto_da():
        return Zugang(True, None)
    await verify_token(request)
    p: Profil = request.state.profil
    if not rechte.darf(p, "einstellungen"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Das darf dieses Profil nicht: {stufenbuch().faehigkeiten['einstellungen']}")
    return Zugang(False, p)


async def angemeldet(request: Request) -> bool:
    """Ob die Anfrage eine gültige Anmeldung mit Profil trägt; fragt nur, weist nie ab."""
    try:
        await verify_token(request)
    except HTTPException:
        return False
    return True


class ZuOft(Einrichtungsfehler):
    status = 429

    def __init__(self, nochmal_in: int) -> None:
        super().__init__(f"Zu viele Prüfungen, bitte {nochmal_in} Sekunden warten")
        self.nochmal_in = nochmal_in


uhr = time.monotonic
_zuletzt: deque[float] = deque()


def _ist_ip(name: str) -> bool:
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return False
    return True


def _adresse_taugt(adresse: str) -> None:
    teile = urlsplit(adresse)
    name = (teile.hostname or "").rstrip(".").lower()
    if teile.scheme != "https":
        raise Einrichtungsfehler("Adresse: vor dem ersten Konto nur https", 422)
    if not name or _ist_ip(name):
        raise Einrichtungsfehler("Adresse: vor dem ersten Konto nur mit einem Namen, keine IP-Adresse", 422)
    if name == "localhost" or name.endswith(".localhost"):
        raise Einrichtungsfehler("Adresse: vor dem ersten Konto nicht localhost", 422)
    try:
        port = teile.port
    except ValueError:
        raise Einrichtungsfehler("Adresse: der Port ist keine Zahl", 422) from None
    if port is not None and port != 443 and port < 1024:
        raise Einrichtungsfehler("Adresse: vor dem ersten Konto kein Port unter 1024 außer 443", 422)


def _takt() -> None:
    jetzt = uhr()
    while _zuletzt and jetzt - _zuletzt[0] >= 60:
        _zuletzt.popleft()
    if len(_zuletzt) >= settings.einrichtung_pruefungen_je_minute:
        raise ZuOft(int(60 - (jetzt - _zuletzt[0])) + 1)
    _zuletzt.append(jetzt)


def vor_dem_konto(z: Zugang, adresse: str) -> None:
    """Vor dem ersten Konto: nur eine Adresse mit Namen über https, nur wenige je Minute; danach gilt die Anmeldung. Ohne Adresse
    geht keine Anfrage hinaus."""
    if z.ohne_konto and adresse:
        _adresse_taugt(adresse)
        _takt()
