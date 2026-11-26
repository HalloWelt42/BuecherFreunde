"""Einordnen mit der lokalen KI (BF-59): Art und Gattung der Bücher mit schlichtem Umschlag.

Ein Buch mit schlichtem Umschlag (services/umschlagpruefung.py) bekommt in der Oberfläche ein gestaltetes Deckblatt; wie es
aussieht, hängt an der Art (books.typ, leer: ein Buch) und bei Büchern an der Gattung. Beides schlägt beim ersten Mal die
lokale KI über die Leitstelle vor (services/ki.py), aus den Angaben und dem Anfang des Volltexts: ein Buch je Anfrage, im
Hintergrund, mit Abstand (`EINORDNEN_ABSTAND_S`), ab- und anschaltbar (`EINORDNEN_AN`). Ändert der Nutzer Art oder
Gattung, gilt `einordnung` "hand", und die KI fasst das Buch nie wieder an.

Antwortet die KI zu einem Buch nicht brauchbar, bleibt es offen und kommt in einer späteren Runde wieder dran. Ist die
Leitstelle länger weg, als die Geduld reicht, endet nur die Runde. Lehnt sie ab, hält das Einordnen mit dem Grund an, bis
es fortgesetzt wird (ein Mensch ist gefragt; nichts wird von selbst wiederholt)."""

from __future__ import annotations

import asyncio
import logging
import uuid

from appkern.leitstelle.arbeit import LAUFENDE_ARBEIT
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.models.book import GATTUNGEN, TYPEN, Gattung, Typ
from backend.app.services.anhalten import Anhalter
from backend.app.services.ki import Ki, KiFehler, ki
from backend.app.services.storage import get_sidecar_path

logger = logging.getLogger("buecherfreunde.einordnung")
AUSZUG_ZEICHEN = 1500                      # so viel vom Anfang des Volltexts bekommt die KI
BUCH = "buch"                              # die Art, die in books.typ leer heißt
ARTEN = (BUCH, *(t["id"] for t in TYPEN))
GATTUNG_IDS = tuple(g["id"] for g in GATTUNGEN)

SYSTEM = ("Du ordnest die Dateien einer privaten Bibliothek ein. Aus Titel, Autor, Verlag, Jahr, ISBN, Format und dem "
          "Anfang des Textes bestimmst du die Art und, bei einem Buch, die Gattung. Antworte mit einem Objekt aus zwei "
          "Feldern. 'art' ist eins von: buch (ein Buch, etwa Roman, Sachbuch oder Fachbuch), "
          + ", ".join(f"{t['id']} ({t['beschreibung']})" for t in TYPEN)
          + ". 'gattung' ist bei einem Buch eins von: " + ", ".join(f"{g['id']} ({g['name']})" for g in GATTUNGEN)
          + "; bei jeder anderen Art und wenn keine passt, leer.")
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["art", "gattung"],
          "properties": {"art": {"type": "string", "enum": list(ARTEN)},
                         "gattung": {"type": "string", "enum": ["", *GATTUNG_IDS]}}}

OFFEN = "umschlag_schlicht = 1 AND einordnung = ''"


class Buchangaben(BaseModel):
    """Was die KI über ein Buch erfährt (dazu der Anfang des Volltexts)."""

    id: int
    hash: str
    title: str = ""
    author: str = ""
    publisher: str | None = ""
    year: int | None = None
    isbn: str | None = ""
    file_format: str = ""


class Vorschlag(BaseModel):
    typ: Typ                                # leer: ein Buch
    gattung: Gattung                        # nur bei Büchern


class EinordnungStand(BaseModel):
    an: bool                                # Einstellung EINORDNEN_AN
    bereit: bool                            # an und eine Leitstelle eingetragen
    laeuft: bool
    angehalten: bool                        # die Leitstelle hat abgelehnt; weiter mit POST /api/einordnung/fortsetzen
    grund: str = ""                         # warum angehalten, die Runde endete oder in ihr zuletzt ein Buch offen blieb
    offen: int = 0                          # schlichte Bücher, die noch niemand eingeordnet hat
    erledigt: int = 0                       # von der KI eingeordnet


class Angehalten(Exception):
    pass


def vorschlag_aus(roh: object) -> Vorschlag:
    """Die Antwort der KI als Vorschlag; eine Gattung gibt es nur bei Büchern, eine unbekannte bleibt leer."""
    if not isinstance(roh, dict) or roh.get("art") not in ARTEN:
        raise KiFehler("Die Antwort der KI passt nicht zur verlangten Form", "einzeln")
    art, gattung = roh["art"], roh.get("gattung")
    if art != BUCH or gattung not in GATTUNG_IDS:
        gattung = ""
    return Vorschlag(typ="" if art == BUCH else art, gattung=gattung)


def textanfang(file_hash: str) -> str:
    """Der Anfang des Volltexts, ohne die ganze Datei zu lesen; Seitenvorschübe und Leerraum werden zu einem Leerzeichen."""
    try:
        with get_sidecar_path(file_hash, "fulltext.txt").open(encoding="utf-8", errors="ignore") as datei:
            return " ".join(datei.read(AUSZUG_ZEICHEN).split())
    except OSError:
        return ""


def anfrage(buch: Buchangaben, text: str) -> str:
    zeilen = [f"Titel: {buch.title or '-'}", f"Autor: {buch.author or '-'}", f"Verlag: {buch.publisher or '-'}",
              f"Jahr: {buch.year or '-'}", f"ISBN: {buch.isbn or '-'}", f"Format: {buch.file_format or '-'}"]
    return "\n".join(zeilen) + f"\n\nAnfang des Textes:\n{text or '-'}"


class Einordner:
    def __init__(self, ki: Ki) -> None:
        self.ki = ki
        self._anhalter = Anhalter()
        self._wecker = asyncio.Event()
        self._lauf: asyncio.Task | None = None
        self.angehalten = False
        self.grund = ""
        self.laeuft = False

    # -- Leben und Bedienung ---------------------------------------------------------------------------------------------
    def starten(self) -> None:
        self._wecker = asyncio.Event()
        self._lauf = asyncio.create_task(self._arbeiten())

    async def stoppen(self) -> None:
        self._anhalter.halte()
        if self._lauf is not None:
            self._lauf.cancel()
            self._lauf = None

    def anstossen(self) -> None:
        self._wecker.set()

    def fortsetzen(self) -> None:
        self.angehalten, self.grund = False, ""
        self.anstossen()

    @property
    def bereit(self) -> bool:
        return settings.einordnen_an and self.ki.bereit

    async def stand(self) -> EinordnungStand:
        z = await db.fetch_one(f"SELECT SUM({OFFEN}) AS offen, SUM(einordnung = 'ki') AS erledigt FROM books")
        return EinordnungStand(an=settings.einordnen_an, bereit=self.bereit, laeuft=self.laeuft, angehalten=self.angehalten,
                               grund=self.grund, offen=z["offen"] or 0, erledigt=z["erledigt"] or 0)

    # -- Arbeit ----------------------------------------------------------------------------------------------------------
    async def _arbeiten(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._wecker.wait(), settings.einordnen_takt_s)
            except TimeoutError:
                pass
            self._wecker.clear()
            try:
                await self.runde()
            except asyncio.CancelledError:
                raise
            except Exception:                              # noqa: BLE001 - das Einordnen darf nie still enden
                logger.exception("Einordnen")

    async def runde(self) -> int:
        """Die offenen Bücher der Reihe nach, bis keins mehr offen ist, abgeschaltet oder angehalten wird oder die Leitstelle
        fehlt; gibt zurück, wie viele eingeordnet wurden. Ein Buch, zu dem die KI nichts Brauchbares sagt, bleibt offen."""
        if not self.bereit or self.angehalten:
            return 0
        self._anhalter.beginne()
        marke = LAUFENDE_ARBEIT.set(f"bf-einordnen-{uuid.uuid4().hex[:12]}")
        self.laeuft, self.grund, eingeordnet, zuletzt = True, "", 0, 0
        try:
            while self.bereit and not self.angehalten and (buch := await self._naechstes(zuletzt)) is not None:
                zuletzt = buch.id
                eingeordnet += await self._buch(buch)
                await self._pause()
        except Angehalten:
            pass
        except KiFehler as f:
            self._unterbrochen(f)
        finally:
            self.laeuft = False
            LAUFENDE_ARBEIT.reset(marke)
        return eingeordnet

    @staticmethod
    async def _naechstes(nach: int) -> Buchangaben | None:
        z = await db.fetch_one(f"""SELECT id, hash, title, author, publisher, year, isbn, file_format FROM books
                                   WHERE {OFFEN} AND id > ? ORDER BY id LIMIT 1""", (nach,))
        return Buchangaben(**z) if z else None

    async def _buch(self, buch: Buchangaben) -> int:
        """1, wenn das Buch eingeordnet wurde; wirft KiFehler, wenn es auch für die übrigen nicht weitergeht."""
        try:
            v = await self.vorschlagen(buch)
        except KiFehler as f:
            if f.art != "einzeln":
                raise
            self.grund = f"{buch.title or buch.id}: {f.grund}"
            logger.info("Einordnen von Buch %d bleibt offen: %s", buch.id, f.grund)
            return 0
        return await self._merken(buch.id, v)

    async def vorschlagen(self, buch: Buchangaben) -> Vorschlag:
        """Die lokale KI über die Leitstelle; im Hintergrund, wartet geduldig, wenn die Leitstelle gerade nicht kann."""
        text = await asyncio.to_thread(textanfang, buch.hash)
        roh = await self.ki.json_antwort(SYSTEM, anfrage(buch, text), "einordnung", SCHEMA, titel=f"Art und Gattung: {buch.title[:80]}",
                                         prioritaet="hintergrund", geduld=True, pruefen=self._pruefen_waehrend_warten,
                                         temperature=0.1, max_tokens=200)
        return vorschlag_aus(roh)

    @staticmethod
    async def _merken(buch: int, v: Vorschlag) -> int:
        """Nur, solange das Buch offen ist: hat der Nutzer es inzwischen eingeordnet, gilt seine Wahl."""
        c = await db.execute("""UPDATE books SET typ = ?, gattung = ?, einordnung = 'ki', updated_at = datetime('now')
                                WHERE id = ? AND einordnung = ''""", (v.typ, v.gattung, buch))
        await db.commit()
        return c.rowcount

    def _unterbrochen(self, f: KiFehler) -> None:
        if f.art == "abgelehnt":
            self.angehalten = True                        # ein Mensch ist gefragt; nichts wird von selbst wiederholt
        self.grund = f.grund
        logger.warning("Einordnen unterbrochen: %s", f.grund)

    async def _pause(self) -> None:
        await self._anhalter.bis(asyncio.sleep(settings.einordnen_abstand_s))
        if self._anhalter.gehalten:
            raise Angehalten

    async def _pruefen_waehrend_warten(self) -> None:
        if self._anhalter.gehalten:
            raise Angehalten


einordner = Einordner(ki)
