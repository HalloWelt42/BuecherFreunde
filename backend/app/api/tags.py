"""API-Endpunkte fuer Tags."""

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.auth import verify_token
from backend.app.core.database import db

router = APIRouter(prefix="/api/tags", tags=["Tags"])


def _slugify(text: str) -> str:
    """Erzeugt einen URL-freundlichen Slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


class TagCreate(BaseModel):
    name: str
    color: str = "#6b7280"


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


@router.get("")
async def list_tags(_token: str = Depends(verify_token)):
    """Gibt alle Tags mit Buchanzahl zurueck."""
    return await db.fetch_all(
        """SELECT t.id, t.name, t.slug, t.color,
                  COUNT(bt.book_id) as buch_anzahl
           FROM tags t
           LEFT JOIN book_tags bt ON bt.tag_id = t.id
           GROUP BY t.id
           ORDER BY t.name"""
    )


@router.post("", status_code=201)
async def create_tag(data: TagCreate, _token: str = Depends(verify_token)):
    """Erstellt einen neuen Tag."""
    slug = _slugify(data.name)

    existing = await db.fetch_one("SELECT id FROM tags WHERE slug = ?", (slug,))
    if existing:
        raise HTTPException(status_code=409, detail="Tag existiert bereits")

    cursor = await db.execute(
        "INSERT INTO tags (name, slug, color) VALUES (?, ?, ?)",
        (data.name, slug, data.color),
    )
    await db.commit()

    return await db.fetch_one("SELECT * FROM tags WHERE id = ?", (cursor.lastrowid,))


@router.patch("/{tag_id}")
async def update_tag(tag_id: int, data: TagUpdate, _token: str = Depends(verify_token)):
    """Aktualisiert einen Tag."""
    existing = await db.fetch_one("SELECT id FROM tags WHERE id = ?", (tag_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Tag nicht gefunden")

    updates = data.model_dump(exclude_none=True)
    if "name" in updates:
        updates["slug"] = _slugify(updates["name"])

    if not updates:
        raise HTTPException(status_code=400, detail="Keine Felder zum Aktualisieren")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [tag_id]
    await db.execute(f"UPDATE tags SET {set_clause} WHERE id = ?", tuple(values))
    await db.commit()

    return await db.fetch_one("SELECT * FROM tags WHERE id = ?", (tag_id,))


@router.delete("/{tag_id}")
async def delete_tag(tag_id: int, _token: str = Depends(verify_token)):
    """Loescht einen Tag."""
    existing = await db.fetch_one("SELECT id FROM tags WHERE id = ?", (tag_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Tag nicht gefunden")

    await db.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    await db.commit()
    return {"geloescht": True, "id": tag_id}


@router.post("/{book_id}/zuordnen")
async def assign_tags(
    book_id: int, tag_ids: list[int], _token: str = Depends(verify_token)
):
    """Ordnet einem Buch Tags zu (ersetzt bestehende)."""
    book = await db.fetch_one("SELECT id FROM books WHERE id = ?", (book_id,))
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    await db.execute("DELETE FROM book_tags WHERE book_id = ?", (book_id,))
    for tag_id in tag_ids:
        await db.execute(
            "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?, ?)",
            (book_id, tag_id),
        )
    await db.commit()

    return {"book_id": book_id, "tags": tag_ids}
