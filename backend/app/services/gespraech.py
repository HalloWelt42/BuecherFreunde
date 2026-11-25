"""Gespräch mit dem Assistenten über eine Stelle im Buch: Chat anlegen, fragen, Antwort als Strom. Der Chat gehört der Anwendung
(`ASSISTENT_URL`), dort geht er weiter; ohne sie fehlt die Fähigkeit."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.database import db
from backend.app.services.hausdienst import DienstFehler, Hausdienst

dienst = Hausdienst("Der Assistent", lambda: settings.assistent_url, zeit_s=60.0)
KENNUNG = r"^[A-Za-z0-9-]{1,64}$"
TITEL_HOECHSTENS = 100


class Stelle(BaseModel):
    """Worauf sich die Frage bezieht; `text` ist das im Buch Gewählte."""

    buch: int | None = None
    seite: int | None = None
    text: str = Field("", max_length=12_000)


class Frage(BaseModel):
    frage: str = Field("", max_length=8_000)
    stelle: Stelle = Stelle()
    chat: str = Field("", pattern=r"^$|" + KENNUNG)


class Gestellt(BaseModel):
    chat: str
    zug: str
    adresse: str                        # der Chat in der Anwendung


class Beleg(BaseModel):
    nummer: str
    titel: str
    seite: str = ""
    verweis: str = ""


def adresse(chat: str) -> str:
    return f"{dienst.adresse}/chats/{chat}"


async def _angaben(buch: int | None) -> tuple[str, str]:
    z = await db.fetch_one("SELECT title, author FROM books WHERE id = ?", (buch,)) if buch else None
    return (z["title"], z["author"] or "") if z else ("", "")


def wortlaut(frage: str, stelle: Stelle, titel: str, autor: str, verweis: str) -> str:
    """Was der Assistent zu lesen bekommt: woher die Stelle ist, die Stelle selbst, die Frage."""
    zeilen = []
    if titel:
        woher = f"Aus dem Buch \"{titel}\"" + (f" von {autor}" if autor else "") + (f", Seite {stelle.seite}" if stelle.seite else "")
        zeilen.append(woher + (f" ({verweis})" if verweis else "") + ":")
    if stelle.text.strip():
        zeilen += ["\n".join("> " + z for z in stelle.text.strip().splitlines()), ""]
    zeilen.append(frage.strip() or ("Erkläre mir diese Stelle." if stelle.text.strip() else "Worum geht es in diesem Buch?"))
    return "\n".join(zeilen)


async def fragen(f: Frage, sitzung: str, basis: str) -> Gestellt:
    titel, autor = await _angaben(f.stelle.buch)
    verweis = f"{basis}/book/{f.stelle.buch}/read?{urlencode({'page': f.stelle.seite})}" if f.stelle.buch and f.stelle.seite else f"{basis}/book/{f.stelle.buch}" if f.stelle.buch else ""
    chat = f.chat
    if not chat:
        name = (titel or f.frage or f.stelle.text).strip().replace("\n", " ")[:TITEL_HOECHSTENS]
        chat = (await dienst.hole("POST", "/api/v1/chats", sitzung, json={"titel": name})).json()["id"]
    text = wortlaut(f.frage, f.stelle, titel, autor, verweis) if not f.chat or f.stelle.text.strip() else f.frage.strip()
    if not text:
        raise DienstFehler("Es fehlt die Frage", 422)
    zug = (await dienst.hole("POST", f"/api/v1/chats/{chat}/zuege", sitzung, json={"text": text, "kennung": uuid.uuid4().hex})).json()
    return Gestellt(chat=chat, zug=zug["id"], adresse=adresse(chat))


def _zeile(**inhalt) -> bytes:
    return json.dumps(inhalt, ensure_ascii=False).encode() + b"\n"


def _stand(zug: dict) -> bytes:
    """Der Stand eines Zugs, auf das Nötige gekürzt."""
    belege = [Beleg(nummer=str(b["nummer"]), titel=b["titel"], seite=str(b.get("gedruckt") or b.get("seite") or ""), verweis=b.get("verweis") or "").model_dump() for b in zug.get("belege", [])]
    return _zeile(art="stand", antwort=zug.get("antwort") or "", zustand=zug.get("zustand"), wartet_auf=zug.get("wartet_auf") or "", fehler=zug.get("fehler") or "", belege=belege)


FERTIG = ("fertig", "fehler", "abgebrochen")


async def antwort(chat: str, zug: str, sitzung: str) -> AsyncIterator[bytes]:
    """Zeilen `{art: stand, antwort, zustand, wartet_auf, fehler, belege}` und `{art: text, text, ab, neu}`, bis der Zug fertig ist."""
    try:
        async with dienst.client.stream("GET", f"/api/v1/chats/{chat}/ereignisse", headers=dienst.im_auftrag(sitzung), timeout=httpx.Timeout(None, connect=4.0)) as r:
            if r.status_code >= 400:
                raise DienstFehler(f"Der Assistent meldet {r.status_code}", 502)
            ereignis = ""
            async for roh in r.aiter_lines():
                if roh.startswith("event:"):
                    ereignis = roh[6:].strip()
                elif roh.startswith("data:"):
                    fertig, zeile = await _uebersetzen(ereignis, roh[5:].strip(), chat, zug, sitzung)
                    if zeile:
                        yield zeile
                    if fertig:
                        return
    except httpx.HTTPError as f:
        yield _zeile(art="stand", antwort="", zustand="fehler", wartet_auf="", fehler=f"Die Verbindung zum Assistenten riss ab ({type(f).__name__})", belege=[])


async def _uebersetzen(ereignis: str, daten: str, chat: str, zug: str, sitzung: str) -> tuple[bool, bytes | None]:
    if ereignis == "verbunden":                          # ab jetzt kommt jede Änderung; den Stand davor einmal holen
        voll = (await dienst.hole("GET", f"/api/v1/chats/{chat}", sitzung)).json()
        z = next((x for x in voll["zuege"] if x["id"] == zug), None)
        return (True, None) if z is None else (z["zustand"] in FERTIG, _stand(z))
    d = json.loads(daten or "{}")
    if ereignis == "zug" and d["zug"]["id"] == zug:
        return d["zug"]["zustand"] in FERTIG, _stand(d["zug"])
    if ereignis == "text" and d["zug"] == zug:
        return False, _zeile(art="text", text=d["text"], ab=d.get("ab", 0), neu=d.get("neu", False))
    return False, None


async def abbrechen(zug: str, sitzung: str) -> None:
    await dienst.hole("POST", f"/api/v1/zuege/{zug}/abbrechen", sitzung)
