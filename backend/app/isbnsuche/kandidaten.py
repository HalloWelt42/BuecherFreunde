"""Aus den Funden die Kandidaten: je ISBN einer (ISBN-10 und ISBN-13, mit und ohne Striche), mit Fundstellen, Stufe aus dem Text
und Rangfolge. Geordnet wird nach Stufe, dann nach Fundort (Impressum vor Rückseite vor Text), dann Druck vor E-Book (BF-111),
dann nach der Zahl der Funde und wo die Nummer zuerst steht."""

from __future__ import annotations

import html
import re
from collections.abc import Iterable

from backend.app.isbnsuche import erkennung
from backend.app.isbnsuche import fundort as orte
from backend.app.isbnsuche.erkennung import Fund
from backend.app.isbnsuche.modelle import AUSGABEN, FREMDE_ORTE, FUNDORTE, Ausgabe, Einstufung, Fundort, Fundstelle, Kandidat
from backend.app.quellen import isbn as nummern
from backend.app.quellen.abgleich import STUFEN, Abgleich, Stufe, echte_autoren, natuerlich, text_abgleich
from backend.app.quellen.modelle import Angaben, Buchfrage
from backend.app.quellen.regeln import REGELN
from backend.app.services.autorennamen import zerlegen

GANZE_SEITE = frozenset({Fundort.IMPRESSUM, Fundort.RUECKSEITE, Fundort.TITELEI})   # hier zählt die ganze Seite als Umfeld
UMFELD_DAVOR, UMFELD_DANACH = 300, 120      # sonst so viel Text vor und nach der Nummer ...
UMFELD_ZEILEN = 2                           # ... und höchstens so viele Zeilen davor
EINTRAG_MINDESTENS = 15                     # so viel Text vor der Nummer braucht ein Eintrag, sonst gehört die Zeile davor dazu
EINTRAG_HOECHSTENS = 120                    # so lang wird ein fremder Eintrag gezeigt
SEITE_OHNE_TRENNER = 3000                   # Zeichen je Seite, wenn ein Text keine Seiten kennt (Text, MOBI)
_ISBN_AM_ENDE = re.compile(r"[\s,;:(\[]*\b(?:e-?|print-?)?isbn(?:[\s-]*1[03])?\s*[:.]?\s*$", re.IGNORECASE)
KEIN_TITEL = "kein Titel daneben"


def als_seiten(text: str, seiten: int | None = None) -> list[str]:
    """Der Text in Seiten: mit Seitenvorschub wie im Volltext, sonst etwa gleich lange Stücke (für Fundort und Lage), die nur an
    einem Zeilenende enden; so zerteilt kein Schnitt eine Nummer oder eine Überschrift."""
    if not text:
        return []
    if "\f" in text:
        return text.split("\f")
    groesse = max(len(text) // seiten, 500) if seiten else SEITE_OHNE_TRENNER
    aus, ab = [], 0
    while ab < len(text):
        bis = ab + groesse
        if bis < len(text):
            ende = text.find("\n", bis)
            if ende < 0 or ende - bis > groesse:
                ende = text.find(" ", bis)
            bis = len(text) if ende < 0 else ende + 1
        aus.append(text[ab:bis])
        ab = bis
    return aus


# -- Umfeld einer Fundstelle -------------------------------------------------------------------------------------------
def _zeilenanfang(text: str, stelle: int) -> int:
    return text.rfind("\n", 0, stelle) + 1


def _zeilen_zurueck(text: str, stelle: int, zeilen: int) -> int:
    """Der Anfang der Zeile `zeilen` Zeilen vor der Zeile von `stelle`."""
    anfang = _zeilenanfang(text, stelle)
    for _ in range(zeilen):
        if anfang == 0:
            break
        anfang = _zeilenanfang(text, anfang - 1)
    return anfang


def eintrag(text: str, fund: Fund, davor_bis: int) -> str:
    """Der Eintrag vor der Nummer in einer Liste (Literatur, Verlagsanzeige): ihre Zeile, ist die kurz, auch die davor; nie über die
    Nummer davor hinaus. Ohne "ISBN" am Ende und ohne einleitende Worte ("Ebenfalls im Verlag erschienen:")."""
    anfang = _zeilenanfang(text, fund.anfang)
    if len(_ISBN_AM_ENDE.sub("", text[anfang:fund.anfang]).strip()) < EINTRAG_MINDESTENS and anfang > 0:
        anfang = _zeilenanfang(text, anfang - 1)
    roh = " ".join(text[max(anfang, davor_bis):fund.anfang].split())
    roh = orte.ohne_einleitung(_ISBN_AM_ENDE.sub("", roh)).strip(" ,;:.-")
    if len(roh) > EINTRAG_HOECHSTENS:
        roh = "..." + roh[-EINTRAG_HOECHSTENS:].split(" ", 1)[-1]
    return roh


def umfeld(text: str, fund: Fund, ort: Fundort, davor_bis: int) -> str:
    """Der Text, in dem Titel und Autor stehen müssten: Impressum, Rückseite und Titelei ganz; in Listen nur der Eintrag; sonst die
    Zeilen um die Nummer."""
    if ort in GANZE_SEITE:
        return text
    if ort in FREMDE_ORTE:
        return eintrag(text, fund, davor_bis)
    anfang = max(_zeilen_zurueck(text, fund.anfang, UMFELD_ZEILEN), fund.anfang - UMFELD_DAVOR)
    ende = text.find("\n", fund.ende)
    ende = min(len(text) if ende < 0 else ende, fund.ende + UMFELD_DANACH)
    return text[anfang:ende]


# -- Was die Stufe zeigt -----------------------------------------------------------------------------------------------
def _marke(text: str, an: bool) -> str:
    t = html.escape(text, quote=False)
    return f"<mark>{t}</mark>" if an and t else t


def _eigenes_markieren(text: str, namen: Iterable[str]) -> str:
    """Ein fremder Eintrag, markiert bis auf die Namen der Autoren des Buchs."""
    muster = [re.escape(n) for name in namen for n in {natuerlich(name), name} if n.strip()]
    stuecke = re.split(f"({'|'.join(muster)})", text, flags=re.IGNORECASE) if muster else [text]
    aus = []
    for n, stueck in enumerate(stuecke):
        if n % 2:
            aus.append(html.escape(stueck, quote=False))
            continue
        kern = stueck.strip(" ,;:.")
        if not kern:
            aus.append(html.escape(stueck, quote=False))
            continue
        vorn, hinten = stueck[:stueck.index(kern)], stueck[stueck.index(kern) + len(kern):]
        aus.append(html.escape(vorn, quote=False) + _marke(kern, True) + html.escape(hinten, quote=False))
    return "".join(aus)


def aus_text(frage: Buchfrage, abgleich: Abgleich, eintragstext: str) -> Einstufung:
    """Die Stufe aus dem Text, wie die Oberfläche sie zeigt: was zum Buch passt, oder der fremde Eintrag."""
    autoren = [natuerlich(a) for a in echte_autoren(frage.autoren)]
    if abgleich.stufe is Stufe.FREMD:
        was = _eigenes_markieren(eintragstext, autoren) if eintragstext else KEIN_TITEL
    elif abgleich.stufe is Stufe.UNBEKANNT:
        was = KEIN_TITEL
    else:
        teile = [] if "Autor steht nicht daneben" in abgleich.gruende else [", ".join(autoren)]
        teile += [] if "nur der Autor steht daneben" in abgleich.gruende else [frage.titel]
        was = html.escape(", ".join(t for t in teile if t), quote=False)
    return Einstufung(stufe=abgleich.stufe, was=was, warum=", ".join(abgleich.gruende))


def aus_quelle(abgleich: Abgleich, fund: Angaben) -> Einstufung:
    """Die Stufe aus dem Fund einer Quelle: Titel, Autoren und Jahr, was abweicht, markiert."""
    teile = [_marke(fund.titel, abgleich.titel_anders), _marke(", ".join(fund.autoren), abgleich.autor_anders), str(fund.jahr or "")]
    regel = REGELN.get(fund.quelle)
    return Einstufung(stufe=abgleich.stufe, quelle=fund.quelle, basis=regel.name if regel else fund.quelle, was=", ".join(t for t in teile if t),
                      warum=", ".join(abgleich.gruende))


# -- Kandidaten --------------------------------------------------------------------------------------------------------
def _stellen(seiten: list[str], funde: list[Fund], orte_je_fund: dict[int, Fundort]) -> list[Fundstelle]:
    """Funde derselben Nummer auf einer Seite, deren Ausschnitte sich überschneiden, werden eine Stelle."""
    gesamt = sum(len(s) + 1 for s in seiten) or 1
    gruppen: list[list[Fund]] = []
    for f in funde:
        if gruppen and gruppen[-1][0].seite == f.seite and f.anfang - gruppen[-1][-1].ende <= 2 * erkennung.UMFELD:
            gruppen[-1].append(f)
        else:
            gruppen.append([f])
    stellen = []
    for g in gruppen:
        text = seiten[g[0].seite]
        von, _ = erkennung.fenster(text, g[0].anfang, g[0].ende)
        _, bis = erkennung.fenster(text, g[-1].anfang, g[-1].ende)
        stellen.append(Fundstelle(seite=g[0].seite + 1, prozent=round(g[0].lage / gesamt * 100, 1), fundort=orte_je_fund[g[0]],
                                  ausschnitt=erkennung.auszug(text, von, bis, [(f.anfang, f.ende) for f in g]), funde=len(g)))
    return stellen


def _ausgabe(funde: list[Fund], orte_je_fund: dict[int, Fundort]) -> Ausgabe:
    """Was der Text am besten Fundort über die Ausgabe sagt."""
    genannt = sorted((FUNDORTE.index(orte_je_fund[f]), AUSGABEN.index(f.ausgabe), f.ausgabe) for f in funde if f.ausgabe is not Ausgabe.OFFEN)
    return genannt[0][2] if genannt else Ausgabe.OFFEN


def _formen(isbn: str, funde: list[Fund]) -> list[str]:
    return [f for f in dict.fromkeys(" ".join(x.form.split()) for x in funde) if f != isbn]


def rang(k: Kandidat) -> tuple:
    return (STUFEN.index(k.einstufung.stufe), FUNDORTE.index(k.fundort), AUSGABEN.index(k.ausgabe), -k.funde, k.stellen[0].prozent)


def kandidaten(seiten: list[str], frage: Buchfrage) -> list[Kandidat]:
    """Alle ISBN des Buchs als Kandidaten in der Rangfolge, jeder mit seiner Stufe aus dem Text."""
    funde = erkennung.finde(seiten)
    if not funde:
        return []
    buch = orte.lage(seiten)
    orte_je_fund = {f: orte.fundort(buch, f.seite, f.anfang) for f in funde}
    davor_bis = {f: (v.ende if v and v.seite == f.seite else 0) for v, f in zip([None, *funde], funde, strict=False)}
    je_isbn: dict[str, list[Fund]] = {}
    for f in funde:
        je_isbn.setdefault(f.isbn13, []).append(f)
    aus = []
    for isbn13, liste in je_isbn.items():
        bewertet = []
        for f in liste:
            ort = orte_je_fund[f]
            text = seiten[f.seite]
            a = text_abgleich(frage, umfeld(text, f, ort, davor_bis[f]), ort in FREMDE_ORTE)
            bewertet.append((STUFEN.index(a.stufe), FUNDORTE.index(ort), a, eintrag(text, f, davor_bis[f]) if a.stufe is Stufe.FREMD else ""))
        _, _, besser, eintragstext = min(bewertet, key=lambda b: b[:2])
        isbn = nummern.mit_strichen(isbn13) or isbn13
        aus.append(Kandidat(isbn=isbn, isbn13=isbn13, formen=_formen(isbn, liste), ausgabe=_ausgabe(liste, orte_je_fund), funde=len(liste),
                            fundort=min((orte_je_fund[f] for f in liste), key=FUNDORTE.index), stellen=_stellen(seiten, liste, orte_je_fund),
                            text=aus_text(frage, besser, eintragstext)))
    return sorted(aus, key=rang)


def beste(seiten: list[str], titel: str, autor: str) -> str:
    """Die ISBN, die am besten zu Titel und Autor aus den Angaben der Datei passt, nur Ziffern; leer, wenn keine oder nur fremde im
    Text stehen. Für die Leser der Formate beim Aufnehmen."""
    eigene = [k for k in kandidaten(seiten, Buchfrage(titel=titel, autoren=zerlegen(autor))) if k.einstufung.stufe is not Stufe.FREMD]
    return eigene[0].isbn13 if eigene else ""
