"""Der Aufbau eines PDF (BF-71): aus den Stücken der Seiten in Lesefolge (pdf_lesen.py) die Elemente eines Buchs wie in einem
EPUB: Überschriften mit Stufe, Absätze, Listen, Tabellen, Code, Abbildungen mit Bildunterschrift, Fußnoten und Kästen, dazu
die Kapitel. Jedes Element merkt sich Seite und Lage seines Anfangs; geht ein Absatz über einen Seitenwechsel, steht die
Stelle des Wechsels in seinem Text.

- Grundschrift: die Größe, in der die meisten Zeichen stehen; der Zeilenabstand je Größe, wie er am häufigsten vorkommt.
- Überschriften: Absätze von höchstens drei Zeilen in größerer Schrift oder ganz fett. Die Stufen kommen aus der Verteilung
  im Dokument: jede Schrift einer Überschrift (Größe, fett) ist eine Stufe, die größte zuerst, fett vor mager.
- Absätze: Zeilen gehören zusammen, solange die nächste in derselben Schrift folgt, nicht eingerückt beginnt und die vorige
  voll war (ihr fehlte der Platz für das erste Wort der nächsten). So geht ein Absatz über einen Spalten- oder Seitenwechsel
  weiter. Eine Trennung am Zeilenende wird aufgelöst: der Bindestrich fällt weg, außer das Dokument schreibt das Wort sonst
  mit ihm ("well-known"). Abbildungen, Tabellen, Kästen und Fußnoten dazwischen kommen hinter den Absatz, den sie
  unterbrechen; Code beendet ihn.
- Listen: ein Absatz, der mit einem Aufzählungszeichen oder einer Nummer beginnt ("\u2022", "1.", "a)"), ist ein Listenpunkt;
  Zeilen bündig mit seinem Text gehören dazu. Das Zeichen bleibt, wie es gedruckt ist.
- Fußnoten: am Fuß einer Seite die Zeilen in kleinerer Schrift, die mit einem Zeichen beginnen; ein hochgestelltes Zeichen im
  Text verweist auf die Fußnote derselben Seite mit diesem Zeichen.
- Bildunterschriften: ein Absatz, der mit "Figure 1", "Table 2", "Listing 3" (auch deutsch) beginnt, gehört zur Abbildung,
  Tabelle oder Codestelle gleich davor oder danach auf derselben Seite.
- Kästen: Text in einem Rahmen oder auf einer Fläche ist ein Kasten mit seinen eigenen Elementen; steht darin nur eine
  Überschrift (ein farbiges Band), gehört sie in den Text.
- Kapitel: aus dem Inhaltsverzeichnis des PDF (oberste Stufe), sonst an den Überschriften der obersten Stufe, die mehr als
  einmal vorkommt; was davor steht, ist ein eigenes Kapitel."""

from __future__ import annotations

import itertools
import re
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import fitz

from backend.app.uebersetzung import pdf_lesen
from backend.app.uebersetzung.pdf_lesen import Seite, Zeile

UEBERSCHRIFT_FAKTOR = 1.12      # so viel größer als die Grundschrift ist eine Überschrift
UEBERSCHRIFT_ZEILEN = 3
UEBERSCHRIFT_HOECHSTENS = 200   # Zeichen
KLEIN = 0.9                     # so viel kleiner als die Grundschrift: Fußnoten, Unterschriften
ENG = 1.35                      # Zeilenabstände: so dicht folgt die nächste Zeile eines Absatzes
EINZUG = 0.8                    # Schriftgrößen: ab hier beginnt eine Zeile eingerückt
STUFEN = 6
ZEICHEN = "\u2022\u25e6\u25aa\u25ab\u2023\u2043\u25cf\u25cb\u25a0\u25a1\u2013\u2014\u00b7*-"
LISTENZEICHEN = re.compile(rf"^([{re.escape(ZEICHEN)}]|\(?\d{{1,3}}[.)]|\(?[a-z][.)]|\((?:[ivx]{{1,5}})\))(?=\s)")
GEORDNET = re.compile(r"^\(?(?:\d|[a-z]|[ivx])")
FUSSNOTENZEICHEN = re.compile(r"^(\d{1,3}|[*\u2020\u2021\u00a7\u00b6]{1,3})(?=[\s.)]|[A-Z])")
UNTERSCHRIFT = re.compile(r"^(?:Figure|Fig\.|Table|Tab\.|Listing|Abbildung|Abb\.|Tabelle|Code)\s*[\dIVXA-Z]+(?:[.\-]\d+)*\s*[:.]?",
                          re.IGNORECASE)
WORT = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")


# -- Text im Satz ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Stil:
    fett: bool = False
    kursiv: bool = False
    festbreit: bool = False
    hoch: bool = False


@dataclass
class Lauf:
    """Text in einer Auszeichnung."""
    text: str
    stil: Stil


@dataclass(frozen=True)
class Seitenwechsel:
    """Hier beginnt im Original die Seite `seite` (Dateiseite)."""
    seite: int


@dataclass(frozen=True)
class Verweis:
    """Ein Fußnotenzeichen im Text, mit der Kennung der Fußnote."""
    zeichen: str
    fussnote: str
    anker: str


Inhalt = list[Lauf | Seitenwechsel | Verweis]


def klartext(inhalt: Inhalt) -> str:
    return "".join(t.text if isinstance(t, Lauf) else t.zeichen if isinstance(t, Verweis) else "" for t in inhalt)


def ohne_gemeinsames(inhalt: Inhalt) -> Inhalt:
    """Der Inhalt ohne die Auszeichnung, die aller Text trägt (eine Überschrift ist ohnehin fett, eine Unterschrift kursiv)."""
    stile = [t.stil for t in inhalt if isinstance(t, Lauf) and t.text.strip()]
    if not stile:
        return inhalt
    fett, kursiv = all(s.fett for s in stile), all(s.kursiv for s in stile)
    if not (fett or kursiv):
        return inhalt
    return _zusammengefasst([Lauf(t.text, Stil(t.stil.fett and not fett, t.stil.kursiv and not kursiv, t.stil.festbreit, t.stil.hoch))
                             if isinstance(t, Lauf) else t for t in inhalt])


# -- Elemente -------------------------------------------------------------------------------------------------------------

@dataclass(eq=False)
class Element:
    seite: int                                       # Dateiseite, auf der es beginnt
    lage: fitz.Rect                                  # seine Fläche auf dieser Seite


@dataclass(eq=False)
class Ueberschrift(Element):
    inhalt: Inhalt
    schrift: tuple[float, bool]                      # Größe und fett: daraus die Stufe
    stufe: int = 1
    anker: str = ""


@dataclass(eq=False)
class Absatz(Element):
    inhalt: Inhalt
    festbreit: bool = False                          # ganz in Festbreitenschrift (ob es Code ist, entscheidet die Erkennung)


@dataclass(eq=False)
class Punkt(Element):
    zeichen: str
    inhalt: Inhalt


@dataclass(eq=False)
class Liste(Element):
    geordnet: bool
    punkte: list[Punkt]


@dataclass(eq=False)
class Zelle(Element):
    inhalt: Inhalt
    kopf: bool
    spalten: int


@dataclass(eq=False)
class Tabelle(Element):
    reihen: list[list[Zelle]]
    unterschrift: Absatz | None = None


@dataclass(eq=False)
class Code(Element):
    teile: list[tuple[int, str]]                     # Seite und Code jedes Teils
    unterschrift: Absatz | None = None


@dataclass(eq=False)
class Abbildung(Element):
    quelle: pdf_lesen.Abbildung
    unterschrift: Absatz | None = None


@dataclass(eq=False)
class Fussnote(Element):
    zeichen: str
    inhalt: Inhalt                                   # ohne das Zeichen
    anker: str
    verweis: str = ""                                # Anker des Zeichens im Text, wenn es eines gibt


@dataclass(eq=False)
class Kasten(Element):
    elemente: list[Element] = field(default_factory=list)


@dataclass(eq=False)
class Kapitel:
    titel: str
    elemente: list[Element]


@dataclass(frozen=True)
class Eintrag:
    """Ein Eintrag des Inhaltsverzeichnisses: Stufe, Titel und wohin er zeigt (Kapitel, Anker)."""
    stufe: int
    titel: str
    kapitel: int                                     # Stelle in `Buch.kapitel`, ab 0
    anker: str


@dataclass(eq=False)
class Buch:
    kapitel: list[Kapitel]
    verzeichnis: list[Eintrag]


# -- Maße des Dokuments ---------------------------------------------------------------------------------------------------

def _alle_zeilen(stuecke: list[pdf_lesen.Stueck]) -> list[Zeile]:
    aus = []
    for s in stuecke:
        if isinstance(s, Zeile):
            aus.append(s)
        elif isinstance(s, pdf_lesen.Kasten):
            aus += _alle_zeilen(s.stuecke)
    return aus


def _gerundet(groesse: float) -> float:
    return round(groesse * 2) / 2


VOLLE_SEITE = 10                # so viele Zeilen zeigen, wo auf einer Seite der Text endet


@dataclass
class Masse:
    grund: float
    abstand: dict[float, float]                      # Größe -> üblicher Abstand der Grundlinien
    woerter: Counter[str]                            # Wörter, wie das Dokument sie schreibt (für die Trennung)
    rechts: dict[int, float]                         # rechtes Ende des Texts auf Seiten mit gerader (0) und ungerader (1) Nummer

    def zeilenabstand(self, groesse: float) -> float:
        return self.abstand.get(_gerundet(groesse), groesse * 1.25)


def masse(seiten: list[Seite]) -> Masse:
    zeichen: Counter[float] = Counter()
    schritte: dict[float, Counter[float]] = {}
    woerter: Counter[str] = Counter()
    rechts: dict[int, list[float]] = {0: [], 1: []}
    for s in seiten:
        zeilen = _alle_zeilen(s.stuecke)
        for z in zeilen:
            zeichen[_gerundet(z.groesse)] += len(z.text)
            teile = z.text.split()
            for w in teile[:-1] if z.text.rstrip().endswith("-") else teile:
                woerter.update(m.group(0).lower() for m in WORT.finditer(w))
        for a, b in zip(zeilen, zeilen[1:]):
            d = b.basis - a.basis
            if a.seite == b.seite and _gerundet(a.groesse) == _gerundet(b.groesse) and 0.9 * a.groesse < d < 2.2 * a.groesse \
                    and pdf_lesen.ueberdecken_x(a.rechteck, b.rechteck):
                schritte.setdefault(_gerundet(a.groesse), Counter())[round(d, 1)] += 1
        if len(zeilen) >= VOLLE_SEITE:
            rechts[s.nr % 2].append(max(z.rechteck.x1 for z in zeilen))
    grund = zeichen.most_common(1)[0][0] if zeichen else 10.0
    return Masse(grund=grund, abstand={g: c.most_common(1)[0][0] for g, c in schritte.items()}, woerter=woerter,
                 rechts={p: statistics.median(r) for p, r in rechts.items() if r})


# -- Spalten einer Seite --------------------------------------------------------------------------------------------------

@dataclass
class Rahmen:
    """Wo die Zeilen einer Seite stehen: die Spalten (links, rechts) und die ganze Breite."""
    spalten: list[tuple[float, float]]
    breit: tuple[float, float]

    def von(self, z: Zeile) -> tuple[float, float]:
        for links, rechts in self.spalten:
            if z.rechteck.x0 >= links - 2 and z.rechteck.x1 <= rechts + 2:
                return links, rechts
        return self.breit


def _luecken(zeilen: list[Zeile], links: float, rechts: float, tiefe: int = 0) -> list[float]:
    """Senkrechte Lücken zwischen Spalten: Stellen, über die kaum eine Zeile reicht, mit Zeilen auf beiden Seiten."""
    breite = rechts - links
    if tiefe > 2 or breite <= 0 or len(zeilen) < 6:
        return []
    beste, wenigste = None, None
    x = links + breite * 0.2
    while x <= rechts - breite * 0.2:
        ueber = sum(1 for z in zeilen if z.rechteck.x0 < x < z.rechteck.x1)
        if wenigste is None or ueber < wenigste:
            beste, wenigste = x, ueber
        x += 2.0
    if beste is None or wenigste > 0.25 * len(zeilen):
        return []
    links_davon = [z for z in zeilen if z.rechteck.x1 <= beste]
    rechts_davon = [z for z in zeilen if z.rechteck.x0 >= beste]
    if len(links_davon) < 3 or len(rechts_davon) < 3:
        return []
    return (_luecken(links_davon, links, beste, tiefe + 1) + [beste] + _luecken(rechts_davon, beste, rechts, tiefe + 1))


def rahmen(seite: int, zeilen: list[Zeile], m: Masse) -> Rahmen:
    """Die Spalten einer Seite aus ihren Zeilen in Grundschrift; auf einer Seite mit wenig Text reicht die ganze Breite so weit
    wie auf den vollen Seiten derselben Seitenart (gerade, ungerade)."""
    text = [z for z in zeilen if 0.8 * m.grund <= z.groesse <= 1.25 * m.grund] or zeilen
    if not text:
        return Rahmen([], (0.0, 0.0))
    links, rechts = min(z.rechteck.x0 for z in text), max(z.rechteck.x1 for z in text)
    grenzen = [links, *_luecken(text, links, rechts), rechts]
    if len(grenzen) == 2:
        if len(text) < VOLLE_SEITE:
            rechts = max(rechts, m.rechts.get(seite % 2, rechts))
        return Rahmen([], (links, rechts))
    spalten = []
    for a, b in zip(grenzen, grenzen[1:]):
        darin = [z for z in text if z.rechteck.x0 >= a - 2 and z.rechteck.x1 <= b + 2]
        if darin:
            spalten.append((min(z.rechteck.x0 for z in darin), max(z.rechteck.x1 for z in darin)))
    return Rahmen(spalten, (links, rechts))


# -- Zeilen eines Absatzes ------------------------------------------------------------------------------------------------

def _schrift(z: Zeile, m: Masse) -> tuple:
    """Woran man Zeilen eines Absatzes erkennt: Überschrift (mit Größe und fett), klein, Festbreite oder Text."""
    if z.groesse >= m.grund * UEBERSCHRIFT_FAKTOR or (z.fett and z.groesse >= m.grund * 0.95):
        return ("kopf", _gerundet(z.groesse), z.fett)
    if z.festbreit:
        return ("fest",)
    if z.groesse <= m.grund * KLEIN:
        return ("klein",)
    return ("text",)


def _zeichen(z: Zeile) -> re.Match | None:
    return LISTENZEICHEN.match(z.text)


def _erstes_wort(z: Zeile) -> float:
    s = z.spannen[0]
    wort = s.text.split()[0] if s.text.split() else s.text
    return (s.x1 - s.x0) * len(wort) / max(len(s.text), 1)


def _getrennt(a: Zeile, b: Zeile) -> bool:
    """Endet a mit einer Trennung, die b fortsetzt (Bindestrich nach Buchstabe oder weiches Trennzeichen, b beginnt klein)?"""
    t = a.text.rstrip()
    if t.endswith("\u00ad"):
        return True
    return len(t) > 1 and t[-1] == "-" and t[-2].isalpha() and b.text[:1].islower()


@dataclass(eq=False)
class _Offen:
    zeilen: list[Zeile]
    schrift: tuple
    zeichen: re.Match | None = None                  # Listenpunkt: sein Zeichen


class _Bau:
    """Geht die Stücke in Lesefolge durch und baut die Elemente; Einschübe warten, bis der Absatz endet, den sie
    unterbrechen."""

    def __init__(self, m: Masse, rahmen_je_seite: dict[int, Rahmen], fussnoten: dict[tuple[int, str], Fussnote],
                 verweise: itertools.count | None = None) -> None:
        self.m, self.rahmen, self.fussnoten = m, rahmen_je_seite, fussnoten
        self.verweise = verweise or itertools.count(1)        # Anker der Fußnotenzeichen, über Kästen hinweg gezählt
        self.elemente: list[Element] = []
        self.offen: _Offen | None = None
        self.warten: list[Element] = []

    # -- Zeilen --------------------------------------------------------------------------------------------------------
    def zeile(self, z: Zeile) -> None:
        if self.offen is not None and self._weiter(self.offen, z):
            self.offen.zeilen.append(z)
            return
        self.schliessen()
        zeichen = _zeichen(z) if _schrift(z, self.m)[0] in ("text", "klein") else None
        self.offen = _Offen([z], _schrift(z, self.m), zeichen)

    def _rahmen(self, z: Zeile) -> tuple[float, float]:
        r = self.rahmen.get(z.seite)
        return r.von(z) if r is not None else (z.rechteck.x0, z.rechteck.x1)

    def _voll(self, a: Zeile, b: Zeile) -> bool:
        """War a voll? Ihr fehlte der Platz für das erste Wort von b."""
        rest = self._rahmen(a)[1] - a.rechteck.x1
        return rest < _erstes_wort(b) + 0.5 * a.groesse

    def _weiter(self, o: _Offen, b: Zeile) -> bool:
        a = o.zeilen[-1]
        if _schrift(b, self.m) != o.schrift or (o.schrift[0] in ("text", "klein") and _zeichen(b)):
            return False
        darunter = (a.seite == b.seite and pdf_lesen.ueberdecken_x(a.rechteck, b.rechteck)
                    and 0 < b.basis - a.basis <= self.m.zeilenabstand(a.groesse) * ENG)
        if o.schrift[0] == "kopf":
            return darunter and len(o.zeilen) < UEBERSCHRIFT_ZEILEN
        if o.zeichen is not None:
            return self._im_punkt(o, a, b, darunter)
        if _getrennt(a, b):
            return True
        if darunter:                                       # eingerückt gegenüber den Zeilen des Absatzes in dieser Spalte?
            links = min(z.rechteck.x0 for z in o.zeilen if z.seite == b.seite and pdf_lesen.ueberdecken_x(z.rechteck, b.rechteck))
            return b.rechteck.x0 <= links + EINZUG * b.groesse and self._voll(a, b)
        sprung = (b.seite == a.seite + 1) or (b.seite == a.seite and b.rechteck.y0 < a.rechteck.y0 and b.rechteck.x0 > a.rechteck.x0)
        return sprung and b.rechteck.x0 <= self._rahmen(b)[0] + EINZUG * b.groesse and self._voll(a, b)

    def _im_punkt(self, o: _Offen, a: Zeile, b: Zeile, darunter: bool) -> bool:
        """Gehört b zum Listenpunkt? Hängend eingerückt (rechts vom Zeichen, höchstens vier Schriftgrößen), oder bündig mit dem
        Zeichen, wenn a voll war; nach einem Spalten- oder Seitenwechsel mit derselben Einrückung gegenüber der Spalte."""
        erste = o.zeilen[0]
        em = b.groesse
        if darunter:
            versatz = b.rechteck.x0 - erste.rechteck.x0 if erste.seite == b.seite else b.rechteck.x0 - a.rechteck.x0
        elif self._voll(a, b) or _getrennt(a, b):
            versatz = (b.rechteck.x0 - self._rahmen(b)[0]) - (erste.rechteck.x0 - self._rahmen(erste)[0])
        else:
            return False
        haengend = 0.4 * em < versatz <= 4 * em
        buendig = abs(versatz) <= 0.5 * em and (self._voll(a, b) or _getrennt(a, b))
        return haengend or buendig

    # -- Einschübe -----------------------------------------------------------------------------------------------------
    def einschub(self, e: Element, wartet: bool) -> None:
        """Ein Element zwischen den Zeilen; `wartet`: es darf hinter den Absatz, den es unterbricht (Abbildung, Tabelle,
        Kasten, Fußnote), sonst endet der Absatz davor (Code)."""
        if self.offen is not None and wartet:
            self.warten.append(e)
            return
        self.schliessen()
        self.elemente.append(e)

    def schliessen(self) -> None:
        if self.offen is not None:
            self.elemente.append(self._element(self.offen))
            self.offen = None
        self.elemente += self.warten
        self.warten = []

    # -- Elemente aus Zeilen -------------------------------------------------------------------------------------------
    def _element(self, o: _Offen) -> Element:
        erste = o.zeilen[0]
        lage = fitz.Rect(erste.rechteck)
        for a, z in zip(o.zeilen, o.zeilen[1:]):            # die Lage des Anfangs: bis zum ersten Spalten- oder Seitenwechsel
            if z.seite != a.seite or not pdf_lesen.ueberdecken_x(a.rechteck, z.rechteck) or z.basis <= a.basis:
                break
            lage |= z.rechteck
        text = " ".join(z.text for z in o.zeilen)
        if o.schrift[0] == "kopf" and len(text) <= UEBERSCHRIFT_HOECHSTENS:
            return Ueberschrift(erste.seite, lage, ohne_gemeinsames(self.inhalt(o.zeilen)), (o.schrift[1], o.schrift[2]))
        if o.zeichen is not None:
            return Punkt(erste.seite, lage, o.zeichen.group(1), self.inhalt(o.zeilen, ab=o.zeichen.end()))
        return Absatz(erste.seite, lage, self.inhalt(o.zeilen), festbreit=o.schrift[0] == "fest")

    def inhalt(self, zeilen: list[Zeile], ab: int = 0) -> Inhalt:
        """Der Text der Zeilen mit seinen Auszeichnungen, Trennungen aufgelöst, Seitenwechsel und Fußnotenzeichen an ihrer
        Stelle; `ab` Zeichen der ersten Zeile fallen weg (das Zeichen eines Listenpunkts)."""
        aus: Inhalt = []
        for i, z in enumerate(zeilen):
            laeufe = [Lauf(s.text, Stil(s.fett, s.kursiv, s.festbreit, s.hoch)) for s in z.spannen]
            if i == 0 and ab:
                laeufe = _ohne_anfang(laeufe, ab)
            laeufe = [self._verweis(z, l) for l in laeufe]
            if i == 0:
                aus += laeufe
                continue
            vorige = zeilen[i - 1]
            wechsel = [Seitenwechsel(z.seite)] if z.seite != vorige.seite else []
            if _getrennt(vorige, z) and laeufe and isinstance(laeufe[0], Lauf):
                self._trennung_aufloesen(aus, laeufe[0])
                kopf, rest = _erstes_wort_teilen(laeufe[0])
                aus += [kopf, *wechsel, *([rest] if rest.text else []), *laeufe[1:]]
            else:
                aus += [Lauf(" ", _gemeinsam(aus, laeufe)), *wechsel, *laeufe]
        return _zusammengefasst(aus)

    def _verweis(self, z: Zeile, lauf: Lauf) -> Lauf | Verweis:
        """Ein hochgestelltes Zeichen, zu dem es auf derselben Seite eine Fußnote gibt, verweist auf sie."""
        f = self.fussnoten.get((z.seite, lauf.text.strip())) if lauf.stil.hoch else None
        if f is None:
            return lauf
        f.verweis = f.verweis or f"fn-verweis-{next(self.verweise)}"
        return Verweis(lauf.text.strip(), f.anker, f.verweis)

    def _trennung_aufloesen(self, aus: Inhalt, weiter: Lauf) -> None:
        """Der Bindestrich am Zeilenende fällt weg, außer das Dokument schreibt das Wort sonst mit ihm."""
        letzter = next((t for t in reversed(aus) if isinstance(t, Lauf)), None)
        if letzter is None:
            return
        if letzter.text.endswith("\u00ad"):
            letzter.text = letzter.text[:-1]
            return
        vorn = (WORT.findall(letzter.text[:-1]) or [""])[-1].lower()
        hinten = (WORT.findall(weiter.text) or [""])[0].lower()
        if self.m.woerter[f"{vorn}-{hinten}"] <= self.m.woerter[f"{vorn}{hinten}"] or not vorn:
            letzter.text = letzter.text[:-1]


def _ohne_anfang(laeufe: list[Lauf], n: int) -> list[Lauf]:
    aus, weg = [], n
    for l in laeufe:
        if weg >= len(l.text):
            weg -= len(l.text)
            continue
        aus.append(Lauf(l.text[weg:], l.stil))
        weg = 0
    if aus:
        aus[0].text = aus[0].text.lstrip()
    return [l for l in aus if l.text]


def _erstes_wort_teilen(l: Lauf) -> tuple[Lauf, Lauf]:
    m = re.match(r"\S+", l.text)
    ende = m.end() if m else 0
    return Lauf(l.text[:ende], l.stil), Lauf(l.text[ende:], l.stil)


def _gemeinsam(vorher: Inhalt, nachher: list) -> Stil:
    """Der Stil eines Leerzeichens zwischen zwei Zeilen: was beide Seiten teilen (so bleibt ein fetter Satz eine Auszeichnung)."""
    a = next((t.stil for t in reversed(vorher) if isinstance(t, Lauf)), Stil())
    b = next((t.stil for t in nachher if isinstance(t, Lauf)), Stil())
    return Stil(a.fett and b.fett, a.kursiv and b.kursiv, a.festbreit and b.festbreit, False)


def _zusammengefasst(inhalt: Inhalt) -> Inhalt:
    aus: Inhalt = []
    for t in inhalt:
        if isinstance(t, Lauf) and not t.text:
            continue
        if isinstance(t, Lauf) and aus and isinstance(aus[-1], Lauf) and aus[-1].stil == t.stil:
            aus[-1] = Lauf(aus[-1].text + t.text, t.stil)
        else:
            aus.append(Lauf(t.text, t.stil) if isinstance(t, Lauf) else t)
    return aus


# -- Fußnoten -------------------------------------------------------------------------------------------------------------

def _fussnotenzeichen(z: Zeile) -> str | None:
    erste = z.spannen[0]
    if erste.hoch and erste.text.strip():
        return erste.text.strip()
    m = FUSSNOTENZEICHEN.match(z.text)
    return m.group(1) if m else None


def _fussnoten_der_seite(s: Seite, m: Masse) -> list[Zeile]:
    """Die Zeilen am Fuß der Seite in kleinerer Schrift, die mit einem Fußnotenzeichen beginnen (in der unteren Hälfte)."""
    fuss: list[Zeile] = []
    for st in reversed(s.stuecke):
        if not (isinstance(st, Zeile) and st.groesse <= m.grund * KLEIN and st.rechteck.y0 >= s.hoehe * 0.5):
            break
        fuss.insert(0, st)
    while fuss and _fussnotenzeichen(fuss[0]) is None:
        fuss.pop(0)
    return fuss


def _fussnoten(s: Seite, zeilen: list[Zeile]) -> list[tuple[Fussnote, list[Zeile]]]:
    """Die Fußnoten einer Seite mit ihren Zeilen: jede beginnt an einer Zeile mit Zeichen (ihr Text kommt später, wenn die
    Verweise gezählt werden)."""
    teile: list[list[Zeile]] = []
    for z in zeilen:
        if _fussnotenzeichen(z) is not None or not teile:
            teile.append([z])
        else:
            teile[-1].append(z)
    aus = []
    for i, teil in enumerate(teile, 1):
        lage = fitz.Rect(teil[0].rechteck)
        for z in teil[1:]:
            lage |= z.rechteck
        aus.append((Fussnote(s.nr, lage, _fussnotenzeichen(teil[0]) or "", [], anker=f"fn-{s.nr}-{i}"), teil))
    return aus


def _fussnote_lesen(bau: _Bau, f: Fussnote, zeilen: list[Zeile]) -> None:
    """Der Text einer Fußnote ohne ihr Zeichen."""
    erste = zeilen[0].spannen[0]
    f.inhalt = bau.inhalt(zeilen, ab=len(erste.text) if erste.hoch else len(f.zeichen))


# -- Elemente aus Stücken -------------------------------------------------------------------------------------------------

def _zelle(bau: _Bau, z: pdf_lesen.Zelle) -> Zelle:
    seite = z.zeilen[0].seite if z.zeilen else 0
    inhalt = bau.inhalt(z.zeilen) if z.zeilen else []
    return Zelle(seite, fitz.Rect(z.rechteck), ohne_gemeinsames(inhalt) if z.kopf else inhalt, z.kopf, z.spalten)


def _stuecke(bau: _Bau, stuecke: list[pdf_lesen.Stueck], ohne: set[int]) -> None:
    for st in stuecke:
        if id(st) in ohne:
            continue
        if isinstance(st, Zeile):
            bau.zeile(st)
        elif isinstance(st, pdf_lesen.Tabelle):
            bau.einschub(Tabelle(st.seite, fitz.Rect(st.rechteck), [[_zelle(bau, z) for z in r] for r in st.reihen]), wartet=True)
        elif isinstance(st, pdf_lesen.Code):
            bau.einschub(Code(st.seite, fitz.Rect(st.rechteck), [(seite, text) for seite, _, text in st.teile]), wartet=False)
        elif isinstance(st, pdf_lesen.Abbildung):
            bau.einschub(Abbildung(st.seite, fitz.Rect(st.rechteck), st), wartet=not st.formel)
        elif isinstance(st, pdf_lesen.Kasten):
            innen = _Bau(bau.m, bau.rahmen, bau.fussnoten, bau.verweise)
            _stuecke(innen, st.stuecke, set())
            innen.schliessen()
            if innen.elemente and all(isinstance(e, Ueberschrift) for e in innen.elemente):
                for e in innen.elemente:                   # eine Überschrift auf einem farbigen Band: kein Kasten
                    bau.einschub(e, wartet=False)
            else:
                bau.einschub(Kasten(st.seite, fitz.Rect(st.rechteck), _listen(innen.elemente)), wartet=True)


def _listen(elemente: list[Element]) -> list[Element]:
    """Folgende Listenpunkte werden eine Liste; geordnet, wenn ihre Zeichen Nummern oder Buchstaben sind."""
    aus: list[Element] = []
    for e in elemente:
        if isinstance(e, Punkt):
            geordnet = bool(GEORDNET.match(e.zeichen))
            if aus and isinstance(aus[-1], Liste) and aus[-1].geordnet == geordnet:
                aus[-1].punkte.append(e)
            else:
                aus.append(Liste(e.seite, fitz.Rect(e.lage), geordnet, [e]))
        else:
            aus.append(e)
    return aus


def _unterschriften(elemente: list[Element]) -> list[Element]:
    """Ein Absatz, der wie eine Bildunterschrift beginnt, gehört zur Abbildung, Tabelle oder Codestelle gleich davor oder
    danach (dieselbe Seite, noch ohne Unterschrift); die nähere gewinnt."""
    aus = list(elemente)
    i = 0
    while i < len(aus):
        e = aus[i]
        if not (isinstance(e, Absatz) and UNTERSCHRIFT.match(klartext(e.inhalt).strip())):
            i += 1
            continue
        nachbarn = [j for j in (i - 1, i + 1) if 0 <= j < len(aus) and isinstance(aus[j], (Abbildung, Tabelle, Code))
                    and aus[j].unterschrift is None and aus[j].seite == e.seite]
        if not nachbarn:
            i += 1
            continue
        j = min(nachbarn, key=lambda k: min(abs(aus[k].lage.y1 - e.lage.y0), abs(e.lage.y1 - aus[k].lage.y0)))
        e.inhalt = ohne_gemeinsames(e.inhalt)
        aus[j].unterschrift = e
        del aus[i]
        i = max(i - 1, 0)
    return aus


def elemente(seiten: list[Seite], m: Masse) -> list[Element]:
    """Alle Elemente des Dokuments in Lesefolge, Fußnoten hinter dem Absatz, in dem ihre Seite endet."""
    rahmen_je = {s.nr: rahmen(s.nr, [z for z in s.stuecke if isinstance(z, Zeile)], m) for s in seiten}
    fuss_je = {s.nr: _fussnoten(s, zeilen) for s in seiten if (zeilen := _fussnoten_der_seite(s, m))}
    fussnoten = {}
    for nr, noten in fuss_je.items():
        for f, _ in noten:
            fussnoten.setdefault((nr, f.zeichen), f)
    bau = _Bau(m, rahmen_je, fussnoten)
    for s in seiten:
        noten = fuss_je.get(s.nr, [])
        _stuecke(bau, s.stuecke, {id(z) for _, teil in noten for z in teil})
        for f, teil in noten:
            _fussnote_lesen(bau, f, teil)
            bau.einschub(f, wartet=True)
    bau.schliessen()
    return _unterschriften(_listen(bau.elemente))


# -- Stufen und Kapitel ---------------------------------------------------------------------------------------------------

def stufen(elemente: list[Element]) -> None:
    """Die Stufen der Überschriften aus ihren Schriften: die größte zuerst, fett vor mager, höchstens sechs."""
    alle = [e for e in _ueberall(elemente) if isinstance(e, Ueberschrift)]
    folge = sorted({e.schrift for e in alle}, key=lambda s: (-s[0], not s[1]))
    for e in alle:
        e.stufe = min(folge.index(e.schrift) + 1, STUFEN)


def _ueberall(elemente: list[Element]):
    for e in elemente:
        yield e
        if isinstance(e, Kasten):
            yield from _ueberall(e.elemente)


def _gleich(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower()
    return "".join(c for c in t if c.isalnum())


def _passt(ueberschrift: str, titel: str) -> bool:
    a, b = _gleich(ueberschrift), _gleich(titel)
    return len(a) >= 3 and len(b) >= 3 and (a == b or a.endswith(b) or b.endswith(a))


def _anfang(elemente: list[Element], seite: int, titel: str, ab: int) -> int | None:
    """Wo ein Eintrag des Verzeichnisses beginnt: die passende Überschrift ab seiner Seite, sonst das erste Element darauf."""
    for i in range(ab, len(elemente)):
        e = elemente[i]
        if e.seite > seite:
            break
        if e.seite == seite and isinstance(e, Ueberschrift) and _passt(klartext(e.inhalt), titel):
            return i
    return next((i for i in range(ab, len(elemente)) if elemente[i].seite >= seite), None)


def _oberste(stufen: list[int]) -> int | None:
    """Die oberste Stufe, die mehr als einmal vorkommt (eine einzelne darüber ist der Buchtitel), sonst die oberste."""
    n = Counter(stufen)
    return next((s for s in sorted(n) if n[s] > 1), min(n) if n else None)


def kapitel(elemente: list[Element], verzeichnis: list[tuple[int, str, int]], titel: str) -> tuple[list[Kapitel], list[Eintrag]]:
    """Die Kapitel und das Inhaltsverzeichnis; `verzeichnis` ist das des PDF (Stufe, Titel, Dateiseite), `titel` der im PDF
    (für das, was vor dem ersten Kapitel ohne Überschrift steht)."""
    anker = 0
    for e in elemente:
        if isinstance(e, Ueberschrift):
            anker += 1
            e.anker = f"h{anker}"
    verzeichnis = [(stufe, " ".join(t.split()), seite) for stufe, t, seite in verzeichnis if seite >= 1 and t.strip()]
    oben = _oberste([stufe for stufe, _, _ in verzeichnis])
    starts: list[tuple[int, str]] = []
    kapitel_von: dict[int, int] = {}                     # Eintrag des Verzeichnisses -> sein Kapitel (Stelle in starts)
    if oben is not None:
        for nr, (stufe, t, seite) in enumerate(verzeichnis):
            if stufe != oben:
                continue
            i = _anfang(elemente, seite, t, starts[-1][0] if starts else 0)
            if i is not None and (not starts or i > starts[-1][0]):
                starts.append((i, t))
            if starts:
                kapitel_von[nr] = len(starts) - 1
    else:
        starts = _kapitel_aus_ueberschriften(elemente)
    if not starts:
        starts = [(0, _erste_ueberschrift(elemente) or titel or "Text")]
    vorspann = starts[0][0] > 0
    if vorspann:
        starts.insert(0, (0, _erste_ueberschrift(elemente[:starts[0][0]]) or titel or "Start"))
        kapitel_von = {e: k + 1 for e, k in kapitel_von.items()}
    grenzen = [i for i, _ in starts] + [len(elemente)]
    teile = [Kapitel(t, elemente[a:b]) for (a, t), b in zip(starts, grenzen[1:])]
    if oben is None:
        return teile, _eintraege_aus_ueberschriften(teile)
    return teile, _eintraege(teile, verzeichnis, oben, kapitel_von)


def _erste_ueberschrift(elemente: list[Element]) -> str:
    e = next((e for e in elemente if isinstance(e, Ueberschrift)), None)
    return klartext(e.inhalt).strip() if e is not None else ""


def _kapitel_aus_ueberschriften(elemente: list[Element]) -> list[tuple[int, str]]:
    """Die Überschriften der obersten Stufe, die mehr als einmal vorkommt."""
    stufe = _oberste([e.stufe for e in elemente if isinstance(e, Ueberschrift)])
    return [(i, klartext(e.inhalt).strip()) for i, e in enumerate(elemente) if isinstance(e, Ueberschrift) and e.stufe == stufe]


def _eintraege_aus_ueberschriften(teile: list[Kapitel]) -> list[Eintrag]:
    """Ohne Verzeichnis im PDF: je Kapitel ein Eintrag, darunter seine Überschriften eine Stufe tiefer."""
    aus: list[Eintrag] = []
    for nr, k in enumerate(teile):
        aus.append(Eintrag(1, k.titel, nr, ""))
        erste = next((e for e in k.elemente if isinstance(e, Ueberschrift)), None)
        aus += [Eintrag(2, klartext(e.inhalt).strip(), nr, e.anker) for e in k.elemente
                if isinstance(e, Ueberschrift) and erste is not None and e is not erste and e.stufe == erste.stufe + 1]
    return aus


def _eintraege(teile: list[Kapitel], verzeichnis: list[tuple[int, str, int]], oben: int, kapitel_von: dict[int, int]) -> list[Eintrag]:
    """Das Verzeichnis des PDF: je Kapitel ein Eintrag, darunter die tieferen Einträge in ihrer Folge, beim Kapitel des
    obersten Eintrags davor; sie zeigen auf ihre Überschrift, sonst auf die Marke ihrer Seite. Einträge über der obersten
    Stufe (der Buchtitel) fallen weg."""
    unter: dict[int, list[Eintrag]] = {}
    aktuell = 0
    for nr, (stufe, t, seite) in enumerate(verzeichnis):
        if stufe == oben:
            aktuell = kapitel_von.get(nr, aktuell)
            continue
        if stufe < oben:
            continue
        k = teile[aktuell]
        ziel = next((e for e in k.elemente if isinstance(e, Ueberschrift) and e.seite == seite and _passt(klartext(e.inhalt), t)), None)
        unter.setdefault(aktuell, []).append(Eintrag(stufe - oben + 1, t, aktuell, ziel.anker if ziel is not None else f"seite-{seite}"))
    aus: list[Eintrag] = []
    for nr, k in enumerate(teile):
        aus += [Eintrag(1, k.titel, nr, ""), *unter.get(nr, [])]
    return aus


def aufbauen(seiten: list[Seite], verzeichnis: list[tuple[int, str, int]], titel: str = "") -> Buch:
    m = masse(seiten)
    alle = elemente(seiten, m)
    stufen(alle)
    teile, eintraege = kapitel(alle, verzeichnis, titel)
    return Buch(teile, eintraege)
