"""Codestellen in einer PDF-Datei (PyMuPDF), wie die Textansicht direkt aus der Datei gelesen.

1. Codezeile: mindestens 85 % der sichtbaren Zeichen in Festbreitenschrift. Festbreite über den Namen der Schrift (viele
   Bücher markieren JetBrains Mono, DejaVu Sans Mono oder LM Mono nicht als Festbreite), das Merkmal der Schrift und als
   Rückfall gleiche Breite aller Zeichen. Seiten ohne Festbreitenschrift werden gar nicht erst gelesen.
2. Nicht dazu: Kopf- und Fußzeilen, Zeilennummern links neben dem Code (Ziffern in Textschrift oder kleiner gesetzt; sie
   werden als Nummern der Zeile gemerkt), Fußnoten aus lauter Adressen.
3. Block: aufeinanderfolgende Codezeilen gleicher Größe. In derselben Fläche (Kasten, hinterlegte Zeilen) gehören sie
   zusammen, auch über Leerzeilen; ohne Fläche bis zu einem Abstand von gut drei Zeilen, und nie über eine Zeile Fließtext
   hinweg. Fängt die Nummerierung neu an, beginnt ein neues Listing.
4. Rahmen: die kleinste Fläche, die den Block umschließt; ist sie an einer Kante bündig mit der Fläche darum (geteilter
   Kasten), geht der Kasten dort weiter. Titel: Kastentitel auf der oberen Kante, sonst eine Beschriftung darüber
   ("Listing 4.2: ..."); Dateizeile darunter ("Quellcode auf GitHub: ...py").
5. Text: Einrückung aus der Lage jedes Stücks geteilt durch die Zeichenbreite, Leerzeilen aus den Zeilennummern oder dem
   Abstand, Zeilen mit dem Umbruchzeichen an die vorige gehängt.
6. Über Seitenwechsel: endet eine Seite mit einem Codeblock und beginnt die nächste mit einem ohne Titel, gleicher Größe
   und in derselben Spalte, ist es eine Stelle, solange nichts widerspricht (beide Kästen an der Bruchkante geschlossen,
   Nummern, die nicht weiterlaufen). Ketten gehen über beliebig viele Seiten.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import fitz

from backend.app.codestellen.sprache import dateiname

RAND_OBEN, RAND_UNTEN = 0.075, 0.94       # Anteil der Seitenhöhe: darüber Kopfzeile, darunter Fußzeile (wie die Textansicht)
MONO_ANTEIL = 0.85
MONO_NAME = re.compile(r"mono|courier|cursor|consol|menlo|typewriter|inconsolata|source ?code|fira ?code|jetbrains|cmtt|sftt|"
                       r"ectt|lmmono|hack-|nimbusmono", re.I)
FESTBREITE_MERKMAL = 8                    # Schriftmerkmal in PyMuPDF
UMBRUCH = re.compile(r"^\s*,?\s*[\u21aa\u2937\u21b3\u2192]")   # Zeichen am Anfang einer umbrochenen Zeile (",->" aus Formelsatz)
MARKENZEICHEN = set(",\u21aa\u2937\u21b3\u2192")
NACH_MARKE = 0.8                          # Zeichenbreiten: so viel Abstand setzt das Buch selbst hinter das Umbruchzeichen
# Schriften mit Ligaturen: zwei Zeichen werden ein Bild, das Buch nennt dann nur das letzte, davor ein "^" ("//" kommt als
# "^/"). Eindeutig zurückzugewinnen sind die gleichen Paare und Kommentarzeichen; "^=" (==, <=, >=, !=) bleibt stehen.
LIGATURSCHRIFT = re.compile(r"jetbrains|fira ?code|cascadia|iosevka", re.I)
LIGATUREN = [(re.compile(m), e) for m, e in [
    (r"\^\*", "/*"), (r"\^/(?=[A-Za-z][\w.-]*>)", "</"), (r"(?<=/\*)(.*?)\^/", r"\1*/"), (r"^(\s*\*.*?)\^/", r"\1*/"),
    (r"^(\s*)\^/$", r"\1*/"),
]]
GLEICHES_PAAR = re.compile(r"\^+(?=[/?_.:&|])")
ZIFFERN = re.compile(r"^\d{1,4}$")
ADRESSE = re.compile(r"https?://|www\.", re.I)
BESCHRIFTUNG = re.compile(r"^(Listing|Quelltext|Quellcode|Codebeispiel|Beispiel|Code)\s*[\dA-Z.:-]", re.I)
DATEIZEILE = re.compile(r"^(Quellcode|Quelltext|Code online|Ganzes Programm|Begleitmaterial|Datei|Vollständig|Siehe)\b", re.I)
GROESSE_GLEICH = 0.6                      # Punkte: so weit dürfen Schriftgrößen eines Blocks auseinander liegen
NAH = 1.6                                 # Zeilenhöhen: so nah folgen Zeilen ohne Leerzeile
LUECKE_HOECHSTENS = 3.4                   # Zeilenhöhen: größerer Abstand ohne Fläche trennt Blöcke
TITEL_NAEHE = 14.0                        # Punkte: so weit über oder unter der oberen Kante sitzt ein Kastentitel
BESCHRIFTUNG_NAEHE = 30.0                 # Punkte: so weit über dem Block steht eine Beschriftung, darunter eine Dateizeile
FLAECHE_MINDESTENS = (20.0, 6.0)          # Breite und Höhe, ab der eine Zeichnung als Fläche zählt
HUELLE = 70.0                             # Punkte: so viel größer als die Fläche darf eine Hülle des Kastens sein


# -- Schriften -----------------------------------------------------------------------------------------------------------

class Schriften:
    """Welche Schrift Festbreite hat, einmal je Datei bestimmt."""

    def __init__(self) -> None:
        self._mono: dict[str, bool] = {}
        self._breiten: dict[str, list[float]] = {}

    def mono(self, schrift: str, merkmale: int) -> bool | None:
        if schrift not in self._mono:
            if MONO_NAME.search(schrift) or merkmale & FESTBREITE_MERKMAL:
                self._mono[schrift] = True
            else:
                return None                    # noch offen: entscheidet die Breite der Zeichen
        return self._mono[schrift]

    def breite_lernen(self, schrift: str, text: str, breite: float, groesse: float) -> None:
        zeichen = text.strip()
        if schrift in self._mono or len(zeichen) < 6 or groesse <= 0 or zeichen != text:
            return
        self._breiten.setdefault(schrift, []).append(breite / (len(zeichen) * groesse))

    def ist_mono(self, schrift: str, merkmale: int) -> bool:
        """Name oder Merkmal, sonst als Rückfall gleiche Breite je Zeichen über viele Spannen mit verschiedenem Text."""
        bekannt = self.mono(schrift, merkmale)
        if bekannt is None:
            werte = self._breiten.get(schrift, [])
            self._mono[schrift] = bekannt = len(werte) >= 3 and statistics.pstdev(werte) / statistics.mean(werte) < 0.02
        return bekannt


def hat_festbreite(seite: fitz.Page) -> bool:
    """Billig vorab, ohne den Text zu lesen: nennt die Seite eine Schrift, deren Name nach Festbreite klingt? Seiten ohne
    eine solche werden übersprungen; Merkmal und Zeichenbreite prüft erst `Schriften` auf den gelesenen Seiten."""
    return any(MONO_NAME.search(f[3] or "") for f in seite.get_fonts())


# -- Zeilen einer Seite ----------------------------------------------------------------------------------------------------

@dataclass
class Spanne:
    x0: float
    x1: float
    y0: float
    y1: float
    basis: float
    groesse: float
    text: str
    mono: bool
    ligaturen: bool = False


@dataclass
class Zeile:
    spannen: list[Spanne]
    nummer: int | None = None
    nur_nummer: bool = False

    @property
    def basis(self) -> float:
        return statistics.median(s.basis for s in self.spannen)

    @property
    def x0(self) -> float:
        return min(s.x0 for s in self.spannen)

    @property
    def x1(self) -> float:
        return max(s.x1 for s in self.spannen)

    @property
    def y0(self) -> float:
        return min(s.y0 for s in self.spannen)

    @property
    def y1(self) -> float:
        return max(s.y1 for s in self.spannen)

    @property
    def groesse(self) -> float:
        mono = [s.groesse for s in self.spannen if s.mono and s.text.strip()]
        return max(mono or [s.groesse for s in self.spannen])

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spannen)

    @property
    def umbrochen(self) -> bool:
        return bool(UMBRUCH.match(self.text))

    @property
    def mono_anteil(self) -> float:
        spannen = [s for s in self.spannen if not set(s.text.strip()) <= MARKENZEICHEN] if self.umbrochen else self.spannen
        alle = sum(len(s.text.strip()) for s in spannen)
        mono = sum(len(s.text.strip()) for s in spannen if s.mono)
        return mono / alle if alle else 0.0

    @property
    def code(self) -> bool:
        return not self.nur_nummer and self.mono_anteil >= MONO_ANTEIL

    @property
    def rechteck(self) -> fitz.Rect:
        return fitz.Rect(self.x0, self.y0, self.x1, self.y1)


def _spannen(seite: fitz.Page, schriften: Schriften) -> list[Spanne]:
    hoehe = seite.rect.height
    roh = []
    for block in seite.get_text("dict")["blocks"]:
        for zeile in block.get("lines", []):
            for s in zeile["spans"]:
                if not s["text"].strip():
                    continue
                x0, y0, x1, y1 = s["bbox"]
                if y1 < hoehe * RAND_OBEN or y0 > hoehe * RAND_UNTEN:
                    continue
                schriften.breite_lernen(s["font"], s["text"], x1 - x0, s["size"])
                roh.append((s, x0, y0, x1, y1))
    aus = []
    for s, x0, y0, x1, y1 in roh:
        mono = schriften.ist_mono(s["font"], s["flags"])
        aus.append(Spanne(x0, x1, y0, y1, s["origin"][1], s["size"], s["text"], mono, bool(LIGATURSCHRIFT.search(s["font"]))))
    return aus


def _zeilen(spannen: list[Spanne]) -> list[Zeile]:
    """Spannen auf gleicher Grundlinie zu einer Zeile, von links nach rechts; Zeilennummern links davon herausgelöst."""
    zeilen: list[list[Spanne]] = []
    for s in sorted(spannen, key=lambda s: (s.basis, s.x0)):
        if zeilen and abs(s.basis - statistics.median(t.basis for t in zeilen[-1])) <= 0.3 * max(s.groesse, zeilen[-1][0].groesse):
            zeilen[-1].append(s)
        else:
            zeilen.append([s])
    aus = []
    for teile in zeilen:
        teile.sort(key=lambda s: s.x0)
        z = Zeile(teile)
        erste = teile[0]
        if ZIFFERN.match(erste.text.strip()):
            rest = teile[1:]
            if rest and (not erste.mono or erste.groesse < 0.8 * rest[0].groesse) and rest[0].x0 - erste.x1 > 1.5:
                z = Zeile(rest, nummer=int(erste.text.strip()))
            elif not rest and not erste.mono:              # Festbreite: erst die Größe entscheidet (seite_lesen)
                z = Zeile(teile, nummer=int(erste.text.strip()), nur_nummer=True)
        aus.append(z)
    return aus


# -- Flächen ---------------------------------------------------------------------------------------------------------------

@dataclass
class Flaeche:
    rechteck: fitz.Rect
    farbe: tuple | None


def _flaechen(seite: fitz.Page) -> list[Flaeche]:
    """Gefüllte und gerahmte Rechtecke; gleich gefärbte, die bündig aufeinander liegen (hinterlegte Zeilen), als eine."""
    breite, hoehe = FLAECHE_MINDESTENS
    flaechen: list[Flaeche] = []
    for d in seite.get_drawings():
        r = fitz.Rect(d["rect"])
        if r.width >= breite and r.height >= hoehe and (d.get("fill") is not None or any(i[0] == "re" for i in d["items"])):
            flaechen.append(Flaeche(r, tuple(round(c, 3) for c in d["fill"]) if d.get("fill") is not None else None))
    flaechen.sort(key=lambda f: (f.farbe or (), round(f.rechteck.x0), round(f.rechteck.x1), f.rechteck.y0))
    vereint: list[Flaeche] = []
    for f in flaechen:
        v = vereint[-1] if vereint else None
        if (v and v.farbe == f.farbe and f.farbe is not None and abs(v.rechteck.x0 - f.rechteck.x0) < 1
                and abs(v.rechteck.x1 - f.rechteck.x1) < 1 and -1 <= f.rechteck.y0 - v.rechteck.y1 <= 1):
            v.rechteck = v.rechteck | f.rechteck
        else:
            vereint.append(Flaeche(fitz.Rect(f.rechteck), f.farbe))
    # Rahmen aus einzelnen Linien (lstlisting mit frame=single)
    for r in seite.cluster_drawings():
        if r.width >= breite and r.height >= 3 * hoehe and not any(abs(r.x0 - f.rechteck.x0) < 1 and abs(r.y0 - f.rechteck.y0) < 1
                                                                    and abs(r.x1 - f.rechteck.x1) < 1 and abs(r.y1 - f.rechteck.y1) < 1
                                                                    for f in vereint):
            vereint.append(Flaeche(fitz.Rect(r), None))
    return vereint


def _umschliessend(flaechen: list[Flaeche], r: fitz.Rect) -> list[Flaeche]:
    """Alle Flächen, die das Rechteck umschließen, die kleinste zuerst."""
    weit = [f for f in flaechen if (f.rechteck + (-2, -2, 2, 2)).contains(r)]
    return sorted(weit, key=lambda f: f.rechteck.get_area())


# -- Blöcke einer Seite ----------------------------------------------------------------------------------------------------

@dataclass
class Block:
    seite: int
    zeilen: list[Zeile]
    flaeche: Flaeche | None
    nummern: list[int] = field(default_factory=list)          # auch die der Leerzeilen
    titel: str = ""
    kastentitel: bool = False
    datei: str = ""
    kasten: fitz.Rect | None = None                            # der sichtbare Kasten um die Fläche (die äußerste Hülle)
    offen_oben: bool = False
    offen_unten: bool = False
    kanten_bekannt: bool = False                               # Kasten aus mehreren Hüllen: offene Kanten sind erkennbar
    rand: float = 0.0                                          # linke Kante, an der die Einrückung gemessen wird

    @property
    def groesse(self) -> float:
        return statistics.median(z.groesse for z in self.zeilen)

    @property
    def zeilenhoehe(self) -> float:
        schritte = [b.basis - a.basis for a, b in zip(self.zeilen, self.zeilen[1:]) if 0 < b.basis - a.basis <= self.groesse * 2.0]
        return statistics.median(schritte) if schritte else self.groesse * 1.3

    @property
    def rechteck(self) -> fitz.Rect:
        if self.kasten is not None:
            return fitz.Rect(self.kasten)
        r = self.zeilen[0].rechteck
        for z in self.zeilen[1:]:
            r |= z.rechteck
        return r

    @property
    def x0(self) -> float:
        return min(z.x0 for z in self.zeilen)

    @property
    def zeichenbreite(self) -> float:
        werte = [(s.x1 - s.x0) / len(s.text) for z in self.zeilen for s in z.spannen if s.mono and len(s.text) >= 4]
        return statistics.median(werte) if werte else self.groesse * 0.6


def _passt(block: Block, zeile: Zeile, flaeche: Flaeche | None) -> bool:
    if abs(zeile.groesse - block.groesse) > GROESSE_GLEICH and not zeile.umbrochen:
        return False
    letzte = block.zeilen[-1]
    if zeile.nummer is not None and letzte.nummer is not None and zeile.nummer <= letzte.nummer:
        return False                                           # Nummerierung beginnt neu: neues Listing
    if block.flaeche is not None or flaeche is not None:
        return block.flaeche is flaeche
    abstand = (zeile.basis - letzte.basis) / block.zeilenhoehe
    if zeile.nummer is not None and letzte.nummer is not None and zeile.nummer - letzte.nummer <= LUECKE_HOECHSTENS * 2:
        return abstand <= (zeile.nummer - letzte.nummer) * 1.5 + 0.5
    if abstand > LUECKE_HOECHSTENS:
        return False
    return abstand <= NAH or zeile.x0 >= block.x0 - 3 * block.zeichenbreite


def _textgroesse(zeilen: list[Zeile]) -> float:
    groessen = Counter(round(z.groesse, 1) for z in zeilen if not z.code and not z.nur_nummer for _ in range(len(z.text)))
    return groessen.most_common(1)[0][0] if groessen else 10.0


def _textrand(zeilen: list[Zeile], textgroesse: float) -> float:
    raender = Counter(round(z.x0) for z in zeilen if not z.code and abs(z.groesse - textgroesse) < 0.5 and len(z.text) > 40)
    return float(raender.most_common(1)[0][0]) if raender else min((z.x0 for z in zeilen), default=0.0)


@dataclass
class Seite:
    nr: int
    bloecke: list[Block]
    zeilen: list[Zeile]
    textgroesse: float
    textrand: float

    def koerper(self, z: Zeile) -> bool:
        return not z.code and not z.nur_nummer and z.groesse >= 0.85 * self.textgroesse and len(z.text.strip()) > 3

    def am_ende(self, b: Block) -> bool:
        unten = b.rechteck.y1
        return not any(self.koerper(z) and z.y0 > unten - 1 and not _in_flaeche(z, b) for z in self.zeilen)

    def am_anfang(self, b: Block) -> bool:
        oben = b.rechteck.y0
        return not any(self.koerper(z) and z.y1 < oben + 1 and not _in_flaeche(z, b) for z in self.zeilen)


def _in_flaeche(z: Zeile, b: Block) -> bool:
    return b.kasten is not None and (b.kasten + (-2, -TITEL_NAEHE, 2, 2)).intersects(z.rechteck)


def _kasten(b: Block, flaechen: list[Flaeche]) -> None:
    """Die Hüllen um die Fläche des Blocks (Zeilenhintergrund, Innenfläche, Rahmen), solange sie eng anliegen; die
    äußerste ist der Kasten. Liegen zwei Hüllen an einer Kante bündig, ist der Kasten dort offen (geteilt)."""
    if b.flaeche is None:
        return
    innen = b.flaeche.rechteck
    huellen = [f.rechteck for f in _umschliessend(flaechen, innen) if f is b.flaeche or f.farbe is not None
               and f.rechteck.width <= innen.width + HUELLE and f.rechteck.height <= innen.height + HUELLE]
    b.kasten = fitz.Rect(huellen[-1]) if huellen else fitz.Rect(innen)
    paare = list(zip(huellen, huellen[1:]))
    b.kanten_bekannt = bool(paare)
    b.offen_oben = any(abs(a.y0 - c.y0) < 0.4 for a, c in paare)
    b.offen_unten = any(abs(a.y1 - c.y1) < 0.4 for a, c in paare)


def _titel(seite_zeilen: list[Zeile], b: Block) -> None:
    """Kastentitel auf der oberen Kante, sonst Beschriftung darüber; Dateiname aus Titel oder Dateizeile darunter."""
    r = b.rechteck
    erste = b.zeilen[0]
    eigene = {id(z) for z in b.zeilen}
    andere = [z for z in seite_zeilen if not z.code and not z.nur_nummer and z.text.strip() and id(z) not in eigene]
    if b.kasten is not None:                   # Kastentitel: sitzt auf der oberen Kante (darüber und darunter)
        oben = [z for z in andere if z.y0 <= r.y0 + 2 and z.y1 >= r.y0 - 2 and z.y1 <= erste.y0 + 1
                and z.x0 >= r.x0 - 2 and z.x1 <= r.x1 + 2 and len(z.text) <= 120]
        if oben:
            b.titel, b.kastentitel = " ".join(z.text.strip() for z in oben), True
    if not b.titel:
        darueber = [z for z in andere if r.y0 - BESCHRIFTUNG_NAEHE <= z.y1 <= r.y0 + 1]
        if darueber and BESCHRIFTUNG.match(darueber[-1].text.strip()):
            b.titel = darueber[-1].text.strip()
    darunter = [z for z in seite_zeilen if r.y1 - 1 <= z.y0 <= r.y1 + BESCHRIFTUNG_NAEHE and id(z) not in eigene
                and not (z.code and z.groesse >= b.groesse - GROESSE_GLEICH)]
    unten = " ".join(z.text.strip() for z in darunter[:2]) if darunter and DATEIZEILE.match(darunter[0].text.strip()) else ""
    b.datei = dateiname(b.titel) or dateiname(unten)


def seite_lesen(seite: fitz.Page, nr: int, schriften: Schriften) -> Seite:
    zeilen = _zeilen(_spannen(seite, schriften))
    codegroessen = [z.groesse for z in zeilen if z.code]
    if codegroessen:
        typisch = statistics.median(codegroessen)
        for z in zeilen:                     # Nummern in Festbreite, aber kleiner als der Code, sind Zeilennummern
            if z.code and ZIFFERN.match(z.text.strip()) and z.groesse < 0.8 * typisch:
                z.nur_nummer, z.nummer = True, int(z.text.strip())
    textgroesse = _textgroesse(zeilen)
    flaechen = _flaechen(seite) if any(z.code for z in zeilen) else []
    bloecke: list[Block] = []
    offen: Block | None = None
    nummern_ohne_code: list[Zeile] = []
    for z in zeilen:
        if z.nur_nummer:
            nummern_ohne_code.append(z)
            continue
        if not z.code:
            im_kasten = offen is not None and offen.flaeche is not None and (offen.flaeche.rechteck + (-2, -2, 2, 2)).contains(z.rechteck)
            if im_kasten and abs(z.groesse - offen.groesse) <= GROESSE_GLEICH:
                offen.zeilen.append(z)         # im Kasten in Codegröße, aber in Textschrift: ein Kommentar
            elif not im_kasten or z.groesse >= 0.85 * textgroesse:
                offen = None                   # Fließtext trennt
            continue
        umschliessend = _umschliessend(flaechen, z.rechteck)
        flaeche = umschliessend[0] if umschliessend else None
        if offen is not None and _passt(offen, z, flaeche):
            offen.zeilen.append(z)
        else:
            offen = Block(nr, [z], flaeche)
            bloecke.append(offen)
    for b in bloecke:
        b.nummern = _nummern(b, nummern_ohne_code)
    bloecke = [b for b in bloecke if _ist_listing(b)]
    seite_zeilen = sorted(zeilen, key=lambda z: (z.basis, z.x0))
    textrand = _textrand(zeilen, textgroesse)
    for b in bloecke:
        _kasten(b, flaechen)
        _titel(seite_zeilen, b)
        b.rand = b.kasten.x0 if b.kasten is not None else textrand
    return Seite(nr, bloecke, seite_zeilen, textgroesse, textrand)


def _nummern(b: Block, nur_nummern: list[Zeile]) -> list[int]:
    """Die Nummern der Codezeilen und der Leerzeilen dazwischen, davor und danach (dort, wo die Zählung sie erwartet)."""
    eigene = [z.nummer for z in b.zeilen if z.nummer is not None]
    if not eigene:
        return []
    oben, unten, hoehe = b.zeilen[0].basis, b.zeilen[-1].basis, b.zeilenhoehe
    erste, letzte = min(eigene), max(eigene)
    leer = []
    for z in nur_nummern:
        if z.nummer is None or z.x1 > b.x0 + 2:
            continue
        if z.nummer < erste:
            erwartet = oben - (erste - z.nummer) * hoehe
        elif z.nummer > letzte:
            erwartet = unten + (z.nummer - letzte) * hoehe
        else:
            erwartet = min(max(z.basis, oben), unten)
        if abs(z.basis - erwartet) <= 0.5 * hoehe:
            leer.append(z.nummer)
    return sorted({*eigene, *leer})


def _ist_listing(b: Block) -> bool:
    if len(b.zeilen) <= 3 and b.flaeche is None and all(ADRESSE.search(z.text) or "/" in z.text and " " not in z.text.strip()
                                                         for z in b.zeilen):
        return False                                             # Fußnoten mit Adressen
    return len(b.zeilen) >= 2 or b.flaeche is not None or bool(b.nummern)


# -- Über Seitenwechsel ----------------------------------------------------------------------------------------------------

def _fortsetzung(vorige: Seite, a: Block, naechste: Seite, b: Block) -> bool:
    if b.titel or abs(a.groesse - b.groesse) > GROESSE_GLEICH:
        return False
    if not (vorige.am_ende(a) and naechste.am_anfang(b)):
        return False
    if abs((a.x0 - a.rand) - (b.x0 - b.rand)) > 40:
        return False
    if (a.flaeche is None) != (b.flaeche is None):
        return False
    if a.kasten is not None and b.kasten is not None:
        if abs(a.kasten.width - b.kasten.width) > 2:
            return False
        if a.kanten_bekannt and b.kanten_bekannt and not a.offen_unten and not b.offen_oben:
            return False                                         # zwei geschlossene Kästen
    if a.nummern and b.nummern and b.nummern[0] != a.nummern[-1] + 1:
        return False
    return True


def ketten(seiten: list[Seite]) -> list[list[Block]]:
    """Alle Blöcke in Lesereihenfolge, fortgesetzte zu Ketten verbunden."""
    aus: list[list[Block]] = []
    vorige: Seite | None = None
    for s in seiten:
        for i, b in enumerate(s.bloecke):
            letzte = aus[-1][-1] if aus else None
            if (i == 0 and vorige is not None and letzte is not None and letzte.seite == vorige.nr and s.nr == vorige.nr + 1
                    and letzte is max(vorige.bloecke, key=lambda x: x.rechteck.y1) and _fortsetzung(vorige, letzte, s, b)):
                aus[-1].append(b)
            else:
                aus.append([b])
        vorige = s
    return aus


# -- Text ------------------------------------------------------------------------------------------------------------------

def _zeilentext(z: Zeile, bezug: float, breite: float) -> str:
    """Jedes Stück an seine Spalte: so bleiben Einrückung und Abstände vor Kommentaren erhalten."""
    text, ende = "", None
    for s in z.spannen:
        spalte = max(0, round((s.x0 - bezug) / breite))
        if spalte > len(text):
            text += " " * (spalte - len(text))
        elif text and not text.endswith(" ") and ende is not None and s.x0 - ende > breite * 0.5:
            text += " "
        text += s.text
        ende = s.x1
    return text.rstrip()


def ligaturen(text: str) -> str:
    """Ligaturen einer Zeile zurück in ihre Zeichen, wo es eindeutig ist (siehe LIGATUREN)."""
    for muster, ersatz in LIGATUREN:
        text = muster.sub(ersatz, text)
    return GLEICHES_PAAR.sub(lambda m: m.string[m.end()] * len(m.group(0)), text)


def _zeile_lesen(z: Zeile, text: str) -> str:
    return ligaturen(text) if "^" in text and any(s.ligaturen for s in z.spannen) else text


def _umbruch_text(z: Zeile, breite: float) -> str:
    """Text einer umbrochenen Zeile ohne das Umbruchzeichen; ein Leerzeichen, das am Umbruch stand, bleibt."""
    marke = UMBRUCH.match(z.text)
    assert marke is not None
    gelesen, ende, rest = 0, z.spannen[0].x0, []
    for s in z.spannen:
        if gelesen + len(s.text) <= marke.end():
            gelesen += len(s.text)
            ende = s.x1
            continue
        if gelesen < marke.end():                          # Zeichen und Text in einer Spanne
            k, je = marke.end() - gelesen, (s.x1 - s.x0) / len(s.text)
            ende = s.x0 + k * je
            s = Spanne(s.x0 + k * je, s.x1, s.y0, s.y1, s.basis, s.groesse, s.text[k:], s.mono, s.ligaturen)
            gelesen = marke.end()
        rest.append(s)
    if not "".join(s.text for s in rest).strip():
        return ""
    erste = rest[0]
    vorne = len(erste.text) - len(erste.text.lstrip())
    beginn = erste.x0 + vorne * (erste.x1 - erste.x0) / len(erste.text)
    rest[0] = Spanne(beginn, erste.x1, erste.y0, erste.y1, erste.basis, erste.groesse, erste.text.lstrip(), erste.mono,
                     erste.ligaturen)
    leer = max(0, round((beginn - ende) / breite - NACH_MARKE))
    return " " * leer + _zeile_lesen(z, _zeilentext(Zeile(rest), beginn, breite))


def text_der_kette(kette: list[Block]) -> tuple[str, int | None]:
    """Der Code einer Kette und die erste gedruckte Zeilennummer. Ein Leerzeichen genau an der Bruchstelle einer
    umbrochenen Zeile ist nicht zu sehen und fehlt dann (gemessen: seltener als ein falsch eingefügtes)."""
    erste = kette[0]
    breite = erste.zeichenbreite
    abstand = min(b.x0 - b.rand for b in kette)       # Spalte 0 der ganzen Kette, gemessen vom Rand ihrer Seite
    zeilen: list[str] = []
    vorige: Zeile | None = None
    for b in kette:
        bezug = b.rand + abstand
        if vorige is not None and vorige.nummer is None:
            vorige = None                                 # über den Seitenwechsel zählen nur Nummern
        for z in b.zeilen:
            if z.umbrochen and zeilen:
                weiter = _umbruch_text(z, breite)                   # umbrochen, mit Zeichen
                getrennt = zeilen[-1][-1:].isalnum() and weiter[:1].isalnum()   # mitten in einem Namen bricht das Buch nie
                zeilen[-1] += (" " if getrennt else "") + weiter
                vorige = z
                continue
            inhalt = _zeile_lesen(z, _zeilentext(z, bezug, breite))
            if (z.nummer is None and b.nummern and vorige is not None and vorige.nummer is not None and vorige in b.zeilen
                    and z.basis - vorige.basis <= NAH * b.zeilenhoehe and zeilen):
                zeilen[-1] += " " + inhalt.lstrip()                 # umbrochen an einem Leerzeichen, ohne eigene Nummer
                continue
            if vorige is not None:
                if z.nummer is not None and vorige.nummer is not None:
                    leer = z.nummer - vorige.nummer - 1
                elif vorige in b.zeilen:
                    leer = max(0, round((z.basis - vorige.basis) / b.zeilenhoehe) - 1)
                else:
                    leer = 0
                zeilen.extend([""] * max(0, min(leer, 20)))
            zeilen.append(inhalt)
            vorige = z
    return "\n".join(zeilen), (erste.nummern[0] if erste.nummern else None)


# -- Datei -----------------------------------------------------------------------------------------------------------------

def seiten_lesen(pfad: Path) -> Iterator[Seite]:
    schriften = Schriften()
    with fitz.open(str(pfad)) as doc:
        for i, seite in enumerate(doc):
            if hat_festbreite(seite):
                yield seite_lesen(seite, i + 1, schriften)
