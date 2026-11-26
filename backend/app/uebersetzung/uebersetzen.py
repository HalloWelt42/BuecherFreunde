"""Übersetzen in Portionen (BF-71, nach Nachschlag artikel.py).

Eine Portion sind Blöcke bis etwa `zeichen` Zeichen oder `hoechstens` Blöcke, immer an Blockgrenzen. Im Auftrag stehen die
Kapitelüberschrift, die Begriffe, die in der Portion vorkommen, und die letzten zwei Sätze davor als Zusammenhang; die
Antwort ist ein JSON-Schema mit genau so vielen Texten wie Blöcken. Gleiche Blöcke einer Portion gehen einmal hinaus.
Passt die Antwort nicht (Anzahl, Form), wird die Portion halbiert, bis einzelne Blöcke übrig sind; liefert die KI auch für
einen einzelnen nichts Brauchbares, steht er ohne Übersetzung da (None) und geht in die Nacharbeit.

Jede Übersetzung kommt mit geraden Zeichen zurück (zeichen.gerade); geprüft wird sie vom Rufer (pruefen.py)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from pydantic import BaseModel, Field

from backend.app.uebersetzung import anweisungen, marken
from backend.app.uebersetzung.begriffe import fuer_text
from backend.app.uebersetzung.modelle import Anfrage, Befund, Begriff, Block, Unbrauchbar
from backend.app.uebersetzung.sprache import saetze
from backend.app.uebersetzung.zeichen import gerade


class Auftrag(BaseModel):
    """Was jede Anfrage zu einem Kapitel mitbekommt."""
    kapitel: str                                     # die Überschrift des Kapitels
    begriffe: list[Begriff] = Field(default_factory=list)       # die Liste, die für das Buch gilt
    anrede: anweisungen.Anrede = "du"
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
    """Die Begriffe, die in den Texten vorkommen, im Format der Buchprojekte."""
    text = "\n".join(marken.klartext(t) for t in texte)
    gilt = fuer_text(begriffe, text)
    return {"begriffe": {b.englisch: "bleibt englisch" if b.bleibt else b.deutsch for b in gilt if b.art == "begriff"},
            "einheiten": {b.englisch: b.deutsch for b in gilt if b.art == "einheit" and b.deutsch}}


def speicherschluessel(vorlage: str, auftrag: Auftrag, sprache: str = "de") -> str:
    """Schlüssel im Zwischenspeicher: Vorlage, die Begriffe, die in ihr vorkommen, Fassung der Anweisungen, Anrede, Sprache.
    Gleiche Blöcke mit denselben Begriffen werden so einmal übersetzt; eine geänderte Begriffsliste gibt neue Schlüssel."""
    daten = {"vorlage": vorlage, **begriffsangaben(auftrag.begriffe, [vorlage]), "anweisung": anweisungen.FASSUNG,
             "anrede": auftrag.anrede, "sprache": sprache}
    return hashlib.sha256(json.dumps(daten, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _nachricht(auftrag: Auftrag, vorlagen: list[str], vorher: Sequence[Block], beanstandet: dict | None = None) -> str:
    daten: dict = {"kapitel": auftrag.kapitel, "zusammenhang": zusammenhang(vorher), **begriffsangaben(auftrag.begriffe, vorlagen),
                   "bloecke": vorlagen}
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
        je_vorlage = dict(zip(eindeutig, texte_aus(roh, len(eindeutig))))
    except Unbrauchbar:
        if len(eindeutig) == 1:
            return {b.kennung: None for b in bloecke}
        mitte = len(eindeutig) // 2
        vorn = [b for b in bloecke if b.vorlage in eindeutig[:mitte]]
        hinten = [b for b in bloecke if b.vorlage in eindeutig[mitte:]]
        aus = await uebersetzen(anfrage, vorn, auftrag, vorher)
        return aus | await uebersetzen(anfrage, hinten, auftrag, [*vorher, *vorn])
    return {b.kennung: je_vorlage[b.vorlage] for b in bloecke}


async def nacharbeiten(anfrage: Anfrage, block: Block, frueher: str, befunde: list[Befund], auftrag: Auftrag,
                       vorher: Sequence[Block] = ()) -> str | None:
    """Ein Block noch einmal, mit der früheren Übersetzung und ihren Mängeln im Auftrag; None, wenn nichts Brauchbares kam."""
    beanstandet = {"uebersetzung": frueher, "maengel": [b.text + (f" (Stelle: {b.stelle})" if b.stelle else "") for b in befunde]}
    try:
        roh = await anfrage(anweisungen.uebersetzen(1, auftrag.anrede, nacharbeit=True),
                            _nachricht(auftrag, [block.vorlage], vorher, beanstandet), schema_name="nacharbeit",
                            schema=anweisungen.schema_texte(1), titel=auftrag.titel, modell=auftrag.modell)
        return texte_aus(roh, 1)[0]
    except Unbrauchbar:
        return None
