"""Die Suchadresse für fehlende Bände (BF-75): eine Vorlage mit Platzhaltern in den Einstellungen der App (`app_settings`,
Schlüssel `luecken_suchadresse`), anfangs leer; ohne Vorlage gibt es im Feld zum fehlenden Band nur Kopieren.

Die fertige Adresse je Band: jeder Platzhalter wird durch seinen Wert ersetzt, kodiert für eine Adresse (Leerzeichen %20, Umlaute
in UTF-8, "&", "/", "#" und "+" als Zeichen, nie als Teil der Adresse). Die Teile der Vorlage dazwischen bleiben, wie sie sind;
nur was in einer Adresse nicht stehen darf (Leerzeichen, Umlaute), wird kodiert. Erlaubt sind nur Adressen mit http oder https
und einem Rechner; geschweifte Klammern nur um einen bekannten Platzhalter."""

from __future__ import annotations

import re
from urllib.parse import quote, urlsplit

from backend.app.core import einstellungen

SCHLUESSEL = "luecken_suchadresse"
# Name -> was eingesetzt wird; die Folge ist die zum Anbieten
PLATZHALTER: dict[str, str] = {
    "titel": "Titel des Bands; ohne bekannten Titel Reihe und Band, etwa \"Leuchtfeuerkai Band 9\"",
    "autor": "Autor des Bands, sonst der häufigste Autor der Sammlung",
    "isbn": "ISBN des Bands nur mit Ziffern, leer, wenn sie unbekannt ist",
    "band": "Nummer des Bands",
    "reihe": "Name der Reihe in der Sprache des Bands, sonst der Sammlung",
    "sprache": "Sprache als Kürzel, etwa de",
}
ANDERE_NAMEN = {"nummer": "band", "sammlung": "reihe"}          # so heißen sie im Entwurf der Einstellungen
_PLATZHALTER = re.compile(r"\{([a-z]+)\}")
_ADRESSZEICHEN = ":/?#[]@!$&'()*+,;=%"                        # bleiben in den Teilen der Vorlage, wie sie sind


class FalscheVorlage(ValueError):
    pass


def bekannt(name: str) -> str | None:
    """Der Platzhalter unter seinem eigentlichen Namen; None, wenn es ihn nicht gibt."""
    return name if name in PLATZHALTER else ANDERE_NAMEN.get(name)


def pruefen(vorlage: str) -> str:
    """Die Vorlage, wenn sie gilt; leer gilt (keine Suche). Wirft FalscheVorlage mit dem Grund."""
    if not vorlage:
        return vorlage
    fremd = [n for n in _PLATZHALTER.findall(vorlage) if bekannt(n) is None]
    if fremd:
        raise FalscheVorlage(f"unbekannter Platzhalter {{{fremd[0]}}}, erlaubt sind {', '.join('{' + n + '}' for n in PLATZHALTER)}")
    if re.search(r"[{}]", _PLATZHALTER.sub("", vorlage)):
        raise FalscheVorlage("geschweifte Klammern nur um einen Platzhalter, etwa {titel}")
    teile = urlsplit(_PLATZHALTER.sub("x", vorlage))
    if teile.scheme not in ("http", "https") or not teile.netloc:
        raise FalscheVorlage("eine Adresse mit http:// oder https:// und einem Rechner, etwa https://katalog.example/suche?q={titel}")
    return vorlage


def fuellen(vorlage: str, werte: dict[str, str]) -> str | None:
    """Die fertige Adresse; None ohne Vorlage. `werte` je Platzhalter unter seinem eigentlichen Namen, Fehlendes bleibt leer."""
    if not vorlage:
        return None
    aus, stelle = [], 0
    for m in _PLATZHALTER.finditer(vorlage):
        aus.append(quote(vorlage[stelle:m.start()], safe=_ADRESSZEICHEN))
        aus.append(quote(werte.get(bekannt(m[1]) or "", ""), safe=""))
        stelle = m.end()
    aus.append(quote(vorlage[stelle:], safe=_ADRESSZEICHEN))
    return "".join(aus)


async def lesen() -> str:
    """Die gemerkte Vorlage; leer, solange keine gesetzt ist oder die gemerkte nicht mehr gilt."""
    gemerkt = await einstellungen.lesen(SCHLUESSEL) or ""
    try:
        return pruefen(gemerkt)
    except FalscheVorlage:
        return ""


async def schreiben(vorlage: str) -> str:
    await einstellungen.schreiben(SCHLUESSEL, pruefen(vorlage))
    return await lesen()
