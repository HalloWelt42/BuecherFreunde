"""Was die Erkennung über die Codestellen eines Buchs weiß (Begleiter codestellen.json) und was die Vorprüfung dazu sagt.

Eine Codestelle ist ein Listing, wie das Buch es zeigt: ein oder mehrere Teile (über einen Seitenwechsel fortgesetzt), ein
Text (der zurückgewonnene Code), die Sprache mit ihrer Sicherheit und woher sie kommt. Die Lage eines Teils hängt am Format:
im PDF Dateiseite und Rechteck, im EPUB das Kapitel und die Nummer des Codeblocks darin, in Markdown und Text die Zeile."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: steigt, wenn die Erkennung anders arbeitet; Begleiter einer älteren Fassung werden neu erkannt
#: (2: je Teil die Zahl seiner Zeilen, für den Baustein der Textansicht)
FASSUNG = 2

#: ab dieser Sicherheit gilt eine Sprache als sicherer Befund (die Taste erscheint nur dann)
SICHER = 0.6

Quelle = Literal["titel", "datei", "inhalt", ""]
Format = Literal["pdf", "epub", "md", "txt"]


class Teil(BaseModel):
    """Ein Stück der Stelle. PDF: `seite` (Dateiseite ab 1) und `rechteck` [x0, y0, x1, y1] in Punkten der Seite, oben
    links; `offen_oben`/`offen_unten`, wenn der Kasten an der Kante weitergeht. EPUB: `kapitel` (Pfad im Buch) und `nr`
    (der wievielte Codeblock darin, ab 0). Markdown und Text: `zeile` (ab 1)."""

    seite: int | None = None
    rechteck: list[float] | None = None
    offen_oben: bool = False
    offen_unten: bool = False
    zeilen: int | None = None            # PDF: so viele Zeilen des Codes stehen in diesem Teil (der Reihe nach)
    kapitel: str | None = None
    nr: int | None = None
    zeile: int | None = None


class Codestelle(BaseModel):
    kennung: str                         # Lage des ersten Teils und Prüfsumme des Codes
    teile: list[Teil]
    sprache: str | None = None           # python, javascript, php, sql, shell, ausgabe, ...; None: unbekannt
    sicherheit: float = 0.0              # 0 bis 1
    quelle: Quelle = ""                  # woher die Sprache kommt
    titel: str = ""                      # Kastentitel oder Beschriftung, wie gedruckt
    datei: str = ""                      # Dateiname, wenn das Buch einen nennt
    code: str
    zeilennummern_ab: int | None = None  # erste gedruckte Zeilennummer
    pruefsumme: str                      # des Codes; bleibt sie gleich, gilt die Vorprüfung weiter

    @property
    def sicher(self) -> bool:
        return self.sprache is not None and self.sicherheit >= SICHER

    def zeilen_der_teile(self) -> list[list[str]]:
        """Der Code Teil für Teil; ohne Angabe je Teil steht alles im ersten."""
        zeilen = self.code.split("\n")
        if any(t.zeilen is None for t in self.teile):
            return [zeilen] + [[] for _ in self.teile[1:]]
        aus, ab = [], 0
        for t in self.teile:
            aus.append(zeilen[ab:ab + (t.zeilen or 0)])
            ab += t.zeilen or 0
        return aus


class Begleiter(BaseModel):
    """Inhalt von codestellen.json neben seiten.json. `grund`: warum die Datei nicht gelesen werden konnte (dann leer)."""

    fassung: int = FASSUNG
    format: Format
    stellen: list[Codestelle] = Field(default_factory=list)
    grund: str = ""


Stand = Literal["laeuft", "auszug", "offen"]


class Vorpruefung(BaseModel):
    """Was die Vorprüfung zu einer Stelle sagt. `laeuft`: lief in der Sandbox für sich (mit `ausgabe`); `auszug`: lief
    nicht für sich, mit kurzem `grund` und was `fehlt` (Vorschlag der KI oder der Fehler des Laufs); `offen`: noch nicht
    geprüft. Die KI schlägt nur vor, am Code ändert sie nichts."""

    stand: Stand = "offen"
    quelle: Literal["lauf", "ki", ""] = ""
    ausgabe: str = ""
    fehler: str = ""                     # erste Zeile des Fehlers aus dem Lauf
    grund: str = ""
    fehlt: list[str] = Field(default_factory=list)
    geprueft_am: str = ""
