"""Zeilen einer erkannten Seite (BF-109): wo die Erkennung gilt (texterkennung/textschicht.py), kommen die Zeilen aus ihr statt
aus der Textschicht, und alles Weitere (Absätze, Trennung, Überschriften, Listen, Kopf- und Fußzeilen) läuft wie bei jeder Seite.

- Eine Zeile ist eine Zeile des Programms, ihre Wörter von links nach rechts (nur sichere, `textschicht.sichere_woerter`).
- Die Schriftgröße steht in keiner Erkennung; sie kommt aus der Höhe der Wörter. Ein Wort ist so hoch wie seine Buchstaben
  reichen: mit Ober- und Unterlänge rund 0,9 Schriftgrößen, nur mit Oberlänge (Großbuchstaben, Ziffern, b d f h k l) 0,7, mit
  i j t und Umlauten 0,63, ohne beides 0,5 (gemessen an drei Schriften, je Klasse auf etwa ein Zehntel genau); Klammern und
  Schrägstriche reichen über beide. Je Zeile gilt der
  Median ihrer Wörter. Weil das ungenau bleibt, gilt eine Zeile, die weder klein noch groß genug für eine Überschrift wäre, als
  Fließtext der Seite (dessen Größe hat die Mehrheit der Zeichen).
- Grundlinie: der Fuß der Wörter ohne Unterlänge.
- Festbreite gibt es nicht (ohne Schrift kein Maß dafür); Code erkennt die Textansicht dann nur an seiner Form.
- Ein einzeln stehendes Zeichen am Zeilenanfang, als das das Programm einen kleinen Aufzählungspunkt liest (Doppelwinkel, Plus,
  Grad), vor einem Wort ist ein Aufzählungspunkt.
- Abbildungen: das Seitenbild selbst ist keine; Flächen ohne Text, die das Programm abgrenzt (Bilder in der Seite), sind es."""

from __future__ import annotations

import statistics

import fitz

from backend.app.services.textansicht.zeilen import KLEIN, RAND_OBEN, RAND_UNTEN, UEBERSCHRIFT_FAKTOR, Zeile
from backend.app.texterkennung.modelle import ErkannteZeile, Seitenerkennung, Wort
from backend.app.texterkennung.textschicht import sichere_woerter

KLAMMERN = set("()[]{}|/")            # reichen von der Oberlänge bis unter die Grundlinie
OBEN_VOLL = set("ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜ0123456789bdfhklß") | KLAMMERN
OBEN_HALB = set("ijtäöü")
UNTEN = set("gjpqyQ") | KLAMMERN
HOEHE_JE_GROESSE = {               # (Oberlänge, Unterlänge) -> Höhe eines Worts in Schriftgrößen (gemessen, siehe oben)
    ("voll", True): 0.9, ("voll", False): 0.7, ("halb", True): 0.83, ("halb", False): 0.63,
    ("", True): 0.7, ("", False): 0.5,
}
UNTERLAENGE = 0.2                   # Schriftgrößen: so weit reicht eine Unterlänge unter die Grundlinie
ZEICHENBREITE = 0.5                 # Schriftgrößen: Breite eines Zeichens für die Einrückung (wie ohne Festbreite)
PUNKT_GELESEN = {chr(0xAB), chr(0xBB), "+", chr(0xB0)}   # so liest das Programm einen kleinen Aufzählungspunkt (als Codepunkte)
PUNKT = chr(0x2022)


def _oberlaenge(wort: str) -> str:
    if any(c in OBEN_VOLL for c in wort):
        return "voll"
    return "halb" if any(c in OBEN_HALB for c in wort) else ""


def _unterlaenge(wort: str) -> bool:
    return any(c in UNTEN for c in wort)


def _groesse_des_worts(w: Wort) -> float | None:
    if sum(c.isalnum() for c in w.text) < 2:
        return None                                 # Satzzeichen und einzelne Zeichen sagen über die Größe nichts
    zeichen = "".join(c for c in w.text if c.isalnum() or c in KLAMMERN)
    hoehe = w.lage[3] - w.lage[1]
    return hoehe / HOEHE_JE_GROESSE[(_oberlaenge(zeichen), _unterlaenge(zeichen))]


def _groesse(woerter: list[Wort]) -> float:
    groessen = [g for w in woerter if (g := _groesse_des_worts(w))]
    if groessen:
        return statistics.median(groessen)
    return max(w.lage[3] - w.lage[1] for w in woerter) / HOEHE_JE_GROESSE[("voll", True)]


def _basis(woerter: list[Wort], groesse: float) -> float:
    fuesse = [w.lage[3] for w in woerter if not _unterlaenge(w.text)]
    return statistics.median(fuesse) if fuesse else max(w.lage[3] for w in woerter) - UNTERLAENGE * groesse


def _text(woerter: list[Wort]) -> str:
    texte = [w.text for w in woerter]
    if len(texte) > 1 and texte[0] in PUNKT_GELESEN and texte[1][:1].isalpha():
        texte[0] = PUNKT
    return " ".join(texte)


def _zeile(z: ErkannteZeile) -> Zeile | None:
    woerter = sichere_woerter(z)
    if not woerter:
        return None
    rechteck = fitz.Rect(woerter[0].lage)
    for w in woerter[1:]:
        rechteck |= fitz.Rect(w.lage)
    groesse = _groesse(woerter)
    return Zeile(rechteck, _text(woerter), groesse, _basis(woerter, groesse), festbreit=0.0, zeichenbreite=groesse * ZEICHENBREITE)


def _fliesstext_angleichen(zeilen: list[Zeile]) -> None:
    """Die Größe, die die meisten Zeichen tragen, ist der Fließtext; was ihr so nahe liegt, dass es weder klein noch eine
    Überschrift wäre, bekommt sie."""
    if not zeilen:
        return
    gewichtet = sorted((z.groesse, len(z.text)) for z in zeilen)
    haelfte, gezaehlt = sum(n for _, n in gewichtet) / 2, 0
    grund = gewichtet[-1][0]
    for g, n in gewichtet:
        gezaehlt += n
        if gezaehlt >= haelfte:
            grund = g
            break
    for z in zeilen:
        if grund * KLEIN < z.groesse < grund * UEBERSCHRIFT_FAKTOR:
            z.groesse, z.zeichenbreite = grund, grund * ZEICHENBREITE


def zeilen_der_erkennung(e: Seitenerkennung, seite: fitz.Page) -> list[Zeile]:
    """Die Zeilen einer erkannten Seite ohne Kopf- und Fußzeilen, in der Gliederung des Programms."""
    hoehe = seite.rect.height
    zeilen = [z for z in map(_zeile, e.zeilen) if z is not None]
    zeilen = [z for z in zeilen if z.rechteck.y1 > hoehe * RAND_OBEN and z.rechteck.y0 < hoehe * RAND_UNTEN]
    _fliesstext_angleichen(zeilen)
    return zeilen


def bilder_der_erkennung(e: Seitenerkennung) -> list[fitz.Rect]:
    """Die Flächen ohne Text, die das Programm abgrenzt: Bilder in der Seite (das Seitenbild selbst zählt nicht)."""
    return [fitz.Rect(f) for f in e.flaechen]
