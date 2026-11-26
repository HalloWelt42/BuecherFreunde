"""Ein EPUB in Kapitel und Blöcke zerlegen (BF-71).

Gelesen wird, was das Paket nennt (META-INF/container.xml, dann die OPF-Datei): die Dateien der Lesefolge (spine) in ihrer
Reihenfolge, dazu das Inhaltsverzeichnis (nav), wenn es nicht in der Lesefolge steht, und die NCX-Datei älterer Bücher,
damit auch das Verzeichnis im Leser deutsch wird. Jede dieser Dateien ist ein Kapitel mit fester Nummer (ihre Stelle in
dieser Folge, ab 1); ihre Blöcke zählen ab 1. Die Kennung eines Blocks ist "Kapitel.Block" (etwa "3.17"). Dasselbe Original
mit denselben Einstellungen ergibt immer dieselben Kennungen; darauf bauen das Fortsetzen und alles, was am Block hängt.

Ein Kapitel heißt wie im Inhaltsverzeichnis, sonst wie seine erste Überschrift, sonst wie der Titel der Datei. Eine Datei,
die sich nicht lesen lässt, bleibt im Original und wird genannt (`nicht_lesbar`). Die Stylesheets eines Kapitels (verlinkt
oder im Kopf) sagen, welche Klassen in Festbreitenschrift stehen: ein Merkmal für Code (codeabsaetze.py)."""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import unquote

from backend.app.uebersetzung import codeabsaetze, marken
from backend.app.uebersetzung.bloecke import Lauf, Regeln, laeufe
from backend.app.uebersetzung.modelle import Block
from backend.app.uebersetzung.xhtml import Element, kodierung, lesen, text_von, wurzelelement

CONTAINER = "META-INF/container.xml"
DOKUMENTARTEN = frozenset({"application/xhtml+xml", "text/html"})
NCX_ART = "application/x-dtbncx+xml"
WORT = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)?|\d+(?:[.,]\d+)*")     # ein Wort, eine Zahl mit Trennzeichen

Rolle = Literal["inhalt", "verzeichnis", "ncx"]


class NichtLesbar(Exception):
    """Das EPUB lässt sich nicht zerlegen (kein Paket, keine Lesefolge); der Grund steht als deutscher Satz da."""


@dataclass(eq=False)
class Quelle:
    """Eine Datei des Archivs als Text, mit dem, was zum Zurückschreiben gehört."""
    pfad: str
    text: str
    kodierung: str
    vorspann: bytes
    baum: Element

    def bytes_aus(self, text: str) -> bytes:
        return self.vorspann + text.encode(self.kodierung, errors="xmlcharrefreplace")


@dataclass(eq=False)
class Dokument:
    quelle: Quelle
    kapitel: int
    titel: str
    rolle: Rolle
    laeufe: list[Lauf] = field(default_factory=list)

    @property
    def pfad(self) -> str:
        return self.quelle.pfad

    def kennung(self, nr: int) -> str:
        return f"{self.kapitel}.{nr}"

    def bloecke(self) -> list[Block]:
        return [Block(kennung=self.kennung(i), kapitel=self.kapitel, nr=i, art=l.art, stufe=l.stufe, vorlage=l.vorlage,
                      woerter=len(WORT.findall(marken.klartext(l.vorlage))))
                for i, l in enumerate(self.laeufe, 1)]


@dataclass(eq=False)
class Zerlegung:
    opf: Quelle
    dokumente: list[Dokument]
    sprache: str                                     # dc:language des Originals
    abbildungen: int
    nicht_lesbar: list[str] = field(default_factory=list)

    def bloecke(self) -> list[Block]:
        return [b for d in self.dokumente for b in d.bloecke()]

    def mit_bloecken(self) -> list[Dokument]:
        return [d for d in self.dokumente if d.laeufe]


def _lesen(archiv: zipfile.ZipFile, pfad: str) -> Quelle:
    daten = archiv.read(pfad)
    art, vorspann = kodierung(daten)
    text = daten[len(vorspann):].decode(art)
    return Quelle(pfad=pfad, text=text, kodierung=art, vorspann=vorspann, baum=lesen(text))


def _aufgeloest(basis: str, href: str) -> str:
    """Ein Verweis relativ zur Datei `basis` als Pfad im Archiv, ohne Sprungmarke."""
    return posixpath.normpath(posixpath.join(posixpath.dirname(basis), unquote(href.split("#", 1)[0])))


def _paketpfad(archiv: zipfile.ZipFile) -> str:
    try:
        container = lesen(archiv.read(CONTAINER).decode("utf-8", errors="replace"))
    except KeyError as f:
        raise NichtLesbar("Das EPUB hat kein META-INF/container.xml") from f
    for rf in container.alle("rootfile"):
        if rf.attr("full-path") and rf.attr("media-type") in ("", "application/oebps-package+xml"):
            return rf.attr("full-path")
    raise NichtLesbar("Das EPUB nennt keine Paketdatei (OPF)")


@dataclass(frozen=True)
class Eintrag:
    pfad: str
    art: str
    eigenschaften: frozenset[str]


def paketinhalt(opf: Quelle) -> tuple[dict[str, Eintrag], list[str], str]:
    """Manifest (Kennung -> Eintrag), Lesefolge (Kennungen) und die Kennung der NCX-Datei."""
    paket = wurzelelement(opf.baum)
    if paket is None or paket.lokal != "package":
        raise NichtLesbar("Die Paketdatei (OPF) ist nicht lesbar")
    manifest = {i.attr("id"): Eintrag(_aufgeloest(opf.pfad, i.attr("href")), i.attr("media-type"), frozenset(i.woerter("properties")))
                for m in paket.alle("manifest") for i in m.alle("item") if i.attr("id") and i.attr("href")}
    spine = paket.erstes("spine")
    if spine is None:
        raise NichtLesbar("Das EPUB hat keine Lesefolge (spine)")
    folge = [r.attr("idref") for r in spine.alle("itemref") if r.attr("idref") in manifest]
    ncx = spine.attr("toc") or next((k for k, e in manifest.items() if e.art == NCX_ART), "")
    return manifest, folge, ncx


def _titel_aus_verzeichnis(nav: Quelle | None, ncx: Quelle | None) -> dict[str, str]:
    """Pfad einer Datei -> ihr Titel im Inhaltsverzeichnis (der erste Eintrag, der auf sie zeigt)."""
    titel: dict[str, str] = {}
    if nav is not None:
        navs = list(nav.baum.alle("nav"))
        toc = next((n for n in navs if "toc" in n.woerter("epub:type")), navs[0] if navs else None)
        for a in toc.alle("a") if toc else ():
            if a.attr("href") and (t := text_von(a)):
                titel.setdefault(_aufgeloest(nav.pfad, a.attr("href")), t)
    if ncx is not None:
        for punkt in ncx.baum.alle("navpoint"):
            inhalt, label = punkt.erstes("content"), punkt.erstes("navlabel")
            if inhalt is not None and label is not None and (t := text_von(label)):
                titel.setdefault(_aufgeloest(ncx.pfad, inhalt.attr("src")), t)
    return titel


def _kapiteltitel(dok: Dokument, verzeichnis: dict[str, str]) -> str:
    if t := verzeichnis.get(dok.pfad):
        return t
    if dok.rolle != "inhalt":
        return "Inhaltsverzeichnis"
    if ueberschrift := next((l for l in dok.laeufe if l.art == "ueberschrift"), None):
        return marken.klartext(ueberschrift.vorlage)
    if (kopf := dok.quelle.baum.erstes("title")) is not None and (t := text_von(kopf)):
        return t
    return posixpath.splitext(posixpath.basename(dok.pfad))[0]


def _abbildungen(dok: Dokument) -> int:
    svgs = list(dok.quelle.baum.alle("svg"))
    in_svg = {id(b) for s in svgs for b in s.alle("img")}
    return sum(1 for b in dok.quelle.baum.alle("img") if id(b) not in in_svg) + sum(1 for s in svgs)


def _stylesheets(archiv: zipfile.ZipFile, quelle: Quelle, gelesen: dict[str, str]) -> list[str]:
    """Die Stylesheets eines Dokuments: verlinkte Dateien des Archivs (einmal gelesen) und `<style>` im Dokument."""
    texte = []
    for link in quelle.baum.alle("link"):
        if "stylesheet" not in link.woerter("rel") or not link.attr("href"):
            continue
        pfad = _aufgeloest(quelle.pfad, link.attr("href"))
        if pfad not in gelesen:
            try:
                gelesen[pfad] = archiv.read(pfad).decode("utf-8", errors="replace")
            except KeyError:
                gelesen[pfad] = ""
        texte.append(gelesen[pfad])
    texte += [quelle.text[stil.kopf_ende:stil.fuss_anfang] for stil in quelle.baum.alle("style")]
    return texte


def zerlegen(daten: bytes, nie_klassen: frozenset[str] = frozenset()) -> Zerlegung:
    try:
        archiv = zipfile.ZipFile(io.BytesIO(daten))
    except zipfile.BadZipFile as f:
        raise NichtLesbar("Die Datei ist kein EPUB (kein ZIP-Archiv)") from f
    with archiv:
        namen = set(archiv.namelist())
        opf_pfad = _paketpfad(archiv)
        if opf_pfad not in namen:
            raise NichtLesbar(f"Die Paketdatei {opf_pfad} fehlt im EPUB")
        opf = _lesen(archiv, opf_pfad)
        manifest, folge, ncx_kennung = paketinhalt(opf)
        plan: list[tuple[str, Rolle]] = []
        for kennung in dict.fromkeys(folge):
            e = manifest[kennung]
            if e.art in DOKUMENTARTEN or e.pfad.lower().endswith((".xhtml", ".html", ".htm")):
                plan.append((e.pfad, "inhalt"))
        nav = next((e for e in manifest.values() if "nav" in e.eigenschaften), None)
        if nav is not None and nav.pfad not in {p for p, _ in plan}:
            plan.append((nav.pfad, "verzeichnis"))
        if ncx_kennung in manifest:
            plan.append((manifest[ncx_kennung].pfad, "ncx"))

        dokumente, nicht_lesbar = [], []
        stile: dict[str, str] = {}
        for nr, (pfad, rolle) in enumerate(plan, 1):
            try:
                quelle = _lesen(archiv, pfad)
            except (KeyError, UnicodeDecodeError, LookupError):
                nicht_lesbar.append(pfad)
                continue
            regeln = Regeln(nie_klassen=nie_klassen, nur_verzeichnis=rolle == "ncx", code_absaetze=rolle == "inhalt",
                            festbreit_klassen=codeabsaetze.klassen_aus(_stylesheets(archiv, quelle, stile)))
            dokumente.append(Dokument(quelle=quelle, kapitel=nr, titel="", rolle=rolle, laeufe=laeufe(quelle.baum, regeln)))
    quellen = {d.pfad: d.quelle for d in dokumente}
    verzeichnis = _titel_aus_verzeichnis(quellen.get(nav.pfad) if nav else None,
                                         quellen.get(manifest[ncx_kennung].pfad) if ncx_kennung in manifest else None)
    for d in dokumente:
        d.titel = _kapiteltitel(d, verzeichnis)
    sprache_el = opf.baum.erstes("language")
    return Zerlegung(opf=opf, dokumente=dokumente, sprache=text_von(sprache_el) if sprache_el is not None else "",
                     abbildungen=sum(_abbildungen(d) for d in dokumente if d.rolle == "inhalt"), nicht_lesbar=nicht_lesbar)
