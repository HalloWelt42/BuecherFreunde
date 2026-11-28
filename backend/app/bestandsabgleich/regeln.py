"""Die Stufe eines Kandidaten und der Vergleich Feld für Feld (BF-119), ohne Datenbank.

Vorhanden ist ein Buch mit gleicher ISBN, oder wenn Titel und Autor passen (dieselben Grenzen wie beim Abgleich mit den Quellen).
Nennt die Seite eine andere Auflage, ist es nur ähnlich. Ähnlich ist auch ein naher Titel, dem der Autor fehlt oder dessen Autor
gleich ist, aber der Titel nur ungefähr; ein gleicher Titel von einem anderen Autor ebenso. Wie nah "ungefähr" ist, stellt die
Erweiterung ein (`aehnlich_ab`). Ohne Autor wird nie etwas vorhanden: ein gleicher Titel allein sagt zu wenig ("Gedichte").

Fremde Seiten hängen Zusätze an den Titel: Klammern ohne Zahl ("(Roman)", "[Taschenbuch]") zählen darum auch weg; eine Zahl in
Klammern bleibt, sie nennt oft den Band."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.app.bestandsabgleich.modelle import Angebot, Fundart, Vergleichszeile
from backend.app.quellen import isbn as nummern
from backend.app.quellen.abgleich import MIT_AUTOR, OHNE_AUTOR, SICHER, autor_passt, echte_autoren, norm, titel_naehe

_KLAMMER = re.compile(r"\s*[(\[][^()\[\]\d]*[)\]]")
_AUFLAGE = re.compile(r"\b(\d{1,2})\s*\.\s*(?:,\s*)?(?:[a-zäöüß]+\s+){0,3}(?:auflage|aufl\b)|\b(\d{1,2})(?:st|nd|rd|th)\s+(?:[a-z]+\s+)?edition",
                      re.IGNORECASE)


@dataclass(frozen=True)
class Bestandsbuch:
    """Was der Vergleich von einem eigenen Buch braucht."""

    id: int
    title: str
    author: str
    autoren: tuple[str, ...]
    year: int | None = None
    isbn13: frozenset[str] = field(default_factory=frozenset)
    formate: tuple[str, ...] = ()


@dataclass(frozen=True)
class Einstufung:
    art: Fundart
    naehe: float
    grund: str


def ohne_klammern(titel: str) -> str:
    return " ".join(_KLAMMER.sub(" ", titel or "").split())


def auflage(text: str) -> int | None:
    m = _AUFLAGE.search(text or "")
    return int(m.group(1) or m.group(2)) if m else None


def isbn13(werte: list[str] | tuple[str, ...] | str) -> frozenset[str]:
    """Alle gültigen ISBN in einem Feld oder einer Liste, als ISBN-13."""
    teile = [werte] if isinstance(werte, str) else list(werte)
    funde = (z for t in teile for z in re.findall(r"[\dXx][\dXx\s-]{8,20}[\dXx]", t or ""))
    return frozenset(nummern.dreizehn(z) for z in funde if nummern.gueltig(z))


def titelnaehe(angebot: Angebot, titel: str) -> float:
    """In beide Richtungen, mit und ohne Klammerzusätze der Seite."""
    formen = {angebot.titel, ohne_klammern(angebot.titel)} - {""}
    return max((max(titel_naehe(f, titel), titel_naehe(titel, f, angebot.untertitel)) for f in formen), default=0.0)


def _auflage_der_seite(angebot: Angebot) -> int | None:
    return auflage(" ".join((angebot.titel, angebot.untertitel, angebot.ausgabe)))


def _andere_auflage(angebot: Angebot, buch: Bestandsbuch) -> bool:
    seite = _auflage_der_seite(angebot)
    return seite is not None and seite != (auflage(buch.title) or 1)


def _grund_auflage(angebot: Angebot, buch: Bestandsbuch) -> str:
    if angebot.jahr and buch.year and angebot.jahr != buch.year:
        return f"andere Auflage: {angebot.jahr} statt {buch.year}"
    return "andere Auflage"


def einstufen(angebot: Angebot, buch: Bestandsbuch, aehnlich_ab: float) -> Einstufung | None:
    """Vorhanden, ähnlich oder kein Treffer."""
    if isbn13(angebot.isbn) & buch.isbn13:
        return Einstufung(Fundart.VORHANDEN, 1.0, "gleiche ISBN")
    t = titelnaehe(angebot, buch.title)
    if t < min(aehnlich_ab, MIT_AUTOR):
        return None
    autor = autor_passt(echte_autoren(angebot.autoren), echte_autoren(buch.autoren))
    if autor:
        if t >= MIT_AUTOR:
            if _andere_auflage(angebot, buch):
                return Einstufung(Fundart.AEHNLICH, t, _grund_auflage(angebot, buch))
            return Einstufung(Fundart.VORHANDEN, t, "Titel und Autor passen")
        return Einstufung(Fundart.AEHNLICH, t, "Titel ähnlich, Autor gleich") if t >= aehnlich_ab else None
    if t < aehnlich_ab:
        return None
    if autor is None:
        return Einstufung(Fundart.AEHNLICH, t, "Titel gleich, ohne Autor" if t >= SICHER else "Titel ähnlich, ohne Autor")
    return Einstufung(Fundart.AEHNLICH, t, "gleicher Titel, anderer Autor") if t >= OHNE_AUTOR else None


def freitext(text: str, buch: Bestandsbuch, aehnlich_ab: float) -> Einstufung | None:
    """Markierter Text oder eine Suche: ein Titel oder ein Name. Der Name zählt, wenn er einen Autor des Buchs nennt."""
    if any(_name_gleich(text, a) for a in echte_autoren(buch.autoren)):
        return Einstufung(Fundart.VORHANDEN, 1.0, "Autor passt")
    t = titelnaehe(Angebot(nr=0, titel=text), buch.title)
    if t >= MIT_AUTOR:
        return Einstufung(Fundart.VORHANDEN, t, "Titel passt")
    return Einstufung(Fundart.AEHNLICH, t, "Titel ähnlich") if t >= aehnlich_ab else None


def _name_gleich(text: str, autor: str) -> bool:
    worte, name = norm(text).split(), norm(autor).split()
    return len(worte) >= 2 and bool(name) and (worte == name or worte == name[::-1] or worte[-1:] == name[-1:] and worte[0] == name[0])


def vergleich(angebot: Angebot, buch: Bestandsbuch) -> list[Vergleichszeile]:
    """Was die Seite nennt neben dem, was in der Bibliothek steht; nur Felder, die die Seite kennt."""
    seite_titel = f"{angebot.titel}: {angebot.untertitel}" if angebot.untertitel else angebot.titel
    zeilen = [Vergleichszeile(feld="Titel", seite=seite_titel, mein=buch.title, gleich=titelnaehe(angebot, buch.title) >= SICHER)]
    if angebot.autoren:
        zeilen.append(Vergleichszeile(feld="Autor", seite=", ".join(angebot.autoren), mein=buch.author,
                                      gleich=bool(autor_passt(echte_autoren(angebot.autoren), echte_autoren(buch.autoren)))))
    if (seite := _auflage_der_seite(angebot)) is not None:
        mein = auflage(buch.title) or 1
        zeilen.append(Vergleichszeile(feld="Auflage", seite=f"{seite}.", mein=f"{mein}.", gleich=seite == mein))
    if angebot.jahr and buch.year:
        zeilen.append(Vergleichszeile(feld="Jahr", seite=str(angebot.jahr), mein=str(buch.year), gleich=angebot.jahr == buch.year))
    if seite_isbn := sorted(isbn13(angebot.isbn)):
        gleich = bool(set(seite_isbn) & buch.isbn13)
        zeige = next((i for i in seite_isbn if i in buch.isbn13), seite_isbn[0])
        mein = zeige if gleich else (sorted(buch.isbn13)[0] if buch.isbn13 else "")
        zeilen.append(Vergleichszeile(feld="ISBN", seite=nummern.mit_strichen(zeige), mein=nummern.mit_strichen(mein) if mein else "keine",
                                      gleich=gleich))
    if angebot.ausgabe:
        formate = [f.upper() for f in buch.formate]
        zeilen.append(Vergleichszeile(feld="Format", seite=angebot.ausgabe, mein=", ".join(formate),
                                      gleich=norm(angebot.ausgabe).upper() in formate))
    return zeilen
