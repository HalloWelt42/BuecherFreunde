"""Kandidaten aus dem Bestand (BF-119): über die ISBN und über die Wörter des Titels im Suchindex, nur Bücher, die das Profil
sieht. Gestuft wird in `regeln.py`; hier wird nur gesucht, geladen und zusammengestellt.

Eine Seite schickt alle ihre Bücher auf einmal; je Buch fragt der Dienst den Suchindex einmal (die Titelwörter, ein Treffer
in einem davon genügt), die ISBN aller eigenen Bücher liest er einmal je Anfrage. Die Angaben fürs Zeigen holt er zum Schluss
gesammelt, nur für die Treffer."""

from __future__ import annotations

import html
import re
from collections import defaultdict

from backend.app.bestandsabgleich import regeln
from backend.app.bestandsabgleich.modelle import (FUNDARTEN, TREFFER_DER_SUCHE, TREFFER_JE_ANGEBOT, Abgleichantwort, Abgleichfrage, Angebot,
                                                  Buchkurz, Ergebnis, Suchantwort, Suchfrage, Treffer)
from backend.app.core.database import db
from backend.app.familie import lesestand
from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht
from backend.app.models.book import umschlag_zeigen
from backend.app.quellen.abgleich import haupttitel, norm
from backend.app.services.autorennamen import zerlegen
from backend.app.services.storage import umschlag_stand

KANDIDATEN_JE_FRAGE = 25           # so viele Bücher holt eine Frage an den Suchindex höchstens
WOERTER_JE_FRAGE = 5               # die längsten Wörter des Titels
BESCHREIBUNG_ZEICHEN = 420
_FUELLWOERTER = frozenset({"der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines", "und", "oder", "im", "in", "am",
                           "an", "auf", "aus", "bei", "mit", "von", "vom", "zu", "zum", "zur", "fur", "uber", "the", "of", "and", "a",
                           "an", "to", "for", "on", "le", "la", "les", "de", "du", "et"})
_TAG = re.compile(r"<[^>]+>")


def suchwoerter(text: str) -> list[str]:
    """Die tragenden Wörter eines Titels für den Suchindex (ohne Füllwörter, die längsten zuerst)."""
    worte = [w for w in norm(haupttitel(regeln.ohne_klammern(text))).split() if len(w) > 2 and w not in _FUELLWOERTER]
    if not worte:
        worte = [w for w in norm(text).split() if len(w) > 1]
    return sorted(dict.fromkeys(worte), key=len, reverse=True)[:WOERTER_JE_FRAGE]


def _fts(worte: list[str], spalten: str) -> str:
    return f"{{{spalten}}} : (" + " OR ".join(f'"{w}"' for w in worte) + ")"


async def _aus_dem_index(worte: list[str], spalten: str, sicht: Sicht) -> list[int]:
    if not worte:
        return []
    bedingung, werte = sicht.bedingung("b.id")
    zeilen = await db.fetch_all(f"""SELECT b.id FROM buch_fts JOIN books b ON b.id = buch_fts.rowid
                                    WHERE buch_fts MATCH ? AND {bedingung} ORDER BY rank LIMIT ?""",
                                (_fts(worte, spalten), *werte, KANDIDATEN_JE_FRAGE))
    return [z["id"] for z in zeilen]


async def _isbn_verzeichnis(sicht: Sicht) -> dict[str, list[int]]:
    bedingung, werte = sicht.bedingung("b.id")
    verzeichnis: dict[str, list[int]] = defaultdict(list)
    for z in await db.fetch_all(f"SELECT b.id, b.isbn FROM books b WHERE COALESCE(b.isbn, '') != '' AND {bedingung}", werte):
        for nummer in regeln.isbn13(z["isbn"]):
            verzeichnis[nummer].append(z["id"])
    return verzeichnis


async def _bestand(ids: set[int]) -> dict[int, regeln.Bestandsbuch]:
    if not ids:
        return {}
    marken = ",".join("?" * len(ids))
    formate: dict[int, list[str]] = defaultdict(list)
    for z in await db.fetch_all(f"SELECT buch_id, format FROM buch_datei WHERE buch_id IN ({marken}) ORDER BY haupt DESC, format", tuple(ids)):
        formate[z["buch_id"]].append(z["format"])
    zeilen = await db.fetch_all(f"SELECT id, title, author, year, isbn FROM books WHERE id IN ({marken})", tuple(ids))
    return {z["id"]: regeln.Bestandsbuch(id=z["id"], title=z["title"] or "", author=z["author"] or "", autoren=tuple(zerlegen(z["author"] or "")),
                                         year=z["year"], isbn13=regeln.isbn13(z["isbn"] or ""), formate=tuple(formate[z["id"]]))
            for z in zeilen}


def _kurz(text: str) -> str:
    t = " ".join(html.unescape(_TAG.sub(" ", text or "")).split())
    if len(t) <= BESCHREIBUNG_ZEICHEN:
        return t
    return t[:BESCHREIBUNG_ZEICHEN].rsplit(" ", 1)[0] + " ..."


async def _zum_zeigen(ids: set[int], profil: Profil) -> dict[int, Buchkurz]:
    """Was der Einblick zeigt, gesammelt für alle Treffer."""
    if not ids:
        return {}
    marken = ",".join("?" * len(ids))
    werte = tuple(ids)
    regale: dict[int, list[str]] = defaultdict(list)
    for z in await db.fetch_all(f"""SELECT x.book_id, c.name FROM book_categories x JOIN categories c ON c.id = x.category_id
                                    WHERE x.book_id IN ({marken}) AND c.art IN ('regal', 'kategorie')
                                    ORDER BY c.art != 'regal', c.name COLLATE NOCASE""", werte):
        regale[z["book_id"]].append(z["name"])
    formate: dict[int, list[str]] = defaultdict(list)
    for z in await db.fetch_all(f"SELECT buch_id, format FROM buch_datei WHERE buch_id IN ({marken}) ORDER BY haupt DESC, format", werte):
        formate[z["buch_id"]].append(z["format"].upper())
    stand = {z["book_id"]: z for z in await db.fetch_all(
        f"SELECT book_id, reading_position, fertig_am FROM user_book_data WHERE profil_id = ? AND book_id IN ({marken})", (profil.id, *werte))}
    aus: dict[int, Buchkurz] = {}
    for b in await db.fetch_all(f"SELECT * FROM books WHERE id IN ({marken})", werte):
        s = stand.get(b["id"]) or {}
        seiten = b.get("page_count") or 0
        aus[b["id"]] = Buchkurz(
            id=b["id"], title=b["title"] or "", author=b["author"] or "", year=b["year"], publisher=b["publisher"] or "", isbn=b["isbn"] or "",
            beschreibung=_kurz(b["description"]), formate=formate[b["id"]], regale=regale[b["id"]][:2], typ=b.get("typ") or "",
            gattung=b.get("gattung") or "", file_format=b["file_format"] or "", cover_path=b["cover_path"] or "",
            umschlag=umschlag_zeigen(b.get("umschlag_wahl") or "", bool(b.get("umschlag_schlicht"))), cover_stand=umschlag_stand(b["hash"]),
            gelesen=lesestand.anteil(s.get("reading_position"), seiten),
            fertig=bool(s.get("fertig_am")) or lesestand.fertig(s.get("reading_position"), seiten))
    return aus


def _beste(funde: list[tuple[regeln.Einstufung, regeln.Bestandsbuch]], hoechstens: int) -> list[tuple[regeln.Einstufung, regeln.Bestandsbuch]]:
    return sorted(funde, key=lambda f: (FUNDARTEN.index(f[0].art), -f[0].naehe, f[1].id))[:hoechstens]


async def abgleichen(frage: Abgleichfrage, sicht: Sicht, profil: Profil) -> Abgleichantwort:
    isbn = await _isbn_verzeichnis(sicht) if any(a.isbn for a in frage.angebote) else {}
    kandidaten: dict[int, set[int]] = {}
    for a in frage.angebote:
        ids = {b for n in regeln.isbn13(a.isbn) for b in isbn.get(n, [])}
        ids |= set(await _aus_dem_index(suchwoerter(a.titel), "title", sicht))
        kandidaten[a.nr] = ids
    bestand = await _bestand(set().union(*kandidaten.values()) if kandidaten else set())
    gewaehlt: dict[int, tuple[Angebot, list[tuple[regeln.Einstufung, regeln.Bestandsbuch]]]] = {}
    for a in frage.angebote:
        funde = [(e, b) for i in kandidaten[a.nr] if (b := bestand.get(i)) and (e := regeln.einstufen(a, b, frage.aehnlich_ab))]
        if funde:
            gewaehlt[a.nr] = (a, _beste(funde, TREFFER_JE_ANGEBOT))
    zeigen = await _zum_zeigen({b.id for _, funde in gewaehlt.values() for _, b in funde}, profil)
    return Abgleichantwort(geprueft=len(frage.angebote), ergebnisse=[
        Ergebnis(nr=nr, treffer=[Treffer(buch=zeigen[b.id], art=e.art, naehe=round(e.naehe, 3), grund=e.grund, vergleich=regeln.vergleich(a, b))
                                 for e, b in funde if b.id in zeigen])
        for nr, (a, funde) in gewaehlt.items()])


async def suchen(frage: Suchfrage, sicht: Sicht, profil: Profil) -> Suchantwort:
    ids = set(await _aus_dem_index(suchwoerter(frage.text), "title author", sicht))
    bestand = await _bestand(ids)
    funde = [(e, b) for b in bestand.values() if (e := regeln.freitext(frage.text, b, frage.aehnlich_ab))]
    beste = _beste(funde, TREFFER_DER_SUCHE)
    zeigen = await _zum_zeigen({b.id for _, b in beste}, profil)
    anfrage = Angebot(nr=0, titel=frage.text)
    return Suchantwort(treffer=[Treffer(buch=zeigen[b.id], art=e.art, naehe=round(e.naehe, 3), grund=e.grund, vergleich=regeln.vergleich(anfrage, b))
                                for e, b in beste if b.id in zeigen])
