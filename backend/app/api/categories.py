"""API-Endpunkte für Regale (`categories` mit `art` regal). Bereiche und Kategorien des Katalogs (BF-69) haben ihre Wege
unter /api/katalog; Bücher hinein und hinaus geht für beide hier."""

import re

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from backend.app.api import vorhanden
from backend.app.core.auth import verify_token
from backend.app.core.database import db
from backend.app.models.grenzen import AUSWAHL_HOECHSTENS, Farbe, Nr, Regalbeschreibung, Regalname, Sortierung, Symbol

router = APIRouter(prefix="/api/categories", tags=["Kategorien"])


def _slugify(text: str) -> str:
    """Erzeugt einen URL-freundlichen Slug aus dem Text."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


FEHLT = "Regal nicht gefunden"
DOPPELT = "Ein Regal mit diesem Namen gibt es schon"


class CategoryCreate(BaseModel):
    name: Regalname
    description: Regalbeschreibung = ""
    color: Farbe = "#6b7280"
    icon: Symbol = ""
    sort_order: Sortierung = 0
    spezial: bool = False


class CategoryUpdate(BaseModel):
    name: Regalname | None = None
    description: Regalbeschreibung | None = None
    color: Farbe | None = None
    icon: Symbol | None = None
    sort_order: Sortierung | None = None
    spezial: bool | None = None


async def _freier_slug(name: str, ausser: int | None = None) -> str:
    """Ein Name gehört genau einem Regal (409 sonst); fällt nur das Kürzel zusammen ("Sci-Fi", "Sci Fi"), wird gezählt.
    Kategorien des Katalogs dürfen wie ein Regal heißen."""
    if await db.fetch_one("SELECT id FROM categories WHERE name = ? COLLATE NOCASE AND art = 'regal' AND id IS NOT ?", (name, ausser)):
        raise HTTPException(status_code=409, detail=DOPPELT)
    grund = _slugify(name) or "regal"
    slug, zaehler = grund, 2
    while await db.fetch_one("SELECT id FROM categories WHERE slug = ? AND id IS NOT ?", (slug, ausser)):
        slug, zaehler = f"{grund}-{zaehler}", zaehler + 1
    return slug


async def _regal(nr: int) -> None:
    """Nur Regale; Bereiche und Kategorien des Katalogs ändert und löscht /api/katalog (nach den Folgen)."""
    if not await db.fetch_one("SELECT id FROM categories WHERE id = ? AND art = 'regal'", (nr,)):
        raise HTTPException(status_code=404, detail=FEHLT)


@router.get("")
async def list_categories(_token: str = Depends(verify_token)):
    """Alle Regale als flache Liste mit Buchanzahl (ohne Bereiche und Kategorien des Katalogs)."""
    rows = await db.fetch_all(
        """SELECT c.id, c.name, c.slug, c.description, c.color, c.icon,
                  c.sort_order, c.spezial,
                  COUNT(bc.book_id) as buch_anzahl
           FROM categories c
           LEFT JOIN book_categories bc ON bc.category_id = c.id
           WHERE c.art = 'regal'
           GROUP BY c.id
           ORDER BY c.sort_order, c.name"""
    )
    return [dict(row) for row in rows]


@router.post("", status_code=201)
async def create_category(data: CategoryCreate, _token: str = Depends(verify_token)):
    """Erstellt eine neue Kategorie."""
    slug = await _freier_slug(data.name)
    cursor = await db.execute(
        """INSERT INTO categories (name, slug, description, color, icon, sort_order, spezial)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (data.name, slug, data.description, data.color, data.icon, data.sort_order, int(data.spezial)),
    )
    await db.commit()

    return await db.fetch_one("SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,))


@router.patch("/{category_id}")
async def update_category(
    category_id: Nr, data: CategoryUpdate, _token: str = Depends(verify_token)
):
    """Aktualisiert ein Regal."""
    await _regal(category_id)
    updates = data.model_dump(exclude_none=True)
    if "name" in updates:
        updates["slug"] = await _freier_slug(updates["name"], category_id)
    if "spezial" in updates:
        updates["spezial"] = int(updates["spezial"])

    if not updates:
        raise HTTPException(status_code=400, detail="Keine Felder zum Aktualisieren")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [category_id]
    await db.execute(f"UPDATE categories SET {set_clause} WHERE id = ?", tuple(values))
    await db.commit()

    return await db.fetch_one("SELECT * FROM categories WHERE id = ?", (category_id,))


@router.delete("/{category_id}")
async def delete_category(category_id: Nr, _token: str = Depends(verify_token)):
    """Löscht ein Regal (Bücher bleiben erhalten)."""
    await _regal(category_id)

    await db.execute("DELETE FROM book_categories WHERE category_id = ?", (category_id,))
    await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    await db.commit()

    return {"geloescht": True, "id": category_id}


@router.post("/{book_id}/zuordnen")
async def assign_categories(
    book_id: Nr, kategorie_ids: Annotated[list[Nr], Body(max_length=AUSWAHL_HOECHSTENS)], _token: str = Depends(verify_token)
):
    """Ordnet einem Buch Kategorien zu (ersetzt bestehende). Fehlt eines der Regale, ändert sich nichts (404)."""
    await vorhanden.buch(book_id)
    kategorie_ids = list(dict.fromkeys(kategorie_ids))
    da = {z["id"] for z in await db.fetch_all(f"SELECT id FROM categories WHERE id IN ({','.join('?' * len(kategorie_ids))})", tuple(kategorie_ids))} if kategorie_ids else set()
    if fehlen := [k for k in kategorie_ids if k not in da]:
        raise HTTPException(status_code=404, detail=f"{FEHLT}: {', '.join(map(str, fehlen))}")

    await db.execute("DELETE FROM book_categories WHERE book_id = ?", (book_id,))
    for cat_id in kategorie_ids:
        await db.execute(
            "INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'manuell')",
            (book_id, cat_id),
        )
    await db.commit()

    return {"book_id": book_id, "kategorien": kategorie_ids}


@router.post("/{category_id}/books/{book_id}")
async def add_book_to_category(
    category_id: Nr, book_id: Nr, _token: str = Depends(verify_token)
):
    """Fügt ein Buch zu einer Kategorie hinzu."""
    await vorhanden.buch(book_id)
    await vorhanden.eintrag("categories", category_id, FEHLT, "id")

    await db.execute(
        "INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'manuell')",
        (book_id, category_id),
    )
    await db.commit()
    return {"message": "Kategorie zugeordnet"}


@router.delete("/{category_id}/books/{book_id}")
async def remove_book_from_category(
    category_id: Nr, book_id: Nr, _token: str = Depends(verify_token)
):
    """Entfernt ein Buch aus einer Kategorie."""
    c = await db.execute(
        "DELETE FROM book_categories WHERE book_id = ? AND category_id = ?",
        (book_id, category_id),
    )
    vorhanden.getroffen(c, "Das Buch steht nicht in diesem Regal")
    await db.commit()
    return {"message": "Kategorie entfernt"}
