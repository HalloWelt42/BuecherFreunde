"""Suche nach Bedeutung: fragt den Fundus, der die Bücher schon eingebettet hat (gerechnet am Rechner, nicht hier). Ist er oder
der Rechner nicht da, sagt die Antwort warum; die Suche nach Wörtern in der App geht weiter."""

from __future__ import annotations

import logging
import re
import time

import httpx

from backend.app.ablage.wolke import _pruefung, _schluessel
from backend.app.core.config import settings
from backend.app.core.database import db

logger = logging.getLogger("buecherfreunde.bedeutung")
SEHR_NAH = 0.60
_client: httpx.AsyncClient | None = None
_sammlung: tuple[str, float] = ("", 0.0)


def _verbindung() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=settings.fundus_url.rstrip("/"), verify=_pruefung(), timeout=httpx.Timeout(45.0, connect=4.0),
                                    headers={"Authorization": "Bearer " + _schluessel()})
    return _client


async def schliessen() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _kennung() -> str:
    """Kennung der Sammlung; steht in den Einstellungen ein Name, fragt sie einmal je Stunde beim Fundus nach."""
    global _sammlung
    if re.fullmatch(r"[0-9a-f-]{36}", settings.fundus_sammlung):
        return settings.fundus_sammlung
    if _sammlung[0] and time.monotonic() - _sammlung[1] < 3600:
        return _sammlung[0]
    r = await _verbindung().get("/api/v1/sammlungen")
    r.raise_for_status()
    for s in r.json():
        s = s.get("sammlung", s)
        if s.get("name") == settings.fundus_sammlung:
            _sammlung = (s["kennung"], time.monotonic())
            return _sammlung[0]
    raise LookupError(f"Der Fundus kennt keine Sammlung \"{settings.fundus_sammlung}\"")


def _auszug(text: str) -> str:
    t = re.sub(r"-\n", "", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:420].rsplit(" ", 1)[0] + "..." if len(t) > 420 else t


async def suchen(frage: str, anzahl: int = 20, buch: int | None = None) -> dict:
    leer = {"verfuegbar": False, "grund": "", "treffer": []}
    if not settings.fundus_url:
        return leer | {"grund": "Der Fundus ist nicht verbunden"}
    try:
        r = await _verbindung().post("/api/v1/suche", json={"frage": frage, "sammlungen": [await _kennung()], "anzahl": 50 if buch else anzahl, "art": "bedeutung"})
    except (httpx.HTTPError, LookupError) as f:
        logger.info("Suche nach Bedeutung: %s", f)
        return leer | {"grund": str(f) if isinstance(f, LookupError) else "Der Fundus antwortet nicht"}
    if r.status_code >= 400:
        grund = "Der Fundus kann gerade nicht nach Bedeutung suchen"
        try:
            grund = str(r.json().get("detail") or grund)
        except ValueError:
            pass
        return leer | {"grund": grund}
    d = r.json()
    if d.get("nur_woertlich"):
        return leer | {"grund": "Der Rechner für die Bedeutung schläft"}
    nummern = [int(t["herkunft"][5:]) for t in d["treffer"] if t["herkunft"].startswith("buch:")]
    namen = {z["id"]: z for z in await db.fetch_all(f"SELECT id, title, author FROM books WHERE id IN ({','.join('?' * len(nummern)) or 'NULL'})", tuple(nummern))}
    treffer = []
    for t, nr in zip([t for t in d["treffer"] if t["herkunft"].startswith("buch:")], nummern):
        if nr not in namen or (buch and nr != buch):
            continue
        wert = round(t.get("dicht") or 0, 3)
        treffer.append({"buch_id": nr, "titel": namen[nr]["title"], "autor": namen[nr]["author"], "seite": t.get("dateiseite") or (int(t["seite"]) if (t.get("seite") or "").isdigit() else None),
                        "gedruckt": t.get("gedruckt") or "", "auszug": _auszug(t["text"]), "naehe": "sehr nah" if wert >= SEHR_NAH else "verwandt", "wert": wert})
    return {"verfuegbar": True, "grund": "", "treffer": treffer[:anzahl]}


async def buch_stand(buch: int) -> dict | None:
    """Wie der Fundus ein Buch kennt: {zustand, abschnitte}; None, wenn er es (noch) nicht kennt oder nicht antwortet."""
    z = await db.fetch_one("SELECT title FROM books WHERE id = ?", (buch,))
    if not settings.fundus_url or z is None:
        return None
    try:
        r = await _verbindung().get(f"/api/v1/sammlungen/{await _kennung()}/dokumente", params={"suche": z["title"], "anzahl": 100})
        r.raise_for_status()
    except (httpx.HTTPError, LookupError) as f:
        logger.info("Stand von Buch %d: %s", buch, f)
        return None
    d = next((e for e in r.json()["eintraege"] if e["herkunft"] == f"buch:{buch}"), None)
    return {"zustand": d["zustand"], "abschnitte": d["abschnitte"]} if d else None


async def stand() -> dict:
    if not settings.fundus_url:
        return {"kennung": "fundus", "name": "Fundus", "stand": "warn", "text": "nicht eingerichtet"}
    try:
        await _kennung()
        return {"kennung": "fundus", "name": "Fundus", "stand": "gut", "text": "Bücher nach Bedeutung durchsuchbar"}
    except (httpx.HTTPError, LookupError) as f:
        return {"kennung": "fundus", "name": "Fundus", "stand": "schlecht", "text": str(f) if isinstance(f, LookupError) else "antwortet nicht"}
