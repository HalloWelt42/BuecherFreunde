"""Gerätebindung (BF-78): ein Gerät lässt sich fest auf ein Kind stellen; es zeigt dann nur dieses Profil. Verlässt das Kind sein
Profil mit der PIN der Eltern, ist die Profilwahl auf diesem Gerät eine Weile offen (`zugang.geraet_offen_s`), damit ein
Erwachsener hinauskommt; die Bindung bleibt. Lösen geht nur mit der PIN der Eltern oder als Verwaltung.

Das Gerät kennt sich an der zufälligen Kennung seines Browsers (`X-Geraet`); wer sie löscht, hat ein neues Gerät, kommt aber
ohne PIN in kein anderes Profil."""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.database import db
from backend.app.familie import pin, profile, rechte
from backend.app.familie.fehler import Konflikt, Unpassend
from backend.app.familie.modelle import Profil
from backend.app.familie.stufen import stufenbuch

OHNE_KENNUNG = "Kopf X-Geraet fehlt: die zufällige Kennung dieses Browsers"
JETZT = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"


@dataclass(frozen=True)
class Bindung:
    profil_id: str
    offen: bool                                      # die Profilwahl ist gerade offen (nach der Eltern-PIN)


async def bindung(kennung: str) -> Bindung | None:
    if not kennung:
        return None
    z = await db.fetch_one(f"SELECT profil_id, COALESCE(offen_bis > {JETZT}, 0) AS offen FROM geraet_bindung WHERE geraet = ?", (kennung,))
    return Bindung(z["profil_id"], bool(z["offen"])) if z else None


async def gebunden_an(kennung: str) -> str | None:
    b = await bindung(kennung)
    return b.profil_id if b else None


async def oeffnen(kennung: str) -> None:
    await db.execute(f"UPDATE geraet_bindung SET offen_bis = strftime('%Y-%m-%dT%H:%M:%SZ', 'now', ?) WHERE geraet = ?",
                     (f"+{stufenbuch().zugang.geraet_offen_s} seconds", kennung))


async def schliessen(kennung: str) -> None:
    await db.execute("UPDATE geraet_bindung SET offen_bis = NULL WHERE geraet = ?", (kennung,))


async def binden(kennung: str, profil_id: str, eltern_pin: str) -> None:
    if not kennung:
        raise Unpassend(OHNE_KENNUNG)
    p = await profile.noetig(profil_id)
    if not p.kind:
        raise Unpassend("Fest stellen lässt sich ein Gerät nur auf ein Kind")
    if not await pin.eltern_haben_pin():
        raise Konflikt("Erst braucht ein Erwachsener eine PIN, sonst lässt sich das Gerät nicht wieder lösen")
    await pin.eltern_pruefen(eltern_pin, kennung)
    await db.execute("""INSERT INTO geraet_bindung (geraet, profil_id) VALUES (?, ?)
                        ON CONFLICT(geraet) DO UPDATE SET profil_id = excluded.profil_id, offen_bis = NULL""", (kennung, profil_id))


async def loesen(kennung: str, eltern_pin: str | None, von: Profil | None) -> None:
    """Mit der PIN der Eltern, oder ohne sie, wenn das gewählte Profil Profile verwalten darf."""
    if not kennung:
        raise Unpassend(OHNE_KENNUNG)
    if von is None or not rechte.darf(von, "profile"):
        await pin.eltern_pruefen(eltern_pin, kennung)
    await db.execute("DELETE FROM geraet_bindung WHERE geraet = ?", (kennung,))
