"""API-Endpunkte für Etiketten (Lesezeichen mit Farbe, Name und Notiz)."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from backend.app.api import vorhanden
from backend.app.core.auth import verify_token
from backend.app.core.database import db
from backend.app.models.grenzen import Etikett, EtikettNotiz, Farbe, Nr, Prozent, Seitenangabe, StelleOderLeer

router = APIRouter(prefix="/api", tags=["labels"])


FEHLT = "Etikett nicht gefunden"


class LabelCreate(BaseModel):
    color: Farbe = "#4FC3F7"
    name: Etikett = ""
    note: EtikettNotiz = ""
    page_reference: Seitenangabe = ""
    position_percent: Prozent = 0
    cfi_reference: StelleOderLeer = ""


class LabelUpdate(BaseModel):
    color: Farbe | None = None
    name: Etikett | None = None
    note: EtikettNotiz | None = None
    page_reference: Seitenangabe | None = None


@router.get("/books/{book_id}/labels")
async def get_labels(book_id: Nr, _token: str = Depends(verify_token)):
    """Alle Labels eines Buches."""
    await vorhanden.buch(book_id)
    rows = await db.fetch_all(
        "SELECT * FROM book_labels WHERE book_id = ? ORDER BY position_percent, created_at",
        (book_id,),
    )
    return [dict(r) for r in rows]


@router.post("/books/{book_id}/labels")
async def create_label(
    book_id: Nr, data: LabelCreate, _token: str = Depends(verify_token)
):
    """Neues Label erstellen."""
    await vorhanden.buch(book_id)
    cursor = await db.execute(
        """INSERT INTO book_labels (book_id, color, name, note, page_reference, position_percent, cfi_reference)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            book_id,
            data.color,
            data.name,
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
    label_id: Nr, data: LabelUpdate, _token: str = Depends(verify_token)
):
    """Label aktualisieren."""
    await vorhanden.eintrag("book_labels", label_id, FEHLT, "id")
    updates = data.model_dump(exclude_none=True)

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
async def delete_label(label_id: Nr, _token: str = Depends(verify_token)):
    """Label löschen."""
    vorhanden.getroffen(await db.execute("DELETE FROM book_labels WHERE id = ?", (label_id,)), FEHLT)
    await db.commit()
    return {"message": "Etikett gelöscht"}


@router.get("/labels/search")
async def search_labels(
    q: str = Query(..., min_length=1, max_length=200),
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
