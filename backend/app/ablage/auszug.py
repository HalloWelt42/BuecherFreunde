"""Der Auszug je Buch in der Kellerwolke (Begleiter `auszug`, eine ZIP neben dem Original): Umschlag, Volltext, Seiten und Angaben.
Hier steht die einzige Wahrheit über seine Form. Geschrieben beim Eintragen (annahme/eintragen.py) und nachts für geänderte Angaben
(services/pflege.py); gelesen beim Neuaufbau aus der Kellerwolke und wenn Volltext oder Umschlag auf dem Gerät fehlen.

`angaben.json` in Form `buecherfreunde-angaben/1`: `{art, buch, kategorien, lesen, notizen, markierungen, labels}`; `buch` ist die
Zeile der Tabelle books ohne Suchtext und Pfad. Das Persönliche steht seit BF-82 nie mehr hier, sondern im eigenen kleinen
Begleiter `persoenlich` (ablage/persoenlich.py); die vier Listen bleiben leer. Ältere Auszüge (bis BF-81, tools/umzug) tragen darin
Zeilen der Tabellen, mit `profil_id` seit BF-78; sie werden weiter gelesen."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from pydantic import BaseModel, Field

from backend.app.ablage.persoenlich import Etikett, Lesestand, Markierung, Notiz, Persoenliches
from backend.app.ablage.wolke import wolke
from backend.app.core.database import db
from backend.app.services.storage import get_sidecar_path

FORM = "buecherfreunde-angaben/1"
DATEIEN = ("cover.jpg", "fulltext.txt", "seiten.json", "metadata.json")


class Angaben(BaseModel):
    art: str = FORM
    buch: dict[str, Any]                      # die Zeile der Tabelle books, wie sie ist (ohne Suchtext und Pfad)
    kategorien: list[str] = Field(default_factory=list)
    lesen: list[dict[str, Any]] = Field(default_factory=list)          # nur noch in alten Auszügen gefüllt: Zeilen der Tabellen
    notizen: list[dict[str, Any]] = Field(default_factory=list)
    markierungen: list[dict[str, Any]] = Field(default_factory=list)
    labels: list[dict[str, Any]] = Field(default_factory=list)

    def persoenliches(self) -> dict[str, Persoenliches]:
        """Was ein alter Auszug an Persönlichem trägt, je Profil; ohne `profil_id` gehört es dem ersten Profil Verwaltung ("")."""
        je: dict[str, Persoenliches] = {}

        def von(z: dict) -> Persoenliches:
            return je.setdefault(str(z.get("profil_id") or ""), Persoenliches())

        for z in self.lesen:
            von(z).lesestand = Lesestand.model_validate(z)
        for zeilen, art, liste in ((self.notizen, Notiz, "notizen"), (self.markierungen, Markierung, "markierungen"), (self.labels, Etikett, "etiketten")):
            for z in zeilen:
                getattr(von(z), liste).append(art.model_validate({k: v for k, v in z.items() if v is not None}))
        return {k: p for k, p in je.items() if not p.leer}


class Gelesen(BaseModel):
    """Ein gelesener Auszug: Angaben und die übrigen Dateien."""

    angaben: Angaben | None
    dateien: dict[str, bytes]


def _ohne(zeile: dict, *weg: str) -> dict:
    return {k: v for k, v in zeile.items() if k not in weg}


async def angaben(buch: int) -> Angaben:
    zeile = await db.fetch_one("SELECT * FROM books WHERE id = ?", (buch,))
    kategorien = await db.fetch_all("SELECT c.name FROM categories c JOIN book_categories x ON x.category_id = c.id WHERE x.book_id = ? "
                                    "ORDER BY c.name", (buch,))
    return Angaben(buch=_ohne(zeile or {}, "fts_content", "storage_path"), kategorien=[z["name"] for z in kategorien])


async def bauen(buch: int, file_hash: str) -> bytes:
    """Der Auszug eines Buchs, ohne Persönliches."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for n in DATEIEN:
            f = get_sidecar_path(file_hash, n)
            if f.is_file():
                z.write(f, n, zipfile.ZIP_STORED if n == "cover.jpg" else zipfile.ZIP_DEFLATED)
        z.writestr("angaben.json", (await angaben(buch)).model_dump_json(indent=1))
    return puffer.getvalue()


def lesen(inhalt: bytes) -> Gelesen:
    """Ein Auszug aus der Kellerwolke; ohne lesbare Angaben `angaben` None. Nur bekannte Namen, nie ein Pfad aus der ZIP."""
    with zipfile.ZipFile(io.BytesIO(inhalt)) as z:
        namen = set(z.namelist())
        dateien = {n: z.read(n) for n in DATEIEN if n in namen}
        roh = json.loads(z.read("angaben.json")) if "angaben.json" in namen else None
    return Gelesen(angaben=Angaben.model_validate(roh) if isinstance(roh, dict) else None, dateien=dateien)


async def holen(original: str) -> Gelesen | None:
    """Der Auszug neben einem Original in der Kellerwolke; None ohne."""
    begleiter = next((b for b in await wolke.begleiter(original) if b.get("rolle") == "auszug"), None)
    return lesen(await wolke.inhalt(begleiter["id"])) if begleiter else None


def dateien_ablegen(file_hash: str, gelesen: Gelesen, nur_fehlende: bool = True) -> list[str]:
    """Umschlag, Volltext, Seiten und Angaben aus dem Auszug an ihre Orte auf dem Gerät; mit `nur_fehlende` bleibt, was da ist.
    Antwortet, welche Dateien geschrieben wurden."""
    geschrieben = []
    for name, inhalt in gelesen.dateien.items():
        ziel = get_sidecar_path(file_hash, name)
        if nur_fehlende and ziel.exists():
            continue
        ziel.parent.mkdir(parents=True, exist_ok=True)
        teil = ziel.with_name(f".{name}.teil")
        teil.write_bytes(inhalt)
        teil.replace(ziel)
        geschrieben.append(name)
    return geschrieben
