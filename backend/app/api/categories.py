"""API-Endpunkte für Kategorien."""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.auth import verify_token
from backend.app.core.database import db

router = APIRouter(prefix="/api/categories", tags=["Kategorien"])


def _slugify(text: str) -> str:
    """Erzeugt einen URL-freundlichen Slug aus dem Text."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


class CategoryCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#6b7280"
    icon: str = ""
    sort_order: int = 0
    spezial: bool = False


class CategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    sort_order: int | None = None
    spezial: bool | None = None


@router.get("")
async def list_categories(_token: str = Depends(verify_token)):
    """Gibt alle Kategorien als flache Liste mit Buchanzahl zurück."""
    rows = await db.fetch_all(
        """SELECT c.id, c.name, c.slug, c.description, c.color, c.icon,
                  c.sort_order, c.spezial,
                  COUNT(bc.book_id) as buch_anzahl
           FROM categories c
           LEFT JOIN book_categories bc ON bc.category_id = c.id
           GROUP BY c.id
           ORDER BY c.sort_order, c.name"""
    )
    return [dict(row) for row in rows]


@router.post("", status_code=201)
async def create_category(data: CategoryCreate, _token: str = Depends(verify_token)):
    """Erstellt eine neue Kategorie."""
    slug = _slugify(data.name)

    existing = await db.fetch_one(
        "SELECT id FROM categories WHERE slug = ?", (slug,)
    )
    if existing:
        counter = 2
        while True:
            new_slug = f"{slug}-{counter}"
            exists = await db.fetch_one(
                "SELECT id FROM categories WHERE slug = ?", (new_slug,)
            )
            if not exists:
                slug = new_slug
                break
            counter += 1

    cursor = await db.execute(
        """INSERT INTO categories (name, slug, description, color, icon, sort_order, spezial)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (data.name, slug, data.description, data.color, data.icon, data.sort_order, int(data.spezial)),
    )
    await db.commit()

    return await db.fetch_one("SELECT * FROM categories WHERE id = ?", (cursor.lastrowid,))


@router.patch("/{category_id}")
async def update_category(
    category_id: int, data: CategoryUpdate, _token: str = Depends(verify_token)
):
    """Aktualisiert eine Kategorie."""
    existing = await db.fetch_one(
        "SELECT * FROM categories WHERE id = ?", (category_id,)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")

    updates = data.model_dump(exclude_none=True)
    if "name" in updates:
        updates["slug"] = _slugify(updates["name"])
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
async def delete_category(category_id: int, _token: str = Depends(verify_token)):
    """Löscht eine Kategorie (Bücher bleiben erhalten)."""
    existing = await db.fetch_one(
        "SELECT id FROM categories WHERE id = ?", (category_id,)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Kategorie nicht gefunden")

    await db.execute("DELETE FROM book_categories WHERE category_id = ?", (category_id,))
    await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    await db.commit()

    return {"geloescht": True, "id": category_id}


@router.post("/{book_id}/zuordnen")
async def assign_categories(
    book_id: int, kategorie_ids: list[int], _token: str = Depends(verify_token)
):
    """Ordnet einem Buch Kategorien zu (ersetzt bestehende)."""
    book = await db.fetch_one("SELECT id FROM books WHERE id = ?", (book_id,))
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    await db.execute("DELETE FROM book_categories WHERE book_id = ?", (book_id,))
    for cat_id in kategorie_ids:
        await db.execute(
            "INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) VALUES (?, ?, 'manuell')",
            (book_id, cat_id),
        )
    await db.commit()

    return {"book_id": book_id, "kategorien": kategorie_ids}
