"""Nachschlag aus den Hausdiensten (`NACHSCHLAG_URL`): viele Lexika und Handbücher, Treffer aus Titeln und Volltext, die Stelle in
der Anwendung zum Weiterlesen."""

from __future__ import annotations

import asyncio
import re
from urllib.parse import quote, unquote, urlencode

from backend.app.core.config import settings
from backend.app.services.hausdienst import DienstFehler, Hausdienst
from backend.app.services.lexikon import Abschnitt, Nachschlagartikel, Nachschlagtreffer, ist_bild, klartext, ordnen, zum_lesen

dienst = Hausdienst("Nachschlag", lambda: settings.nachschlag_url)
LEXIKON = "wikipedia_de_all"                       # bei gleichem Titel zuerst

_buecher: dict[str, str] = {}


async def _titel_der_buecher(sitzung: str) -> dict[str, str]:
    if not _buecher:
        d = (await dienst.hole("GET", "/api/v1/buecher", sitzung)).json()
        _buecher.update({b["kennung"]: b["titel"] for b in d.get("buecher", [])})
    return _buecher


def adresse(buch: str, pfad: str, frage: str = "", anker: str = "") -> str:
    zusatz = urlencode({k: w for k, w in (("frage", frage), ("anker", anker)) if w})
    return f"{dienst.adresse}/lesen/{quote(buch, safe='')}/{quote(pfad)}" + (f"?{zusatz}" if zusatz else "")


def _bild(verweis: str) -> str:
    m = re.match(r"/api/v1/inhalt/medien/([^/]+)/(.+)$", verweis or "")
    return f"/api/nachschlag/bild/{m.group(1)}/{m.group(2)}" if m else ""


def lesbar(html: str, buch: str) -> str:
    """Verweise bleiben nur, wenn sie ins selbe Buch führen."""
    def verweis(href: str) -> str | None:
        m = re.match(rf"/lesen/{re.escape(buch)}/([^#?]+)", href)
        return unquote(m.group(1)) if m else None
    return zum_lesen(html, verweis)


class Nachschlag:
    art = "nachschlag"

    @property
    def adresse(self) -> str:
        return dienst.adresse

    async def vorwaermen(self) -> None:
        """Die Namen der Bücher schon beim Start holen; das dauert dort beim ersten Mal lange."""
        try:
            await _titel_der_buecher("")
        except DienstFehler:
            pass

    async def schliessen(self) -> None:
        await dienst.schliessen()

    async def suche(self, frage: str, anzahl: int, sitzung: str, nur_titel: bool) -> list[Nachschlagtreffer]:
        """`nur_titel`: nur Titel im großen Lexikon (schnell); sonst alle Bücher und auch die Suche im Text."""
        titel = await _titel_der_buecher(sitzung)
        lexika = [b for b in titel if b.startswith(LEXIKON)] if nur_titel else []
        wege = [dienst.hole("GET", "/api/v1/vorschlaege", sitzung, params={"anfang": frage[:200], "anzahl": 8, **({"buecher": lexika} if lexika else {})})]
        if not nur_titel:
            wege.append(dienst.hole("GET", "/api/v1/suche", sitzung, params={"frage": frage[:400], "anzahl": 12, "wege": "index"}))
        vorschlaege, *gefunden = await asyncio.gather(*wege)
        aus: dict[tuple[str, str], Nachschlagtreffer] = {}
        for v in vorschlaege.json():
            pfad, _, anker = (v.get("weiterleitung") or v["pfad"]).partition("#")
            aus.setdefault((v["buch"], pfad), Nachschlagtreffer(buch=v["buch"], buchtitel=titel.get(v["buch"], ""), pfad=pfad, titel=v["titel"],
                                                                auszug=klartext(v.get("kurztext", "")), anker=anker, bild=_bild(v.get("bild", ""))))
        for t in (t for g in gefunden for t in g.json()["treffer"]):
            neu = Nachschlagtreffer(buch=t["buch"], buchtitel=titel.get(t["buch"], ""), pfad=t["pfad"], titel=t["titel"],
                                    auszug=klartext(t.get("ausschnitt", "")), anker=t.get("anker", ""), bild=_bild(t.get("bild", "")))
            vorhanden = aus.setdefault((t["buch"], t["pfad"]), neu)
            vorhanden.auszug = vorhanden.auszug or neu.auszug
        return ordnen(frage, list(aus.values()), lambda t: t.buch.startswith(LEXIKON))[:anzahl]

    async def artikel(self, buch: str, pfad: str, frage: str, anker: str, sitzung: str) -> Nachschlagartikel:
        a = (await dienst.hole("GET", f"/api/v1/artikel/{quote(buch, safe='')}/{quote(pfad)}", sitzung)).json()
        titel = await _titel_der_buecher(sitzung)
        stelle = anker or a.get("anker", "")
        return Nachschlagartikel(buch=a["buch"], buchtitel=titel.get(a["buch"], ""), pfad=a["pfad"], titel=a["titel"], anker=stelle,
                                 html=lesbar(a.get("html") or "", a["buch"]) or f"<p>{klartext(a.get('einleitung', ''))}</p>", bild=_bild(a.get("bild", "")),
                                 abschnitte=[Abschnitt(anker=x["anker"], titel=x["titel"]) for x in a.get("abschnitte", []) if x.get("ebene") == 2],
                                 adresse=adresse(a["buch"], a["pfad"], frage, stelle))

    async def bild(self, buch: str, pfad: str) -> tuple[bytes, str]:
        r = await dienst.hole("GET", f"/api/v1/inhalt/medien/{quote(buch, safe='')}/{quote(pfad)}")
        art = r.headers.get("content-type", "").split(";")[0]
        if not ist_bild(art):
            raise DienstFehler("Das ist kein Bild", 404)
        return r.content, art
