"""Lücken rechnen (BF-75), ohne Datenbank und ohne Quelle: welche Plätze die Bände einer Sprache belegen, welche fehlen, die
kurzen Sätze dazu und was aus den Funden eines Katalogs gilt.

- Mit einer Zahl der Bände fehlt jeder Platz von 1 bis zu ihr, den kein Band belegt.
- Ohne Zahl fehlen nur Plätze zwischen dem ersten und dem letzten belegten.
- Ausgeblendete Plätze fehlen nie; ohne belegten Platz gibt es keine Lücke (eine Sammlung ohne Nummern hat keine Folge)."""

from __future__ import annotations

from collections.abc import Iterable

from backend.app.luecken.bandnummer import Bandnummer, lesen
from backend.app.luecken.modelle import Quellband, Quellergebnis
from backend.app.luecken.sprachen import sprachname
from backend.app.quellen.reihen import Reihenfund

BEREICH_AB = 3                                 # ab so vielen Nummern in Folge steht "1 bis 5", darunter "1 und 2"


def belegt(baende: Iterable[Bandnummer]) -> set[int]:
    return {n for b in baende for n in b.plaetze}


def fehlende(plaetze: set[int], gesamt: int | None, ausgeblendet: set[int] = frozenset()) -> list[int]:
    if not plaetze:
        return []
    anfang, ende = (1, gesamt) if gesamt else (min(plaetze), max(plaetze))
    return [n for n in range(anfang, ende + 1) if n not in plaetze and n not in ausgeblendet]


def bereiche(nummern: Iterable[int]) -> list[str]:
    """[1, 2, 3, 4, 5, 8] -> ["1 bis 5", "8"]; zwei in Folge bleiben einzeln."""
    folge = sorted(set(nummern))
    aus: list[str] = []
    i = 0
    while i < len(folge):
        j = i
        while j + 1 < len(folge) and folge[j + 1] == folge[j] + 1:
            j += 1
        aus += [f"{folge[i]} bis {folge[j]}"] if j - i + 1 >= BEREICH_AB else [str(n) for n in folge[i:j + 1]]
        i = j + 1
    return aus


def aufzaehlen(teile: list[str]) -> str:
    return teile[0] if len(teile) == 1 else f"{', '.join(teile[:-1])} und {teile[-1]}" if teile else ""


def fehlen_satz(fehlen: list[int]) -> str:
    """"es fehlt 6", "es fehlen 6 und 7", "es fehlen 4, 9, 11 und 12"; leer ohne Lücke."""
    if not fehlen:
        return ""
    return f"{'es fehlt' if len(fehlen) == 1 else 'es fehlen'} {aufzaehlen(bereiche(fehlen))}"


def lueckenzeile(plaetze: set[int], fehlen: list[int]) -> str:
    """"vorhanden 1 bis 5 und 8, es fehlen 6 und 7"; leer ohne Lücke."""
    return f"vorhanden {aufzaehlen(bereiche(plaetze))}, {fehlen_satz(fehlen)}" if fehlen else ""


def vorschlagszeile(je_sprache: dict[str, list[Bandnummer]]) -> str:
    """Die Zeile eines Sammlungsvorschlags, nur aus den eigenen Nummern: je Sprache mit Lücken ein Teil, bei mehreren Sprachen
    mit ihrem Namen davor ("Deutsch: vorhanden 1 bis 3 und 5, es fehlt 4; Englisch: ...")."""
    teile = []
    for sprache, baende in je_sprache.items():
        plaetze = belegt(baende)
        if zeile := lueckenzeile(plaetze, fehlende(plaetze, None)):
            teile.append((sprache, zeile))
    if len(je_sprache) == 1:
        return teile[0][1] if teile else ""
    return "; ".join(f"{sprachname(s)}: {z}" for s, z in teile)


def _wert(f: Reihenfund) -> tuple:
    """Welcher Satz für einen Band gilt, wenn der Katalog mehrere Ausgaben kennt: mit ISBN und Titel vor ohne, die neueste zuerst."""
    return (bool(f.isbn), bool(f.titel), f.jahr or 0)


def aus_den_quellen(funde: list[Reihenfund]) -> Quellergebnis:
    """Die Zahl der Bände ist der höchste Platz, den ein Fund belegt; die Angaben je Band kommen vom besten Satz für genau
    diesen Band (Doppelbände und Zwischenbände geben keine Angaben für einen Platz)."""
    je_platz: dict[int, Reihenfund] = {}
    hoechster = 0
    for f in funde:
        plaetze = lesen(f.band).plaetze
        if not plaetze:
            continue
        hoechster = max(hoechster, plaetze[-1])
        if len(plaetze) == 1 and (plaetze[0] not in je_platz or _wert(f) > _wert(je_platz[plaetze[0]])):
            je_platz[plaetze[0]] = f
    return Quellergebnis(gesamt=hoechster or None,
                         baende=[Quellband(nummer=n, titel=f.titel, autor=next(iter(f.autoren), ""), isbn=f.isbn, jahr=f.jahr, quelle=f.quelle)
                                 for n, f in sorted(je_platz.items())])
