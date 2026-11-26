"""API-Endpunkte für Nutzerdaten (Favoriten, Lesestand, Bewertung), je Profil (BF-78): jedes Profil hat seine eigenen."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.app.api import vorhanden
from backend.app.core.auth import braucht, profil
from backend.app.core.database import db
from backend.app.familie import lesestand, sichtbar
from backend.app.familie.modelle import Geteilt, Privat, Profil
from backend.app.material import dienst as material_dienst
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


async def _ensure_user_data(book_id: int, p: Profil) -> None:
    """Stellt sicher, dass es für das Profil einen Eintrag in user_book_data gibt."""
    await db.execute("INSERT OR IGNORE INTO user_book_data (profil_id, book_id) VALUES (?, ?)", (p.id, book_id))


async def _check_book_exists(book_id: int) -> None:
    """Prüft ob das Buch existiert."""
    await vorhanden.buch(book_id)


async def _umschalten(book_id: int, p: Profil, spalte: str) -> bool:
    """Schaltet einen Schalter des Profils an diesem Buch um und gibt den neuen Wert."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id, p)
    await db.execute(f"UPDATE user_book_data SET {spalte} = 1 - COALESCE({spalte}, 0) WHERE profil_id = ? AND book_id = ?", (p.id, book_id))
    z = await db.fetch_one(f"SELECT {spalte} AS wert FROM user_book_data WHERE profil_id = ? AND book_id = ?", (p.id, book_id))
    await db.commit()
    return bool(z["wert"])


@router.patch("/{book_id}/favorit")
async def toggle_favorite(book_id: Nr, p: Profil = Depends(braucht("favoriten"))):
    """Wechselt den Favoriten-Status eines Buches."""
    return {"book_id": book_id, "ist_favorit": await _umschalten(book_id, p, "is_favorite")}


@router.patch("/{book_id}/zu-lesen")
async def toggle_to_read(book_id: Nr, p: Profil = Depends(braucht("sammeln"))):
    """Wechselt den Zum-Lesen-Status eines Buches (Lesesofa)."""
    return {"book_id": book_id, "zu_lesen": await _umschalten(book_id, p, "is_to_read")}


@router.patch("/{book_id}/gelesen")
async def toggle_read(book_id: Nr, p: Profil = Depends(braucht("gelesen"))):
    """Markiert ein Buch als fertig gelesen oder nimmt das zurück (`fertig_am`, familie/lesestand.py); `last_read_at` bleibt
    der Zeitpunkt des letzten Lesens."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id, p)
    current = await db.fetch_one("SELECT fertig_am FROM user_book_data WHERE profil_id = ? AND book_id = ?", (p.id, book_id))
    is_read = current is not None and current["fertig_am"] is not None
    await db.execute("""UPDATE user_book_data SET fertig_am = CASE WHEN ? THEN NULL ELSE datetime('now') END,
                        last_read_at = COALESCE(last_read_at, datetime('now')) WHERE profil_id = ? AND book_id = ?""",
                     (int(is_read), p.id, book_id))
    await db.commit()
    return {"book_id": book_id, "gelesen": not is_read}


@router.patch("/{book_id}/bewertung")
async def set_rating(book_id: Nr, data: RatingUpdate, p: Profil = Depends(braucht("favoriten"))):
    """Setzt die Bewertung eines Buches (0-5 Sterne)."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id, p)
    await db.execute("UPDATE user_book_data SET rating = ? WHERE profil_id = ? AND book_id = ?", (data.bewertung, p.id, book_id))
    await db.commit()
    return {"book_id": book_id, "bewertung": data.bewertung}


@router.patch("/{book_id}/leseposition")
async def set_reading_position(book_id: Nr, data: ReadingPositionUpdate, p: Profil = Depends(braucht("lesen"))):
    """Speichert die Leseposition (Seitenzahl, CFI oder Prozent); der Leser merkt sie von selbst, darum reicht Lesen (BF-78).
    Erreicht sie das Ende (familie/lesestand.py), ist das Buch fertig gelesen und bleibt es."""
    buch = await vorhanden.buch(book_id, "id, page_count")
    await _ensure_user_data(book_id, p)
    fertig = lesestand.fertig(data.position, buch["page_count"] or 0)
    await db.execute("""UPDATE user_book_data SET reading_position = ?, last_read_at = datetime('now'),
                        fertig_am = CASE WHEN ? THEN COALESCE(fertig_am, datetime('now')) ELSE fertig_am END
                        WHERE profil_id = ? AND book_id = ?""", (data.position, int(fertig), p.id, book_id))
    await db.commit()
    return {"book_id": book_id, "position": data.position}


class PrivatStand(Privat):
    material: int = 0                    # so viele Dateien Begleitmaterial gelten mit (BF-81): das Material folgt dem Buch


@router.put("/{book_id}/privat", response_model=PrivatStand)
async def set_privat(book_id: Nr, data: Privat, p: Profil = Depends(braucht("privat"))) -> PrivatStand:
    """Privat: nur dieses Profil sieht das Buch und sein Material; die anderen sehen es nicht mehr, auch nicht in Zählern (BF-78)."""
    await _check_book_exists(book_id)
    await sichtbar.privat_setzen(p.id, book_id, data.privat)
    await db.commit()
    return PrivatStand(privat=data.privat, material=(await material_dienst.anzahlen([book_id])).get(book_id, 0))


@router.put("/{book_id}/geteilt", response_model=Geteilt)
async def set_geteilt(book_id: Nr, data: Geteilt, p: Profil = Depends(profil)) -> Geteilt:
    """Das Kind teilt dieses Buch mit den Eltern; ab der Stufe Jugend sehen sie im Einblick nur Geteiltes (BF-78)."""
    await _check_book_exists(book_id)
    await _ensure_user_data(book_id, p)
    await db.execute("UPDATE user_book_data SET geteilt = ? WHERE profil_id = ? AND book_id = ?", (int(data.geteilt), p.id, book_id))
    await db.commit()
    return data


# Vorlesestelle (BF-37): Anhalten, Pause, Schlafuhr, Schließen und Abriss merken sie, damit es auf jedem Gerät an
# demselben Satz weitergeht; ist der gewählte Umfang zu Ende gelesen, wird sie gelöscht. Je Profil (BF-78).


async def _vorlesestelle(book_id: int, p: Profil) -> Vorlesestelle | None:
    zeile = await db.fetch_one("SELECT einheit, zeichen, bis_einheit, bis_zeichen, umfang, ort, gemerkt_am FROM vorlesestelle "
                               "WHERE profil_id = ? AND buch_id = ?", (p.id, book_id))
    return Vorlesestelle(**dict(zeile)) if zeile else None


@router.get("/{book_id}/vorlesestelle", response_model=Vorlesestelle | None)
async def lies_vorlesestelle(book_id: Nr, p: Profil = Depends(profil)) -> Vorlesestelle | None:
    """Wo das Vorlesen dieses Buchs stehen blieb; null, wenn nichts gemerkt ist."""
    await _check_book_exists(book_id)
    return await _vorlesestelle(book_id, p)


@router.put("/{book_id}/vorlesestelle", response_model=Vorlesestelle)
async def merke_vorlesestelle(book_id: Nr, stelle: VorlesestelleNeu, p: Profil = Depends(braucht("vorlesen"))) -> Vorlesestelle:
    """Merkt die Stelle; eine frühere desselben Buchs wird ersetzt."""
    await _check_book_exists(book_id)
    await db.execute(
        """INSERT INTO vorlesestelle (profil_id, buch_id, einheit, zeichen, bis_einheit, bis_zeichen, umfang, ort, gemerkt_am)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
           ON CONFLICT(profil_id, buch_id) DO UPDATE SET einheit = excluded.einheit, zeichen = excluded.zeichen,
             bis_einheit = excluded.bis_einheit, bis_zeichen = excluded.bis_zeichen, umfang = excluded.umfang, ort = excluded.ort,
             gemerkt_am = excluded.gemerkt_am""",
        (p.id, book_id, stelle.einheit, stelle.zeichen, stelle.bis_einheit, stelle.bis_zeichen, stelle.umfang, stelle.ort),
    )
    await db.commit()
    gemerkt = await _vorlesestelle(book_id, p)
    assert gemerkt is not None
    return gemerkt


@router.delete("/{book_id}/vorlesestelle", status_code=204)
async def vergiss_vorlesestelle(book_id: Nr, p: Profil = Depends(braucht("vorlesen"))) -> None:
    """Der gewählte Umfang ist zu Ende gelesen: nichts mehr zum Weiterlesen."""
    await _check_book_exists(book_id)
    await db.execute("DELETE FROM vorlesestelle WHERE profil_id = ? AND buch_id = ?", (p.id, book_id))
    await db.commit()
