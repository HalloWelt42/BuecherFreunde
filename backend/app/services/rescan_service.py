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
from backend.app.services.storage import (
    get_original_file,
    get_sidecar_path,
    save_cover,
    save_fulltext,
)

logger = logging.getLogger("buecherfreunde.rescan")

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

    ergebnis = {"gesamt": 0, "typen": {}}

    typ_bedingungen = {
        "cover": "(b.cover_path IS NULL OR b.cover_path = '')",
        "isbn": "(b.isbn IS NULL OR b.isbn = '')",
        "metadaten": "(b.isbn IS NOT NULL AND b.isbn != '')",  # Nur Buecher MIT ISBN koennen angereichert werden
        "volltext": "NOT EXISTS (SELECT 1 FROM (SELECT 1) WHERE 1=1)",  # Wird per Sidecar geprueft
    }

    # Volltext separat behandeln (muss Sidecar pruefen)
    for typ in typen:
        if typ == "volltext":
            # Alle Buecher zaehlen, Volltext-Pruefung geht nur zur Laufzeit
            sql = f"SELECT COUNT(*) as cnt FROM books b WHERE {basis_clause}"
            row = await db.fetch_one(sql, tuple(basis_params))
            ergebnis["typen"]["volltext"] = row["cnt"] if row else 0
        elif typ in typ_bedingungen:
            sql = f"SELECT COUNT(*) as cnt FROM books b WHERE {basis_clause} AND {typ_bedingungen[typ]}"
            row = await db.fetch_one(sql, tuple(basis_params))
            cnt = row["cnt"] if row else 0
            ergebnis["typen"][typ] = cnt

    # Kombinierte Zahl (UNION um Duplikate zu vermeiden)
    if typen:
        union_parts = []
        union_params = []
        for typ in typen:
            if typ in typ_bedingungen and typ != "volltext":
                union_parts.append(
                    f"SELECT b.id FROM books b WHERE {basis_clause} AND {typ_bedingungen[typ]}"
                )
                union_params.extend(basis_params)

        if union_parts:
            sql = f"SELECT COUNT(*) as cnt FROM ({' UNION '.join(union_parts)})"
            row = await db.fetch_one(sql, tuple(union_params))
            ergebnis["gesamt"] = row["cnt"] if row else 0
        elif "volltext" in typen:
            ergebnis["gesamt"] = ergebnis["typen"].get("volltext", 0)

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

    # Typ-Filter
    typ_bedingungen = []
    if "cover" in typen:
        typ_bedingungen.append("(b.cover_path IS NULL OR b.cover_path = '')")
    if "isbn" in typen:
        typ_bedingungen.append("(b.isbn IS NULL OR b.isbn = '')")
    if "metadaten" in typen:
        typ_bedingungen.append("(b.isbn IS NOT NULL AND b.isbn != '')")
    if "volltext" in typen:
        typ_bedingungen.append("1=1")  # Alle -- Volltext wird zur Laufzeit geprueft

    if typ_bedingungen:
        where_parts.append(f"({' OR '.join(typ_bedingungen)})")

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    buecher = await db.fetch_all(
        f"""SELECT id, hash, title, file_name, file_format, isbn, cover_path
            FROM books b WHERE {where_clause}
            ORDER BY id""",
        tuple(params),
    )

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
            original = get_original_file(book["hash"])
            fmt = (book["file_format"] or "").lower()
            hat_cover = bool(book["cover_path"] and book["cover_path"].strip())
            hat_isbn = bool(book["isbn"] and book["isbn"].strip())

            # Cover
            if scan_cover and not hat_cover and original and original.exists():
                cover_data = _extrahiere_cover(original, fmt)
                if cover_data:
                    save_cover(book["hash"], cover_data)
                    await db.execute(
                        "UPDATE books SET cover_path = 'cover.jpg', updated_at = datetime('now') WHERE id = ?",
                        (book["id"],),
                    )
                    await db.commit()
                    status["cover_gefunden"] += 1

            # ISBN
            if scan_isbn and not hat_isbn and original and original.exists():
                isbn = await _extrahiere_isbn(book, original, fmt)
                if isbn:
                    status["isbn_gefunden"] += 1

            # Volltext
            if scan_volltext and original and original.exists():
                fulltext_path = get_sidecar_path(book["hash"], "fulltext.txt")
                if not fulltext_path.exists() or fulltext_path.stat().st_size < 100:
                    text = _extrahiere_volltext(original, fmt)
                    if text:
                        save_fulltext(book["hash"], text)
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


def _extrahiere_cover(original: Path, fmt: str) -> bytes | None:
    """Cover aus Datei extrahieren (alle Formate)."""
    if fmt == "epub":
        from backend.app.services.processors.epub_processor import EpubProcessor
        try:
            import ebooklib.epub
            book = ebooklib.epub.read_epub(str(original), options={"ignore_ncx": True})
            proc = EpubProcessor()
            data = proc._extract_cover(book)
            if data:
                return data
        except Exception:
            pass
        return EpubProcessor._extract_cover_from_zip(original)

    elif fmt == "pdf":
        try:
            from backend.app.services.processors.pdf_processor import PdfProcessor
            import fitz
            doc = fitz.open(str(original))
            proc = PdfProcessor()
            data = proc._extract_cover(doc)
            doc.close()
            return data
        except Exception:
            pass

    return None


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
            import fitz
            doc = fitz.open(str(original))
            parts = []
            for page in doc:
                text = page.get_text()
                if text:
                    parts.append(text)
            doc.close()
            if parts:
                return "\n\n".join(parts)
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
        text_direkt = _extrahiere_volltext(original, fmt) or ""
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
