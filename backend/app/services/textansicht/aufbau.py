"""Der Aufbau einer Seite aus Absätzen, Flächen und Codestellen, und das Lesen mehrerer Seiten samt Seitenwechsel."""

from __future__ import annotations

import re
from pathlib import Path

import fitz

from backend.app.codestellen.pdf import ADRESSE, MONO_ANTEIL
from backend.app.services.pdfseite import gruppen as zeichnungsgruppen, lesbar, sichtbare_zeichnungen
from backend.app.services.textansicht.code import (KASTEN_TEXT_AB, codebaustein, kastenrest, lose_codezeilen, tafel, tafelart,
                                                    tafelcode)
from backend.app.services.textansicht import nachgebessert
from backend.app.services.textansicht.erkannt import bilder_der_erkennung, zeilen_der_erkennung
from backend.app.services.textansicht.modelle import MINDESTGROESSE, Baustein, Codeteil, Textseite
from backend.app.services.textansicht.zeilen import (SATZENDE, UEBERSCHRIFT_FAKTOR, Block, Zeile, abgesetzte_formel,
                                                     absaetze, masse, verbinde, zeilen_der_seite)
from backend.app.services.textansicht.zuschnitt import zuschnitt
from backend.app.texterkennung import textschicht
from backend.app.texterkennung.modelle import Erkennungen, Seitenerkennung

UEBERSCHRIFT_HOECHSTENS = 160   # Zeichen; längere Blöcke sind auch bei großer Schrift Text
NAEHE = 12.0                    # Punkte: so nah beieinander gehören Zeichnungsteile zu einer Abbildung
BESCHRIFTUNG_NAEHE_X = 40.0     # Beschriftungen neben einer Abbildung
BESCHRIFTUNG_NAEHE_Y = 22.0     # Beschriftungen über und unter einer Abbildung (etwa Achsentitel)
BESCHRIFTUNG_HOECHSTENS = 100   # Zeichen; längere Blöcke sind Text, keine Beschriftung
KASTEN_TITEL_NAEHE = 18.0       # Titel eines Kastens sitzt auf oder knapp über seinem Rahmen
KASTEN_TITEL_HOECHSTENS = 100   # Zeichen eines Kastentitels
FORMEL_NAEHE = 6.0              # Punkte: Teile einer mehrzeiligen Formel (Bruch) liegen so dicht
FORMEL_TEIL_HOECHSTENS = 24     # Zeichen eines Formelteils ohne Formelzeichen (Nenner "8 s")
INNEN_RAND = 4.0                # Punkte: so weit außerhalb einer Fläche zählt die Mitte eines Absatzes noch als darin
CODE_RAND = 4.0                 # Punkte um eine Codestelle, die noch zu ihr gehören (Rahmen, Titel auf der Kante)
CODE_NUMMERN = 32.0             # Punkte links einer Codestelle ohne Kasten, in denen ihre Zeilennummern stehen
UNTERSCHRIFT = re.compile(r"^(Abbildung|Abb\.|Tabelle|Tab\.|Figure|Fig\.|Table)\s*[\dIVX]", re.IGNORECASE)


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


def _mitte(r: fitz.Rect) -> fitz.Point:
    return fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)


def _innen(block: Block, flaeche: fitz.Rect, rand: float = INNEN_RAND) -> bool:
    return _mitte(block.rechteck) in flaeche + (-rand, -rand, rand, rand)


def _ist_beschriftung(block: Block, flaeche: fitz.Rect, fliesstext: float) -> bool:
    """Steht der Block als Beschriftung bei der Fläche? Kurz, nah, keine Bildunterschrift und keine Überschrift (die über einer
    Abbildung beginnt den Abschnitt, zu dem sie gehört)."""
    if len(block.text) > BESCHRIFTUNG_HOECHSTENS or UNTERSCHRIFT.match(block.text):
        return False
    if fliesstext and block.groesse >= fliesstext * UEBERSCHRIFT_FAKTOR:
        return False
    umgebung = flaeche + (-BESCHRIFTUNG_NAEHE_X, -BESCHRIFTUNG_NAEHE_Y, BESCHRIFTUNG_NAEHE_X, BESCHRIFTUNG_NAEHE_Y)
    return umgebung.intersects(block.rechteck)


def _textart(block: Block, fliesstext: float) -> str:
    if block.festbreit >= MONO_ANTEIL and not all(ADRESSE.search(z.text) for z in block.zeilen):
        return "code"                                  # Festbreite ist Code, nur Adressen (Fußnoten) bleiben Text
    if UNTERSCHRIFT.match(block.text):
        return "unterschrift"
    if fliesstext and block.groesse >= fliesstext * UEBERSCHRIFT_FAKTOR and len(block.text) <= UEBERSCHRIFT_HOECHSTENS:
        return "ueberschrift"
    return "absatz"


def _im_code(r: fitz.Rect, codeteile: list[Codeteil]) -> bool:
    """Gehört eine Zeile oder eine Zeichnung zu einer Codestelle: liegt ihre Mitte darin, oder ganz in ihrem Rand."""
    return any(_mitte(r) in c.rechteck + (-CODE_RAND, -CODE_RAND, CODE_RAND, CODE_RAND)
               or (c.rechteck + (-CODE_RAND, -CODE_RAND, CODE_RAND, CODE_RAND)).contains(r) for c in codeteile)


def _zeilennummer(z: Zeile, codeteile: list[Codeteil]) -> bool:
    """Eine Zeilennummer links neben einer Codestelle."""
    r = z.rechteck
    return z.text.replace(" ", "").isdigit() and any(
        c.rechteck.x0 - CODE_NUMMERN <= r.x0 and r.x1 <= c.rechteck.x0 + CODE_RAND
        and c.rechteck.y0 - CODE_RAND <= r.y0 and r.y1 <= c.rechteck.y1 + CODE_RAND for c in codeteile)


class _Seitenbau:
    """Baut die Bausteine einer Seite und merkt sich, welche Absätze schon vergeben sind (an Kästen, Tafeln, Abbildungen,
    Formeln). Gilt für die Seite ihre Erkennung (`schicht`), kommen Zeilen und Bilder aus ihr."""

    def __init__(self, seite: fitz.Page, codeteile: list[Codeteil], zuschneiden: bool, schicht: textschicht.Schicht) -> None:
        self.seite, self.codeteile, self.zuschneiden = seite, codeteile, zuschneiden
        self.erkennung = schicht.erkennung
        roh = zeilen_der_erkennung(self.erkennung, seite) if self.erkennung else zeilen_der_seite(seite)
        zeilen = [z for z in roh if not _im_code(z.rechteck, codeteile) and not _zeilennummer(z, codeteile)]
        if not lesbar(" ".join(z.text for z in zeilen)):
            zeilen = []
        self.masse = masse(zeilen)
        self.bloecke = absaetze(zeilen, self.masse)
        self.formelbloecke = {i for i, b in enumerate(self.bloecke) if abgesetzte_formel(b.text, b.rechteck, seite.rect.width)}
        self.vergeben: set[int] = set()
        self.bausteine: list[Baustein] = []
        self.abbildungen: list[fitz.Rect] = []
        self.kaesten: list[tuple[fitz.Rect, Baustein]] = []
        self.im_kasten: dict[int, tuple[Baustein, Baustein]] = {}   # Block -> (Kasten, sein Absatz)
        self.quelle: dict[int, Block] = {}                          # Absatz -> sein Block (für lose Codezeilen)

    @property
    def fliesstext(self) -> float:
        return self.masse.grund

    def bauen(self) -> list[Baustein]:
        zeichnungen, bilder, flaechen = self._flaechen()
        for flaeche in sorted(flaechen, key=lambda r: (r.y0, r.x0)):
            self._flaeche(flaeche, zeichnungen, bilder)
        self._formeln()
        self._text()
        bausteine = lose_codezeilen(sorted(self.bausteine, key=lambda b: (b.oben, b.links)), self.quelle)
        self._bilder_nummerieren(bausteine)
        return bausteine

    # -- Flächen -------------------------------------------------------------------------------------------------------
    def _flaechen(self) -> tuple[list[dict], list[fitz.Rect], list[fitz.Rect]]:
        """Die sichtbaren Zeichnungen, die Bilder und daraus die Flächen der Seite (nahe Teile zusammen, ohne Codestellen)."""
        zeichnungen = sichtbare_zeichnungen(self.seite)
        gruppen = [r for r in zeichnungsgruppen(self.seite, zeichnungen)
                   if (r.width >= MINDESTGROESSE or r.height >= MINDESTGROESSE) and not _im_code(r, self.codeteile)]
        bilder = self._bilder()
        bilder = [r for r in bilder if r.width >= MINDESTGROESSE and r.height >= MINDESTGROESSE]
        return zeichnungen, bilder, _vereinigen(gruppen + bilder, NAEHE)

    def _bilder(self) -> list[fitz.Rect]:
        """Die Bilder der Seite; auf einer erkannten Seite ist das Seitenbild keins, dort zählen die Bildflächen der Erkennung."""
        if self.erkennung is not None:
            return bilder_der_erkennung(self.erkennung)
        return [fitz.Rect(b["bbox"]) for b in self.seite.get_image_info()]

    def _flaeche(self, flaeche: fitz.Rect, zeichnungen: list[dict], bilder: list[fitz.Rect]) -> None:
        """Eine Fläche wird Tafel (Code oder Kasten), Kasten oder Abbildung; ohne eigenen Text ist sie vielleicht nur
        Hintergrund (das Ende eines Kastens von der Seite davor, die Fläche erkannter Codestellen)."""
        frei = [i for i in range(len(self.bloecke)) if i not in self.vergeben]
        innen = [i for i in frei if _innen(self.bloecke[i], flaeche)]
        if not innen and (kastenrest(flaeche, zeichnungen, bilder)
                          or any(flaeche.contains(_mitte(c.rechteck)) for c in self.codeteile)):
            return
        text = [self.bloecke[i] for i in innen if i not in self.formelbloecke]
        art = tafelart(text, self.fliesstext) if tafel(flaeche, text, zeichnungen, bilder) else ""
        if art == "text":
            return
        if art == "code":
            self.vergeben.update(innen)
            self.bausteine += tafelcode([self.bloecke[i] for i in innen], self.codeteile)
        elif art == "kasten" or max((len(b.text) for b in text), default=0) >= KASTEN_TEXT_AB:
            self._kasten(flaeche, frei, innen)
        else:
            self._abbildung(flaeche, frei)

    def _kastentitel(self, frei: list[int], innen: list[int], flaeche: fitz.Rect) -> int | None:
        """Einzeiliger kurzer Block auf oder knapp über dem Rahmen; liegt das Etikett innen, der erste Block oben."""
        def passt(i: int) -> bool:
            return len(self.bloecke[i].zeilen) == 1 and len(self.bloecke[i].text) <= KASTEN_TITEL_HOECHSTENS
        aussen = next((i for i in frei if i not in innen and passt(i) and _innen(self.bloecke[i], flaeche, KASTEN_TITEL_NAEHE)
                       and self.bloecke[i].rechteck.y1 <= flaeche.y0 + KASTEN_TITEL_NAEHE), None)
        if aussen is not None:
            return aussen
        if len(innen) > 1 and passt(innen[0]) and self.bloecke[innen[0]].rechteck.y0 <= flaeche.y0 + KASTEN_TITEL_NAEHE:
            return innen[0]
        return None

    def _kasten(self, flaeche: fitz.Rect, frei: list[int], innen: list[int]) -> None:
        titel = self._kastentitel(frei, innen, flaeche)
        innen = [i for i in innen if i != titel and i not in self.formelbloecke]
        self.vergeben.update(innen)
        if titel is not None:
            self.vergeben.add(titel)
        kasten = Baustein("kasten", flaeche.y0, flaeche.x0, titel=self.bloecke[titel].text if titel is not None else "")
        for i in innen:
            b = self.bloecke[i]
            absatz = Baustein("absatz", b.rechteck.y0, b.rechteck.x0, text=b.text)
            kasten.inhalt.append(absatz)
            self.im_kasten[i] = (kasten, absatz)
        self.kaesten.append((flaeche, kasten))
        self.bausteine.append(kasten)

    def _abbildung(self, flaeche: fitz.Rect, frei: list[int]) -> None:
        """Ausschnitt samt Beschriftungen, auch der zweiten Reihe (Achsentitel unter den Achsenzahlen) und Beschriftungen mit
        Formelbuchstaben ("Zeit t(s)")."""
        ausschnitt = fitz.Rect(flaeche)
        gewachsen = True
        while gewachsen:
            gewachsen = False
            for i in frei:
                b = self.bloecke[i]
                if i not in self.vergeben and (_innen(b, ausschnitt) or _ist_beschriftung(b, ausschnitt, self.fliesstext)):
                    ausschnitt |= b.rechteck
                    self.vergeben.add(i)
                    gewachsen = True
        self.abbildungen.append(ausschnitt)

    # -- Formeln -------------------------------------------------------------------------------------------------------
    def _formeln(self) -> None:
        """Abgesetzte Formeln als Ausschnitt; mehrzeilige (Brüche) samt kurzer Teile ohne Formelzeichen zusammengefasst, im
        Kasten im Kasten."""
        formeln: list[fitz.Rect] = []
        rechtecke = [self.bloecke[i].rechteck for i in self.formelbloecke if i not in self.vergeben]
        for flaeche in _vereinigen(rechtecke, FORMEL_NAEHE):
            self.vergeben.update(i for i in self.formelbloecke if _innen(self.bloecke[i], flaeche))
            for i, b in enumerate(self.bloecke):
                naehe = flaeche + (0, -FORMEL_NAEHE, 0, FORMEL_NAEHE)
                frei = i not in self.vergeben or i in self.im_kasten
                if frei and len(b.text) <= FORMEL_TEIL_HOECHSTENS and naehe.intersects(b.rechteck):
                    flaeche |= b.rechteck
                    self.vergeben.add(i)
                    if i in self.im_kasten:
                        kasten, absatz = self.im_kasten.pop(i)
                        kasten.inhalt.remove(absatz)
            formeln.append(flaeche)
        for formel in list(formeln):
            kasten = next((k for f, k in self.kaesten if f.contains(formel)), None)
            if kasten is not None:
                formeln.remove(formel)
                kasten.inhalt.append(Baustein("bild", formel.y0, formel.x0, rechteck=formel))
        for _, kasten in self.kaesten:
            kasten.inhalt.sort(key=lambda b: (b.oben, b.links))
        for flaeche in _vereinigen(self.abbildungen, 0.0) + formeln:
            self.bausteine.append(Baustein("bild", flaeche.y0, flaeche.x0, rechteck=flaeche))

    # -- Text und Code -------------------------------------------------------------------------------------------------
    def _text(self) -> None:
        for i, b in enumerate(self.bloecke):
            if i in self.vergeben:
                continue
            art = _textart(b, self.fliesstext)
            baustein = codebaustein(b.zeilen) if art == "code" else Baustein(art, b.rechteck.y0, b.rechteck.x0, text=b.text)
            self.quelle[id(baustein)] = b
            self.bausteine.append(baustein)
        for c in self.codeteile:
            self.bausteine.append(Baustein("code", c.rechteck.y0, c.rechteck.x0, titel=c.titel if c.teil == 0 else "", code=c))

    def _bilder_nummerieren(self, bausteine: list[Baustein]) -> None:
        """Jede Abbildung eng zugeschnitten, mit ihrer Nummer auf der Seite und ihrer Breite in Schriftgrößen."""
        nummer = 0
        for b in bausteine:
            for teil in [b, *b.inhalt]:
                if teil.art == "bild":
                    if self.zuschneiden:
                        teil.rechteck = zuschnitt(self.seite, teil.rechteck)
                    teil.bild = nummer
                    teil.breite_em = round(teil.rechteck.width / self.fliesstext, 2) if self.fliesstext else None
                    nummer += 1


def _bauen(seite: fitz.Page, codeteile: list[Codeteil] | None, zuschneiden: bool, schicht: textschicht.Schicht) -> list[Baustein]:
    if schicht.erkennung is not None and schicht.erkennung.markdown:     # nachgebessert (BF-118): die Gestalt kommt aus dem Markdown
        return nachgebessert.bausteine(seite, schicht.erkennung, zuschneiden)
    return _Seitenbau(seite, codeteile or [], zuschneiden, schicht).bauen()


def seitenaufbau(seite: fitz.Page, codeteile: list[Codeteil] | None = None, zuschneiden: bool = True,
                 erkennung: Seitenerkennung | None = None) -> list[Baustein]:
    """Die Bausteine einer Seite in Lesereihenfolge (siehe Beschreibung des Pakets); `zuschneiden` False spart den engen
    Ausschnitt der Abbildungen (für die Erkennung der Codestellen, die nur den Text braucht). `erkennung`: die Erkennung der
    Seite, falls es eine gibt; ob sie gilt, entscheidet die Textschicht (texterkennung/textschicht.py)."""
    return _bauen(seite, codeteile, zuschneiden, textschicht.schicht(seite, erkennung))


def abbildungen(seite: fitz.Page, codeteile: list[Codeteil] | None = None, erkennung: Seitenerkennung | None = None
                ) -> list[fitz.Rect]:
    """Die Ausschnitte der Abbildungen einer Seite, nummeriert wie in `seitenaufbau` (ab 0, mit denselben Codestellen und
    derselben Erkennung)."""
    return [t.rechteck for b in seitenaufbau(seite, codeteile, erkennung=erkennung) for t in [b, *b.inhalt] if t.art == "bild"]


# -- Über den Seitenwechsel ----------------------------------------------------------------------------------------------

def _geht_weiter(vorn: list[Baustein], hinten: list[Baustein]) -> bool:
    """Endet die Seite `vorn` mit einem Absatz mitten im Satz, den die Seite `hinten` mit ihrem ersten Absatz fortsetzt?
    Eine Seite aus nur diesem Absatz gibt ihn nicht weiter."""
    if len(vorn) < 2 or not hinten:
        return False
    ende, anfang = vorn[-1], hinten[0]
    return ende.art == "absatz" and anfang.art == "absatz" and not SATZENDE.search(ende.text.rstrip())


def ueber_seitenwechsel(seiten: dict[int, list[Baustein]]) -> None:
    """Ein Absatz, der mitten im Satz über den Seitenwechsel geht, steht ganz am Anfang der nächsten Seite. Entschieden wird
    je Paar von Seiten an ihrem gelesenen Inhalt, also unabhängig davon, welche Seiten zusammen geladen werden."""
    weiter = [nr for nr in sorted(seiten) if nr + 1 in seiten and _geht_weiter(seiten[nr], seiten[nr + 1])]
    for nr in weiter:
        ende = seiten[nr].pop()
        anfang = seiten[nr + 1][0]
        anfang.text = verbinde([ende.text, anfang.text])


def seiten_lesen(pfad: Path, ab: int, anzahl: int, codeteile: dict[int, list[Codeteil]] | None = None,
                 erkennungen: Erkennungen | None = None) -> tuple[int, list[Textseite]]:
    """Gesamtzahl der Seiten und die Seiten ab `ab` (Dateiseite, ab 1) mit ihren Bausteinen und ihrer Textschicht;
    `codeteile` und `erkennungen` je Dateiseite. Die Seite davor und danach werden mitgelesen, für Absätze über den
    Seitenwechsel."""
    codeteile, erkennungen = codeteile or {}, erkennungen or {}
    with fitz.open(str(pfad)) as doc:
        gesamt = doc.page_count
        bis = min(ab + anzahl - 1, gesamt)
        von, nach = max(1, ab - 1), min(bis + 1, gesamt)
        schichten = {nr: textschicht.schicht(doc[nr - 1], erkennungen.get(nr)) for nr in range(von, nach + 1)}
        seiten = {nr: _bauen(doc[nr - 1], codeteile.get(nr), True, s) for nr, s in schichten.items()}
    ueber_seitenwechsel(seiten)
    return gesamt, [Textseite(nr, seiten[nr], schichten[nr].art) for nr in range(ab, bis + 1)]


def abbildung_png(pfad: Path, seite: int, nr: int, zoom: float = 2.5, codeteile: dict[int, list[Codeteil]] | None = None,
                  erkennungen: Erkennungen | None = None) -> bytes | None:
    """Abbildung `nr` der Dateiseite `seite` als PNG, genau der Ausschnitt des Bausteins; None, wenn es sie nicht gibt."""
    with fitz.open(str(pfad)) as doc:
        if not 1 <= seite <= doc.page_count:
            return None
        blatt = doc[seite - 1]
        ausschnitte = abbildungen(blatt, (codeteile or {}).get(seite), (erkennungen or {}).get(seite))
        if not 0 <= nr < len(ausschnitte):
            return None
        return blatt.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=ausschnitte[nr], alpha=False).tobytes("png")
