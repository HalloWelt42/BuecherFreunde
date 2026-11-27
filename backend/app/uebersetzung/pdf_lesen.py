"""Ein PDF Seite für Seite lesen (BF-71): Zeilen mit ihren Schriften, Abbildungen, Kästen, Tabellen und Code, ohne Kopf- und
Fußzeilen, je Seite in Lesefolge, auch bei mehreren Spalten. Alles ohne Datenbank und Netz, nur aus der Datei.

- Zeilen: aus der Textschicht (PyMuPDF), Ligaturen aufgelöst, auch falsch abgebildete (services/pdfseite.py). Eine Zeile,
  die über eine breite Lücke reicht (Spalten, Zellen), wird dort geteilt.
- Code: die Erkennung der Codestellen (codestellen/pdf.py: Festbreite, Kasten, Titel, Fortsetzung über Seiten) wie die
  Textansicht; Zeilen darin und Zeilennummern daneben gehören nicht mehr zum Text.
- Tabellen: aus den Linien der Seite (PyMuPDF find_tables), ab zwei Zeilen und zwei Spalten, mit Text in mindestens der
  Hälfte der Zellen; jede Zelle mit ihren Zeilen.
- Abbildungen: Zeichnungen und Bilder, nahe Teile zusammen (wie in der Textansicht). Text darin gehört zum Bild, ebenso
  Beschriftungen gleich daneben: kurz, ohne Satz, nicht größer als der Text der Seite (Achsen, Werte); Sätze und
  Überschriften darüber und darunter bleiben Text. Eine Fläche mit Text ist ein
  Kasten mit eigener Lesefolge (seine Bilder darin), wenn sie längeren Text umschließt, oder wenn ihre Zeichnungen nur Rahmen
  sind (Hintergrund, Rand, Linien über die ganze Breite) und sie Text in Sätzen oder kein Bild trägt: so bleibt Text auf einem
  farbigen Band, in einem Rahmen oder neben einem Symbol Text. Ein Bild über fast die ganze Seite ist Hintergrund (Scan mit
  Textschicht), eine dünne Linie keine Abbildung. Abgesetzte Formeln (mittig, mit mathematischen Zeichen) werden als Bild
  gezeigt.
- Kopf- und Fußzeilen: Zeilen im oberen und unteren Rand, die auf einer anderen Seite an derselben Stelle wiederkehren
  (Ziffern zählen gleich, "Seite 3" ist wie "Seite 4"), und Seitenzahlen dort fallen weg.
- Lesefolge nach Breuel: oben vor unten, wo sich zwei Stücke waagerecht überdecken; links vor rechts, wenn nichts zwischen
  ihnen über beide reicht. So liest sich eine Spalte zu Ende, bevor die nächste beginnt, und was über beide Spalten reicht,
  steht davor oder danach."""

from __future__ import annotations

import heapq
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import cached_property

import fitz

from backend.app.codestellen import pdf as codestellen_pdf
from backend.app.services.pdfseite import TEXTART, fehlzeichen_der_seite, gerade, ligaturen_aufloesen
from backend.app.services.textansicht import lesbar

RAND = 0.12                     # Anteil der Seitenhöhe oben und unten, in dem Kopf- und Fußzeilen stehen
WIEDERKEHR_NAEHE = 4.0          # Punkte: so genau steht eine Kopfzeile auf jeder Seite an derselben Stelle
LUECKE = 1.6                    # Schriftgrößen: eine so breite Lücke ohne Zeichen teilt eine Zeile
MINDESTGROESSE = 24.0           # kleinere Zeichnungen und Bilder (Linien, Zierrat, Aufzählungszeichen) zählen nicht
DUENN = 4.0                     # so schmal oder flach ist eine Linie, keine Abbildung
NAEHE = 12.0                    # Punkte: so nah beieinander gehören Teile zu einer Abbildung
HINTERGRUND = 0.85              # ein Bild oder Kasten über so viel der Seite ist Hintergrund
KASTEN_TEXT_AB = 120            # Zeichen in einer Zeichnung: ab hier ist sie ein Kasten um Text
SATZ_AB = 6                     # Wörter: so viele in einer Zeile sind ein Satz, keine Beschriftung
RAHMEN_ANTEIL = 0.8             # so viel einer Fläche deckt eine Zeichnung, die ihr Hintergrund oder Rand ist
BESCHRIFTUNG_NAEHE = 40.0       # Punkte links oder rechts neben einer Abbildung
BESCHRIFTUNG_NAEHE_Y = 22.0     # Punkte über oder unter einer Abbildung (wie in der Textansicht)
BESCHRIFTUNG_HOECHSTENS = 40    # Zeichen einer Beschriftung daneben
CODE_RAND = 4.0                 # Punkte um eine Codestelle, die noch zu ihr gehören (wie die Textansicht)
CODE_NUMMERN = 32.0             # Punkte links einer Codestelle, in denen ihre Zeilennummern stehen
TABELLE_GEFUELLT = 0.5          # so viele Zellen einer Tabelle tragen Text
FORMEL_MITTE = 0.12             # Anteil der Seitenbreite: so nah an der Mitte steht eine abgesetzte Formel
FORMEL_HOECHSTENS = 160
MONO_ANTEIL = codestellen_pdf.MONO_ANTEIL
FETT_NAME = re.compile(r"bold|black|heavy|semibold|demibold|demi\b", re.I)
KURSIV_NAME = re.compile(r"italic|oblique|kursiv", re.I)
FETT_MERKMAL, KURSIV_MERKMAL, HOCH_MERKMAL = 16, 2, 1
STEUERZEICHEN = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f\ufffd]")
ZIFFERN = re.compile(r"\d+")
ROEMISCH = re.compile(r"(?<![a-z])[ivxlcdm]+(?![a-z])")
#: eine Zeile, die nur eine Seitenzahl ist ("12", "- 12 -", "Page 12", "12 of 300", "xii"), Ziffern schon als # geschrieben
WORT = re.compile(r"[^\W\d_]{2,}")
SATZENDE = re.compile(r"[.!?:;]\W*$")
SEITENZAHL = re.compile(r"^(?:page|seite|p\.|s\.)?\s*[-(\[|]?\s*#\s*[-)\]|]?(?:\s*(?:of|von|/)\s*#)?$")


# -- Stücke einer Seite ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Spanne:
    text: str
    x0: float
    x1: float
    groesse: float
    fett: bool
    kursiv: bool
    festbreit: bool
    hoch: bool                                       # hochgestellt (Fußnotenzeichen, Hochzahl)


@dataclass(eq=False)
class Zeile:
    seite: int
    spannen: list[Spanne]
    rechteck: fitz.Rect
    basis: float                                     # Grundlinie

    @cached_property
    def text(self) -> str:
        return "".join(s.text for s in self.spannen)

    def _anteil(self, merkmal: str) -> float:
        alle = sum(len(s.text.strip()) for s in self.spannen if not s.hoch)
        return sum(len(s.text.strip()) for s in self.spannen if not s.hoch and getattr(s, merkmal)) / alle if alle else 0.0

    @cached_property
    def groesse(self) -> float:
        """Die Schriftgröße der meisten Zeichen (ohne Hochgestelltes)."""
        n: Counter[float] = Counter()
        for s in self.spannen:
            if not s.hoch:
                n[round(s.groesse, 1)] += len(s.text.strip())
        return n.most_common(1)[0][0] if n else round(self.spannen[0].groesse, 1)

    @cached_property
    def fett(self) -> bool:
        return self._anteil("fett") >= 0.9

    @cached_property
    def festbreit(self) -> bool:
        return self._anteil("festbreit") >= MONO_ANTEIL

    @property
    def mitte(self) -> fitz.Point:
        r = self.rechteck
        return fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)


@dataclass(eq=False)
class Abbildung:
    seite: int
    rechteck: fitz.Rect
    bild: int | None = None                          # das Bild der Datei (xref), wenn die Abbildung genau dieses eine ist
    formel: bool = False
    ganze_seite: bool = False                        # eine Seite ohne Textschicht, ganz als Bild


@dataclass(eq=False)
class Zelle:
    zeilen: list[Zeile]
    rechteck: fitz.Rect
    kopf: bool = False
    spalten: int = 1


@dataclass(eq=False)
class Tabelle:
    seite: int
    rechteck: fitz.Rect
    reihen: list[list[Zelle]]


@dataclass(eq=False)
class Code:
    """Eine Codestelle; über Seiten fortgesetzt hat sie mehrere Teile, jeder mit seiner Seite."""
    seite: int
    rechteck: fitz.Rect
    titel: str
    teile: list[tuple[int, fitz.Rect, str]]          # Seite, Rechteck, Code dieses Teils


@dataclass(eq=False)
class Kasten:
    seite: int
    rechteck: fitz.Rect
    stuecke: list[Stueck] = field(default_factory=list)
    bilder: list[Abbildung] = field(default_factory=list)   # Bilder im Kasten (sie stehen dort in der Lesefolge)


Stueck = Zeile | Abbildung | Tabelle | Code | Kasten


@dataclass(eq=False)
class Seite:
    nr: int                                          # Dateiseite ab 1
    breite: float
    hoehe: float
    stuecke: list[Stueck]                            # in Lesefolge
    mit_text: bool                                   # trägt lesbaren Text
    mit_zeichen: bool                                # trägt überhaupt Zeichen (lesbar oder nicht, etwa ohne Zeichenzuordnung)
    mit_bild: bool                                   # trägt Bilder (ohne Text, aber mit Bild: ein Scan)


def rechteck_von(stueck: Stueck) -> fitz.Rect:
    return stueck.rechteck


# -- Zeilen ---------------------------------------------------------------------------------------------------------------

def _spanne(s: dict, fehlzeichen: frozenset[str] = frozenset()) -> Spanne:
    schrift, merkmale = s.get("font", ""), s.get("flags", 0)
    text = ligaturen_aufloesen(STEUERZEICHEN.sub("", s["text"]), fehlzeichen)
    return Spanne(text=text, x0=s["bbox"][0], x1=s["bbox"][2], groesse=s["size"],
                  fett=bool(merkmale & FETT_MERKMAL or FETT_NAME.search(schrift)),
                  kursiv=bool(merkmale & KURSIV_MERKMAL or KURSIV_NAME.search(schrift)),
                  festbreit=bool(merkmale & codestellen_pdf.FESTBREITE_MERKMAL or codestellen_pdf.MONO_NAME.search(schrift)),
                  hoch=bool(merkmale & HOCH_MERKMAL))


def _verbunden(spannen: list[Spanne]) -> list[Spanne]:
    """Spannen einer Zeile; ein sichtbarer Abstand ohne Leerzeichen wird eines (wie in der Textansicht)."""
    aus: list[Spanne] = []
    for s in spannen:
        if aus and s.text and not s.text[0].isspace() and not aus[-1].text[-1:].isspace() and s.x0 - aus[-1].x1 > s.groesse * 0.15:
            s = Spanne(" " + s.text, s.x0, s.x1, s.groesse, s.fett, s.kursiv, s.festbreit, s.hoch)
        aus.append(s)
    return aus


def zeilen_der_seite(seite: fitz.Page, nr: int) -> list[Zeile]:
    """Alle Zeilen mit Text; eine Zeile über eine breite Lücke hinweg wird geteilt."""
    aus = []
    bloecke = seite.get_text("dict", flags=TEXTART)["blocks"]
    fehlzeichen = fehlzeichen_der_seite(seite)
    for block in bloecke:
        for z in block.get("lines", []):
            if abs(z.get("dir", (1, 0))[1]) > 0.1:                  # gedrehter Text (Achsen, Randnotizen) bleibt draußen
                continue
            stuecke: list[list[dict]] = [[]]
            for s in sorted(z["spans"], key=lambda s: s["bbox"][0]):
                if not s["text"]:
                    continue
                vorige = next((t for t in reversed(stuecke[-1]) if t["text"].strip()), None)
                if vorige is not None and s["text"].strip() and s["bbox"][0] - vorige["bbox"][2] > LUECKE * max(s["size"], vorige["size"]):
                    stuecke.append([])
                stuecke[-1].append(s)
            for teil in stuecke:
                sichtbar = [s for s in teil if s["text"].strip()]
                if not sichtbar:
                    continue
                r = fitz.Rect(sichtbar[0]["bbox"])
                for s in sichtbar[1:]:
                    r |= fitz.Rect(s["bbox"])
                spannen = _verbunden([_spanne(s, fehlzeichen) for s in teil])
                basis = statistics.median(s["origin"][1] for s in sichtbar if not s["flags"] & HOCH_MERKMAL) \
                    if any(not s["flags"] & HOCH_MERKMAL for s in sichtbar) else sichtbar[0]["origin"][1]
                zeile = Zeile(nr, _ohne_rand(spannen), r, basis)
                if zeile.text.strip():
                    aus.append(zeile)
    return aus


def _ohne_rand(spannen: list[Spanne]) -> list[Spanne]:
    """Die Spannen ohne Leerraum am Anfang und Ende der Zeile."""
    aus = [s for s in spannen if s.text]
    while aus and not aus[0].text.strip():
        aus.pop(0)
    while aus and not aus[-1].text.strip():
        aus.pop()
    if aus:
        erst = aus[0]
        aus[0] = Spanne(erst.text.lstrip(), erst.x0, erst.x1, erst.groesse, erst.fett, erst.kursiv, erst.festbreit, erst.hoch)
        letzt = aus[-1]
        aus[-1] = Spanne(letzt.text.rstrip(), letzt.x0, letzt.x1, letzt.groesse, letzt.fett, letzt.kursiv, letzt.festbreit, letzt.hoch)
    return aus


def _innen(punkt: fitz.Point, r: fitz.Rect, rand: float = 0.0) -> bool:
    return r.x0 - rand <= punkt.x <= r.x1 + rand and r.y0 - rand <= punkt.y <= r.y1 + rand


# -- Code -----------------------------------------------------------------------------------------------------------------

def codestellen(doc: fitz.Document) -> dict[int, list[tuple[Code, fitz.Rect]]]:
    """Je Dateiseite die Teile der Codestellen; die Stelle selbst steht auf der Seite ihres ersten Teils."""
    schriften = codestellen_pdf.Schriften()
    seiten = [codestellen_pdf.seite_lesen(s, s.number + 1, schriften) for s in doc if codestellen_pdf.hat_festbreite(s)]
    je_seite: dict[int, list[tuple[Code, fitz.Rect]]] = defaultdict(list)
    for kette in codestellen_pdf.ketten(seiten):
        text, _nummer, je_teil = codestellen_pdf.text_der_kette(kette)
        if not text.strip():
            continue
        zeilen = text.split("\n")
        teile, ab = [], 0
        for b, n in zip(kette, je_teil):
            teile.append((b.seite, fitz.Rect(b.rechteck), "\n".join(zeilen[ab:ab + n])))
            ab += n
        code = Code(seite=kette[0].seite, rechteck=fitz.Rect(kette[0].rechteck), titel=kette[0].titel, teile=teile)
        for seite, r, _ in teile:
            je_seite[seite].append((code, r))
    return je_seite


def _im_code(z: Zeile, teile: list[fitz.Rect]) -> bool:
    """Eine Zeile gehört zu einer Codestelle: ihre Mitte liegt darin, oder sie ist eine Zeilennummer links davon."""
    if any(_innen(z.mitte, r, CODE_RAND) for r in teile):
        return True
    return z.text.replace(" ", "").isdigit() and any(
        r.x0 - CODE_NUMMERN <= z.rechteck.x0 and z.rechteck.x1 <= r.x0 + CODE_RAND
        and r.y0 - CODE_RAND <= z.rechteck.y0 and z.rechteck.y1 <= r.y1 + CODE_RAND for r in teile)


# -- Tabellen -------------------------------------------------------------------------------------------------------------

def _tabellen(seite: fitz.Page, nr: int, zeilen: list[Zeile], aussparen: list[fitz.Rect]) -> list[Tabelle]:
    """Tabellen aus den Linien der Seite; nur mit Linien, ab 2x2, mit Text in der Hälfte der Zellen."""
    if not seite.get_drawings():
        return []
    try:
        gefunden = seite.find_tables().tables
    except Exception:  # noqa: BLE001 - eine Seite, deren Linien sich nicht lesen lassen, hat keine Tabelle
        return []
    aus = []
    for t in gefunden:
        r = fitz.Rect(t.bbox)
        if t.row_count < 2 or t.col_count < 2 or any(r.intersects(a) for a in aussparen):
            continue
        reihen: list[list[Zelle]] = []
        gefuellt = gesamt = 0
        for reihe in t.rows:
            zellen: list[Zelle] = []
            for c in reihe.cells:
                if c is None:
                    if zellen:
                        zellen[-1].spalten += 1                   # verbunden mit der Zelle links davon
                    else:
                        zellen.append(Zelle([], fitz.Rect(r.x0, r.y0, r.x0, r.y0)))
                    continue
                zr = fitz.Rect(c)
                darin = [z for z in zeilen if _innen(z.mitte, zr, 1.0)]
                gesamt += 1
                gefuellt += bool(darin)
                zellen.append(Zelle(sorted(darin, key=lambda z: (z.basis, z.rechteck.x0)), zr))
            reihen.append(zellen)
        if gesamt and gefuellt / gesamt >= TABELLE_GEFUELLT:
            erste = [z for zelle in reihen[0] for z in zelle.zeilen]
            if erste and all(z.fett for z in erste):
                for zelle in reihen[0]:
                    zelle.kopf = True
            aus.append(Tabelle(nr, r, reihen))
    return aus


# -- Abbildungen und Kästen -----------------------------------------------------------------------------------------------

def _vereinigen(rechtecke: list[fitz.Rect], naehe: float) -> list[fitz.Rect]:
    """Rechtecke, die sich bis auf `naehe` nahekommen, zu einem (bis nichts mehr zusammengeht)."""
    gruppen = [fitz.Rect(r) for r in rechtecke]
    geaendert = True
    while geaendert:
        geaendert = False
        for i in range(len(gruppen)):
            for j in range(i + 1, len(gruppen)):
                if (gruppen[i] + (-naehe, -naehe, naehe, naehe)).intersects(gruppen[j]):
                    gruppen[i] |= gruppen.pop(j)
                    geaendert = True
                    break
            if geaendert:
                break
    return gruppen


def _formelzeichen(text: str) -> bool:
    """Mathematische Schriftzeichen (kursive Formelbuchstaben und Operatoren), wie sie Formelsatz erzeugt."""
    return any(0x1D400 <= ord(c) <= 0x1D7FF or 0x2200 <= ord(c) <= 0x22FF for c in text)


def _formel(z: Zeile, breite: float) -> bool:
    mitte = (z.rechteck.x0 + z.rechteck.x1) / 2
    return (_formelzeichen(z.text) and len(z.text) <= FORMEL_HOECHSTENS and abs(mitte - breite / 2) <= breite * FORMEL_MITTE
            and z.rechteck.width < breite * 0.7)


def _flaechen(seite: fitz.Page, aussparen: list[fitz.Rect]) -> tuple[list[fitz.Rect], list[tuple[fitz.Rect, int]]]:
    """Zeichnungen und Bilder, die zählen (groß genug, keine Linie, kein Hintergrund, nicht in Code oder Tabelle), nahe
    zusammen; dazu die Bilder der Seite mit ihrer Nummer in der Datei."""
    flaeche = seite.rect.width * seite.rect.height

    def zaehlt(r: fitz.Rect) -> bool:
        return ((r.width >= MINDESTGROESSE or r.height >= MINDESTGROESSE) and min(r.width, r.height) >= DUENN
                and r.width * r.height < HINTERGRUND * flaeche
                and not any(_innen(fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2), a, CODE_RAND) for a in aussparen))

    bilder = [(fitz.Rect(b["bbox"]) & seite.rect, b.get("xref", 0)) for b in seite.get_image_info(xrefs=True)]
    bilder = [(r, x) for r, x in bilder if r.width >= MINDESTGROESSE and r.height >= MINDESTGROESSE and zaehlt(r)]
    zeichnungen = [r for r in seite.cluster_drawings() if zaehlt(r)]
    return _vereinigen(zeichnungen + [r for r, _ in bilder], NAEHE), bilder


def _rahmenartig(zeichnung: dict, f: fitz.Rect) -> bool:
    """Hintergrund oder Rand der Fläche: gerade und so groß wie sie, oder eine Linie über ihre ganze Breite oder Höhe."""
    r = fitz.Rect(zeichnung["rect"])
    if not gerade(zeichnung):
        return False
    return (r.width * r.height >= RAHMEN_ANTEIL * f.width * f.height or r.width >= 0.9 * f.width and r.height <= DUENN
            or r.height >= 0.9 * f.height and r.width <= DUENN)


def _grafisch(f: fitz.Rect, zeichnungen: list[dict]) -> bool:
    """Trägt die Fläche Zeichnungen, die mehr als Rahmen sind (Kurven, schräge Linien, Balken, Gitter)?"""
    return any(not _rahmenartig(z, f) for z in zeichnungen if f.contains(z["rect"]) or (f + (1, 1, -1, -1)).intersects(z["rect"]))


def _einziges_bild(f: fitz.Rect, bilder: list[tuple[fitz.Rect, int]]) -> int | None:
    """Das Bild der Datei, wenn die Fläche genau aus ihm besteht (so kommt es unverändert ins EPUB)."""
    darin = [(r, x) for r, x in bilder if (f + (2, 2, -2, -2)).intersects(r)]
    if len(darin) != 1 or darin[0][1] <= 0:
        return None
    r, x = darin[0]
    return x if all(abs(a - b) <= 2 for a, b in zip(f, r)) else None


def _grundschrift(zeilen: list[Zeile]) -> float:
    """Die Größe, in der die meisten Zeichen der Seite stehen."""
    n: Counter[float] = Counter()
    for z in zeilen:
        n[z.groesse] += len(z.text)
    return n.most_common(1)[0][0] if n else 0.0


def _beschriftung(z: Zeile, f: fitz.Rect, grund: float) -> bool:
    """Eine Beschriftung gleich neben oder über und unter der Abbildung: kurz, kein Satz, nicht größer als der Text."""
    kurz = len(z.text) <= BESCHRIFTUNG_HOECHSTENS and len(WORT.findall(z.text)) < SATZ_AB and not SATZENDE.search(z.text)
    if not kurz or z.groesse > grund + 0.1:
        return False
    neben = (f + (-BESCHRIFTUNG_NAEHE, 0, BESCHRIFTUNG_NAEHE, 0)).intersects(z.rechteck) and f.y0 - 2 <= z.mitte.y <= f.y1 + 2
    darueber_darunter = ((f + (0, -BESCHRIFTUNG_NAEHE_Y, 0, BESCHRIFTUNG_NAEHE_Y)).intersects(z.rechteck)
                         and f.x0 - 10 <= z.rechteck.x0 and z.rechteck.x1 <= f.x1 + 10)
    return neben or darueber_darunter


def _abbildungen_und_kaesten(seite: fitz.Page, nr: int, zeilen: list[Zeile], aussparen: list[fitz.Rect]
                             ) -> tuple[list[Abbildung], list[tuple[Kasten, list[Zeile]]], set[int]]:
    """Abbildungen (mit dem Text darin und kurzen Beschriftungen daneben), Kästen (mit ihren Zeilen), abgesetzte Formeln;
    dazu die Zeilen, die damit vergeben sind (ihre Stelle in `zeilen`)."""
    flaechen, bilder = _flaechen(seite, aussparen)
    zeichnungen = seite.get_drawings() if flaechen else []
    grund = _grundschrift(zeilen)
    vergeben: set[int] = set()
    abbildungen: list[Abbildung] = []
    kaesten: list[tuple[Kasten, list[Zeile]]] = []
    for f in sorted(flaechen, key=lambda r: (r.y0, r.x0)):
        innen = [i for i, z in enumerate(zeilen) if i not in vergeben and _innen(z.mitte, f, 2.0)]
        mit_bild = any(f.intersects(r) for r, _ in bilder)
        saetze = any(len(WORT.findall(zeilen[i].text)) >= SATZ_AB for i in innen)
        if sum(len(zeilen[i].text) for i in innen) >= KASTEN_TEXT_AB or (
                innen and not _grafisch(f, zeichnungen) and (saetze or not mit_bild)):
            titel = [i for i, z in enumerate(zeilen) if i not in vergeben and i not in innen     # auf der oberen Kante
                     and z.rechteck.y0 < f.y0 < z.rechteck.y1 and f.x0 - 2 <= z.rechteck.x0 and z.rechteck.x1 <= f.x1 + 2]
            darin = sorted(set(innen) | set(titel))
            vergeben.update(darin)
            im_kasten = [Abbildung(nr, fitz.Rect(r), bild=x if x > 0 else None) for r, x in bilder if f.contains(r)]
            kaesten.append((Kasten(nr, fitz.Rect(f), bilder=im_kasten), [zeilen[i] for i in darin]))
            continue
        ausschnitt = fitz.Rect(f)
        for i in innen:
            ausschnitt |= zeilen[i].rechteck
        gewachsen = True
        while gewachsen:                                   # Beschriftungen daneben, auch eine zweite Reihe (Achsentitel)
            gewachsen = False
            for i, z in enumerate(zeilen):
                if i not in vergeben and i not in innen and _beschriftung(z, ausschnitt, grund):
                    innen.append(i)
                    ausschnitt |= z.rechteck
                    gewachsen = True
        vergeben.update(innen)
        abbildungen.append(Abbildung(nr, ausschnitt, bild=_einziges_bild(f, bilder) if not innen else None))
    for i, z in enumerate(zeilen):
        if i not in vergeben and _formel(z, seite.rect.width):
            vergeben.add(i)
            abbildungen.append(Abbildung(nr, fitz.Rect(z.rechteck), formel=True))
    return abbildungen, kaesten, vergeben


# -- Kopf- und Fußzeilen --------------------------------------------------------------------------------------------------

def _gleich(text: str) -> str:
    """Eine Zeile, wie sie auf jeder Seite gleich aussieht: klein, Ziffern und römische Zahlen als #."""
    t = ROEMISCH.sub("#", ZIFFERN.sub("#", text.lower()))
    return " ".join(t.split())


def _im_rand(z: Zeile, hoehe: float) -> str | None:
    if z.rechteck.y1 <= hoehe * RAND:
        return "oben"
    if z.rechteck.y0 >= hoehe * (1 - RAND):
        return "unten"
    return None


def kopf_und_fuss(seiten: list[tuple[float, list[Zeile]]]) -> set[int]:
    """Die Zeilen (id), die Kopf- oder Fußzeile oder Seitenzahl sind; `seiten` je Seite ihre Höhe und freien Zeilen."""
    kandidaten: dict[tuple[str, str], list[Zeile]] = defaultdict(list)
    weg: set[int] = set()
    for hoehe, zeilen in seiten:
        for z in zeilen:
            rand = _im_rand(z, hoehe)
            if rand is None:
                continue
            gleich = _gleich(z.text)
            if SEITENZAHL.match(gleich):
                weg.add(id(z))
            kandidaten[(rand, gleich)].append(z)
    for gruppe in kandidaten.values():
        for z in gruppe:
            if any(a.seite != z.seite and abs(a.rechteck.y0 - z.rechteck.y0) <= WIEDERKEHR_NAEHE for a in gruppe):
                weg.add(id(z))
    return weg


# -- Lesefolge ------------------------------------------------------------------------------------------------------------

def ueberdecken_x(a: fitz.Rect, b: fitz.Rect) -> bool:
    return min(a.x1, b.x1) - max(a.x0, b.x0) > 1.0


def lesefolge(stuecke: list[Stueck]) -> list[Stueck]:
    """Die Stücke einer Seite (oder eines Kastens) in Lesefolge, nach Breuel (siehe Moduldokumentation). Liegt ein Stück
    links unter einem anderen, das keine Spalte neben sich hat (eine mittige Überschrift über einer kurzen Zeile), gilt
    nur oben vor unten."""
    n = len(stuecke)
    r = [rechteck_von(s) for s in stuecke]
    nach: list[set[int]] = [set() for _ in range(n)]

    def zwischen(a: int, b: int) -> bool:
        """Liegt etwas senkrecht zwischen a und b, das waagerecht über beide reicht?"""
        oben, unten = min(r[a].y1, r[b].y1), max(r[a].y0, r[b].y0)
        return any(c != a and c != b and r[c].y0 >= oben - 1 and r[c].y1 <= unten + 1
                   and ueberdecken_x(r[c], r[a]) and ueberdecken_x(r[c], r[b]) for c in range(n))

    def spalte_reicht_hinauf(a: int, b: int) -> bool:
        """a liegt ganz unter b: links von b steht etwas in a's Spalte auf der Höhe von b (es gibt die Spalte)."""
        return any(c != a and r[c].x1 <= r[b].x0 + 1 and ueberdecken_x(r[c], r[a]) and r[c].y0 < r[b].y1 and r[c].y1 > r[b].y0
                   for c in range(n))

    for a in range(n):
        for b in range(n):
            if a == b:
                continue
            if ueberdecken_x(r[a], r[b]):
                if r[a].y0 < r[b].y0 or (r[a].y0 == r[b].y0 and a < b):
                    nach[a].add(b)
            elif r[a].x1 <= r[b].x0 + 1 and not zwischen(a, b):
                if r[a].y0 < r[b].y1 or spalte_reicht_hinauf(a, b):
                    nach[a].add(b)
    rein = [0] * n
    for a in range(n):
        for b in nach[a]:
            rein[b] += 1
    bereit = [(r[i].y0, r[i].x0, i) for i in range(n) if rein[i] == 0]
    heapq.heapify(bereit)
    folge: list[int] = []
    gesehen = [False] * n
    while len(folge) < n:
        if not bereit:                                     # ein Kreis: das oberste übrige Stück zuerst
            rest = min((i for i in range(n) if not gesehen[i]), key=lambda i: (r[i].y0, r[i].x0))
            rein[rest] = 0
            bereit = [(r[rest].y0, r[rest].x0, rest)]
        _, _, i = heapq.heappop(bereit)
        if gesehen[i]:
            continue
        gesehen[i] = True
        folge.append(i)
        for b in nach[i]:
            rein[b] -= 1
            if rein[b] == 0 and not gesehen[b]:
                heapq.heappush(bereit, (r[b].y0, r[b].x0, b))
    return [stuecke[i] for i in folge]


# -- Seiten ---------------------------------------------------------------------------------------------------------------

@dataclass(eq=False)
class _Roh:
    nr: int
    breite: float
    hoehe: float
    frei: list[Zeile]
    einschuebe: list[Stueck]
    kaesten: list[tuple[Kasten, list[Zeile]]]
    mit_bild: bool
    text: str                                        # aller Text der Seite, auch in Code, Tabellen und Kästen


def _roh(seite: fitz.Page, nr: int, code: list[tuple[Code, fitz.Rect]]) -> _Roh:
    zeilen = zeilen_der_seite(seite, nr)
    text = " ".join(z.text for z in zeilen)
    teile = [r for _, r in code]
    zeilen = [z for z in zeilen if not _im_code(z, teile)]
    tabellen = _tabellen(seite, nr, zeilen, teile)
    in_tabelle = {id(z) for t in tabellen for reihe in t.reihen for zelle in reihe for z in zelle.zeilen}
    zeilen = [z for z in zeilen if id(z) not in in_tabelle and not any(_innen(z.mitte, t.rechteck, 1.0) for t in tabellen)]
    abbildungen, kaesten, vergeben = _abbildungen_und_kaesten(seite, nr, zeilen, teile + [t.rechteck for t in tabellen])
    frei = [z for i, z in enumerate(zeilen) if i not in vergeben]
    einschuebe: list[Stueck] = [*abbildungen, *tabellen, *(c for c, _ in code if c.seite == nr)]
    return _Roh(nr, seite.rect.width, seite.rect.height, frei, einschuebe, kaesten, bool(seite.get_images()), text)


def lesen(doc: fitz.Document) -> list[Seite]:
    """Alle Seiten des PDF in Lesefolge, ohne Kopf- und Fußzeilen."""
    code = codestellen(doc)
    roh = [_roh(s, s.number + 1, code.get(s.number + 1, [])) for s in doc]
    weg = kopf_und_fuss([(r.hoehe, r.frei) for r in roh])
    seiten = []
    for r in roh:
        frei = [z for z in r.frei if id(z) not in weg]
        kaesten = []
        for kasten, zeilen in r.kaesten:
            kasten.stuecke = lesefolge([*zeilen, *kasten.bilder])
            kaesten.append(kasten)
        mit_text = bool(r.text.strip()) and lesbar(r.text)
        if mit_text:
            stuecke = lesefolge([*frei, *r.einschuebe, *kaesten])
        elif r.mit_bild:                                   # ohne Textschicht: die ganze Seite als Bild
            stuecke = [Abbildung(r.nr, fitz.Rect(0, 0, r.breite, r.hoehe), ganze_seite=True)]
        else:
            stuecke = [s for s in r.einschuebe if isinstance(s, Abbildung)]
        seiten.append(Seite(r.nr, r.breite, r.hoehe, stuecke, mit_text, bool(r.text.strip()), r.mit_bild))
    return seiten
