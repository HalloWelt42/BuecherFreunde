"""Anmeldung ohne Kellerwolke: eigene Konten der App, mit denselben Aufrufen wie der Baustein des Appkern. Beim ersten Start
legt man ein Konto an (`einrichten`); danach geht das nicht mehr. Kennwörter liegen nur als scrypt-Wert, Sitzungen nur als
Prüfsumme in der Datenbank."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import secrets
import time

from appkern.anmeldung import AnmeldungsFehler, Konto
from appkern.anmeldung.dienst import Abgelehnt, NichtErlaubt, ZuVieleVersuche

from backend.app.core.database import db

KENNWORT_MINDESTENS = 8
SITZUNG_TAGE = 90
FREI = 5                              # so viele Fehlversuche je Name ohne Wartezeit
WARTEN_HOECHSTENS_S = 15 * 60
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}


class Unbrauchbar(AnmeldungsFehler):
    """Name oder Kennwort taugen nicht zum Anlegen."""

    status = 422


def _wert(kennwort: str, salz: bytes) -> bytes:
    return hashlib.scrypt(kennwort.encode(), salt=salz, **_SCRYPT)


def verschluesseln(kennwort: str) -> str:
    salz = secrets.token_bytes(16)
    return f"scrypt${salz.hex()}${_wert(kennwort, salz).hex()}"


def stimmt(kennwort: str, gemerkt: str) -> bool:
    try:
        _, salz, wert = gemerkt.split("$")
        return hmac.compare_digest(_wert(kennwort, bytes.fromhex(salz)), bytes.fromhex(wert))
    except ValueError:
        return False


_FALSCH = verschluesseln(secrets.token_hex(16))     # gegen das Erraten von Namen: auch ohne Konto wird gerechnet


def _pruefsumme(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class EigeneAnmeldung:
    def __init__(self, uhr=time.monotonic) -> None:
        self._uhr = uhr
        self._versuche: dict[str, tuple[int, float]] = {}

    @property
    def eigene(self) -> EigeneAnmeldung:
        """Wie bei der Weiche (core/anmeldung.py): die eigenen Konten gelten."""
        return self

    async def eingerichtet(self) -> bool:
        return await db.fetch_one("SELECT id FROM nutzer LIMIT 1") is not None

    async def einrichten(self, name: str, kennwort: str) -> tuple[str, Konto]:
        name = name.strip()
        if not 1 <= len(name) <= 60:
            raise Unbrauchbar("Der Name braucht 1 bis 60 Zeichen")
        self._taugt(kennwort)
        wert = await asyncio.to_thread(verschluesseln, kennwort)
        c = await db.execute("INSERT INTO nutzer(name, kennwort) SELECT ?, ? WHERE NOT EXISTS (SELECT 1 FROM nutzer)", (name, wert))
        await db.commit()
        if not c.rowcount:
            raise NichtErlaubt("Es gibt schon ein Konto")
        return await self._sitzung({"id": c.lastrowid, "name": name})

    @staticmethod
    def _taugt(kennwort: str) -> None:
        if len(kennwort) < KENNWORT_MINDESTENS:
            raise Unbrauchbar(f"Das Kennwort braucht mindestens {KENNWORT_MINDESTENS} Zeichen")

    async def kennwort_aendern(self, konto: Konto, alt: str, neu: str) -> None:
        """Neues Kennwort; alle anderen Anmeldungen enden."""
        z = await db.fetch_one("SELECT kennwort FROM nutzer WHERE id = ?", (int(konto.id),))
        if z is None or not await asyncio.to_thread(stimmt, alt, z["kennwort"]):
            raise NichtErlaubt("Das bisherige Kennwort stimmt nicht")
        self._taugt(neu)
        await db.execute("UPDATE nutzer SET kennwort = ? WHERE id = ?", (await asyncio.to_thread(verschluesseln, neu), int(konto.id)))
        await db.execute("DELETE FROM nutzer_sitzung WHERE nutzer = ?", (int(konto.id),))
        await db.commit()

    async def anmelden(self, kennung: str, passwort: str) -> tuple[str, Konto]:
        name = kennung.strip().lower()
        anzahl, frei_ab = self._versuche.get(name, (0, 0.0))
        if self._uhr() < frei_ab:
            rest = int(frei_ab - self._uhr()) + 1
            raise ZuVieleVersuche(f"Zu viele Versuche, bitte {rest} Sekunden warten", rest)
        z = await db.fetch_one("SELECT id, name, kennwort FROM nutzer WHERE name = ?", (kennung.strip(),))
        if not await asyncio.to_thread(stimmt, passwort, z["kennwort"] if z else _FALSCH) or z is None:
            anzahl += 1
            warten = min(WARTEN_HOECHSTENS_S, 15 * 2 ** (anzahl - FREI)) if anzahl >= FREI else 0
            self._versuche[name] = (anzahl, self._uhr() + warten)
            raise Abgelehnt("Name oder Kennwort stimmt nicht")
        self._versuche.pop(name, None)
        return await self._sitzung(z)

    async def _sitzung(self, nutzer: dict) -> tuple[str, Konto]:
        token = secrets.token_urlsafe(32)
        await db.execute("DELETE FROM nutzer_sitzung WHERE zuletzt_am < datetime('now', ?)", (f"-{SITZUNG_TAGE} days",))
        await db.execute("INSERT INTO nutzer_sitzung(schluessel, nutzer) VALUES (?, ?)", (_pruefsumme(token), nutzer["id"]))
        await db.commit()
        return token, Konto(id=str(nutzer["id"]), name=nutzer["name"], rolle="admin")

    async def pruefen(self, token: str) -> Konto | None:
        if not token or token.startswith("kw_app_"):
            return None
        z = await db.fetch_one("SELECT n.id, n.name, s.zuletzt_am < datetime('now', '-1 day') AS alt FROM nutzer_sitzung s JOIN nutzer n ON n.id = s.nutzer "
                               "WHERE s.schluessel = ? AND s.zuletzt_am >= datetime('now', ?)", (_pruefsumme(token), f"-{SITZUNG_TAGE} days"))
        if z is None:
            return None
        if z["alt"]:
            await db.execute("UPDATE nutzer_sitzung SET zuletzt_am = datetime('now') WHERE schluessel = ?", (_pruefsumme(token),))
            await db.commit()
        return Konto(id=str(z["id"]), name=z["name"], rolle="admin")

    async def koppeln(self, code: str, name: str, art: str) -> tuple[str, Konto]:
        raise NichtErlaubt("Koppeln mit Code geht nur mit der Kellerwolke")

    async def abmelden(self, token: str) -> None:
        await db.execute("DELETE FROM nutzer_sitzung WHERE schluessel = ?", (_pruefsumme(token),))
        await db.commit()

    async def schliessen(self) -> None:
        pass
