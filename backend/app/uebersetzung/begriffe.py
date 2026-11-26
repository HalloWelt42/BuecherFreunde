"""Begriffsliste je Buch (BF-71): was englisch bleibt und was eine vereinbarte deutsche Form hat, im Format der Buchprojekte
(`regeln`, `begriffe`, `einheiten`; Regeln stehen fest in den Anweisungen, Einheiten sind Begriffe der Art "einheit").

Woher Begriffe kommen:
1. Regeln: Bezeichner, Code, Abkürzungen, Dateinamen und Versionen bleiben ohnehin (pruefen.py, Prüfung "Bezeichner"). In
   die Liste kommen nach Regeln die Namen: Wörter, die im ganzen Buch gleich geschrieben sind, im Fließtext groß auch mitten
   im Satz und nie klein (Produktnamen wie Python oder Kubernetes). Überschriften und Titelzeilen (Einträge im Verzeichnis,
   Tabellenköpfe, Zeilen aus lauter großen Wörtern ohne Punkt am Ende) zählen nicht, sie schreiben im Englischen oft jedes
   Wort groß; gewöhnliche Wörter (Alltagswörter aus vorgaben.json) sind nie Namen.
2. KI-Vorschlag: aus Inhaltsverzeichnis, Stichwortverzeichnis und Proben schlägt die KI Fachbegriffe vor, je mit "bleibt"
   oder einer oder mehreren deutschen Formen und einem kurzen Grund. Neben der deutschen Form gilt das englische Wort als
   erlaubt, außer die KI verbietet es (`nur_deutsch`). Verworfen wird (`verstoss`): "bleibt englisch" aus lauter
   gewöhnlichen Wörtern (solche Wörter werden übersetzt), eine deutsche Form für ein Fachwort, das im deutschen Fachtext
   englisch bleibt (Paging, Cache, Thread: `englisch_im_fach` in vorgaben.json), und eine Überschrift statt eines Begriffs
   (steht nur in Überschriften und Titelzeilen).
3. Pflege: von Hand (services/begriffsliste.py); was der Nutzer angelegt oder geändert hat, fasst keine Regel und keine KI
   mehr an. Einträge von Regel und KI, die die Regeln von heute nicht bestehen, sind fragwürdig (`fragwuerdig`): sie bleiben
   in der Liste, gelten aber nicht, bis der Nutzer sie ändert oder entfernt.

Gefunden wird ein Begriff im Original an Wortgrenzen, Groß und Klein gleich, auch in der Mehrzahl (thread, Threads), auch
mit Ziffern und Zeichen am Rand (5-Level Paging, IA-32e mode, x86-64, C++, .NET); zwischen Wörtern zählen Leerzeichen,
Bindestriche und Striche gleich. Eine Stelle, die ganz in der Stelle eines längeren Begriffs der Liste liegt (paging in
5-level paging), zählt nur für den längeren (`fuer_text`). In der Übersetzung zählt jede Form mit deutscher Endung: je Wort
der Stamm (ohne -e, -en, -er, -es, -em, -n, -s) mit einer Endung (ansprechende Spiele: ansprechender Spiele, kritischen
Rezensionen, Verzeichnisses), dazu als Teil eines zusammengesetzten Worts: hinten ab einem Stamm von ZUSAMMEN_AB Buchstaben
(Spieleplattformen, Zuweisungsoperatoren), vorn ab VORN_AB (Thread-Pool, Plattformunabhängigkeit); ist der Stamm kürzer als
das Wort, zählt das ganze Wort in diesen Längen (Server: Serverleistung, Webserver). Kürzere Stämme brauchen ihre
Wortgrenzen, damit "Spiel" nicht in "Beispiel" steckt. Abkürzungen (KI) zählen nur in dieser Schreibung, auch mit
Bindestrich (KI-Routinen). Zwischen Wörtern zählen Leerzeichen und Bindestrich gleich (Event Loop, Event-Loop). Ein Begriff
mit mehreren erlaubten Formen ("KI | künstliche Intelligenz") ist da, wenn eine davon dasteht."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from backend.app.uebersetzung import marken
from backend.app.uebersetzung.modelle import FORMEN_TRENNER, Begriff, Block, Kandidat, formen_von
from backend.app.uebersetzung.sprache import STOPP_EN, saetze
from backend.app.uebersetzung.vorgaben import grundform, in_liste

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
#: Endungen deutscher Wörter, die eine Form im Text tragen darf, und die, die vom Ende einer Form als Endung abgehen
ENDUNGEN = ("ern", "ens", "ses", "sen", "en", "er", "es", "em", "se", "e", "n", "s")
ABGEHEND = ("en", "er", "es", "em", "e", "n", "s")
STAMM_MINDESTENS = 4
ZUSAMMEN_AB = 6                                      # so lang muss ein Stamm sein, um hinten in einem Wort zu stehen
VORN_AB = 5                                          # ... und um vorn in einem Wort zu stehen, mit Weiterem dahinter
ABKUERZUNG = re.compile(r"[A-ZÄÖÜ][A-ZÄÖÜ0-9]{1,5}")
#: zwischen den Wörtern eines Begriffs im Original: Leerraum, Bindestrich und Striche (5-level, 5 level, 5\u2013level)
TRENNER_EN = r"[-\u2010\u2011\u2012\u2013\s]+"
GRUND_KEIN_NAME = "Kein Name nach der Regel: im Fließtext nicht oft genug mitten im Satz groß"
GRUND_ALLTAG = "Gewöhnliches englisches Wort: solche Wörter werden übersetzt"
GRUND_UEBERSCHRIFT = "Überschrift statt Fachbegriff: steht nur in Überschriften und Titelzeilen"


@lru_cache(maxsize=4096)
def muster_englisch(englisch: str) -> re.Pattern[str]:
    """Ein Begriff im Original an Wortgrenzen; Ziffern und Zeichen am Rand gehören zum Begriff (5-Level Paging, C++, .NET)."""
    teile = [re.escape(t) for t in re.split(TRENNER_EN, englisch.strip()) if t]
    return re.compile(r"(?<![\w])" + TRENNER_EN.join(teile) + r"(?:s|es)?(?![\w])", re.I)


def stamm(wort: str) -> str:
    """Ein Wort ohne deutsche Endung; ein s nach i, s, u oder x bleibt (Verzeichnis, Prozess, Status, Index), und die
    Mehrzahl auf -nisse geht auf -nis zurück (Hindernisse: Hindernis)."""
    klein = wort.lower()
    for e in ABGEHEND:
        if klein.endswith(e) and len(wort) - len(e) >= STAMM_MINDESTENS:
            if e == "s" and klein[-2:-1] in ("i", "s", "u", "x"):
                continue
            rest = wort[:-len(e)]
            return rest[:-1] if rest.lower().endswith("niss") else rest
    return wort


def _zusammengesetzt(teile: list[str]) -> str:
    """Wörter (Stämme oder ganze Wörter) mit Endungen, an Wortgrenzen; lange erste stehen auch hinten in einem Wort, lange
    letzte auch vorn."""
    endung = "(?:" + "|".join(ENDUNGEN) + ")?"
    kern = r"[-\s]?".join(re.escape(s) + endung for s in teile)
    vorn = r"(?<![\w])(?:[^\W\d_]+-?)?" if len(teile[0]) >= ZUSAMMEN_AB else r"(?<![\w])"
    hinten = "" if len(teile[-1]) >= VORN_AB else r"(?![\w])"
    return vorn + kern + hinten


@lru_cache(maxsize=4096)
def muster_deutsch(form: str) -> re.Pattern[str]:
    """Eine Form der Begriffsliste im deutschen Text, mit Endungen und als Teil zusammengesetzter Wörter. Ist ein Stamm am
    Rand kürzer, als ein Teil eines Worts sein muss, das ganze Wort aber lang genug (Server: Stamm Serv), zählt das ganze
    Wort im zusammengesetzten (Serverleistung, Webserver), der Stamm nur mit Endung für sich (Servern)."""
    woerter = [t for t in re.split(r"[-\s]+", form.strip()) if t]
    if len(woerter) == 1 and ABKUERZUNG.fullmatch(woerter[0]):
        return re.compile(r"(?<![\w])" + re.escape(woerter[0]) + r"s?(?![^\W\d_])")
    staemme = [stamm(w) for w in woerter]
    muster = [_zusammengesetzt(staemme)]
    if len(woerter[0]) >= ZUSAMMEN_AB > len(staemme[0]) or len(woerter[-1]) >= VORN_AB > len(staemme[-1]):
        muster.append(_zusammengesetzt(woerter))
    return re.compile("|".join(f"(?:{m})" for m in muster), re.I)


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
    """Ob eine Form (oder eine von mehreren, mit | getrennt) im deutschen Text steht."""
    return any(muster_deutsch(f).search(text) for f in formen_von(form))


def gelten(allgemein: list[Begriff], buch: list[Begriff]) -> list[Begriff]:
    """Die Liste, die für ein Buch gilt: die allgemeine, darüber die des Buchs (gleicher englischer Begriff gewinnt)."""
    eigene = {b.englisch.lower() for b in buch}
    return [*buch, *(b for b in allgemein if b.englisch.lower() not in eigene)]


def fuer_text(begriffe: list[Begriff], text: str) -> list[Begriff]:
    """Die Begriffe, die in einem Text (ohne Marken) für sich vorkommen: eine Stelle, die ganz in der Stelle eines längeren
    Begriffs der Liste liegt (paging in 5-level paging, Fundamentals in Game Development Fundamentals), zählt nur für den
    längeren. So bekommt das Modell keine zwei Vorgaben für dieselben Wörter, und die Prüfung fordert nur, was gilt."""
    funde = [(b, [m.span() for m in muster_englisch(b.englisch).finditer(text)]) for b in begriffe if b.englisch.strip()]
    funde = [(b, s) for b, s in funde if s]
    alle = [stelle for _, s in funde for stelle in s]

    def ueberdeckt(a: int, e: int) -> bool:
        return any(a2 <= a and e <= e2 and e2 - a2 > e - a for a2, e2 in alle)
    return [b for b, s in funde if any(not ueberdeckt(a, e) for a, e in s)]


# -- Fließtext und Titelzeilen ------------------------------------------------------------------------------------------------

def _erster_buchstabe(wort: str) -> str:
    return next((z for z in wort if z.isalpha()), "")


def titelzeile(satz: str) -> bool:
    """Eine Zeile aus lauter groß geschriebenen Wörtern ohne Punkt oder Ausrufezeichen am Ende: eine Überschrift, ein Eintrag
    im Verzeichnis, ein Tabellenkopf, ein Titel (2.2 Enumeration and Enabling, Bit Position(s), Motion and Position:). Kleine
    Wörter (of, and, the) und Wörter ohne Buchstaben zählen nicht."""
    if satz.rstrip(" \"')]").endswith((".", "!")):
        return False
    anfaenge = [_erster_buchstabe(w) for w in satz.split() if w.strip("\"'()[].,:;!?").lower() not in STOPP_EN]
    anfaenge = [a for a in anfaenge if a]
    return bool(anfaenge) and all(a.isupper() for a in anfaenge)


@dataclass(frozen=True)
class Buchtext:
    """Der Text eines Buchs für die Regeln der Begriffsliste, als Sätze: Fließtext und Titel (Überschriften und
    Titelzeilen) getrennt, dazu jedes Wort, das irgendwo klein steht."""
    fliesstext: tuple[str, ...]
    titel: tuple[str, ...]
    klein: frozenset[str]

    @classmethod
    def aus(cls, bloecke: Sequence[Block]) -> Buchtext:
        fliesstext: list[str] = []
        titel: list[str] = []
        klein: set[str] = set()
        for b in bloecke:
            text = marken.klartext(b.vorlage)
            klein.update(w for w in WORT.findall(text) if w.islower())
            for satz in saetze(text):
                (titel if b.art == "ueberschrift" or titelzeile(satz) else fliesstext).append(satz)
        return cls(tuple(fliesstext), tuple(titel), frozenset(klein))

    @property
    def alle(self) -> list[str]:
        return [*self.fliesstext, *self.titel]


# -- 1. Regeln ----------------------------------------------------------------------------------------------------------------

def namen(bloecke: Sequence[Block], vorhanden: set[str], alltag: frozenset[str] = frozenset()) -> list[Kandidat]:
    """Namen nach der Regel: im Fließtext mitten im Satz (nicht gleich nach einem Doppelpunkt) mindestens `NAMEN_AB` Mal
    groß, nie klein, kein kleines Wort, kein
    gewöhnliches (`alltag`) und keins der großen Wörter, die übersetzt werden; was schon in der Liste steht (`vorhanden`,
    klein), bleibt draußen."""
    return namen_aus(Buchtext.aus(bloecke), vorhanden, alltag)


def namen_aus(text: Buchtext, vorhanden: set[str], alltag: frozenset[str] = frozenset()) -> list[Kandidat]:
    mitten: Counter[str] = Counter()
    alle: Counter[str] = Counter()
    for satz in text.fliesstext:
        for m in NAME.finditer(satz):
            alle[m.group(0)] += 1
            vor = satz[:m.start()].rstrip(" \"'([")
            if vor and not vor.endswith((":", ";")):           # nach einem Doppelpunkt beginnt ein Satz (Display Update: Finally)
                mitten[m.group(0)] += 1
    return [Kandidat(englisch=w, bleibt=True, grund=REGEL_GRUND, stellen=alle[w], herkunft="regel")
            for w, n in sorted(mitten.items(), key=lambda e: (-e[1], e[0]))
            if n >= NAMEN_AB and w.lower() not in text.klein and w.lower() not in STOPP_EN and w not in KEINE_NAMEN
            and not in_liste(w, alltag) and w.lower() not in vorhanden]


# -- 2. KI-Vorschlag ----------------------------------------------------------------------------------------------------------

SCHEMA_VORSCHLAG: dict[str, Any] = {
    "type": "object", "additionalProperties": False, "required": ["begriffe"],
    "properties": {"begriffe": {"type": "array", "maxItems": VORSCHLAG_HOECHSTENS, "items": {
        "type": "object", "additionalProperties": False, "required": ["englisch", "bleibt", "deutsch", "nur_deutsch", "grund"],
        "properties": {"englisch": {"type": "string", "description": "der Begriff, wie er im Buch steht"},
                       "bleibt": {"type": "boolean", "description": "true, wenn er im Deutschen englisch bleibt"},
                       "deutsch": {"type": "string", "description": "die deutsche Form, wenn er nicht bleibt, sonst leer; mehrere "
                                                                    "übliche Formen mit | getrennt, die übliche zuerst"},
                       "nur_deutsch": {"type": "boolean", "description": "true nur, wenn das englische Wort im deutschen "
                                                                        "Fachtext falsch wäre"},
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


def alltaeglich(englisch: str, alltag: frozenset[str]) -> bool:
    """Ob ein Begriff nur aus gewöhnlichen Wörtern besteht (Alltagswörter, kleine Wörter; Mehrzahl auf -s mitgedacht)."""
    woerter = [w.lower() for w in WORT.findall(englisch)]
    return bool(woerter) and all(w in STOPP_EN or in_liste(w, alltag) for w in woerter)


def verstoss(k: Kandidat, text: Buchtext, alltag: frozenset[str], im_fach: frozenset[str]) -> str:
    """Warum ein Vorschlag der KI die Regeln der Begriffsliste nicht besteht, leer, wenn er sie besteht: "bleibt englisch"
    aus lauter gewöhnlichen Wörtern; eine deutsche Form für ein Fachwort, das im deutschen Fachtext englisch bleibt (die
    vereinbarte, erste Form trägt es nicht); eine Überschrift statt eines Begriffs."""
    if k.bleibt:
        return GRUND_ALLTAG if alltaeglich(k.englisch, alltag) else ""
    erste = next(iter(formen_von(k.deutsch)), "").lower()
    for w in WORT.findall(k.englisch):
        g = grundform(w, im_fach)
        if g is not None and g not in erste:
            return f"{g.capitalize()} bleibt im deutschen Fachtext gebräuchlich englisch"
    if not stellen(k.englisch, list(text.fliesstext)) and stellen(k.englisch, list(text.titel)):
        return GRUND_UEBERSCHRIFT
    return ""


def _formen(englisch: str, deutsch: str, nur_deutsch: bool) -> str:
    """Die erlaubten deutschen Formen eines Vorschlags; das englische Wort gilt mit, außer die KI verbietet es."""
    formen = formen_von(deutsch)
    if not nur_deutsch and not any(f.lower() == englisch.lower() for f in formen):
        formen.append(englisch)
    return f" {FORMEN_TRENNER} ".join(formen)


def vorschlaege_aus(roh: object, text: Buchtext, vorhanden: set[str], alltag: frozenset[str] = frozenset(),
                    im_fach: frozenset[str] = frozenset()) -> list[Kandidat]:
    """Die Antwort der KI als Kandidaten: nur Begriffe, die im Buch stehen und noch nicht in der Liste sind, mit einer
    deutschen Form, wenn sie nicht bleiben (das englische Wort als weitere erlaubte Form, außer bei `nur_deutsch`); was die
    Regeln nicht besteht (`verstoss`), wird verworfen. Wirft ValueError, wenn die Form nicht stimmt."""
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
        if not e["bleibt"] and not formen_von(deutsch):
            continue
        k = Kandidat(englisch=englisch, deutsch="" if e["bleibt"] else _formen(englisch, deutsch, e.get("nur_deutsch") is True),
                     bleibt=e["bleibt"], grund=" ".join(str(e.get("grund") or "").split())[:200], herkunft="ki")
        n = stellen(englisch, text.alle)
        if n and not verstoss(k, text, alltag, im_fach):
            aus[englisch.lower()] = k.model_copy(update={"stellen": n})
    return list(aus.values())


# -- Fragwürdige Einträge -----------------------------------------------------------------------------------------------------

def fragwuerdig(eintraege: Sequence[Kandidat], text: Buchtext, alltag: frozenset[str], im_fach: frozenset[str]) -> dict[str, str]:
    """Die Einträge von Regel und KI (englisch, klein) mit dem Grund, warum sie die Regeln von heute nicht bestehen: ein Name
    der Regel, den die Regel für Namen nicht mehr findet; ein Vorschlag der KI mit einem Verstoß (`verstoss`). Einträge von
    Hand und Vorgaben fasst das nie an."""
    jetzt = {k.englisch.lower() for k in namen_aus(text, set(), alltag)}
    aus: dict[str, str] = {}
    for k in eintraege:
        if k.herkunft == "regel":
            grund = "" if k.englisch.lower() in jetzt else GRUND_ALLTAG if alltaeglich(k.englisch, alltag) else GRUND_KEIN_NAME
        else:
            grund = verstoss(k, text, alltag, im_fach)
        if grund:
            aus[k.englisch.lower()] = grund
    return aus
