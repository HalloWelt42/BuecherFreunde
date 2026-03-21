"""API-Endpunkte für Autoren."""

import asyncio
import io
import json
import math
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from backend.app.core.auth import verify_token, verify_token_query
from backend.app.core.database import db
from backend.app.models.author import (
    AuthorListItem,
    AuthorListResponse,
    AuthorResponse,
    AuthorUpdate,
)

router = APIRouter(prefix="/api/authors", tags=["Autoren"])


def _slugify(text: str) -> str:
    """Erzeugt einen URL-freundlichen Slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


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
    "abbrechen": False,
    "fortschritt": {},
}


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

    return {
        "gesamt": total["total"] if total else 0,
        "mit_biografie": mit_bio["total"] if mit_bio else 0,
        "mit_foto": mit_foto["total"] if mit_foto else 0,
        "mit_wikidata": mit_wikidata["total"] if mit_wikidata else 0,
    }


@router.post("/resync")
async def resync_authors(_token: str = Depends(verify_token)):
    """Synchronisiert die Autoren-Tabelle komplett neu aus books.author.

    Autoren MIT Wikidata-Daten (biography, wikidata_id, photo) werden beibehalten.
    Alle anderen werden gelöscht und aus den Buch-Strings neu angelegt.
    """
    from backend.app.api.metadata import _parse_author_string

    # Angereicherte Autoren sichern (haben wertvolle Daten)
    enriched = await db.fetch_all("""
        SELECT id, name, slug FROM authors
        WHERE wikidata_id IS NOT NULL AND wikidata_id != ''
    """)
    enriched_slugs = {a["slug"]: a["id"] for a in enriched}

    # Nicht-angereicherte Autoren und deren Verknüpfungen löschen
    await db.execute("""
        DELETE FROM book_authors WHERE author_id IN (
            SELECT id FROM authors WHERE wikidata_id IS NULL OR wikidata_id = ''
        )
    """)
    await db.execute("DELETE FROM authors WHERE wikidata_id IS NULL OR wikidata_id = ''")

    # Alle Bücher durchgehen und Autoren neu anlegen
    books = await db.fetch_all(
        "SELECT id, author FROM books WHERE author IS NOT NULL AND author != ''"
    )

    neu_angelegt = 0
    verknuepft = 0

    for book in books:
        namen = _parse_author_string(book["author"])
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
    await db.execute("""
        DELETE FROM authors WHERE id NOT IN (
            SELECT DISTINCT author_id FROM book_authors
        ) AND (wikidata_id IS NULL OR wikidata_id = '')
    """)
    await db.commit()

    total = await db.fetch_one("SELECT COUNT(*) as n FROM authors")

    return {
        "neu_angelegt": neu_angelegt,
        "verknuepft": verknuepft,
        "beibehalten": len(enriched),
        "gesamt": total["n"] if total else 0,
        "buecher_verarbeitet": len(books),
    }


@router.post("/scanner/starten")
async def scan_authors(_token: str = Depends(verify_token)):
    """Findet Autoren ohne angereicherte Daten und gibt sie als Liste zurück."""
    rows = await db.fetch_all("""
        SELECT a.id, a.name,
               (SELECT COUNT(*) FROM book_authors ba WHERE ba.author_id = a.id) as book_count
        FROM authors a
        WHERE a.wikidata_id IS NULL OR a.wikidata_id = ''
        ORDER BY book_count DESC
        LIMIT 100
    """)

    return {
        "offene_autoren": [dict(r) for r in rows],
        "anzahl": len(rows),
    }


@router.post("/scanner/batch")
async def start_batch_scan(_token: str = Depends(verify_token)):
    """Startet den Batch-Scan aller Autoren ohne Wikidata-ID."""
    if _batch_scan_status["laeuft"]:
        raise HTTPException(status_code=409, detail="Batch-Scan läuft bereits")

    rows = await db.fetch_all("""
        SELECT a.id, a.name,
               (SELECT COUNT(*) FROM book_authors ba WHERE ba.author_id = a.id) as book_count
        FROM authors a
        WHERE (a.wikidata_id IS NULL OR a.wikidata_id = '')
        ORDER BY book_count DESC
    """)

    return {
        "autoren": [dict(r) for r in rows],
        "anzahl": len(rows),
    }


@router.post("/scanner/abbrechen")
async def cancel_batch_scan(_token: str = Depends(verify_token)):
    """Bricht den laufenden Batch-Scan ab."""
    if _batch_scan_status["laeuft"]:
        _batch_scan_status["abbrechen"] = True
        return {"abgebrochen": True}
    return {"abgebrochen": False, "grund": "Kein Scan aktiv"}


@router.get("/scanner/events")
async def batch_scan_events(
    _token: str = Depends(verify_token_query),
    nur_ohne_wikidata: bool = Query(True, description="Nur Autoren ohne Wikidata-ID"),
    auto_uebernehmen: bool = Query(False, description="Hohe Konfidenz automatisch übernehmen"),
):
    """SSE-Endpunkt für den Batch-Scan. Streamt Fortschritt pro Autor."""
    from backend.app.services import wikipedia
    from backend.app.core.config import settings

    if _batch_scan_status["laeuft"]:
        raise HTTPException(status_code=409, detail="Batch-Scan läuft bereits")

    where = "(a.wikidata_id IS NULL OR a.wikidata_id = '')" if nur_ohne_wikidata else "1=1"
    rows = await db.fetch_all(f"""
        SELECT a.id, a.name, a.photo_path,
               (SELECT COUNT(*) FROM book_authors ba WHERE ba.author_id = a.id) as book_count
        FROM authors a
        WHERE {where}
        ORDER BY book_count DESC
    """)

    autoren = [dict(r) for r in rows]
    gesamt = len(autoren)

    async def event_generator():
        _batch_scan_status["laeuft"] = True
        _batch_scan_status["abbrechen"] = False
        _batch_scan_status["fortschritt"] = {
            "gesamt": gesamt, "bearbeitet": 0,
            "gefunden": 0, "nicht_gefunden": 0, "fehler": 0,
        }

        try:
            yield _sse_event({"typ": "start", "gesamt": gesamt})

            for i, autor in enumerate(autoren):
                if _batch_scan_status["abbrechen"]:
                    yield _sse_event({"typ": "abgebrochen", "bearbeitet": i, "gesamt": gesamt})
                    break

                autor_id = autor["id"]
                autor_name = autor["name"]

                yield _sse_event({
                    "typ": "suche", "autor_id": autor_id, "name": autor_name,
                    "index": i + 1, "gesamt": gesamt,
                })

                try:
                    books = await db.fetch_all(
                        """SELECT b.title, b.isbn FROM books b
                           JOIN book_authors ba ON ba.book_id = b.id
                           WHERE ba.author_id = ?""",
                        (autor_id,),
                    )
                    book_titles = [b["title"] for b in books]
                    book_isbns = [b["isbn"] for b in books if b["isbn"]]

                    result = await wikipedia.lookup_author(autor_name, book_titles=book_titles, book_isbns=book_isbns)

                    if result:
                        _batch_scan_status["fortschritt"]["gefunden"] += 1
                        uebernommen = False
                        if auto_uebernehmen and result.get("konfidenz") == "hoch":
                            await _auto_apply_enrichment(autor_id, result, settings)
                            uebernommen = True

                        yield _sse_event({
                            "typ": "gefunden", "autor_id": autor_id, "name": autor_name,
                            "index": i + 1, "gesamt": gesamt,
                            "vorschlag": {
                                "name": result.get("name", ""),
                                "wikidata_id": result.get("wikidata_id", ""),
                                "biography": (result.get("biography", "") or "")[:200],
                                "birth_year": result.get("birth_year"),
                                "death_year": result.get("death_year"),
                                "nationality": result.get("nationality", ""),
                                "photo_url": result.get("photo_url", ""),
                                "wikipedia_url": result.get("wikipedia_url", ""),
                                "konfidenz": result.get("konfidenz", "niedrig"),
                                "score": result.get("score", 0),
                            },
                            "uebernommen": uebernommen,
                        })
                    else:
                        _batch_scan_status["fortschritt"]["nicht_gefunden"] += 1
                        yield _sse_event({
                            "typ": "nicht_gefunden", "autor_id": autor_id, "name": autor_name,
                            "index": i + 1, "gesamt": gesamt,
                        })

                except Exception as e:
                    _batch_scan_status["fortschritt"]["fehler"] += 1
                    yield _sse_event({
                        "typ": "fehler", "autor_id": autor_id, "name": autor_name,
                        "index": i + 1, "gesamt": gesamt, "fehler": str(e),
                    })

                _batch_scan_status["fortschritt"]["bearbeitet"] = i + 1
                await asyncio.sleep(1.0)

            yield _sse_event({"typ": "fertig", **_batch_scan_status["fortschritt"]})

        finally:
            _batch_scan_status["laeuft"] = False
            _batch_scan_status["abbrechen"] = False

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

    return AuthorResponse(**author, books=books, werke=[dict(w) for w in werke])


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
    _token: str = Depends(verify_token_query),
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
    """Reichert einen Autor mit Daten aus Wikipedia/Wikidata an.

    Sucht nach dem Autor bei Wikidata, holt Biografie, Lebensdaten,
    Foto und Wikipedia-URL. Buchtitel werden zur Validierung genutzt.
    """
    from backend.app.core.config import settings
    from backend.app.services import wikipedia

    author = await db.fetch_one(
        "SELECT id, name, wikidata_id, photo_path FROM authors WHERE id = ?",
        (author_id,),
    )
    if not author:
        raise HTTPException(status_code=404, detail="Autor nicht gefunden")

    # Buchtitel und ISBNs für Validierung laden
    books = await db.fetch_all(
        """SELECT b.title, b.isbn FROM books b
           JOIN book_authors ba ON ba.book_id = b.id
           WHERE ba.author_id = ?""",
        (author_id,),
    )
    book_titles = [b["title"] for b in books]
    book_isbns = [b["isbn"] for b in books if b["isbn"]]

    result = await wikipedia.lookup_author(author["name"], book_titles=book_titles, book_isbns=book_isbns)
    if not result:
        return {"angereichert": False, "grund": "Keine Daten bei Wikipedia/Wikidata gefunden"}

    # Vorschlag zurückgeben mit aktuellem Vergleich
    aktuell = await db.fetch_one("SELECT * FROM authors WHERE id = ?", (author_id,))

    return {
        "angereichert": True,
        "vorschlag": result,
        "aktuell": {
            "name": aktuell["name"],
            "biography": aktuell["biography"],
            "birth_year": aktuell["birth_year"],
            "death_year": aktuell["death_year"],
            "nationality": aktuell["nationality"],
            "wikidata_id": aktuell["wikidata_id"],
            "wikipedia_url": aktuell["wikipedia_url"],
            "hat_foto": bool(aktuell["photo_path"]),
        },
        "buecher_im_system": [{"id": b["id"], "title": b["title"], "isbn": b["isbn"]} for b in
                               await db.fetch_all(
                                   """SELECT b.id, b.title, b.isbn FROM books b
                                      JOIN book_authors ba ON ba.book_id = b.id
                                      WHERE ba.author_id = ?""",
                                   (author_id,),
                               )],
    }


@router.post("/{author_id}/anreichern/uebernehmen")
async def apply_author_enrichment(
    author_id: int, felder: dict, _token: str = Depends(verify_token)
):
    """Übernimmt die angereicherten Autorendaten."""
    from backend.app.core.config import settings
    from backend.app.services import wikipedia

    author = await db.fetch_one(
        "SELECT id, photo_path FROM authors WHERE id = ?", (author_id,)
    )
    if not author:
        raise HTTPException(status_code=404, detail="Autor nicht gefunden")

    # Duplikatprüfung: Gibt es schon einen anderen Autor mit dieser Wikidata-ID?
    wikidata_id = felder.get("wikidata_id", "")
    if wikidata_id:
        duplicate = await db.fetch_one(
            "SELECT id, name FROM authors WHERE wikidata_id = ? AND id != ?",
            (wikidata_id, author_id),
        )
        if duplicate:
            # Bücher des Duplikats auf diesen Autor umhängen
            await db.execute(
                """UPDATE OR IGNORE book_authors SET author_id = ?
                   WHERE author_id = ?""",
                (duplicate["id"], author_id),
            )
            # Restliche Verknüpfungen löschen (OR IGNORE hat sie übersprungen)
            await db.execute(
                "DELETE FROM book_authors WHERE author_id = ?", (author_id,)
            )
            # Autor löschen
            await db.execute("DELETE FROM authors WHERE id = ?", (author_id,))
            await db.commit()
            return {
                "uebernommen": False,
                "zusammengefuehrt": True,
                "ziel_autor_id": duplicate["id"],
                "ziel_autor_name": duplicate["name"],
                "hinweis": f"Autor wurde mit '{duplicate['name']}' (ID {duplicate['id']}) zusammengeführt",
            }

    allowed = {"name", "biography", "beschreibung", "birth_year", "death_year",
               "nationality", "wikidata_id", "wikipedia_url", "website",
               "quelle", "konfidenz", "score"}
    updates = {}
    for key, value in felder.items():
        if key in allowed and value is not None:
            updates[key] = value

    # Name geändert -> Slug neu generieren
    if "name" in updates:
        updates["slug"] = _slugify(updates["name"])

    # Quelle setzen wenn Wikidata-ID vorhanden
    if "wikidata_id" in updates and "quelle" not in updates:
        updates["quelle"] = "wikidata"

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [author_id]
        await db.execute(
            f"UPDATE authors SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            tuple(values),
        )

    # Foto herunterladen und persistieren (mehrere Größen)
    foto_gespeichert = False
    photo_url = felder.get("photo_url", "")
    if photo_url:
        photo_files = await wikipedia.download_author_photo(photo_url)
        if photo_files:
            photo_dir = settings.storage_dir / "authors" / str(author_id)
            photo_dir.mkdir(parents=True, exist_ok=True)
            for filename, data in photo_files.items():
                (photo_dir / filename).write_bytes(data)
            await db.execute(
                "UPDATE authors SET photo_path = 'foto.jpg', updated_at = datetime('now') WHERE id = ?",
                (author_id,),
            )
            foto_gespeichert = True

    # Werkeliste persistieren
    werke_gespeichert = 0
    werke = felder.get("werke", [])
    if werke:
        # Alte Werke löschen, neue einfügen
        await db.execute("DELETE FROM author_works WHERE author_id = ?", (author_id,))
        for werk in werke:
            # Prüfe ob das Werk einem Buch im System entspricht
            book_id = None
            if werk.get("titel"):
                book = await db.fetch_one(
                    "SELECT id FROM books WHERE LOWER(title) LIKE ?",
                    (f"%{werk['titel'].lower()}%",),
                )
                if book:
                    book_id = book["id"]
            await db.execute(
                """INSERT INTO author_works (author_id, wikidata_id, titel, book_id)
                   VALUES (?, ?, ?, ?)""",
                (author_id, werk.get("wikidata_id", ""), werk.get("titel", ""), book_id),
            )
            werke_gespeichert += 1

    await db.commit()

    return {
        "uebernommen": True,
        "felder": list(updates.keys()),
        "foto_gespeichert": foto_gespeichert,
        "werke_gespeichert": werke_gespeichert,
    }


def _sse_event(data: dict) -> str:
    """Formatiert ein SSE-Event."""
    return f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def _auto_apply_enrichment(author_id: int, result: dict, settings) -> None:
    """Übernimmt Anreicherungsdaten automatisch bei hoher Konfidenz."""
    from backend.app.services import wikipedia

    updates = {}
    for key in ("wikidata_id", "biography", "beschreibung", "birth_year", "death_year",
                "nationality", "wikipedia_url", "konfidenz", "score"):
        val = result.get(key)
        if val:
            updates[key] = val

    updates["quelle"] = "wikidata"

    if result.get("name") and len(result["name"]) > 3:
        current = await db.fetch_one("SELECT name FROM authors WHERE id = ?", (author_id,))
        if current and len(result["name"]) > len(current["name"]):
            updates["name"] = result["name"]
            updates["slug"] = _slugify(result["name"])

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [author_id]
        await db.execute(
            f"UPDATE authors SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            tuple(values),
        )

    # Foto persistieren (mehrere Größen)
    photo_url = result.get("photo_url", "")
    if photo_url:
        photo_files = await wikipedia.download_author_photo(photo_url)
        if photo_files:
            photo_dir = settings.storage_dir / "authors" / str(author_id)
            photo_dir.mkdir(parents=True, exist_ok=True)
            for filename, data in photo_files.items():
                (photo_dir / filename).write_bytes(data)
            await db.execute(
                "UPDATE authors SET photo_path = 'foto.jpg', updated_at = datetime('now') WHERE id = ?",
                (author_id,),
            )

    # Werkeliste persistieren
    werke = result.get("werke", [])
    if werke:
        await db.execute("DELETE FROM author_works WHERE author_id = ?", (author_id,))
        for werk in werke:
            book_id = None
            if werk.get("titel"):
                book = await db.fetch_one(
                    "SELECT id FROM books WHERE LOWER(title) LIKE ?",
                    (f"%{werk['titel'].lower()}%",),
                )
                if book:
                    book_id = book["id"]
            await db.execute(
                """INSERT INTO author_works (author_id, wikidata_id, titel, book_id)
                   VALUES (?, ?, ?, ?)""",
                (author_id, werk.get("wikidata_id", ""), werk.get("titel", ""), book_id),
            )

    await db.commit()


