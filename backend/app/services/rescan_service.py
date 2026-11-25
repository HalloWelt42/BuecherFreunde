"""Selektiver Rescan-Service fuer die Bibliothek.

Ermoeglicht gezieltes Nachscannen von Buechern nach:
- Fehlenden Covern (lokal aus Datei)
- Fehlenden ISBNs (lokal aus Datei)
- Metadaten-Anreicherung (OpenLibrary, rate-limited)
- Fehlendem Volltext

Mit Filtern nach Kategorie und manuell-bearbeitet-Schutz.
"""

import asyncio
import logging
import re
from pathlib import Path

from backend.app.core.database import db
from backend.app.core.suchindex import SUCHTEXT_ZEICHEN
from backend.app.services import deckblatt
from backend.app.services.storage import (
    get_original_file,
    get_sidecar_path,
    save_cover,
    save_fulltext,
)

logger = logging.getLogger("buecherfreunde.rescan")

VOLLTEXT_MINDESTENS = 100        # Bytes; weniger ist kein Text

# Globaler Status
status = {
    "laeuft": False,
    "typ": "",
    "fortschritt": 0,
    "gesamt": 0,
    "cover_gefunden": 0,
    "isbn_gefunden": 0,
    "metadaten_aktualisiert": 0,
    "volltext_extrahiert": 0,
    "uebersprungen": 0,
    "fehler": 0,
    "aktuelles_buch": "",
}


def _reset_status():
    status.update({
        "laeuft": False,
        "typ": "",
        "fortschritt": 0,
        "gesamt": 0,
        "cover_gefunden": 0,
        "isbn_gefunden": 0,
        "metadaten_aktualisiert": 0,
        "volltext_extrahiert": 0,
        "uebersprungen": 0,
        "fehler": 0,
        "aktuelles_buch": "",
    })


def _ohne_volltext(buecher: list) -> set[int]:
    """Bücher, deren Volltext fehlt oder so kurz ist, dass er keiner ist."""
    ids = set()
    for b in buecher:
        try:
            kurz = get_sidecar_path(b["hash"], "fulltext.txt").stat().st_size < VOLLTEXT_MINDESTENS
        except OSError:
            kurz = True
        if kurz:
            ids.add(b["id"])
    return ids


async def _betroffen(buecher: list, typen: list[str]) -> dict[str, set[int]]:
    """Je Art die Nummern der Bücher, denen etwas fehlt (bei "metadaten": die sich über ihre ISBN ergänzen lassen)."""
    proben = {"cover": lambda b: not (b["cover_path"] or "").strip(), "isbn": lambda b: not (b["isbn"] or "").strip(), "metadaten": lambda b: bool((b["isbn"] or "").strip())}
    aus = {t: {b["id"] for b in buecher if proben[t](b)} for t in typen if t in proben}
    if "volltext" in typen:
        aus["volltext"] = await asyncio.to_thread(_ohne_volltext, buecher)
    return aus


async def vorschau(
    typen: list[str],
    kategorie_id: int | None = None,
    manuell_einschliessen: bool = False,
) -> dict:
    """Zaehlt wie viele Buecher vom Rescan betroffen waeren.

    Returns:
        Dict mit Gesamtzahl und Aufschluesselung pro Typ.
    """
    basis_where = []
    basis_params = []

    if not manuell_einschliessen:
        basis_where.append("b.manuell_bearbeitet = 0")

    if kategorie_id is not None:
        basis_where.append("b.id IN (SELECT book_id FROM book_categories WHERE category_id = ?)")
        basis_params.append(kategorie_id)

    basis_clause = " AND ".join(basis_where) if basis_where else "1=1"

    buecher = await db.fetch_all(f"SELECT b.id, b.hash, b.isbn, b.cover_path FROM books b WHERE {basis_clause}", tuple(basis_params))
    betroffen = await _betroffen(buecher, typen)
    ergebnis = {"gesamt": len(set().union(*betroffen.values())) if betroffen else 0, "typen": {t: len(ids) for t, ids in betroffen.items()}}

    return ergebnis


async def vorschau_kategorien(
    typen: list[str],
    manuell_einschliessen: bool = False,
) -> list[dict]:
    """Zaehlt betroffene Buecher pro Kategorie.

    Returns:
        Liste mit {id, name, anzahl} pro Kategorie.
    """
    manuell_clause = "" if manuell_einschliessen else "AND b.manuell_bearbeitet = 0"

    typ_bedingungen = []
    if "cover" in typen:
        typ_bedingungen.append("(b.cover_path IS NULL OR b.cover_path = '')")
    if "isbn" in typen:
        typ_bedingungen.append("(b.isbn IS NULL OR b.isbn = '')")
    if "metadaten" in typen:
        typ_bedingungen.append("(b.isbn IS NOT NULL AND b.isbn != '')")

    if not typ_bedingungen:
        return []

    typ_where = " OR ".join(typ_bedingungen)

    rows = await db.fetch_all(f"""
        SELECT c.id, c.name, COUNT(DISTINCT b.id) as anzahl
        FROM categories c
        JOIN book_categories bc ON bc.category_id = c.id
        JOIN books b ON b.id = bc.book_id
        WHERE ({typ_where}) {manuell_clause}
        GROUP BY c.id, c.name
        ORDER BY anzahl DESC
    """)

    # Auch "ohne Kategorie" zaehlen
    ohne_kat = await db.fetch_one(f"""
        SELECT COUNT(*) as cnt FROM books b
        WHERE b.id NOT IN (SELECT book_id FROM book_categories)
        AND ({typ_where}) {manuell_clause}
    """)

    ergebnis = [{"id": r["id"], "name": r["name"], "anzahl": r["anzahl"]} for r in rows]
    if ohne_kat and ohne_kat["cnt"] > 0:
        ergebnis.append({"id": None, "name": "Ohne Kategorie", "anzahl": ohne_kat["cnt"]})

    return ergebnis


async def starte_rescan(
    typen: list[str],
    kategorie_id: int | None = None,
    manuell_einschliessen: bool = False,
) -> dict:
    """Startet den Rescan als Hintergrundprozess."""
    if status["laeuft"]:
        return {"gestartet": False, "grund": "Rescan laeuft bereits"}

    # Buecher ermitteln
    where_parts = []
    params = []

    if not manuell_einschliessen:
        where_parts.append("b.manuell_bearbeitet = 0")

    if kategorie_id is not None:
        if kategorie_id == 0:
            # "Ohne Kategorie"
            where_parts.append("b.id NOT IN (SELECT book_id FROM book_categories)")
        else:
            where_parts.append("b.id IN (SELECT book_id FROM book_categories WHERE category_id = ?)")
            params.append(kategorie_id)

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    buecher = await db.fetch_all(
        f"""SELECT id, hash, title, file_name, file_format, isbn, cover_path
            FROM books b WHERE {where_clause}
            ORDER BY id""",
        tuple(params),
    )

    faellig = set().union(*(await _betroffen(buecher, typen)).values())
    buecher = [b for b in buecher if b["id"] in faellig]
    if not buecher:
        return {"gestartet": False, "grund": "Keine Buecher gefunden die gescannt werden muessen"}

    _reset_status()
    status["laeuft"] = True
    status["typ"] = ",".join(typen)
    status["gesamt"] = len(buecher)

    asyncio.create_task(_rescan_worker(list(buecher), typen))

    return {"gestartet": True, "anzahl": len(buecher)}


def abbrechen() -> dict:
    """Bricht den laufenden Rescan ab."""
    if not status["laeuft"]:
        return {"abgebrochen": False, "grund": "Kein Rescan aktiv"}
    status["laeuft"] = False
    return {"abgebrochen": True}


async def _rescan_worker(buecher: list, typen: list[str]):
    """Hintergrund-Worker fuer den Rescan."""
    scan_cover = "cover" in typen
    scan_isbn = "isbn" in typen
    scan_metadaten = "metadaten" in typen
    scan_volltext = "volltext" in typen

    for i, book in enumerate(buecher):
        if not status["laeuft"]:
            logger.info("Rescan abgebrochen bei %d/%d", i, len(buecher))
            break

        status["fortschritt"] = i + 1
        status["aktuelles_buch"] = book["title"] or book["file_name"] or f"ID {book['id']}"

        try:
            fmt = (book["file_format"] or "").lower()
            hat_cover = bool(book["cover_path"] and book["cover_path"].strip())
            hat_isbn = bool(book["isbn"] and book["isbn"].strip())
            fehlt_text = scan_volltext and bool(await asyncio.to_thread(_ohne_volltext, [book]))
            original = None
            if (scan_cover and not hat_cover) or (scan_isbn and not hat_isbn) or fehlt_text:
                original = await asyncio.to_thread(get_original_file, book["hash"])     # kann aus der Kellerwolke laden

            if original is not None and scan_cover and not hat_cover:
                cover_data = await asyncio.to_thread(deckblatt.von_datei, original, fmt)
                if cover_data:
                    save_cover(book["hash"], cover_data)
                    await db.execute(
                        "UPDATE books SET cover_path = 'cover.jpg', updated_at = datetime('now') WHERE id = ?",
                        (book["id"],),
                    )
                    await db.commit()
                    status["cover_gefunden"] += 1

            if original is not None and scan_isbn and not hat_isbn:
                if await _extrahiere_isbn(book, original, fmt):
                    status["isbn_gefunden"] += 1

            if original is not None and fehlt_text:
                text = await asyncio.to_thread(_extrahiere_volltext, original, fmt)
                if text:
                    save_fulltext(book["hash"], text)
                    # über fts_content in den Suchindex (Trigger), dann wieder leer
                    await db.execute("UPDATE books SET fts_content = ?, updated_at = datetime('now') WHERE id = ?", (text[:SUCHTEXT_ZEICHEN], book["id"]))
                    await db.execute("UPDATE books SET fts_content = '' WHERE id = ?", (book["id"],))
                    await db.commit()
                    status["volltext_extrahiert"] += 1

            # Metadaten-Anreicherung (OpenLibrary, rate-limited)
            if scan_metadaten and hat_isbn:
                aktualisiert = await _anreichern_openlibrary(book)
                if aktualisiert:
                    status["metadaten_aktualisiert"] += 1
                # Rate-Limit: 10 Sekunden Pause
                await asyncio.sleep(10)
            else:
                # Kurze Pause damit der Event-Loop nicht blockiert
                await asyncio.sleep(0.05)

        except Exception as e:
            logger.warning("Rescan Fehler bei Buch %d: %s", book["id"], e)
            status["fehler"] += 1

    status["laeuft"] = False
    logger.info(
        "Rescan abgeschlossen: %d/%d, Cover: %d, ISBN: %d, Metadaten: %d, Volltext: %d, Fehler: %d",
        status["fortschritt"], status["gesamt"],
        status["cover_gefunden"], status["isbn_gefunden"],
        status["metadaten_aktualisiert"], status["volltext_extrahiert"],
        status["fehler"],
    )


def _extrahiere_volltext(original: Path, fmt: str) -> str | None:
    """Volltext aus Datei extrahieren."""
    if fmt == "epub":
        import zipfile
        try:
            from bs4 import BeautifulSoup
            with zipfile.ZipFile(original) as zf:
                parts = []
                html_files = sorted([
                    n for n in zf.namelist()
                    if n.lower().endswith((".html", ".xhtml", ".htm"))
                ])
                for html_name in html_files:
                    try:
                        content = zf.read(html_name).decode("utf-8", errors="ignore")
                        soup = BeautifulSoup(content, "html.parser")
                        text = soup.get_text(separator="\n", strip=True)
                        if text:
                            parts.append(text)
                    except Exception:
                        continue
                if parts:
                    return "\n\n".join(parts)
        except Exception:
            pass

    elif fmt == "pdf":
        try:
            from backend.app.services.seiten import pdf_volltext
            text = pdf_volltext(original)
            if text.strip():
                return text
        except Exception:
            pass

    return None


async def _extrahiere_isbn(book: dict, original: Path, fmt: str) -> str | None:
    """ISBN aus Datei extrahieren.

    Strategie (priorisiert):
    1. Direkt aus EPUB-Metadaten (OPF dc:identifier)
    2. Direkt aus Datei-Inhalt (erste Seiten / Impressum)
    3. Fallback: Volltext-Sidecar durchsuchen
    """
    from backend.app.services.isbn_extractor import extract_isbns_from_text
    import isbnlib

    def _speichere(isbn_str: str, quelle: str) -> str | None:
        """Validiert und gibt ISBN zurueck (DB-Update asynchron)."""
        canonical = isbnlib.canonical(isbn_str)
        if canonical and len(canonical) in (10, 13):
            return canonical
        return None

    # 1. Direkt aus EPUB-OPF (dc:identifier)
    if fmt == "epub":
        import zipfile
        try:
            with zipfile.ZipFile(original) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".opf"):
                        content = zf.read(name).decode("utf-8", errors="ignore")
                        # ISBN aus dc:identifier
                        import re as _re
                        for match in _re.finditer(
                            r'<dc:identifier[^>]*>([^<]+)</dc:identifier>', content
                        ):
                            val = match.group(1).strip()
                            cleaned = _re.sub(r'[^\dXx]', '', val)
                            if len(cleaned) in (10, 13):
                                result = _speichere(cleaned, "OPF")
                                if result:
                                    await _isbn_db_update(book, result, "OPF")
                                    return result
                        break
        except Exception:
            pass

    # 2. Direkt aus Datei-Inhalt (erste Seiten)
    text_direkt = ""
    if fmt == "epub":
        text_direkt = await asyncio.to_thread(_extrahiere_volltext, original, fmt) or ""
    elif fmt == "pdf":
        try:
            import fitz
            doc = fitz.open(str(original))
            # Nur erste und letzte 10 Seiten (Impressum, Titelseite)
            seiten = []
            total = len(doc)
            for i in list(range(min(10, total))) + list(range(max(0, total - 10), total)):
                try:
                    seiten.append(doc[i].get_text())
                except Exception:
                    pass
            doc.close()
            text_direkt = "\n".join(seiten)
        except Exception:
            pass

    if text_direkt.strip():
        raw_isbns = extract_isbns_from_text(text_direkt)
        if raw_isbns:
            for isbn in raw_isbns:
                result = _speichere(isbn, "Datei")
                if result:
                    await _isbn_db_update(book, result, "Datei-Inhalt")
                    return result

    # 3. Fallback: Volltext-Sidecar
    fulltext_path = get_sidecar_path(book["hash"], "fulltext.txt")
    if fulltext_path.exists():
        text = fulltext_path.read_text(encoding="utf-8", errors="ignore")
        if text.strip():
            raw_isbns = extract_isbns_from_text(text)
            if raw_isbns:
                for isbn in raw_isbns:
                    result = _speichere(isbn, "Sidecar")
                    if result:
                        await _isbn_db_update(book, result, "Sidecar")
                        return result

    return None


async def _isbn_db_update(book: dict, isbn: str, quelle: str):
    """Speichert eine gefundene ISBN in der Datenbank."""
    await db.execute(
        "UPDATE books SET isbn = ?, updated_at = datetime('now') WHERE id = ?",
        (isbn, book["id"]),
    )
    await db.commit()
    logger.info("Rescan ISBN fuer '%s' (%s): %s", book["title"] or book["id"], quelle, isbn)


async def _anreichern_openlibrary(book: dict) -> bool:
    """Reichert Buchdaten ueber OpenLibrary an. Ueberschreibt nur leere Felder.

    Beim Rescan werden KEINE Kategorien automatisch angelegt -- das wuerde
    das System mit Muell-Kategorien von externen Quellen zumuellen.
    Kategorien sollen nur ueber die manuelle Anreicherung (Vorschau + Uebernahme)
    erstellt werden.
    """
    from backend.app.services import openlibrary

    isbn = book["isbn"]
    if not isbn:
        return False

    try:
        daten = await openlibrary.lookup_isbn(isbn)
        if not daten:
            return False

        updates = {}
        # OpenLibrary nutzt deutsche Feldnamen
        update_felder = {
            "titel": "title",
            "autor": "author",
            "verlag": "publisher",
            "jahr": "year",
            "beschreibung": "description",
            "sprache": "language",
        }

        # Nur leere Felder aktualisieren
        current = await db.fetch_one("SELECT * FROM books WHERE id = ?", (book["id"],))
        if not current:
            return False

        for api_feld, db_feld in update_felder.items():
            neuer_wert = daten.get(api_feld)
            if neuer_wert and not current.get(db_feld):
                updates[db_feld] = neuer_wert

        # Cover aus OpenLibrary wenn keins vorhanden
        if not current.get("cover_path") and daten.get("cover_url"):
            try:
                import httpx
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(daten["cover_url"])
                    if resp.status_code == 200 and len(resp.content) > 500:
                        save_cover(book["hash"], resp.content)
                        updates["cover_path"] = "cover.jpg"
            except Exception as e:
                logger.debug("OpenLibrary Cover-Download: %s", e)

        # KEINE Kategorien beim Rescan anlegen -- nur Stammdaten
        # Kategorien kommen nur ueber manuelle Uebernahme ins System

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [book["id"]]
            await db.execute(
                f"UPDATE books SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                tuple(values),
            )
            await db.commit()
            logger.info(
                "OpenLibrary Anreicherung fuer '%s': %s",
                book["title"] or isbn,
                ", ".join(updates.keys()),
            )
            return True

    except Exception as e:
        logger.warning("OpenLibrary Anreicherung fehlgeschlagen fuer ISBN %s: %s", isbn, e)

    return False
