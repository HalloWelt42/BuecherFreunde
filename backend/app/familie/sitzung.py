"""Profilsitzung (BF-78): nach der Wahl trägt jede Anfrage den Profilschlüssel im Kopf `X-Profil`; gespeichert ist nur seine
Prüfsumme. Ein Schlüssel gilt, bis gewechselt oder abgemeldet wird. Bilder, Dateien und Ereignisströme haben keinen Kopf: für sie
setzt die Wahl das Cookie `bf_profil` (nur für /api, nur zum Lesen, neben dem Inhalts-Cookie der Anmeldung).

Ohne Schlüssel gilt das einzige Profil, solange es genau eins ohne PIN gibt (so bleibt die App für alte Oberflächen, wie sie
war); sonst verlangt jeder persönliche Weg ein Profil. Die Wahl geht auch dann, wenn es nur ein Profil ohne PIN gibt.

Ein Gerät kennt sich an `X-Geraet`; ist es fest auf ein Kind gestellt, gilt nur dieses Profil, außer für eine Sitzung, die nach
der PIN der Eltern gewählt wurde (`ueber_bindung`, familie/geraet.py)."""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass

from starlette.requests import Request

from backend.app.core.database import db
from backend.app.familie import geraet, pin, profile
from backend.app.familie.fehler import NichtErlaubt
from backend.app.familie.modelle import Profil, Wahl

KOPF = "x-profil"
GERAET_KOPF = "x-geraet"
COOKIE = "bf_profil"
_GERAET = re.compile(r"^[A-Za-z0-9_-]{8,100}$")
FREMDES_GERAET = "Dieses Gerät ist fest auf ein anderes Profil gestellt"


class ProfilNoetig(Exception):
    """Ohne gültiges Profil geht dieser Weg nicht (401, code profil_waehlen)."""

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


@dataclass(frozen=True)
class Sitzung:
    profil: Profil
    ueber_bindung: bool                              # nach der Eltern-PIN auf einem fest gestellten Gerät gewählt


def pruefsumme(schluessel: str) -> str:
    return hashlib.sha256(schluessel.encode()).hexdigest()


def schluessel_aus(request: Request, inhalt: bool = False) -> str:
    return request.headers.get(KOPF, "") or (request.cookies.get(COOKIE, "") if inhalt else "")


def geraet_aus(request: Request) -> str:
    """Die Kennung des Browsers; was nicht danach aussieht, gilt als keine."""
    g = request.headers.get(GERAET_KOPF, "")
    return g if _GERAET.fullmatch(g) else ""


async def zum_schluessel(schluessel: str) -> Sitzung | None:
    if not schluessel:
        return None
    z = await db.fetch_one("SELECT profil_id, ueber_bindung, zuletzt_am < strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-1 day') AS alt "
                           "FROM profil_sitzung WHERE pruefsumme = ?", (pruefsumme(schluessel),))
    if z is None:
        return None
    if z["alt"]:
        await db.execute("UPDATE profil_sitzung SET zuletzt_am = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE pruefsumme = ?",
                         (pruefsumme(schluessel),))
        await db.commit()                # vor dem Weg selbst: hält keine Sperre über die ganze Anfrage
    p = await profile.holen(z["profil_id"])
    return Sitzung(p, bool(z["ueber_bindung"])) if p else None


async def profil_zum_schluessel(schluessel: str) -> Profil | None:
    s = await zum_schluessel(schluessel)
    return s.profil if s else None


async def beenden(schluessel: str) -> None:
    if schluessel:
        await db.execute("DELETE FROM profil_sitzung WHERE pruefsumme = ?", (pruefsumme(schluessel),))


async def waehlen(wahl: Wahl, kennung_geraet: str, bisher: str) -> tuple[str, Profil]:
    """Prüft PIN oder Bild-PIN und gibt einen neuen Schlüssel; der bisherige dieses Browsers endet. Auf einem fest gestellten
    Gerät geht ein anderes Profil nur, solange die Wahl nach der Eltern-PIN offen ist."""
    p = await profile.noetig(wahl.profil_id)
    b = await geraet.bindung(kennung_geraet)
    ueber = b is not None and b.profil_id != p.id
    if ueber and not b.offen:
        raise NichtErlaubt(FREMDES_GERAET)
    await pin.profil_pruefen(p.id, wahl.pin, wahl.bild_pin)
    await beenden(bisher)
    schluessel = secrets.token_urlsafe(32)
    await db.execute("INSERT INTO profil_sitzung (pruefsumme, profil_id, geraet, ueber_bindung) VALUES (?, ?, ?, ?)",
                     (pruefsumme(schluessel), p.id, kennung_geraet, int(ueber)))
    if ueber:
        await geraet.schliessen(kennung_geraet)
    return schluessel, p


async def verlassen(schluessel: str, kennung_geraet: str, eltern_pin: str | None) -> None:
    """Profil verlassen. Auf einem fest gestellten Gerät verlässt das Kind sein Profil nur mit der PIN der Eltern; dann ist die
    Profilwahl hier eine Weile offen. Die Bindung bleibt."""
    s = await zum_schluessel(schluessel)
    b = await geraet.bindung(kennung_geraet)
    kind_des_geraets = b is not None and (s.profil.id == b.profil_id if s else bool(eltern_pin))
    if kind_des_geraets:
        await pin.eltern_pruefen(eltern_pin, kennung_geraet)
        await geraet.oeffnen(kennung_geraet)
    await beenden(schluessel)


async def aufloesen(request: Request, inhalt: bool = False) -> Profil:
    """Das Profil dieser Anfrage; wirft `ProfilNoetig`, wenn eins gewählt sein muss."""
    schluessel = schluessel_aus(request, inhalt)
    if schluessel:
        s = await zum_schluessel(schluessel)
        if s is None:
            raise ProfilNoetig("Das gewählte Profil gilt nicht mehr, bitte neu wählen")
        b = await geraet.bindung(geraet_aus(request))
        if b and b.profil_id != s.profil.id and not s.ueber_bindung:
            raise ProfilNoetig(FREMDES_GERAET)
        return s.profil
    if await profile.braucht_wahl():
        raise ProfilNoetig("Bitte zuerst ein Profil wählen")
    return await profile.einziges()
