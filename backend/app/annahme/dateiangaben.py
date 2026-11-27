"""Die Angaben einer Buchdatei noch einmal lesen, als Vorschlag im Vergleich (Quelle "Datei", BF-112): Titel, Autor, Verlag, Jahr,
Sprache, Beschreibung und ISBN aus den Metadaten der EPUB oder den Eigenschaften des PDF, mit denselben Lesern wie beim Aufnehmen
(eigener Prozess). Der Erzeuger eines PDF ist nie ein Verlag (BF-110); ein Titel, der nur der Dateiname ist, zählt nicht."""

from __future__ import annotations

import asyncio

from pydantic import BaseModel

from backend.app.annahme import auswertung
from backend.app.quellen import isbn as nummern
from backend.app.quellen.abgleich import norm
from backend.app.quellen.modelle import FELDER, Angaben
from backend.app.quellen.sprache import kuerzel
from backend.app.services.autorennamen import zerlegen
from backend.app.services.data_cleaner import bereinige_autor, bereinige_text, bereinige_titel
from backend.app.services.storage import get_original_file

DATEI = "datei"                   # Kennung der Quelle im Vergleich
OHNE_DATEI = "Die Datei des Buchs ist gerade nicht erreichbar, die Angaben bleiben, wie sie sind"
NICHTS = "In den Angaben der Datei steht nichts"


class Dateiangaben(BaseModel):
    angaben: Angaben | None = None
    grund: str = ""               # warum es keine gibt


def _kein_dateiname(titel: str, stamm: str) -> str:
    return "" if norm(titel) == norm(stamm.replace("_", " ").replace("-", " ")) else titel


async def lesen(file_hash: str, fmt: str) -> Dateiangaben:
    original = await asyncio.to_thread(get_original_file, file_hash)        # kann aus der Kellerwolke laden
    if original is None:
        return Dateiangaben(grund=OHNE_DATEI)
    e = await auswertung.angaben(original)
    if not e.lesbar:
        return Dateiangaben(grund=e.grund)
    a = Angaben(quelle=DATEI, titel=bereinige_titel(_kein_dateiname(e.title, original.stem)), autoren=zerlegen(bereinige_autor(e.author or "")),
                verlag=bereinige_text(e.publisher or "", 200), jahr=e.year, isbn=nummern.mit_strichen(e.isbn) or e.isbn or "",
                sprache=kuerzel(e.language), beschreibung=bereinige_text(e.description or ""), seiten=e.page_count if fmt == "pdf" else 0)
    gefuellt = [f for f in FELDER if getattr(a, f)]
    if not gefuellt:
        return Dateiangaben(grund=NICHTS)
    return Dateiangaben(angaben=a.model_copy(update={"herkunft": {f: DATEI for f in gefuellt}}))
