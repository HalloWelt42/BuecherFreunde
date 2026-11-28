"""API-Endpunkte für Textmarkierungen (Highlights) - Farbmarkierungen mit optionalem Label, je Profil (BF-78). Eine Markierung
über ein Rechteck einer gescannten Seite (Stelle `page:N:bereich:...`, BF-123) bekommt ihren Text über den Auftrag
"Markierungen lesen" (markierungen/lesen.py); die Liste nennt dazu, wo das Lesen steht (`lesen`)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.api import vorhanden
from backend.app.core.auth import braucht
from backend.app.core.database import db
from backend.app.familie.modelle import Profil
from backend.app.markierungen.lesen import Lesestand, markierungslesen
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
    lesung: Nr | None = None             # über ein Rechteck: die Lesung, die das Menü schon begonnen hat (BF-123)


class Lesewunsch(BaseModel):
    stelle: Stelle                       # page:N:bereich:x0,y0,x1,y1


def _mit_lesen(zeile, lesen: Lesestand | None) -> dict:
    """Eine Markierung, wie die Oberfläche sie bekommt: mit dem Stand ihres Lesens, wenn sie ein Rechteck ist."""
    return dict(zeile) | {"lesen": {"stand": lesen.stand, "grund": lesen.grund} if lesen else None}


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
    lesen = await markierungslesen.je_markierung(p.id, book_id)
    return [_mit_lesen(r, lesen.get(r["id"])) for r in rows]


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
    lesen = await markierungslesen.fuer_markierung(p.id, cursor.lastrowid, daten.lesung)
    return _mit_lesen(await db.fetch_one("SELECT * FROM book_highlights WHERE id = ?", (cursor.lastrowid,)), lesen)


@router.post("/books/{book_id}/lesen", response_model=Lesestand)
async def lies_bereich(book_id: Nr, daten: Lesewunsch, p: Profil = Depends(MARKIERUNGEN)):
    """Den Text eines Rechtecks lesen, das gerade gezogen ist (für das Menü daran, BF-123); der Stand kommt über GET /lesen/{id}."""
    await vorhanden.buch(book_id)
    try:
        return await markierungslesen.beginnen_fuer(p.id, book_id, daten.stelle)
    except ValueError as f:
        raise HTTPException(status_code=422, detail=str(f)) from f


@router.get("/lesen/{lesung}", response_model=Lesestand)
async def lesestand(lesung: Nr, p: Profil = Depends(MARKIERUNGEN)):
    """Wo das Lesen eines Rechtecks steht, mit dem Text, sobald er da ist."""
    stand = await markierungslesen.lesestand(p.id, lesung)
    if stand is None:
        raise HTTPException(status_code=404, detail="Lesung nicht gefunden")
    return stand


@router.post("/highlights/{highlight_id}/lesen", response_model=Lesestand)
async def lies_markierung_erneut(highlight_id: Nr, p: Profil = Depends(MARKIERUNGEN)):
    """Eine Markierung über ein Rechteck noch einmal lesen (Erneut lesen)."""
    await vorhanden.eigenes("book_highlights", highlight_id, p.id, FEHLT)
    stand = await markierungslesen.erneut(p.id, highlight_id)
    if stand is None:
        raise HTTPException(status_code=422, detail="Diese Markierung ist kein Rechteck")
    return stand


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
    zeile = await db.fetch_one("SELECT * FROM book_highlights WHERE id = ?", (highlight_id,))
    return _mit_lesen(zeile, await markierungslesen.von_markierung(p.id, highlight_id))
