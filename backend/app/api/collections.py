"""API-Endpunkte für Sammlungen: anlegen und pflegen, Bücher zuordnen und ordnen (BF-67), ab wann eine Sammlung in der
Bücherliste ein Eintrag ist, und Sammlungen finden (BF-66, services/sammlungsfinder.py). Bücher und Zahlen nur, wie das Profil sie
sieht (BF-78); ein Kind sieht nur Sammlungen mit freigegebenen Büchern."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.api import vorhanden
from backend.app.api.books import buecher_mit_nummern
from backend.app.core.auth import braucht, profil
from backend.app.core.database import db
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.models.book import GATTUNGEN, TYPEN, BookListItem
from backend.app.models.grenzen import AUSWAHL_HOECHSTENS, AlsEintragAb, Band, Farbe, Nr, Sammlungsbeschreibung, Sammlungsname
from backend.app.services import sammlungen, vorschlaege
from backend.app.services.buchliste import BANDORDNUNG
from backend.app.services.sammlungsfinder import SuchStand, sammlungsfinder

router = APIRouter(prefix="/api/collections", tags=["Sammlungen"])

FEHLT = "Sammlung nicht gefunden"
BEARBEITEN = braucht("bearbeiten")
FARBE_VORGABE = "#2563eb"


class CollectionCreate(BaseModel):
    name: Sammlungsname
    description: Sammlungsbeschreibung = ""
    color: Farbe = FARBE_VORGABE


class CollectionUpdate(BaseModel):
    name: Sammlungsname | None = None
    description: Sammlungsbeschreibung | None = None
    color: Farbe | None = None


class BuchZuordnung(BaseModel):
    band_nummer: Band = ""


class SammlungEinstellungen(BaseModel):
    als_eintrag_ab: AlsEintragAb                # ab so vielen Büchern unter dem Filter ist eine Sammlung ein Eintrag


class Reihenfolge(BaseModel):
    book_ids: list[Nr] = Field(max_length=AUSWAHL_HOECHSTENS)


class VorschlagAnpassen(BaseModel):
    name: Sammlungsname | None = None           # ohne: der Name des Vorschlags
    book_ids: list[Nr] | None = Field(default=None, max_length=AUSWAHL_HOECHSTENS)   # ohne: alle Bücher des Vorschlags


class VorschlagBuch(BookListItem):
    band: str                                   # die erkannte Bandnummer


class Vorschlag(BaseModel):
    id: int
    name: str
    autor: str
    anzahl: int                                 # Bücher, die noch in keiner Sammlung sind
    wege: list[str]                             # wie die Reihe gefunden wurde, kurze deutsche Sätze
    ki: str                                     # Satz der KI, oder warum sie nicht geprüft hat
    ki_geprueft: bool
    ki_zweifel: bool                            # die KI hält es für keine Reihe; du entscheidest
    buecher: list[VorschlagBuch]


class Verworfen(BaseModel):
    id: int
    stand: Literal["verworfen"] = "verworfen"


# --- Systemtypen ---

@router.get("/typen")
async def liste_typen(_: Profil = Depends(profil)):
    """Gibt die verfügbaren Systemtypen zurück."""
    return TYPEN


@router.get("/gattungen")
async def liste_gattungen(_: Profil = Depends(profil)):
    """Die festen Gattungen eines Buchs, in der Reihenfolge, in der sie angeboten werden (BF-59)."""
    return GATTUNGEN


# --- Einstellungen und Sammlungen finden (vor den Wegen mit Nummer) ---

@router.get("/einstellungen", response_model=SammlungEinstellungen)
async def hole_einstellungen(_: Profil = Depends(profil)) -> SammlungEinstellungen:
    return SammlungEinstellungen(als_eintrag_ab=await sammlungen.als_eintrag_ab())


@router.put("/einstellungen", response_model=SammlungEinstellungen)
async def setze_einstellungen(data: SammlungEinstellungen, _: Profil = Depends(braucht("einstellungen"))) -> SammlungEinstellungen:
    await sammlungen.als_eintrag_ab_setzen(data.als_eintrag_ab)
    return data


@router.get("/vorschlaege", response_model=list[Vorschlag])
async def liste_vorschlaege(p: Profil = Depends(BEARBEITEN)) -> list[Vorschlag]:
    """Die offenen Vorschläge, die größten zuerst; je Buch die erkannte Bandnummer. Bücher, die das Profil nicht sieht, fehlen."""
    offen = await vorschlaege.offene()
    buecher = await buecher_mit_nummern([b.buch_id for v in offen for b in v.baende], p)
    liste = []
    for v in offen:
        baende = [b for b in v.baende if b.buch_id in buecher]
        if baende:
            liste.append(Vorschlag(id=v.id, name=v.name, autor=v.autor, anzahl=len(baende), wege=v.wege, ki=v.ki, ki_geprueft=v.ki_geprueft,
                                   ki_zweifel=v.ki_zweifel, buecher=[VorschlagBuch(**buecher[b.buch_id].model_dump(), band=b.band) for b in baende]))
    return liste


@router.post("/vorschlaege/suchen", response_model=SuchStand, dependencies=[Depends(braucht("ki"))])
async def suche_vorschlaege(_: Profil = Depends(BEARBEITEN)) -> SuchStand:
    """Startet die Suche im Hintergrund; läuft schon eine, bleibt es bei ihr."""
    sammlungsfinder.starten()
    return await sammlungsfinder.stand()


@router.get("/vorschlaege/stand", response_model=SuchStand)
async def stand_vorschlaege(_: Profil = Depends(BEARBEITEN)) -> SuchStand:
    return await sammlungsfinder.stand()


def _vorschlagsfehler(f: Exception) -> HTTPException:
    status = 404 if isinstance(f, vorschlaege.VorschlagFehlt) else 409 if isinstance(f, vorschlaege.NichtOffen) else 400
    return HTTPException(status_code=status, detail=str(f))


@router.post("/vorschlaege/{vorschlag_id}/anlegen")
async def lege_vorschlag_an(vorschlag_id: Nr, data: VorschlagAnpassen = VorschlagAnpassen(), p: Profil = Depends(BEARBEITEN)):
    """Legt die Sammlung an (Name und Bücher anpassbar), mit den erkannten Bandnummern; gibt sie mit ihren Büchern."""
    try:
        sammlung = await vorschlaege.anlegen(vorschlag_id, data.name, data.book_ids, FARBE_VORGABE)
    except (vorschlaege.VorschlagFehlt, vorschlaege.NichtOffen, vorschlaege.FalscheAuswahl) as f:
        raise _vorschlagsfehler(f) from None
    return await hole_sammlung(sammlung, p)


@router.post("/vorschlaege/{vorschlag_id}/verwerfen", response_model=Verworfen)
async def verwirf_vorschlag(vorschlag_id: Nr, _: Profil = Depends(BEARBEITEN)) -> Verworfen:
    """Der Vorschlag kommt nie wieder, auch nicht in einem späteren Lauf."""
    try:
        await vorschlaege.verwerfen(vorschlag_id)
    except (vorschlaege.VorschlagFehlt, vorschlaege.NichtOffen) as f:
        raise _vorschlagsfehler(f) from None
    return Verworfen(id=vorschlag_id)


# --- Sammlungen CRUD ---

@router.get("")
async def liste_sammlungen(p: Profil = Depends(profil)):
    """Alle Sammlungen mit der Zahl der Bücher, die das Profil sieht; ein Kind nur die mit freigegebenen. Eine Sammlung,
    deren Bücher alle für dieses Profil unsichtbar sind (etwa nur private Bücher eines anderen), fehlt für alle; eine leere
    Sammlung ohne Bücher bleibt für Erwachsene sichtbar, damit man sie füllen kann."""
    bedingung, werte = Sicht.von(p).bedingung("b.id")
    leer_erlaubt = "" if p.kind else " OR NOT EXISTS (SELECT 1 FROM books x WHERE x.sammlung_id = c.id)"
    rows = await db.fetch_all(f"""
        SELECT c.*, COUNT(b.id) AS buch_anzahl
        FROM collections c
        LEFT JOIN books b ON b.sammlung_id = c.id AND {bedingung}
        GROUP BY c.id
        HAVING COUNT(b.id) > 0{leer_erlaubt}
        ORDER BY c.sort_order, c.name
    """, werte)
    return [dict(r) for r in rows]


@router.post("")
async def erstelle_sammlung(
    data: CollectionCreate, _: Profil = Depends(BEARBEITEN)
):
    """Neue Sammlung erstellen."""
    cursor = await db.execute(
        """INSERT INTO collections (name, description, color)
        VALUES (?, ?, ?)""",
        (data.name, data.description, data.color),
    )
    await db.commit()
    return await db.fetch_one(
        "SELECT * FROM collections WHERE id = ?", (cursor.lastrowid,)
    )


@router.get("/{collection_id}")
async def hole_sammlung(
    collection_id: Nr, p: Profil = Depends(profil)
):
    """Einzelne Sammlung mit den Büchern, die das Profil sieht; ein Kind sieht eine ohne freigegebene Bücher nicht."""
    sammlung = await vorhanden.eintrag("collections", collection_id, FEHLT)
    bedingung, werte = Sicht.von(p).bedingung("b.id")
    buecher = await db.fetch_all(f"""
        SELECT b.id, b.title, b.author, b.isbn, b.file_format, b.cover_path, b.year, b.band_nummer
        FROM books b
        WHERE b.sammlung_id = ? AND {bedingung}
        ORDER BY {BANDORDNUNG.sql()}
    """, (collection_id, *werte))
    if not buecher and (p.kind or await db.fetch_one("SELECT 1 FROM books WHERE sammlung_id = ? LIMIT 1", (collection_id,))):
        raise HTTPException(status_code=404, detail=FEHLT)              # Bücher da, aber keins für dieses Profil sichtbar

    result = dict(sammlung)
    result["books"] = [dict(b) for b in buecher]
    return result


@router.patch("/{collection_id}")
async def aktualisiere_sammlung(
    collection_id: Nr,
    data: CollectionUpdate,
    _: Profil = Depends(BEARBEITEN),
):
    """Sammlung aktualisieren."""
    await vorhanden.eintrag("collections", collection_id, FEHLT, "id")
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Keine Änderungen")

    sets = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [collection_id]
    await db.execute(
        f"UPDATE collections SET {sets} WHERE id = ?", tuple(values)
    )
    await db.commit()
    return await db.fetch_one(
        "SELECT * FROM collections WHERE id = ?", (collection_id,)
    )


@router.delete("/{collection_id}")
async def loesche_sammlung(
    collection_id: Nr, _: Profil = Depends(braucht("loeschen"))
):
    """Sammlung löschen. Setzt sammlung_id bei zugehörigen Büchern auf NULL."""
    await vorhanden.eintrag("collections", collection_id, FEHLT, "id")
    await db.execute(
        "UPDATE books SET sammlung_id = NULL, band_nummer = '' WHERE sammlung_id = ?",
        (collection_id,),
    )
    await db.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
    await db.commit()
    return {"message": "Sammlung gelöscht"}


@router.put("/{collection_id}/reihenfolge")
async def setze_reihenfolge(collection_id: Nr, data: Reihenfolge, p: Profil = Depends(BEARBEITEN)):
    """Bandnummern 1 bis n in der gegebenen Reihenfolge; nicht genannte Bücher der Sammlung folgen in ihrer bisherigen."""
    await vorhanden.eintrag("collections", collection_id, FEHLT, "id")
    try:
        await sammlungen.reihenfolge_setzen(collection_id, data.book_ids)
    except sammlungen.NichtInDerSammlung as f:
        raise HTTPException(status_code=400, detail=str(f)) from None
    return await hole_sammlung(collection_id, p)


# --- Buch-Zuordnung (1:1) ---

@router.post("/{collection_id}/buch/{book_id}")
async def buch_zuordnen(
    collection_id: Nr,
    book_id: Nr,
    data: BuchZuordnung = BuchZuordnung(),
    _: Profil = Depends(BEARBEITEN),
):
    """Buch einer Sammlung zuordnen (ersetzt vorherige Zuordnung)."""
    await vorhanden.eintrag("collections", collection_id, FEHLT, "id")
    await vorhanden.buch(book_id)

    await db.execute(
        "UPDATE books SET sammlung_id = ?, band_nummer = ? WHERE id = ?",
        (collection_id, data.band_nummer, book_id),
    )
    await db.commit()
    return {"message": "Buch zur Sammlung zugeordnet"}


@router.delete("/{collection_id}/buch/{book_id}")
async def buch_aus_sammlung(
    collection_id: Nr, book_id: Nr, _: Profil = Depends(BEARBEITEN)
):
    """Buch aus Sammlung entfernen."""
    c = await db.execute(
        "UPDATE books SET sammlung_id = NULL, band_nummer = '' WHERE id = ? AND sammlung_id = ?",
        (book_id, collection_id),
    )
    vorhanden.getroffen(c, "Das Buch gehört nicht zu dieser Sammlung")
    await db.commit()
    return {"message": "Buch aus Sammlung entfernt"}
