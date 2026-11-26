"""Was der Katalog die lokale KI fragt (BF-69), mit JSON-Schema, und wie die Antworten gelesen werden. Die KI entscheidet nie
still: was sie sagt, wird ein Vorschlag. Unbekannte Nummern und Schlüssel fallen weg; passt eine Antwort nicht zur
verlangten Form, ist das ein KiFehler ("einzeln"), und es bleibt bei den Regeln.

- Einordnen: je Anfrage einige Bücher und die Kategorien, die für ihre Art gelten; je Buch höchstens zwei Kategorien mit
  Sicherheit und einem kurzen deutschen Satz.
- Alte Regale: je Name eine Kategorie des Katalogs oder keine (dann wird der Name ein Schlagwort am Buch).
- Neu aus dem Bestand: aus häufigen Schlagworten ohne passende Kategorie höchstens fünf neue Kategorien."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel

from backend.app.katalog.merkmale import Buchmerkmale
from backend.app.katalog.modelle import Einordnungskategorie
from backend.app.models.grenzen import KATALOG_NAME, KI_BESCHREIBUNG
from backend.app.services.ki import KiFehler

JE_BUCH = 2                                    # so viele Kategorien schlägt die KI je Buch höchstens vor
NEUE_HOECHSTENS = 5
SATZ_ZEICHEN = 300
SCHLAGWORTE_JE_BUCH = 8


class KiFund(BaseModel):
    schluessel: str
    sicherheit: int
    satz: str


class NeueKategorie(BaseModel):
    bereich: str
    name: str
    zeichen: str
    ki_beschreibung: str
    schlagworte: list[str]


def form_falsch() -> KiFehler:
    return KiFehler("Die Antwort der KI passt nicht zur verlangten Form", "einzeln")


def _satz(roh: object) -> str:
    return " ".join(roh.split())[:SATZ_ZEICHEN] if isinstance(roh, str) else ""


def _ganz(roh: object) -> int | None:
    if isinstance(roh, bool) or not isinstance(roh, (int, float)):
        return None
    return int(round(roh))


def _sicherheit(roh: object) -> int | None:
    """0 bis 100; ein Anteil wie 0,85 gilt als 85 (manche Modelle antworten so, obwohl das Schema ganze Zahlen verlangt)."""
    if isinstance(roh, float) and 0 < roh <= 1:
        roh *= 100
    wert = _ganz(roh)
    return None if wert is None else max(0, min(100, wert))


def _liste(roh: object, feld: str) -> list:
    if not isinstance(roh, dict) or not isinstance(roh.get(feld), list):
        raise form_falsch()
    return roh[feld]


def katalogtext(kategorien: Sequence[Einordnungskategorie]) -> str:
    return "\n".join(f"- {k.schluessel}: {k.name}" + (f" ({k.ki_beschreibung})" if k.ki_beschreibung else "") for k in kategorien)


# -- Einordnen --------------------------------------------------------------------------------------------------------------

SYSTEM_EINORDNEN = (
    "Du ordnest die Werke einer privaten Bibliothek in ihren Katalog ein. Du bekommst die Kategorien des Katalogs, je mit "
    "Schlüssel, Name und was hineingehört, und nummerierte Werke mit Titel, Autor, Verlag, Schlagworten und dem Anfang der "
    "Beschreibung. Antworte mit einem Objekt mit dem Feld 'buecher': je Werk ein Eintrag mit 'nummer' und 'kategorien'. "
    "'kategorien' sind höchstens zwei, die am besten passen, je mit 'schluessel' (genau ein Schlüssel aus dem Katalog), "
    "'sicherheit' (0 bis 100: wie sicher du bist) und 'satz' (ein kurzer deutscher Satz, warum). Passt keine Kategorie, "
    "bleibt 'kategorien' leer. Rate nicht: lieber keine Kategorie als eine unsichere.")


def schema_einordnen(schluessel: Sequence[str]) -> dict:
    kategorie = {"type": "object", "additionalProperties": False, "required": ["schluessel", "sicherheit", "satz"],
                 "properties": {"schluessel": {"type": "string", "enum": list(schluessel)},
                                "sicherheit": {"type": "integer", "description": "0 bis 100"},
                                "satz": {"type": "string", "description": "ein kurzer deutscher Satz"}}}
    buch = {"type": "object", "additionalProperties": False, "required": ["nummer", "kategorien"],
            "properties": {"nummer": {"type": "integer"}, "kategorien": {"type": "array", "items": kategorie}}}
    return {"type": "object", "additionalProperties": False, "required": ["buecher"],
            "properties": {"buecher": {"type": "array", "items": buch}}}


def buchzeile(nummer: int, b: Buchmerkmale) -> str:
    teile = [f"Titel: {b.titel or '-'}", f"Autor: {b.autor or '-'}", f"Verlag: {b.verlag or '-'}"]
    if b.schlagworte:
        teile.append("Schlagworte: " + ", ".join(b.schlagworte[:SCHLAGWORTE_JE_BUCH]))
    if b.beschreibung:
        teile.append("Beschreibung: " + " ".join(b.beschreibung.split()))
    return f"{nummer}. " + " | ".join(teile)


def anfrage_einordnen(kategorien: Sequence[Einordnungskategorie], buecher: Sequence[Buchmerkmale]) -> str:
    return "Katalog:\n" + katalogtext(kategorien) + "\n\nWerke:\n" + "\n".join(buchzeile(i, b) for i, b in enumerate(buecher, 1))


def einordnung_aus(roh: object, anzahl: int, schluessel: set[str]) -> dict[int, list[KiFund]]:
    """Je Nummer (ab 1) die Kategorien der KI; unbekannte Nummern und Schlüssel fallen weg, je Buch höchstens `JE_BUCH`."""
    aus: dict[int, list[KiFund]] = {}
    for eintrag in _liste(roh, "buecher"):
        if not isinstance(eintrag, dict) or not isinstance(eintrag.get("kategorien"), list):
            raise form_falsch()
        nummer = _ganz(eintrag.get("nummer"))
        if nummer is None or not 1 <= nummer <= anzahl or nummer in aus:
            continue
        funde: list[KiFund] = []
        for k in eintrag["kategorien"]:
            if not isinstance(k, dict):
                raise form_falsch()
            sicherheit = _sicherheit(k.get("sicherheit"))
            if k.get("schluessel") not in schluessel or sicherheit is None or any(f.schluessel == k["schluessel"] for f in funde):
                continue
            funde.append(KiFund(schluessel=k["schluessel"], sicherheit=sicherheit,
                                satz=_satz(k.get("satz")) or "Die KI hält das für passend"))
        aus[nummer] = funde[:JE_BUCH]
    return aus


# -- alte Regale ------------------------------------------------------------------------------------------------------------

SYSTEM_ALT = (
    "Du hilfst, die alten Regale einer privaten Bibliothek in ihren neuen Katalog zu überführen. Du bekommst die Kategorien "
    "des Katalogs, je mit Schlüssel, Name und was hineingehört, und nummerierte Namen alter Regale, oft Schlagworte aus "
    "Bibliothekskatalogen. Antworte mit einem Objekt mit dem Feld 'regale': je Regal ein Eintrag mit 'nummer', 'schluessel' "
    "(der Schlüssel der Kategorie, in die die Bücher dieses Regals gehören, oder leer, wenn der Name besser ein Schlagwort am "
    "Buch bleibt, etwa weil er ein Ort, eine Person oder zu allgemein ist) und 'satz' (ein kurzer deutscher Satz, warum).")


def schema_alt(schluessel: Sequence[str]) -> dict:
    regal = {"type": "object", "additionalProperties": False, "required": ["nummer", "schluessel", "satz"],
             "properties": {"nummer": {"type": "integer"}, "schluessel": {"type": "string", "enum": ["", *schluessel]},
                            "satz": {"type": "string", "description": "ein kurzer deutscher Satz"}}}
    return {"type": "object", "additionalProperties": False, "required": ["regale"],
            "properties": {"regale": {"type": "array", "items": regal}}}


def anfrage_alt(kategorien: Sequence[Einordnungskategorie], namen: Sequence[str]) -> str:
    return "Katalog:\n" + katalogtext(kategorien) + "\n\nAlte Regale:\n" + "\n".join(f"{i}. {n}" for i, n in enumerate(namen, 1))


def alt_aus(roh: object, anzahl: int, schluessel: set[str]) -> dict[int, tuple[str, str]]:
    """Je Nummer (ab 1) der Schlüssel (leer: Schlagwort am Buch) und der Satz der KI."""
    aus: dict[int, tuple[str, str]] = {}
    for eintrag in _liste(roh, "regale"):
        if not isinstance(eintrag, dict) or not isinstance(eintrag.get("schluessel"), str):
            raise form_falsch()
        nummer = _ganz(eintrag.get("nummer"))
        if nummer is None or not 1 <= nummer <= anzahl or nummer in aus or eintrag["schluessel"] not in schluessel | {""}:
            continue
        aus[nummer] = (eintrag["schluessel"], _satz(eintrag.get("satz")))
    return aus


# -- neue Kategorien aus dem Bestand ----------------------------------------------------------------------------------------

SYSTEM_NEU = (
    "Du hilfst, den Katalog einer privaten Bibliothek an ihren Bestand anzupassen. Du bekommst die Bereiche des Katalogs mit "
    "ihren Kategorien und häufige Schlagworte der Bücher, zu denen noch keine Kategorie passt, je mit der Zahl der Bücher. "
    f"Schlage höchstens {NEUE_HOECHSTENS} neue Kategorien vor, die viele dieser Bücher sinnvoll zusammenfassen, und keine, "
    "die es im Katalog schon gibt. Antworte mit einem Objekt mit dem Feld 'neu': je Kategorie 'bereich' (Schlüssel eines "
    "Bereichs), 'name' (kurz, deutsch), 'zeichen' (eins aus der Liste), 'ki_beschreibung' (ein deutscher Satz, was "
    "hineingehört) und 'schlagworte' (die Schlagworte aus der Liste, die dazugehören). Passt nichts, bleibt 'neu' leer.")


def schema_neu(bereiche: Sequence[str], zeichen: Sequence[str]) -> dict:
    kategorie = {"type": "object", "additionalProperties": False,
                 "required": ["bereich", "name", "zeichen", "ki_beschreibung", "schlagworte"],
                 "properties": {"bereich": {"type": "string", "enum": list(bereiche)}, "name": {"type": "string"},
                                "zeichen": {"type": "string", "enum": list(zeichen)}, "ki_beschreibung": {"type": "string"},
                                "schlagworte": {"type": "array", "items": {"type": "string"}}}}
    return {"type": "object", "additionalProperties": False, "required": ["neu"],
            "properties": {"neu": {"type": "array", "items": kategorie}}}


def anfrage_neu(bereiche: Sequence[tuple[str, str, list[str]]], haeufige: Sequence[tuple[str, int]], zeichen: Sequence[str]) -> str:
    """`bereiche`: Schlüssel, Name und die Namen seiner Kategorien; `haeufige`: Schlagwort und Zahl der Bücher."""
    zeilen = ["Bereiche:"] + [f"- {s}: {n} ({', '.join(ks)})" for s, n, ks in bereiche]
    zeilen += ["", "Häufige Schlagworte ohne Kategorie:"] + [f"- {w} ({n} Bücher)" for w, n in haeufige]
    zeilen += ["", "Zeichen: " + ", ".join(zeichen)]
    return "\n".join(zeilen)


def neue_aus(roh: object, bereiche: set[str], zeichen: set[str], schlagworte: Sequence[str],
             vergeben: dict[str, set[str]]) -> list[NeueKategorie]:
    """Die neuen Kategorien, die taugen: bekannter Bereich, ein Name, den es dort noch nicht gibt (`vergeben`: je Bereich
    die Namen klein), mindestens ein angebotenes Schlagwort; höchstens `NEUE_HOECHSTENS`."""
    angeboten = {w.casefold(): w for w in schlagworte}
    aus: list[NeueKategorie] = []
    for e in _liste(roh, "neu"):
        if not isinstance(e, dict) or not isinstance(e.get("schlagworte"), list):
            raise form_falsch()
        name = _satz(e.get("name"))[:KATALOG_NAME]
        worte = list(dict.fromkeys(angeboten[w.casefold()] for w in e["schlagworte"] if isinstance(w, str) and w.casefold() in angeboten))
        bereich = e.get("bereich")
        if bereich not in bereiche or not name or not worte or name.casefold() in vergeben.setdefault(bereich, set()):
            continue
        vergeben[bereich].add(name.casefold())
        aus.append(NeueKategorie(bereich=bereich, name=name, zeichen=e.get("zeichen") if e.get("zeichen") in zeichen else "tag",
                                 ki_beschreibung=_satz(e.get("ki_beschreibung"))[:KI_BESCHREIBUNG], schlagworte=worte))
    return aus[:NEUE_HOECHSTENS]
