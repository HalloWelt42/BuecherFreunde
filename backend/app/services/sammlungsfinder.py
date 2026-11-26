"""Sammlungen finden (BF-66): Reihen im Bestand erkennen und als Vorschläge anbieten.

Stufe 1, Regeln: aus dem Titel, sonst aus dem Dateinamen Reihe und Band lesen (`MUSTER`), etwa "Reihe 01 - Titel",
"Reihe - 12 - Titel", "Reihe Band 3 - Titel", "Reihe 3. Titel", "Titel (Reihe 4)" oder "Reihe, Band 2". Zusammen gehört,
was nach normiertem Reihennamen und normiertem ersten Autor gleich ist ("Nachname, Vorname" gleich "Vorname Nachname";
Groß und Klein, Umlaute, Akzente und Satzzeichen gleich). Bücher, die schon in einer Sammlung sind, zählen nicht. Ab
`SAMMLUNG_VORSCHLAG_AB` (3) Büchern mit mindestens zwei verschiedenen Bänden wird daraus ein Kandidat.

Stufe 2, lokale KI über die Leitstelle (nur wenn eingetragen): je Autor mit mehreren erkannten Reihen, ob verschiedene Namen
dieselbe Reihe sind (etwa eine Abkürzung und der volle Name) und wie sie richtig heißt; danach je Kandidat, ob die Bücher
wirklich eine Reihe bilden. Zwischen zwei Anfragen `SAMMLUNGEN_FINDEN_ABSTAND_S` Pause. Ohne KI, bei einer unbrauchbaren
Antwort oder wenn die Leitstelle nicht kann, bleiben die Regelfunde mit dem Hinweis, dass die KI nicht geprüft hat.

Die Vorschläge stehen in `sammlung_vorschlag` (Bücher in `sammlung_vorschlag_buch`); ein Lauf ersetzt die offenen.
Angelegte und verworfene Schlüssel werden nie wieder vorgeschlagen."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Literal, TypeVar

from appkern.leitstelle.arbeit import LAUFENDE_ARBEIT
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.models.grenzen import SAMMLUNG
from backend.app.services import autorennamen, vorschlaege
from backend.app.services.anhalten import Anhalter
from backend.app.services.ki import Ki, KiFehler, ki

logger = logging.getLogger("buecherfreunde.sammlungsfinder")
T = TypeVar("T")

# -- Stufe 1: Regeln --------------------------------------------------------------------------------------------------------

BANDWORT = r"(?:band|bd\.?|teil|folge|buch|vol\.?|volume|book|nr\.?|no\.?|#)"
NUMMER = r"(?P<band>\d{1,3})"
REIHE = r"(?P<reihe>.*?[^\W\d_].*?)"                                   # mit mindestens einem Buchstaben
REIHE_IN_KLAMMERN = r"(?P<reihe>[^()\[\]]*?[^\W\d_][^()\[\]]*?)"
MUSTER = (
    re.compile(rf"^(?P<titel>.+?)\s*[(\[]\s*{REIHE_IN_KLAMMERN}[\s,]*(?:{BANDWORT}\s*)?{NUMMER}\s*[)\]]$", re.I),  # Titel (Reihe 4)
    re.compile(rf"^{REIHE}[\s,:-]+{BANDWORT}\s*{NUMMER}(?:\s*[-:.,]\s*(?P<titel>.+))?$", re.I),                    # Reihe Band 3 - Titel
    re.compile(rf"^{REIHE}\s*[-:]\s*{NUMMER}\s*[-:]\s*(?P<titel>.+)$", re.I),                                       # Reihe - 12 - Titel
    re.compile(rf"^{REIHE}\s+{NUMMER}\.\s+(?P<titel>.+)$", re.I),                                                   # Reihe 3. Titel
    re.compile(rf"^{REIHE}\s+{NUMMER}\s*[-:]\s+(?P<titel>.+)$", re.I),                                              # Reihe 01 - Titel
)
NUR_BANDWORT = re.compile(rf"^{BANDWORT}$", re.I)
KEINE_REIHE = {"der", "die", "das", "den", "dem", "des", "ein", "eine", "the", "a", "an", "le", "la", "les"}
UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
RAND = " \t-:,.;#([)]"

Quelle = Literal["titel", "dateiname"]


class Erkannt(BaseModel):
    reihe: str
    band: str
    titel: str = ""


class Buchzeile(BaseModel):
    id: int
    title: str = ""
    author: str = ""
    file_name: str = ""


class Fund(BaseModel):
    """Ein Buch mit erkannter Reihe."""

    buch_id: int
    titel: str                                  # der Titel des Buchs, wie er dasteht
    reihe: str                                  # der Reihenname, wie er dasteht
    band: str
    quelle: Quelle
    autor_feld: str                             # das Autorenfeld, wie es dasteht
    autor: str                                  # erster Autor, "Vorname Nachname"
    autor_schluessel: str

    @property
    def schluessel(self) -> str:
        return f"{normiert(self.reihe)}|{self.autor_schluessel}"


class Kandidat(BaseModel):
    """Bücher, die eine Reihe sein könnten: aus einem Regelfund oder mehreren, die die KI zusammengeführt hat."""

    schluessel: list[str]                       # die Schlüssel der Regelfunde
    name: str
    autor: str
    autor_schluessel: str
    funde: list[Fund]
    ki_wege: list[str] = Field(default_factory=list)   # was die KI dazu beigetragen hat, als kurze Sätze
    ki: str = ""                                # Satz der KI, oder warum sie nicht geprüft hat
    ki_geprueft: bool = False
    ki_zweifel: bool = False                    # die KI hält es für keine Reihe

    def wege(self) -> list[str]:
        """Wie die Reihe gefunden wurde, als kurze deutsche Sätze."""
        wege = []
        for quelle, wort in (("titel", "Titel"), ("dateiname", "Dateinamen")):
            n = sum(f.quelle == quelle for f in self.funde)
            if n:
                wege.append(f"Reihe und Band im {wort} bei {n} {'Buch' if n == 1 else 'Büchern'}")
        if (n := len({f.reihe for f in self.funde})) > 1:
            wege.append(f"Name der Reihe in {n} Schreibweisen")
        if (n := len({f.autor_feld for f in self.funde})) > 1:
            wege.append(f"Autor in {n} Schreibweisen")
        return wege + self.ki_wege

    def ergebnis(self) -> vorschlaege.Ergebnis:
        return vorschlaege.Ergebnis(schluessel=self.schluessel, name=self.name, autor=self.autor, wege=self.wege(), ki=self.ki,
                                    ki_geprueft=self.ki_geprueft, ki_zweifel=self.ki_zweifel,
                                    baende=[vorschlaege.Bandangabe(buch_id=f.buch_id, band=f.band) for f in self.funde])


def normiert(text: str) -> str:
    """Klein, Umlaute ausgeschrieben, ohne Akzente, Bindestriche und Apostrophe; andere Satzzeichen trennen wie Leerzeichen."""
    t = unicodedata.normalize("NFKC", text or "").casefold().translate(UMLAUTE)
    t = "".join(z for z in unicodedata.normalize("NFKD", t) if not unicodedata.combining(z))
    t = re.sub(r"(?<=\w)[-'\u2019](?=\w)", "", t)                  # \u2019: das gesetzte Apostroph
    return " ".join(re.sub(r"[\W_]+", " ", t).split())


def erster_autor(feld: str) -> str:
    namen = autorennamen.zerlegen(feld)
    return namen[0] if namen else ""


def autor_schluessel(name: str) -> str:
    """Gleich für "Nachname, Vorname" und "Vorname Nachname": die Teile des Namens, sortiert."""
    return " ".join(sorted(normiert(name).split()))


def _reihe_taugt(reihe: str) -> bool:
    n = normiert(reihe)
    return len(n) >= 2 and not n.isdigit() and n not in KEINE_REIHE and not NUR_BANDWORT.match(reihe.strip(RAND))


def erkennen(text: str) -> Erkannt | None:
    """Reihe und Band aus einem Titel oder Dateinamen; None, wenn keins der Muster passt."""
    text = " ".join((text or "").split())
    for muster in MUSTER:
        if (t := muster.match(text)) is None:
            continue
        reihe, titel = t.group("reihe").strip(RAND), (t.group("titel") or "").strip(RAND)
        if muster is MUSTER[0] and NUR_BANDWORT.match(reihe):            # "Reihe (Band 4)": die Reihe steht vorn
            reihe, titel = titel, ""
        if _reihe_taugt(reihe):
            return Erkannt(reihe=reihe, band=str(int(t.group("band"))), titel=titel)
    return None


def ohne_autor(dateiname: str, schluessel: str) -> str:
    """Der Dateiname ohne Endung, ohne Unterstriche und ohne Stücke zwischen " - ", die nur der Autor sind."""
    stamm = dateiname.rsplit(".", 1)[0] if "." in dateiname else dateiname
    stuecke = re.split(r"\s+-\s+", " ".join(stamm.replace("_", " ").split()))
    return " - ".join(s for s in stuecke if not schluessel or autor_schluessel(erster_autor(s)) != schluessel)


def fund(buch: Buchzeile) -> Fund | None:
    autor = erster_autor(buch.author)
    schluessel = autor_schluessel(autor)
    for quelle, text in (("titel", buch.title), ("dateiname", ohne_autor(buch.file_name, schluessel))):
        if e := erkennen(text):
            return Fund(buch_id=buch.id, titel=buch.title or e.titel, reihe=e.reihe, band=e.band, quelle=quelle,
                        autor_feld=buch.author, autor=autor, autor_schluessel=schluessel)
    return None


def _haeufigster(werte: list[str]) -> str:
    return Counter(werte).most_common(1)[0][0] if werte else ""


def gruppieren(funde: list[Fund]) -> list[Kandidat]:
    """Ein Kandidat je Schlüssel, in der Reihenfolge der ersten Funde."""
    je: dict[str, list[Fund]] = defaultdict(list)
    for f in funde:
        je[f.schluessel].append(f)
    return [Kandidat(schluessel=[s], name=_haeufigster([f.reihe for f in fs]), autor=_haeufigster([f.autor for f in fs]),
                     autor_schluessel=fs[0].autor_schluessel, funde=fs) for s, fs in je.items()]


def reicht(k: Kandidat) -> bool:
    """Genug für einen Vorschlag: so viele Bücher wie eingestellt, mindestens zwei verschiedene Bände."""
    return len(k.funde) >= settings.sammlung_vorschlag_ab and len({f.band for f in k.funde}) >= 2


def regelfunde(buecher: list[Buchzeile], geschlossen: set[str]) -> list[Kandidat]:
    """Alle erkannten Reihen, auch kleine (die KI darf sie zusammenführen), ohne angelegte und verworfene."""
    funde = [f for b in buecher if (f := fund(b))]
    return [k for k in gruppieren(funde) if not set(k.schluessel) & geschlossen]


# -- Stufe 2: lokale KI -----------------------------------------------------------------------------------------------------

SYSTEM_GLEICH = ("Du ordnest die Bücher einer privaten Bibliothek in Reihen. Zu einem Autor bekommst du nummerierte Namen von "
                 "Reihen, die aus Titeln und Dateinamen erkannt wurden, je mit Bänden und Titeln. Manche Namen bezeichnen "
                 "dieselbe Reihe, etwa eine Abkürzung und der volle Name oder zwei Schreibweisen. Antworte mit einem Objekt "
                 "mit dem Feld 'reihen': je Reihe ein Eintrag mit 'nummern' (die Nummern der Namen, die zu ihr gehören) und "
                 "'name' (wie die Reihe richtig heißt). Jede Nummer steht in höchstens einem Eintrag.")
SCHEMA_GLEICH = {"type": "object", "additionalProperties": False, "required": ["reihen"],
                 "properties": {"reihen": {"type": "array", "description": "je Reihe ein Eintrag", "items": {
                     "type": "object", "additionalProperties": False, "required": ["nummern", "name"],
                     "properties": {"nummern": {"type": "array", "items": {"type": "integer"}, "description": "Nummern der Namen"},
                                    "name": {"type": "string", "description": "der richtige Name der Reihe"}}}}}}
SYSTEM_PRUEFEN = ("Du prüfst Vorschläge für Reihen in einer privaten Bibliothek. Du bekommst den vermuteten Namen einer Reihe, "
                  "den Autor und die Bücher mit Band und Titel. Urteile nur nach diesen Angaben: Gehören die Bücher nach Titeln "
                  "und Bandnummern zusammen, als Reihe, Folge oder mehrbändiges Werk? Ein unbekannter, abgekürzter oder anders "
                  "geschriebener Autor, eine Übersetzung, ein deutscher Titel oder Bände, die von einer bekannten Ausgabe "
                  "abweichen, sind kein Grund dagegen. Dagegen spricht nur, wenn die Titel offensichtlich nichts miteinander zu "
                  "tun haben oder die Nummern keine Bände sind (etwa Jahrgänge, Folien, Kapitel einzelner Dokumente). "
                  "Antworte mit einem Objekt aus drei Feldern: 'reihe' ist true, wenn die Bücher zusammengehören, sonst false; "
                  "'name' ist der Name der Reihe, wie er in den Titeln steht oder richtig heißt; 'satz' ist ein ganzer kurzer "
                  "deutscher Satz, warum.")
SCHEMA_PRUEFEN = {"type": "object", "additionalProperties": False, "required": ["reihe", "name", "satz"],
                  "properties": {"reihe": {"type": "boolean", "description": "true, wenn die Bücher eine Reihe bilden"},
                                 "name": {"type": "string", "description": "der richtige Name der Reihe"},
                                 "satz": {"type": "string", "description": "ein ganzer kurzer deutscher Satz"}}}
UNBRAUCHBAR = "Die KI hat nicht brauchbar geantwortet; gefunden nur nach Regeln"
TITEL_IN_DER_ANFRAGE = 12                     # so viele Bücher je Reihe nennt eine Anfrage


class Zusammenlegung(BaseModel):
    nummern: list[int]                         # ab 1, in der Reihenfolge der Anfrage
    name: str


class Urteil(BaseModel):
    reihe: bool
    name: str
    satz: str


def _form_falsch() -> KiFehler:
    return KiFehler("Die Antwort der KI passt nicht zur verlangten Form", "einzeln")


def zusammenlegungen_aus(roh: object, anzahl: int) -> list[Zusammenlegung]:
    """Die Antwort auf die Frage, welche Namen dieselbe Reihe sind; unbekannte und doppelte Nummern fallen weg."""
    if not isinstance(roh, dict) or not isinstance(roh.get("reihen"), list):
        raise _form_falsch()
    vergeben: set[int] = set()
    aus = []
    for r in roh["reihen"]:
        if not isinstance(r, dict) or not isinstance(r.get("nummern"), list) or not isinstance(r.get("name"), str):
            raise _form_falsch()
        nummern = [n for n in r["nummern"] if isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= anzahl and n not in vergeben]
        vergeben |= set(nummern)
        if nummern:
            aus.append(Zusammenlegung(nummern=list(dict.fromkeys(nummern)), name=r["name"]))
    return aus


def urteil_aus(roh: object) -> Urteil:
    if (not isinstance(roh, dict) or not isinstance(roh.get("reihe"), bool) or not isinstance(roh.get("name"), str)
            or not isinstance(roh.get("satz"), str) or len(roh["satz"].split()) < 3):
        raise _form_falsch()
    return Urteil(reihe=roh["reihe"], name=roh["name"], satz=" ".join(roh["satz"].split())[:300])


def kiname(name: str) -> str | None:
    """Ein Name von der KI, wenn er als Name einer Sammlung taugt."""
    name = " ".join((name or "").split())
    return name if 0 < len(name) <= SAMMLUNG else None


def _baende(k: Kandidat) -> str:
    funde = sorted(k.funde, key=lambda f: (int(f.band), f.titel))[:TITEL_IN_DER_ANFRAGE]
    return "; ".join(f"Band {f.band}: {f.titel or '-'}" for f in funde)


def anfrage_gleich(gruppen: list[Kandidat]) -> str:
    zeilen = [f"Autor: {gruppen[0].autor or '-'}", ""]
    zeilen += [f"{i}. {k.name} ({_baende(k)})" for i, k in enumerate(gruppen, 1)]
    return "\n".join(zeilen)


def anfrage_pruefen(k: Kandidat) -> str:
    return f"Reihe: {k.name}\nAutor: {k.autor or '-'}\nBücher: {_baende(k)}"


def aufzaehlung(namen: list[str]) -> str:
    """Namen als Aufzählung: A, B und C."""
    return f"{', '.join(namen[:-1])} und {namen[-1]}" if len(namen) > 1 else "".join(namen)


def zusammenlegen(gruppen: list[Kandidat], legungen: list[Zusammenlegung]) -> list[Kandidat]:
    """Die Gruppen eines Autors nach der Antwort der KI; was sie nicht nennt, bleibt, wie es war."""
    aus, genannt = [], set()
    for z in legungen:
        teile = [gruppen[n - 1] for n in z.nummern]
        genannt |= set(z.nummern)
        k = teile[0].model_copy(update={"schluessel": [s for t in teile for s in t.schluessel], "funde": [f for t in teile for f in t.funde],
                                        "ki_wege": []})
        if len(teile) > 1:
            k.ki_wege.append(f"Die KI führt {aufzaehlung([t.name for t in teile])} zusammen")
        if (name := kiname(z.name)) and name != k.name:
            k.ki_wege.append(f"Die KI nennt die Reihe {name}")
            k.name = name
        aus.append(k)
    return aus + [g for i, g in enumerate(gruppen, 1) if i not in genannt]


# -- Lauf und Vorschläge ----------------------------------------------------------------------------------------------------

class SuchStand(BaseModel):
    laeuft: bool
    schritt: str = ""                          # was der Lauf gerade tut
    gefunden: int = 0                          # offene Vorschläge; während des Laufs die bisher gefundenen
    grund: str = ""                            # warum die KI nicht geprüft hat, oder warum der Lauf endete


class Angehalten(Exception):
    pass


class Sammlungsfinder:
    def __init__(self, ki: Ki) -> None:
        self.ki = ki
        self._anhalter = Anhalter()
        self._lauf: asyncio.Task | None = None
        self._gefragt = 0
        self.laeuft = False
        self.schritt = ""
        self.gefunden = 0
        self.grund = ""

    # -- Leben und Bedienung ---------------------------------------------------------------------------------------------
    def starten(self) -> None:
        """Ein Lauf im Hintergrund; läuft schon einer, bleibt es bei ihm."""
        if not self.laeuft:
            self.laeuft, self.schritt = True, "Beginnt"
            self._lauf = asyncio.create_task(self._im_hintergrund())

    async def stoppen(self) -> None:
        self._anhalter.halte()
        if self._lauf is not None:
            self._lauf.cancel()
            self._lauf = None

    async def warten(self) -> None:
        """Bis der laufende Lauf zu Ende ist."""
        if self._lauf is not None:
            await asyncio.shield(self._lauf)

    async def stand(self) -> SuchStand:
        if self.laeuft:
            return SuchStand(laeuft=True, schritt=self.schritt, gefunden=self.gefunden, grund=self.grund)
        z = await db.fetch_one("SELECT COUNT(*) AS n FROM sammlung_vorschlag WHERE stand = 'offen'")
        return SuchStand(laeuft=False, gefunden=z["n"] if z else 0, grund=self.grund)

    # -- Arbeit ----------------------------------------------------------------------------------------------------------
    async def _im_hintergrund(self) -> None:
        try:
            await self.suchen()
        except asyncio.CancelledError:
            raise
        except Exception:                                  # noqa: BLE001 - ein Fehler endet den Lauf mit Grund, nie still
            logger.exception("Sammlungen finden")
            self.grund = "Die Suche ist mit einem Fehler abgebrochen"

    async def suchen(self) -> int:
        """Ein ganzer Lauf: Regeln, KI, Vorschläge merken. Gibt zurück, wie viele Vorschläge offen sind."""
        self._anhalter.beginne()
        marke = LAUFENDE_ARBEIT.set(f"bf-sammlungen-{uuid.uuid4().hex[:12]}")
        self.laeuft, self.schritt, self.gefunden, self.grund, self._gefragt = True, "Titel und Dateinamen lesen", 0, "", 0
        try:
            zeilen = await db.fetch_all("SELECT id, title, author, file_name FROM books WHERE sammlung_id IS NULL ORDER BY id")
            buecher = [Buchzeile(**z) for z in zeilen]
            gruppen = await asyncio.to_thread(regelfunde, buecher, await vorschlaege.geschlossene_schluessel())
            self.gefunden = sum(map(reicht, gruppen))
            kandidaten = await self._mit_ki(gruppen)
            self.schritt = "Vorschläge merken"
            self.gefunden = await self._merken(kandidaten)
            return self.gefunden
        except Angehalten:
            return 0
        finally:
            self.laeuft, self.schritt = False, ""
            LAUFENDE_ARBEIT.reset(marke)

    async def _mit_ki(self, gruppen: list[Kandidat]) -> list[Kandidat]:
        if not self.ki.bereit:
            self.grund = "Die KI hat nicht geprüft: Keine Leitstelle eingetragen"
        gruppen = await self._zusammenfuehren(gruppen)
        kandidaten = [g for g in gruppen if reicht(g)]
        self.gefunden = len(kandidaten)
        return await self._pruefen(kandidaten)

    async def _zusammenfuehren(self, gruppen: list[Kandidat]) -> list[Kandidat]:
        """Je Autor mit mehreren erkannten Reihen: welche Namen dieselbe Reihe sind."""
        je_autor: dict[str, list[Kandidat]] = defaultdict(list)
        for g in gruppen:
            je_autor[g.autor_schluessel].append(g)
        gefragt = [a for a, gs in je_autor.items()
                   if a and len(gs) > 1 and sum(len(g.funde) for g in gs) >= settings.sammlung_vorschlag_ab]
        aus = [g for a, gs in je_autor.items() if a not in gefragt for g in gs]
        for i, gs in enumerate((je_autor[a] for a in gefragt), 1):
            self.schritt = f"KI vergleicht die Reihen von {gs[0].autor} ({i} von {len(gefragt)})"
            legungen = await self._frage(SYSTEM_GLEICH, anfrage_gleich(gs), "reihen_gleich", SCHEMA_GLEICH,
                                         f"Reihen vergleichen: {gs[0].autor[:80]}", lambda roh, n=len(gs): zusammenlegungen_aus(roh, n))
            aus += zusammenlegen(gs, legungen or [])
        return aus

    async def _pruefen(self, kandidaten: list[Kandidat]) -> list[Kandidat]:
        """Je Kandidat: bilden die Bücher wirklich eine Reihe? Verneint die KI, bleibt der Vorschlag mit ihrem Zweifel
        sichtbar; entscheiden darf nur der Mensch (BF-66)."""
        behalten = []
        for i, k in enumerate(kandidaten, 1):
            self.schritt = f"KI prüft die Reihe {k.name} ({i} von {len(kandidaten)})"
            u = await self._frage(SYSTEM_PRUEFEN, anfrage_pruefen(k), "reihe_pruefen", SCHEMA_PRUEFEN, f"Reihe prüfen: {k.name[:80]}", urteil_aus)
            if u is None:
                k.ki = self.grund or UNBRAUCHBAR
            elif not u.reihe:
                logger.info("Die KI hält %s für keine Reihe: %s", k.name, u.satz)
                k.ki, k.ki_geprueft, k.ki_zweifel = u.satz, True, True
            else:
                k.ki, k.ki_geprueft = u.satz, True
                if (name := kiname(u.name)) and name != k.name:
                    k.ki_wege.append(f"Die KI nennt die Reihe {name}")
                    k.name = name
            behalten.append(k)
        return behalten

    async def _frage(self, system: str, nutzer: str, schema_name: str, schema: dict, titel: str, lesen: Callable[[object], T]) -> T | None:
        """Die gelesene Antwort der KI; None, wenn sie unbrauchbar ist oder die KI nicht kann. Kann sie nicht (nicht
        eingetragen, weg, abgelehnt), steht das in `grund`, und keine weitere Anfrage geht hinaus."""
        if self.grund:
            return None
        if self._gefragt:
            await self._pause()
        self._gefragt += 1
        try:
            roh = await self.ki.json_antwort(system, nutzer, schema_name, schema, titel=titel, prioritaet="hintergrund", geduld=True,
                                             pruefen=self._pruefen_waehrend_warten, temperature=0.1, max_tokens=400)
            return lesen(roh)
        except KiFehler as f:
            if f.art != "einzeln":
                self.grund = f"Die KI hat nicht geprüft: {f.grund}"
            logger.info("Sammlungen finden: %s", f.grund)
            return None

    @staticmethod
    async def _merken(kandidaten: list[Kandidat]) -> int:
        """Die Kandidaten als Vorschläge. Was inzwischen angelegt oder verworfen wurde, und Bücher, die inzwischen in einer
        Sammlung sind, bleiben draußen; wer dann nicht mehr reicht, auch."""
        async with db.einheit():
            geschlossen = await vorschlaege.geschlossene_schluessel()
            frei = await vorschlaege.ohne_sammlung({f.buch_id for k in kandidaten for f in k.funde})
            noch = [k.model_copy(update={"funde": [f for f in k.funde if f.buch_id in frei]}) for k in kandidaten]
            return await vorschlaege.merken([k.ergebnis() for k in noch if reicht(k) and not set(k.schluessel) & geschlossen])

    async def _pause(self) -> None:
        await self._anhalter.bis(asyncio.sleep(settings.sammlungen_finden_abstand_s))
        if self._anhalter.gehalten:
            raise Angehalten

    async def _pruefen_waehrend_warten(self) -> None:
        if self._anhalter.gehalten:
            raise Angehalten


sammlungsfinder = Sammlungsfinder(ki)
