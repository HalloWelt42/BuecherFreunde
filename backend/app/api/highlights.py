"""API-Endpunkte für Textmarkierungen (Highlights) - Farbmarkierungen mit optionalem Label, je Profil (BF-78)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.api import vorhanden
from backend.app.core.auth import braucht
from backend.app.core.database import db
from backend.app.familie.modelle import Profil
from backend.app.models.grenzen import Etikett, EtikettNotiz, Farbe, Nr, Stelle, Textauszug

router = APIRouter(prefix="/api", tags=["Highlights"])
MARKIERUNGEN = braucht("markierungen")

FEHLT = "Markierung nicht gefunden"


class HighlightCreate(BaseModel):
    cfi_range: Stelle
    color: Farbe = "#FFEE58"
    text_snippet: Textauszug = ""
    label_name: Etikett = ""
    label_note: EtikettNotiz = ""


class HighlightUpdate(BaseModel):
    color: Farbe | None = None
    label_name: Etikett | None = None
    label_note: EtikettNotiz | None = None


@router.get("/books/{book_id}/highlights")
async def liste_highlights(book_id: Nr, p: Profil = Depends(MARKIERUNGEN)):
    """Alle Highlights eines Buches."""
    await vorhanden.buch(book_id)
    rows = await db.fetch_all(
        "SELECT * FROM book_highlights WHERE profil_id = ? AND book_id = ? ORDER BY created_at",
        (p.id, book_id),
    )
    return [dict(r) for r in rows]


@router.post("/books/{book_id}/highlights")
async def erstelle_highlight(
    book_id: Nr, daten: HighlightCreate, p: Profil = Depends(MARKIERUNGEN)
):
    """Neues Highlight erstellen."""
    await vorhanden.buch(book_id)
    cursor = await db.execute(
        """INSERT INTO book_highlights (profil_id, book_id, cfi_range, color, text_snippet, label_name, label_note)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (p.id, book_id, daten.cfi_range, daten.color, daten.text_snippet, daten.label_name, daten.label_note),
    )
    await db.commit()
    return await db.fetch_one("SELECT * FROM book_highlights WHERE id = ?", (cursor.lastrowid,))


@router.delete("/highlights/{highlight_id}")
async def loesche_highlight(highlight_id: Nr, p: Profil = Depends(MARKIERUNGEN)):
    """Highlight löschen."""
    vorhanden.getroffen(await db.execute("DELETE FROM book_highlights WHERE id = ? AND profil_id = ?", (highlight_id, p.id)), FEHLT)
    await db.commit()
    return {"ok": True}


@router.patch("/highlights/{highlight_id}")
async def aktualisiere_highlight(
    highlight_id: Nr, daten: HighlightUpdate, p: Profil = Depends(MARKIERUNGEN)
):
    """Highlight aktualisieren (Farbe, Name, Notiz)."""
    await vorhanden.eigenes("book_highlights", highlight_id, p.id, FEHLT)
    updates = daten.model_dump(exclude_none=True)
    if updates:
        await db.execute(
            f"UPDATE book_highlights SET {', '.join(f'{k} = ?' for k in updates)} WHERE id = ?", (*updates.values(), highlight_id)
        )
        await db.commit()
    return await db.fetch_one("SELECT * FROM book_highlights WHERE id = ?", (highlight_id,))
