"""Die neun festen Prüfungen je Block (BF-71). Alle müssen bestehen; jede liefert Befunde mit einem deutschen Satz und dem
Stück im deutschen Text, an dem es auffiel.

| Prüfung | bestanden, wenn |
|---|---|
| Marken | jede Marke genau einmal, gleiche Schachtelung, keine fremde Auszeichnung |
| Zahlen | dieselben Zahlen nach Angleichen der Tausender- und Dezimalzeichen (zahlen.py) |
| Einheiten | dieselben Einheiten, keine von selbst zugefügte Umrechnung; englische Einheitennamen in der vereinbarten Form |
| Bezeichner | Adressen, Dateinamen, Pfade, Aufrufe, Bezeichner, Optionen, Versionen und Abkürzungen unverändert |
| Begriffe | jeder Begriff mit "bleibt" steht da, jeder mit deutscher Form in dieser Form |
| Sprache | kein englischer Satz übrig (Begriffe und Bezeichner ausgenommen), nichts unübersetzt stehen gelassen |
| Länge | Verhältnis Deutsch zu Englisch in den Grenzen, ab einer Mindestlänge des Originals |
| Vollständigkeit | gleich viele Sätze, Abweichung höchstens eins |
| Zeichen | echte Umlaute, gerade Anführungszeichen, keine Sonderstriche (zeichen.py) |

Inline-Code geht als Platzhalter nie ans Modell und kommt Zeichen für Zeichen zurück; die Prüfung "Bezeichner" gilt dem, was
im Fließtext steht."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable

from backend.app.uebersetzung import marken, zahlen, zeichen
from backend.app.uebersetzung.begriffe import fuer_text, im_deutschen, muster_deutsch, muster_einheit, muster_englisch
from backend.app.uebersetzung.modelle import Befund, Befundart, Begriff, Laengengrenzen
from backend.app.uebersetzung.sprache import STOPP_EN, englischer_satz, saetze, woerter

DATEIENDUNGEN = ("py|pyc|js|mjs|ts|tsx|jsx|json|yaml|yml|toml|ini|cfg|conf|txt|md|rst|html|htm|xhtml|css|scss|xml|csv|tsv|sh|"
                 "bash|zsh|ps1|bat|c|h|cc|cpp|hpp|cs|java|kt|go|rs|rb|php|pl|swift|sql|db|log|lock|env|zip|tar|gz|tgz|bz2|"
                 "xz|7z|png|jpg|jpeg|gif|svg|webp|pdf|epub|exe|dll|so|dylib|jar|war|wasm|ipynb|dockerfile|mk|gradle")
BEZEICHNER = (
    re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s<>\"']*[^\s<>\"'.,;:!?)\]]"),                    # Adresse
    re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),                                         # Mail
    re.compile(r"(?<![\w/])(?:~|\.{1,2})?(?:/[\w.-]+){2,}/?"),                                # Pfad
    re.compile(rf"\b[\w-]+(?:\.[\w-]+)*\.(?:{DATEIENDUNGEN})\b", re.I),                       # Dateiname
    re.compile(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\(\)"),                                    # Aufruf
    re.compile(r"\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b"),                               # snake_case
    re.compile(r"\b[a-z]+[0-9]*(?:[A-Z][a-z0-9]*)+\b"),                                      # camelCase
    re.compile(r"\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]*)+\b"),                                    # PascalCase
    re.compile(r"\b[a-z_]\w+(?:\.[a-z_]\w+)+\b"),                                            # gepunktet: os.path, example.org
    re.compile(r"(?<![\w-])--?[A-Za-z][\w-]*"),                                              # Option
    re.compile(r"\bv\d+(?:\.\d+)+\b|\b\d+\.\d+\.\d+(?:[-+.]\w+)*\b"),                         # Version
)
ABKUERZUNG = re.compile(r"\b[A-Z][A-Z0-9]{1,9}s?\b")
EINHEITEN_MEHR = ("km", "cm", "mm", "\u00b5m", "\u03bcm", "nm", "kg", "mg", "ms", "\u00b5s", "\u03bcs", "ns", "min", "Hz", "kHz", "MHz", "GHz", "KB", "kB",
                  "MB", "GB", "TB", "PB", "KiB", "MiB", "GiB", "TiB", "kbit", "Mbit", "Gbit", "bps", "kbps", "Mbps", "Gbps", "mV", "kV",
                  "mA", "mAh", "kW", "MW", "Wh", "kWh", "°C", "°F", "px", "pt", "dpi", "ppi", "ft", "mi", "lb", "lbs", "oz", "mph", "psi",
                  "ml", "dB", "fps", "rpm")
EINHEIT = re.compile(r"(?<=\d)(?:[ \u00a0\u202f]?(?P<mehr>" + "|".join(sorted(map(re.escape, EINHEITEN_MEHR), key=len, reverse=True))
                     + r")|[ \u00a0\u202f](?P<eins>[smghlVWABK]))(?![\w])|(?<=\d)[ \u00a0\u202f]?(?P<prozent>%)")
PROZENT_WORT = re.compile(r"(?<=\d)[ \u00a0\u202f]Prozent\b")
UNUEBERSETZT_AB = 3                                  # so viele Wörter ohne Begriffe und Bezeichner, damit Gleichheit auffällt


def _befund(art: Befundart, text: str, stelle: str = "") -> Befund:
    return Befund(art=art, quelle="pruefung", text=text, stelle=stelle)


def pruefe_marken(original: str, deutsch: str, **_: object) -> list[Befund]:
    try:
        marken.lesen(marken.plan(original), deutsch)
    except marken.MarkenFehler as f:
        return [_befund("marken", f.grund, f.stelle)]
    return []


def pruefe_zahlen(original: str, deutsch: str, **_: object) -> list[Befund]:
    v = zahlen.vergleichen(marken.klartext(original), marken.klartext(deutsch))
    aus = []
    if v.fehlt or v.dazu:
        teile = ([f"im Original {', '.join(v.fehlt)}"] if v.fehlt else []) + ([f"in der Übersetzung {', '.join(v.dazu)}"] if v.dazu else [])
        aus.append(_befund("zahlen", "Die Zahlen weichen ab: " + "; ".join(teile), v.dazu[0] if v.dazu else ""))
    for roh in v.englisch_geschrieben:
        aus.append(_befund("zahlen", f"Die Zahl {roh} steht in englischer Schreibweise und heißt im Deutschen etwas anderes", roh))
    return aus


def _einheiten(text: str, prozent_als_wort: bool) -> Counter[str]:
    n = Counter(m.group("mehr") or m.group("eins") or m.group("prozent") for m in EINHEIT.finditer(text))
    if prozent_als_wort:
        n["%"] += len(PROZENT_WORT.findall(text))
    return n


def pruefe_einheiten(original: str, deutsch: str, begriffe: list[Begriff], **_: object) -> list[Befund]:
    en, de = marken.klartext(original), marken.klartext(deutsch)
    vorher, nachher = _einheiten(en, False), _einheiten(de, True)
    aus = [_befund("einheiten", f"Die Einheit {e} fehlt", "") for e in sorted(vorher - nachher)]
    aus += [_befund("einheiten", f"Die Einheit {e} ist hinzugekommen (umgerechnet?)", e) for e in sorted(nachher - vorher)]
    for b in begriffe:
        if b.art != "einheit" or not b.deutsch:
            continue
        n = len(muster_einheit(b.englisch).findall(en))
        if n and len(muster_deutsch(b.deutsch).findall(de)) < n:
            aus.append(_befund("einheiten", f"Die Einheit {b.englisch} steht nicht als {b.deutsch} da", ""))
    return aus


def bezeichner(text: str) -> list[str]:
    """Was im Fließtext unverändert bleiben muss, je Vorkommen; überlappende Funde zählen einmal (der längste)."""
    funde = sorted(((m.start(), m.end()) for muster in BEZEICHNER for m in muster.finditer(text)), key=lambda s: (s[0], -s[1]))
    aus, bis = [], -1
    for a, e in funde:
        if a >= bis:
            aus.append(text[a:e])
            bis = e
    gross = sum(z.isupper() for z in text) > 0.5 * max(1, sum(z.isalpha() for z in text))
    if not gross:                                    # ein Satz in Großbuchstaben besteht nicht aus Abkürzungen
        aus += [m.group(0) for m in ABKUERZUNG.finditer(text) if m.group(0).rstrip("s").lower() not in STOPP_EN
                and not any(a <= m.start() < e for a, e in funde)]
    return aus


def _gezaehlt(token: str, text: str) -> int:
    if ABKUERZUNG.fullmatch(token):
        return len(re.findall(r"(?<![\w])" + re.escape(token.rstrip("s")), text))
    return len(re.findall(r"(?<![\w])" + re.escape(token) + r"(?![\w])", text))


def pruefe_bezeichner(original: str, deutsch: str, begriffe: list[Begriff], **_: object) -> list[Befund]:
    en, de = marken.klartext(original), marken.klartext(deutsch)
    namen = {b.englisch.lower() for b in begriffe}
    aus = []
    for token, n in Counter(bezeichner(en)).items():
        if token.lower() not in namen and _gezaehlt(token, de) < n:
            aus.append(_befund("bezeichner", f"{token} fehlt oder ist verändert", ""))
    return aus


def pruefe_begriffe(original: str, deutsch: str, begriffe: list[Begriff], **_: object) -> list[Befund]:
    de = marken.klartext(deutsch)
    aus = []
    for b in fuer_text([b for b in begriffe if b.art == "begriff"], marken.klartext(original)):
        if b.bleibt and not im_deutschen(b.englisch, de):
            aus.append(_befund("begriffe", f"Der Begriff {b.englisch} bleibt englisch, steht aber nicht da", ""))
        elif not b.bleibt and b.deutsch and not im_deutschen(b.deutsch, de):
            aus.append(_befund("begriffe", f"Der Begriff {b.englisch} heißt hier {b.deutsch}", ""))
    return aus


def _ohne_festes(text: str, begriffe: list[Begriff]) -> str:
    """Der Text ohne Begriffe, die englisch bleiben, und ohne Bezeichner: was dann englisch klingt, ist unübersetzt."""
    for b in begriffe:
        if b.bleibt:
            text = muster_englisch(b.englisch).sub(" ", text)
    for token in sorted(set(bezeichner(text)), key=len, reverse=True):
        text = text.replace(token, " ")
    return text


def _uebernommene_klammern(original: str, deutsch: str) -> list[str]:
    """Was in einer Klammermarke unverändert aus dem Original übernommen ist (Titel, Namen): das ist kein vergessener Satz."""
    aus = []
    for n in {m.group(2) for m in marken.MARKE.finditer(original) if m.group(2)}:
        muster = re.compile(rf"<t{n}>(.*?)</t{n}>", re.S)
        vorher, nachher = muster.search(original), muster.search(deutsch)
        if vorher and nachher and marken.klartext(vorher.group(1)) == marken.klartext(nachher.group(1)):
            aus.append(marken.klartext(nachher.group(1)))
    return aus


def pruefe_sprache(original: str, deutsch: str, begriffe: list[Begriff], **_: object) -> list[Befund]:
    en, de = marken.klartext(original), marken.klartext(deutsch)
    rest = _ohne_festes(de, begriffe)
    for uebernommen in sorted(_uebernommene_klammern(original, deutsch), key=len, reverse=True):
        rest = rest.replace(uebernommen, " ")
    aus = [_befund("sprache", "Ein englischer Satz ist übrig", s) for s in saetze(rest) if englischer_satz(s)]
    if not aus and en == de and len(woerter(_ohne_festes(en, begriffe))) >= UNUEBERSETZT_AB:
        aus.append(_befund("sprache", "Der Block ist unübersetzt", de[:120]))
    return aus


def pruefe_laenge(original: str, deutsch: str, grenzen: Laengengrenzen, **_: object) -> list[Befund]:
    en, de = marken.klartext(original), marken.klartext(deutsch)
    if len(en) < grenzen.ab_zeichen:
        return []
    verhaeltnis = len(de) / len(en)
    if grenzen.kleinst <= verhaeltnis <= grenzen.groesst:
        return []
    wie = "kürzer" if verhaeltnis < grenzen.kleinst else "länger"
    return [_befund("laenge", f"Die Übersetzung ist auffällig {wie} (Verhältnis {_komma(verhaeltnis)}, erlaubt {_komma(grenzen.kleinst)} "
                              f"bis {_komma(grenzen.groesst)})")]


def _komma(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def pruefe_vollstaendigkeit(original: str, deutsch: str, **_: object) -> list[Befund]:
    vorher, nachher = len(saetze(marken.klartext(original, "X"))), len(saetze(marken.klartext(deutsch, "X")))
    if abs(vorher - nachher) <= 1:
        return []
    return [_befund("vollstaendigkeit", f"Die Zahl der Sätze weicht ab: {vorher} im Original, {nachher} in der Übersetzung", "")]


def pruefe_zeichen(original: str, deutsch: str, **_: object) -> list[Befund]:
    return [_befund("zeichen", text, stelle) for text, stelle in zeichen.befunde(deutsch)]


PRUEFUNGEN: tuple[Callable[..., list[Befund]], ...] = (
    pruefe_marken, pruefe_zahlen, pruefe_einheiten, pruefe_bezeichner, pruefe_begriffe, pruefe_sprache, pruefe_laenge,
    pruefe_vollstaendigkeit, pruefe_zeichen,
)


def pruefen(original: str, deutsch: str, begriffe: list[Begriff], grenzen: Laengengrenzen) -> list[Befund]:
    """Alle festen Prüfungen; leer heißt bestanden. `original` ist die Vorlage, `deutsch` die Übersetzung mit Marken."""
    if not deutsch.strip():
        return [_befund("vollstaendigkeit", "Die Übersetzung ist leer")]
    return [b for p in PRUEFUNGEN for b in p(original=original, deutsch=deutsch, begriffe=begriffe, grenzen=grenzen)]
