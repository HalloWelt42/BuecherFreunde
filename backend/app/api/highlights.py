"""API-Endpunkte für Textmarkierungen (Highlights) - Farbmarkierungen mit optionalem Label."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.auth import verify_token
from backend.app.core.database import db

router = APIRouter(prefix="/api", tags=["Highlights"])


class HighlightCreate(BaseModel):
    cfi_range: str
    color: str = "#FFEE58"
    text_snippet: str = ""
    label_name: str = ""
    label_note: str = ""


class HighlightUpdate(BaseModel):
    color: str | None = None
    label_name: str | None = None
    label_note: str | None = None


@router.get("/books/{book_id}/highlights")
async def liste_highlights(book_id: int, _: str = Depends(verify_token)):
    """Alle Highlights eines Buches."""
    rows = await db.fetch_all(
        "SELECT * FROM book_highlights WHERE book_id = ? ORDER BY created_at",
        (book_id,),
    )
    return [dict(r) for r in rows]


@router.post("/books/{book_id}/highlights")
async def erstelle_highlight(
    book_id: int, daten: HighlightCreate, _: str = Depends(verify_token)
):
    """Neues Highlight erstellen."""
    cursor = await db.execute(
        """INSERT INTO book_highlights (book_id, cfi_range, color, text_snippet, label_name, label_note)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (book_id, daten.cfi_range, daten.color, daten.text_snippet, daten.label_name, daten.label_note),
    )
    row = await db.fetch_one(
        "SELECT * FROM book_highlights WHERE id = ?", (cursor.lastrowid,)
    )
    return dict(row) if row else {"id": cursor.lastrowid}


@router.delete("/highlights/{highlight_id}")
async def loesche_highlight(highlight_id: int, _: str = Depends(verify_token)):
    """Highlight löschen."""
    await db.execute("DELETE FROM book_highlights WHERE id = ?", (highlight_id,))
    return {"ok": True}


@router.patch("/highlights/{highlight_id}")
async def aktualisiere_highlight(
    highlight_id: int, daten: HighlightUpdate, _: str = Depends(verify_token)
):
    """Highlight aktualisieren (Farbe, Name, Notiz)."""
    updates = []
    values = []
    if daten.color is not None:
        updates.append("color = ?")
        values.append(daten.color)
    if daten.label_name is not None:
        updates.append("label_name = ?")
        values.append(daten.label_name)
    if daten.label_note is not None:
        updates.append("label_note = ?")
        values.append(daten.label_note)
    if not updates:
        return {"ok": True}

    values.append(highlight_id)
    await db.execute(
        f"UPDATE book_highlights SET {', '.join(updates)} WHERE id = ?", values
    )

    row = await db.fetch_one(
        "SELECT * FROM book_highlights WHERE id = ?", (highlight_id,)
    )
    return dict(row) if row else {"ok": True}
