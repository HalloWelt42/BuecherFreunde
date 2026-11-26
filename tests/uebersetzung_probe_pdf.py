"""Ein erfundenes technisches PDF für die Tests der Übersetzung (BF-71, docs/neubau/UEBERSETZUNG.md, Prüfen der Arbeit 3):
Überschriften in drei Stufen, ein Absatz über einen Seitenwechsel (mit Trennung genau an der Bruchstelle), einer über einen
Spaltenwechsel, zwei Spalten auf einer Seite, Liste, Tabelle mit Linien, Code in Festbreite mit Titel, Fußnote mit Zeichen im
Satz, Abbildung (Zeichnung mit Beschriftung im Bild) mit Bildunterschrift, Kopf- und Fußzeile mit Seitenzahl, Silbentrennung
am Zeilenende, gedruckte Seiten ab 11 und ein Inhaltsverzeichnis. Alle Texte sind selbst geschrieben.

Absätze werden wie in einem Satzprogramm umbrochen (so viele Wörter je Zeile, wie hineinpassen; "|" ist eine Trennstelle, an
der ein Wort mit Bindestrich bricht, wenn sein Anfang noch passt). `LESEFOLGE` nennt jeden Block, wie er zu lesen ist (Art,
Text ohne Trennung, Dateiseite, auf der er beginnt, Stufe); `IM_BILD` die Fläche der Zeichnung, deren Beschriftung nur im
Bild steht."""

from __future__ import annotations

from dataclasses import dataclass

import fitz

BREITE, HOEHE = 595, 842
LINKS, RECHTS = 72, 523
SPALTE_LINKS, SPALTE_RECHTS = (72.0, 290.0), (305.0, 523.0)
GROESSE = 10
ABSTAND = 13                 # Zeilenabstand im Fließtext
NACH_ABSATZ = 7              # zusätzlicher Abstand nach einem Absatz
KOPF = "Gardening with Small Machines"
ERSTE_GEDRUCKTE = 11
TRENNSTELLE = "|"

Teil = tuple[str, str]       # Text und Schrift: helv, hebo (fett), heit (kursiv), cour (Festbreite), hoch (Fußnotenzeichen),
                             # zeichen (eingebettet, für das Aufzählungszeichen)
Zeile = list[Teil]


@dataclass
class Erwartet:
    art: str                 # ueberschrift, absatz, listenpunkt, tabellenzelle, bildunterschrift, fussnote, code
    text: str
    seite: int               # Dateiseite, auf der der Block beginnt
    stufe: int = 0


LESEFOLGE: list[Erwartet] = []
IM_BILD: list[tuple[int, fitz.Rect]] = []        # Dateiseite und Fläche der Zeichnung; Wörter darin gehören zum Bild


ZEICHEN = fitz.Font("cjk")   # die Schriften der PDF-Grundausstattung kennen kein Aufzählungszeichen


def _laenge(text: str, schrift: str, groesse: float) -> float:
    if schrift == "hoch":
        return fitz.get_text_length(text, "helv", groesse * 0.6)
    if schrift == "zeichen":
        return ZEICHEN.text_length(text, groesse)
    return fitz.get_text_length(text, schrift, groesse)


def umbrechen(teile: list[Teil], breite: float, groesse: float = GROESSE) -> list[Zeile]:
    """Greedy wie ein Satzprogramm: Wort für Wort, solange es passt; an einer Trennstelle bricht ein Wort mit Bindestrich."""
    woerter: list[list[Teil]] = []                       # ein Wort kann aus Stücken in verschiedenen Schriften bestehen
    offen = False                                        # seit dem letzten Stück kam kein Leerzeichen: das Wort geht weiter
    for text, schrift in teile:
        for i, stueck in enumerate(text.split(" ")):
            if i > 0:
                offen = False
            if not stueck:
                continue
            if offen:
                woerter[-1].append((stueck, schrift))
            else:
                woerter.append([(stueck, schrift)])
            offen = True

    def breite_von(wort: list[Teil]) -> float:
        return sum(_laenge(t.replace(TRENNSTELLE, ""), s, groesse) for t, s in wort)

    zeilen: list[list[list[Teil]]] = [[]]
    platz = breite
    leer = _laenge(" ", "helv", groesse)
    for wort in woerter:
        noetig = breite_von(wort) + (leer if zeilen[-1] else 0)
        if noetig <= platz:
            zeilen[-1].append(wort)
            platz -= noetig
            continue
        teil = _trennen(wort, platz - (leer if zeilen[-1] else 0), groesse)
        if teil is not None:
            vorn, hinten = teil
            zeilen[-1].append(vorn)
            wort = hinten
        zeilen.append([wort])
        platz = breite - breite_von(wort)
    aus = []
    for z in zeilen:
        zeile: Zeile = []
        for i, wort in enumerate(z):
            for j, (t, s) in enumerate(wort):
                t = t.replace(TRENNSTELLE, "")
                zeile.append((("" if i == 0 or j > 0 else " ") + t, s))
        aus.append(zeile)
    return aus


def _trennen(wort: list[Teil], platz: float, groesse: float) -> tuple[list[Teil], list[Teil]] | None:
    """Das Wort an seiner letzten Trennstelle, deren Anfang samt Bindestrich noch passt."""
    if len(wort) != 1 or TRENNSTELLE not in wort[0][0]:
        return None
    text, schrift = wort[0]
    stellen = [i for i, c in enumerate(text) if c == TRENNSTELLE]
    for i in reversed(stellen):
        vorn = text[:i].replace(TRENNSTELLE, "") + "-"
        if _laenge(vorn, schrift, groesse) <= platz:
            return [(vorn, schrift)], [(text[i + 1:], schrift)]
    return None


def zeilentext(zeilen: list[Zeile]) -> str:
    """Der Text eines Blocks, wie er zu lesen ist: Zeilen mit Leerzeichen verbunden, Trennung am Zeilenende aufgelöst."""
    aus = ""
    for z in zeilen:
        t = "".join(text for text, _ in z)
        if aus.endswith("-") and t[:1].islower():
            aus = aus[:-1] + t
        else:
            aus = f"{aus} {t}" if aus else t
    return aus


class Blatt:
    """Eine Seite mit Kopf- und Fußzeile (ohne `rahmen` ohne) und der laufenden Stelle `y` (Grundlinie der nächsten Zeile)."""

    def __init__(self, doc: fitz.Document, nr: int, rahmen: bool = True) -> None:
        self.seite = doc.new_page(width=BREITE, height=HOEHE)
        self.seite.insert_font(fontname="zeichen", fontbuffer=ZEICHEN.buffer)
        self.nr = nr
        self.y = 95.0
        self.spalte = (float(LINKS), float(RECHTS))
        if not rahmen:
            return
        self.zeile([(KOPF, "heit")], groesse=8, y=42)
        self.zeile([("Chapter notes", "helv")], x=470, groesse=8, y=42)
        gedruckt = str(ERSTE_GEDRUCKTE + nr - 1)
        self.zeile([(gedruckt, "helv")], x=BREITE / 2 - _laenge(gedruckt, "helv", 9) / 2, groesse=9, y=812)

    def zeile(self, teile: Zeile, x: float | None = None, groesse: float = GROESSE, y: float | None = None) -> float:
        x = self.spalte[0] if x is None else x
        y = self.y if y is None else y
        for text, schrift in teile:
            if schrift == "hoch":
                self.seite.insert_text((x, y - groesse * 0.35), text, fontname="helv", fontsize=groesse * 0.6)
            else:
                self.seite.insert_text((x, y), text, fontname=schrift, fontsize=groesse)
            x += _laenge(text, schrift, groesse)
        return x

    def zeilen(self, zeilen: list[Zeile], x: float | None = None, groesse: float = GROESSE, abstand: float = ABSTAND) -> None:
        for z in zeilen:
            self.zeile(z, x=x, groesse=groesse)
            self.y += abstand

    def absatz(self, teile: list[Teil], art: str = "absatz") -> list[Zeile]:
        zeilen = umbrechen(teile, self.spalte[1] - self.spalte[0])
        LESEFOLGE.append(Erwartet(art, zeilentext(zeilen), self.nr))
        self.zeilen(zeilen)
        self.y += NACH_ABSATZ
        return zeilen

    def ueberschrift(self, text: str, stufe: int) -> None:
        groesse = {1: 20, 2: 14, 3: 11.5}[stufe]
        self.y += groesse * 0.6
        LESEFOLGE.append(Erwartet("ueberschrift", text, self.nr, stufe))
        self.zeile([(text, "hebo")], groesse=groesse)
        self.y += groesse * 1.2 + 4


# -- Die Seiten ----------------------------------------------------------------------------------------------------------------

def _seite_1(doc: fitz.Document) -> None:
    b = Blatt(doc, 1)
    b.ueberschrift("1 Getting Started", 1)
    b.absatz([("A small garden robot can water ", "helv"), ("sixteen", "heit"), (" beds in one hour. It needs only a ", "helv"),
              ("charged battery", "hebo"), (" and a full tank.", "helv"), ("1", "hoch"),
              (" Most owners start with one machine and add more later.", "helv")])
    b.ueberschrift("1.1 The First Machine", 2)
    b.absatz([("The first machine should be small and quiet. A heavy robot presses the soil and leaves deep tracks between "
               "the rows, which makes the next round of watering for all the small young plants less ef|fec|tive. Choose wide "
               "wheels and a light frame.", "helv")])
    for text in ("Check the wheels before every run.",
                 "Clean the filter once a week, even when the water looks clear and the tank shows no dirt at all after the "
                 "last round.",
                 "Keep a spare battery in a dry place."):
        zeilen = umbrechen([(text, "helv")], RECHTS - LINKS - 18)
        LESEFOLGE.append(Erwartet("listenpunkt", "\u2022 " + zeilentext(zeilen), b.nr))
        b.zeile([("\u2022", "zeichen")], x=LINKS + 6)
        b.zeilen(zeilen, x=LINKS + 18)
        b.y += 3
    b.y += NACH_ABSATZ
    b.absatz([("After a few days the robot knows the garden. It stores a map of every bed and returns to its station when "
               "the battery runs low.", "helv")])
    LESEFOLGE.append(Erwartet("fussnote", "1 Measured on a dry morning in early summer.", b.nr))
    b.seite.draw_line((LINKS, 752), (LINKS + 120, 752), width=0.5)
    b.zeile([("1", "hoch"), (" Measured on a dry morning in early summer.", "helv")], groesse=8, y=766)


def _seite_2_und_3(doc: fitz.Document) -> None:
    b = Blatt(doc, 2)
    b.ueberschrift("1.1.1 Soil and Water", 3)
    b.absatz([("Sandy soil drains fast and needs short, frequent rounds. Heavy clay holds water for a long time, so the "
               "robot waits longer between two rounds.", "helv")])
    LESEFOLGE.append(Erwartet("bildunterschrift", "Table 1: Daily water needs", b.nr))
    b.zeile([("Table 1: Daily water needs", "heit")], groesse=9)
    b.y += 8
    tabelle = [["Plant", "Litres", "Rounds"], ["Tomato", "2", "Morning"], ["Lettuce", "1", "Evening"]]
    spalten = [0, 150, 300, 451]
    oben = b.y - 2
    for r, reihe in enumerate(tabelle):
        for s, zelle in enumerate(reihe):
            LESEFOLGE.append(Erwartet("tabellenzelle", zelle, b.nr))
            b.zeile([(zelle, "hebo" if r == 0 else "helv")], x=LINKS + spalten[s] + 6, y=b.y + 12)
        b.y += 20
    for r in range(len(tabelle) + 1):
        b.seite.draw_line((LINKS, oben + 20 * r), (RECHTS, oben + 20 * r), width=0.6)
    for x in spalten:
        b.seite.draw_line((LINKS + x, oben), (LINKS + x, oben + 20 * len(tabelle)), width=0.6)
    # ein Absatz am Fuß der Seite, der auf der nächsten weitergeht; das letzte Wort der Seite ist getrennt
    b.y = 726
    zeilen = umbrechen([("Water that runs off the surface is lost for the plants. A slow drip close to the roots is better than "
                         "a strong jet from above, and it also keeps the leaves and the stems quite dry for long hours. Good "
                         "ir|ri|ga|tion saves water, time and power for the next round.", "helv")], RECHTS - LINKS)
    LESEFOLGE.append(Erwartet("absatz", zeilentext(zeilen), b.nr))
    b.zeilen(zeilen[:2])
    b = Blatt(doc, 3)
    b.zeilen(zeilen[2:])
    b.y += NACH_ABSATZ
    # Abbildung: eine Zeichnung mit Beschriftung im Bild, darunter die Bildunterschrift
    flaeche = fitz.Rect(200, b.y, 400, b.y + 110)
    IM_BILD.append((b.nr, fitz.Rect(flaeche)))
    b.seite.draw_rect(flaeche, color=(0, 0, 0.6), fill=(0.85, 0.9, 1), width=1)
    b.seite.draw_circle((260, b.y + 55), 30, color=(0, 0.4, 0), fill=(0.8, 1, 0.8))
    b.seite.draw_line((290, b.y + 55), (380, b.y + 90), width=2)
    b.zeile([("pump", "helv")], x=248, groesse=8, y=b.y + 58)
    b.zeile([("hose", "helv")], x=335, groesse=8, y=b.y + 72)
    b.y += 128
    LESEFOLGE.append(Erwartet("bildunterschrift", "Figure 1: The pump and its hose.", b.nr))
    b.zeile([("Figure 1: The pump and its hose.", "heit")], x=232, groesse=9)
    b.y += 30
    b.absatz([("Start the pump from the command line:", "helv")])
    LESEFOLGE.append(Erwartet("bildunterschrift", "Listing 1: Starting the pump", b.nr))
    b.zeile([("Listing 1: Starting the pump", "heit")], groesse=9)
    b.y += 18
    code = ["from garden import Pump", "", "pump = Pump(port=3)", "pump.start(litres=2)  # one bed"]
    LESEFOLGE.append(Erwartet("code", "\n".join(code), b.nr))
    b.seite.draw_rect(fitz.Rect(LINKS, b.y - 12, RECHTS, b.y - 12 + 12 * len(code) + 8), color=(0.6, 0.6, 0.6),
                      fill=(0.95, 0.95, 0.95), width=0.5)
    for zeile in code:
        if zeile:
            b.zeile([(zeile, "cour")], x=LINKS + 8, groesse=9)
        b.y += 12
    b.y += 22
    b.absatz([("The pump stops by itself when the tank is empty. The status light then turns red.", "helv")])


def _seite_4(doc: fitz.Document) -> None:
    b = Blatt(doc, 4)
    b.ueberschrift("1.2 Two Columns", 2)
    oben = b.y
    b.spalte = SPALTE_LINKS
    zeilen = umbrechen([("Many gardens have two kinds of beds. Raised beds dry out quickly in the sun, while low beds near the "
                         "fence stay wet for days. The robot learns both kinds and plans its rounds so that no bed is forgotten "
                         "and none gets too much water. On hot days it adds a second round for the raised beds.", "helv")],
                       SPALTE_LINKS[1] - SPALTE_LINKS[0])
    LESEFOLGE.append(Erwartet("absatz", zeilentext(zeilen), b.nr))
    b.zeilen(zeilen[:5])
    b.spalte, b.y = SPALTE_RECHTS, oben
    b.zeilen(zeilen[5:])
    b.y += NACH_ABSATZ
    b.absatz([("In winter the robot rests in its station and charges slowly.", "helv")])
    unten = max(oben + 5 * ABSTAND, b.y)
    b.spalte, b.y = (float(LINKS), float(RECHTS)), unten + NACH_ABSATZ + 4
    b.absatz([("Both columns end here, and this paragraph runs across the whole width of the page again.", "helv")])


def _seite_5(doc: fitz.Document) -> None:
    b = Blatt(doc, 5)
    b.ueberschrift("2 Watering the Beds", 1)
    b.absatz([("Every bed has its own plan. The robot reads the plan in the morning and starts with the driest bed.", "helv")])
    b.ueberschrift("2.1 Morning Rounds", 2)
    b.absatz([("Early rounds lose less water to the sun. Most plants also like a cool drink before the day gets warm.", "helv")])
    # ein Rasterbild als Abbildung: es kommt unverändert ins EPUB
    b.seite.insert_image(fitz.Rect(LINKS, b.y, LINKS + 180, b.y + 120), pixmap=rasterbild())
    b.y += 138
    LESEFOLGE.append(Erwartet("bildunterschrift", "Figure 2: A bed at sunrise.", b.nr))
    b.zeile([("Figure 2: A bed at sunrise.", "heit")], groesse=9)
    b.y += 30
    b.absatz([("The next chapter shows how the robot finds its way back in the dark.", "helv")])


def rasterbild() -> fitz.Pixmap:
    """Ein kleines Bild mit Verlauf, jedes Mal gleich."""
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 40), False)
    for x in range(60):
        for y in range(40):
            pix.set_pixel(x, y, (4 * x, 200 - 4 * y, 120))
    return pix


INHALT = [[1, "1 Getting Started", 1], [2, "1.1 The First Machine", 1], [3, "1.1.1 Soil and Water", 2],
          [2, "1.2 Two Columns", 4], [1, "2 Watering the Beds", 5], [2, "2.1 Morning Rounds", 5]]


def probe_pdf(mit_verzeichnis: bool = True, mit_beschriftungen: bool = True) -> bytes:
    """Das Probe-PDF; ohne Verzeichnis zerfällt es nach den Überschriften der obersten Stufe, ohne Beschriftungen der
    Seiten (PageLabels) zählen die Marken nach den Seiten des PDF."""
    LESEFOLGE.clear()
    IM_BILD.clear()
    doc = fitz.open()
    _seite_1(doc)
    _seite_2_und_3(doc)
    _seite_4(doc)
    _seite_5(doc)
    doc.set_metadata({"title": "Gardening with Small Machines", "author": "Ada Example"})
    if mit_verzeichnis:
        doc.set_toc(INHALT)
    if mit_beschriftungen:
        doc.set_page_labels([{"startpage": 0, "prefix": "", "style": "D", "firstpagenum": ERSTE_GEDRUCKTE}])
    doc.subset_fonts()
    return doc.tobytes(garbage=3, deflate=True)


def scan_pdf(seiten: int = 2) -> bytes:
    """Ein PDF ohne Textschicht: jede Seite nur ein Bild (wie ein Scan)."""
    doc = fitz.open()
    bild = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 80), False)
    bild.clear_with(200)
    for _ in range(seiten):
        seite = doc.new_page(width=BREITE, height=HOEHE)
        seite.insert_image(seite.rect, pixmap=bild)
    return doc.tobytes()
