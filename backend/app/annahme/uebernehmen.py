"""Übernehmen aus der Vorschau (BF-80): erst bestätigen (Weg der Schnittstelle), dann führt die Annahme jede Datei weiter
(annahme/dienst.py): als neues Werk ins Regal, als weiteres Format zu einem Buch, als Begleitmaterial (BF-81).

Bestätigen prüft, ob alles zusammenpasst (gehört eine Datei zu einer anderen Aufnahme, muss die mit übernommen werden), merkt
die Zuordnung als endgültig und schickt die Dateien weiter. Was weggelassen wird oder nicht übernommen werden kann, bleibt im
Eingang (oder im Ordner, aus dem es kam), mit Hinweis; nichts wird von selbst weggeräumt.

`felder_setzen` schreibt die Felder der Zuordnung an das neue Buch: Art (wer sie bestimmt hat, wie beim Einordnen: Regel, KI
oder von Hand), Kategorien, Sammlung und Band, Sprache und die Etiketten des Profils, das übernommen hat."""

from __future__ import annotations

from backend.app.annahme.modelle import BUCH, MATERIAL, NUTZER, Zuordnung
from backend.app.annahme.vorschau import IN_ARBEIT, WARTET, VorschauFehlt, beruehrt, offene, rolle, zuordnung_aus
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.katalog.alt import ETIKETT_FARBE
from backend.app.models.grenzen import ETIKETT
from backend.app.services import sammlungen

BEHALTEN = ("ordner", "extern")                  # aus diesen Quellen bleibt die Datei, wo sie ist
QUELLE_DER_KATEGORIE = {"regel": "katalog-regel", "ki": "katalog-ki"}


class Unvollstaendig(ValueError):
    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


def datei_da(z: dict) -> bool:
    """Liegt zu der Aufnahme eine Datei (in der Kellerwolke, im Ordner, im Eingang auf dem Gerät)?"""
    eingang = settings.eingang_dir / str(z["id"])
    return bool(z["knoten"] or z["pfad"] or (eingang.is_dir() and any(eingang.iterdir())))


def liegt_noch(z: dict) -> str:
    return "Bleibt im Ordner" if z["quelle"] in BEHALTEN else "Bleibt im Eingang"


def _hinweis(anzahl: int, behalten: bool) -> str:
    if not anzahl:
        return ""
    wo = "im Ordner" if behalten else "im Eingang"
    return f"1 Datei blieb {wo}" if anzahl == 1 else f"{anzahl} Dateien blieben {wo}"


async def _abhaengig_pruefen(zeilen: list[dict], gewaehlt: set[int]) -> None:
    """Gehört eine Datei zu einer anderen Aufnahme (Format, Material), muss die mit übernommen werden oder schon im Regal sein."""
    for z in zeilen:
        zo = zuordnung_aus(z)
        if z["id"] not in gewaehlt or zo is None or zo.ziel is None or zo.ziel.aufnahme is None:
            continue
        if rolle(z, zo) not in (BUCH, MATERIAL) or (zo.art.wert != MATERIAL and zo.doppel.wahl != "format"):
            continue
        ziel = next((x for x in zeilen if x["id"] == zo.ziel.aufnahme), None)
        if ziel is None or (ziel["id"] not in gewaehlt and not ziel["buch_id"]):
            raise Unvollstaendig(f"{z['name']} gehört zu {zo.ziel.titel or 'einer anderen Datei'}: bitte beide übernehmen")


async def bestaetigen(nr: str, ids: list[int] | None, profil_id: str) -> int:
    """Übernimmt die gewählten Aufnahmen (ohne Wahl alle wartenden); liefert, wie viele weitergehen. Ist danach nichts mehr
    offen, ist die Vorschau übernommen, mit dem Hinweis, was liegen blieb."""
    v = await offene(nr)
    if v["stand"] != "offen":
        raise VorschauFehlt("Diese Vorschau ist schon erledigt")
    zeilen = await db.fetch_all("SELECT * FROM aufnahme WHERE vorschau = ? ORDER BY id", (nr,))
    alle = {z["id"] for z in zeilen}
    if ids is not None and (fremd := set(ids) - alle):
        raise VorschauFehlt(f"Diese Aufnahme gehört nicht zu der Vorschau: {', '.join(map(str, sorted(fremd)))}")
    gewaehlt = {z["id"] for z in zeilen if (ids is None or z["id"] in ids) and (z["stand"] == WARTET or z["stand"] in IN_ARBEIT)}
    await _abhaengig_pruefen(zeilen, gewaehlt)
    weiter = 0
    async with db.einheit():
        for z in zeilen:
            if z["id"] in gewaehlt:
                weiter += await _eine(z, profil_id)
        offen = await db.fetch_one(f"SELECT COUNT(*) AS n FROM aufnahme WHERE vorschau = ? AND stand IN ('{WARTET}', {', '.join(repr(s) for s in IN_ARBEIT)})",
                                   (nr,))
        if not offen["n"]:
            liegen = [z for z in await db.fetch_all("SELECT * FROM aufnahme WHERE vorschau = ? ORDER BY id", (nr,))
                      if z["stand"] in ("da", "format", "entpackt") and datei_da(z)]
            await db.execute("UPDATE vorschau SET stand = 'uebernommen', hinweis = ? WHERE id = ?",
                             (_hinweis(len(liegen), v["quelle"] in BEHALTEN), nr))
        await beruehrt(nr)
        await db.commit()                            # die Annahme liest über die gemeinsame Verbindung weiter
    return weiter


async def _eine(z: dict, profil_id: str) -> int:
    """Eine Aufnahme: weiter zur Station Regal (1) oder liegen lassen, mit Grund (0)."""
    zo = zuordnung_aus(z) or Zuordnung()
    r = rolle(z, zo)
    zo.bestaetigt, zo.von_profil = True, profil_id
    if r == "doppel":
        stand, text, schritt = "da", f"Weggelassen. {liegt_noch(z)}." if datei_da(z) else z["text"], 0
    elif r == "rest":
        stand, text, schritt = "format", f"Nicht übernommen: {zo.nicht or z['text']}. {liegt_noch(z)}.", 0
    elif r == "zip":
        return 0
    elif z["stand"] in IN_ARBEIT:                    # noch beim Hochladen oder Lesen: danach geht sie ohne Halt weiter
        await db.execute("UPDATE aufnahme SET zuordnung = ? WHERE id = ?", (zo.model_dump_json(), z["id"]))
        return 1
    else:
        lesen = r == BUCH and zo.doppel.wahl != "format" and not z["gelesen"]
        stand, text, schritt = ("liest", "Wartet auf das Lesen", 2) if lesen else ("regal", "Kommt ins Regal", 4)
    await db.execute("UPDATE aufnahme SET zuordnung = ?, stand = ?, schritt = ?, text = ?, geaendert_am = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                     (zo.model_dump_json(), stand, schritt, text, z["id"]))
    return int(stand in ("liest", "regal"))


# -- die Felder an das neue Buch --------------------------------------------------------------------------------------------

def _einordnung(zo: Zuordnung) -> tuple[str, str] | None:
    """Wer die Art bestimmt hat, wie beim Einordnen (services/einordnung.py); None: offen, dann ordnet die App später ein."""
    return {NUTZER: ("hand", ""), "regel": ("regel", zo.art.grund), "ki": ("ki", "")}.get(zo.art.herkunft or "")


async def felder_setzen(buch: int, zo: Zuordnung) -> None:
    """Die Zuordnung an das gerade eingetragene Buch, in einer Einheit."""
    async with db.einheit():
        if zo.art.wert not in ("", MATERIAL) and (wer := _einordnung(zo)):
            await db.execute("UPDATE books SET typ = ?, einordnung = ?, einordnung_grund = ?, gattung = COALESCE(?, gattung) WHERE id = ?",
                             ("" if zo.art.wert == BUCH else zo.art.wert, *wer, zo.gattung if zo.art.herkunft == "ki" else None, buch))
        for k in zo.kategorien.wert:
            await db.execute("INSERT OR IGNORE INTO book_categories (book_id, category_id, quelle) SELECT ?, id, ? FROM categories WHERE id = ?",
                             (buch, QUELLE_DER_KATEGORIE.get(zo.kategorien.herkunft or "", "manuell"), k))
        if zo.sammlung.wert and await db.fetch_one("SELECT 1 AS da FROM collections WHERE id = ?", (zo.sammlung.wert,)):
            if zo.band.wert.strip():
                await db.execute("UPDATE books SET sammlung_id = ?, band_nummer = ? WHERE id = ?", (zo.sammlung.wert, zo.band.wert.strip(), buch))
            else:
                await sammlungen.anhaengen(zo.sammlung.wert, [buch])
        if zo.sprache.wert and zo.sprache.herkunft in (NUTZER, "luecke"):
            await db.execute("UPDATE books SET language = ? WHERE id = ?", (zo.sprache.wert, buch))
        if zo.von_profil:
            for name in dict.fromkeys(e[:ETIKETT] for e in zo.etiketten.wert if e.strip()):
                await db.execute("""INSERT INTO book_labels (profil_id, book_id, color, name) SELECT ?, ?, ?, ?
                                    WHERE NOT EXISTS (SELECT 1 FROM book_labels WHERE profil_id = ? AND book_id = ? AND name = ? COLLATE NOCASE)""",
                                 (zo.von_profil, buch, ETIKETT_FARBE, name, zo.von_profil, buch, name))


async def ziel_buch(zo: Zuordnung) -> int | None:
    """Das Buch, zu dem eine Datei gehört: im Bestand oder das Buch der anderen Aufnahme, sobald es im Regal ist."""
    if zo.ziel is None:
        return None
    if zo.ziel.buch_id:
        return zo.ziel.buch_id
    z = await db.fetch_one("SELECT buch_id FROM aufnahme WHERE id = ?", (zo.ziel.aufnahme,))
    return z["buch_id"] if z else None

