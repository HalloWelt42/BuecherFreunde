"""Art und Gattung der Werke bestimmen (BF-59, BF-77).

Die Art (books.typ, leer: ein Buch) braucht jedes Werk: nach ihr steht es unter "Bücher" oder "Besonderes", und das
gestaltete Deckblatt eines schlichten Umschlags (services/umschlagpruefung.py) hängt an ihr, bei Büchern auch an der
Gattung. Offen ist ein Werk, das noch niemand eingeordnet hat und das keine Art hat (eine Art, die schon dasteht, hat vor
BF-59 der Nutzer gesetzt und bleibt).

Eine Runde ordnet alle offenen Werke ein:
1. Feste Regeln (services/artregeln.py) mit kurzer Begründung; `einordnung` wird "regel", der Grund steht in
   `einordnung_grund`.
2. Den Rest die lokale KI über die Leitstelle (services/ki.py), gebündelt: bis zu `EINORDNEN_JE_ANFRAGE` (40) Werke je Anfrage
   mit Titel, Autor, Verlag, Seiten, Dateiname und dem Anfang des Volltexts, Antwort als Liste fester Länge; zwischen zwei
   Anfragen `EINORDNEN_ABSTAND_S`. Dran sind nur Werke mit geprüftem Umschlag: die Gattung fragt sie nur, wo das
   gezeichnete Deckblatt sie braucht (Umschlag schlicht), und nur Bücher bekommen eine. `einordnung` wird "ki". Die
   Umschlagprüfung stößt nach jeder Runde an, die Umschläge geprüft hat.

Wer Art oder Gattung von Hand setzt, hat das letzte Wort (`einordnung` "hand"): weder Regel noch KI fasst das Werk wieder an,
auch nicht, wenn es während einer Anfrage geschah. Was die KI zu einem Werk nicht brauchbar sagt, bleibt offen und kommt in
einer späteren Runde wieder dran. Ist die Leitstelle länger weg, als die Geduld reicht, endet nur die Runde; lehnt sie ab,
hält das Einordnen an, bis es fortgesetzt wird. Der Stand steht in `books`: nach einem Neustart beginnt sofort eine Runde
mit dem, was noch offen ist."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Sequence

from appkern.leitstelle.arbeit import LAUFENDE_ARBEIT
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.models.book import GATTUNGEN, TYPEN, Gattung, Typ
from backend.app.services import artregeln
from backend.app.services.anhalten import Anhalter
from backend.app.services.artregeln import Werk
from backend.app.services.ki import Ki, KiFehler, ki
from backend.app.services.storage import get_sidecar_path

logger = logging.getLogger("buecherfreunde.einordnung")
AUSZUG_ZEICHEN = 300                       # so viel vom Anfang des Volltexts bekommt die KI je Werk
TOKEN_JE_WERK = 30
BUCH = "buch"                              # die Art, die in books.typ leer heißt
ARTEN = (BUCH, *(t["id"] for t in TYPEN))
GATTUNG_IDS = tuple(g["id"] for g in GATTUNGEN)
SPALTEN = "id, hash, title, author, publisher, year, isbn, file_format, file_name, page_count, umschlag_schlicht"

SYSTEM = ("Du ordnest die Werke einer privaten Bibliothek ein. Zu jedem nummerierten Werk bekommst du Titel, Autor, Verlag, "
          "Seiten, Dateiname und den Anfang des Textes. Bestimme die Art: buch (ein Buch, etwa Roman, Sachbuch oder Fachbuch), "
          + ", ".join(f"{t['id']} ({t['beschreibung']})" for t in TYPEN)
          + ". Steht bei einem Werk 'Gattung gefragt' und ist es ein Buch, bestimme auch die Gattung, eine von: "
          + ", ".join(f"{g['id']} ({g['name']})" for g in GATTUNGEN)
          + "; sonst, oder wenn keine passt, bleibt 'gattung' leer. Antworte mit einem Objekt mit dem Feld 'werke': genau ein "
          "Eintrag je Werk in derselben Reihenfolge, je mit 'nummer', 'art' und 'gattung'.")

# Offen: von niemandem eingeordnet und ohne Art. Eine Art, die schon dasteht, hat vor BF-59 der Nutzer gesetzt (nur er
# schrieb typ); sie bleibt, auch wenn einordnung dort noch leer ist.
OFFEN = "einordnung = '' AND COALESCE(typ, '') = ''"
FUER_DIE_KI = f"{OFFEN} AND umschlag_schlicht IS NOT NULL"     # erst mit Befund des Umschlags: braucht das Deckblatt die Gattung?


def schema(anzahl: int) -> dict:
    """Die Antwort als Liste fester Länge: je Werk ein Eintrag."""
    werk = {"type": "object", "additionalProperties": False, "required": ["nummer", "art", "gattung"],
            "properties": {"nummer": {"type": "integer"}, "art": {"type": "string", "enum": list(ARTEN)},
                           "gattung": {"type": "string", "enum": ["", *GATTUNG_IDS]}}}
    return {"type": "object", "additionalProperties": False, "required": ["werke"],
            "properties": {"werke": {"type": "array", "minItems": anzahl, "maxItems": anzahl, "items": werk}}}


class Vorschlag(BaseModel):
    typ: Typ                                # leer: ein Buch
    gattung: Gattung | None                 # leer bei allem außer Büchern; None: nicht gefragt, sie bleibt, wie sie ist


class EinordnungStand(BaseModel):
    an: bool                                # Einstellung EINORDNEN_AN
    bereit: bool                            # an und eine Leitstelle eingetragen
    laeuft: bool
    angehalten: bool                        # die Leitstelle hat abgelehnt; weiter mit POST /api/einordnung/fortsetzen
    grund: str = ""                         # warum angehalten, die Runde endete oder in ihr zuletzt ein Werk offen blieb
    gesamt: int = 0                         # alle Werke
    nach_regel: int = 0                     # von den festen Regeln eingeordnet
    durch_ki: int = 0                       # von der KI eingeordnet
    offen: int = 0                          # noch ohne Art und von niemandem eingeordnet
    erledigt: int = 0                       # wie durch_ki (für Stellen, die es noch lesen)


class Angehalten(Exception):
    pass


def vorschlaege_aus(roh: object, werke: Sequence[Werk]) -> dict[int, Vorschlag]:
    """Je Werk (Nummer im Bestand) die Antwort der KI; unbekannte Nummern und Arten fallen weg, eine Gattung gilt nur bei
    Büchern, nach deren Gattung gefragt war. Passt die Antwort gar nicht zur Form: KiFehler."""
    if not isinstance(roh, dict) or not isinstance(roh.get("werke"), list):
        raise KiFehler("Die Antwort der KI passt nicht zur verlangten Form", "einzeln")
    aus: dict[int, Vorschlag] = {}
    for e in roh["werke"]:
        nummer = e.get("nummer") if isinstance(e, dict) else None
        if not isinstance(nummer, int) or isinstance(nummer, bool) or not 1 <= nummer <= len(werke) or e.get("art") not in ARTEN:
            continue
        w = werke[nummer - 1]
        if w.id in aus:
            continue
        if e["art"] != BUCH:
            gattung: str | None = ""                     # nur Bücher haben eine Gattung
        elif w.gattung_gefragt:
            gattung = e.get("gattung") if e.get("gattung") in GATTUNG_IDS else ""
        else:
            gattung = None
        aus[w.id] = Vorschlag(typ="" if e["art"] == BUCH else e["art"], gattung=gattung)
    return aus


def textanfang(file_hash: str) -> str:
    """Der Anfang des Volltexts, ohne die ganze Datei zu lesen; Seitenvorschübe und Leerraum werden zu einem Leerzeichen."""
    try:
        with get_sidecar_path(file_hash, "fulltext.txt").open(encoding="utf-8", errors="ignore") as datei:
            return " ".join(datei.read(AUSZUG_ZEICHEN).split())
    except OSError:
        return ""


def werkzeile(nummer: int, w: Werk, text: str) -> str:
    teile = [f"Titel: {w.title or '-'}", f"Autor: {w.author or '-'}", f"Verlag: {w.publisher or '-'}",
             f"Seiten: {w.seiten or '-'}", f"ISBN: {'ja' if w.hat_isbn else 'nein'}", f"Datei: {w.file_name or '-'}"]
    if w.gattung_gefragt:
        teile.append("Gattung gefragt")
    return f"{nummer}. " + " | ".join(teile) + f"\n   Anfang: {text or '-'}"


def anfrage(werke: Sequence[Werk], texte: Sequence[str]) -> str:
    return "\n".join(werkzeile(i, w, t) for i, (w, t) in enumerate(zip(werke, texte, strict=True), 1))


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
        """Im Hintergrund, mit einer Runde gleich zu Beginn: was vor einem Neustart offen blieb, geht sofort weiter."""
        self._wecker = asyncio.Event()
        self._wecker.set()
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
        z = await db.fetch_one(f"""SELECT COUNT(*) AS gesamt, SUM({OFFEN}) AS offen, SUM(einordnung = 'regel') AS regel,
                                          SUM(einordnung = 'ki') AS ki FROM books""")
        return EinordnungStand(an=settings.einordnen_an, bereit=self.bereit, laeuft=self.laeuft, angehalten=self.angehalten,
                               grund=self.grund, gesamt=z["gesamt"] or 0, nach_regel=z["regel"] or 0, durch_ki=z["ki"] or 0,
                               offen=z["offen"] or 0, erledigt=z["ki"] or 0)

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
        """Alle offenen Werke: erst die Regeln, dann die KI, bis keins mehr offen ist, abgeschaltet oder angehalten wird
        oder die Leitstelle fehlt; gibt zurück, wie viele eingeordnet wurden."""
        if not settings.einordnen_an or self.angehalten:
            return 0
        self._anhalter.beginne()
        marke = LAUFENDE_ARBEIT.set(f"bf-einordnen-{uuid.uuid4().hex[:12]}")
        self.laeuft, self.grund = True, ""
        try:
            eingeordnet = await self.nach_regeln()
            if self.ki.bereit:
                eingeordnet += await self._mit_ki()
            return eingeordnet
        finally:
            self.laeuft = False
            LAUFENDE_ARBEIT.reset(marke)

    @staticmethod
    async def _offene(nach: int, anzahl: int, wo: str = OFFEN) -> list[Werk]:
        zeilen = await db.fetch_all(f"SELECT {SPALTEN} FROM books WHERE {wo} AND id > ? ORDER BY id LIMIT ?", (nach, anzahl))
        return [Werk(**z) for z in zeilen]

    async def nach_regeln(self) -> int:
        """Die festen Regeln über alle offenen Werke, in Teilen; gibt zurück, wie viele sie eingeordnet haben."""
        eingeordnet, zuletzt = 0, 0
        while werke := await self._offene(zuletzt, 500):
            zuletzt = werke[-1].id
            urteile = [(w.id, u) for w in werke if (u := artregeln.urteil(w))]
            async with db.einheit():
                for nr, u in urteile:
                    c = await db.execute("""UPDATE books SET typ = ?, einordnung = 'regel', einordnung_grund = ?, updated_at = datetime('now')
                                            WHERE id = ? AND einordnung = ''""", (u.typ, u.grund, nr))
                    eingeordnet += c.rowcount
        if eingeordnet:
            logger.info("Einordnen: %d Werke nach Regeln", eingeordnet)
        return eingeordnet

    async def _mit_ki(self) -> int:
        eingeordnet, zuletzt, gefragt = 0, 0, False
        try:
            while self.bereit and not self.angehalten and (werke := await self._offene(zuletzt, settings.einordnen_je_anfrage, FUER_DIE_KI)):
                zuletzt = werke[-1].id
                if gefragt:
                    await self._pause()
                gefragt = True
                eingeordnet += await self._teil(werke)
        except Angehalten:
            pass
        except KiFehler as f:
            self._unterbrochen(f)
        return eingeordnet

    async def _teil(self, werke: list[Werk]) -> int:
        """Eine Anfrage für diese Werke; wirft KiFehler, wenn es auch für die übrigen nicht weitergeht."""
        try:
            vorschlaege = await self.vorschlagen(werke)
        except KiFehler as f:
            if f.art != "einzeln":
                raise
            self.grund = f"{len(werke)} Werke ab {werke[0].title or werke[0].id}: {f.grund}"
            logger.info("Einordnen von %d Werken bleibt offen: %s", len(werke), f.grund)
            return 0
        if len(vorschlaege) < len(werke):
            self.grund = f"Zu {len(werke) - len(vorschlaege)} von {len(werke)} Werken sagte die KI nichts Brauchbares"
        return await self._merken(vorschlaege)

    async def vorschlagen(self, werke: list[Werk]) -> dict[int, Vorschlag]:
        """Die lokale KI über die Leitstelle; im Hintergrund, wartet geduldig, wenn die Leitstelle gerade nicht kann."""
        texte = await asyncio.to_thread(lambda: [textanfang(w.hash) for w in werke])
        titel = f"Art und Gattung: {len(werke)} {'Werk' if len(werke) == 1 else 'Werke'} ab {werke[0].title[:60]}"
        roh = await self.ki.json_antwort(SYSTEM, anfrage(werke, texte), "einordnung", schema(len(werke)), titel=titel,
                                         prioritaet="hintergrund", geduld=True, pruefen=self._pruefen_waehrend_warten,
                                         temperature=0.1, max_tokens=TOKEN_JE_WERK * len(werke) + 200)
        return vorschlaege_aus(roh, werke)

    @staticmethod
    async def _merken(vorschlaege: dict[int, Vorschlag]) -> int:
        """Nur, solange ein Werk offen ist: hat der Nutzer es inzwischen eingeordnet, gilt seine Wahl. Eine Gattung, nach
        der nicht gefragt war, bleibt, wie sie ist."""
        eingeordnet = 0
        async with db.einheit():
            for nr, v in vorschlaege.items():
                c = await db.execute("""UPDATE books SET typ = ?, gattung = COALESCE(?, gattung), einordnung = 'ki', einordnung_grund = '',
                                        updated_at = datetime('now') WHERE id = ? AND einordnung = ''""", (v.typ, v.gattung, nr))
                eingeordnet += c.rowcount
        return eingeordnet

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
