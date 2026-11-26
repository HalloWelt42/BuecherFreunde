"""Die Begriffsliste in der Datenbank (BF-71, Tabelle `begriff`): je Buch und eine für alle Bücher (`buch_id` leer).

Herkunft: `vorgabe` (aus uebersetzung/vorgaben.json, einmal je Fassung der Vorgaben eingespielt), `regel` und `ki` (vom Lauf
beim ersten Übersetzen eines Buchs), `hand` (angelegt oder geändert vom Nutzer; daran ändert kein Lauf mehr etwas). Was
für ein Buch gilt: die Liste für alle, darüber die des Buchs (begriffe.gelten). Eine Änderung markiert nur die Blöcke zum
Neuübersetzen, in denen der Begriff vorkommt (fassungen.neu_markieren)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from backend.app.core.database import db
from backend.app.models.fassung import BegriffAenderung, BegriffEintrag, BegriffNeu
from backend.app.services import fassungen
from backend.app.uebersetzung import begriffe as regeln
from backend.app.uebersetzung import marken
from backend.app.uebersetzung.modelle import Begriff, Kandidat

logger = logging.getLogger("buecherfreunde.begriffsliste")
VORGABEN = Path(__file__).resolve().parent.parent / "uebersetzung" / "vorgaben.json"
VORGABEN_STAND = "begriffe_vorgaben"                 # Schlüssel in app_settings: die zuletzt eingespielte Fassung
SPALTEN = "id, englisch, deutsch, bleibt, herkunft, stellen, grund, art"


def _eintrag(z: dict) -> BegriffEintrag:
    return BegriffEintrag(**{**z, "bleibt": bool(z["bleibt"])})


async def liste(buch_id: int | None) -> list[BegriffEintrag]:
    """Die Einträge eines Buchs, ohne Buch die für alle Bücher."""
    wo = "buch_id = ?" if buch_id is not None else "buch_id IS NULL"
    zeilen = await db.fetch_all(f"SELECT {SPALTEN} FROM begriff WHERE {wo} ORDER BY lower(englisch)",
                                (buch_id,) if buch_id is not None else ())
    return [_eintrag(z) for z in zeilen]


async def eintrag(bid: int) -> tuple[BegriffEintrag, int | None] | None:
    z = await db.fetch_one(f"SELECT {SPALTEN}, buch_id FROM begriff WHERE id = ?", (bid,))
    return (_eintrag({k: v for k, v in z.items() if k != "buch_id"}), z["buch_id"]) if z else None


async def gelten(buch_id: int) -> list[Begriff]:
    """Die Liste, die für ein Buch gilt."""
    def als(e: BegriffEintrag) -> Begriff:
        return Begriff(englisch=e.englisch, deutsch=e.deutsch, bleibt=e.bleibt, art=e.art)
    return regeln.gelten([als(e) for e in await liste(None)], [als(e) for e in await liste(buch_id)])


async def vorhandene(buch_id: int) -> set[str]:
    """Die englischen Begriffe (klein), die für ein Buch schon in einer Liste stehen."""
    return {b.englisch.lower() for b in await gelten(buch_id)}


async def kandidaten_merken(buch_id: int, kandidaten: list[Kandidat]) -> int:
    """Vorschläge von Regel oder KI in die Liste des Buchs; was schon dasteht, bleibt unberührt."""
    vorher = (await db.fetch_one("SELECT count(*) AS n FROM begriff WHERE buch_id = ?", (buch_id,)))["n"]
    await db.execute_many("INSERT OR IGNORE INTO begriff (buch_id, englisch, deutsch, bleibt, herkunft, stellen, grund) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          [(buch_id, k.englisch, k.deutsch, int(k.bleibt), k.herkunft, k.stellen, k.grund) for k in kandidaten])
    return (await db.fetch_one("SELECT count(*) AS n FROM begriff WHERE buch_id = ?", (buch_id,)))["n"] - vorher


async def _stellen(buch_id: int | None, englisch: str) -> int:
    """Wie oft der Begriff in den Blöcken des Buchs steht (ohne Buch: 0, gezählt wird je Buch)."""
    if buch_id is None:
        return 0
    f = await fassungen.zum_buch(buch_id, "de")
    if f is None:
        return 0
    return regeln.stellen(englisch, [marken.klartext(z.vorlage) for z in await fassungen.bloecke(f.id)])


async def _eigene_buecher(englisch: list[str]) -> frozenset[int]:
    """Bücher mit einem eigenen Eintrag zu einem der Begriffe: dort gilt eine Änderung der allgemeinen Liste nicht."""
    if not englisch:
        return frozenset()
    zeilen = await db.fetch_all(f"SELECT DISTINCT buch_id FROM begriff WHERE buch_id IS NOT NULL AND lower(englisch) IN ({','.join('?' * len(englisch))})",
                                tuple(e.lower() for e in englisch))
    return frozenset(z["buch_id"] for z in zeilen)


async def _markieren(buch_id: int | None, englisch: list[str]) -> None:
    ausser = await _eigene_buecher(englisch) if buch_id is None else frozenset()
    n = await fassungen.neu_markieren(buch_id, englisch, ausser)
    if n:
        logger.info("Begriffsliste geändert (%s): %d Blöcke werden neu übersetzt", ", ".join(englisch), n)


async def anlegen(buch_id: int | None, neu: BegriffNeu) -> BegriffEintrag:
    c = await db.execute("INSERT INTO begriff (buch_id, englisch, deutsch, bleibt, art, herkunft, stellen, grund) VALUES (?, ?, ?, ?, ?, 'hand', ?, ?)",
                         (buch_id, neu.englisch, "" if neu.bleibt else neu.deutsch, int(neu.bleibt), neu.art,
                          await _stellen(buch_id, neu.englisch), neu.grund))
    await _markieren(buch_id, [neu.englisch])
    e = await eintrag(c.lastrowid)
    assert e is not None
    return e[0]


async def aendern(bid: int, aenderung: BegriffAenderung) -> BegriffEintrag | None:
    """Ändern macht den Eintrag zu einem von Hand; danach muss er bleiben oder eine deutsche Form haben (ValueError)."""
    vorher = await eintrag(bid)
    if vorher is None:
        return None
    alt, buch_id = vorher
    neu = alt.model_copy(update=aenderung.model_dump(exclude_none=True))
    if neu.bleibt:
        neu.deutsch = ""
    elif not neu.deutsch:
        raise ValueError("Ein Begriff bleibt englisch oder hat eine deutsche Form")
    stellen = await _stellen(buch_id, neu.englisch) if neu.englisch != alt.englisch else alt.stellen
    await db.execute("UPDATE begriff SET englisch = ?, deutsch = ?, bleibt = ?, art = ?, grund = ?, stellen = ?, herkunft = 'hand', "
                     "geaendert_am = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                     (neu.englisch, neu.deutsch, int(neu.bleibt), neu.art, neu.grund, stellen, bid))
    await _markieren(buch_id, list(dict.fromkeys([alt.englisch, neu.englisch])))
    e = await eintrag(bid)
    return e[0] if e else None


async def loeschen(bid: int) -> bool:
    vorher = await eintrag(bid)
    if vorher is None:
        return False
    await db.execute("DELETE FROM begriff WHERE id = ?", (bid,))
    await _markieren(vorher[1], [vorher[0].englisch])
    return True


async def vorgaben_einspielen() -> int:
    """Die allgemeine Liste aus vorgaben.json, einmal je Fassung der Datei; was der Nutzer gelöscht hat, kommt erst mit
    einer neuen Fassung wieder. Gibt zurück, wie viele Einträge neu sind."""
    daten = json.loads(VORGABEN.read_text(encoding="utf-8"))
    stand = await db.fetch_one("SELECT value FROM app_settings WHERE key = ?", (VORGABEN_STAND,))
    if stand is not None and stand["value"] == str(daten["fassung"]):
        return 0
    zeilen = [(e, d, int(not d), "begriff") for e, d in daten.get("begriffe", {}).items()]
    zeilen += [(e, d, int(not d), "einheit") for e, d in daten.get("einheiten", {}).items()]
    vorher = (await db.fetch_one("SELECT count(*) AS n FROM begriff WHERE buch_id IS NULL"))["n"]
    async with db.einheit():
        await db.execute_many("INSERT OR IGNORE INTO begriff (buch_id, englisch, deutsch, bleibt, art, herkunft) VALUES (NULL, ?, ?, ?, ?, 'vorgabe')",
                              zeilen)
        await db.execute("INSERT INTO app_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                         (VORGABEN_STAND, str(daten["fassung"])))
    return (await db.fetch_one("SELECT count(*) AS n FROM begriff WHERE buch_id IS NULL"))["n"] - vorher
