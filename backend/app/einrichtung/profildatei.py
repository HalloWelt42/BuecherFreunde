"""Die Profile als kleine Datei der App in der Kellerwolke (BF-82): `Apps/BücherFreunde/profile.json` mit Name, Zeichen, Farbe,
Rolle, Geburtsjahr, Stufe und Einstellungen je Profil, den Freigaben ganzer Kategorien und der Stimme der Familie. PINs und
Bild-PINs stehen nie darin; nach einem Neuaufbau setzt man sie neu. Einzelne Bücher, die einem Kind freigegeben sind, stehen im
Begleiter `persoenlich` des Buchs (ablage/persoenlich.py)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

from backend.app.ablage.wolke import wolke
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.familie import ansagen
from backend.app.familie.modelle import Einstellungen

NAME = "profile.json"
FORM = "buecherfreunde-profile/1"


class Profilzeile(BaseModel):
    id: str
    name: str
    zeichen: str = ""
    farbe: str = ""
    rolle: str
    geburtsjahr: int | None = None
    stufe: str | None = None
    einstellungen: Einstellungen = Field(default_factory=Einstellungen)    # die Wahl der Eltern, wie gespeichert
    sortierung: int = 0


class KategorieFreigabe(BaseModel):
    profil: str
    schluessel: str                                         # Schlüssel der Kategorie im Katalog; leer bei Regalen
    name: str


class Profildatei(BaseModel):
    art: str = FORM
    profile: list[Profilzeile] = Field(default_factory=list)
    freigaben: list[KategorieFreigabe] = Field(default_factory=list)
    stimme: str = ""


def pfad() -> str:
    return f"{settings.ablage_ordner}/{NAME}"


async def bauen() -> Profildatei:
    profile = [Profilzeile(**{**z, "einstellungen": Einstellungen.model_validate_json(z["einstellungen"] or "{}")}) for z in await db.fetch_all(
        "SELECT id, name, zeichen, farbe, rolle, geburtsjahr, stufe, einstellungen, sortierung FROM profil ORDER BY sortierung, angelegt_am, id")]
    freigaben = [KategorieFreigabe(**z) for z in await db.fetch_all(
        "SELECT f.profil_id AS profil, c.schluessel, c.name FROM freigabe f JOIN categories c ON c.id = f.ziel_id WHERE f.art = 'kategorie' "
        "ORDER BY f.profil_id, c.name")]
    return Profildatei(profile=profile, freigaben=freigaben, stimme=await ansagen.familienstimme())


async def _knoten() -> dict | None:
    ordner = await wolke.ordner(settings.ablage_ordner)
    async for k in wolke.kinder(ordner["id"]):
        if k.get("name") == NAME and k.get("typ") == "datei":
            return k
    return None


async def schreiben() -> None:
    """Die Datei neu in der Kellerwolke; eine vorhandene bekommt eine neue Version."""
    inhalt = (await bauen()).model_dump_json(indent=1).encode("utf-8")
    settings.zwischen_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=settings.zwischen_dir, prefix=".profile-", suffix=".json", delete=False) as f:
        f.write(inhalt)
        quelle = Path(f.name)
    try:
        alt = await _knoten()
        if alt:
            await wolke.inhalt_ersetzen(alt["id"], quelle, str(alt.get("etag") or ""))
        else:
            await wolke.datei_schreiben(pfad(), quelle)
    finally:
        quelle.unlink(missing_ok=True)


async def lesen() -> Profildatei | None:
    k = await _knoten()
    if k is None:
        return None
    return Profildatei.model_validate_json(await wolke.inhalt(k["id"]))


async def in_den_papierkorb() -> bool:
    k = await _knoten()
    return bool(k) and await wolke.papierkorb(k["id"])
