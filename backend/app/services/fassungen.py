"""Fassungen eines Buchs (BF-71): die deutsche Fassung als eigene Datei neben dem Original, mit ihrem Lauf in eigenen
Tabellen (core/database.py): `fassung` (Stand, Modell, Ablage, Zeit), `uebersetzung_kapitel` und `uebersetzung_block` (je
Block Vorlage, Übersetzung, Stand, Befunde, Versuche, beim PDF Seite und Lage im Original). An den Blöcken setzt der Lauf nach
jedem Halt fort (services/uebersetzungslauf.py); dieselbe Zerlegung ergibt dieselben Kennungen (uebersetzung/werk.py: EPUB
und PDF, die deutsche Fassung ist immer ein EPUB). Die Seiten eines PDF tragen in der Fassung die Beschriftungen, die
BücherFreunde überall zeigt (services/seiten.py).

Stand einer Fassung: laeuft, pause, teilweise (abgebrochen, Fertiges bleibt), fertig, fehler (ein Mensch ist gefragt).
Stand eines Blocks: wartet, uebersetzt (feste Prüfungen bestanden, wartet auf den Prüfer), nacharbeit, bestanden,
nachgearbeitet, offen (im Original, im Bericht), angenommen (offen und vom Nutzer angenommen), gesetzt (Text des Nutzers).
Die Reparaturen eines Blocks gehören zu seiner Übersetzung: eine neue Antwort der KI bringt ihre eigenen mit, ein Text des
Nutzers und neu Übersetzen nehmen sie weg.

`aenderungen` zählt jede Änderung an Blöcken, `gesetzt` den Stand, den die abgelegte Datei zeigt; weichen sie ab, wird neu
gesetzt und abgelegt. `geprueft_mit` nennt die Fassung der festen Prüfungen samt Grenzen, mit der die Blöcke geprüft sind;
weicht sie ab, prüft der Lauf neu (uebersetzungslauf.py). Jede Fassung spricht den Leser mit ihrer `anrede` an, beim Anlegen
gewählt. Das Original bleibt immer unverändert."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Sequence
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.models.fassung import IN_ARBEIT, MIT_DEUTSCH, VON_DER_KI, Blockstand, Stand
from backend.app.services.seiten import buch_seiten
from backend.app.services.storage import get_original_file
from backend.app.uebersetzung import marken
from backend.app.uebersetzung.anweisungen import FASSUNG as ANWEISUNG
from backend.app.uebersetzung.begriffe import kommt_vor
from backend.app.uebersetzung.modelle import Anrede, Befund, Begriff, Block, Laengengrenzen, Reparatur
from backend.app.uebersetzung.pruefen import FASSUNG as PRUEF_FASSUNG
from backend.app.uebersetzung.pruefen import pruefen
from backend.app.uebersetzung.setzen import Hinweis, Satz, Uebersetzt
from backend.app.uebersetzung.werk import FORMATE, Werk, zerlegen
from backend.app.uebersetzung.zeichen import gerade

logger = logging.getLogger("buecherfreunde.fassungen")

ZERLEGEN_FASSUNG = 2                        # steigt sie (andere Regeln beim Zerlegen), wird jede Fassung neu zerlegt
NOCH_NICHT = "Im Original: noch nicht übersetzt"
NICHT_BESTANDEN = "Im Original: die Übersetzung hat die Prüfung nicht bestanden"
SPRACHE_IN_WORTEN = {"en": "Englischen"}


class Buchangaben(BaseModel):
    id: int
    hash: str
    title: str = ""
    author: str = ""
    language: str | None = ""
    file_format: str = ""
    file_name: str = ""
    page_count: int | None = 0

    @property
    def format(self) -> str:
        return (self.file_format or "").lower().lstrip(".")


class FassungZeile(BaseModel):
    id: int
    buch_id: int
    sprache: str
    aus_sprache: str
    stand: Stand
    grund: str = ""
    zerlegt: str = ""
    nicht_lesbar: list[str] = Field(default_factory=list)
    begriffe_fertig: bool = False
    begriffe_text: str = ""
    woerter: int = 0
    aenderungen: int = 0
    gesetzt: int = -1
    datei: str = ""
    knoten: str | None = None
    modell: str = ""
    pruefmodell: str = ""
    anweisung: int = 0
    anrede: Anrede = "du"
    geprueft_mit: str = ""
    pruefer_verworfen: int = 0
    begonnen: str | None = None
    bisher_s: float = 0
    angelegt_am: str
    geaendert_am: str

    @property
    def datei_aktuell(self) -> bool:
        return bool(self.datei) and self.gesetzt == self.aenderungen


class KapitelZeile(BaseModel):
    nr: int
    titel: str = ""
    datei: str = ""
    bloecke: int = 0
    woerter: int = 0
    dauer_s: float = 0


class BlockZeile(BaseModel):
    kennung: str
    kapitel: int
    nr: int
    art: str
    stufe: int = 0
    pruefsumme: str
    vorlage: str
    woerter: int = 0
    uebersetzung: str = ""
    stand: Blockstand = "wartet"
    befunde: list[Befund] = Field(default_factory=list)
    reparaturen: list[Reparatur] = Field(default_factory=list)   # was an der Übersetzung berichtigt ist (pruefen.reparieren)
    versuche: int = 0
    nacharbeiten: int = 0
    geprueft: bool = False
    seite: int | None = None                         # beim PDF: Dateiseite im Original
    seite_gedruckt: str = ""
    lage: list[float] = Field(default_factory=list)

    def als_block(self) -> Block:
        return Block(kennung=self.kennung, kapitel=self.kapitel, nr=self.nr, art=self.art, stufe=self.stufe, vorlage=self.vorlage,
                     woerter=self.woerter)


class Ungueltig(Exception):
    """Die Aktion passt nicht zum Block; der Grund steht als deutscher Satz da."""


class Beanstandet(Exception):
    """Ein Text von Hand besteht die festen Prüfungen nicht."""

    def __init__(self, befunde: list[Befund]) -> None:
        super().__init__("; ".join(b.text for b in befunde))
        self.befunde = befunde


def jetzt() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def nie_klassen() -> frozenset[str]:
    return frozenset(k.strip() for k in settings.uebersetzen_nie_klassen.split(",") if k.strip())


def zerlegt_mit(format: str) -> str:
    """Womit ein Original dieses Formats zerlegt wird; ändert es sich, wird neu zerlegt (Kennungen können sich dann
    verschieben)."""
    art = FORMATE.get(format.lower().lstrip("."), "")
    return f"{ZERLEGEN_FASSUNG}:{','.join(sorted(nie_klassen()))}" + (f":{art}" if art else "")


def grenzen() -> Laengengrenzen:
    return Laengengrenzen(kleinst=settings.uebersetzen_laenge_min, groesst=settings.uebersetzen_laenge_max,
                          ab_zeichen=settings.uebersetzen_laenge_ab_zeichen)


def geprueft_mit() -> str:
    """Womit fest geprüft wird (Fassung der Prüfungen und Grenzen der Länge); ändert es sich, wird neu geprüft."""
    g = grenzen()
    return f"{PRUEF_FASSUNG}:{g.kleinst}:{g.groesst}:{g.ab_zeichen}"


def anrede_vorgabe() -> Anrede:
    return "Sie" if settings.uebersetzen_anrede == "Sie" else "du"


# -- Lesen --------------------------------------------------------------------------------------------------------------------

async def buch(buch_id: int) -> Buchangaben | None:
    z = await db.fetch_one("SELECT id, hash, title, author, language, file_format, file_name, page_count FROM books WHERE id = ?",
                           (buch_id,))
    return Buchangaben(**z) if z else None


def _fassung(z: dict) -> FassungZeile:
    return FassungZeile(**{**z, "nicht_lesbar": json.loads(z["nicht_lesbar"] or "[]")})


async def holen(fid: int) -> FassungZeile | None:
    z = await db.fetch_one("SELECT * FROM fassung WHERE id = ?", (fid,))
    return _fassung(z) if z else None


async def zum_buch(buch_id: int, sprache: str) -> FassungZeile | None:
    z = await db.fetch_one("SELECT * FROM fassung WHERE buch_id = ? AND sprache = ?", (buch_id, sprache))
    return _fassung(z) if z else None


async def alle_zum_buch(buch_id: int) -> list[FassungZeile]:
    return [_fassung(z) for z in await db.fetch_all("SELECT * FROM fassung WHERE buch_id = ? ORDER BY id", (buch_id,))]


async def naechste(ausser: set[int]) -> FassungZeile | None:
    """Die nächste Fassung mit Arbeit: ein laufender Lauf, oder eine Datei, die neu zu setzen ist."""
    nicht = ",".join(str(i) for i in ausser) or "0"
    z = await db.fetch_one(f"""SELECT * FROM fassung WHERE id NOT IN ({nicht}) AND (stand = 'laeuft'
                               OR (stand IN ('fertig', 'teilweise') AND zerlegt != '' AND gesetzt != aenderungen))
                               ORDER BY angelegt_am, id LIMIT 1""")
    return _fassung(z) if z else None


def _block(z: dict) -> BlockZeile:
    return BlockZeile(**{**z, "befunde": json.loads(z["befunde"] or "[]"), "reparaturen": json.loads(z["reparaturen"] or "[]"),
                         "geprueft": bool(z["geprueft"]), "lage": json.loads(z["lage"] or "[]")})


async def bloecke(fid: int, kapitel: int | None = None, staende: tuple[str, ...] | None = None) -> list[BlockZeile]:
    sql, werte = "SELECT * FROM uebersetzung_block WHERE fassung_id = ?", [fid]
    if kapitel is not None:
        sql += " AND kapitel = ?"
        werte.append(kapitel)
    if staende is not None:
        sql += f" AND stand IN ({','.join('?' * len(staende))})"
        werte += staende
    return [_block(z) for z in await db.fetch_all(sql + " ORDER BY kapitel, nr", tuple(werte))]


async def block(fid: int, kennung: str) -> BlockZeile | None:
    z = await db.fetch_one("SELECT * FROM uebersetzung_block WHERE fassung_id = ? AND kennung = ?", (fid, kennung))
    return _block(z) if z else None


async def kapitel(fid: int) -> list[KapitelZeile]:
    return [KapitelZeile(**z) for z in await db.fetch_all("SELECT nr, titel, datei, bloecke, woerter, dauer_s FROM uebersetzung_kapitel "
                                                         "WHERE fassung_id = ? ORDER BY nr", (fid,))]


# -- Schreiben ----------------------------------------------------------------------------------------------------------------

async def anlegen(buch_id: int, sprache: str, aus_sprache: str, anrede: Anrede) -> FassungZeile:
    await db.execute("INSERT INTO fassung (buch_id, sprache, aus_sprache, stand, anweisung, anrede, geprueft_mit) "
                     "VALUES (?, ?, ?, 'laeuft', ?, ?, ?)", (buch_id, sprache, aus_sprache, ANWEISUNG, anrede, geprueft_mit()))
    f = await zum_buch(buch_id, sprache)
    assert f is not None
    return f


async def aendern(fid: int, **felder: object) -> None:
    if "nicht_lesbar" in felder:
        felder["nicht_lesbar"] = json.dumps(felder["nicht_lesbar"], ensure_ascii=False)
    spalten = ", ".join(f"{k} = ?" for k in felder)
    await db.execute(f"UPDATE fassung SET {spalten}, geaendert_am = ? WHERE id = ?", (*felder.values(), jetzt(), fid))


async def stand_setzen(fid: int, stand: Stand, grund: str = "", nur_aus: tuple[Stand, ...] | None = None) -> bool:
    """Den Stand setzen, auf Wunsch nur aus bestimmten Ständen (der Lauf überschreibt nie, was der Nutzer gewählt hat)."""
    bedingung, werte = "", ()
    if nur_aus is not None:
        bedingung, werte = f" AND stand IN ({','.join('?' * len(nur_aus))})", nur_aus
    c = await db.execute(f"UPDATE fassung SET stand = ?, grund = ?, geaendert_am = ? WHERE id = ?{bedingung}",
                         (stand, grund, jetzt(), fid, *werte))
    return c.rowcount > 0


async def zeit_merken(fid: int, kapitel_nr: int | None, sekunden: float) -> None:
    if sekunden <= 0:
        return
    async with db.einheit():
        await db.execute("UPDATE fassung SET bisher_s = bisher_s + ? WHERE id = ?", (sekunden, fid))
        if kapitel_nr is not None:
            await db.execute("UPDATE uebersetzung_kapitel SET dauer_s = dauer_s + ? WHERE fassung_id = ? AND nr = ?",
                             (sekunden, fid, kapitel_nr))


_BLOCKSPALTEN = ("kapitel", "nr", "art", "stufe", "pruefsumme", "vorlage", "woerter", "uebersetzung", "stand", "befunde",
                 "reparaturen", "versuche", "nacharbeiten", "geprueft", "seite", "seite_gedruckt", "lage")


def _als_json(liste: Sequence[BaseModel]) -> str:
    return json.dumps([x.model_dump() for x in liste], ensure_ascii=False)


def _werte(fid: int, z: BlockZeile) -> tuple:
    return (fid, z.kennung, z.kapitel, z.nr, z.art, z.stufe, z.pruefsumme, z.vorlage, z.woerter, z.uebersetzung, z.stand,
            _als_json(z.befunde), _als_json(z.reparaturen), z.versuche, z.nacharbeiten, int(z.geprueft), z.seite, z.seite_gedruckt,
            json.dumps(z.lage) if z.lage else "")


async def bloecke_merken(fid: int, zeilen: list[BlockZeile]) -> None:
    """Ergebnisse mehrerer Blöcke zusammen, als eine Änderung."""
    if not zeilen:
        return
    zeit = jetzt()
    async with db.einheit():
        await db.execute_many("""UPDATE uebersetzung_block SET uebersetzung = ?, stand = ?, befunde = ?, reparaturen = ?, versuche = ?,
                                 nacharbeiten = ?, geprueft = ?, geaendert_am = ? WHERE fassung_id = ? AND kennung = ?""",
                              [(z.uebersetzung, z.stand, _als_json(z.befunde), _als_json(z.reparaturen), z.versuche, z.nacharbeiten,
                                int(z.geprueft), zeit, fid, z.kennung) for z in zeilen])
        await db.execute("UPDATE fassung SET aenderungen = aenderungen + 1, geaendert_am = ? WHERE id = ?", (jetzt(), fid))


def _uebernommen(neu: Block, alt: BlockZeile | None) -> BlockZeile:
    zeile = BlockZeile(kennung=neu.kennung, kapitel=neu.kapitel, nr=neu.nr, art=neu.art, stufe=neu.stufe, pruefsumme=neu.pruefsumme,
                       vorlage=neu.vorlage, woerter=neu.woerter, seite=neu.seite, seite_gedruckt=neu.gedruckt,
                       lage=[round(v, 1) for v in neu.lage] if neu.lage else [])
    if alt is None:
        return zeile
    return zeile.model_copy(update={k: getattr(alt, k) for k in ("uebersetzung", "stand", "befunde", "reparaturen", "versuche", "nacharbeiten",
                                                                  "geprueft")})


async def abgleichen(fid: int, werk: Werk) -> None:
    """Kapitel und Blöcke nach der Zerlegung. Was schon übersetzt war, bleibt bei dem Block mit derselben Vorlage (gleiche
    Kennung zuerst, sonst gleiche Prüfsumme); ein Block, dessen Vorlage sich geändert hat, wartet wieder."""
    alt = await bloecke(fid)
    je_kennung = {z.kennung: z for z in alt}
    je_summe: dict[str, BlockZeile] = {}
    for z in alt:
        je_summe.setdefault(z.pruefsumme, z)
    dauer = {k.nr: k.dauer_s for k in await kapitel(fid)}
    neue = []
    for b in werk.bloecke():
        vorher = je_kennung.get(b.kennung)
        neue.append(_uebernommen(b, vorher if vorher is not None and vorher.pruefsumme == b.pruefsumme else je_summe.get(b.pruefsumme)))
    async with db.einheit():
        await db.execute("DELETE FROM uebersetzung_block WHERE fassung_id = ?", (fid,))
        await db.execute("DELETE FROM uebersetzung_kapitel WHERE fassung_id = ?", (fid,))
        await db.execute_many(f"INSERT INTO uebersetzung_block (fassung_id, kennung, {', '.join(_BLOCKSPALTEN)}) "
                              f"VALUES ({', '.join('?' * (len(_BLOCKSPALTEN) + 2))})", [_werte(fid, z) for z in neue])
        await db.execute_many("INSERT INTO uebersetzung_kapitel (fassung_id, nr, titel, datei, bloecke, woerter, dauer_s) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              [(fid, d.kapitel, d.titel, d.pfad, len(d.laeufe), sum(b.woerter for b in d.bloecke()), dauer.get(d.kapitel, 0))
                               for d in werk.kapitel()])
        await db.execute("UPDATE fassung SET zerlegt = ?, woerter = ?, nicht_lesbar = ?, aenderungen = aenderungen + 1, geaendert_am = ? "
                         "WHERE id = ?", (zerlegt_mit(werk.format), sum(z.woerter for z in neue), json.dumps(werk.nicht_lesbar, ensure_ascii=False),
                                          jetzt(), fid))


# -- Zwischenspeicher ---------------------------------------------------------------------------------------------------------

async def speicher_holen(schluessel: str) -> str | None:
    z = await db.fetch_one("SELECT uebersetzung FROM uebersetzung_speicher WHERE schluessel = ?", (schluessel,))
    return z["uebersetzung"] if z else None


async def speicher_merken(eintraege: dict[str, str]) -> None:
    if eintraege:
        await db.execute_many("INSERT OR REPLACE INTO uebersetzung_speicher (schluessel, uebersetzung) VALUES (?, ?)",
                              list(eintraege.items()))


# -- Original und deutsche Datei ----------------------------------------------------------------------------------------------

async def original_lesen(b: Buchangaben) -> bytes | None:
    """Das Original (vom Gerät, aus dem Zwischenspeicher oder der Kellerwolke); None, wenn es gerade nicht zu holen ist."""
    pfad = await asyncio.to_thread(get_original_file, b.hash)
    return await asyncio.to_thread(pfad.read_bytes) if pfad is not None else None


def gedruckte_seiten(b: Buchangaben) -> list[str]:
    """Die Beschriftungen der Seiten eines PDF, wie BücherFreunde sie überall zeigt ("" wo unbekannt; im Faden rufen)."""
    try:
        return buch_seiten(b.hash, b.format, b.page_count)[1]
    except Exception as f:  # noqa: BLE001 - ohne Beschriftungen zeigen die Marken die Seiten des PDF
        logger.warning("Seiten von %s nicht lesbar: %s", b.hash[:12], f)
        return []


def werk_aus(b: Buchangaben, original: bytes) -> Werk:
    """Das Original zerlegt (im Faden rufen); wirft NichtLesbar mit einem deutschen Satz."""
    gedruckt = gedruckte_seiten(b) if b.format == "pdf" else []
    return zerlegen(original, b.format, nie_klassen(), gedruckt, b.title or "", b.author or "")


async def satz(f: FassungZeile, mit_hinweis: bool = True) -> Satz:
    zeilen = await bloecke(f.id)
    deutsch = {z.kennung: Uebersetzt(pruefsumme=z.pruefsumme, text=z.uebersetzung) for z in zeilen if z.stand in MIT_DEUTSCH}
    im_original = {z.kennung: NICHT_BESTANDEN if z.stand == "offen" else NOCH_NICHT for z in zeilen if z.stand not in MIT_DEUTSCH}
    datum = datetime.strptime(f.geaendert_am, "%Y-%m-%dT%H:%M:%SZ").strftime("%d.%m.%Y")
    hinweis = Hinweis(aus=SPRACHE_IN_WORTEN.get(f.aus_sprache, f.aus_sprache), modell=f.modell, pruefmodell=f.pruefmodell,
                      datum=datum, im_original=len(im_original)) if mit_hinweis else None
    return Satz(deutsch=deutsch, im_original=im_original, hinweis=hinweis, sprache=f.sprache, aus_sprache=f.aus_sprache)


def epub_bauen(b: Buchangaben, original: bytes, s: Satz) -> bytes:
    """Die deutsche Fassung aus dem Original und dem Satz, immer ein EPUB (im Faden rufen)."""
    return werk_aus(b, original).setzen(s)


async def verworfen_zaehlen(fid: int, n: int) -> None:
    """Einwände des KI-Prüfers, die nicht gelten (Begriffe, Schreibung, Anrede), an der Fassung zählen."""
    if n:
        await db.execute("UPDATE fassung SET pruefer_verworfen = pruefer_verworfen + ? WHERE id = ?", (n, fid))


# -- Aktionen an einem Block --------------------------------------------------------------------------------------------------

def wartend(z: BlockZeile) -> BlockZeile:
    """Ein Block, der wieder auf seine Übersetzung wartet: ohne Text, Befunde und Reparaturen, mit allen Versuchen."""
    return z.model_copy(update={"uebersetzung": "", "stand": "wartet", "befunde": [], "reparaturen": [], "versuche": 0, "nacharbeiten": 0,
                                "geprueft": False})

async def _block_aendern(fid: int, z: BlockZeile) -> BlockZeile:
    await bloecke_merken(fid, [z])
    return z


async def block_neu(f: FassungZeile, kennung: str) -> BlockZeile | None:
    """Neu übersetzen: der Block wartet wieder; eine fertige Fassung läuft dafür weiter."""
    z = await block(f.id, kennung)
    if z is None:
        return None
    neu = await _block_aendern(f.id, wartend(z))
    await stand_setzen(f.id, "laeuft", nur_aus=("fertig",))
    return neu


async def block_annehmen(f: FassungZeile, kennung: str) -> BlockZeile | None:
    """Eine offene Stelle so annehmen, wie die KI sie zuletzt übersetzt hat; nur mit vollständigen Marken."""
    z = await block(f.id, kennung)
    if z is None:
        return None
    if z.stand != "offen":
        raise Ungueltig("Annehmen geht nur bei offenen Stellen")
    if not z.uebersetzung:
        raise Ungueltig("Zu dieser Stelle gibt es keine Übersetzung zum Annehmen")
    try:
        marken.lesen(marken.plan(z.vorlage), z.uebersetzung)
    except marken.MarkenFehler as e:
        raise Ungueltig(f"Die Marken der Übersetzung passen nicht ({e.grund}); bitte den Text von Hand setzen") from e
    return await _block_aendern(f.id, z.model_copy(update={"stand": "angenommen"}))


async def block_setzen(f: FassungZeile, kennung: str, text: str, begriffe: list[Begriff]) -> BlockZeile | None:
    """Ein Text von Hand mit Marken, Zeichen wie < und & dürfen roh stehen; er gilt nur, wenn er die festen Prüfungen
    besteht (sonst Beanstandet mit den Befunden)."""
    z = await block(f.id, kennung)
    if z is None:
        return None
    text = marken.gesichert(gerade(text.strip()), z.vorlage)
    befunde = pruefen(z.vorlage, text, begriffe, grenzen(), f.anrede)
    if befunde:
        raise Beanstandet(befunde)
    return await _block_aendern(f.id, z.model_copy(update={"uebersetzung": text, "stand": "gesetzt", "befunde": [], "reparaturen": []}))


async def neu_markieren(buch_id: int | None, englisch: list[str], ausser_buecher: frozenset[int] = frozenset()) -> int:
    """Nach einer Änderung der Begriffsliste: die Blöcke, in denen einer der Begriffe vorkommt und die die KI übersetzt hat,
    warten wieder (Texte und Annahmen des Nutzers bleiben). Gilt für die Fassungen des Buchs, ohne Buch für alle außer
    `ausser_buecher` (dort gilt ein eigener Eintrag). Gibt zurück, wie viele Blöcke es sind."""
    begriffe = [e for e in englisch if e.strip()]
    if not begriffe:
        return 0
    sql, werte = "SELECT id, buch_id, stand FROM fassung", ()
    if buch_id is not None:
        sql, werte = sql + " WHERE buch_id = ?", (buch_id,)
    gesamt = 0
    for f in await db.fetch_all(sql, werte):
        if f["buch_id"] in ausser_buecher:
            continue
        betroffen = [z for z in await bloecke(f["id"], staende=VON_DER_KI)
                     if any(kommt_vor(e, marken.klartext(z.vorlage)) for e in begriffe)]
        await bloecke_merken(f["id"], [wartend(z) for z in betroffen])
        if betroffen:
            await stand_setzen(f["id"], "laeuft", nur_aus=("fertig",))
        gesamt += len(betroffen)
    return gesamt


async def offen_in_arbeit(fid: int) -> int:
    z = await db.fetch_one(f"SELECT count(*) AS n FROM uebersetzung_block WHERE fassung_id = ? AND stand IN ({','.join('?' * len(IN_ARBEIT))})",
                           (fid, *IN_ARBEIT))
    return z["n"]


async def noch_zu_tun(f: FassungZeile) -> bool:
    """Ob eine fertige Fassung wieder laufen muss: Blöcke in Arbeit, oder die festen Prüfungen haben sich geändert."""
    return bool(await offen_in_arbeit(f.id)) or f.geprueft_mit != geprueft_mit()
