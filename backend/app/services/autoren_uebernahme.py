"""Angaben zu einem Autor in die Bibliothek übernehmen: Felder, Verweise auf Normdateien, Foto und Werkliste. Ein Weg für die
Übernahme von Hand und den Abgleich."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.quellen import bilder
from backend.app.quellen.abgleich import norm, titel_naehe
from backend.app.quellen.fehler import QuelleFehler

FELDER = ("name", "biography", "beschreibung", "birth_year", "death_year", "nationality", "wikidata_id", "wikipedia_url", "website", "quelle", "konfidenz", "score")
WERK_NAH = 0.9
WERK_KURZ = 4                       # kürzere Titel gelten nur bei voller Gleichheit
# Art -> wie die Kennung aussieht und wohin sie zeigt
VERWEISARTEN: dict[str, tuple[str, str]] = {
    "gnd": (r"[\dX-]{6,12}", "https://d-nb.info/gnd/{}"), "viaf": (r"\d{4,24}", "https://viaf.org/viaf/{}"),
    "isni": (r"\d{15}[\dX]", "https://isni.org/isni/{}"), "orcid": (r"(?:\d{4}-){3}\d{3}[\dX]", "https://orcid.org/{}"),
}
OHNE_EINTRAG = ("(a.wikidata_id IS NULL OR a.wikidata_id = '') AND NOT EXISTS (SELECT 1 FROM autor_verweis v WHERE v.author_id = a.id AND v.art = 'gnd')")


class Verweis(BaseModel):
    art: str
    kennung: str
    adresse: str


class Uebernahme(BaseModel):
    uebernommen: bool = True
    felder: list[str] = Field(default_factory=list)
    foto_gespeichert: bool = False
    werke_gespeichert: int = 0
    hinweis: str = ""


def slug(text: str) -> str:
    """Erzeugt einen URL-freundlichen Slug."""
    s = re.sub(r"[^\w\s-]", "", text.lower().strip())
    return re.sub(r"[-\s]+", "-", s).strip("-")


async def doppel(autor: int, felder: Mapping[str, Any]) -> dict[str, Any] | None:
    """Ein anderer Autor, der schon denselben Eintrag trägt."""
    nummer, gnd = felder.get("wikidata_id") or "", (felder.get("verweise") or {}).get("gnd", "")
    if nummer and (da := await db.fetch_one("SELECT id, name FROM authors WHERE wikidata_id = ? AND id != ?", (nummer, autor))):
        return da
    return await db.fetch_one("SELECT a.id, a.name FROM authors a JOIN autor_verweis v ON v.author_id = a.id WHERE v.art = 'gnd' AND v.kennung = ? AND a.id != ?", (gnd, autor)) if gnd else None


async def zusammenlegen(autor: int, ziel: int) -> None:
    """Die Bücher eines Autors an einen anderen hängen; der leere Autor geht."""
    await db.execute("UPDATE OR IGNORE book_authors SET author_id = ? WHERE author_id = ?", (ziel, autor))
    await db.execute("DELETE FROM book_authors WHERE author_id = ?", (autor,))
    await db.execute("DELETE FROM authors WHERE id = ?", (autor,))
    await db.commit()


async def verweise(autor: int) -> list[Verweis]:
    zeilen = await db.fetch_all("SELECT art, kennung FROM autor_verweis WHERE author_id = ?", (autor,))
    da = {z["art"]: z["kennung"] for z in zeilen}
    return [Verweis(art=art, kennung=da[art], adresse=muster.format(da[art])) for art, (_, muster) in VERWEISARTEN.items() if art in da]


async def verweise_setzen(autor: int, neue: Mapping[str, str]) -> list[str]:
    gesetzt = [art for art, (form, _) in VERWEISARTEN.items() if re.fullmatch(form, str(neue.get(art) or ""))]
    for art in gesetzt:
        await db.execute("INSERT OR REPLACE INTO autor_verweis(author_id, art, kennung) VALUES (?, ?, ?)", (autor, art, str(neue[art])))
    return gesetzt


async def _felder_setzen(autor: int, felder: Mapping[str, Any]) -> list[str]:
    neu = {k: felder[k] for k in FELDER if felder.get(k) is not None}
    if "quelle" not in neu and neu.get("wikidata_id"):
        neu["quelle"] = "wikidata"
    if neu.get("name"):
        kurz = slug(neu["name"])
        vergeben = await db.fetch_one("SELECT id FROM authors WHERE slug = ? AND id != ?", (kurz, autor))
        if kurz and not vergeben:
            neu["slug"] = kurz
    if neu:
        await db.execute(f"UPDATE authors SET {', '.join(f'{k} = ?' for k in neu)}, updated_at = datetime('now') WHERE id = ?", (*neu.values(), autor))
    return list(neu)


async def _werke_setzen(autor: int, werke: list[Mapping[str, Any]]) -> int:
    """Die Werkliste ersetzen; ein Werk, das als Buch des Autors im Bestand ist, zeigt dorthin."""
    buecher = await db.fetch_all("SELECT b.id, b.title FROM books b JOIN book_authors ba ON ba.book_id = b.id WHERE ba.author_id = ?", (autor,))

    def im_bestand(titel: str) -> int | None:
        kurz = len(norm(titel)) < WERK_KURZ
        return next((b["id"] for b in buecher if (norm(b["title"]) == norm(titel) if kurz else norm(titel) in norm(b["title"]) or titel_naehe(b["title"], titel) >= WERK_NAH)), None)

    genannt = [w for w in werke if w.get("titel")]
    await db.execute("DELETE FROM author_works WHERE author_id = ?", (autor,))
    for w in genannt:
        await db.execute("INSERT INTO author_works (author_id, wikidata_id, titel, book_id) VALUES (?, ?, ?, ?)", (autor, w.get("wikidata_id", ""), w["titel"], im_bestand(w["titel"])))
    return len(genannt)


async def _foto_holen(adresse: str) -> tuple[dict[str, bytes] | None, str]:
    if not adresse:
        return None, ""
    try:
        fotos = await bilder.autorenfoto(adresse)
    except QuelleFehler as f:
        return None, f.grund
    return fotos, "" if fotos else "Dort liegt kein brauchbares Foto"


async def _foto_ablegen(autor: int, fotos: dict[str, bytes]) -> None:
    ordner = settings.storage_dir / "authors" / str(autor)
    ordner.mkdir(parents=True, exist_ok=True)
    for name, daten in fotos.items():
        (ordner / name).write_bytes(daten)
    await db.execute("UPDATE authors SET photo_path = 'foto.jpg', updated_at = datetime('now') WHERE id = ?", (autor,))


async def uebernehmen(autor: int, felder: Mapping[str, Any]) -> Uebernahme:
    """Nur was in `felder` steht. Das Foto wird vor dem Schreiben geholt, es kann dauern."""
    fotos, hinweis = await _foto_holen(felder.get("photo_url") or "")
    gesetzt = await _felder_setzen(autor, felder)
    gesetzt += await verweise_setzen(autor, felder.get("verweise") or {})
    if fotos:
        await _foto_ablegen(autor, fotos)
    werke = await _werke_setzen(autor, felder["werke"]) if felder.get("werke") else 0
    await db.commit()
    return Uebernahme(felder=gesetzt, foto_gespeichert=bool(fotos), werke_gespeichert=werke, hinweis=hinweis)


async def sicher_uebernehmen(autor: int, felder: Mapping[str, Any]) -> str:
    """Für den Abgleich: übernimmt, ohne einen längeren Namen zu kürzen; nennt den Grund, wenn nicht."""
    if da := await doppel(autor, felder):
        return f"Diesen Eintrag hat schon {da['name']}"
    bisher = await db.fetch_one("SELECT name FROM authors WHERE id = ?", (autor,))
    neu = {k: w for k, w in felder.items() if w}
    if bisher and len(neu.get("name", "")) <= len(bisher["name"]):
        neu.pop("name", None)
    await uebernehmen(autor, neu)
    return ""
