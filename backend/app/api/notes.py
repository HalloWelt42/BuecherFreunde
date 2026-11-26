"""API-Endpunkte für Notizen."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.api import vorhanden
from backend.app.core.auth import verify_token
from backend.app.core.database import db
from backend.app.models.grenzen import Notiz, Nr, Seitenangabe, StelleOderLeer

router = APIRouter(prefix="/api", tags=["Notizen"])

FEHLT = "Notiz nicht gefunden"
AUSZUG = 200                              # so viele Zeichen zeigt die Liste der letzten Notizen


class NoteCreate(BaseModel):
    content: Notiz
    page_reference: Seitenangabe | None = None
    cfi_reference: StelleOderLeer | None = None


class NoteUpdate(BaseModel):
    content: Notiz | None = None
    page_reference: Seitenangabe | None = None
    cfi_reference: StelleOderLeer | None = None


@router.get("/books/{book_id}/notes")
async def notizen_fuer_buch(
    book_id: Nr, _: str = Depends(verify_token)
):
    """Alle Notizen eines Buches."""
    await vorhanden.buch(book_id)
    rows = await db.fetch_all(
        """SELECT * FROM book_notes WHERE book_id = ?
        ORDER BY created_at DESC""",
        (book_id,),
    )
    return [dict(r) for r in rows]


@router.post("/books/{book_id}/notes")
async def erstelle_notiz(
    book_id: Nr, data: NoteCreate, _: str = Depends(verify_token)
):
    """Neue Notiz für ein Buch."""
    await vorhanden.buch(book_id)
    cursor = await db.execute(
        """INSERT INTO book_notes (book_id, content, page_reference, cfi_reference)
        VALUES (?, ?, ?, ?)""",
        (book_id, data.content, data.page_reference, data.cfi_reference),
    )
    await db.commit()
    return await db.fetch_one("SELECT * FROM book_notes WHERE id = ?", (cursor.lastrowid,))


@router.patch("/notes/{note_id}")
async def aktualisiere_notiz(
    note_id: Nr, data: NoteUpdate, _: str = Depends(verify_token)
):
    """Notiz aktualisieren."""
    await vorhanden.eintrag("book_notes", note_id, FEHLT, "id")
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Keine Änderungen")

    sets = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [note_id]
    await db.execute(
        f"UPDATE book_notes SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        tuple(values),
    )
    await db.commit()
    return await db.fetch_one("SELECT * FROM book_notes WHERE id = ?", (note_id,))


@router.delete("/notes/{note_id}")
async def loesche_notiz(note_id: Nr, _: str = Depends(verify_token)):
    """Notiz löschen."""
    vorhanden.getroffen(await db.execute("DELETE FROM book_notes WHERE id = ?", (note_id,)), FEHLT)
    await db.commit()
    return {"message": "Notiz gelöscht"}


@router.get("/notes/recent")
async def letzte_notizen(
    limit: int = Query(10, ge=1, le=100), _: str = Depends(verify_token)
):
    """Letzte Notizen bücherübergreifend, je Notiz ein Auszug; die ganze Notiz liefert das Buch."""
    rows = await db.fetch_all(
        f"""SELECT n.id, n.book_id, n.page_reference, n.cfi_reference, n.created_at, n.updated_at,
                  SUBSTR(n.content, 1, {AUSZUG + 1}) AS anfang, b.title AS book_title
        FROM book_notes n
        JOIN books b ON b.id = n.book_id
        ORDER BY n.updated_at DESC
        LIMIT ?""",
        (limit,),
    )
    return [{k: v for k, v in r.items() if k != "anfang"} | {"auszug": " ".join(r["anfang"][:AUSZUG].split()), "gekuerzt": len(r["anfang"]) > AUSZUG}
            for r in rows]
