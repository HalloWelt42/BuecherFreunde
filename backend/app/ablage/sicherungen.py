"""Sicherungen in der Kellerwolke (BF-82, HELF-21): jede neue Sicherung kommt auch nach `Apps/BücherFreunde/Sicherung`, solange
eingeschaltet (Einstellung `sicherung_in_kellerwolke`, Vorgabe `SICHERUNG_IN_KELLERWOLKE`). Von dort holt sie ein neues Gerät
beim Wiederherstellen. Die Zahl der Bücher und Profile steht in den Feldern der Datei, damit die Liste nichts laden muss.
Gelöscht wird in der Kellerwolke nichts; aufräumen dort bleibt dem Menschen."""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel

from backend.app.ablage.wolke import WolkeFehler, wolke
from backend.app.core import einstellungen
from backend.app.core.config import settings
from backend.app.services import sicherung

logger = logging.getLogger("buecherfreunde.sicherungen")
ORDNER = "Sicherung"
EINSTELLUNG = "sicherung_in_kellerwolke"     # app_settings: "1" an, "0" aus; ohne Eintrag gilt SICHERUNG_IN_KELLERWOLKE


class Abgelegt(BaseModel):
    knoten: str
    name: str
    groesse: int | None = None
    angelegt_am: str | None = None
    buecher: int | None = None
    profile: int | None = None


def ordnerpfad() -> str:
    return f"{settings.ablage_ordner}/{ORDNER}"


async def an() -> bool:
    wert = await einstellungen.lesen(EINSTELLUNG)
    return settings.sicherung_in_kellerwolke if wert is None else wert == "1"


async def setzen(wert: bool) -> None:
    await einstellungen.schreiben(EINSTELLUNG, "1" if wert else "0")


async def ablegen(datei: Path) -> bool:
    """Legt eine Sicherung ab, wenn eingeschaltet und die Kellerwolke da ist; eine gleichnamige bleibt, wie sie ist."""
    if not (wolke.bereit and await an()):
        return False
    await wolke.ordner(ordnerpfad())
    try:
        k = await wolke.datei_schreiben(f"{ordnerpfad()}/{datei.name}", datei)
    except WolkeFehler as f:
        if f.status == 409:
            return True
        raise
    i = sicherung.inhalt(datei)
    await wolke.felder(k["id"], {"buecher": i.buecher, "profile": i.profile, "version": i.version})
    logger.info("Sicherung %s liegt in der Kellerwolke", datei.name)
    return True


async def liste() -> list[Abgelegt]:
    """Die Sicherungen dort, neueste zuerst (nach dem Namen, der die Zeit trägt)."""
    ordner = await wolke.ordner(ordnerpfad())
    aus = []
    async for k in wolke.kinder(ordner["id"]):
        name = str(k.get("name") or "")
        if k.get("typ") != "datei" or not (name.startswith("buecherfreunde_backup_") and name.endswith(".zip")):
            continue
        felder = k.get("felder") or {}
        aus.append(Abgelegt(knoten=k["id"], name=name, groesse=k.get("groesse"), angelegt_am=k.get("geaendert_am") or k.get("angelegt_am"),
                            buecher=felder.get("buecher"), profile=felder.get("profile")))
    return sorted(aus, key=lambda a: a.name, reverse=True)
