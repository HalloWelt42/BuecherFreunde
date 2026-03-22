"""API-Endpunkte fuer Buch-Labels (Lesezeichen mit Farbe)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

from ..core.auth import verify_token
from ..core.database import db

router = APIRouter(prefix="/api", tags=["labels"])


class LabelCreate(BaseModel):
    color: str = Field(default="#4FC3F7", max_length=20)
    name: str = Field(default="", max_length=50)
    note: str = Field(default="")
    page_reference: str = Field(default="", max_length=50)
    position_percent: float = Field(default=0)
    cfi_reference: str = Field(default="")


class LabelUpdate(BaseModel):
    color: Optional[str] = Field(default=None, max_length=20)
    name: Optional[str] = Field(default=None, max_length=50)
    note: Optional[str] = None
    page_reference: Optional[str] = Field(default=None, max_length=50)


@router.get("/books/{book_id}/labels")
async def get_labels(book_id: int, _token: str = Depends(verify_token)):
    """Alle Labels eines Buches."""
    rows = await db.fetch_all(
        "SELECT * FROM book_labels WHERE book_id = ? ORDER BY position_percent, created_at",
        (book_id,),
    )
    return [dict(r) for r in rows]


@router.post("/books/{book_id}/labels")
async def create_label(
    book_id: int, data: LabelCreate, _token: str = Depends(verify_token)
):
    """Neues Label erstellen."""
    book = await db.fetch_one("SELECT id FROM books WHERE id = ?", (book_id,))
    if not book:
        raise HTTPException(status_code=404, detail="Buch nicht gefunden")

    cursor = await db.execute(
        """INSERT INTO book_labels (book_id, color, name, note, page_reference, position_percent, cfi_reference)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            book_id,
            data.color,
            data.name[:50],
            data.note,
            data.page_reference,
            data.position_percent,
            data.cfi_reference,
        ),
    )
    label_id = cursor.lastrowid
    await db.commit()
    row = await db.fetch_one("SELECT * FROM book_labels WHERE id = ?", (label_id,))
    return dict(row)


@router.patch("/labels/{label_id}")
async def update_label(
    label_id: int, data: LabelUpdate, _token: str = Depends(verify_token)
):
    """Label aktualisieren."""
    label = await db.fetch_one("SELECT * FROM book_labels WHERE id = ?", (label_id,))
    if not label:
        raise HTTPException(status_code=404, detail="Label nicht gefunden")

    updates = {}
    if data.color is not None:
        updates["color"] = data.color
    if data.name is not None:
        updates["name"] = data.name[:50]
    if data.note is not None:
        updates["note"] = data.note
    if data.page_reference is not None:
        updates["page_reference"] = data.page_reference

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [label_id]
        await db.execute(
            f"UPDATE book_labels SET {set_clause} WHERE id = ?", values
        )
        await db.commit()

    row = await db.fetch_one("SELECT * FROM book_labels WHERE id = ?", (label_id,))
    return dict(row)


@router.delete("/labels/{label_id}")
async def delete_label(label_id: int, _token: str = Depends(verify_token)):
    """Label loeschen."""
    label = await db.fetch_one("SELECT id FROM book_labels WHERE id = ?", (label_id,))
    if not label:
        raise HTTPException(status_code=404, detail="Label nicht gefunden")
    await db.execute("DELETE FROM book_labels WHERE id = ?", (label_id,))
    await db.commit()
    return {"message": "Label geloescht"}


@router.get("/labels/search")
async def search_labels(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
    _token: str = Depends(verify_token),
):
    """Labels durchsuchen (Name und Notiz)."""
    rows = await db.fetch_all(
        """SELECT l.*, b.title as book_title
           FROM book_labels l
           JOIN books b ON b.id = l.book_id
           WHERE l.name LIKE ? OR l.note LIKE ?
           ORDER BY l.created_at DESC
           LIMIT ?""",
        (f"%{q}%", f"%{q}%", limit),
    )
    return [dict(r) for r in rows]
