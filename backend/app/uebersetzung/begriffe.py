"""Begriffsliste je Buch (BF-71): was englisch bleibt und was eine vereinbarte deutsche Form hat, im Format der Buchprojekte
(`regeln`, `begriffe`, `einheiten`; Regeln stehen fest in den Anweisungen, Einheiten sind Begriffe der Art "einheit").

Woher Begriffe kommen:
1. Regeln: Bezeichner, Code, Abkürzungen, Dateinamen und Versionen bleiben ohnehin (pruefen.py, Prüfung "Bezeichner"). In
   die Liste kommen nach Regeln die Namen: Wörter, die im ganzen Buch gleich geschrieben sind, groß auch mitten im Satz und
   nie klein (Produktnamen wie Python oder Kubernetes). Überschriften zählen nicht, sie schreiben im Englischen oft jedes
   Wort groß.
2. KI-Vorschlag: aus Inhaltsverzeichnis, Stichwortverzeichnis und Proben schlägt die KI Fachbegriffe vor, je mit "bleibt"
   oder einer deutschen Form und einem kurzen Grund.
3. Pflege: von Hand (services/begriffsliste.py); was der Nutzer angelegt oder geändert hat, fasst keine Regel und keine KI
   mehr an.

Gefunden wird ein Begriff im Original an Wortgrenzen, Groß und Klein gleich, auch in der Mehrzahl (thread, Threads); in der
Übersetzung am Wortanfang, damit Beugung und Zusammensetzung gelten (Thread-Pool, Rückgabewerte). Zwischen Wörtern zählen
Leerzeichen und Bindestrich gleich (Event Loop, Event-Loop)."""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from typing import Any

from backend.app.uebersetzung import marken
from backend.app.uebersetzung.modelle import Begriff, Block, Kandidat
from backend.app.uebersetzung.sprache import STOPP_EN, saetze

NAME = re.compile(r"(?<![\w.@/\\-])[A-Z][a-z]{2,}(?![\w-])")
WORT = re.compile(r"[A-Za-z]+")
#: Groß geschrieben, aber kein Name, der englisch bleibt (Tage, Monate, Sprachen, Völker, Anreden)
KEINE_NAMEN = frozenset("""
Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July August September October
November December English German French Spanish Italian Chinese Japanese Russian American British European Europe America
Africa Asia Christmas Easter Mr Mrs Ms Dr Figure Table Chapter Section Appendix Part Note Tip Warning Example Listing
""".split())
NAMEN_AB = 3                                         # so oft mitten im Satz groß, damit ein Wort als Name gilt
REGEL_GRUND = "Name: im ganzen Buch groß geschrieben, auch mitten im Satz"
VORSCHLAG_HOECHSTENS = 60
PROBE_ZEICHEN = 4000
STICHWORT_ZEICHEN = 3000


@lru_cache(maxsize=4096)
def muster_englisch(englisch: str) -> re.Pattern[str]:
    teile = [re.escape(t) for t in re.split(r"[-\s]+", englisch.strip()) if t]
    return re.compile(r"(?<![\w])" + r"[-\s]+".join(teile) + r"(?:s|es)?(?![\w])", re.I)


@lru_cache(maxsize=4096)
def muster_deutsch(form: str) -> re.Pattern[str]:
    teile = [re.escape(t) for t in re.split(r"[-\s]+", form.strip()) if t]
    return re.compile(r"(?<![\w])" + r"[-\s]?".join(teile), re.I)


@lru_cache(maxsize=512)
def muster_einheit(englisch: str) -> re.Pattern[str]:
    """Ein Einheitenname gleich nach einer Zahl: "5 feet", "5-foot"."""
    teile = [re.escape(t) for t in re.split(r"[-\s]+", englisch.strip()) if t]
    return re.compile(r"\d[ \u00a0\u202f-]*" + r"[-\s]+".join(teile) + r"(?![\w])", re.I)


def kommt_vor(englisch: str, text: str) -> bool:
    return bool(englisch.strip()) and bool(muster_englisch(englisch).search(text))


def stellen(englisch: str, texte: list[str]) -> int:
    m = muster_englisch(englisch)
    return sum(len(m.findall(t)) for t in texte)


def im_deutschen(form: str, text: str) -> bool:
    return bool(muster_deutsch(form).search(text))


def gelten(allgemein: list[Begriff], buch: list[Begriff]) -> list[Begriff]:
    """Die Liste, die für ein Buch gilt: die allgemeine, darüber die des Buchs (gleicher englischer Begriff gewinnt)."""
    eigene = {b.englisch.lower() for b in buch}
    return [*buch, *(b for b in allgemein if b.englisch.lower() not in eigene)]


def fuer_text(begriffe: list[Begriff], text: str) -> list[Begriff]:
    """Die Begriffe, die in einem Text (ohne Marken) vorkommen."""
    return [b for b in begriffe if kommt_vor(b.englisch, text)]


# -- 1. Regeln ----------------------------------------------------------------------------------------------------------------

def namen(bloecke: list[Block], vorhanden: set[str]) -> list[Kandidat]:
    """Namen nach der Regel: mitten im Satz mindestens `NAMEN_AB` Mal groß, nie klein, kein kleines Wort und keins der
    großen Wörter, die übersetzt werden; was schon in der Liste steht (`vorhanden`, klein), bleibt draußen."""
    mitten: Counter[str] = Counter()
    alle: Counter[str] = Counter()
    klein: set[str] = set()
    for b in bloecke:
        text = marken.klartext(b.vorlage)
        klein.update(w for w in WORT.findall(text) if w.islower())
        if b.art == "ueberschrift":
            continue
        for satz in saetze(text):
            for m in NAME.finditer(satz):
                alle[m.group(0)] += 1
                if m.start() > 0 and satz[:m.start()].strip(" \"'(["):
                    mitten[m.group(0)] += 1
    return [Kandidat(englisch=w, bleibt=True, grund=REGEL_GRUND, stellen=alle[w], herkunft="regel")
            for w, n in sorted(mitten.items(), key=lambda e: (-e[1], e[0]))
            if n >= NAMEN_AB and w.lower() not in klein and w.lower() not in STOPP_EN and w not in KEINE_NAMEN
            and w.lower() not in vorhanden]


# -- 2. KI-Vorschlag ----------------------------------------------------------------------------------------------------------

SCHEMA_VORSCHLAG: dict[str, Any] = {
    "type": "object", "additionalProperties": False, "required": ["begriffe"],
    "properties": {"begriffe": {"type": "array", "maxItems": VORSCHLAG_HOECHSTENS, "items": {
        "type": "object", "additionalProperties": False, "required": ["englisch", "bleibt", "deutsch", "grund"],
        "properties": {"englisch": {"type": "string", "description": "der Begriff, wie er im Buch steht"},
                       "bleibt": {"type": "boolean", "description": "true, wenn er im Deutschen englisch bleibt"},
                       "deutsch": {"type": "string", "description": "die deutsche Form, wenn er nicht bleibt, sonst leer"},
                       "grund": {"type": "string", "description": "ein kurzer deutscher Satz"}}}}}}


def proben(bloecke: list[Block], zeichen: int = PROBE_ZEICHEN) -> list[str]:
    """Absätze aus dem ganzen Buch, gleichmäßig verteilt, bis etwa `zeichen` Zeichen."""
    absaetze = [marken.klartext(b.vorlage) for b in bloecke if b.art == "absatz" and b.woerter >= 20]
    if not absaetze:
        return []
    schritt = max(1, len(absaetze) * 400 // max(zeichen, 1))
    aus, summe = [], 0
    for text in absaetze[::schritt]:
        if summe + len(text) > zeichen and aus:
            break
        aus.append(text)
        summe += len(text)
    return aus


def stichwoerter(kapitel: list[tuple[str, list[Block]]], zeichen: int = STICHWORT_ZEICHEN) -> str:
    """Der Anfang des Stichwortverzeichnisses (ein Kapitel, das Index heißt), sonst leer."""
    for titel, bloecke in kapitel:
        if titel.strip().lower() in ("index", "subject index", "stichwortverzeichnis"):
            return "; ".join(marken.klartext(b.vorlage) for b in bloecke)[:zeichen]
    return ""


def vorschlaege_aus(roh: object, texte: list[str], vorhanden: set[str]) -> list[Kandidat]:
    """Die Antwort der KI als Kandidaten: nur Begriffe, die im Buch stehen und noch nicht in der Liste sind, mit einer
    deutschen Form, wenn sie nicht bleiben. Wirft ValueError, wenn die Form nicht stimmt."""
    if not isinstance(roh, dict) or not isinstance(roh.get("begriffe"), list):
        raise ValueError("Die Antwort der KI passt nicht zur verlangten Form")
    aus: dict[str, Kandidat] = {}
    for e in roh["begriffe"][:VORSCHLAG_HOECHSTENS]:
        if not isinstance(e, dict) or not isinstance(e.get("englisch"), str) or not isinstance(e.get("bleibt"), bool):
            continue
        englisch = " ".join(e["englisch"].split())
        deutsch = " ".join(str(e.get("deutsch") or "").split())
        if not (0 < len(englisch) <= 80) or englisch.lower() in vorhanden or englisch.lower() in aus:
            continue
        if not e["bleibt"] and not deutsch:
            continue
        n = stellen(englisch, texte)
        if n:
            aus[englisch.lower()] = Kandidat(englisch=englisch, deutsch="" if e["bleibt"] else deutsch, bleibt=e["bleibt"],
                                             grund=" ".join(str(e.get("grund") or "").split())[:200], stellen=n, herkunft="ki")
    return list(aus.values())
