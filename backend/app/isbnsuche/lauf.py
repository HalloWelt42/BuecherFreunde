"""Der Lauf "ISBN" in Bibliothek ergänzen, je Buch (BF-111). Eingetragen wird nur, was zu Titel und Autor passt; alles andere
kommt zur Wahl, außer was schon der Text als fremd zeigt (Literaturliste, Verlagsanzeige). Was erst eine Quelle für fremd hält,
bleibt zur Wahl, mit ihrem Befund: oft ist dann der Titel des Buchs selbst unbrauchbar ("9783... Unbekannt"), und die Nummer aus
dem Impressum stimmt. Der Text reicht als Beleg, wenn Titel und Autor neben der Nummer stehen; sonst fragt der Lauf die Quellen
zu den besten Kandidaten, im Hintergrund über den gemeinsamen Abruf (Takt, Tagesgrenze), nie zu mehr."""

from __future__ import annotations

import asyncio
import re
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from backend.app.isbnsuche import wahl
from backend.app.isbnsuche.dienst import frage_aus, frage_quellen
from backend.app.isbnsuche.kandidaten import kandidaten, rang
from backend.app.isbnsuche.modelle import Kandidat
from backend.app.quellen import isbn as nummern
from backend.app.quellen.abgleich import Stufe
from backend.app.quellen.modelle import Buchfrage
from backend.app.quellen.vorrang import hintergrund

PRUEFT_HOECHSTENS = 2                # zu so vielen Kandidaten je Buch fragt der Lauf die Quellen (Abnahme BF-111: nie mehr)
_OPF_KENNUNG = re.compile(r"<dc:identifier[^>]*>([^<]+)</dc:identifier>", re.IGNORECASE)


class Laufergebnis(BaseModel):
    isbn: str = ""                   # eingetragen
    zur_wahl: bool = False
    ungeprueft: bool = False         # zur Wahl, ohne dass eine Quelle antworten konnte
    ruht: str = ""                   # warum die Quellen gerade nicht antworten; der Lauf fragt sie dann nicht mehr


def isbn_der_datei(original: Path) -> str:
    """Die ISBN aus den Angaben einer EPUB (dc:identifier); sie beschreibt diese Datei selbst und gilt ohne weitere Prüfung."""
    try:
        with zipfile.ZipFile(original) as zf:
            opf = next((n for n in zf.namelist() if n.lower().endswith(".opf")), None)
            inhalt = zf.read(opf).decode("utf-8", errors="ignore") if opf else ""
    except (OSError, zipfile.BadZipFile, KeyError):
        return ""
    for m in _OPF_KENNUNG.finditer(inhalt):
        if nummern.gueltig(m.group(1)):
            return nummern.mit_strichen(m.group(1)) or nummern.sauber(m.group(1))
    return ""


async def _pruefen(frage: Buchfrage, eigene: list[Kandidat]) -> tuple[Kandidat | None, bool, str]:
    """Fragt die Quellen zu den besten Kandidaten: (der erste, der danach passt; ob eine Quelle antworten konnte; Grund der Ruhe)."""
    gefragt, ruht = False, ""
    for k in eigene[:PRUEFT_HOECHSTENS]:
        with hintergrund():
            pruefung, antwortete = await frage_quellen(frage, k.isbn13)
        if not antwortete:
            ruht = "; ".join(pruefung.hinweise)
            break
        gefragt = True
        if pruefung.einstufung:
            k.quelle = pruefung.einstufung
            if k.quelle.stufe is Stufe.PASST:
                return k, gefragt, ruht
    return None, gefragt, ruht


async def fuer_buch(buch: Mapping[str, Any], seiten: list[str], fragen: bool) -> Laufergebnis:
    """Was der Lauf mit einem Buch ohne ISBN tut; `fragen`: ob die Quellen gefragt werden dürfen (sie ruhten noch nicht)."""
    frage = frage_aus(buch)
    weg = await wahl.abgelehnt(buch["id"])
    eigene = [k for k in await asyncio.to_thread(kandidaten, seiten, frage) if k.einstufung.stufe is not Stufe.FREMD and k.isbn13 not in weg]
    if not eigene:
        return Laufergebnis()
    if eigene[0].text.stufe is Stufe.PASST:
        return Laufergebnis(isbn=eigene[0].isbn)
    passend, gefragt, ruht = await _pruefen(frage, eigene) if fragen else (None, False, "")
    if passend:
        return Laufergebnis(isbn=passend.isbn)
    await wahl.merken(buch["id"], sorted(eigene, key=rang))         # was eine Quelle für fremd hält, zuletzt
    return Laufergebnis(zur_wahl=True, ungeprueft=not gefragt, ruht=ruht)
