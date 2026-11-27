"""Anschlüsse (BF-82): Kellerwolke, Leitstelle (KI), Vertonung (Vorlesen, BF-14) und Nachschlag, je mit Adresse und "Verbindung
prüfen".

Eine Adresse, die in der App eingetragen ist, steht in `app_settings` (`anschluss_<art>`) und gilt vor der aus der Einrichtung
(.env); `anwenden` legt sie beim Start, nach dem Wiederherstellen und nach jeder Änderung über die Einstellungen, danach
verbinden sich Kellerwolke, Anmeldung und Nachschlag neu. Schlüssel gehen nur in den Schlüsselbund (`core/schluessel.py`); die
Antworten nennen nur, ob einer eingetragen ist. Ein neuer Schlüssel gilt erst, wenn die Prüfung mit ihm besteht; bis dahin
bleibt der alte. Vertonung und Nachschlag haben keinen eigenen Schlüssel, sie kennen die App über ihren Zugang der Kellerwolke."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from appkern.leitstelle import Leitstelle, LeitstellenFehler

from backend.app.ablage.wolke import _pruefung, wolke
from backend.app.core import anmeldung as anmeldung_modul, einstellungen, schluessel
from backend.app.core.config import settings
from backend.app.einrichtung.modelle import Anschluss, AnschlussEingabe, Verbindungspruefung
from backend.app.einrichtung.zustand import Einrichtungsfehler, jetzt
from backend.app.services import ki as ki_modul, lexikon_nachschlag
from backend.app.vorlesen import stimmen as vertonung_stimmen

logger = logging.getLogger("buecherfreunde.einrichtung.anschluesse")


@dataclass(frozen=True)
class Beschreibung:
    name: str
    feld: str                                   # das Feld der Einstellungen, das die Adresse hält
    schluessel: schluessel.Art | None
    hinweis: str = ""


ARTEN: dict[str, Beschreibung] = {
    "kellerwolke": Beschreibung("Kellerwolke", "kellerwolke_url", schluessel.Art.KELLERWOLKE,
                                "Originale und je Buch ein Auszug liegen dort; mit \"Persönliches in der Kellerwolke\" je Buch auch Notizen, "
                                "Markierungen, Etiketten, Lesestand und Freigaben je Profil. Wer die Kellerwolke verwaltet, könnte sie lesen."),
    "leitstelle": Beschreibung("Leitstelle", "leitstelle_adresse", schluessel.Art.LEITSTELLE, "KI zum Einordnen und Prüfen"),
    "vertonung": Beschreibung("Vertonung", "vertonung_url", None,
                              "Vorlesen und Ansagen mit ihren Stimmen, auch privaten und geklonten; ohne Schlüssel, sie kennt die App über "
                              "ihren Zugang der Kellerwolke"),
    "nachschlag": Beschreibung("Nachschlag", "nachschlag_url", None, "Lexika und Handbücher beim Lesen; ohne Schlüssel"),
}
_zuletzt: dict[str, Verbindungspruefung] = {}             # die letzte Prüfung je Anschluss seit dem Start


def einstellung(art: str) -> str:
    return f"anschluss_{art}"


def _client() -> httpx.AsyncClient:
    """Für die Prüfung eine eigene Verbindung; die Wege der App bleiben unberührt."""
    return httpx.AsyncClient(verify=_pruefung(), timeout=httpx.Timeout(10.0, connect=4.0))


async def anwenden() -> None:
    for art, b in ARTEN.items():
        wert = await einstellungen.lesen(einstellung(art))
        if wert is not None:
            setattr(settings, b.feld, wert)
    await neu_verbinden()


async def neu_verbinden() -> None:
    """Nach neuer Adresse oder neuem Schlüssel: die Verbindungen der App mit den neuen Werten aufbauen."""
    await wolke.schliessen()
    anmeldung_modul.anmeldung.umstellen()
    await lexikon_nachschlag.dienst.schliessen()


async def _herkunft(art: str) -> str:
    if await einstellungen.lesen(einstellung(art)) is not None:
        return "app"
    return "einrichtung" if getattr(settings, ARTEN[art].feld) else ""


async def eintrag(art: str) -> Anschluss:
    b = ARTEN[art]
    return Anschluss(art=art, name=b.name, adresse=getattr(settings, b.feld), herkunft=await _herkunft(art),
                     schluessel=schluessel.stand(b.schluessel) if b.schluessel else None, hinweis=b.hinweis, pruefung=_zuletzt.get(art))


async def liste() -> list[Anschluss]:
    return [await eintrag(art) for art in ARTEN]


# -- prüfen -------------------------------------------------------------------------------------------------------------

def _grund(r: httpx.Response, name: str) -> str:
    try:
        d = r.json().get("detail")
    except (ValueError, AttributeError):
        d = None
    return f"{name}: {d}" if isinstance(d, str) else f"{name} meldet {r.status_code}"


async def _kellerwolke(c: httpx.AsyncClient, adresse: str, wert: str) -> Verbindungspruefung:
    r = await c.get(f"{adresse}/api/v1/ablage/ich", headers={"Authorization": f"Bearer {wert}"})
    if r.status_code in (401, 403):
        return Verbindungspruefung(ok=False, grund="Die Kellerwolke kennt diesen App-Zugang nicht")
    if r.status_code >= 400:
        return Verbindungspruefung(ok=False, grund=_grund(r, "Kellerwolke"))
    ich = r.json()
    if not ich.get("app"):
        return Verbindungspruefung(ok=False, grund="Das ist kein App-Zugang; die Kellerwolke nennt keine App")
    return Verbindungspruefung(ok=True, text=f"{ich['app']}, Konto {ich.get('konto') or 'unbekannt'}", app=str(ich["app"]), konto=str(ich.get("konto") or ""))


async def _leitstelle(c: httpx.AsyncClient, adresse: str, wert: str) -> Verbindungspruefung:
    l = Leitstelle(adresse, wert, ki_modul.APP, client=c)
    try:
        modelle = await l.modelle()
    except LeitstellenFehler as f:
        return Verbindungspruefung(ok=False, grund=ki_modul.fehler(f, settings.ki_modell).grund)
    return Verbindungspruefung(ok=True, text=f"KI mit {len(modelle)} {'Modell' if len(modelle) == 1 else 'Modellen'}")


async def _vertonung(adresse: str) -> Verbindungspruefung:
    """Über den Verbund wie beim Vorlesen, mit dem App-Zugang der Kellerwolke: welche Stimmen sie BücherFreunde anbietet."""
    liste = await vertonung_stimmen.liste(adresse)
    if not liste.da:
        return Verbindungspruefung(ok=False, grund=liste.hinweis or "Die Vertonung antwortet nicht")
    zahl = {b.bereich: sum(s.bereich == b.bereich for s in liste.stimmen) for b in liste.bereiche if b.frei}
    teile = [f"{n} {name}" for b, name in (("katalog", "eingebaut"), ("fremd", "fremd"), ("privat", "privat")) if (n := zahl.get(b))]
    text = "Stimmen: " + (", ".join(teile) if teile else "keine")
    gesperrt = next((b.hinweis for b in liste.bereiche if not b.frei), "")
    return Verbindungspruefung(ok=True, text=f"{text}; {gesperrt}" if gesperrt else text)


async def _nachschlag(c: httpx.AsyncClient, adresse: str) -> Verbindungspruefung:
    r = await c.get(f"{adresse}/api/v1/buecher", headers={"Authorization": f"Bearer {k}"} if (k := schluessel.lesen(schluessel.Art.KELLERWOLKE)) else {})
    if r.status_code >= 400:
        return Verbindungspruefung(ok=False, grund=_grund(r, "Nachschlag"))
    buecher = r.json().get("buecher") or []
    return Verbindungspruefung(ok=True, text=f"{len(buecher)} Lexika und Handbücher")


async def pruefen(art: str, adresse: str | None = None, wert: str | None = None) -> Verbindungspruefung:
    """Prüft die genannten Werte, sonst die eingetragenen; merkt nichts außer dem Ergebnis für die Anzeige."""
    b = ARTEN[art]
    adresse = (adresse if adresse is not None else getattr(settings, b.feld)).strip().rstrip("/")
    wert = wert or (schluessel.lesen(b.schluessel) if b.schluessel else "")
    if not adresse:
        p = Verbindungspruefung(ok=False, grund="Keine Adresse eingetragen")
    elif b.schluessel and not wert:
        p = Verbindungspruefung(ok=False, grund="Kein Schlüssel eingetragen")
    else:
        try:
            if art == "vertonung":
                p = await _vertonung(adresse)
            else:
                async with _client() as c:
                    p = await (_kellerwolke(c, adresse, wert) if art == "kellerwolke" else _leitstelle(c, adresse, wert) if art == "leitstelle"
                               else _nachschlag(c, adresse))
        except httpx.HTTPError as f:
            p = Verbindungspruefung(ok=False, grund=f"{b.name} antwortet nicht ({type(f).__name__})")
    p.am = jetzt()
    _zuletzt[art] = p
    return p


# -- eintragen ----------------------------------------------------------------------------------------------------------

async def vorbereiten(art: str, e: AnschlussEingabe) -> tuple[Verbindungspruefung, str]:
    """Prüft, was eingetragen werden soll; ohne Erfolg 422 mit dem Grund. Antwortet die Prüfung und den Schlüssel, der gelten soll."""
    b = ARTEN[art]
    if not e.adresse:
        raise Einrichtungsfehler("Adresse: darf nicht leer sein", 422)
    if e.schluessel and not b.schluessel:
        raise Einrichtungsfehler(f"Schlüssel: {b.name} hat keinen", 422)
    wert = e.schluessel or (schluessel.lesen(b.schluessel) if b.schluessel else "")
    p = await pruefen(art, e.adresse, wert)
    if not p.ok:
        raise Einrichtungsfehler(f"Verbindung: {p.grund}", 422)
    return p, wert


async def anwenden_eintrag(art: str, adresse: str, neuer_schluessel: str | None) -> None:
    """Gilt sofort: Adresse in die Einstellungen, ein neuer Schlüssel in den Schlüsselbund, danach neu verbinden."""
    b = ARTEN[art]
    if neuer_schluessel and b.schluessel:
        schluessel.eintragen(b.schluessel, neuer_schluessel)
    await einstellungen.schreiben(einstellung(art), adresse)
    setattr(settings, b.feld, adresse)
    await neu_verbinden()
