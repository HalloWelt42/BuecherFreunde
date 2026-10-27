"""Textansicht eines PDF: jede Seite als Folge von Bausteinen zum Lesen am Telefon, statt fester Zeilen.

Gelesen wird direkt aus der PDF-Datei, in Lesereihenfolge von oben nach unten:
- Absätze: die Textblöcke der Seite, Zeilen verbunden. Trennstriche am Zeilenende werden verbunden, wenn die nächste
  Zeile klein weitergeht ("Bei-" + "spiel"); vor einem Großbuchstaben bleibt der Bindestrich ("Nord-" + "Süd").
- Überschriften: Blöcke in deutlich größerer Schrift als der Fließtext.
- Bildunterschriften: Blöcke, die mit "Abbildung", "Abb." oder "Tabelle" beginnen.
- Abbildungen: Rasterbilder und Zeichnungen (nahe beieinander liegende Linien und Flächen, samt ihrer kurzen
  Beschriftungen) werden als Ausschnitt der Originalseite gezeigt; die Oberfläche holt ihn über den Bild-Endpunkt.
- Kästen: eine Zeichnung, die einen längeren Text umrahmt ("Merke", "Fachbegriff"), bleibt Text, als Kasten mit
  seinem Titel (einzeilig, auf oder knapp über dem Rahmen).
- Abgesetzte Formeln (mittig, mit mathematischen Schriftzeichen) zerfallen als Text; sie werden wie Abbildungen als
  Ausschnitt gezeigt, auch innerhalb eines Kastens.
- Hochgestellte Ziffern im Fließtext werden zu Hochzahlen ("m/s2" wird "m/s" mit hochgestellter 2).
- Kopf- und Fußzeilen (Blöcke im oberen und unteren Rand) fallen weg.

Seiten ohne lesbaren Text (Scan ohne Textschicht, oder eine Schrift ohne Zeichenzuordnung, die nur Steuer- und
Sonderzeichen liefert) tragen keine Textbausteine; die Oberfläche weist dann auf die Originalansicht hin.

Die Abbildungen einer Seite entstehen bei jedem Aufruf gleich aus `seitenaufbau`; der Bild-Endpunkt nutzt dieselbe
Funktion, damit Nummer und Ausschnitt immer zusammenpassen.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path

import fitz

_RAND_OBEN = 0.075              # Anteil der Seitenhöhe: darüber Kopfzeile
_RAND_UNTEN = 0.94              # darunter Fußzeile
_UEBERSCHRIFT_FAKTOR = 1.15     # so viel größer als der Fließtext gilt als Überschrift
_UEBERSCHRIFT_HOECHSTENS = 160  # Zeichen; längere Blöcke sind auch bei großer Schrift Text
_NAEHE = 12.0                   # Punkte: so nah beieinander gehören Zeichnungsteile zu einer Abbildung
_BESCHRIFTUNG_NAEHE_X = 40.0    # Beschriftungen neben einer Abbildung
_BESCHRIFTUNG_NAEHE_Y = 22.0    # Beschriftungen über und unter einer Abbildung (etwa Achsentitel)
_BESCHRIFTUNG_HOECHSTENS = 100  # Zeichen; längere Blöcke sind Text, keine Beschriftung
_KASTEN_TEXT_AB = 120           # Zeichen in einer Zeichnung: ab hier ist sie ein Kasten um Text
_KASTEN_TITEL_NAEHE = 18.0      # Titel eines Kastens sitzt auf oder knapp über seinem Rahmen
_KASTEN_TITEL_HOECHSTENS = 100  # Zeichen eines Kastentitels
_MINDESTGROESSE = 24.0          # kleinere Zeichnungen und Bilder (Linien, Zierrat) zählen nicht
_FORMEL_HOECHSTENS = 160        # Zeichen; längere Blöcke mit Formelzeichen sind Text mit Formeln darin
_FORMEL_MITTE = 0.12            # Anteil der Seitenbreite: so nah an der Mitte steht eine abgesetzte Formel
_FORMEL_NAEHE = 6.0             # Punkte: Teile einer mehrzeiligen Formel (Bruch) liegen so dicht
_FORMEL_TEIL_HOECHSTENS = 24    # Zeichen eines Formelteils ohne Formelzeichen (Nenner "8 s")
_LESBAR_ANTEIL = 0.5            # mindestens so viele der sichtbaren Zeichen müssen Buchstaben oder Ziffern sein
_UNTERSCHRIFT = re.compile(r"^(Abbildung|Abb\.|Tabelle|Tab\.|Figure|Fig\.|Table)\s*[\dIVX]", re.IGNORECASE)
_STEUERZEICHEN = re.compile(r"[\x00-\x08\x0b\x0e-\x1f\x7f]")
_HOCHGESTELLT = 1               # Merkmal einer Textspanne in PyMuPDF
# Hochzahlen: 0-9 sowie Plus, Minus (beide Formen) und n, als Codepunkte (keine Sonderzeichen im Quelltext)
_HOCHZAHLEN = str.maketrans("0123456789+-" + chr(0x2212) + "n",
                            "".join(map(chr, (0x2070, 0xB9, 0xB2, 0xB3, 0x2074, 0x2075, 0x2076, 0x2077, 0x2078, 0x2079,
                                              0x207A, 0x207B, 0x207B, 0x207F))))
_HOCHZAHL_FAEHIG = re.compile(r"^[0-9+\-" + chr(0x2212) + r"n]+$")


def _formelzeichen(text: str) -> bool:
    """Mathematische Schriftzeichen (kursive Formelbuchstaben und Operatoren), wie sie Formelsatz erzeugt."""
    return any(0x1D400 <= ord(c) <= 0x1D7FF or 0x2200 <= ord(c) <= 0x22FF for c in text)


@dataclass
class Baustein:
    art: str                    # absatz, ueberschrift, unterschrift, kasten, bild
    oben: float
    links: float
    text: str = ""
    titel: str = ""
    inhalt: list[Baustein] = field(default_factory=list)   # Absätze und Bilder eines Kastens
    rechteck: fitz.Rect | None = None
    bild: int | None = None     # Nummer der Abbildung auf der Seite (Bild-Endpunkt)


@dataclass
class _Block:
    rechteck: fitz.Rect
    text: str
    groesse: float
    zeilen: int


def lesbar(text: str) -> bool:
    """Trägt der Text echte Zeichen? Zeichensalat aus Steuer- und Sonderzeichen gilt nicht."""
    sichtbar = [c for c in text if not c.isspace()]
    if not sichtbar:
        return False
    return sum(c.isalnum() for c in sichtbar) / len(sichtbar) >= _LESBAR_ANTEIL


def verbinde(zeilen: list[str]) -> str:
    """Zeilen eines Blocks zu einem Absatz, Trennstriche am Zeilenende aufgelöst."""
    laufend = ""
    for roh in zeilen:
        zeile = " ".join(_STEUERZEICHEN.sub("", roh).split())
        if not zeile:
            continue
        if not laufend:
            laufend = zeile
        elif laufend.endswith("-") and len(laufend) > 1 and laufend[-2].isalpha():
            laufend = (laufend[:-1] if zeile[0].islower() else laufend) + zeile
        else:
            laufend = f"{laufend} {zeile}"
    return laufend


def _spanne(spanne: dict) -> str:
    text = spanne["text"]
    if spanne["flags"] & _HOCHGESTELLT and _HOCHZAHL_FAEHIG.match(text.strip()):
        return text.strip().translate(_HOCHZAHLEN)
    return text


def _zeilentext(zeile: dict) -> str:
    """Spannen einer Zeile verbinden; ein sichtbarer Abstand ohne Leerzeichen (nach Formelbuchstaben) wird eines."""
    text, voriges_ende = "", None
    for spanne in zeile["spans"]:
        stueck = _spanne(spanne)
        luecke = voriges_ende is not None and spanne["bbox"][0] - voriges_ende > spanne["size"] * 0.15
        if luecke and text and not text[-1].isspace() and stueck and not stueck[0].isspace():
            text += " "
        text += stueck
        voriges_ende = spanne["bbox"][2]
    return text


def _formelzeile(zeile: dict, text: str, breite: float) -> bool:
    x0, _, x1, _ = zeile["bbox"]
    return (_formelzeichen(text) and len(text) <= _FORMEL_HOECHSTENS
            and abs((x0 + x1) / 2 - breite / 2) <= breite * _FORMEL_MITTE and x1 - x0 < breite * 0.7)


def _bloecke(seite: fitz.Page) -> list[_Block]:
    """Textblöcke der Seite; abgesetzte Formelzeilen innerhalb eines Blocks werden zu eigenen Blöcken."""
    breite = seite.rect.width
    bloecke = []
    for block in seite.get_text("dict", sort=True)["blocks"]:
        if block.get("type") != 0:
            continue
        gruppen: list[tuple[bool, list[dict], list[str]]] = []
        for zeile in block["lines"]:
            text = _zeilentext(zeile)
            formel = _formelzeile(zeile, text, breite)
            if not gruppen or gruppen[-1][0] != formel:
                gruppen.append((formel, [], []))
            gruppen[-1][1].append(zeile)
            gruppen[-1][2].append(text)
        for _, zeilen, texte in gruppen:
            text = verbinde(texte)
            if not text:
                continue
            rechteck = fitz.Rect(zeilen[0]["bbox"])
            for zeile in zeilen[1:]:
                rechteck |= fitz.Rect(zeile["bbox"])
            groessen = [sp["size"] for z in zeilen for sp in z["spans"] if sp["text"].strip()]
            bloecke.append(_Block(rechteck, text, max(groessen, default=0.0), len(zeilen)))
    return bloecke


def _vereinigen(rechtecke: list[fitz.Rect], naehe: float) -> list[fitz.Rect]:
    """Rechtecke, die sich bis auf `naehe` nahekommen, zu einem zusammenfassen (bis nichts mehr zusammengeht)."""
    gruppen = [fitz.Rect(r) for r in rechtecke]
    geaendert = True
    while geaendert:
        geaendert = False
        for i in range(len(gruppen)):
            for j in range(i + 1, len(gruppen)):
                a, b = gruppen[i], gruppen[j]
                if (a + (-naehe, -naehe, naehe, naehe)).intersects(b):
                    gruppen[i] = a | b
                    del gruppen[j]
                    geaendert = True
                    break
            if geaendert:
                break
    return gruppen


def _innen(block: _Block, flaeche: fitz.Rect, rand: float = 4.0) -> bool:
    mitte = fitz.Point((block.rechteck.x0 + block.rechteck.x1) / 2, (block.rechteck.y0 + block.rechteck.y1) / 2)
    return mitte in flaeche + (-rand, -rand, rand, rand)


def _ist_beschriftung(block: _Block, flaeche: fitz.Rect) -> bool:
    if len(block.text) > _BESCHRIFTUNG_HOECHSTENS or _UNTERSCHRIFT.match(block.text):
        return False
    umgebung = flaeche + (-_BESCHRIFTUNG_NAEHE_X, -_BESCHRIFTUNG_NAEHE_Y, _BESCHRIFTUNG_NAEHE_X, _BESCHRIFTUNG_NAEHE_Y)
    return umgebung.intersects(block.rechteck)


def _ist_formel(block: _Block, breite: float) -> bool:
    mitte = (block.rechteck.x0 + block.rechteck.x1) / 2
    return (len(block.text) <= _FORMEL_HOECHSTENS and _formelzeichen(block.text)
            and abs(mitte - breite / 2) <= breite * _FORMEL_MITTE and block.rechteck.width < breite * 0.7)


def _textart(block: _Block, fliesstext: float) -> str:
    if _UNTERSCHRIFT.match(block.text):
        return "unterschrift"
    if fliesstext and block.groesse >= fliesstext * _UEBERSCHRIFT_FAKTOR and len(block.text) <= _UEBERSCHRIFT_HOECHSTENS:
        return "ueberschrift"
    return "absatz"


def _kastentitel(bloecke: list[_Block], frei: list[int], innen: list[int], flaeche: fitz.Rect) -> int | None:
    """Einzeiliger kurzer Block auf oder knapp über dem Rahmen; liegt das Etikett innen, der erste Block oben."""
    def passt(i: int) -> bool:
        return bloecke[i].zeilen == 1 and len(bloecke[i].text) <= _KASTEN_TITEL_HOECHSTENS
    aussen = next((i for i in frei if i not in innen and passt(i) and _innen(bloecke[i], flaeche, _KASTEN_TITEL_NAEHE)
                   and bloecke[i].rechteck.y1 <= flaeche.y0 + _KASTEN_TITEL_NAEHE), None)
    if aussen is not None:
        return aussen
    if len(innen) > 1 and passt(innen[0]) and bloecke[innen[0]].rechteck.y0 <= flaeche.y0 + _KASTEN_TITEL_NAEHE:
        return innen[0]
    return None


def seitenaufbau(seite: fitz.Page) -> list[Baustein]:
    """Die Bausteine einer Seite in Lesereihenfolge (siehe Moduldokumentation)."""
    hoehe, breite = seite.rect.height, seite.rect.width
    bloecke = [b for b in _bloecke(seite)
               if b.rechteck.y1 > hoehe * _RAND_OBEN and b.rechteck.y0 < hoehe * _RAND_UNTEN]
    if not lesbar(" ".join(b.text for b in bloecke)):
        bloecke = []
    fliesstext = statistics.median([b.groesse for b in bloecke if len(b.text) > 200]
                                   or [b.groesse for b in bloecke] or [0])

    formelbloecke = {i for i, b in enumerate(bloecke) if _ist_formel(b, breite)}
    vergeben: set[int] = set()

    zeichnungen = [r for r in seite.cluster_drawings() if r.width >= _MINDESTGROESSE or r.height >= _MINDESTGROESSE]
    bilder = [fitz.Rect(b["bbox"]) for b in seite.get_image_info()]
    bilder = [r for r in bilder if r.width >= _MINDESTGROESSE and r.height >= _MINDESTGROESSE]
    flaechen = _vereinigen(zeichnungen + bilder, _NAEHE)

    bausteine: list[Baustein] = []
    abbildungen: list[fitz.Rect] = []
    kaesten: list[tuple[fitz.Rect, Baustein]] = []
    im_kasten: dict[int, tuple[Baustein, Baustein]] = {}   # Block -> (Kasten, sein Absatz)
    for flaeche in sorted(flaechen, key=lambda r: (r.y0, r.x0)):
        frei = [i for i in range(len(bloecke)) if i not in vergeben]
        innen = [i for i in frei if _innen(bloecke[i], flaeche)]
        if max((len(bloecke[i].text) for i in innen if i not in formelbloecke), default=0) >= _KASTEN_TEXT_AB:
            titel = _kastentitel(bloecke, frei, innen, flaeche)
            innen = [i for i in innen if i != titel and i not in formelbloecke]
            vergeben.update(innen)
            if titel is not None:
                vergeben.add(titel)
            kasten = Baustein("kasten", flaeche.y0, flaeche.x0, titel=bloecke[titel].text if titel is not None else "")
            for i in innen:
                absatz = Baustein("absatz", bloecke[i].rechteck.y0, bloecke[i].rechteck.x0, text=bloecke[i].text)
                kasten.inhalt.append(absatz)
                im_kasten[i] = (kasten, absatz)
            kaesten.append((flaeche, kasten))
            bausteine.append(kasten)
            continue
        # Beschriftungen gehören dazu, auch die zweite Reihe (Achsentitel unter den Achsenzahlen) und Beschriftungen
        # mit Formelbuchstaben ("Zeit t(s)")
        ausschnitt = fitz.Rect(flaeche)
        gewachsen = True
        while gewachsen:
            gewachsen = False
            for i in frei:
                if i not in vergeben and (_innen(bloecke[i], ausschnitt) or _ist_beschriftung(bloecke[i], ausschnitt)):
                    ausschnitt |= bloecke[i].rechteck
                    vergeben.add(i)
                    gewachsen = True
        abbildungen.append(ausschnitt)

    # Abgesetzte Formeln: als Ausschnitt; mehrzeilige (Brüche) samt kurzer Teile ohne Formelzeichen zusammengefasst
    formeln: list[fitz.Rect] = []
    for flaeche in _vereinigen([bloecke[i].rechteck for i in formelbloecke if i not in vergeben], _FORMEL_NAEHE):
        vergeben.update(i for i in formelbloecke if _innen(bloecke[i], flaeche))
        for i, b in enumerate(bloecke):
            naehe = flaeche + (0, -_FORMEL_NAEHE, 0, _FORMEL_NAEHE)
            frei = i not in vergeben or i in im_kasten
            if frei and len(b.text) <= _FORMEL_TEIL_HOECHSTENS and naehe.intersects(b.rechteck):
                flaeche |= b.rechteck
                vergeben.add(i)
                if i in im_kasten:
                    kasten, absatz = im_kasten.pop(i)
                    kasten.inhalt.remove(absatz)
        formeln.append(flaeche)
    for formel in list(formeln):
        kasten = next((k for f, k in kaesten if f.contains(formel)), None)
        if kasten is not None:
            formeln.remove(formel)
            kasten.inhalt.append(Baustein("bild", formel.y0, formel.x0, rechteck=formel))
    for _, kasten in kaesten:
        kasten.inhalt.sort(key=lambda b: (b.oben, b.links))

    for flaeche in _vereinigen(abbildungen, 0.0) + formeln:
        bausteine.append(Baustein("bild", flaeche.y0, flaeche.x0, rechteck=flaeche))
    for i, b in enumerate(bloecke):
        if i not in vergeben:
            bausteine.append(Baustein(_textart(b, fliesstext), b.rechteck.y0, b.rechteck.x0, text=b.text))

    bausteine.sort(key=lambda b: (b.oben, b.links))
    nummer = 0
    for b in bausteine:
        for teil in [b, *b.inhalt]:
            if teil.art == "bild":
                teil.bild = nummer
                nummer += 1
    return bausteine


def abbildungen(seite: fitz.Page) -> list[fitz.Rect]:
    """Die Ausschnitte der Abbildungen einer Seite, nummeriert wie in `seitenaufbau` (ab 0)."""
    return [t.rechteck for b in seitenaufbau(seite) for t in [b, *b.inhalt] if t.art == "bild"]


def seiten_lesen(pfad: Path, ab: int, anzahl: int) -> tuple[int, list[tuple[int, list[Baustein]]]]:
    """Gesamtzahl der Seiten und die Bausteine der Seiten ab `ab` (Dateiseite, ab 1)."""
    with fitz.open(str(pfad)) as doc:
        bis = min(ab + anzahl - 1, doc.page_count)
        return doc.page_count, [(nr, seitenaufbau(doc[nr - 1])) for nr in range(ab, bis + 1)]


def abbildung_png(pfad: Path, seite: int, nr: int, zoom: float = 2.5) -> bytes | None:
    """Abbildung `nr` der Dateiseite `seite` als PNG; None, wenn es sie nicht gibt."""
    with fitz.open(str(pfad)) as doc:
        if not 1 <= seite <= doc.page_count:
            return None
        blatt = doc[seite - 1]
        ausschnitte = abbildungen(blatt)
        if not 0 <= nr < len(ausschnitte):
            return None
        ausschnitt = (ausschnitte[nr] + (-4, -4, 4, 4)) & blatt.rect
        return blatt.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=ausschnitt, alpha=False).tobytes("png")
