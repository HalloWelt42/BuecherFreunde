"""Die Anrede des Lesers (BF-71): ein Buch bleibt durchgehend bei einer, "du" oder "Sie" (je Fassung beim Start gewählt,
vorbelegt mit UEBERSETZEN_ANREDE). Die feste Prüfung "Anrede" meldet die jeweils andere Form.

- Bei du: Sie, Ihnen, Ihr, Ihre ... groß im Satzinneren; klein sind es die dritte Person (sie, ihnen, ihr Buch). Am
  Satzanfang ist "Sie" mehrdeutig (Sie findet, Sie sind schnell); dort zählt es nur, wenn das Original den Leser anspricht
  (you, your), der Block keine Form von du trägt und ein Verb in der Mehrzahl folgt (Sie können, Sie lernen). "Ihr" und
  "Ihnen" am Satzanfang zählen nie.
- Bei Sie: du, dich, dir, dein ... in jeder Schreibung außer ganz in Großbuchstaben.

Was das Original selbst so schreibt (ein deutsches Zitat), zählt nicht. Satzanfang ist der Anfang des Blocks und was nach
. ! ? : ; steht, auch hinter öffnenden Anführungszeichen oder Klammern."""

from __future__ import annotations

import re

from backend.app.uebersetzung.modelle import Anrede

SIE = re.compile(r"(?<![\w])(Sie|Ihnen|Ihr|Ihre|Ihren|Ihrem|Ihrer|Ihres)(?![\w])")
DU = re.compile(r"(?<![\w])([Dd]u|[Dd]ich|[Dd]ir|[Dd]ein|[Dd]eine|[Dd]einen|[Dd]einem|[Dd]einer|[Dd]eines)(?![\w])")
LESER_EN = re.compile(r"(?<![\w])(?:you|your|yours|yourself|yourselves)(?![\w])", re.I)
VOR_DEM_SATZ = re.compile(r"[\"'(\[\u201e\u201c\u00bb]+$")    # öffnende Zeichen vor einem Satz
MEHRZAHL = re.compile(r"\s+[a-zäöüß]+en(?![\w])")
VORWORT = re.compile(r"(\S+\s+)?$")


def _am_satzanfang(text: str, stelle: int) -> bool:
    vor = VOR_DEM_SATZ.sub("", text[:stelle].rstrip()).rstrip()
    return not vor or vor[-1] in ".!?:;"


def _stelle(text: str, m: re.Match) -> str:
    """Das Wort davor und die Form, als Stelle im Text."""
    vor = VORWORT.search(text[:m.start()])
    return ((vor.group(1) or "") if vor else "") + m.group(1)


def befunde(original: str, deutsch: str, anrede: Anrede) -> list[tuple[str, str]]:
    """Je falscher Form einmal (Satz, Stelle); `original` und `deutsch` als Klartext."""
    aus: dict[str, tuple[str, str]] = {}
    if anrede == "du":
        leser, du_da = bool(LESER_EN.search(original)), bool(DU.search(deutsch))
        for m in SIE.finditer(deutsch):
            form = m.group(1)
            if form in aus or re.search(rf"(?<![\w]){form}(?![\w])", original):
                continue
            if _am_satzanfang(deutsch, m.start()):
                if form != "Sie" or not leser or du_da or not MEHRZAHL.match(deutsch, m.end()):
                    continue
            aus[form] = (f'Der Leser wird mit "du" angesprochen, hier steht "{form}"', _stelle(deutsch, m))
    else:
        for m in DU.finditer(deutsch):
            form = m.group(1)
            if form.lower() in aus or re.search(rf"(?<![\w]){form}(?![\w])", original, re.I):
                continue
            aus[form.lower()] = (f'Der Leser wird mit "Sie" angesprochen, hier steht "{form}"', _stelle(deutsch, m))
    return list(aus.values())
