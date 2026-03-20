"""API-Endpunkte fuer Notizen."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.core.auth import verify_token
from backend.app.core.database import db

router = APIRouter(prefix="/api", tags=["Notizen"])


class NoteCreate(BaseModel):
    content: str
    page_reference: str | None = None
    cfi_reference: str | None = None


class NoteUpdate(BaseModel):
    content: str | None = None
    page_reference: str | None = None
    cfi_reference: str | None = None


@router.get("/books/{book_id}/notes")
async def notizen_fuer_buch(
    book_id: int, _: str = Depends(verify_token)
):
    """Alle Notizen eines Buches."""
    rows = await db.fetch_all(
        """SELECT * FROM book_notes WHERE book_id = ?
        ORDER BY created_at DESC""",
        (book_id,),
    )
    return [dict(r) for r in rows]


@router.post("/books/{book_id}/notes")
async def erstelle_notiz(
    book_id: int, data: NoteCreate, _: str = Depends(verify_token)
):
    """Neue Notiz fuer ein Buch."""
    result = await db.execute(
        """INSERT INTO book_notes (book_id, content, page_reference, cfi_reference)
        VALUES (?, ?, ?, ?)""",
        (book_id, data.content, data.page_reference, data.cfi_reference),
    )
    return await db.fetch_one("SELECT * FROM book_notes WHERE id = ?", (result,))


@router.patch("/notes/{note_id}")
async def aktualisiere_notiz(
    note_id: int, data: NoteUpdate, _: str = Depends(verify_token)
):
    """Notiz aktualisieren."""
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Keine Aenderungen")

    sets = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [note_id]
    await db.execute(
        f"UPDATE book_notes SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        tuple(values),
    )
    return await db.fetch_one("SELECT * FROM book_notes WHERE id = ?", (note_id,))


@router.delete("/notes/{note_id}")
async def loesche_notiz(note_id: int, _: str = Depends(verify_token)):
    """Notiz loeschen."""
    await db.execute("DELETE FROM book_notes WHERE id = ?", (note_id,))
    return {"message": "Notiz geloescht"}


@router.get("/notes/recent")
async def letzte_notizen(
    limit: int = 10, _: str = Depends(verify_token)
):
    """Letzte Notizen buecheruebergreifend."""
    rows = await db.fetch_all(
        """SELECT n.*, b.title AS book_title
        FROM book_notes n
        JOIN books b ON b.id = n.book_id
        ORDER BY n.updated_at DESC
        LIMIT ?""",
        (limit,),
    )
    return [dict(r) for r in rows]
