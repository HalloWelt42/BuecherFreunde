"""Zeilen und Absätze einer Seite (BF-103): aus der Textschicht die Zeilen, wie sie gedruckt stehen, und daraus die Absätze.

Die Regeln stehen in der Beschreibung des Pakets (__init__.py); hier sind sie umgesetzt, mit ihren Schwellen als Namen.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass

import fitz

from backend.app.codestellen.pdf import MONO_ANTEIL, festbreit_nach_name
from backend.app.services.pdfseite import TEXTART, fehlzeichen_der_seite, ligaturen_aufloesen

RAND_OBEN = 0.075               # Anteil der Seitenhöhe: darüber Kopfzeile
RAND_UNTEN = 0.94               # darunter Fußzeile
UEBERSCHRIFT_FAKTOR = 1.12      # so viel größer als der Fließtext gilt als Überschrift (wie die Übersetzung)
UEBERSCHRIFT_ZEILEN = 3         # so viele Zeilen hat eine Überschrift höchstens
SATZ_AB = 6                     # Wörter: so viele in einem Absatz, der mit einem Satzzeichen endet, sind ein Satz
FORMEL_HOECHSTENS = 160         # Zeichen; längere Blöcke mit Formelzeichen sind Text mit Formeln darin
FORMEL_MITTE = 0.12             # Anteil der Seitenbreite: so nah an der Mitte steht eine abgesetzte Formel
FORMEL_BREITE = 0.7             # Anteil der Seitenbreite: so breit ist eine abgesetzte Formel höchstens

GLEICHE_GRUNDLINIE = 0.3        # Schriftgrößen: so nah liegen die Grundlinien der Stücke einer Zeile
LUECKE_LEERZEICHEN = 0.15       # Schriftgrößen: ein so breiter Abstand ohne Leerzeichen wird eines
ENG = 1.35                      # Zeilenabstände: so dicht folgt die nächste Zeile eines Absatzes
ZEILENABSTAND = (0.9, 2.2)      # Schriftgrößen: in diesem Bereich liegt der Abstand zweier Zeilen eines Absatzes
ZEILENABSTAND_VORGABE = 1.25    # Schriftgrößen, wenn die Seite keinen Abstand zeigt
EINZUG = 0.8                    # Schriftgrößen: ab hier beginnt eine Zeile eingerückt (ein neuer Absatz)
HAENGEND = (0.4, 4.0)           # Schriftgrößen: so weit stehen die Folgezeilen eines Listenpunkts eingerückt
BUENDIG = 0.5                   # Schriftgrößen: so genau steht eine Folgezeile bündig unter dem Listenpunkt
WORTLUFT = 0.5                  # Schriftgrößen: Platz für den Wortabstand vor dem ersten Wort der nächsten Zeile
KNAPP = 2.0                     # Schriftgrößen: so viel Platz mehr gilt noch als voll, wenn die Zeile mitten im Satz endet
KLEIN = 0.9                     # so viel kleiner als der Fließtext: Fußnoten, Unterschriften
OFFENE_ABSAETZE = 12            # so viele der jüngsten Absätze kommen für die nächste Zeile in Frage (Spalten)

WEICH = chr(0xAD)               # weiches Trennzeichen
TRENNSTRICHE = "-" + chr(0x2010)
SCHLIESSEND = "\"'" + "".join(map(chr, (0xBB, 0xAB, 0x201C, 0x201D, 0x2019, 0x203A, 0x2039))) + ")]"
SATZENDE = re.compile("[.!?:;" + chr(0x2026) + "][" + re.escape(SCHLIESSEND) + "]*$")
AUFZAEHLUNG = "".join(map(chr, (0x2022, 0x25E6, 0x25AA, 0x25AB, 0x2023, 0x2043, 0x25CF, 0x25CB, 0x25A0, 0x25A1, 0x2013,
                                0x2014, 0xB7))) + "*-"
LISTENZEICHEN = re.compile("^([" + re.escape(AUFZAEHLUNG) + r"]|\(?\d{1,3}[.)]|\(?[a-z]\))(?=\s)")
WORT = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")
STEUERZEICHEN = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")
HOCHGESTELLT = 1                # Merkmal einer Textspanne in PyMuPDF
# Hochzahlen: 0-9 sowie Plus, Minus (beide Formen) und n, als Codepunkte (keine Sonderzeichen im Quelltext)
HOCHZAHLEN = str.maketrans("0123456789+-" + chr(0x2212) + "n",
                           "".join(map(chr, (0x2070, 0xB9, 0xB2, 0xB3, 0x2074, 0x2075, 0x2076, 0x2077, 0x2078, 0x2079,
                                             0x207A, 0x207B, 0x207B, 0x207F))))
HOCHZAHL_FAEHIG = re.compile(r"^[0-9+\-" + chr(0x2212) + r"n]+$")


@dataclass
class Zeile:
    """Eine Zeile der Seite, wie sie gedruckt steht: der Text mit seinem Leerraum (für Code), die sichtbare Lage."""
    rechteck: fitz.Rect
    text: str
    groesse: float
    basis: float
    festbreit: float            # Anteil der sichtbaren Zeichen in Festbreitenschrift
    zeichenbreite: float        # Breite eines Zeichens in Festbreite, sonst eine halbe Schriftgröße (für die Einrückung)
    formel: bool = False

    @property
    def mitte(self) -> fitz.Point:
        return fitz.Point((self.rechteck.x0 + self.rechteck.x1) / 2, (self.rechteck.y0 + self.rechteck.y1) / 2)


@dataclass(eq=False)
class Block:
    """Ein Absatz aus Zeilen (oder eine einzelne Zeile, eine Codezeile, ein Formelteil)."""
    zeilen: list[Zeile]
    listenpunkt: bool = False
    text: str = ""

    @property
    def rechteck(self) -> fitz.Rect:
        r = fitz.Rect(self.zeilen[0].rechteck)
        for z in self.zeilen[1:]:
            r |= z.rechteck
        return r

    @property
    def groesse(self) -> float:
        return max(z.groesse for z in self.zeilen)

    @property
    def festbreit(self) -> float:
        zeichen = sum(len(z.text.strip()) for z in self.zeilen)
        return sum(len(z.text.strip()) * z.festbreit for z in self.zeilen) / zeichen if zeichen else 0.0


@dataclass
class Masse:
    """Was eine Seite über ihren Satz verrät: Größe des Fließtexts, üblicher Zeilenabstand je Größe, wie sie ihre Wörter
    schreibt (für die Trennung) und ihre Zeilen (für den rechten Rand einer Spalte)."""
    grund: float
    abstand: dict[float, float]
    woerter: Counter[str]
    zeilen: list[Zeile]

    def zeilenabstand(self, groesse: float) -> float:
        return self.abstand.get(gerundet(groesse), groesse * ZEILENABSTAND_VORGABE)

    def schrift(self, z: Zeile) -> tuple:
        """Woran man Zeilen eines Absatzes erkennt: Überschrift (mit Größe), Festbreite, klein oder Text."""
        if self.grund and z.groesse >= self.grund * UEBERSCHRIFT_FAKTOR:
            return ("kopf", gerundet(z.groesse))
        if z.festbreit >= MONO_ANTEIL:
            return ("fest",)
        if self.grund and z.groesse <= self.grund * KLEIN:
            return ("klein",)
        return ("text",)

    def rechts(self, z: Zeile) -> float:
        """Rechter Rand der Spalte einer Zeile: so weit reichen die Zeilen derselben Schrift, die sie waagerecht überdecken."""
        art = self.schrift(z)
        return max((x.rechteck.x1 for x in self.zeilen if self.schrift(x) == art and ueberdecken_x(x.rechteck, z.rechteck)),
                   default=z.rechteck.x1)


# -- Text ----------------------------------------------------------------------------------------------------------------

def satz(text: str) -> bool:
    """Ein Satz: genug Wörter und ein Satzzeichen am Ende."""
    return len(WORT.findall(text)) >= SATZ_AB and bool(SATZENDE.search(text.rstrip()))


def _trennung_aufloesen(vorn: str, weiter: str, woerter: Counter[str] | None) -> bool:
    """Ist der Strich am Ende von `vorn` eine Trennung (fällt weg)? Nur vor kleinem Anfang, nach Buchstaben, die keine
    Abkürzung sind, und wenn die Seite das Wort nicht sonst mit Strich schreibt."""
    stueck = re.search(r"([^\W\d_]+)$", vorn[:-1])
    anfang = WORT.match(weiter)
    if stueck is None or anfang is None or not weiter[:1].islower() or stueck.group(1)[-1].isupper():
        return False
    wort_vorn, wort_hinten = stueck.group(1).lower(), anfang.group(0).split("-")[0].lower()
    return not woerter or woerter[f"{wort_vorn}-{wort_hinten}"] <= woerter[f"{wort_vorn}{wort_hinten}"]


def verbinde(zeilen: list[str], woerter: Counter[str] | None = None) -> str:
    """Zeilen eines Absatzes zu einem Text, Trennungen am Zeilenende aufgelöst; `woerter`: wie die Seite ihre Wörter
    schreibt."""
    laufend = ""
    for roh in zeilen:
        zeile = " ".join(STEUERZEICHEN.sub("", roh).split())
        if not zeile:
            continue
        if not laufend:
            laufend = zeile
        elif laufend.endswith(WEICH):
            laufend = laufend[:-1] + zeile
        elif laufend[-1] in TRENNSTRICHE and len(laufend) > 1 and not laufend[-2].isspace():
            laufend = (laufend[:-1] if _trennung_aufloesen(laufend, zeile, woerter) else laufend) + zeile
        else:
            laufend = f"{laufend} {zeile}"
    return laufend.replace(WEICH, "")


# -- Zeilen der Seite ----------------------------------------------------------------------------------------------------

def gerundet(groesse: float) -> float:
    return round(groesse * 2) / 2


def ueberdecken_x(a: fitz.Rect, b: fitz.Rect) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1


def formelzeichen(text: str) -> bool:
    """Mathematische Schriftzeichen (kursive Formelbuchstaben und Operatoren), wie sie Formelsatz erzeugt."""
    return any(0x1D400 <= ord(c) <= 0x1D7FF or 0x2200 <= ord(c) <= 0x22FF for c in text)


def abgesetzte_formel(text: str, r: fitz.Rect, breite: float) -> bool:
    """Eine abgesetzte Formel: kurz, mit Formelzeichen, mittig und schmaler als die Seite."""
    return (formelzeichen(text) and len(text) <= FORMEL_HOECHSTENS
            and abs((r.x0 + r.x1) / 2 - breite / 2) <= breite * FORMEL_MITTE and r.width < breite * FORMEL_BREITE)


def _spanne(spanne: dict) -> str:
    text = spanne["text"]
    if spanne["flags"] & HOCHGESTELLT and HOCHZAHL_FAEHIG.match(text.strip()):
        return text.strip().translate(HOCHZAHLEN)
    return text


def _zeilentext(spannen: list[dict]) -> str:
    """Spannen einer Zeile verbinden; ein sichtbarer Abstand ohne Leerzeichen (nach Formelbuchstaben) wird eines."""
    text, voriges_ende = "", None
    for spanne in spannen:
        stueck = _spanne(spanne)
        luecke = voriges_ende is not None and spanne["bbox"][0] - voriges_ende > spanne["size"] * LUECKE_LEERZEICHEN
        if luecke and text and not text[-1].isspace() and stueck and not stueck[0].isspace():
            text += " "
        text += stueck
        voriges_ende = spanne["bbox"][2]
    return text


def _sichtbar_ab(spanne: dict) -> float:
    """Wo das erste sichtbare Zeichen einer Spanne beginnt (der Leerraum davor zählt nicht)."""
    text = spanne["text"]
    vorn = len(text) - len(text.lstrip())
    x0, _, x1, _ = spanne["bbox"]
    return x0 + vorn * (x1 - x0) / len(text) if text else x0


def _zeile_aus(stuecke: list[dict], breite: float, fehlzeichen: frozenset[str]) -> Zeile:
    """Die Stücke einer Zeile (Zeilen der Textschicht auf einer Grundlinie, von links nach rechts) als eine Zeile."""
    spannen = [s for z in stuecke for s in z["spans"] if s["text"]]
    sichtbar = [s for s in spannen if s["text"].strip()]
    rechteck = fitz.Rect(_sichtbar_ab(sichtbar[0]), sichtbar[0]["bbox"][1], sichtbar[0]["bbox"][2], sichtbar[0]["bbox"][3])
    for s in sichtbar[1:]:
        rechteck |= fitz.Rect(s["bbox"])
    text = ligaturen_aufloesen(STEUERZEICHEN.sub("", _zeilentext(spannen)), fehlzeichen)
    zeichen = sum(len(s["text"].strip()) for s in sichtbar)
    fest = [s for s in sichtbar if festbreit_nach_name(s.get("font", ""), s.get("flags", 0))]
    groesse = max(s["size"] for s in sichtbar)
    breiten = [(s["bbox"][2] - s["bbox"][0]) / len(s["text"]) for s in fest if len(s["text"]) >= 2]
    grundlinien = [s["origin"][1] for s in sichtbar if not s["flags"] & HOCHGESTELLT] or [sichtbar[0]["origin"][1]]
    return Zeile(rechteck, text, groesse, statistics.median(grundlinien),
                 sum(len(s["text"].strip()) for s in fest) / zeichen if zeichen else 0.0,
                 statistics.median(breiten) if breiten else groesse * 0.5,
                 any(abgesetzte_formel(_zeilentext(z["spans"]), fitz.Rect(z["bbox"]), breite) for z in stuecke))


def zeilen_der_seite(seite: fitz.Page) -> list[Zeile]:
    """Die Zeilen der Seite ohne Kopf- und Fußzeilen; Stücke eines Blocks auf derselben Grundlinie sind eine Zeile."""
    hoehe, breite = seite.rect.height, seite.rect.width
    bloecke = seite.get_text("dict", flags=TEXTART, sort=True)["blocks"]
    fehlzeichen = fehlzeichen_der_seite(seite)
    aus = []
    for block in bloecke:
        if block.get("type") != 0:
            continue
        reihen: list[tuple[float, list[dict]]] = []           # Grundlinie und die Stücke darauf
        for zeile in block["lines"]:
            spannen = [s for s in zeile["spans"] if s["text"].strip()]
            if not spannen:
                continue
            basis, groesse = spannen[0]["origin"][1], max(s["size"] for s in spannen)
            reihe = next((r for b, r in reihen if abs(b - basis) <= GLEICHE_GRUNDLINIE * groesse), None)
            if reihe is None:
                reihen.append((basis, [zeile]))
            else:
                reihe.append(zeile)
        for _, reihe in reihen:
            reihe.sort(key=lambda z: z["bbox"][0])
            z = _zeile_aus(reihe, breite, fehlzeichen)
            if z.rechteck.y1 > hoehe * RAND_OBEN and z.rechteck.y0 < hoehe * RAND_UNTEN and z.text.strip():
                aus.append(z)
    return aus


def masse(zeilen: list[Zeile]) -> Masse:
    """Die Maße der Seite aus ihren Zeilen (siehe Masse)."""
    groessen: Counter[float] = Counter()
    for z in zeilen:
        if z.festbreit < MONO_ANTEIL:
            groessen[gerundet(z.groesse)] += len(z.text.strip())
    grund = groessen.most_common(1)[0][0] if groessen else (gerundet(zeilen[0].groesse) if zeilen else 0.0)
    schritte: dict[float, Counter[float]] = {}
    geordnet = sorted(zeilen, key=lambda z: z.basis)
    for a, b in zip(geordnet, geordnet[1:]):
        d = b.basis - a.basis
        if (gerundet(a.groesse) == gerundet(b.groesse) and ueberdecken_x(a.rechteck, b.rechteck)
                and ZEILENABSTAND[0] * a.groesse < d < ZEILENABSTAND[1] * a.groesse):
            schritte.setdefault(gerundet(a.groesse), Counter())[round(d, 1)] += 1
    woerter: Counter[str] = Counter()
    for z in zeilen:
        teile = z.text.split()
        for w in teile[:-1] if z.text.rstrip()[-1:] in TRENNSTRICHE else teile:
            woerter.update(m.group(0).lower() for m in WORT.finditer(w))
    return Masse(grund, {g: c.most_common(1)[0][0] for g, c in schritte.items()}, woerter, zeilen)


# -- Absätze -------------------------------------------------------------------------------------------------------------

def _getrennt(a: Zeile) -> bool:
    """Endet die Zeile mit einer Trennung (weiches Trennzeichen oder Strich gleich nach einem Buchstaben)?"""
    t = a.text.rstrip()
    return t.endswith(WEICH) or (len(t) > 1 and t[-1] in TRENNSTRICHE and t[-2].isalpha())


def _mitten_im_satz(a: Zeile) -> bool:
    return not SATZENDE.search(a.text.rstrip())


def _erstes_wort(z: Zeile) -> float:
    """Ungefähre Breite des ersten Worts einer Zeile."""
    text = z.text.strip()
    wort = text.split()[0] if text else ""
    return z.rechteck.width * len(wort) / max(len(text), 1)


def _voll(a: Zeile, b: Zeile, m: Masse) -> bool:
    """War a voll? Ihr fehlte der Platz für das erste Wort von b. Der rechte Rand ist nur geschätzt (aus den Zeilen der
    Spalte), darum gilt eine Zeile mitten im Satz auch dann als voll, wenn knapp mehr Platz blieb."""
    platz = m.rechts(a) - a.rechteck.x1 - _erstes_wort(b)
    if platz < WORTLUFT * a.groesse:
        return True
    return platz < KNAPP * a.groesse and _mitten_im_satz(a)


def _darunter(a: Zeile, b: Zeile, m: Masse) -> bool:
    return ueberdecken_x(a.rechteck, b.rechteck) and 0 < b.basis - a.basis <= m.zeilenabstand(a.groesse) * ENG


def _im_punkt(o: Block, a: Zeile, b: Zeile, m: Masse) -> bool:
    """Gehört b zum Listenpunkt? Hängend eingerückt gegenüber seiner ersten Zeile, oder bündig nach einer vollen Zeile."""
    em = b.groesse
    versatz = b.rechteck.x0 - o.zeilen[0].rechteck.x0
    haengend = HAENGEND[0] * em < versatz <= HAENGEND[1] * em
    return haengend or (abs(versatz) <= BUENDIG * em and (_voll(a, b, m) or _getrennt(a)))


def _listenanfang(a: Zeile, b: Zeile, m: Masse) -> bool:
    """Beginnt mit b ein Listenpunkt? Ein Aufzählungszeichen immer; eine Nummer ("3.") nur, wenn a nicht mitten im Satz voll
    war (sonst ist es eher ein Datum oder eine Zahl im Satz)."""
    zeichen = LISTENZEICHEN.match(b.text.strip())
    if zeichen is None:
        return False
    nummer = any(c.isdigit() for c in zeichen.group(1))
    return not nummer or not _voll(a, b, m) or not _mitten_im_satz(a)


def _codeblock(o: Block, m: Masse) -> bool:
    return all(m.schrift(z)[0] == "fest" for z in o.zeilen)


def _gleiche_schrift(o: Block, a: Zeile, b: Zeile, m: Masse) -> bool:
    """Passt die Schrift von b zum Absatz? Gleich, oder Text und Festbreite im Wechsel mitten im Satz: Code im Fließtext,
    der an den Zeilenanfang umbrochen ist ("... die Variablen vorname und" + "nachname:")."""
    if m.schrift(a) == m.schrift(b):
        return True
    gemischt = {m.schrift(a)[0], m.schrift(b)[0]} == {"text", "fest"}
    return gemischt and not _codeblock(o, m) and _mitten_im_satz(a)


def _weiter(o: Block, b: Zeile, m: Masse) -> bool:
    """Setzt die Zeile b den Absatz o fort?"""
    a = o.zeilen[-1]
    if a.formel or b.formel or not _gleiche_schrift(o, a, b, m) or not _darunter(a, b, m):
        return False
    if _codeblock(o, m):
        return m.schrift(b)[0] == "fest"               # Codezeilen: Zeile für Zeile, sie bleiben Zeilen
    if m.schrift(a)[0] == "kopf":
        return len(o.zeilen) < UEBERSCHRIFT_ZEILEN
    if _listenanfang(a, b, m):
        return False
    if o.listenpunkt:
        return _im_punkt(o, a, b, m)
    if _getrennt(a):
        return True
    if b.rechteck.x0 > a.rechteck.x0 + EINZUG * b.groesse:             # eingerückt: ein neuer Absatz, außer hängend
        return len(o.zeilen) == 1 and _voll(a, b, m) and _mitten_im_satz(a)
    return _voll(a, b, m)


def absaetze(zeilen: list[Zeile], m: Masse) -> list[Block]:
    """Die Zeilen der Seite zu Absätzen, von oben nach unten; jede Zeile setzt den jüngsten passenden Absatz fort."""
    bloecke: list[Block] = []
    for z in sorted(zeilen, key=lambda z: (z.basis, z.rechteck.x0)):
        ziel = next((o for o in reversed(bloecke[-OFFENE_ABSAETZE:]) if _weiter(o, z, m)), None)
        if ziel is None:
            punkt = m.schrift(z)[0] in ("text", "klein") and bool(LISTENZEICHEN.match(z.text.strip()))
            bloecke.append(Block([z], listenpunkt=punkt))
        else:
            ziel.zeilen.append(z)
    for o in bloecke:
        o.text = verbinde([z.text for z in o.zeilen], m.woerter)
    return [o for o in bloecke if o.text]
