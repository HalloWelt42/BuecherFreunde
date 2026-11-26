"""Der Lauf der Übersetzung im Hintergrund (BF-71), wie Einordnen und Umschlagprüfung: eine Fassung nach der anderen, jede an
ihrem ersten offenen Block. Nach einem Neustart oder Ausrollen nimmt er jede Fassung mit Stand "laeuft" wieder auf; was
eine Antwort der KI ergab, steht nach jedem Schritt in der Datenbank, also geht keine Portion verloren und keine doppelt.

Stationen je Fassung: Zerlegen (einmal, wieder bei anderen Einstellungen), Begriffe (Regeln, dann Vorschlag der KI), dann
Kapitel für Kapitel Übersetzen (Portionen, Zwischenspeicher), Prüfen (KI-Prüfer) und Nacharbeit (bis UEBERSETZEN_NACHARBEITEN,
Rest bleibt offen im Original), zuletzt Setzen und Ablegen. Fertige Kapitel sind sofort lesbar: die Datei für den Leser
wird bis dahin aus den Blöcken gesetzt (api/uebersetzung.py).

Ändern sich die festen Prüfungen (fassungen.geprueft_mit), prüft der nächste Durchgang zuerst die Begriffsliste des Buchs
(Einträge von Regel und KI, die die Regeln nicht mehr bestehen, werden fragwürdig und gelten nicht, bis der Nutzer
entscheidet), dann alles neu, was die KI schon übersetzt hat, ohne neue Anfrage: was besteht, bleibt bestanden (eine offene
Stelle, die nur an den festen Prüfungen oder an einem Einwand des Prüfers scheiterte, der nicht mehr gilt, geht zum Prüfer);
was neu durchfällt, geht mit vollen Nacharbeiten in die Nacharbeit. Texte und Annahmen des Nutzers bleiben unberührt.

Einwände des Prüfers anderer Art als Sinn, Ausgelassenes und Hinzugefügtes gelten nicht (uebersetzung/pruefer.py); sie
werden verworfen und an der Fassung gezählt. Kommt eine Nacharbeit unverändert zurück, steht das als Befund dabei, damit die
nächste Nacharbeit (bei Temperatur 0) nicht dieselbe Anfrage ist.

Anhalten (Pause, Abbrechen, Herunterfahren) wirkt sofort, auch mitten in einer Anfrage; deren Ergebnis fehlt dann und die
Portion kommt beim Fortsetzen neu. Ist die Leitstelle weg, länger als die Geduld reicht, oder das Original gerade nicht zu
holen, endet nur die Runde (Grund am Stand); lehnt die Leitstelle ab, steht die Fassung auf "fehler", bis ein Mensch sie
fortsetzt. Nichts wird von selbst still eingesetzt: was die Prüfungen nicht besteht, bleibt im Original und steht im Bericht."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from appkern.leitstelle import LeitstellenFehler
from appkern.leitstelle.arbeit import LAUFENDE_ARBEIT

from backend.app.ablage.wolke import WolkeFehler
from backend.app.core.config import settings
from backend.app.models.fassung import NACHZUPRUEFEN, Stationsname
from backend.app.services import begriffsliste, fassung_ablage, fassungen
from backend.app.services.anhalten import Anhalter
from backend.app.services.fassungen import BlockZeile, Buchangaben, FassungZeile, KapitelZeile
from backend.app.services.ki import Ki, KiFehler, fehler as ki_fehler, ki
from backend.app.uebersetzung import anweisungen, begriffe, marken, vorgaben
from backend.app.uebersetzung.anweisungen import FASSUNG as ANWEISUNG
from backend.app.uebersetzung.begriffe import Buchtext
from backend.app.uebersetzung.modelle import Anrede, Befund, Begriff, Unbrauchbar
from backend.app.uebersetzung.pruefen import pruefen
from backend.app.uebersetzung.pruefer import Urteil, gilt as einwand_gilt, pruefen_lassen
from backend.app.uebersetzung.uebersetzen import Auftrag, nacharbeiten, portionen, speicherschluessel, uebersetzen
from backend.app.uebersetzung.werk import NichtLesbar

logger = logging.getLogger("buecherfreunde.uebersetzungslauf")
ANTWORT_TOKEN = 8192                                 # Obergrenze je Antwort; eine Portion braucht weit weniger
KEINE_ANTWORT = "Die KI hat keine brauchbare Übersetzung geliefert"
UNVERAENDERT = "Die Nacharbeit kam unverändert zurück; die Mängel bestehen weiter"


class Angehalten(Exception):
    pass


class NichtJetzt(Exception):
    """Gerade geht es nicht (Original nicht zu holen, keine Leitstelle, Kellerwolke weg); die Runde endet, der Lauf bleibt."""


@dataclass
class Jetzt:
    fassung: int
    station: Stationsname
    kapitel: int | None = None
    block: str | None = None


class KiAnfrage:
    """Eine Anfrage an die KI für die Fachschicht: im Hintergrund, geduldig, sofort anhaltbar; eine unbrauchbare Antwort
    ist `Unbrauchbar`, alles andere geht an den Lauf."""

    def __init__(self, ki_: Ki, anhalter: Anhalter) -> None:
        self._ki, self._anhalter = ki_, anhalter

    async def __call__(self, system: str, nutzer: str, *, schema_name: str, schema: dict[str, Any], titel: str, modell: str = "") -> Any:
        if self._anhalter.gehalten:
            raise Angehalten
        try:
            roh = await self._anhalter.bis(self._ki.json_antwort(system, nutzer, schema_name, schema, titel=titel, prioritaet="hintergrund",
                                                                 geduld=True, pruefen=self._waehrend_warten, modell=modell,
                                                                 temperature=0, max_tokens=ANTWORT_TOKEN))
        except KiFehler as f:
            if f.art == "einzeln":
                raise Unbrauchbar(f.grund) from f
            raise
        if roh is None and self._anhalter.gehalten:
            raise Angehalten
        return roh

    async def _waehrend_warten(self) -> None:
        if self._anhalter.gehalten:
            raise Angehalten


class Uhr:
    """Misst die Zeit, die an einer Fassung gerechnet wird, je Kapitel."""

    def __init__(self, fid: int) -> None:
        self.fid, self.kapitel, self._seit = fid, None, time.monotonic()

    async def merken(self) -> None:
        jetzt = time.monotonic()
        sekunden, self._seit = jetzt - self._seit, jetzt
        await fassungen.zeit_merken(self.fid, self.kapitel, sekunden)


def _nach_mangel(z: BlockZeile) -> str:
    return "nacharbeit" if z.nacharbeiten < settings.uebersetzen_nacharbeiten else "offen"


def geprueft(z: BlockZeile, text: str | None, gilt: list[Begriff], anrede: Anrede) -> BlockZeile:
    """Nach einer Antwort der KI: die festen Prüfungen. Bestanden wartet auf den Prüfer, sonst Nacharbeit, oder offen,
    wenn keine Nacharbeit mehr bleibt. Ohne brauchbare Antwort bleibt die frühere Übersetzung für den Bericht stehen."""
    if text is None:
        return z.model_copy(update={"stand": _nach_mangel(z), "versuche": z.versuche + 1,
                                    "befunde": [Befund(art="antwort", quelle="pruefung", text=KEINE_ANTWORT)]})
    befunde = pruefen(z.vorlage, text, gilt, fassungen.grenzen(), anrede)
    return z.model_copy(update={"uebersetzung": text, "befunde": befunde, "versuche": z.versuche + 1,
                                "stand": "uebersetzt" if not befunde else _nach_mangel(z)})


def nachgeprueft(z: BlockZeile, gilt: list[Begriff], anrede: Anrede) -> BlockZeile | None:
    """Ein Block, den die KI übersetzt hat, nach geänderten Prüfungen noch einmal fest geprüft, ohne neue Anfrage; None,
    wenn alles bleibt. Rohe Zeichen einer früheren Antwort (<, &) werden dabei sicher geschrieben. Besteht er, bleibt sein
    Stand; eine offene Stelle, die nur an den festen Prüfungen oder an einem Einwand des Prüfers scheiterte, der nicht mehr
    gilt (über Begriffe, Grammatik), geht zum Prüfer. Fällt er durch, geht er mit vollen Nacharbeiten in die Nacharbeit.
    Eine Stelle ohne Übersetzung oder mit einem Mangel des Prüfers, der gilt, bleibt offen."""
    if not z.uebersetzung:
        return None
    text = marken.gesichert(z.uebersetzung, z.vorlage)
    befunde = pruefen(z.vorlage, text, gilt, fassungen.grenzen(), anrede)
    if befunde:
        return z.model_copy(update={"uebersetzung": text, "befunde": befunde, "stand": "nacharbeit", "nacharbeiten": 0})
    if z.stand == "offen" and not any(b.quelle == "ki" and einwand_gilt(b) for b in z.befunde):
        return z.model_copy(update={"uebersetzung": text, "befunde": [], "stand": "uebersetzt", "geprueft": False})
    return z.model_copy(update={"uebersetzung": text}) if text != z.uebersetzung else None


def nicht_geltende_einwaende(z: BlockZeile) -> int:
    return sum(not einwand_gilt(b) for b in z.befunde)


class Uebersetzungslauf:
    def __init__(self, ki_: Ki) -> None:
        self.ki = ki_
        self._anhalter = Anhalter()
        self._anfrage = KiAnfrage(ki_, self._anhalter)
        self._wecker = asyncio.Event()
        self._lauf: asyncio.Task | None = None
        self._ende = False
        self._aktuell: int | None = None                 # die Fassung, an der gerade gearbeitet wird
        self.jetzt: Jetzt | None = None

    # -- Leben und Bedienung ---------------------------------------------------------------------------------------------
    def starten(self) -> None:
        self._ende = False
        self._wecker = asyncio.Event()
        self._lauf = asyncio.create_task(self._arbeiten())

    async def stoppen(self) -> None:
        self._ende = True
        self._anhalter.halte()
        if self._lauf is not None:
            self._lauf.cancel()
            self._lauf = None

    def anstossen(self) -> None:
        self._wecker.set()

    def halten(self, fid: int) -> None:
        """Die Arbeit an dieser Fassung sofort anhalten (Pause, Abbrechen); die Runde geht mit der nächsten weiter. Wer den
        Stand ändert, bucht ihn vorher: der Lauf liest ihn zu Beginn jeder Fassung noch einmal."""
        if self._aktuell == fid:
            self._anhalter.halte()

    # -- Runden ----------------------------------------------------------------------------------------------------------
    async def _arbeiten(self) -> None:
        while True:
            try:
                await self.runde()
            except asyncio.CancelledError:
                raise
            except Exception:                              # noqa: BLE001 - der Lauf darf nie still enden
                logger.exception("Übersetzen")
            try:
                await asyncio.wait_for(self._wecker.wait(), settings.uebersetzen_takt_s)
            except TimeoutError:
                pass
            self._wecker.clear()

    async def runde(self) -> int:
        """Alle Fassungen mit Arbeit, je einmal; gibt zurück, wie viele bearbeitet wurden."""
        await begriffsliste.vorgaben_einspielen()
        gesehen: set[int] = set()
        while not self._ende and (f := await fassungen.naechste(gesehen)) is not None:
            gesehen.add(f.id)
            if not await self._fassung(f):
                break
        return len(gesehen)

    async def _fassung(self, f: FassungZeile) -> bool:
        """False, wenn die Runde enden soll."""
        self._anhalter.beginne()
        self._aktuell = f.id
        marke = LAUFENDE_ARBEIT.set(f"bf-uebersetzen-{f.id}-{uuid.uuid4().hex[:8]}")
        uhr = Uhr(f.id)
        try:
            await self._bearbeiten(f, uhr)
            return True
        except Angehalten:
            return not self._ende
        except KiFehler as e:
            if e.art == "abgelehnt":                       # ein Mensch ist gefragt; nichts wird von selbst wiederholt
                await fassungen.stand_setzen(f.id, "fehler", e.grund, nur_aus=("laeuft",))
            else:
                await fassungen.aendern(f.id, grund=e.grund)
            logger.warning("Übersetzen von Fassung %d unterbrochen: %s", f.id, e.grund)
            return False
        except NichtJetzt as e:
            await fassungen.aendern(f.id, grund=str(e))
            return False
        except NichtLesbar as e:
            await fassungen.stand_setzen(f.id, "fehler", str(e))
            return True
        except Exception as e:                             # noqa: BLE001 - mit Grund am Stand, nie still
            logger.exception("Übersetzen von Fassung %d", f.id)
            await fassungen.stand_setzen(f.id, "fehler", f"Unerwarteter Fehler: {type(e).__name__}: {e}"[:300])
            return True
        finally:
            await uhr.merken()
            self.jetzt, self._aktuell = None, None
            LAUFENDE_ARBEIT.reset(marke)

    async def _bearbeiten(self, gewaehlt: FassungZeile, uhr: Uhr) -> None:
        f = await fassungen.holen(gewaehlt.id)               # der Stand, wie er jetzt gilt (Pause kurz vor dem Beginn)
        b = await fassungen.buch(gewaehlt.buch_id)
        if f is None or b is None or f.stand != gewaehlt.stand:
            return
        original: bytes | None = None
        if f.stand == "laeuft":
            if not self.ki.bereit:
                raise NichtJetzt("Keine Leitstelle eingetragen (LEITSTELLE_ADRESSE, LEITSTELLE_SCHLUESSEL_DATEI)")
            await fassungen.aendern(f.id, grund="", **({"begonnen": fassungen.jetzt()} if f.begonnen is None else {}))
            if f.zerlegt != fassungen.zerlegt_mit(b.format):
                self.jetzt = Jetzt(f.id, "Zerlegen")
                original = await self._original(b)
                await fassungen.abgleichen(f.id, await asyncio.to_thread(fassungen.werk_aus, b, original))
            if not f.begriffe_fertig:
                await self._begriffe(f, b)
            await self._modelle_merken(f)
            if f.geprueft_mit != fassungen.geprueft_mit():
                await self._nachpruefen(f)
            for kap in await fassungen.kapitel(f.id):
                if await fassungen.bloecke(f.id, kap.nr, ("wartet", "uebersetzt", "nacharbeit")):
                    await self._kapitel(f, b, kap, uhr)
            neu = await fassungen.holen(f.id)
            if neu is None or neu.stand != "laeuft":
                return
        self.jetzt = Jetzt(f.id, "Setzen")
        await self._setzen(f.id, b, original)
        if await fassungen.offen_in_arbeit(f.id) == 0:
            await fassungen.stand_setzen(f.id, "fertig", nur_aus=("laeuft",))

    async def _original(self, b: Buchangaben) -> bytes:
        daten = await fassungen.original_lesen(b)
        if daten is None:
            raise NichtJetzt("Das Original ist gerade nicht zu holen")
        return daten

    async def _modelle_merken(self, f: FassungZeile) -> None:
        try:
            modell, pruefmodell = await self.ki.fuer(), await self.ki.fuer(settings.uebersetzen_pruefmodell)
        except LeitstellenFehler as e:
            raise ki_fehler(e, self.ki.modell()) from e
        await fassungen.aendern(f.id, modell=modell, pruefmodell=pruefmodell, anweisung=ANWEISUNG)

    async def _nachpruefen(self, f: FassungZeile) -> None:
        """Die festen Prüfungen haben sich geändert: erst die Begriffsliste nach den Regeln von heute (fragwürdige Einträge
        gelten nicht), dann wird, was die KI übersetzt hat, ohne neue Anfrage noch einmal geprüft."""
        self.jetzt = Jetzt(f.id, "Prüfen")
        fragwuerdig = await begriffsliste.fragwuerdige_markieren(f.buch_id, Buchtext.aus([z.als_block() for z in await fassungen.bloecke(f.id)]))
        gilt = await begriffsliste.gelten(f.buch_id)
        alt = await fassungen.bloecke(f.id, staende=NACHZUPRUEFEN)
        paare = [(z, n) for z in alt if (n := nachgeprueft(z, gilt, f.anrede)) is not None]
        await fassungen.bloecke_merken(f.id, [n for _, n in paare])
        await fassungen.verworfen_zaehlen(f.id, sum(nicht_geltende_einwaende(z) for z, _ in paare))
        await fassungen.aendern(f.id, geprueft_mit=fassungen.geprueft_mit())
        if paare or fragwuerdig:
            logger.info("Fassung %d nach geänderten Prüfungen neu geprüft: %d Blöcke geändert, %d Begriffe fragwürdig", f.id, len(paare),
                        fragwuerdig)

    # -- Begriffe --------------------------------------------------------------------------------------------------------
    async def _begriffe(self, f: FassungZeile, b: Buchangaben) -> None:
        self.jetzt = Jetzt(f.id, "Begriffe")
        bloecke = [z.als_block() for z in await fassungen.bloecke(f.id)]
        text = Buchtext.aus(bloecke)
        kapitel = await fassungen.kapitel(f.id)
        nach_regeln = await begriffsliste.kandidaten_merken(
            f.buch_id, begriffe.namen_aus(text, await begriffsliste.vorhandene(f.buch_id), vorgaben.alltagswoerter()))
        vorhanden = await begriffsliste.vorhandene(f.buch_id)
        nachricht = json.dumps({"titel": b.title, "verzeichnis": [k.titel for k in kapitel],
                                "stichwoerter": begriffe.stichwoerter([(k.titel, [x for x in bloecke if x.kapitel == k.nr]) for k in kapitel]),
                                "proben": begriffe.proben(bloecke), "vorhanden": sorted(vorhanden)}, ensure_ascii=False)
        try:
            roh = await self._anfrage(anweisungen.begriffe(begriffe.VORSCHLAG_HOECHSTENS), nachricht, schema_name="begriffe",
                                      schema=begriffe.SCHEMA_VORSCHLAG, titel=f"Begriffe: {b.title[:80]}")
            vorschlaege = begriffe.vorschlaege_aus(roh, text, vorhanden, vorgaben.alltagswoerter(), vorgaben.englisch_im_fach())
            bericht = f"{nach_regeln} nach Regeln, {await begriffsliste.kandidaten_merken(f.buch_id, vorschlaege)} von der KI"
        except (Unbrauchbar, ValueError) as e:
            bericht = f"{nach_regeln} nach Regeln; ohne Vorschlag der KI: {e}"
        await begriffsliste.fragwuerdige_markieren(f.buch_id, text)
        await fassungen.aendern(f.id, begriffe_fertig=1, begriffe_text=bericht)

    # -- Kapitel ---------------------------------------------------------------------------------------------------------
    async def _kapitel(self, f: FassungZeile, b: Buchangaben, kap: KapitelZeile, uhr: Uhr) -> None:
        await uhr.merken()
        uhr.kapitel = kap.nr
        gilt = await begriffsliste.gelten(f.buch_id)
        auftrag = Auftrag(kapitel=kap.titel, begriffe=gilt, anrede=f.anrede,
                          titel=f"Übersetzen: {b.title[:60]}, {kap.titel[:40]}")
        pruefauftrag = auftrag.model_copy(update={"titel": f"Prüfen: {b.title[:60]}, {kap.titel[:40]}",
                                                  "modell": settings.uebersetzen_pruefmodell})
        await self._aus_dem_speicher(f, kap, auftrag)
        await self._uebersetzen(f, kap, auftrag, uhr)
        while await self._pruefen(f, kap, pruefauftrag, auftrag, uhr) or await self._nacharbeiten(f, kap, auftrag, uhr):
            pass

    async def _aus_dem_speicher(self, f: FassungZeile, kap: KapitelZeile, auftrag: Auftrag) -> None:
        """Was schon einmal geprüft übersetzt wurde (gleiche Vorlage, gleiche Begriffe), kommt ohne Anfrage; es muss die
        festen Prüfungen wieder bestehen."""
        gefunden = []
        for z in await fassungen.bloecke(f.id, kap.nr, ("wartet",)):
            text = await fassungen.speicher_holen(speicherschluessel(z.vorlage, auftrag, f.sprache))
            if text is not None and not pruefen(z.vorlage, text, auftrag.begriffe, fassungen.grenzen(), auftrag.anrede):
                gefunden.append(z.model_copy(update={"uebersetzung": text, "stand": "bestanden", "befunde": [], "geprueft": True}))
        await fassungen.bloecke_merken(f.id, gefunden)

    async def _uebersetzen(self, f: FassungZeile, kap: KapitelZeile, auftrag: Auftrag, uhr: Uhr) -> None:
        while True:
            alle = await fassungen.bloecke(f.id, kap.nr)
            wartend = [z for z in alle if z.stand == "wartet"]
            if not wartend:
                return
            portion = portionen([z.als_block() for z in wartend], settings.uebersetzen_portion_zeichen, settings.uebersetzen_portion_bloecke)[0]
            self.jetzt = Jetzt(f.id, "Übersetzen", kap.nr, portion[0].kennung)
            texte = await uebersetzen(self._anfrage, portion, auftrag, [z.als_block() for z in alle if z.nr < portion[0].nr])
            je = {z.kennung: z for z in wartend}
            await fassungen.bloecke_merken(f.id, [geprueft(je[k], text, auftrag.begriffe, auftrag.anrede) for k, text in texte.items()])
            await uhr.merken()

    async def _pruefen(self, f: FassungZeile, kap: KapitelZeile, pruefauftrag: Auftrag, auftrag: Auftrag, uhr: Uhr) -> bool:
        bereit = await fassungen.bloecke(f.id, kap.nr, ("uebersetzt",))
        if not bereit:
            return False
        je = {z.kennung: z for z in bereit}
        for portion in portionen([z.als_block() for z in bereit], settings.uebersetzen_portion_zeichen, settings.uebersetzen_portion_bloecke):
            self.jetzt = Jetzt(f.id, "Prüfen", kap.nr, portion[0].kennung)
            urteile = await pruefen_lassen(self._anfrage, [(x, je[x.kennung].uebersetzung) for x in portion], pruefauftrag)
            neu, speicher = [], {}
            for x in portion:
                z, mangel = je[x.kennung], urteile.get(x.kennung, Urteil()).mangel
                if mangel is None:
                    neu.append(z.model_copy(update={"stand": "bestanden" if z.nacharbeiten == 0 else "nachgearbeitet", "befunde": [],
                                                    "geprueft": True}))
                    speicher[speicherschluessel(z.vorlage, auftrag, f.sprache)] = z.uebersetzung
                else:
                    neu.append(z.model_copy(update={"stand": _nach_mangel(z), "befunde": [mangel], "geprueft": True}))
            await fassungen.bloecke_merken(f.id, neu)
            await fassungen.speicher_merken(speicher)
            await fassungen.verworfen_zaehlen(f.id, sum(u.verworfen for u in urteile.values()))
            await uhr.merken()
        return True

    async def _nacharbeiten(self, f: FassungZeile, kap: KapitelZeile, auftrag: Auftrag, uhr: Uhr) -> bool:
        alle = await fassungen.bloecke(f.id, kap.nr)
        offen = [z for z in alle if z.stand == "nacharbeit"]
        if not offen:
            return False
        for z in offen:
            if z.nacharbeiten >= settings.uebersetzen_nacharbeiten:       # keine Nacharbeit mehr übrig
                await fassungen.bloecke_merken(f.id, [z.model_copy(update={"stand": "offen"})])
                continue
            self.jetzt = Jetzt(f.id, "Nacharbeit", kap.nr, z.kennung)
            text = await nacharbeiten(self._anfrage, z.als_block(), z.uebersetzung, z.befunde, auftrag,
                                      [y.als_block() for y in alle if y.nr < z.nr])
            neu = geprueft(z.model_copy(update={"nacharbeiten": z.nacharbeiten + 1}), text, auftrag.begriffe, auftrag.anrede)
            if text == z.uebersetzung and neu.befunde:
                neu.befunde.append(Befund(art="antwort", quelle="pruefung", text=UNVERAENDERT))
            await fassungen.bloecke_merken(f.id, [neu])
            await uhr.merken()
        return True

    # -- Setzen ----------------------------------------------------------------------------------------------------------
    async def _setzen(self, fid: int, b: Buchangaben, original: bytes | None) -> None:
        f = await fassungen.holen(fid)
        if f is None:
            return
        stand = f.aenderungen
        satz = await fassungen.satz(f)
        daten = await asyncio.to_thread(fassungen.epub_bauen, b, original or await self._original(b), satz)
        try:
            pfad, knoten = await fassung_ablage.ablegen(f, b, daten)
        except WolkeFehler as e:
            raise NichtJetzt(f"Die deutsche Fassung kam nicht in die Kellerwolke: {e.meldung}") from e
        await fassungen.aendern(fid, datei=pfad, knoten=knoten, gesetzt=stand)


uebersetzungslauf = Uebersetzungslauf(ki)
