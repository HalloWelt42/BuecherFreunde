"""Vorprüfung je Codestelle (BF-29): läuft der Code für sich, oder ist er ein Auszug?

Zuerst ein echter Lauf in der Sandbox der Codeschmiede: kommt er ohne Fehler zu Ende, läuft die Stelle für sich (mit ihrer
Ausgabe). Sonst schätzt, wenn eine Leitstelle angeschlossen ist, die lokale KI ein: ein kurzer Grund und was fehlt (Import,
Klasse, Eingabe, ...). Die KI schlägt nur vor, am Code ändert sie nichts. Ohne Leitstelle bleibt der Fehler des Laufs der
Grund. Das Ergebnis gilt je Sprache und Prüfsumme des Codes, also nur bis der Code sich ändert.

Läuft im Hintergrund, Buch für Buch, mit einer Pause zwischen zwei Läufen (Menschen kommen in der Sandbox ohnehin zuerst
dran) und anhaltbar. Ist die Sandbox oder die Leitstelle gerade weg, geht es in der nächsten Runde weiter; lehnt eine von
beiden ab, hält die Vorprüfung mit dem Grund an, bis ein Mensch sie fortsetzt. Nichts wird von selbst wiederholt."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid

from appkern.leitstelle.arbeit import LAUFENDE_ARBEIT
from pydantic import BaseModel, Field

from backend.app.codestellen.dienst import begleiter_lesen
from backend.app.codestellen.modelle import Codestelle, Vorpruefung
from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services.anhalten import Anhalter
from backend.app.services.ausfuehren import HOECHSTENS_ZEICHEN, SPRACHEN, Sandbox, SandboxFehler, sandbox
from backend.app.services.ki import Ki, KiFehler, ki

logger = logging.getLogger("buecherfreunde.vorpruefung")
TAKT_S = 10 * 60                          # so oft sieht die Vorprüfung von selbst nach (dazu: nach jeder Erkennung)
AUSGABE_HOECHSTENS = 2000
FEHLT = ("import", "paket", "klasse", "funktion", "variable", "datei", "eingabe", "netz", "datenbank", "rahmenwerk",
         "vorgaenger", "sonstiges")
FEHLERZEILE = re.compile(r"^((\w+\.)*\w*(Error|Exception)\b|PHP (Fatal|Parse) error|(Fatal|Parse) error|Warning:|Uncaught)")

SYSTEM = ("Du prüfst Codebeispiele aus einem Lehrbuch. Das Beispiel lief für sich allein in einer abgeschotteten Umgebung "
          "(ohne Netz, ohne fremde Pakete, ohne Dateien, ohne Eingabe) und brach ab. Ändere den Code nicht und schreibe keinen "
          "Code. Antworte mit einem Objekt aus zwei Feldern: 'satz' ist ein ganzer kurzer deutscher Satz, warum das Beispiel "
          "für sich nicht läuft (etwa: \"Die Funktion lade_daten stammt aus einem früheren Beispiel.\"). 'fehlt' ist eine "
          "Liste mit den zutreffenden Wörtern aus: import (eine Importzeile der Standardbibliothek fehlt), paket (ein "
          "fremdes Paket, das die Umgebung nicht hat), klasse, funktion, variable (ein Name, der anderswo definiert ist), "
          "vorgaenger (Code aus früheren Beispielen des Buchs), datei, eingabe, netz, datenbank, rahmenwerk (ein Rahmenwerk "
          "wie ein Webserver oder eine Oberfläche), sonstiges.")
# Felder mit Beschreibung, ohne Aufzählung und Längen: so eingeschränkt verrutschten die Felder, und "grund" hielt das
# Modell für ein Stichwort (gemessen 26.11.2026); die Wörter von "fehlt" werden danach gefiltert
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["satz", "fehlt"],
          "properties": {"satz": {"type": "string", "description": "ein ganzer kurzer deutscher Satz"},
                         "fehlt": {"type": "array", "items": {"type": "string"}, "description": "Wörter aus der Liste der Anweisung"}}}


class Einschaetzung(BaseModel):
    grund: str
    fehlt: list[str] = Field(default_factory=list)


class VorpruefungStand(BaseModel):
    bereit: bool                          # Sandbox angeschlossen
    ki: bool                              # Leitstelle angeschlossen (sonst nur der Lauf)
    laeuft: bool
    angehalten: bool
    grund: str = ""                       # warum angehalten oder gerade nichts geht
    geprueft: int = 0                     # Ergebnisse insgesamt
    offen: int = 0                        # Bücher mit Stellen, deren Vorprüfung noch aussteht


class Angehalten(Exception):
    pass


def fehlerzeile(text: str) -> str:
    """Die eine Zeile, die sagt, was schiefging (Python: die letzte Zeile der Spur, PHP und JavaScript: die Meldung)."""
    zeilen = [z.strip() for z in (text or "").splitlines() if z.strip()]
    treffer = [z for z in zeilen if FEHLERZEILE.match(z)]
    return ((treffer[-1] if treffer else zeilen[0]) if zeilen else "")[:300]


async def ergebnisse(schluessel: list[tuple[str, str]]) -> dict[tuple[str, str], Vorpruefung]:
    """Die gemerkten Ergebnisse zu (Sprache, Prüfsumme)."""
    aus: dict[tuple[str, str], Vorpruefung] = {}
    for i in range(0, len(schluessel), 400):
        teil = schluessel[i:i + 400]
        bedingung = " OR ".join("(sprache = ? AND pruefsumme = ?)" for _ in teil)
        for z in await db.fetch_all(f"SELECT * FROM code_vorpruefung WHERE {bedingung}", tuple(w for p in teil for w in p)):
            aus[(z["sprache"], z["pruefsumme"])] = Vorpruefung(stand=z["stand"], quelle=z["quelle"], ausgabe=z["ausgabe"], fehler=z["fehler"],
                                                              grund=z["grund"], fehlt=json.loads(z["fehlt"] or "[]"), geprueft_am=z["geprueft_am"])
    return aus


class Vorpruefer:
    def __init__(self, sandbox: Sandbox, ki: Ki) -> None:
        self.sandbox, self.ki = sandbox, ki
        self._anhalter = Anhalter()
        self._wecker = asyncio.Event()
        self._lauf: asyncio.Task | None = None
        self.angehalten = False
        self.grund = ""
        self.laeuft = False
        self._geprueft = 0

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

    async def nach_erkennung(self, _buch: int) -> None:
        self.anstossen()

    def anhalten(self, grund: str = "Von Hand angehalten") -> None:
        self.angehalten, self.grund = True, grund
        self._anhalter.halte()

    def fortsetzen(self) -> None:
        self.angehalten, self.grund = False, ""
        self.anstossen()

    async def stand(self) -> VorpruefungStand:
        geprueft = (await db.fetch_one("SELECT COUNT(*) AS n FROM code_vorpruefung"))["n"]
        sprachen = await self.sandbox.sprachen() if self.sandbox.angeschlossen else set()
        offen = (await db.fetch_one("SELECT COUNT(*) AS n FROM codestellen WHERE anzahl > 0 AND vorgeprueft != ?",
                                    (self._schluessel(sprachen),)))["n"] if sprachen else 0
        return VorpruefungStand(bereit=self.sandbox.angeschlossen, ki=self.ki.bereit, laeuft=self.laeuft, angehalten=self.angehalten,
                                grund=self.grund, geprueft=geprueft, offen=offen)

    # -- Arbeit ----------------------------------------------------------------------------------------------------------
    @staticmethod
    def _schluessel(sprachen: set[str]) -> str:
        return ",".join(sorted(sprachen))

    async def _arbeiten(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._wecker.wait(), TAKT_S)
            except TimeoutError:
                pass
            self._wecker.clear()
            if self.angehalten or not self.sandbox.angeschlossen:
                continue
            try:
                await self.runde()
            except asyncio.CancelledError:
                raise
            except Exception:                              # noqa: BLE001 - die Vorprüfung darf nie still enden
                logger.exception("Vorprüfung")

    async def runde(self) -> int:
        """Bücher mit offenen Stellen nacheinander, bis keins mehr offen ist, angehalten wird oder ein Dienst fehlt."""
        sprachen = (await self.sandbox.sprachen()) & set(SPRACHEN)
        if not sprachen:
            return 0
        schluessel = self._schluessel(sprachen)
        self._anhalter.beginne()
        marke = LAUFENDE_ARBEIT.set(f"bf-vorpruefung-{uuid.uuid4().hex[:12]}")
        self.laeuft, self._geprueft = True, 0
        try:
            while not self.angehalten:
                z = await db.fetch_one("""SELECT c.buch_id, b.hash FROM codestellen c JOIN books b ON b.id = c.buch_id
                                          WHERE c.anzahl > 0 AND c.vorgeprueft != ? ORDER BY c.erkannt_am DESC LIMIT 1""", (schluessel,))
                if z is None:
                    break
                await self._buch(z["hash"], sprachen)
                await db.execute("UPDATE codestellen SET vorgeprueft = ? WHERE buch_id = ?", (schluessel, z["buch_id"]))
                await db.commit()
        except Angehalten:
            pass
        except SandboxFehler as f:
            self._unterbrochen(f.grund, f.art == "abgelehnt")
        except KiFehler as f:
            self._unterbrochen(f.grund, f.art == "abgelehnt")
        finally:
            self.laeuft = False
            LAUFENDE_ARBEIT.reset(marke)
        return self._geprueft

    def _unterbrochen(self, grund: str, abgelehnt: bool) -> None:
        if abgelehnt:
            self.anhalten(grund)                          # ein Mensch ist gefragt; nichts wird von selbst wiederholt
        else:
            self.grund = grund                            # gleich wieder: in der nächsten Runde
        logger.warning("Vorprüfung unterbrochen: %s", grund)

    async def _buch(self, file_hash: str, sprachen: set[str]) -> None:
        begleiter = await asyncio.to_thread(begleiter_lesen, file_hash)
        if begleiter is None:
            return
        stellen = [s for s in begleiter.stellen if s.sicher and s.sprache in sprachen]
        bekannt = await ergebnisse([(s.sprache, s.pruefsumme) for s in stellen])
        for s in stellen:
            assert s.sprache is not None
            if (s.sprache, s.pruefsumme) in bekannt:
                continue
            ergebnis = await self.pruefe(s)
            await self._merken(s.sprache, s.pruefsumme, ergebnis)
            bekannt[(s.sprache, s.pruefsumme)] = ergebnis
            self.grund = ""
            self._geprueft += 1
            await self._pause()

    async def _pause(self) -> None:
        await self._anhalter.bis(asyncio.sleep(settings.vorpruefung_abstand_s))
        if self._anhalter.gehalten:
            raise Angehalten

    async def _pruefen_waehrend_warten(self) -> None:
        if self._anhalter.gehalten:
            raise Angehalten

    async def pruefe(self, s: Codestelle) -> Vorpruefung:
        assert s.sprache is not None
        if len(s.code) > HOECHSTENS_ZEICHEN:
            return Vorpruefung(stand="auszug", quelle="lauf", grund=f"Länger als {HOECHSTENS_ZEICHEN} Zeichen, zu lang für die Sandbox")
        lauf = await self._anhalter.bis(self.sandbox.pruefen(s.code, s.sprache))
        if lauf is None:
            raise Angehalten
        if lauf.fehler is None and not lauf.zeitueberschreitung:
            return Vorpruefung(stand="laeuft", quelle="lauf", ausgabe=lauf.ausgabe[:AUSGABE_HOECHSTENS])
        fehler = fehlerzeile(lauf.fehler or "") or "Zeit überschritten"
        if self.ki.bereit:
            try:
                e = await self.einschaetzen(s, lauf.fehler or fehler)
                return Vorpruefung(stand="auszug", quelle="ki", fehler=fehler, grund=e.grund, fehlt=e.fehlt)
            except KiFehler as f:
                if f.art != "einzeln":
                    raise
                logger.info("Vorprüfung ohne Einschätzung: %s", f.grund)
        return Vorpruefung(stand="auszug", quelle="lauf", fehler=fehler, grund=fehler)

    async def einschaetzen(self, s: Codestelle, fehler: str) -> Einschaetzung:
        """Die lokale KI über die Leitstelle; im Hintergrund, wartet geduldig, wenn die Leitstelle gerade nicht kann."""
        nutzer = (f"Sprache: {s.sprache}\nTitel im Buch: {s.titel or '-'}\n\nCode:\n{s.code[:6000]}\n\n"
                  f"Fehler beim Lauf:\n{fehler[-1500:]}")
        roh = await self.ki.json_antwort(SYSTEM, nutzer, "vorpruefung", SCHEMA, titel=f"Vorprüfung {s.datei or s.sprache}",
                                         prioritaet="hintergrund", geduld=True, pruefen=self._pruefen_waehrend_warten,
                                         temperature=0.2, max_tokens=300)
        if not isinstance(roh, dict) or not isinstance(roh.get("satz"), str) or len(roh["satz"].split()) < 3:
            raise KiFehler("Die Antwort der KI passt nicht zur verlangten Form", "einzeln")
        fehlt = [w.strip().lower() for w in roh.get("fehlt") or [] if isinstance(w, str) and w.strip().lower() in FEHLT]
        return Einschaetzung(grund=roh["satz"].strip()[:200], fehlt=list(dict.fromkeys(fehlt)))

    async def _merken(self, sprache: str, pruefsumme: str, v: Vorpruefung) -> None:
        await db.execute("""INSERT OR REPLACE INTO code_vorpruefung(sprache, pruefsumme, stand, quelle, ausgabe, fehler, grund, fehlt)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                         (sprache, pruefsumme, v.stand, v.quelle, v.ausgabe, v.fehler, v.grund, json.dumps(v.fehlt)))
        await db.commit()


vorpruefer = Vorpruefer(sandbox, ki)
