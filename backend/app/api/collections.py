"""API-Endpunkte fuer Sammlungen."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.auth import verify_token
from backend.app.core.database import db

router = APIRouter(prefix="/api/collections", tags=["Sammlungen"])


class CollectionCreate(BaseModel):
    name: str
    description: str = ""
    color: str = "#2563eb"


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


@router.get("")
async def liste_sammlungen(_: str = Depends(verify_token)):
    """Alle Sammlungen mit Buchanzahl."""
    rows = await db.fetch_all("""
        SELECT c.*, COUNT(bc.book_id) AS buch_anzahl
        FROM collections c
        LEFT JOIN book_collections bc ON bc.collection_id = c.id
        GROUP BY c.id
        ORDER BY c.sort_order, c.name
    """)
    return [dict(r) for r in rows]


@router.post("")
async def erstelle_sammlung(
    data: CollectionCreate, _: str = Depends(verify_token)
):
    """Neue Sammlung erstellen."""
    result = await db.execute(
        """INSERT INTO collections (name, description, color)
        VALUES (?, ?, ?)""",
        (data.name, data.description, data.color),
    )
    return await db.fetch_one(
        "SELECT * FROM collections WHERE id = ?", (result,)
    )


@router.get("/{collection_id}")
async def hole_sammlung(
    collection_id: int, _: str = Depends(verify_token)
):
    """Einzelne Sammlung mit Buechern."""
    sammlung = await db.fetch_one(
        "SELECT * FROM collections WHERE id = ?", (collection_id,)
    )
    if not sammlung:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")

    buecher = await db.fetch_all("""
        SELECT b.* FROM books b
        JOIN book_collections bc ON bc.book_id = b.id
        WHERE bc.collection_id = ?
        ORDER BY bc.sort_order, b.title
    """, (collection_id,))

    result = dict(sammlung)
    result["books"] = [dict(b) for b in buecher]
    return result


@router.patch("/{collection_id}")
async def aktualisiere_sammlung(
    collection_id: int,
    data: CollectionUpdate,
    _: str = Depends(verify_token),
):
    """Sammlung aktualisieren."""
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")

    sets = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [collection_id]
    await db.execute(
        f"UPDATE collections SET {sets} WHERE id = ?", tuple(values)
    )
    return await db.fetch_one(
        "SELECT * FROM collections WHERE id = ?", (collection_id,)
    )


@router.delete("/{collection_id}")
async def loesche_sammlung(
    collection_id: int, _: str = Depends(verify_token)
):
    """Sammlung loeschen."""
    await db.execute(
        "DELETE FROM book_collections WHERE collection_id = ?",
        (collection_id,),
    )
    await db.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
    return {"message": "Sammlung geloescht"}


@router.post("/{collection_id}/books/{book_id}")
async def buch_hinzufuegen(
    collection_id: int, book_id: int, _: str = Depends(verify_token)
):
    """Buch zu Sammlung hinzufuegen."""
    await db.execute(
        """INSERT OR IGNORE INTO book_collections (book_id, collection_id)
        VALUES (?, ?)""",
        (book_id, collection_id),
    )
    return {"message": "Buch zur Sammlung hinzugefuegt"}


@router.delete("/{collection_id}/books/{book_id}")
async def buch_entfernen(
    collection_id: int, book_id: int, _: str = Depends(verify_token)
):
    """Buch aus Sammlung entfernen."""
    await db.execute(
        """DELETE FROM book_collections
        WHERE book_id = ? AND collection_id = ?""",
        (book_id, collection_id),
    )
    return {"message": "Buch aus Sammlung entfernt"}
