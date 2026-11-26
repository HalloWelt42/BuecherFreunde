"""Die deutsche Fassung eines EPUB setzen (BF-71): dieselben Dateien mit demselben Markup, nur der Text tauscht.

Jeder Block mit geprüfter Übersetzung ersetzt genau sein Stück der Quelle (bloecke.darstellen); alles andere bleibt Byte für
Byte. Die Sprache wird deutsch (`lang` und `xml:lang` am html, `dc:language` im Paket). Ein Block, der im Original bleibt,
steht hell hinterlegt in einem `<span lang="en">` mit dem Grund als Titel: noch nicht übersetzt, oder die Prüfung nicht
bestanden. Auf Wunsch kommt vor das erste Kapitel mit Text ein Blatt "Über diese Übersetzung" (von uns übersetzt aus dem
Englischen, mit Modell und Datum).

Ohne Übersetzungen, ohne Marken und ohne Blatt ergibt Setzen dasselbe EPUB bis auf die Angaben der Sprache (Rundlauf)."""

from __future__ import annotations

import copy
import io
import posixpath
import re
import zipfile
from html import escape

from pydantic import BaseModel, Field

from backend.app.uebersetzung import marken
from backend.app.uebersetzung.bloecke import darstellen
from backend.app.uebersetzung.modelle import pruefsumme
from backend.app.uebersetzung.zerlegen_epub import Dokument, Quelle, Zerlegung, paketinhalt
from backend.app.uebersetzung.xhtml import wurzelelement

HINWEIS_NAME = "bf-uebersetzung"
ORIGINAL_ANDERS = "Im Original: der Block passt nicht mehr zur Übersetzung"
MARKE_STIL = "background-color: rgba(255, 196, 0, 0.18)"


class Hinweis(BaseModel):
    """Was auf dem Blatt "Über diese Übersetzung" steht."""
    aus: str = "Englischen"                          # für "aus dem Englischen"
    modell: str = ""                                 # leer: noch keins bekannt
    pruefmodell: str = ""
    datum: str                                       # wie für Menschen, etwa "26.11.2026"
    im_original: int = 0                             # so viele Stellen stehen noch im Original
    seitenmarken: bool = False                       # das Original ist ein PDF: die Marken zeigen seine Seiten


class Uebersetzt(BaseModel):
    """Eine geprüfte Übersetzung mit Marken, für den Block mit dieser Vorlage (Prüfsumme); passt die Vorlage im Original
    nicht mehr, bleibt der Block im Original."""
    pruefsumme: str
    text: str


class Satz(BaseModel):
    deutsch: dict[str, Uebersetzt] = Field(default_factory=dict)  # Kennung -> geprüfte Übersetzung
    im_original: dict[str, str] = Field(default_factory=dict)    # Kennung -> warum der Block im Original steht
    hinweis: Hinweis | None = None
    sprache: str = "de"
    aus_sprache: str = "en"


def mit_sprache(kopf: str, sprache: str, hinzufuegen: bool = True) -> str:
    """Ein Kopf (`<html ...>`) mit `lang` und `xml:lang` auf `sprache`; fehlen beide, kommen sie dazu."""
    neu, gefunden = kopf, False
    for name in ("xml:lang", "lang"):
        muster = re.compile(rf"""(\s{re.escape(name)}\s*=\s*)(["'])(.*?)\2""", re.S)
        if muster.search(neu):
            gefunden = True
            neu = muster.sub(lambda m: f"{m.group(1)}{m.group(2)}{sprache}{m.group(2)}", neu)
    if gefunden or not hinzufuegen:
        return neu
    schluss = len(neu) - (2 if neu.endswith("/>") else 1)
    return f'{neu[:schluss].rstrip()} lang="{sprache}" xml:lang="{sprache}"{neu[schluss:]}'


def _markiert(stueck: str, grund: str, sprache: str) -> str:
    return (f'<span class="bf-original" lang="{sprache}" xml:lang="{sprache}" title="{escape(grund)}" style="{MARKE_STIL}">'
            f"{stueck}</span>")


def _einsetzen(text: str, ersetzungen: list[tuple[int, int, str]]) -> str:
    for anfang, ende, neu in sorted(ersetzungen, key=lambda e: e[0], reverse=True):
        text = text[:anfang] + neu + text[ende:]
    return text


def _dokument(dok: Dokument, satz: Satz, je_vorlage: dict[str, Uebersetzt]) -> str:
    quelle = dok.quelle.text
    ersetzungen: list[tuple[int, int, str]] = []
    for nr, lauf in enumerate(dok.laeufe, 1):
        kennung = dok.kennung(nr)
        summe = pruefsumme(lauf.vorlage)
        u = satz.deutsch.get(kennung)
        if u is None or u.pruefsumme != summe:                # anders zerlegt: die Übersetzung derselben Vorlage
            u = je_vorlage.get(summe, u)
        if u is not None and u.pruefsumme == summe:
            baum = marken.lesen(marken.plan(lauf.vorlage), u.text)
            ersetzungen.append((lauf.anfang, lauf.ende, darstellen(lauf, quelle, baum)))
        elif u is not None and dok.rolle != "ncx":
            ersetzungen.append((lauf.anfang, lauf.ende, _markiert(quelle[lauf.anfang:lauf.ende], ORIGINAL_ANDERS, satz.aus_sprache)))
        elif (grund := satz.im_original.get(kennung)) is not None and dok.rolle != "ncx":
            ersetzungen.append((lauf.anfang, lauf.ende, _markiert(quelle[lauf.anfang:lauf.ende], grund, satz.aus_sprache)))
    wurzel = wurzelelement(dok.quelle.baum)
    if wurzel is not None:
        ersetzungen.append((wurzel.anfang, wurzel.kopf_ende,
                            mit_sprache(quelle[wurzel.anfang:wurzel.kopf_ende], satz.sprache, hinzufuegen=wurzel.lokal == "html")))
    return _einsetzen(quelle, ersetzungen)


def _paket(zerlegung: Zerlegung, satz: Satz, hinweis_href: str | None) -> str:
    opf = zerlegung.opf
    quelle = opf.text
    ersetzungen: list[tuple[int, int, str]] = []
    paket = wurzelelement(opf.baum)
    assert paket is not None
    ersetzungen.append((paket.anfang, paket.kopf_ende, mit_sprache(quelle[paket.anfang:paket.kopf_ende], satz.sprache, False)))
    if (sprache := opf.baum.erstes("language")) is not None:
        ersetzungen.append((sprache.kopf_ende, sprache.fuss_anfang, satz.sprache))
    if hinweis_href is not None:
        ersetzungen += _hinweis_im_paket(zerlegung, opf, hinweis_href)
    return _einsetzen(quelle, ersetzungen)


def _hinweis_im_paket(zerlegung: Zerlegung, opf: Quelle, href: str) -> list[tuple[int, int, str]]:
    """Das Blatt ins Manifest und in die Lesefolge, vor das erste Kapitel mit Text."""
    paket = wurzelelement(opf.baum)
    manifest, spine = (paket.erstes("manifest"), paket.erstes("spine")) if paket else (None, None)
    if manifest is None or spine is None:
        return []
    eintraege, _, _ = paketinhalt(opf)
    erstes = next((d.pfad for d in zerlegung.mit_bloecken() if d.rolle == "inhalt"), None)
    vor = next((r for r in spine.alle("itemref") if erstes and eintraege.get(r.attr("idref")) and eintraege[r.attr("idref")].pfad == erstes),
               None)
    item = f'<item id="{HINWEIS_NAME}" href="{href}" media-type="application/xhtml+xml"/>'
    ref = f'<itemref idref="{HINWEIS_NAME}"/>'
    stelle = vor.anfang if vor is not None else spine.kopf_ende
    return [(manifest.fuss_anfang, manifest.fuss_anfang, f"  {item}\n  "), (stelle, stelle, f"{ref}\n    " if vor is not None else f"\n    {ref}")]


def hinweisblatt(h: Hinweis) -> str:
    saetze = [f"Von uns übersetzt aus dem {escape(h.aus)}."]
    mit = f"Übersetzt mit {escape(h.modell) or 'der lokalen KI'}" + (f", geprüft mit {escape(h.pruefmodell)}" if h.pruefmodell else "")
    saetze.append(f"{mit}, am {escape(h.datum)}.")
    if h.im_original:
        saetze.append(f"{h.im_original} {'Stelle steht' if h.im_original == 1 else 'Stellen stehen'} noch im Original; "
                      f"{'sie ist' if h.im_original == 1 else 'sie sind'} hell hinterlegt.")
    if h.seitenmarken:
        saetze.append('Das Original ist ein PDF. Marken wie "Seite 12" zeigen, wo dort eine neue Seite beginnt.')
    absaetze = "\n".join(f"<p>{s}</p>" for s in saetze)
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" lang="de" xml:lang="de">\n'
            "<head><title>Über diese Übersetzung</title></head>\n"
            f'<body>\n<section class="{HINWEIS_NAME}">\n<h1>Über diese Übersetzung</h1>\n{absaetze}\n</section>\n</body>\n</html>\n')


def _freier_name(namen: set[str], ordner: str) -> str:
    n = 0
    while True:
        name = f"{HINWEIS_NAME}{n or ''}.xhtml"
        if posixpath.join(ordner, name) not in namen:
            return name
        n += 1


def setzen(original: bytes, zerlegung: Zerlegung, satz: Satz) -> bytes:
    """Das EPUB mit dem Satz; die Reihenfolge der Dateien und ihre Art der Ablage im Archiv bleiben. Passt eine Kennung nicht
    mehr zu ihrer Vorlage (das Original wurde mit anderen Regeln zerlegt), gilt die Übersetzung eines Blocks mit derselben
    Vorlage; sonst bleibt der Block im Original."""
    je_vorlage = {u.pruefsumme: u for u in satz.deutsch.values()}
    neu: dict[str, bytes] = {d.pfad: d.quelle.bytes_aus(_dokument(d, satz, je_vorlage)) for d in zerlegung.dokumente}
    ziel = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as archiv, zipfile.ZipFile(ziel, "w") as aus:
        namen = set(archiv.namelist())
        ordner = posixpath.dirname(zerlegung.opf.pfad)
        hinweis_href = _freier_name(namen, ordner) if satz.hinweis is not None else None
        neu[zerlegung.opf.pfad] = zerlegung.opf.bytes_aus(_paket(zerlegung, satz, hinweis_href))
        for info in archiv.infolist():
            aus.writestr(copy.copy(info), neu[info.filename] if info.filename in neu else archiv.read(info.filename))
        if satz.hinweis is not None and hinweis_href is not None:
            aus.writestr(zipfile.ZipInfo(posixpath.join(ordner, hinweis_href), date_time=archiv.infolist()[0].date_time),
                         hinweisblatt(satz.hinweis).encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
    return ziel.getvalue()
