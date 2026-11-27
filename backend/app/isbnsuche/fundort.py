"""Wo im Buch eine ISBN steht. Literaturliste, Anmerkungen und Verlagsanzeige an ihrer Überschrift (gilt ab dort, bis ein neuer
Teil beginnt), das Impressum an seinen Angaben (Copyright, Nationalbibliothek, Auflage), die Rückseite an Preis oder Strichcode
auf den letzten Seiten, die Titelei an den ersten Seiten; alles andere ist Text. Die Überschrift "Impressum" oder ein sicheres
Zeichen ("©", "Alle Rechte vorbehalten") beginnt das Impressum auch mitten auf einer Seite und beendet eine Liste davor.

Überschriften in der Titelei zählen nicht, dort stehen sie im Inhaltsverzeichnis. Eine Verlagsanzeige vorn im Buch endet mit
ihrer Seite; erst im hinteren Teil gilt sie auch für die Seiten danach, wie Literaturliste und Anmerkungen."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.app.isbnsuche.modelle import Fundort

TITELEI_SEITEN = 6                 # so viele Seiten vorn sind mindestens Titelei
TITELEI_ANTEIL = 0.03              # bei langen Büchern ein Anteil
IMPRESSUM_VORN = 0.12              # ein Impressum steht in diesem Anteil vorn ...
IMPRESSUM_HINTEN = 0.1             # ... oder hinten
IMPRESSUM_SEITEN = 12              # vorn mindestens so viele Seiten
RUECKSEITE_SEITEN = 2              # die letzten so vielen Seiten können die Rückseite sein
HINTERER_TEIL = 0.75               # ab hier gilt eine Verlagsanzeige über ihre Seite hinaus
UEBERSCHRIFT_LAENGE = 80           # eine längere Zeile ist keine Überschrift

_NUMMER = r"(?:[\divx]+(?:\.\d+)*\.?\s+)?"
_LITERATUR = re.compile(
    rf"^{_NUMMER}(?:(?:weiterführende|ausgewählte|verwendete|zitierte)\s+)?(?:literatur(?:verzeichnis|liste|hinweise|angaben)?|quellen(?:verzeichnis|"
    r"\s+und\s+literatur)?|literatur\s+und\s+quellen|bibliogra(?:ph|f)ie|bibliography|references|further reading|works cited|sources)\s*:?$", re.IGNORECASE)
_ANMERKUNGEN = re.compile(rf"^{_NUMMER}(?:anmerkungen|fußnoten|fussnoten|endnoten|nachweise|notes|endnotes)\s*:?$", re.IGNORECASE)
_VERLAGSANZEIGE = re.compile(
    r"^(?:(?:ebenfalls|außerdem|ausserdem|bereits|auch)\s+(?:im\s+.{1,60}?\s+)?(?:erschienen|lieferbar|bei|im|von)\b|weitere\s+(?:bücher|titel|bände|romane|"
    r"krimis)\b|lieferbare\s+titel|mehr\s+(?:von|aus)\b|aus\s+unserem\s+programm|unser\s+programm|leseprobe\b|von\s+.{1,60}?\s+(?:sind|ist)\s+(?:außerdem\s+|"
    r"bereits\s+|ebenfalls\s+)?(?:bei\s+.{1,40}?\s+)?erschienen)", re.IGNORECASE)
_NEUER_TEIL = re.compile(rf"^{_NUMMER}(?:register|index|personenregister|sachregister|ortsregister|glossar|inhalt|inhaltsverzeichnis|kapitel\s+\d+|\d+\.\s*kapitel|"
                         r"teil\s+[ivx\d]+|epilog|prolog|nachwort|vorwort|danksagung|dank|über\s+(?:den|die)\s+autor(?:in)?|zum\s+autor|zur\s+autorin)\s*:?$",
                         re.IGNORECASE)
_IMPRESSUM_SICHER = re.compile(r"©|\(c\)\s*\d{4}|copyright|alle rechte vorbehalten|all rights reserved|bibliogra(?:f|ph)ische information|"
                               r"nationalbibliothek|printed in|cip-titelaufnahme", re.IGNORECASE)
_IMPRESSUM_HINWEIS = re.compile(r"\bauflage\b|gesamtherstellung|umschlaggestaltung|umschlagabbildung|\blektorat\b|\bsatz\b|\bherstellung\b|"
                                r"gedruckt auf|\bdruck und bindung\b|\boriginalausgabe\b|\blizenzausgabe\b", re.IGNORECASE)
# eine Zeile, mit der auf ihrer Seite ein Impressum beginnt, auch mitten in einer Liste davor (E-Books legen Verlagsanzeige,
# Quellen und Impressum oft in ein Dokument): die Überschrift oder ein sicheres Zeichen; "Copyright" allein steht auch in Titeln
_IMPRESSUM_ZEILE = re.compile(r"^impressum\s*:?$|©|\(c\)\s*\d{4}|alle rechte vorbehalten|all rights reserved", re.IGNORECASE)
_RUECKSEITE = re.compile(r"\d+[,.]\d{2}\s*(?:€|eur\b)|€\s*\d|\((?:d|a|ch)\)|\bsfr\b|\bchf\b|\b97[89]\s\d{6}\s\d{6}\b", re.IGNORECASE)


@dataclass(frozen=True)
class Buchlage:
    """Was der Fundort vom ganzen Buch braucht: je Seite die Abschnitte (ab welcher Lage was gilt) und welche Seite ein Impressum ist."""

    abschnitte: list[list[tuple[int, Fundort | None]]]
    impressum: list[bool]
    rueckseite: list[bool]         # eine der letzten Seiten mit Preis oder Strichcode
    titelei: int                   # so viele Seiten vorn sind Titelei

    @property
    def seitenzahl(self) -> int:
        return len(self.impressum)


def _abschnitt(zeile: str, titelei: bool) -> tuple[Fundort | None, bool] | None:
    """Was eine Zeile beginnt: (Abschnitt, gilt über die Seite hinaus) oder None, wenn sie nichts beginnt. In der Titelei zählen nur
    eine Verlagsanzeige ("Von ... ist außerdem erschienen") und das Impressum, Überschriften dort gehören zum Inhaltsverzeichnis.
    Ein Impressum gilt bis zum Ende seiner Seite, eine Verlagsanzeige nur im hinteren Teil darüber hinaus."""
    z = " ".join(zeile.split())
    if not z:
        return None
    if _VERLAGSANZEIGE.match(z):
        return Fundort.VERLAGSANZEIGE, False
    if _IMPRESSUM_ZEILE.search(z):
        return Fundort.IMPRESSUM, False
    if titelei or len(z) > UEBERSCHRIFT_LAENGE:
        return None
    if _LITERATUR.match(z):
        return Fundort.LITERATURLISTE, True
    if _ANMERKUNGEN.match(z):
        return Fundort.ANMERKUNGEN, True
    if _NEUER_TEIL.match(z):
        return None, True
    return None


def _ist_impressum(text: str) -> bool:
    return bool(_IMPRESSUM_SICHER.search(text)) or len(_IMPRESSUM_HINWEIS.findall(text)) >= 2


def lage(seiten: list[str]) -> Buchlage:
    n = len(seiten)
    titelei = max(TITELEI_SEITEN, round(n * TITELEI_ANTEIL))
    vorn, hinten = max(IMPRESSUM_SEITEN, round(n * IMPRESSUM_VORN)), n - max(1, round(n * IMPRESSUM_HINTEN))
    abschnitte: list[list[tuple[int, Fundort | None]]] = []
    jetzt: Fundort | None = None
    for nr, text in enumerate(seiten):
        hier: list[tuple[int, Fundort | None]] = [(0, jetzt)]
        lage_im_text = 0
        for zeile in text.split("\n"):
            beginnt = _abschnitt(zeile, nr < titelei)
            if beginnt is not None:
                ort, bleibt = beginnt
                jetzt = ort if bleibt or (ort is Fundort.VERLAGSANZEIGE and nr >= n * HINTERER_TEIL) else None
                hier.append((lage_im_text, ort))
            lage_im_text += len(zeile) + 1
        abschnitte.append(hier)
    impressum = [(nr < vorn or nr >= hinten) and _ist_impressum(t) for nr, t in enumerate(seiten)]
    rueckseite = [nr >= n - RUECKSEITE_SEITEN and bool(_RUECKSEITE.search(t)) for nr, t in enumerate(seiten)]
    return Buchlage(abschnitte=abschnitte, impressum=impressum, rueckseite=rueckseite, titelei=titelei)


def abschnitt(buch: Buchlage, seite: int, stelle: int) -> Fundort | None:
    """Der Abschnitt, der an dieser Stelle gilt; None: gewöhnlicher Text."""
    gilt: Fundort | None = None
    for ab, ort in buch.abschnitte[seite]:
        if ab > stelle:
            break
        gilt = ort
    return gilt


def fundort(buch: Buchlage, seite: int, stelle: int) -> Fundort:
    """Wo diese Stelle liegt. Eine Überschrift auf derselben Seite davor gilt vor allem anderen; Impressum und Rückseite mit Preis
    oder Strichcode gelten vor einem Abschnitt von früheren Seiten; die letzte Seite ohne solchen Abschnitt ist die Rückseite."""
    davor_auf_der_seite = [ort for ab, ort in buch.abschnitte[seite][1:] if ab <= stelle]
    if davor_auf_der_seite and davor_auf_der_seite[-1] is not None:
        return davor_auf_der_seite[-1]
    if buch.impressum[seite]:
        return Fundort.IMPRESSUM
    if buch.rueckseite[seite]:
        return Fundort.RUECKSEITE
    if (ort := abschnitt(buch, seite, stelle)) is not None:
        return ort
    if seite == buch.seitenzahl - 1 and seite >= buch.titelei:
        return Fundort.RUECKSEITE
    if seite < buch.titelei:
        return Fundort.TITELEI
    return Fundort.TEXT


def ohne_einleitung(eintrag: str) -> str:
    """Ein Eintrag einer Verlagsanzeige ohne ihre einleitenden Worte ("Ebenfalls im Beispielverlag: ...")."""
    if _VERLAGSANZEIGE.match(eintrag) and ":" in eintrag[:UEBERSCHRIFT_LAENGE]:
        return eintrag.split(":", 1)[1].strip()
    return eintrag
