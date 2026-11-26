"""Das Persönliche je Buch als eigener kleiner Begleiter des Originals in der Kellerwolke (BF-82): Rolle `persoenlich`, Name wie
das Original mit `.persoenlich.json`. Hier steht die einzige Wahrheit über seine Form. Er trägt je Profil Lesestand,
Vorlesestelle, Notizen, Markierungen, Etiketten, ob das Buch privat und ob es einem Kind freigegeben ist; nie Volltext oder
Umschlag (die stehen im Auszug, ablage/auszug.py). So wird beim Lesen nur ein paar hundert Byte neu geschrieben, nie der Auszug.

Form `buecherfreunde-persoenlich/1`: `{art, buch, hash, profile: {<profil_id>: Persoenliches}}`. Geschrieben vom Auftrag
"Persönliches nachführen" (einrichtung/nachfuehren.py), solange "Persönliches in der Kellerwolke" an ist; gelesen beim Neuaufbau."""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, BaseModel, Field

from backend.app.ablage.wolke import wolke
from backend.app.core import einstellungen
from backend.app.core.config import settings
from backend.app.core.database import db

FORM = "buecherfreunde-persoenlich/1"
ROLLE = "persoenlich"                          # Rollen der Kellerwolke nur aus [a-z_]
ZUSATZ = ".persoenlich.json"
EINSTELLUNG = "persoenlich_in_kellerwolke"     # app_settings: "1" an, "0" aus; ohne Eintrag gilt PERSOENLICH_IN_KELLERWOLKE


# Die Seitenangabe ist freier Text, wie in der Schnittstelle der App ("S.19", "2%", "12"); ältere Bestände halten sie in einer
# Spalte mit Zahl als Art, SQLite gibt dann je nach Wert Zahl oder Text zurück. Im Begleiter steht sie immer als Text.
Seite = Annotated[str | None, BeforeValidator(lambda v: None if v is None else str(v))]


class Lesestand(BaseModel):
    """Die Zeile in user_book_data; leer darf jede Spalte sein, wie in der Tabelle."""

    is_favorite: int | None = 0
    is_to_read: int | None = 0
    rating: int | None = 0
    reading_position: str | None = ""
    last_read_at: str | None = None
    fassung_wahl: str | None = ""
    geteilt: int | None = 0
    fertig_am: str | None = None


class Vorlesestelle(BaseModel):
    einheit: int
    zeichen: int
    bis_einheit: int | None = None
    bis_zeichen: int | None = None
    umfang: str = ""
    ort: str = ""
    gemerkt_am: str | None = None


class Notiz(BaseModel):
    content: str
    page_reference: Seite = None
    cfi_reference: str | None = ""
    created_at: str | None = None
    updated_at: str | None = None


class Markierung(BaseModel):
    cfi_range: str
    color: str = "#FFEE58"
    text_snippet: str = ""
    label_name: str = ""
    label_note: str = ""
    created_at: str | None = None


class Etikett(BaseModel):
    color: str = "#4FC3F7"
    name: str = ""
    note: str = ""
    page_reference: Seite = ""
    position_percent: float | None = 0
    cfi_reference: str | None = ""
    created_at: str | None = None


class Persoenliches(BaseModel):
    """Was einem Profil an einem Buch gehört."""

    lesestand: Lesestand | None = None
    vorlesestelle: Vorlesestelle | None = None
    notizen: list[Notiz] = Field(default_factory=list)
    markierungen: list[Markierung] = Field(default_factory=list)
    etiketten: list[Etikett] = Field(default_factory=list)
    privat: bool = False
    freigegeben: bool = False                 # einem Kind einzeln freigegeben (Kategorien stehen in der Datei der Profile)

    @property
    def leer(self) -> bool:
        return not (self.lesestand or self.vorlesestelle or self.notizen or self.markierungen or self.etiketten or self.privat or self.freigegeben)


class Begleiter(BaseModel):
    art: str = FORM
    buch: int
    hash: str
    profile: dict[str, Persoenliches] = Field(default_factory=dict)    # je Profil (Kennung); "" für Daten ohne Profil (alte Auszüge)


async def an() -> bool:
    wert = await einstellungen.lesen(EINSTELLUNG)
    return settings.persoenlich_in_kellerwolke if wert is None else wert == "1"


async def setzen(wert: bool) -> None:
    await einstellungen.schreiben(EINSTELLUNG, "1" if wert else "0")


def _ohne(zeile: dict, *weg: str) -> dict:
    return {k: v for k, v in zeile.items() if k not in weg}


async def sammeln(buch: int) -> dict[str, Persoenliches]:
    """Je Profil, was ihm an diesem Buch gehört; Profile ohne etwas fehlen."""
    je: dict[str, Persoenliches] = {}

    def von(pid: str) -> Persoenliches:
        return je.setdefault(pid, Persoenliches())

    for z in await db.fetch_all("SELECT * FROM user_book_data WHERE book_id = ?", (buch,)):
        von(z["profil_id"]).lesestand = Lesestand(**_ohne(z, "profil_id", "book_id"))
    for z in await db.fetch_all("SELECT * FROM vorlesestelle WHERE buch_id = ?", (buch,)):
        von(z["profil_id"]).vorlesestelle = Vorlesestelle(**_ohne(z, "profil_id", "buch_id"))
    for z in await db.fetch_all("SELECT * FROM book_notes WHERE book_id = ? ORDER BY id", (buch,)):
        von(z["profil_id"]).notizen.append(Notiz(**_ohne(z, "id", "profil_id", "book_id")))
    for z in await db.fetch_all("SELECT * FROM book_highlights WHERE book_id = ? ORDER BY id", (buch,)):
        von(z["profil_id"]).markierungen.append(Markierung(**_ohne(z, "id", "profil_id", "book_id")))
    for z in await db.fetch_all("SELECT * FROM book_labels WHERE book_id = ? ORDER BY id", (buch,)):
        von(z["profil_id"]).etiketten.append(Etikett(**_ohne(z, "id", "profil_id", "book_id")))
    for z in await db.fetch_all("SELECT profil_id FROM buch_privat WHERE book_id = ?", (buch,)):
        von(z["profil_id"]).privat = True
    for z in await db.fetch_all("SELECT profil_id FROM freigabe WHERE art = 'buch' AND ziel_id = ?", (buch,)):
        von(z["profil_id"]).freigegeben = True
    return {pid: p for pid, p in je.items() if not p.leer}


def form(buch: int, file_hash: str, profile: dict[str, Persoenliches]) -> bytes:
    return Begleiter(buch=buch, hash=file_hash, profile=profile).model_dump_json(exclude_none=True).encode("utf-8")


def lesen(inhalt: bytes) -> Begleiter:
    return Begleiter.model_validate_json(inhalt)


async def knoten(original: str) -> str | None:
    """Der Begleiter neben dem Original; None ohne."""
    b = next((b for b in await wolke.begleiter(original) if b.get("rolle") == ROLLE), None)
    return b["id"] if b else None


async def schreiben(original: str, buch: int, file_hash: str) -> int:
    """Schreibt den Begleiter neu (auch leer, wenn alles entfernt wurde); ohne Persönliches und ohne Begleiter bleibt es dabei.
    Antwortet die Größe in Byte (0: nichts geschrieben)."""
    profile = await sammeln(buch)
    if not profile and await knoten(original) is None:
        return 0
    inhalt = form(buch, file_hash, profile)
    await wolke.begleiter_setzen(original, ROLLE, ZUSATZ, inhalt, "application/json")
    return len(inhalt)


async def holen(original: str) -> Begleiter | None:
    k = await knoten(original)
    return lesen(await wolke.inhalt(k)) if k else None
