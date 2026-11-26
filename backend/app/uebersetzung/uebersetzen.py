"""Übersetzen in Portionen (BF-71, nach Nachschlag artikel.py).

Eine Portion sind Blöcke bis etwa `zeichen` Zeichen oder `hoechstens` Blöcke, immer an Blockgrenzen. Im Auftrag stehen die
Kapitelüberschrift, die Begriffe, die in der Portion vorkommen, und die letzten zwei Sätze davor als Zusammenhang; die
Antwort ist ein JSON-Schema mit genau so vielen Texten wie Blöcken. Gleiche Blöcke einer Portion gehen einmal hinaus.
Passt die Antwort nicht (Anzahl, Form), wird die Portion halbiert, bis einzelne Blöcke übrig sind; liefert die KI auch für
einen einzelnen nichts Brauchbares, steht er ohne Übersetzung da (None) und geht in die Nacharbeit. Kommt ein Block
unverändert englisch zurück (pruefen.unuebersetzt), wird er gleich einzeln mit eigener Anweisung neu angefragt
(anweisungen.UNUEBERSETZT); in der Nacharbeit bekommt ein solcher Block dieselbe Anweisung statt seiner "früheren
Übersetzung", denn die Kopie des Originals als frühere Übersetzung lädt das Modell nur ein, sie noch einmal abzuschreiben.

Das Modell sieht den Text als Zeichen (marken.fuer_modell); jede Übersetzung kommt mit geraden Zeichen (zeichen.gerade) in
der Schreibweise der Vorlagen zurück (marken.aus_modell); geprüft wird sie vom Rufer (pruefen.py)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from pydantic import BaseModel, Field

from backend.app.uebersetzung import anweisungen, marken
from backend.app.uebersetzung.begriffe import fuer_text
from backend.app.uebersetzung.modelle import Anfrage, Anrede, Befund, Begriff, Block, Unbrauchbar
from backend.app.uebersetzung.pruefen import unuebersetzt
from backend.app.uebersetzung.sprache import saetze
from backend.app.uebersetzung.zeichen import gerade


class Auftrag(BaseModel):
    """Was jede Anfrage zu einem Kapitel mitbekommt."""
    kapitel: str                                     # die Überschrift des Kapitels
    begriffe: list[Begriff] = Field(default_factory=list)       # die Liste, die für das Buch gilt
    anrede: Anrede = "du"
    titel: str = "Übersetzen"                        # so heißt die Anfrage in der Leitstelle
    modell: str = ""                                 # leer: das Modell, das gilt


def portionen(bloecke: Sequence[Block], zeichen: int, hoechstens: int) -> list[list[Block]]:
    teile: list[list[Block]] = []
    teil: list[Block] = []
    summe = 0
    for b in bloecke:
        if teil and (summe + len(b.vorlage) > zeichen or len(teil) >= hoechstens):
            teile.append(teil)
            teil, summe = [], 0
        teil.append(b)
        summe += len(b.vorlage)
    return teile + ([teil] if teil else [])


def zusammenhang(vorher: Sequence[Block], saetze_: int = 2) -> str:
    """Die letzten Sätze vor einer Portion (ohne Marken)."""
    gesammelt: list[str] = []
    for b in reversed(vorher):
        gesammelt = saetze(marken.klartext(b.vorlage)) + gesammelt
        if len(gesammelt) >= saetze_:
            break
    return " ".join(gesammelt[-saetze_:])


def begriffsangaben(begriffe: list[Begriff], texte: Sequence[str]) -> dict[str, dict[str, str]]:
    """Die Begriffe, die in den Texten vorkommen, im Format der Buchprojekte; mit der vereinbarten Form (der ersten)."""
    text = "\n".join(marken.klartext(t) for t in texte)
    gilt = fuer_text(begriffe, text)
    return {"begriffe": {b.englisch: "bleibt englisch" if b.bleibt else b.vereinbart for b in gilt if b.art == "begriff"},
            "einheiten": {b.englisch: b.vereinbart for b in gilt if b.art == "einheit" and b.vereinbart}}


def speicherschluessel(vorlage: str, auftrag: Auftrag, sprache: str = "de") -> str:
    """Schlüssel im Zwischenspeicher: Vorlage, die Begriffe, die in ihr vorkommen, Fassung der Anweisungen, Anrede, Sprache.
    Gleiche Blöcke mit denselben Begriffen werden so einmal übersetzt; eine geänderte Begriffsliste gibt neue Schlüssel."""
    daten = {"vorlage": vorlage, **begriffsangaben(auftrag.begriffe, [vorlage]), "anweisung": anweisungen.FASSUNG,
             "anrede": auftrag.anrede, "sprache": sprache}
    return hashlib.sha256(json.dumps(daten, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _nachricht(auftrag: Auftrag, vorlagen: list[str], vorher: Sequence[Block], beanstandet: dict | None = None) -> str:
    daten: dict = {"kapitel": auftrag.kapitel, "zusammenhang": zusammenhang(vorher), **begriffsangaben(auftrag.begriffe, vorlagen),
                   "bloecke": [marken.fuer_modell(v) for v in vorlagen]}
    if beanstandet is not None:
        daten["beanstandet"] = beanstandet
    return json.dumps(daten, ensure_ascii=False)


def texte_aus(roh: object, anzahl: int) -> list[str]:
    """Die Texte einer Antwort; wirft Unbrauchbar, wenn Form oder Anzahl nicht stimmen."""
    texte = roh.get("bloecke") if isinstance(roh, dict) else None
    if not isinstance(texte, list) or len(texte) != anzahl or not all(isinstance(t, str) for t in texte):
        raise Unbrauchbar(f"Die Antwort hat nicht genau {anzahl} Texte")
    return [gerade(t.strip()) for t in texte]


async def uebersetzen(anfrage: Anfrage, bloecke: Sequence[Block], auftrag: Auftrag, vorher: Sequence[Block] = ()) -> dict[str, str | None]:
    """Kennung -> Übersetzung; None, wenn die KI auch für den einzelnen Block nichts Brauchbares geliefert hat.
    `vorher` sind die Blöcke des Kapitels vor dieser Portion (für den Zusammenhang)."""
    eindeutig = list(dict.fromkeys(b.vorlage for b in bloecke))
    try:
        roh = await anfrage(anweisungen.uebersetzen(len(eindeutig), auftrag.anrede), _nachricht(auftrag, eindeutig, vorher),
                            schema_name="uebersetzung", schema=anweisungen.schema_texte(len(eindeutig)), titel=auftrag.titel,
                            modell=auftrag.modell)
        je_vorlage = {v: marken.aus_modell(t, v) for v, t in zip(eindeutig, texte_aus(roh, len(eindeutig)))}
    except Unbrauchbar:
        if len(eindeutig) == 1:
            return {b.kennung: None for b in bloecke}
        mitte = len(eindeutig) // 2
        vorn = [b for b in bloecke if b.vorlage in eindeutig[:mitte]]
        hinten = [b for b in bloecke if b.vorlage in eindeutig[mitte:]]
        aus = await uebersetzen(anfrage, vorn, auftrag, vorher)
        return aus | await uebersetzen(anfrage, hinten, auftrag, [*vorher, *vorn])
    for v, text in list(je_vorlage.items()):
        if unuebersetzt(v, text, auftrag.begriffe):
            davor = [*vorher, *bloecke[:next(i for i, b in enumerate(bloecke) if b.vorlage == v)]]
            je_vorlage[v] = await _noch_einmal(anfrage, v, auftrag, davor) or text
    return {b.kennung: je_vorlage[b.vorlage] for b in bloecke}


async def _noch_einmal(anfrage: Anfrage, vorlage: str, auftrag: Auftrag, vorher: Sequence[Block], maengel: list[str] | None = None,
                       schema_name: str = "uebersetzung") -> str | None:
    """Ein Block, der unverändert englisch zurückkam, einzeln mit der Anweisung dafür; None, wenn nichts Brauchbares kam."""
    try:
        roh = await anfrage(anweisungen.uebersetzen(1, auftrag.anrede, unuebersetzt=True),
                            _nachricht(auftrag, [vorlage], vorher, {"maengel": maengel} if maengel else None),
                            schema_name=schema_name, schema=anweisungen.schema_texte(1), titel=auftrag.titel, modell=auftrag.modell)
        return marken.aus_modell(texte_aus(roh, 1)[0], vorlage)
    except Unbrauchbar:
        return None


def _maengel(befunde: list[Befund]) -> list[str]:
    return [b.text + (f" (Stelle: {b.stelle})" if b.stelle else "") for b in befunde]


async def nacharbeiten(anfrage: Anfrage, block: Block, frueher: str, befunde: list[Befund], auftrag: Auftrag,
                       vorher: Sequence[Block] = ()) -> str | None:
    """Ein Block noch einmal, mit der früheren Übersetzung und ihren Mängeln im Auftrag; None, wenn nichts Brauchbares kam.
    War die frühere Übersetzung das unveränderte Original, geht sie nicht mit, nur ihre Mängel und die Anweisung für einen
    unübersetzten Block."""
    if unuebersetzt(block.vorlage, frueher, auftrag.begriffe):
        return await _noch_einmal(anfrage, block.vorlage, auftrag, vorher, _maengel(befunde), schema_name="nacharbeit")
    beanstandet = {"uebersetzung": marken.fuer_modell(frueher), "maengel": _maengel(befunde)}
    try:
        roh = await anfrage(anweisungen.uebersetzen(1, auftrag.anrede, nacharbeit=True),
                            _nachricht(auftrag, [block.vorlage], vorher, beanstandet), schema_name="nacharbeit",
                            schema=anweisungen.schema_texte(1), titel=auftrag.titel, modell=auftrag.modell)
        return marken.aus_modell(texte_aus(roh, 1)[0], block.vorlage)
    except Unbrauchbar:
        return None
