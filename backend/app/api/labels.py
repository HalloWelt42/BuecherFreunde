"""API-Endpunkte für Etiketten (Lesezeichen mit Farbe, Name und Notiz), je Profil (BF-78). Ein Lesezeichen setzen darf jede
Stufe (so viele, wie sie erlaubt, `lesezeichen_je_buch`); Name und Notiz brauchen die Fähigkeit Etiketten."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from backend.app.api import vorhanden
from backend.app.core.auth import braucht
from backend.app.core.database import db
from backend.app.familie import rechte
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.models.grenzen import Etikett, EtikettNotiz, Farbe, Nr, Prozent, Seitenangabe, StelleOderLeer

router = APIRouter(prefix="/api", tags=["labels"])


FEHLT = "Etikett nicht gefunden"
LESEZEICHEN = braucht("lesezeichen")


def _mit_namen(p: Profil, name: str | None, note: str | None) -> None:
    if (name or note) and not rechte.darf(p, "etiketten"):
        raise HTTPException(status_code=403, detail="Name und Notiz am Lesezeichen erlaubt diese Stufe nicht")


async def _noch_frei(book_id: int, p: Profil) -> None:
    grenze = rechte.lesezeichen_je_buch(p)
    if grenze is None:
        return
    z = await db.fetch_one("SELECT COUNT(*) AS n FROM book_labels WHERE profil_id = ? AND book_id = ?", (p.id, book_id))
    if z["n"] >= grenze:
        raise HTTPException(status_code=409, detail=f"Mehr als {grenze} Lesezeichen je Buch erlaubt diese Stufe nicht")


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
async def get_labels(book_id: Nr, p: Profil = Depends(LESEZEICHEN)):
    """Alle Labels eines Buches."""
    await vorhanden.buch(book_id)
    rows = await db.fetch_all(
        "SELECT * FROM book_labels WHERE profil_id = ? AND book_id = ? ORDER BY position_percent, created_at",
        (p.id, book_id),
    )
    return [dict(r) for r in rows]


@router.post("/books/{book_id}/labels")
async def create_label(
    book_id: Nr, data: LabelCreate, p: Profil = Depends(LESEZEICHEN)
):
    """Neues Label erstellen."""
    await vorhanden.buch(book_id)
    _mit_namen(p, data.name, data.note)
    await _noch_frei(book_id, p)
    cursor = await db.execute(
        """INSERT INTO book_labels (profil_id, book_id, color, name, note, page_reference, position_percent, cfi_reference)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            p.id,
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
    label_id: Nr, data: LabelUpdate, p: Profil = Depends(LESEZEICHEN)
):
    """Label aktualisieren."""
    await vorhanden.eigenes("book_labels", label_id, p.id, FEHLT)
    _mit_namen(p, data.name, data.note)
    updates = data.model_dump(exclude_none=True)

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [label_id, p.id]
        await db.execute(
            f"UPDATE book_labels SET {set_clause} WHERE id = ? AND profil_id = ?", values
        )
        await db.commit()

    row = await db.fetch_one("SELECT * FROM book_labels WHERE id = ?", (label_id,))
    return dict(row)


@router.delete("/labels/{label_id}")
async def delete_label(label_id: Nr, p: Profil = Depends(LESEZEICHEN)):
    """Label löschen."""
    vorhanden.getroffen(await db.execute("DELETE FROM book_labels WHERE id = ? AND profil_id = ?", (label_id, p.id)), FEHLT)
    await db.commit()
    return {"message": "Etikett gelöscht"}


@router.get("/labels/search")
async def search_labels(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    p: Profil = Depends(braucht("etiketten")),
):
    """Labels durchsuchen (Name und Notiz)."""
    bedingung, werte = Sicht.von(p).bedingung("b.id")
    rows = await db.fetch_all(
        f"""SELECT l.*, b.title as book_title
           FROM book_labels l
           JOIN books b ON b.id = l.book_id
           WHERE l.profil_id = ? AND (l.name LIKE ? OR l.note LIKE ?) AND {bedingung}
           ORDER BY l.created_at DESC
           LIMIT ?""",
        (p.id, f"%{q}%", f"%{q}%", *werte, limit),
    )
    return [dict(r) for r in rows]
