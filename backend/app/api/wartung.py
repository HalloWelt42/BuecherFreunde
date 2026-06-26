"""Wartungs-Endpunkte: beschädigte Buchdateien finden, in Quarantäne verschieben
und aus der Bibliothek entfernen.

Eine Datei gilt als defekt, wenn sie sich nicht als ihr Format öffnen lässt
(z. B. abgeschnittenes/leeres PDF, kaputtes EPUB-ZIP). Die Prüfung ist bewusst
konservativ, um gesunde Bücher nicht fälschlich auszusortieren.
"""

import asyncio
import logging
import shutil
import threading
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from backend.app.core.auth import verify_token
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services.storage import get_original_file, get_storage_path

logger = logging.getLogger("buecherfreunde.wartung")

router = APIRouter(prefix="/api/wartung", tags=["Wartung"])

# Nebenläufigkeit beim Prüfen (mehrere Dateien gleichzeitig im Threadpool)
_PRUEF_PARALLEL = 6

# MuPDF-Warnungen liegen in einem prozessweiten Speicher -> beim Auslesen
# serialisieren, damit die Zuordnung Datei<->Warnung stimmt.
_fitz_lock = threading.Lock()


def _quarantaene_dir() -> Path:
    """Verzeichnis für aussortierte Dateien (auf derselben Platte wie der
    Speicher, damit das Verschieben ein schneller Rename ist)."""
    d = settings.storage_dir / "_quarantaene"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _pruefe_datei(file_format: str, path: Path | None) -> str | None:
    """Prüft eine Datei. Gibt den Defekt-Grund zurück oder None wenn alles ok.

    Läuft synchron (CPU/IO) und wird via asyncio.to_thread aufgerufen.
    """
    if path is None or not path.exists():
        return "Datei fehlt im Speicher"
    try:
        if path.stat().st_size == 0:
            return "Datei ist leer (0 Bytes)"
    except OSError:
        return "Datei nicht lesbar"

    fmt = (file_format or path.suffix.lstrip(".")).lower()
    try:
        if fmt == "pdf":
            import fitz

            with _fitz_lock:
                fitz.TOOLS.mupdf_warnings()  # alten Warnungsspeicher leeren (reset=True)
                doc = fitz.open(str(path))
                try:
                    if doc.page_count == 0:
                        return "PDF hat 0 Seiten"
                    doc.load_page(0)  # erste Seite muss ladbar sein
                finally:
                    doc.close()
                warnungen = (fitz.TOOLS.mupdf_warnings() or "").lower()
            # MuPDF repariert kaputte PDFs still; pdf.js (der Reader) kann das
            # nicht und zeigt "Invalid PDF structure". Solche Dateien aussortieren.
            if "repair" in warnungen or "rebuild" in warnungen:
                return "PDF strukturell beschädigt (MuPDF musste reparieren – Reader scheitert)"

        elif fmt == "epub":
            if not zipfile.is_zipfile(path):
                return "EPUB ist kein gültiges ZIP-Archiv"
            with zipfile.ZipFile(path) as zf:
                namen = zf.namelist()
                if not namen:
                    return "EPUB-Archiv ist leer"
                # container.xml muss vorhanden und lesbar sein
                container = "META-INF/container.xml"
                if container in namen:
                    zf.read(container)
                # Mindestens eine HTML-Datei muss lesbar sein
                html = [n for n in namen if n.lower().endswith((".html", ".xhtml", ".htm"))]
                if html:
                    zf.read(html[0])

        elif fmt == "mobi":
            import mobi

            tempdir, extracted = mobi.extract(str(path))
            try:
                if not extracted or not Path(extracted).exists():
                    return "MOBI konnte nicht entpackt werden"
            finally:
                # Temp-Verzeichnis von mobi.extract aufräumen (sonst Leck)
                if tempdir:
                    shutil.rmtree(tempdir, ignore_errors=True)

        # txt/md: nur 0-Byte-Prüfung (oben), Inhalt nicht als "defekt" werten
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    return None


def _verschiebe_in_quarantaene(file_hash: str) -> str | None:
    """Verschiebt das komplette Hash-Verzeichnis in die Quarantäne.
    Gibt den Zielpfad zurück oder None wenn nichts zu verschieben war."""
    src = get_storage_path(file_hash)
    if not src.exists():
        return None
    ziel = _quarantaene_dir() / file_hash
    if ziel.exists():
        shutil.rmtree(ziel, ignore_errors=True)
    shutil.move(str(src), str(ziel))
    # leere Elternverzeichnisse aufräumen
    try:
        src.parent.rmdir()
        src.parent.parent.rmdir()
    except OSError:
        pass
    return str(ziel)


async def _aus_db_entfernen(book_id: int) -> None:
    """Entfernt ein Buch und alle abhängigen Datensätze aus der DB."""
    for tabelle in (
        "book_categories",
        "book_authors",
        "user_book_data",
        "book_highlights",
        "book_labels",
        "book_notes",
    ):
        try:
            await db.execute(f"DELETE FROM {tabelle} WHERE book_id = ?", (book_id,))
        except Exception:
            pass  # Tabelle/Spalte evtl. nicht vorhanden - tolerieren
    await db.execute("DELETE FROM books WHERE id = ?", (book_id,))


@router.post("/defekte-pruefen")
async def defekte_pruefen(
    verschieben: bool = Query(
        False,
        description="False = nur Bericht (Dry-Run). True = defekte Dateien in "
        "Quarantäne verschieben und aus der Bibliothek entfernen.",
    ),
    _token: str = Depends(verify_token),
) -> dict:
    """Prüft alle Buchdateien auf Beschädigung.

    Im Dry-Run (Standard) wird nur berichtet. Mit verschieben=true werden die
    defekten Dateien in den Quarantäne-Ordner verschoben (umkehrbar) und die
    zugehörigen Bücher aus der Datenbank entfernt.
    """
    rows = await db.fetch_all(
        "SELECT id, hash, title, author, file_format, file_name, file_size "
        "FROM books ORDER BY id"
    )

    sem = asyncio.Semaphore(_PRUEF_PARALLEL)

    async def pruefe(row: dict):
        async with sem:
            path = get_original_file(row["hash"])
            grund = await asyncio.to_thread(_pruefe_datei, row["file_format"], path)
            return row, grund

    ergebnisse = await asyncio.gather(*[pruefe(r) for r in rows])

    defekte = []
    for row, grund in ergebnisse:
        if grund:
            defekte.append(
                {
                    "id": row["id"],
                    "titel": row["title"] or row["file_name"] or f"#{row['id']}",
                    "autor": row["author"] or "",
                    "format": row["file_format"],
                    "dateiname": row["file_name"],
                    "groesse": row["file_size"],
                    "grund": grund,
                }
            )

    verschoben = 0
    quarantaene = str(_quarantaene_dir())
    if verschieben and defekte:
        for d in defekte:
            row = next(r for r in rows if r["id"] == d["id"])
            try:
                ziel = await asyncio.to_thread(_verschiebe_in_quarantaene, row["hash"])
                await _aus_db_entfernen(d["id"])
                d["quarantaene_pfad"] = ziel
                verschoben += 1
            except Exception as e:
                d["fehler_beim_verschieben"] = f"{type(e).__name__}: {e}"
                logger.error("Quarantäne fehlgeschlagen für Buch %s: %s", d["id"], e)
        await db.commit()
        # FTS-Index neu aufbauen, damit aussortierte Bücher aus der Suche fallen
        try:
            await db.execute("INSERT INTO books_fts(books_fts) VALUES('rebuild')")
            await db.commit()
        except Exception:
            pass

    return {
        "geprueft": len(rows),
        "defekt": len(defekte),
        "verschoben": verschoben,
        "modus": "ausgeführt" if verschieben else "nur Bericht (Dry-Run)",
        "quarantaene_ordner": quarantaene,
        "eintraege": defekte,
    }
