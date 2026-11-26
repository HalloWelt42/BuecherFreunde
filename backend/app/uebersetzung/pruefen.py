"""Die zehn festen Prüfungen je Block (BF-71). Alle müssen bestehen; jede liefert Befunde mit einem deutschen Satz und dem
Stück im deutschen Text, an dem es auffiel. `FASSUNG` zählt die Prüfungen: steigt sie, prüft der Lauf, was schon übersetzt
ist, ohne neue Anfrage noch einmal (services/uebersetzungslauf.py).

Vor den Prüfungen berichtigt `reparieren` an jeder Antwort der KI, was eindeutig und verlustfrei geht: eine Klammermarke,
die doppelt steht oder die es im Original nicht gibt, verliert die Marke, nie den Text (marken.reparieren). Jede Reparatur
steht als Hinweis am Block. Platzhalter fasst sie nie an.

| Prüfung | bestanden, wenn |
|---|---|
| Marken | jede Marke genau einmal, gleiche Schachtelung, keine fremde Auszeichnung; fehlt ein Platzhalter, nennt der Befund seine Stelle im Original |
| Zahlen | dieselben Zahlen nach Angleichen der Tausender- und Dezimalzeichen; Zahlwörter eins bis zwölf zählen für eine übrige Zahl (4-level: vierstufig; zahlen.py) |
| Einheiten | dieselben Einheiten, keine von selbst zugefügte Umrechnung; englische Einheitennamen in der vereinbarten Form; eine Zahl gleich hinter dem Satzende ist ein Fußnotenzeichen und trägt keine Einheit (12].1 A logical: kein Ampere) |
| Bezeichner | Adressen, Dateinamen, Pfade, Aufrufe, Bezeichner, Optionen, Versionen und Abkürzungen unverändert (außer sie stehen mit deutscher Form in der Begriffsliste) |
| Begriffe | jeder Begriff mit "bleibt" steht da, jeder mit deutscher Form in einer erlaubten Form, gebeugt oder in einem zusammengesetzten Wort; was nur Teil eines längeren Begriffs der Liste ist, zählt für diesen |
| Sprache | kein englischer Satz übrig (Begriffe und Bezeichner ausgenommen), nichts unübersetzt stehen gelassen (`unuebersetzt`: unverändert mit mindestens drei Wörtern oder einem gewöhnlichen englischen Wort außer Begriffen, Namen und Bezeichnern), keine stehengebliebene englische Wortgruppe (`stehengeblieben`) |
| Länge | Verhältnis Deutsch zu Englisch in den Grenzen, ab einer Mindestlänge des Originals |
| Vollständigkeit | gleich viele Sätze, Abweichung höchstens eins |
| Zeichen | echte Umlaute, gerade Anführungszeichen, keine Sonderstriche, keine Zeichenreferenz als Text (zeichen.py) |
| Anrede | der Leser durchgehend mit der Anrede der Fassung angesprochen, du oder Sie (anrede.py) |

Inline-Code (auch in Backticks) geht als Platzhalter nie ans Modell und kommt Zeichen für Zeichen zurück; die Prüfung
"Bezeichner" gilt dem, was im Fließtext steht. Ein Wort in Binnenmajuskeln (CrossPlatform) fordert sie nicht, wenn es aus
zwei gewöhnlichen Wörtern besteht und in einer Zeile mit lauter großen Wörtern steht (einer Überschrift, deren Bindestrich
beim Umwandeln des Buchs verloren ging) oder das Original es auch klein schreibt.

Stehengebliebenes Englisch (`stehengeblieben`): eine Wortgruppe der Übersetzung aus mindestens zwei klein geschriebenen
Wörtern, die genau so, Wort für Wort, klein im Original steht ("graphics rendering"). Das Original ist das Wörterbuch: was
dort klein steht, ist kein Name, und was nicht dort steht, ist kein stehengebliebenes Englisch. Nicht gezählt werden
Begriffe, die englisch bleiben dürfen, eingeführte Fachwörter (`englisch_im_fach`), Bezeichner, Namen mit ihrer Abkürzung,
was in einer Klammermarke unverändert aus dem Original übernommen ist (ein benannter Begriff), Text in Anführungszeichen und
Wörter, die es im Deutschen genauso gibt (`auch_deutsch`: in, so, null). Groß geschriebene Wortgruppen (Scene Management,
aber auch Game Loop, Draw Calls) unterscheidet keine feste Regel von eingeführten Begriffen: über sie urteilt der Prüfer
(Art "englisch", pruefer.py)."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Sequence

from backend.app.uebersetzung import anrede as anreden
from backend.app.uebersetzung import marken, zahlen, zeichen
from backend.app.uebersetzung.begriffe import fuer_text, im_deutschen, muster_deutsch, muster_einheit, muster_englisch
from backend.app.uebersetzung.modelle import Anrede, Befund, Befundart, Begriff, Laengengrenzen, Reparatur
from backend.app.uebersetzung.sprache import STOPP_DE, STOPP_EN, englischer_satz, saetze, woerter
from backend.app.uebersetzung.vorgaben import alltagswoerter, auch_deutsch, englisch_im_fach, in_liste

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
FASSUNG = 4
ABKUERZUNG = re.compile(r"\b[A-Z][A-Z0-9]{1,9}s?\b")
#: ein Wort aus zwei groß geschriebenen gewöhnlichen Wörtern (CrossPlatform, InGame), wie es ein verlorener Bindestrich hinterlässt
ZWEI_WOERTER = re.compile(r"[A-Z][a-z]{1,}[A-Z][a-z]{1,}")
WORT_EN = re.compile(r"[A-Za-z][A-Za-z'-]*")
#: ein Name mit seiner Abkürzung dahinter: Global Game Jam (GGJ); die Anfangsbuchstaben ergeben die Abkürzung
NAME_MIT_KUERZEL = re.compile(r"((?:[A-Z][\w'-]*\s+){1,8})\(([A-Z]{2,6})\)")
ZEILENGRENZEN = (":", ". ", "! ", "? ", "(", ")")
EINHEITEN_MEHR = ("km", "cm", "mm", "\u00b5m", "\u03bcm", "nm", "kg", "mg", "ms", "\u00b5s", "\u03bcs", "ns", "min", "Hz", "kHz", "MHz", "GHz", "KB", "kB",
                  "MB", "GB", "TB", "PB", "KiB", "MiB", "GiB", "TiB", "kbit", "Mbit", "Gbit", "bps", "kbps", "Mbps", "Gbps", "mV", "kV",
                  "mA", "mAh", "kW", "MW", "Wh", "kWh", "°C", "°F", "px", "pt", "dpi", "ppi", "ft", "mi", "lb", "lbs", "oz", "mph", "psi",
                  "ml", "dB", "fps", "rpm")
EINHEIT = re.compile(r"(?<=\d)(?:[ \u00a0\u202f]?(?P<mehr>" + "|".join(sorted(map(re.escape, EINHEITEN_MEHR), key=len, reverse=True))
                     + r")|[ \u00a0\u202f](?P<eins>[smghlVWABK]))(?![\w])|(?<=\d)[ \u00a0\u202f]?(?P<prozent>%)")
PROZENT_WORT = re.compile(r"(?<=\d)[ \u00a0\u202f]Prozent\b")
#: eine Zahl gleich hinter dem Ende eines Satzes oder einer Klammer ist ein Fußnotenzeichen, keine Menge: "[bit 12].1 A logical"
FUSSNOTENZEICHEN = re.compile(r"(?:(?<=[^\W\d_][.!?;:,)\]])|(?<=[)\]][.!?;:,]))\d+(?=[ \u00a0\u202f])")
UNUEBERSETZT_AB = 3                                  # so viele Wörter ohne Begriffe und Bezeichner, damit Gleichheit auffällt
STEHENGEBLIEBEN_AB = 2                               # so viele englische Wörter, die nicht auch deutsch sind, machen eine Wortgruppe
#: ein englisch geschriebenes Wort: Buchstaben ohne Umlaute, auch mit Bindestrichen (platform-specific)
WORT_ASCII = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)*")
#: Text in geraden Anführungszeichen: ein Name, eine Aufschrift, ein Zitat
ANGEFUEHRT = re.compile(r'"[^"]*"')
LUECKE = " | "                                       # was an die Stelle von Ausgenommenem tritt; trennt Wortgruppen


def _befund(art: Befundart, text: str, stelle: str = "") -> Befund:
    return Befund(art=art, quelle="pruefung", text=text, stelle=stelle)


def reparieren(original: str, deutsch: str) -> tuple[str, list[Reparatur]]:
    """Eine Antwort der KI mit eindeutig und verlustfrei berichtigten Marken, dazu je Berichtigung ein Hinweis."""
    text, berichtigt = marken.reparieren(original, deutsch)
    return text, [Reparatur(art="marken", text=b.grund, stelle=b.stelle) for b in berichtigt]


def pruefe_marken(original: str, deutsch: str, **_: object) -> list[Befund]:
    plan = marken.plan(original)
    try:
        marken.lesen(plan, deutsch)
    except marken.MarkenFehler as f:
        fehlt = f.grund.endswith("fehlt") and f.nr in plan and plan[f.nr].atom
        ort = marken.umgebung(original, f.nr) if fehlt else ""
        return [_befund("marken", f"{f.grund}; im Original steht sie so: \"{ort}\"" if ort else f.grund, f.stelle)]
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
    text = FUSSNOTENZEICHEN.sub(" ", text)
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
        if b.art != "einheit" or not b.formen():
            continue
        n = len(muster_einheit(b.englisch).findall(en))
        if n and max(len(muster_deutsch(f).findall(de)) for f in b.formen()) < n:
            aus.append(_befund("einheiten", f"Die Einheit {b.englisch} steht nicht als {b.vereinbart} da", ""))
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


def _zeile_aus_grossen_woertern(text: str, stelle: int) -> bool:
    """Ob die Zeile um eine Stelle (bis Doppelpunkt, Klammer oder Satzende) aus lauter groß geschriebenen Wörtern besteht;
    kleine Wörter (of, and, the) zählen nicht."""
    anfang = max(text.rfind(z, 0, stelle) for z in ZEILENGRENZEN) + 1
    ende = min([i for z in ZEILENGRENZEN if (i := text.find(z, stelle)) >= 0] + [len(text)])
    woerter = [w for w in WORT_EN.findall(text[anfang:ende]) if w.lower() not in STOPP_EN]
    return len(woerter) >= 2 and all(w[0].isupper() for w in woerter)


def gefordert(text: str) -> list[str]:
    """Die Bezeichner, die die Übersetzung tragen muss: ohne Wörter aus zwei gewöhnlichen Wörtern, die nur ein verlorener
    Bindestrich zusammenschrieb (in einer Zeile aus großen Wörtern, oder das Original schreibt sie auch klein)."""
    aus = []
    for token in bezeichner(text):
        if ZWEI_WOERTER.fullmatch(token):
            stellen = [m.start() for m in re.finditer(rf"(?<![\w]){re.escape(token)}(?![\w])", text)]
            klein = re.search(rf"(?<![\w]){re.escape(token.lower())}(?![\w])", text)
            if klein or (stellen and all(_zeile_aus_grossen_woertern(text, s) for s in stellen)):
                continue
        aus.append(token)
    return aus


def pruefe_bezeichner(original: str, deutsch: str, begriffe: list[Begriff], **_: object) -> list[Befund]:
    en, de = marken.klartext(original), marken.klartext(deutsch)
    namen = {b.englisch.lower() for b in begriffe}
    aus = []
    for token, n in Counter(gefordert(en)).items():
        if token.lower() not in namen and _gezaehlt(token, de) < n:
            aus.append(_befund("bezeichner", f"{token} fehlt oder ist verändert", ""))
    return aus


def pruefe_begriffe(original: str, deutsch: str, begriffe: list[Begriff], **_: object) -> list[Befund]:
    de = marken.klartext(deutsch)
    aus = []
    for b in fuer_text([b for b in begriffe if b.art == "begriff"], marken.klartext(original)):
        if b.bleibt and not im_deutschen(b.englisch, de):
            aus.append(_befund("begriffe", f"Der Begriff {b.englisch} bleibt englisch, steht aber nicht da", ""))
        elif not b.bleibt and b.formen() and not im_deutschen(b.deutsch, de):
            aus.append(_befund("begriffe", f"Der Begriff {b.englisch} heißt hier {' oder '.join(b.formen())}", ""))
    return aus


def namen_mit_kuerzel(text: str) -> list[str]:
    """Namen, hinter denen ihre Abkürzung steht (Game Developers Conference (GDC)): sie dürfen bleiben, wie sie sind."""
    aus = []
    for m in NAME_MIT_KUERZEL.finditer(text):
        woerter, kuerzel = m.group(1).split(), m.group(2)
        if len(woerter) >= len(kuerzel) and "".join(w[0] for w in woerter[-len(kuerzel):]) == kuerzel:
            aus.append(" ".join(woerter[-len(kuerzel):]))
    return aus


def englisch_erlaubt(b: Begriff) -> bool:
    """Ob ein Begriff der Liste englisch dastehen darf: er bleibt, oder das englische Wort ist eine seiner Formen."""
    return b.bleibt or any(f.casefold() == b.englisch.casefold() for f in b.formen())


def _ohne_festes(text: str, begriffe: list[Begriff], namen: Sequence[str] = (), luecke: str = " ") -> str:
    """Der Text ohne Begriffe, die englisch dastehen dürfen, ohne Namen mit ihrer Abkürzung und ohne Bezeichner: was dann
    englisch klingt, ist unübersetzt. `luecke` tritt an ihre Stelle."""
    for b in begriffe:
        if englisch_erlaubt(b):
            text = muster_englisch(b.englisch).sub(luecke, text)
    for name in sorted(namen, key=len, reverse=True):
        text = text.replace(name, luecke)
    for token in sorted(set(bezeichner(text)), key=len, reverse=True):
        text = text.replace(token, luecke)
    return text


def _ohne_fachwoerter(text: str, luecke: str = LUECKE) -> str:
    """Der Text ohne eingeführte Fachwörter, die englisch bleiben (`englisch_im_fach`, auch Wortgruppen wie game loop)."""
    for eintrag in sorted(englisch_im_fach(), key=len, reverse=True):
        text = muster_englisch(eintrag).sub(luecke, text)
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


def unuebersetzt(original: str, deutsch: str, begriffe: list[Begriff]) -> bool:
    """Ob ein Block unverändert zurückkam, obwohl er Englisch trägt: ohne Begriffe, die englisch bleiben, Namen mit ihrer
    Abkürzung und Bezeichner bleiben mindestens `UNUEBERSETZT_AB` Wörter oder ein gewöhnliches englisches Wort
    (Introduction, Basics). Ein Name oder Code für sich ist nicht unübersetzt. Verglichen wird mit geraden Zeichen, wie jede
    Antwort sie bekommt: ein abgeschriebener Block mit Gedankenstrich (" \u2014 #SS \u2014 ") ist danach nicht mehr zeichengleich."""
    en, de = marken.klartext(original), marken.klartext(deutsch)
    if zeichen.gerade(en) != zeichen.gerade(de):
        return False
    rest = woerter(_ohne_festes(en, begriffe, namen_mit_kuerzel(en)))
    return len(rest) >= UNUEBERSETZT_AB or any(in_liste(w, alltagswoerter()) for w in rest)


def _ohne_uebernommenes(original: str, deutsch: str, de: str, luecke: str = " ") -> str:
    """Der deutsche Klartext ohne das, was in einer Klammermarke unverändert aus dem Original übernommen ist."""
    for uebernommen in sorted(_uebernommene_klammern(original, deutsch), key=len, reverse=True):
        de = de.replace(uebernommen, luecke)
    return de


def _klein_im_original(woerter_: Sequence[str], en: str) -> bool:
    """Ob Wörter genau so, klein und nacheinander (getrennt durch Leerraum oder Bindestrich), im Original stehen."""
    return re.search(r"(?<![\w-])" + r"[\s-]+".join(re.escape(w) for w in woerter_) + r"(?![\w-])", en) is not None


def _englisches_wort(wort: str) -> bool:
    return wort.islower() and wort not in STOPP_DE


def _zaehlt(gruppe: Sequence[str]) -> bool:
    return sum(w not in auch_deutsch() for w in gruppe) >= STEHENGEBLIEBEN_AB


def stehengeblieben(original: str, deutsch: str, begriffe: list[Begriff]) -> list[str]:
    """Die englischen Wortgruppen, die in der Übersetzung stehen geblieben sind (siehe oben), je Vorkommen."""
    en = marken.klartext(original, LUECKE)
    de = _ohne_uebernommenes(original, deutsch, marken.klartext(deutsch, LUECKE), LUECKE)
    de = ANGEFUEHRT.sub(LUECKE, _ohne_fachwoerter(_ohne_festes(de, begriffe, namen_mit_kuerzel(en), LUECKE)))
    aus: list[str] = []
    gruppe: list[str] = []
    ende = 0
    for m in WORT_ASCII.finditer(de):
        w = m.group(0)
        anschluss = bool(gruppe) and not de[ende:m.start()].strip() and _klein_im_original([gruppe[-1], w], en)
        if _englisches_wort(w) and anschluss:
            gruppe.append(w)
        else:
            if _zaehlt(gruppe):
                aus.append(" ".join(gruppe))
            gruppe = [w] if _englisches_wort(w) else []
        ende = m.end()
    if _zaehlt(gruppe):
        aus.append(" ".join(gruppe))
    return aus


def englisch_aus_dem_original(stelle: str, original: str, begriffe: list[Begriff]) -> list[str]:
    """Die Wörter einer Stelle, die englisch aus dem Original stammen und nicht englisch bleiben dürfen (Begriffe, die bleiben,
    eingeführte Fachwörter, Bezeichner, Wörter, die es auch im Deutschen gibt): leer, wenn an der Stelle kein
    stehengebliebenes Englisch sein kann (pruefer.py)."""
    im_original = {w.casefold() for w in WORT_ASCII.findall(marken.klartext(original))}
    rest = _ohne_fachwoerter(_ohne_festes(marken.klartext(stelle), begriffe, (), LUECKE))
    return [w for w in WORT_ASCII.findall(rest) if w.casefold() in im_original and w.casefold() not in STOPP_DE
            and w.casefold() not in auch_deutsch()]


def pruefe_sprache(original: str, deutsch: str, begriffe: list[Begriff], **_: object) -> list[Befund]:
    en, de = marken.klartext(original), marken.klartext(deutsch)
    rest = _ohne_festes(_ohne_uebernommenes(original, deutsch, de), begriffe, namen_mit_kuerzel(en))
    aus = [_befund("sprache", "Ein englischer Satz ist übrig", s) for s in saetze(rest) if englischer_satz(s)]
    if not aus and unuebersetzt(original, deutsch, begriffe):
        aus.append(_befund("sprache", "Der Block ist unübersetzt", de[:120]))
    if not aus:
        aus = [_befund("sprache", f"Englisch stehen geblieben: \"{g}\" hat im Deutschen eine übliche Form", g)
               for g in stehengeblieben(original, deutsch, begriffe)]
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


def pruefe_anrede(original: str, deutsch: str, anrede: Anrede, **_: object) -> list[Befund]:
    return [_befund("anrede", text, stelle) for text, stelle in anreden.befunde(marken.klartext(original), marken.klartext(deutsch), anrede)]


def pruefe_zeichen(original: str, deutsch: str, **_: object) -> list[Befund]:
    befunde = zeichen.befunde(deutsch) + zeichen.referenzen(marken.klartext(original), marken.klartext(deutsch))
    return [_befund("zeichen", text, stelle) for text, stelle in befunde]


PRUEFUNGEN: tuple[Callable[..., list[Befund]], ...] = (
    pruefe_marken, pruefe_zahlen, pruefe_einheiten, pruefe_bezeichner, pruefe_begriffe, pruefe_sprache, pruefe_laenge,
    pruefe_vollstaendigkeit, pruefe_zeichen, pruefe_anrede,
)


def pruefen(original: str, deutsch: str, begriffe: list[Begriff], grenzen: Laengengrenzen, anrede: Anrede) -> list[Befund]:
    """Alle festen Prüfungen; leer heißt bestanden. `original` ist die Vorlage, `deutsch` die Übersetzung mit Marken, beide in
    der Schreibweise der Vorlagen."""
    if not deutsch.strip():
        return [_befund("vollstaendigkeit", "Die Übersetzung ist leer")]
    return [b for p in PRUEFUNGEN for b in p(original=original, deutsch=deutsch, begriffe=begriffe, grenzen=grenzen, anrede=anrede)]
