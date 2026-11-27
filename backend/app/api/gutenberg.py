"""Gemeinfreie Bücher (Project Gutenberg): Stand der Quelle, der eigene Katalog (BF-98), Vorschläge beim Tippen, die ausdrückliche
Suche bei Gutendex mit Rückfall auf den Katalog, Aufnahme und das Holen in die Lücke einer Sammlung. Aufgenommen wird über die
Annahme (annahme/gemeinfrei.py); Stand und Fortschritt stehen in der einen Liste unter /api/annahme."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.app.annahme import vorschau
from backend.app.annahme.dienst import annahme
from backend.app.annahme.gemeinfrei import QUELLE
from backend.app.annahme.modelle import Vorgabe
from backend.app.core.auth import braucht, verify_token
from backend.app.core.database import db
from backend.app.models.grenzen import ADRESSE, AUSWAHL_HOECHSTENS, AUTOR, LISTENSEITE, TITEL, Band, Nr, Sprache
from backend.app.quellen import stand
from backend.app.quellen.fehler import QuelleFehler
from backend.app.quellen.gutenberg import Fundliste, stoerung, suche
from backend.app.quellen.gutenberg_katalog import SEITE, Katalogstand, katalog
from backend.app.quellen.regeln import GUTENBERG

router = APIRouter(prefix="/api/gutenberg", tags=["Gutenberg"], dependencies=[Depends(braucht("hinzufuegen"))])
RUECKFALL = "Die Treffer kommen aus dem eigenen Katalog; später erneut versuchen."
OHNE_KATALOG = "Später erneut versuchen."
KATALOG_KOMMT = "Der eigene Katalog wird gerade geholt, danach gibt es Treffer auch ohne Gutendex."


@router.get("/status")
async def gutenberg_status(_token: str = Depends(verify_token)) -> dict:
    """Der gemerkte Stand der Gutendex-API; gefragt wird sie dabei nicht."""
    s = await stand.einer(GUTENBERG.kennung)
    return {"erreichbar": s.erreichbar, "url": s.adresse, "info": s.grund or s.wort}


def _blaettern(liste: Fundliste, request: Request) -> Fundliste:
    """Für Listen aus dem eigenen Katalog die Wege zur nächsten und vorigen Seite, wie Gutendex sie nennt."""
    def weg(seite: int) -> str:
        return f"{request.url.path}?{urlencode({**request.query_params, 'seite': seite})}"

    liste.naechste = weg(liste.seite + 1) if liste.seite * SEITE < liste.gesamt else None
    liste.vorherige = weg(liste.seite - 1) if liste.seite > 1 else None
    return liste


# -- Eigener Katalog (BF-98) ------------------------------------------------------------------------------------------------

@router.get("/katalog", response_model=Katalogstand)
async def katalog_stand(_token: str = Depends(verify_token)) -> Katalogstand:
    """Anzahl, Stand und Alter des eigenen Katalogs; läuft er gerade, wie weit (Byte) und welcher Schritt."""
    return await katalog.stand()


@router.post("/katalog", response_model=Katalogstand)
async def katalog_holen(_token: str = Depends(verify_token)) -> Katalogstand:
    """Den eigenen Katalog holen oder erneuern, als sichtbarer Auftrag; läuft er schon, bleibt es bei diesem Lauf."""
    if not GUTENBERG.aktiv:
        raise HTTPException(status_code=409, detail="Gemeinfreie Bücher sind in der Einrichtung abgeschaltet")
    katalog.starten()
    return await katalog.stand()


@router.get("/vorschlaege", response_model=Fundliste)
async def gutenberg_vorschlaege(
    request: Request,
    q: str = Query("", max_length=TITEL, description="Was getippt ist (Titel, Autor)"),
    sprache: str = Query("", max_length=100, description="Sprachfilter (z.B. 'de' oder 'de,en')"),
    seite: int = Query(1, ge=1, le=LISTENSEITE),
    _token: str = Depends(verify_token),
) -> Fundliste:
    """Beim Tippen: nur der eigene Katalog, kein Dienst im Netz wird gefragt. Ohne Wort oder ohne Katalog leer."""
    return _blaettern(await katalog.vorschlaege(q, sprache, seite), request)


@router.get("/suche", response_model=Fundliste)
async def gutenberg_suche(
    request: Request,
    q: str = Query("", description="Suchbegriff (Titel, Autor)"),
    sprache: str = Query("", description="Sprachfilter (z.B. 'de', 'en', 'de,en')"),
    topic: str = Query("", description="Thema/Kategorie"),
    seite: int = Query(1, ge=1, le=LISTENSEITE, description="Seitennummer"),
    _token: str = Depends(verify_token),
) -> Fundliste:
    """Ausdrücklich bei Gutendex, mit großzügiger Geduld (GUTENBERG_SUCHE_GEDULD_S). Antwortet Gutendex nicht, kommen die Treffer
    aus dem eigenen Katalog (`herkunft` katalog, `hinweis` sagt warum); ohne Katalog 502 mit dem Grund als Satz."""
    try:
        return await suche(query=q, sprache=sprache, topic=topic, seite=seite)
    except QuelleFehler as f:
        grund = stoerung(f)
        if await katalog.da():
            liste = await katalog.suche(q, sprache, topic, seite)
            liste.hinweis = f"{grund}. {RUECKFALL}"
            return _blaettern(liste, request)
        raise HTTPException(status_code=502, detail=f"{grund}. {KATALOG_KOMMT if katalog.laeuft else OHNE_KATALOG}") from f


# -- Aufnehmen -------------------------------------------------------------------------------------------------------------

class GemeinfreiesBuch(BaseModel):
    """Ein Buch aus der Suche, wie sie es liefert."""
    gutenberg_id: Nr
    titel: str = Field("", max_length=TITEL)
    autor: str = Field("", max_length=AUTOR)
    download_url: str = Field("", max_length=ADRESSE)
    download_format: str = Field("", max_length=100)
    cover_url: str = Field("", max_length=ADRESSE)


class GutenbergImportRequest(BaseModel):
    """Bücher aus der Suche."""
    buecher: list[GemeinfreiesBuch] = Field(max_length=AUSWAHL_HOECHSTENS)


class InDieLuecke(BaseModel):
    """Ein gemeinfreies Buch für den fehlenden Band einer Sammlung."""
    buch: GemeinfreiesBuch
    sammlung_id: Nr
    band: Band
    sprache: Sprache = ""


@router.post("/import")
async def gutenberg_import(request: GutenbergImportRequest, _token: str = Depends(verify_token)):
    """Ausgewählte gemeinfreie Bücher aufnehmen, über dieselbe Annahme wie jede Datei (Liste unter /api/annahme): geholt,
    gelesen, ins Regal "Gutenberg". `anzahl`: neu in der Liste; was es schon gibt, steht dort als vorhanden."""
    if not request.buecher:
        raise HTTPException(status_code=400, detail="Keine Bücher ausgewählt")
    neu = await annahme.aus_gemeinfrei([b.model_dump() for b in request.buecher])
    return {"gestartet": neu > 0, "anzahl": neu}


@router.post("/luecke")
async def gutenberg_in_die_luecke(a: InDieLuecke, _token: str = Depends(verify_token)) -> dict:
    """In die Lücke holen (BF-98): wie jedes gemeinfreie Buch geholt und gelesen, dann mit Halt in einer Vorschau, die Sammlung,
    Band und Sprache der Lücke vorgibt, wie beim Hochladen in die Lücke. `vorschau`: dort geht es weiter."""
    if await db.fetch_one("SELECT 1 AS da FROM collections WHERE id = ?", (a.sammlung_id,)) is None:
        raise HTTPException(status_code=422, detail="Sammlung: diese Sammlung gibt es nicht")
    if await annahme.gemeinfrei_in_arbeit(a.buch.gutenberg_id):
        raise HTTPException(status_code=409, detail="Dieses Buch wird gerade schon geholt. Danach steht es im Regal und lässt sich dort der Sammlung zuordnen.")
    nr = await vorschau.anlegen(a.buch.titel or f"Gutenberg {a.buch.gutenberg_id}", QUELLE, Vorgabe(sammlung_id=a.sammlung_id, band=a.band, sprache=a.sprache))
    await annahme.aus_gemeinfrei([a.buch.model_dump()], vorschau=nr)
    return {"vorschau": nr}
