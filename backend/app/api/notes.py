"""API-Endpunkte für Notizen, je Profil (BF-78): jedes Profil sieht und ändert nur seine eigenen."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.api import vorhanden
from backend.app.core.auth import braucht
from backend.app.core.database import db
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.models.grenzen import Notiz, Nr, Seitenangabe, StelleOderLeer

router = APIRouter(prefix="/api", tags=["Notizen"])
NOTIZEN = braucht("notizen")

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
    book_id: Nr, p: Profil = Depends(NOTIZEN)
):
    """Alle Notizen eines Buches."""
    await vorhanden.buch(book_id)
    rows = await db.fetch_all(
        """SELECT * FROM book_notes WHERE profil_id = ? AND book_id = ?
        ORDER BY created_at DESC""",
        (p.id, book_id),
    )
    return [dict(r) for r in rows]


@router.post("/books/{book_id}/notes")
async def erstelle_notiz(
    book_id: Nr, data: NoteCreate, p: Profil = Depends(NOTIZEN)
):
    """Neue Notiz für ein Buch."""
    await vorhanden.buch(book_id)
    cursor = await db.execute(
        """INSERT INTO book_notes (profil_id, book_id, content, page_reference, cfi_reference)
        VALUES (?, ?, ?, ?, ?)""",
        (p.id, book_id, data.content, data.page_reference, data.cfi_reference),
    )
    await db.commit()
    return await db.fetch_one("SELECT * FROM book_notes WHERE id = ?", (cursor.lastrowid,))


@router.patch("/notes/{note_id}")
async def aktualisiere_notiz(
    note_id: Nr, data: NoteUpdate, p: Profil = Depends(NOTIZEN)
):
    """Notiz aktualisieren."""
    await vorhanden.eigenes("book_notes", note_id, p.id, FEHLT)
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Keine Änderungen")

    sets = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [note_id, p.id]
    await db.execute(
        f"UPDATE book_notes SET {sets}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND profil_id = ?",
        tuple(values),
    )
    await db.commit()
    return await db.fetch_one("SELECT * FROM book_notes WHERE id = ?", (note_id,))


@router.delete("/notes/{note_id}")
async def loesche_notiz(note_id: Nr, p: Profil = Depends(NOTIZEN)):
    """Notiz löschen."""
    vorhanden.getroffen(await db.execute("DELETE FROM book_notes WHERE id = ? AND profil_id = ?", (note_id, p.id)), FEHLT)
    await db.commit()
    return {"message": "Notiz gelöscht"}


@router.get("/notes/recent")
async def letzte_notizen(
    limit: int = Query(10, ge=1, le=100), p: Profil = Depends(NOTIZEN)
):
    """Letzte Notizen bücherübergreifend, je Notiz ein Auszug; die ganze Notiz liefert das Buch."""
    bedingung, werte = Sicht.von(p).bedingung("b.id")
    rows = await db.fetch_all(
        f"""SELECT n.id, n.book_id, n.page_reference, n.cfi_reference, n.created_at, n.updated_at,
                  SUBSTR(n.content, 1, {AUSZUG + 1}) AS anfang, b.title AS book_title
        FROM book_notes n
        JOIN books b ON b.id = n.book_id
        WHERE n.profil_id = ? AND {bedingung}
        ORDER BY n.updated_at DESC
        LIMIT ?""",
        (p.id, *werte, limit),
    )
    return [{k: v for k, v in r.items() if k != "anfang"} | {"auszug": " ".join(r["anfang"][:AUSZUG].split()), "gekuerzt": len(r["anfang"]) > AUSZUG}
            for r in rows]
