"""Englisch oder Deutsch, Wörter und Sätze (BF-71): für die Prüfung "Sprache", für "Vollständigkeit" und für die Frage, ob
ein Buch englisch ist.

Die Sprache eines Satzes zeigen seine kleinen Wörter (Artikel, Bindewörter, Hilfsverben). Wörter, die es in beiden
Sprachen gibt (die, in, was, will ...), zählen für keine. Sätze enden an . ! ? vor einem großen Buchstaben oder einer
Ziffer; Abkürzungen beider Sprachen (e.g., z. B., Nr.) und Initialen beenden keinen Satz."""

from __future__ import annotations

import re

from backend.app.quellen.sprache import kuerzel

STOPP_EN = frozenset("""
the a an and or of to is are were be been being this that these those with for on at by from it its as which who whom whose
what when where how why not can would should could has have had you your we our they their there then than if but into
about only more most such each other some any all do does did just very he she his her them after before because while
through over under between both same own here
""".split())
STOPP_DE = frozenset("""
der das den dem des ein eine einer eines einem einen und oder ist sind wird werden wurde wurden nicht mit für auf von zu zum
zur im sich auch als wie bei nach aus kann können dass es sie wir ihr er noch nur schon über unter durch wenn dann aber hier
jetzt diese dieser dieses diesen mehr sehr kein keine keinen vor bis ohne gegen um wo haben hat hatte sein seine ihre uns
unser weil damit dabei sowie jede jeder jedes
""".split())
WORT = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)?")
ABKUERZUNGEN = (
    "e.g.", "i.e.", "etc.", "vs.", "cf.", "approx.", "Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "Fig.", "fig.", "No.", "Vol.", "vol.",
    "pp.", "p.", "ch.", "Ch.", "Sec.", "sec.", "Inc.", "Ltd.", "Jr.", "Sr.", "St.", "Eq.", "eq.",
    "z. B.", "z.B.", "d. h.", "d.h.", "u. a.", "u.a.", "u. U.", "z. T.", "bzw.", "ca.", "vgl.", "usw.", "Nr.", "Abb.", "Kap.", "S.",
    "evtl.", "ggf.", "inkl.", "sog.", "bspw.", "Tab.", "Bd.", "Hrsg.", "Jh.", "Mio.", "Mrd.", "min.", "max.", "insb.", "zzgl.",
)
_ABKUERZUNG = re.compile(r"(?<![\w.])(?:" + "|".join(re.escape(a) for a in sorted(ABKUERZUNGEN, key=len, reverse=True)) + ")")
_INITIALE = re.compile(r"(?<![\w.])([A-ZÄÖÜ])\.(?=\s?[A-ZÄÖÜ])")
_SATZENDE = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[\"'(\[]?[A-ZÄÖÜ0-9])")
GESCHUETZT = "\x00"


def woerter(text: str) -> list[str]:
    return WORT.findall(text)


def saetze(text: str) -> list[str]:
    """Die Sätze eines Texts (ohne Marken), Abkürzungen und Initialen geschützt."""
    t = _ABKUERZUNG.sub(lambda m: m.group(0).replace(".", GESCHUETZT), text)
    t = _INITIALE.sub(lambda m: m.group(1) + GESCHUETZT, t)
    return [s.replace(GESCHUETZT, ".").strip() for s in _SATZENDE.split(t) if WORT.search(s)]


def stoppwoerter(text: str) -> tuple[int, int]:
    """Wie viele kleine Wörter englisch und wie viele deutsch sind."""
    klein = [w.lower() for w in woerter(text)]
    return sum(w in STOPP_EN for w in klein), sum(w in STOPP_DE for w in klein)


def englischer_satz(satz: str) -> bool:
    """Ein Satz ist englisch, wenn er mindestens drei englische kleine Wörter hat und mehr englische als deutsche."""
    en, de = stoppwoerter(satz)
    return len(woerter(satz)) >= 4 and en >= 3 and en > de


def ist_englisch(text: str) -> bool:
    """Für einen längeren Text (ab 30 Wörtern): deutlich mehr englische kleine Wörter als deutsche."""
    n = len(woerter(text))
    en, de = stoppwoerter(text)
    return n >= 30 and en >= 2 * de and en / n >= 0.05


def buch_ist_englisch(sprache: str | None, probe: str) -> bool:
    """Nach der Angabe am Buch (en, en-US, eng, English ...); fehlt sie, nach den Wörtern einer Probe aus dem Text."""
    k = kuerzel(sprache)
    if k:
        return k == "en"
    return ist_englisch(probe)
