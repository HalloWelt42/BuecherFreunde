"""Selektiver Rescan-Service für die Bibliothek.

Ermöglicht gezieltes Nachscannen von Büchern nach:
- Fehlenden Covern (lokal aus Datei)
- Fehlenden ISBNs (aus der Datei; eingetragen nur, was zum Buch passt, sonst zur Wahl: isbnsuche/lauf.py)
- Fehlenden Angaben (aus den Quellen, über die ISBN)
- Fehlendem Volltext

Mit Filtern nach Kategorie und manuell-bearbeitet-Schutz.
"""

import asyncio
import logging
from pathlib import Path

from backend.app.core.database import db
from backend.app.isbnsuche import dienst as isbnsuche
from backend.app.isbnsuche import lauf as isbnlauf
from backend.app.quellen import auskunft, bilder
from backend.app.quellen.fehler import QuelleFehler
from backend.app.quellen.modelle import Angaben
from backend.app.quellen.open_library import SAMMEL_HOECHSTENS, OpenLibrary
from backend.app.quellen.vorrang import hintergrund
from backend.app.quellen.vorschlag import frage_aus
from backend.app.services import deckblatt, volltext
from backend.app.services.anhalten import Anhalter
from backend.app.services.data_cleaner import bereinige_autor, bereinige_text, bereinige_titel
from backend.app.services.storage import (
    get_original_file,
    get_sidecar_path,
    save_cover,
)

logger = logging.getLogger("buecherfreunde.rescan")

VOLLTEXT_MINDESTENS = 100        # Bytes; weniger ist kein Text
# Feld der Angaben -> Spalte; nur Leeres wird ergänzt
ANGABEN = {"titel": "title", "autoren": "author", "verlag": "publisher", "jahr": "year", "sprache": "language", "beschreibung": "description", "umschlag": "cover_path"}
ANGABEN_FEHLEN = "(b.isbn != '' AND (" + " OR ".join(f"COALESCE(b.{s}, '') = ''" for s in ANGABEN.values()) + "))"
SPALTEN = "b.id, b.hash, b.isbn, b.page_count, " + ", ".join(f"b.{s}" for s in ANGABEN.values())
_lauf = Anhalter()                  # der laufende oder letzte Lauf
_aufgaben: set[asyncio.Task] = set()

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
    "grund": "",                    # warum Angaben nicht weiter ergänzt wurden (Pause oder Tagesgrenze einer Quelle)
    "isbn_zur_wahl": 0,             # Bücher, deren ISBN nicht sicher passte und zur Wahl steht (BF-111)
    "isbn_ungeprueft": 0,           # davon ohne Antwort einer Quelle, weil die Quellen ruhten
    "isbn_grund": "",               # warum der Lauf ISBN die Quellen nicht mehr fragt
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
        "grund": "",
        "isbn_zur_wahl": 0,
        "isbn_ungeprueft": 0,
        "isbn_grund": "",
    })


def _ohne_volltext(buecher: list) -> set[int]:
    """Bücher, deren Volltext fehlt oder so kurz ist, dass er keiner ist, oder die keine Seiten haben (BF-17: beim
    Aufnehmen nicht lesbar, inzwischen schon)."""
    ids = set()
    for b in buecher:
        try:
            kurz = get_sidecar_path(b["hash"], "fulltext.txt").stat().st_size < VOLLTEXT_MINDESTENS
        except OSError:
            kurz = True
        if kurz or not b["page_count"]:
            ids.add(b["id"])
    return ids


def _fehlende_angaben(b: dict) -> set[str]:
    return {feld for feld, spalte in ANGABEN.items() if not str(b[spalte] or "").strip()}


async def _betroffen(buecher: list, typen: list[str]) -> dict[str, set[int]]:
    """Je Art die Nummern der Bücher, denen etwas fehlt (bei "metadaten": denen eine Angabe fehlt und die eine ISBN haben)."""
    proben = {"cover": lambda b: not (b["cover_path"] or "").strip(), "isbn": lambda b: not (b["isbn"] or "").strip(), "metadaten": lambda b: bool((b["isbn"] or "").strip()) and bool(_fehlende_angaben(b))}
    aus = {t: {b["id"] for b in buecher if proben[t](b)} for t in typen if t in proben}
    if "volltext" in typen:
        aus["volltext"] = await asyncio.to_thread(_ohne_volltext, buecher)
    return aus


async def vorschau(
    typen: list[str],
    kategorie_id: int | None = None,
    manuell_einschliessen: bool = False,
) -> dict:
    """Zählt, wie viele Bücher vom Rescan betroffen wären.

    Returns:
        Dict mit Gesamtzahl und Aufschlüsselung pro Typ.
    """
    basis_where = []
    basis_params = []

    if not manuell_einschliessen:
        basis_where.append("b.manuell_bearbeitet = 0")

    if kategorie_id is not None:
        basis_where.append("b.id IN (SELECT book_id FROM book_categories WHERE category_id = ?)")
        basis_params.append(kategorie_id)

    basis_clause = " AND ".join(basis_where) if basis_where else "1=1"

    buecher = await db.fetch_all(f"SELECT {SPALTEN} FROM books b WHERE {basis_clause}", tuple(basis_params))
    betroffen = await _betroffen(buecher, typen)
    ergebnis = {"gesamt": len(set().union(*betroffen.values())) if betroffen else 0, "typen": {t: len(ids) for t, ids in betroffen.items()}}

    return ergebnis


async def vorschau_kategorien(
    typen: list[str],
    manuell_einschliessen: bool = False,
) -> list[dict]:
    """Zählt betroffene Bücher pro Kategorie.

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
        typ_bedingungen.append(ANGABEN_FEHLEN)

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

    # Auch "ohne Kategorie" zählen
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
        return {"gestartet": False, "grund": "Rescan läuft bereits"}

    # Bücher ermitteln
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
        f"""SELECT {SPALTEN}, b.file_name, b.file_format
            FROM books b WHERE {where_clause}
            ORDER BY b.id""",
        tuple(params),
    )

    faellig = set().union(*(await _betroffen(buecher, typen)).values())
    buecher = [b for b in buecher if b["id"] in faellig]
    if not buecher:
        return {"gestartet": False, "grund": "Keine Bücher gefunden, die gescannt werden müssen"}

    _reset_status()
    status["laeuft"] = True
    status["typ"] = ",".join(typen)
    status["gesamt"] = len(buecher)
    global _lauf
    _lauf = Anhalter()
    _lauf.beginne()
    aufgabe = asyncio.create_task(_rescan_worker(list(buecher), typen, _lauf))
    _aufgaben.add(aufgabe)
    aufgabe.add_done_callback(_aufgaben.discard)

    return {"gestartet": True, "anzahl": len(buecher)}


def abbrechen() -> dict:
    """Bricht den laufenden Rescan ab."""
    if not status["laeuft"]:
        return {"abgebrochen": False, "grund": "Kein Rescan aktiv"}
    status["laeuft"] = False
    _lauf.halte()
    return {"abgebrochen": True}


async def _rescan_worker(buecher: list, typen: list[str], lauf: Anhalter):
    """Hintergrund-Worker für den Rescan."""
    scan_cover = "cover" in typen
    scan_isbn = "isbn" in typen
    scan_metadaten = "metadaten" in typen
    scan_volltext = "volltext" in typen

    for i, book in enumerate(buecher):
        if lauf.gehalten:
            logger.info("Rescan abgebrochen bei %d/%d", i, len(buecher))
            return                              # abbrechen() hat den Stand schon gesetzt

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

            if scan_isbn and not hat_isbn:
                await _isbn_suchen(book, original, fmt)

            if original is not None and fehlt_text and await volltext.nachlesen(book["id"], book["hash"], original):
                status["volltext_extrahiert"] += 1

            # Fehlende Angaben aus den Quellen; den Takt hält der gemeinsame Abruf
            if scan_metadaten and not status["grund"]:
                if i % SAMMEL_HOECHSTENS == 0:
                    await lauf.bis(_vorwaermen(buecher[i:i + SAMMEL_HOECHSTENS]))
                if await lauf.bis(_angaben_ergaenzen(book)):
                    status["metadaten_aktualisiert"] += 1
            await asyncio.sleep(0.05)       # die übrige App kommt dran

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


async def _isbn_suchen(book: dict, original: Path | None, fmt: str) -> None:
    """Lauf "ISBN" für ein Buch: die ISBN aus den Angaben einer EPUB, sonst nach den Kandidaten im Text (isbnsuche/lauf.py).
    Ruhen die Quellen, fragt der Lauf sie für die übrigen Bücher nicht mehr; was nicht passt, kommt dann ungeprüft zur Wahl."""
    isbn = await asyncio.to_thread(isbnlauf.isbn_der_datei, original) if original is not None and fmt == "epub" else ""
    if not isbn:
        seiten = await isbnsuche.seiten(book, original)
        ergebnis = await isbnlauf.fuer_buch(book, seiten, fragen=not status["isbn_grund"])
        isbn = ergebnis.isbn
        status["isbn_zur_wahl"] += int(ergebnis.zur_wahl)
        status["isbn_ungeprueft"] += int(ergebnis.zur_wahl and ergebnis.ungeprueft)
        status["isbn_grund"] = status["isbn_grund"] or ergebnis.ruht
    if isbn:
        await db.execute("UPDATE books SET isbn = ?, updated_at = datetime('now') WHERE id = ?", (isbn, book["id"]))
        await db.commit()
        status["isbn_gefunden"] += 1
        logger.info("Rescan ISBN für %s: %s", book["id"], isbn)


async def _vorwaermen(buecher: list[dict]) -> None:
    """Die nächsten Bücher bei einer Quelle mit einer Sammelanfrage erfragen statt einzeln."""
    try:
        with hintergrund():
            await OpenLibrary().vorwaermen([b["isbn"] for b in buecher if b["isbn"] and _fehlende_angaben(b)])
    except QuelleFehler as f:
        logger.info("Sammelanfrage: %s", f.grund)


async def _umschlag(adresse: str) -> bytes | None:
    try:
        return await bilder.umschlag(adresse)
    except QuelleFehler as f:
        logger.info("Umschlag nicht geholt: %s", f.grund)
        return None


async def _werte(angaben: Angaben, fehlend: set[str], file_hash: str) -> dict[str, object]:
    """Spalte -> Wert für alles, was fehlt und gefunden wurde; ein Umschlag wird dabei abgelegt."""
    gefunden = {"titel": bereinige_titel(angaben.titel), "autoren": bereinige_autor(", ".join(angaben.autoren)), "verlag": bereinige_text(angaben.verlag, 200), "jahr": angaben.jahr,
                "sprache": angaben.sprache, "beschreibung": bereinige_text(angaben.beschreibung)}
    werte = {ANGABEN[f]: gefunden[f] for f in fehlend & gefunden.keys() if gefunden[f]}
    if "umschlag" in fehlend and angaben.umschlag and (bild := await _umschlag(angaben.umschlag)):
        save_cover(file_hash, bild)
        werte["cover_path"] = "cover.jpg"
    return werte


async def _angaben_ergaenzen(book: dict) -> bool:
    """Ergänzt leere Felder eines Buchs über seine ISBN. Vorhandenes bleibt, Kategorien entstehen hier nie (die kommen nur über
    den Vergleich von Hand). Ruhen die Quellen, endet dieser Teil des Laufs mit ihrem Grund."""
    aktuell = await db.fetch_one("SELECT * FROM books WHERE id = ?", (book["id"],))
    fehlend = _fehlende_angaben(aktuell) if aktuell and (aktuell["isbn"] or "").strip() else set()
    if not fehlend:
        return False
    with hintergrund():
        antwort = await auskunft.ergaenze(frage_aus(aktuell), fehlend)
        werte = await _werte(antwort.angaben, fehlend, book["hash"]) if antwort.angaben else {}
    if antwort.ruht and antwort.angaben is None:
        status["grund"] = ". ".join(antwort.hinweise)
    if werte:
        await db.execute(f"UPDATE books SET {', '.join(f'{k} = ?' for k in werte)}, updated_at = datetime('now') WHERE id = ?", (*werte.values(), book["id"]))
        await db.commit()
    return bool(werte)
