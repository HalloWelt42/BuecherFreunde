"""Anbieterweg für Fundus (Protokoll fundus-anbieter/1): Fundus fragt den Bücherbestand, statt ihn doppelt einzulesen.

Zugang nur mit dem App-Schlüssel der Kellerwolke einer erlaubten App (`core/app_zugang.py`). Alles ist Nachschlagen in
fertigen Daten (Suchindex, fulltext.txt, Angaben), keine Rechnung; die Angaben bleiben hier die Wahrheit.

| Weg | Inhalt |
|---|---|
| GET /api/v1/fundus/steckbrief | was der Anbieter kann |
| GET /api/v1/fundus/suche?q=&n=&ab= | Treffer je Buch mit der besten Seite, Ausschnitt, Umschlag und Pfad in den Leser |
| GET /api/v1/fundus/inhalt/{buch}?von=&bis= | Seiten des Volltexts (Seite N wie im Leser) |
| GET /api/v1/fundus/bestand?ab=&n= | Angaben aller Bücher seitenweise, mit Lesestand und Zahl der Notizen |
| GET /api/v1/fundus/umschlag/{buch} | der Umschlag |
"""

from __future__ import annotations

import asyncio
import html
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.api.books import get_cover
from appkern.anmeldung import Konto

from backend.app.core.auth import app_pruefen
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services.search import search_books, search_count
from backend.app.services.seiten import seiten_aus
from backend.app.services.storage import get_sidecar_path, load_fulltext

router = APIRouter(prefix="/api/v1/fundus", tags=["Fundus"])

PROTOKOLL = "fundus-anbieter/1"
HOECHSTENS = 50
AUSZUG_ZEICHEN = 320
SEITEN_JE_BUCH = 3
_MARKE = re.compile(r"</?(mark|b)>")
_WORT = re.compile(r"\w{3,}", re.UNICODE)
_FILTER = re.compile(r"\b(autor|author|format|datum):(\"[^\"]*\"|\S+)", re.IGNORECASE)
_LEER = {"and", "not", "der", "die", "das", "und", "oder", "ein", "eine", "einer", "eines", "wie", "was", "wer", "wo",
         "warum", "welche", "welcher", "welches", "ist", "sind", "mit", "von", "für", "auf", "aus", "bei", "den", "dem",
         "des", "im", "in", "zu", "zum", "zur", "über", "nach", "the", "of", "to", "is", "what", "how", "about", "steht",
         "buch", "buecher", "bücher", "seite"}


def _woerter(q: str) -> list[str]:
    ohne_filter = _FILTER.sub(" ", q)
    return [w for w in dict.fromkeys(w.lower() for w in _WORT.findall(ohne_filter)) if w not in _LEER]


def _filter(q: str) -> str:
    return " ".join(m.group(0) for m in _FILTER.finditer(q))


def _reiner(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_MARKE.sub("", text or ""))).strip()


def _beste_seiten(seiten: list[str], woerter: list[str]) -> list[tuple[int, int, int]]:
    """(Seite ab 1, Zahl der Wörter darauf, erste Stelle) der besten Seiten: zuerst die mit den meisten verschiedenen
    Wörtern, dann die mit den meisten Vorkommen."""
    if not woerter:
        return []
    muster = [re.compile(re.escape(w), re.IGNORECASE) for w in woerter]
    wertung = []
    for nr, seite in enumerate(seiten, 1):
        funde = [m.search(seite) for m in muster]
        verschiedene = sum(1 for f in funde if f)
        if not verschiedene:
            continue
        vorkommen = sum(len(m.findall(seite)) for m in muster)
        erste = min(f.start() for f in funde if f)
        wertung.append((verschiedene, vorkommen, -nr, nr, erste))
    wertung.sort(reverse=True)
    return [(nr, verschiedene, erste) for verschiedene, _v, _n, nr, erste in wertung[:SEITEN_JE_BUCH]]


def _auszug(seite: str, stelle: int) -> str:
    anfang = max(0, stelle - AUSZUG_ZEICHEN // 3)
    stueck = re.sub(r"\s+", " ", seite[anfang: anfang + AUSZUG_ZEICHEN]).strip()
    return ("..." if anfang > 0 else "") + stueck + ("..." if anfang + AUSZUG_ZEICHEN < len(seite) else "")


def _leserpfad(buch: int, seite: int | None, begriff: str) -> str:
    teile = [f"page={seite}"] if seite else []
    if begriff:
        teile.append(f"q={quote(begriff)}")
    return f"/book/{buch}/read" + (f"?{'&'.join(teile)}" if teile else "")


async def _buch(buch: int) -> dict:
    zeile = await db.fetch_one("SELECT id, hash, title, author, page_count, year, language, file_format FROM books WHERE id = ?",
                               (buch,))
    if not zeile:
        raise HTTPException(404, "Buch nicht gefunden")
    return dict(zeile)


async def _seiten(zeile: dict) -> list[str]:
    text = await asyncio.to_thread(load_fulltext, zeile["hash"])
    return seiten_aus(text or "", zeile["page_count"])


@router.get("/steckbrief")
async def steckbrief(_app: Konto = Depends(app_pruefen)):
    gesamt = await db.fetch_one("SELECT COUNT(*) AS n FROM books")
    return {
        "protokoll": PROTOKOLL, "kennung": "buecherfreunde", "name": "BücherFreunde", "fassung": settings.version,
        "zweck": "Der Bücherbestand: Volltextsuche in den Büchern mit Seite, Ausschnitt und Umschlag; Seiten lesen.",
        "eignung": ["buecher", "gruendlich"], "sprachen": [], "arten": ["buch"],
        "suche": {"hoechstens": HOECHSTENS, "felder": ["titel", "autor", "seite", "auszug", "umschlag"],
                  "filter": ["autor:", "format:", "datum:"], "verknuepfung": "alle Wörter, sonst eines davon"},
        "inhalt": True, "bestand": gesamt["n"] if gesamt else 0,
    }


@router.get("/suche")
async def suche(q: str = Query(..., min_length=1, max_length=500), n: int = Query(10, ge=1, le=HOECHSTENS),
                ab: int = Query(0, ge=0), _app: Konto = Depends(app_pruefen)):
    """Treffer je Buch: zuerst alle Wörter (Suchindex des Bestands), gibt es so keine, dann eines davon. Je Buch die
    besten Seiten aus fulltext.txt mit Ausschnitt."""
    beginn = time.monotonic()
    woerter = _woerter(q)
    verknuepfung = "alle"
    eigene_syntax = '"' in q or "*" in q or re.search(r"\b(AND|OR|NOT)\b", q)
    erste = q if eigene_syntax or not woerter else " ".join(woerter) + (f" {_filter(q)}" if _filter(q) else "")
    ergebnisse, _ = await search_books(erste, n, ab)
    gesamt = await search_count(erste) if ergebnisse else 0
    if not ergebnisse and len(woerter) > 1:
        oder = " OR ".join(woerter) + (f" {_filter(q)}" if _filter(q) else "")
        ergebnisse, _ = await search_books(oder, n, ab)
        gesamt = await search_count(oder) if ergebnisse else 0
        verknuepfung = "eines"
    begriff = " ".join(woerter[:3])
    treffer = []
    hoechste = max((r.relevance for r in ergebnisse), default=0.0) or 1.0
    for r in ergebnisse:
        zeile = await _buch(r.book_id)
        seiten = await _seiten(zeile)
        beste = _beste_seiten(seiten, woerter)
        seite, stelle = (beste[0][0], beste[0][2]) if beste else (None, 0)
        auszug = _auszug(seiten[seite - 1], stelle) if seite else _reiner(r.snippet)
        treffer.append({
            "kennung": f"{r.book_id}:{seite or 0}", "buch": r.book_id, "titel": r.title, "autor": r.author, "art": "buch",
            "auszug": auszug, "seite": seite, "weitere_seiten": [b[0] for b in beste[1:]], "seiten_gesamt": len(seiten),
            "wann": zeile["year"], "sprache": zeile["language"] or "", "format": zeile["file_format"],
            "wertung": round(r.relevance / hoechste, 4), "umschlag": f"/api/v1/fundus/umschlag/{r.book_id}",
            "verweise": [{"art": "app", "titel": f"Im Leser an Seite {seite} öffnen" if seite else "Im Leser öffnen",
                          "pfad": _leserpfad(r.book_id, seite, begriff)},
                         {"art": "app", "titel": "Buch ansehen", "pfad": f"/book/{r.book_id}"}],
        })
    return {"treffer": treffer, "gesamt": gesamt, "verknuepfung": verknuepfung, "woerter": woerter,
            "dauer_ms": round((time.monotonic() - beginn) * 1000), "stand": datetime.now(timezone.utc).isoformat()}


@router.get("/inhalt/{buch}")
async def inhalt(buch: int, von: int = Query(1, ge=1), bis: int | None = Query(None, ge=1),
                 _app: Konto = Depends(app_pruefen)):
    """Seiten von `von` bis `bis` (ohne `bis`: bis zum Ende). Seite N ist die N-te Seite der Datei."""
    zeile = await _buch(buch)
    seiten = await _seiten(zeile)
    ende = min(bis or len(seiten), len(seiten))
    return {"buch": buch, "titel": zeile["title"], "autor": zeile["author"], "seitenart": "dateiseiten",
            "seiten_gesamt": len(seiten), "seiten": [{"seite": nr, "text": seiten[nr - 1]} for nr in range(von, ende + 1)]}


@router.get("/bestand")
async def bestand(ab: int = Query(0, ge=0), n: int = Query(500, ge=1, le=2000), _app: Konto = Depends(app_pruefen)):
    """Angaben aller Bücher nach Kennung, seitenweise; `lesestand`: es gibt einen Lesestand, `notizen`: Notizen und
    Markierungen zusammen."""
    gesamt = await db.fetch_one("SELECT COUNT(*) AS n FROM books")
    zeilen = await db.fetch_all(
        """SELECT b.id, b.hash, b.title, b.author, b.isbn, b.publisher, b.year, b.language, b.description, b.page_count,
                  b.file_format, b.updated_at,
                  COALESCE(u.reading_position, '') AS lesestand, u.last_read_at,
                  (SELECT COUNT(*) FROM book_notes n WHERE n.book_id = b.id)
                  + (SELECT COUNT(*) FROM book_highlights h WHERE h.book_id = b.id) AS notizen
           FROM books b LEFT JOIN user_book_data u ON u.book_id = b.id
           ORDER BY b.id LIMIT ? OFFSET ?""", (n, ab))
    buecher = []
    for z in zeilen:
        volltext = get_sidecar_path(z["hash"], "fulltext.txt")
        buecher.append({
            "buch": z["id"], "titel": z["title"], "autor": z["author"], "isbn": z["isbn"] or "", "verlag": z["publisher"] or "",
            "jahr": z["year"], "sprache": z["language"] or "", "beschreibung": z["description"] or "",
            "seiten": z["page_count"] or 0, "format": z["file_format"], "geaendert": z["updated_at"],
            "volltext_zeichen": volltext.stat().st_size if volltext.exists() else 0,
            "lesestand": bool(z["lesestand"] or z["last_read_at"]), "zuletzt_gelesen": z["last_read_at"],
            "notizen": z["notizen"] or 0,
        })
    return {"gesamt": gesamt["n"] if gesamt else 0, "ab": ab, "buecher": buecher}


@router.get("/umschlag/{buch}")
async def umschlag(buch: int, _app: Konto = Depends(app_pruefen)):
    return await get_cover(buch, _token="")
