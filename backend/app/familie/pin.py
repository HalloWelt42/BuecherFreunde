"""PIN und Bild-PIN (BF-78): nur als scrypt-Wert gespeichert, wie Kennwörter (core/eigene_anmeldung.py). Fehlversuche je
Profil zählen; ab der Zahl aus stufen.json wächst die Wartezeit, bis höchstens zur Grenze von dort. Eine Bild-PIN sind die
Bilder in ihrer Folge.

Die Eltern-PIN ist die PIN eines Erwachsenen (Verwaltung oder Erwachsen); hat keiner eine, gibt es nichts zu prüfen."""

from __future__ import annotations

import asyncio
import time

from backend.app.core.database import db
from backend.app.core.eigene_anmeldung import stimmt, verschluesseln
from backend.app.familie.fehler import Falsch, ZuVieleVersuche
from backend.app.familie.stufen import ERWACHSENE, stufenbuch

FALSCH = "Die PIN stimmt nicht"


def bilder_text(bilder: list[str]) -> str:
    return "|".join(bilder)


async def wert(geheimnis: str) -> str:
    return await asyncio.to_thread(verschluesseln, geheimnis)


async def passt(geheimnis: str, gemerkt: str) -> bool:
    return bool(gemerkt) and await asyncio.to_thread(stimmt, geheimnis, gemerkt)


class Fehlversuche:
    """Je Schlüssel (Profil, Eltern auf einem Gerät) die Fehlversuche und ab wann es wieder geht."""

    def __init__(self, uhr=time.monotonic) -> None:
        self.uhr = uhr
        self._je: dict[str, tuple[int, float]] = {}

    def pruefen(self, schluessel: str) -> None:
        _anzahl, frei_ab = self._je.get(schluessel, (0, 0.0))
        if self.uhr() < frei_ab:
            raise ZuVieleVersuche(int(frei_ab - self.uhr()) + 1)

    def fehlgeschlagen(self, schluessel: str) -> None:
        z = stufenbuch().zugang
        anzahl = self._je.get(schluessel, (0, 0.0))[0] + 1
        warten = min(z.warten_hoechstens_s, z.warten_ab_s * 2 ** (anzahl - z.fehlversuche_frei)) if anzahl >= z.fehlversuche_frei else 0
        self._je[schluessel] = (anzahl, self.uhr() + warten)

    def gelungen(self, schluessel: str) -> None:
        self._je.pop(schluessel, None)

    def leeren(self) -> None:
        self._je.clear()


versuche = Fehlversuche()


async def profil_pruefen(profil_id: str, pin: str | None, bild_pin: list[str] | None) -> None:
    """Wirft, wenn das Profil eine PIN oder Bild-PIN hat und die Angabe nicht passt; zählt Fehlversuche."""
    z = await db.fetch_one("SELECT pin, bild_pin FROM profil WHERE id = ?", (profil_id,))
    if z is None or not (z["pin"] or z["bild_pin"]):
        return
    versuche.pruefen(profil_id)
    richtig = (pin is not None and await passt(pin, z["pin"])) or (bild_pin is not None and await passt(bilder_text(bild_pin), z["bild_pin"]))
    if not richtig:
        versuche.fehlgeschlagen(profil_id)
        raise Falsch(FALSCH)
    versuche.gelungen(profil_id)


async def eltern_pruefen(eltern_pin: str | None, geraet: str) -> None:
    """Die PIN eines Erwachsenen; hat keiner eine, gibt es nichts zu prüfen."""
    zeilen = await db.fetch_all(f"SELECT pin FROM profil WHERE rolle IN ({','.join('?' * len(ERWACHSENE))}) AND pin != ''", ERWACHSENE)
    if not zeilen:
        return
    schluessel = f"eltern:{geraet}"
    versuche.pruefen(schluessel)
    for z in zeilen:
        if eltern_pin and await passt(eltern_pin, z["pin"]):
            versuche.gelungen(schluessel)
            return
    versuche.fehlgeschlagen(schluessel)
    raise Falsch("Die PIN der Eltern stimmt nicht")


async def eltern_haben_pin() -> bool:
    return await db.fetch_one(f"SELECT 1 FROM profil WHERE rolle IN ({','.join('?' * len(ERWACHSENE))}) AND pin != '' LIMIT 1",
                              ERWACHSENE) is not None
