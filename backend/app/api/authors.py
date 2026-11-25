"""API-Endpunkte für Autoren."""

import json
import math
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from backend.app.core.auth import verify_token, verify_token_inhalt
from backend.app.core.database import db
from backend.app.models.author import (
    AuthorListItem,
    AuthorListResponse,
    AuthorResponse,
    AuthorUpdate,
)
from backend.app.quellen import autoren as quellen
from backend.app.quellen.autoren import Autorauskunft
from backend.app.quellen.modelle import Autorfrage
from backend.app.quellen.vorrang import hintergrund
from backend.app.services import autoren_uebernahme as uebernahme
from backend.app.services.anhalten import Anhalter
from backend.app.services.autoren_uebernahme import OHNE_EINTRAG
from backend.app.services.autoren_uebernahme import slug as _slugify
from backend.app.services.autorennamen import zerlegen

router = APIRouter(prefix="/api/authors", tags=["Autoren"])


@router.get("", response_model=AuthorListResponse)
async def list_authors(
    _token: str = Depends(verify_token),
    seite: int = Query(1, ge=1),
    pro_seite: int = Query(24, ge=1, le=100),
    suche: str | None = Query(None, description="Namenssuche"),
    sortierung: str = Query("name", description="Sortierung: name, bücher, datum"),
    richtung: str = Query("asc", description="asc oder desc"),
    hat_foto: bool | None = Query(None, description="Nur mit/ohne Foto"),
    hat_bio: bool | None = Query(None, description="Nur mit/ohne Biografie"),
):
    """Listet Autoren paginiert und filterbar auf."""
    conditions = []
    params: list = []

    if suche:
        conditions.append("a.name LIKE ?")
        params.append(f"%{suche}%")

    if hat_foto is not None:
        if hat_foto:
            conditions.append("a.photo_path != ''")
        else:
            conditions.append("(a.photo_path IS NULL OR a.photo_path = '')")

    if hat_bio is not None:
        if hat_bio:
            conditions.append("a.biography != ''")
        else:
            conditions.append("(a.biography IS NULL OR a.biography = '')")

    where = " AND ".join(conditions) if conditions else "1=1"

    sort_map = {
        "name": "a.name",
        "datum": "a.created_at",
        "buecher": "book_count",
    }
    sort_col = sort_map.get(sortierung, "a.name")
    sort_dir = "DESC" if richtung.lower() == "desc" else "ASC"

    # Zählen
    count_sql = f"SELECT COUNT(*) as total FROM authors a WHERE {where}"
    count_row = await db.fetch_one(count_sql, tuple(params))
    gesamt = count_row["total"] if count_row else 0

    # Abfrage mit Buchanzahl
    offset = (seite - 1) * pro_seite
    select_sql = f"""
        SELECT a.id, a.name, a.slug, a.photo_path, a.birth_year, a.death_year,
               a.nationality, a.created_at,
               (SELECT COUNT(*) FROM book_authors ba WHERE ba.author_id = a.id) as book_count
        FROM authors a
        WHERE {where}
        ORDER BY {sort_col} {sort_dir}
        LIMIT ? OFFSET ?
    """
    rows = await db.fetch_all(select_sql, tuple(params) + (pro_seite, offset))

    autoren = [AuthorListItem(**row) for row in rows]

    return AuthorListResponse(
        autoren=autoren,
        gesamt=gesamt,
        seite=seite,
        pro_seite=pro_seite,
        seiten_gesamt=math.ceil(gesamt / pro_seite) if gesamt > 0 else 0,
    )


# --- Statische Routen (MÜSSEN vor /{author_id} stehen) ---

# Globaler Status für laufenden Batch-Scan
_batch_scan_status = {
    "laeuft": False,
    "fortschritt": {},
}
_abgleich = Anhalter()


@router.get("/statistik/uebersicht")
async def author_stats(_token: str = Depends(verify_token)):
    """Gibt Statistiken über Autoren zurück."""
    total = await db.fetch_one("SELECT COUNT(*) as total FROM authors")
    mit_bio = await db.fetch_one(
        "SELECT COUNT(*) as total FROM authors WHERE biography != ''"
    )
    mit_foto = await db.fetch_one(
        "SELECT COUNT(*) as total FROM authors WHERE photo_path != ''"
    )
    mit_wikidata = await db.fetch_one(
        "SELECT COUNT(*) as total FROM authors WHERE wikidata_id != ''"
    )
    mit_normdatei = await db.fetch_one(
        "SELECT COUNT(*) as total FROM autor_verweis WHERE art = 'gnd'"
    )
    mit_eintrag = await db.fetch_one(f"SELECT COUNT(*) as total FROM authors a WHERE NOT ({OHNE_EINTRAG})")

    return {
        "gesamt": total["total"] if total else 0,
        "mit_biografie": mit_bio["total"] if mit_bio else 0,
        "mit_foto": mit_foto["total"] if mit_foto else 0,
        "mit_wikidata": mit_wikidata["total"] if mit_wikidata else 0,
        "mit_normdatei": mit_normdatei["total"] if mit_normdatei else 0,
        "mit_eintrag": mit_eintrag["total"] if mit_eintrag else 0,
    }


@router.post("/resync")
async def resync_authors(_token: str = Depends(verify_token)):
    """Synchronisiert die Autoren-Tabelle komplett neu aus books.author.

    Autoren mit Eintrag (Lexikon oder Normdatei, mit Biografie und Foto) werden beibehalten.
    Alle anderen werden gelöscht und aus den Buch-Strings neu angelegt.
    """
    # Angereicherte Autoren sichern (haben wertvolle Daten)
    enriched = await db.fetch_all(f"SELECT a.id, a.name, a.slug FROM authors a WHERE NOT ({OHNE_EINTRAG})")
    enriched_slugs = {a["slug"]: a["id"] for a in enriched}

    # Nicht-angereicherte Autoren und deren Verknüpfungen löschen
    await db.execute(f"DELETE FROM book_authors WHERE author_id IN (SELECT a.id FROM authors a WHERE {OHNE_EINTRAG})")
    await db.execute(f"DELETE FROM authors WHERE id IN (SELECT a.id FROM authors a WHERE {OHNE_EINTRAG})")

    # Alle Bücher durchgehen und Autoren neu anlegen
    books = await db.fetch_all(
        "SELECT id, author FROM books WHERE author IS NOT NULL AND author != ''"
    )

    neu_angelegt = 0
    verknuepft = 0

    for book in books:
        namen = zerlegen(book["author"])
        for i, name in enumerate(namen):
            name = name.strip()
            if not name or len(name) < 2:
                continue

            slug = _slugify(name)
            if not slug:
                continue

            # Prüfe ob bereits angereichert vorhanden
            if slug in enriched_slugs:
                author_id = enriched_slugs[slug]
            else:
                existing = await db.fetch_one("SELECT id FROM authors WHERE slug = ?", (slug,))
                if existing:
                    author_id = existing["id"]
                else:
                    cursor = await db.execute(
                        "INSERT INTO authors (name, slug) VALUES (?, ?)",
                        (name, slug),
                    )
                    author_id = cursor.lastrowid
                    neu_angelegt += 1

            await db.execute(
                "INSERT OR IGNORE INTO book_authors (book_id, author_id, sort_order) VALUES (?, ?, ?)",
                (book["id"], author_id, i),
            )
            verknuepft += 1

    await db.commit()

    # Verwaiste Autoren aufräumen
    await db.execute(f"DELETE FROM authors WHERE id IN (SELECT a.id FROM authors a WHERE {OHNE_EINTRAG} AND a.id NOT IN (SELECT DISTINCT author_id FROM book_authors))")
    await db.commit()

    total = await db.fetch_one("SELECT COUNT(*) as n FROM authors")

    return {
        "neu_angelegt": neu_angelegt,
        "verknuepft": verknuepft,
        "beibehalten": len(enriched),
        "gesamt": total["n"] if total else 0,
        "buecher_verarbeitet": len(books),
    }


async def _offene(hoechstens: int | None = None, nur_ohne_eintrag: bool = True) -> list[dict]:
    """Autoren, zu denen noch ein Eintrag gesucht werden kann, die mit den meisten Büchern zuerst."""
    return await db.fetch_all(
        f"""SELECT a.id, a.name, a.photo_path,
                   (SELECT COUNT(*) FROM book_authors ba WHERE ba.author_id = a.id) as book_count
            FROM authors a WHERE {OHNE_EINTRAG if nur_ohne_eintrag else '1=1'}
            ORDER BY book_count DESC, a.id LIMIT ?""",
        (hoechstens or -1,),
    )


@router.post("/scanner/starten")
async def scan_authors(_token: str = Depends(verify_token)):
    """Findet Autoren ohne angereicherte Daten und gibt sie als Liste zurück."""
    rows = await _offene(100)
    return {"offene_autoren": [{k: r[k] for k in ("id", "name", "book_count")} for r in rows], "anzahl": len(rows)}


@router.post("/scanner/batch")
async def start_batch_scan(_token: str = Depends(verify_token)):
    """Die Autoren, die der Batch-Scan bearbeiten würde."""
    if _batch_scan_status["laeuft"]:
        raise HTTPException(status_code=409, detail="Batch-Scan läuft bereits")
    rows = await _offene()
    return {"autoren": [{k: r[k] for k in ("id", "name", "book_count")} for r in rows], "anzahl": len(rows)}


@router.post("/scanner/abbrechen")
async def cancel_batch_scan(_token: str = Depends(verify_token)):
    """Bricht den laufenden Batch-Scan ab, auch mitten im Warten auf eine Quelle."""
    if _batch_scan_status["laeuft"]:
        _abgleich.halte()
        return {"abgebrochen": True}
    return {"abgebrochen": False, "grund": "Kein Scan aktiv"}


async def _frage_zu(autor_id: int, name: str) -> Autorfrage:
    """Name, Buchtitel und ISBN des Autors; an ihnen misst sich, ob ein Eintrag passt."""
    buecher = await db.fetch_all(
        "SELECT b.title, b.isbn FROM books b JOIN book_authors ba ON ba.book_id = b.id WHERE ba.author_id = ?",
        (autor_id,),
    )
    return Autorfrage(name=name, titel=[b["title"] for b in buecher], isbns=[b["isbn"] for b in buecher if b["isbn"]])


def _kurzfassung(vorschlag: dict) -> dict:
    """Was der Fortschritt von einem Vorschlag zeigt."""
    felder = ("name", "wikidata_id", "birth_year", "death_year", "nationality", "photo_url", "wikipedia_url", "konfidenz", "score", "verweise")
    return {k: vorschlag[k] for k in felder} | {"biography": vorschlag["biography"][:200]}


async def _suche(autor: dict) -> Autorauskunft:
    return await quellen.suche(await _frage_zu(autor["id"], autor["name"]))


async def _ein_autor(autor: dict, auto_uebernehmen: bool) -> dict:
    """Das Ergebnis eines Autors im Abgleich; sichere Treffer auf Wunsch gleich übernommen. Fehlt eine Quelle, wird nichts
    Halbes übernommen."""
    antwort = await _suche(autor)
    if antwort.hinweise:
        return {"typ": "ruht" if antwort.ruht else "fehler", "fehler": ". ".join(antwort.hinweise)}
    if antwort.angaben is None:
        return {"typ": "nicht_gefunden"}
    vorschlag = antwort.angaben.model_dump()
    grund = await uebernahme.sicher_uebernehmen(autor["id"], vorschlag) if auto_uebernehmen and antwort.angaben.konfidenz == "hoch" else "nicht sicher genug"
    return {"typ": "gefunden", "vorschlag": _kurzfassung(vorschlag), "uebernommen": not grund, "grund": grund}


async def _im_hintergrund(autor: dict, auto_uebernehmen: bool) -> dict:
    """Ein Autor mit niedrigem Vorrang; ein Fehler hält die übrigen nicht auf."""
    try:
        with hintergrund():
            return await _abgleich.bis(_ein_autor(autor, auto_uebernehmen)) or {"typ": "abgebrochen"}
    except Exception as e:                                   # noqa: BLE001
        return {"typ": "fehler", "fehler": str(e)}


async def _abgleichen(autoren: list[dict], auto_uebernehmen: bool) -> AsyncIterator[dict]:
    """Ein Ereignis je Schritt. Ruht eine Quelle, endet der Lauf mit ihrem Grund."""
    gesamt = len(autoren)
    stand = _batch_scan_status["fortschritt"] = {"gesamt": gesamt, "bearbeitet": 0, "gefunden": 0, "nicht_gefunden": 0, "fehler": 0}
    yield {"typ": "start", "gesamt": gesamt}
    for i, autor in enumerate(autoren, 1):
        kopf = {"autor_id": autor["id"], "name": autor["name"], "index": i, "gesamt": gesamt}
        yield {"typ": "suche", **kopf}
        ereignis = await _im_hintergrund(autor, auto_uebernehmen)
        if ereignis["typ"] in ("abgebrochen", "ruht"):
            yield {"typ": ereignis["typ"], "bearbeitet": i - 1, "gesamt": gesamt, "grund": ereignis.get("fehler", "")}
            return
        stand[ereignis["typ"]] += 1
        stand["bearbeitet"] = i
        yield {**ereignis, **kopf}
    yield {"typ": "fertig", **stand}


@router.get("/scanner/events")
async def batch_scan_events(
    _token: str = Depends(verify_token_inhalt),
    nur_ohne_wikidata: bool = Query(True, description="Nur Autoren ohne Eintrag in Lexikon oder Normdatei"),
    auto_uebernehmen: bool = Query(False, description="Hohe Konfidenz automatisch übernehmen"),
):
    """SSE-Endpunkt für den Batch-Scan. Streamt Fortschritt pro Autor."""
    if _batch_scan_status["laeuft"]:
        raise HTTPException(status_code=409, detail="Batch-Scan läuft bereits")
    autoren = await _offene(nur_ohne_eintrag=nur_ohne_wikidata)

    async def event_generator():
        _batch_scan_status["laeuft"] = True
        _abgleich.beginne()
        try:
            async for ereignis in _abgleichen(autoren, auto_uebernehmen):
                yield _sse_event(ereignis)
        finally:
            _batch_scan_status["laeuft"] = False

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/verwaist")
async def delete_orphaned_authors(_token: str = Depends(verify_token)):
    """Löscht alle Autoren ohne verknüpfte Bücher."""
    rows = await db.fetch_all("""
        SELECT a.id, a.name FROM authors a
        WHERE NOT EXISTS (
            SELECT 1 FROM book_authors ba WHERE ba.author_id = a.id
        )
    """)

    if not rows:
        return {"gelöscht": 0, "autoren": []}

    ids = [r["id"] for r in rows]
    namen = [r["name"] for r in rows]

    placeholders = ",".join("?" * len(ids))
    await db.execute(f"DELETE FROM authors WHERE id IN ({placeholders})", tuple(ids))
    await db.commit()

    return {"gelöscht": len(ids), "autoren": namen}


# --- Dynamische Routen (/{author_id}) ---

@router.get("/{author_id}", response_model=AuthorResponse)
async def get_author(author_id: int, _token: str = Depends(verify_token)):
    """Gibt die vollständigen Details eines Autors zurück."""
    author = await db.fetch_one(
        "SELECT * FROM authors WHERE id = ?", (author_id,)
    )
    if not author:
        raise HTTPException(status_code=404, detail="Autor nicht gefunden")

    # Bücher des Autors laden
    books = await db.fetch_all(
        """SELECT b.id, b.title, b.year, b.file_format, b.cover_path, b.isbn,
                  ba.role
           FROM books b
           JOIN book_authors ba ON ba.book_id = b.id
           WHERE ba.author_id = ?
           ORDER BY b.year DESC NULLS LAST, b.title ASC""",
        (author_id,),
    )

    # Werkeliste laden
    werke = await db.fetch_all(
        """SELECT aw.id, aw.wikidata_id, aw.titel, aw.book_id
           FROM author_works aw
           WHERE aw.author_id = ?
           ORDER BY aw.titel""",
        (author_id,),
    )

    return AuthorResponse(**author, books=books, werke=[dict(w) for w in werke], verweise=await uebernahme.verweise(author_id))


@router.patch("/{author_id}")
async def update_author(
    author_id: int, data: AuthorUpdate, _token: str = Depends(verify_token)
):
    """Aktualisiert einen Autor."""
    existing = await db.fetch_one(
        "SELECT id FROM authors WHERE id = ?", (author_id,)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Autor nicht gefunden")

    updates = {}
    for key, value in data.model_dump(exclude_unset=True).items():
        updates[key] = value

    # Name geändert -> Slug neu generieren
    if "name" in updates and updates["name"]:
        updates["slug"] = _slugify(updates["name"])

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [author_id]
        await db.execute(
            f"UPDATE authors SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            tuple(values),
        )
        await db.commit()

    return await get_author(author_id, _token)


@router.delete("/{author_id}")
async def delete_author(author_id: int, _token: str = Depends(verify_token)):
    """Löscht einen Autor."""
    existing = await db.fetch_one(
        "SELECT id FROM authors WHERE id = ?", (author_id,)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Autor nicht gefunden")

    await db.execute("DELETE FROM authors WHERE id = ?", (author_id,))
    await db.commit()
    return {"gelöscht": True}


@router.post("")
async def create_author(data: AuthorUpdate, _token: str = Depends(verify_token)):
    """Erstellt einen neuen Autor."""
    name = data.name
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Name ist erforderlich")

    slug = _slugify(name)
    existing = await db.fetch_one(
        "SELECT id FROM authors WHERE slug = ?", (slug,)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Autor existiert bereits")

    fields = {"name": name, "slug": slug}
    for key, value in data.model_dump(exclude_unset=True).items():
        if key != "name" and value is not None:
            fields[key] = value

    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" * len(fields))
    cursor = await db.execute(
        f"INSERT INTO authors ({cols}) VALUES ({placeholders})",
        tuple(fields.values()),
    )
    await db.commit()

    return await get_author(cursor.lastrowid, _token)


@router.post("/{author_id}/buecher/{book_id}")
async def link_book(
    author_id: int,
    book_id: int,
    role: str = Query("autor"),
    _token: str = Depends(verify_token),
):
    """Verknüpft ein Buch mit einem Autor."""
    await db.execute(
        "INSERT OR IGNORE INTO book_authors (book_id, author_id, role) VALUES (?, ?, ?)",
        (book_id, author_id, role),
    )
    await db.commit()
    return {"verknüpft": True}


@router.delete("/{author_id}/buecher/{book_id}")
async def unlink_book(
    author_id: int, book_id: int, _token: str = Depends(verify_token)
):
    """Entfernt die Verknüpfung zwischen Buch und Autor."""
    await db.execute(
        "DELETE FROM book_authors WHERE book_id = ? AND author_id = ?",
        (book_id, author_id),
    )
    await db.commit()
    return {"entfernt": True}


@router.get("/{author_id}/foto")
async def get_author_photo(
    author_id: int,
    groesse: str = Query("normal", description="normal, thumb, mini"),
    _token: str = Depends(verify_token_inhalt),
):
    """Gibt das Foto eines Autors in der gewünschten Größe zurück."""
    from backend.app.core.config import settings

    author = await db.fetch_one(
        "SELECT photo_path FROM authors WHERE id = ?", (author_id,)
    )
    if not author or not author["photo_path"]:
        raise HTTPException(status_code=404, detail="Kein Foto vorhanden")

    photo_dir = settings.storage_dir / "authors" / str(author_id)

    # Dateinamen je nach Größe
    filenames = {
        "normal": "foto.jpg",
        "thumb": "foto_thumb.jpg",
        "mini": "foto_mini.jpg",
    }
    filename = filenames.get(groesse, "foto.jpg")
    photo_path = photo_dir / filename

    # Fallback auf Hauptbild wenn gewünschte Größe nicht existiert
    if not photo_path.exists():
        photo_path = photo_dir / "foto.jpg"

    if not photo_path.exists():
        raise HTTPException(status_code=404, detail="Fotodatei nicht gefunden")

    return Response(
        content=photo_path.read_bytes(),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.post("/{author_id}/anreichern")
async def enrich_author(author_id: int, _token: str = Depends(verify_token)):
    """Sucht Angaben zu einem Autor in Normdatei und Lexikon (Wikidata, Wikipedia).

    Biografie, Lebensdaten, Foto, Werke und Verweise kommen als Vorschlag; die Bücher des Autors
    entscheiden mit, ob ein Eintrag passt.
    """
    author = await db.fetch_one("SELECT * FROM authors WHERE id = ?", (author_id,))
    if not author:
        raise HTTPException(status_code=404, detail="Autor nicht gefunden")

    antwort = await _suche(author)
    if antwort.angaben is None:
        grund = ". ".join(antwort.hinweise) or "Weder Lexikon noch Normdatei kennen diesen Autor."
        return {"angereichert": False, "grund": grund, "hinweise": antwort.hinweise}

    buecher = await db.fetch_all(
        "SELECT b.id, b.title, b.isbn FROM books b JOIN book_authors ba ON ba.book_id = b.id WHERE ba.author_id = ?",
        (author_id,),
    )
    return {
        "angereichert": True,
        "vorschlag": antwort.angaben.model_dump(),
        "hinweise": antwort.hinweise,
        "aktuell": {
            "name": author["name"],
            "biography": author["biography"],
            "beschreibung": author["beschreibung"],
            "birth_year": author["birth_year"],
            "death_year": author["death_year"],
            "nationality": author["nationality"],
            "wikidata_id": author["wikidata_id"],
            "wikipedia_url": author["wikipedia_url"],
            "website": author["website"],
            "verweise": {v.art: v.kennung for v in await uebernahme.verweise(author_id)},
            "hat_foto": bool(author["photo_path"]),
        },
        "buecher_im_system": buecher,
    }


@router.post("/{author_id}/anreichern/uebernehmen")
async def apply_author_enrichment(
    author_id: int, felder: dict, _token: str = Depends(verify_token)
):
    """Übernimmt die angereicherten Autorendaten."""
    author = await db.fetch_one("SELECT id FROM authors WHERE id = ?", (author_id,))
    if not author:
        raise HTTPException(status_code=404, detail="Autor nicht gefunden")

    # Gibt es schon einen anderen Autor mit diesem Eintrag? Dann werden beide einer.
    da = await uebernahme.doppel(author_id, felder)
    if da:
        await uebernahme.zusammenlegen(author_id, da["id"])
        return {
            "uebernommen": False,
            "zusammengefuehrt": True,
            "ziel_autor_id": da["id"],
            "ziel_autor_name": da["name"],
            "hinweis": f"Autor wurde mit '{da['name']}' (ID {da['id']}) zusammengeführt",
        }
    return await uebernahme.uebernehmen(author_id, felder)


def _sse_event(data: dict) -> str:
    """Formatiert ein SSE-Event."""
    return f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
