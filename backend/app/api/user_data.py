"""API-Endpunkte für Nutzerdaten (Favoriten, Lesestand, Bewertung)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api import vorhanden
from backend.app.core.auth import verify_token
from backend.app.core.database import db
from backend.app.models.grenzen import GROESSTE_ZAHL, Leseposition, Nr

router = APIRouter(prefix="/api/books", tags=["Nutzerdaten"])


class RatingUpdate(BaseModel):
    bewertung: int = Field(ge=0, le=5)


class ReadingPositionUpdate(BaseModel):
    position: Leseposition


class VorlesestelleNeu(BaseModel):
    """Wo das Vorlesen stehen blieb: Einheit der Lesequelle und Anfang des Satzes, dazu der gewählte Umfang."""

    einheit: int = Field(ge=0, le=GROESSTE_ZAHL)
    zeichen: int = Field(ge=0, le=GROESSTE_ZAHL)
    bis_einheit: int | None = Field(default=None, ge=0, le=GROESSTE_ZAHL)
    bis_zeichen: int | None = Field(default=None, ge=0, le=GROESSTE_ZAHL)
    umfang: str = Field(default="", max_length=80)
    ort: str = Field(default="", max_length=120)


class Vorlesestelle(VorlesestelleNeu):
    gemerkt_am: str


async def _ensure_user_data(book_id: int) -> None:
    """Stellt sicher, dass ein Eintrag in user_book_data existiert."""
    existing = await db.fetch_one(
        "SELECT book_id FROM user_book_data WHERE book_id = ?", (book_id,)
    )
    if not existing:
        await db.execute(
            "INSERT INTO user_book_data (book_id) VALUES (?)", (book_id,)
        )


async def _check_book_exists(book_id: int) -> None:
    """Prüft ob das Buch existiert."""
    await vorhanden.buch(book_id)


@router.patch("/{book_id}/favorit")
async def toggle_favorite(book_id: Nr, _token: str = Depends(verify_token)):
    """Wechselt den Favoriten-Status eines Buches."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id)

    current = await db.fetch_one(
        "SELECT is_favorite FROM user_book_data WHERE book_id = ?", (book_id,)
    )
    new_value = 0 if current and current["is_favorite"] else 1

    await db.execute(
        "UPDATE user_book_data SET is_favorite = ? WHERE book_id = ?",
        (new_value, book_id),
    )
    await db.commit()

    return {"book_id": book_id, "ist_favorit": bool(new_value)}


@router.patch("/{book_id}/zu-lesen")
async def toggle_to_read(book_id: Nr, _token: str = Depends(verify_token)):
    """Wechselt den Zum-Lesen-Status eines Buches."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id)

    current = await db.fetch_one(
        "SELECT is_to_read FROM user_book_data WHERE book_id = ?", (book_id,)
    )
    new_value = 0 if current and current["is_to_read"] else 1

    await db.execute(
        "UPDATE user_book_data SET is_to_read = ? WHERE book_id = ?",
        (new_value, book_id),
    )
    await db.commit()

    return {"book_id": book_id, "zu_lesen": bool(new_value)}


@router.patch("/{book_id}/gelesen")
async def toggle_read(book_id: Nr, _token: str = Depends(verify_token)):
    """Wechselt den Gelesen-Status eines Buches (setzt/löscht last_read_at)."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id)

    current = await db.fetch_one(
        "SELECT last_read_at FROM user_book_data WHERE book_id = ?", (book_id,)
    )
    is_read = current and current["last_read_at"] is not None

    if is_read:
        await db.execute(
            "UPDATE user_book_data SET last_read_at = NULL WHERE book_id = ?",
            (book_id,),
        )
    else:
        await db.execute(
            "UPDATE user_book_data SET last_read_at = datetime('now') WHERE book_id = ?",
            (book_id,),
        )
    await db.commit()

    return {"book_id": book_id, "gelesen": not is_read}


@router.patch("/{book_id}/bewertung")
async def set_rating(
    book_id: Nr, data: RatingUpdate, _token: str = Depends(verify_token)
):
    """Setzt die Bewertung eines Buches (0-5 Sterne)."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id)

    await db.execute(
        "UPDATE user_book_data SET rating = ? WHERE book_id = ?",
        (data.bewertung, book_id),
    )
    await db.commit()

    return {"book_id": book_id, "bewertung": data.bewertung}


@router.patch("/{book_id}/leseposition")
async def set_reading_position(
    book_id: Nr, data: ReadingPositionUpdate, _token: str = Depends(verify_token)
):
    """Speichert die Leseposition (Seitenzahl, CFI oder Prozent)."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id)

    await db.execute(
        "UPDATE user_book_data SET reading_position = ?, last_read_at = datetime('now') WHERE book_id = ?",
        (data.position, book_id),
    )
    await db.commit()

    return {"book_id": book_id, "position": data.position}


# Vorlesestelle (BF-37): Anhalten, Pause, Schlafuhr, Schließen und Abriss merken sie, damit es auf jedem Gerät an
# demselben Satz weitergeht; ist der gewählte Umfang zu Ende gelesen, wird sie gelöscht.


@router.get("/{book_id}/vorlesestelle", response_model=Vorlesestelle | None)
async def lies_vorlesestelle(book_id: Nr, _token: str = Depends(verify_token)) -> Vorlesestelle | None:
    """Wo das Vorlesen dieses Buchs stehen blieb; null, wenn nichts gemerkt ist."""
    await _check_book_exists(book_id)
    zeile = await db.fetch_one(
        "SELECT einheit, zeichen, bis_einheit, bis_zeichen, umfang, ort, gemerkt_am FROM vorlesestelle WHERE buch_id = ?", (book_id,)
    )
    return Vorlesestelle(**dict(zeile)) if zeile else None


@router.put("/{book_id}/vorlesestelle", response_model=Vorlesestelle)
async def merke_vorlesestelle(book_id: Nr, stelle: VorlesestelleNeu, _token: str = Depends(verify_token)) -> Vorlesestelle:
    """Merkt die Stelle; eine frühere desselben Buchs wird ersetzt."""
    await _check_book_exists(book_id)
    await db.execute(
        """INSERT INTO vorlesestelle (buch_id, einheit, zeichen, bis_einheit, bis_zeichen, umfang, ort, gemerkt_am)
           VALUES (?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
           ON CONFLICT(buch_id) DO UPDATE SET einheit = excluded.einheit, zeichen = excluded.zeichen, bis_einheit = excluded.bis_einheit,
             bis_zeichen = excluded.bis_zeichen, umfang = excluded.umfang, ort = excluded.ort, gemerkt_am = excluded.gemerkt_am""",
        (book_id, stelle.einheit, stelle.zeichen, stelle.bis_einheit, stelle.bis_zeichen, stelle.umfang, stelle.ort),
    )
    await db.commit()
    gemerkt = await lies_vorlesestelle(book_id, _token)
    assert gemerkt is not None
    return gemerkt


@router.delete("/{book_id}/vorlesestelle", status_code=204)
async def vergiss_vorlesestelle(book_id: Nr, _token: str = Depends(verify_token)) -> None:
    """Der gewählte Umfang ist zu Ende gelesen: nichts mehr zum Weiterlesen."""
    await _check_book_exists(book_id)
    await db.execute("DELETE FROM vorlesestelle WHERE buch_id = ?", (book_id,))
    await db.commit()
