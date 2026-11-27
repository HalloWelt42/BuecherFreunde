"""Die Pakete des Servers, wie die Seite Drittanbieter sie zeigt (BF-90). Eine Wahrheit: was in dieser Umgebung installiert
ist (`importlib.metadata`), mit Fassung, Lizenz und Adresse, wie jedes Paket sie selbst angibt. Ihre Lizenztexte bringen die
Pakete in ihrem Ordner `*.dist-info` mit; so liegen sie jedem gebauten Server bei.

Wofür ein Paket da ist, folgt aus `backend/requirements.txt`: ein Paket von dort steht für sich, jedes andere kommt über die
Pakete von dort, die es (auch über weitere) verlangen. Was ein Paket nur für ein Extra verlangt, zählt nur, wenn dieses Extra
verlangt ist (etwa `uvicorn[standard]`). Wie die Seite den Zweck dazu nennt, steht in der Oberfläche
(frontend/src/ansichten/einstellungen/zwecke.json)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from functools import cache
from importlib import metadata
from pathlib import Path

from pydantic import BaseModel

ANFORDERUNGEN = Path(__file__).resolve().parents[2] / "requirements.txt"
LIZENZFELD_HOECHSTENS = 100                 # länger ist das Feld License der ganze Lizenztext; dann gelten die Klassifikatoren
ADRESSEN = ("homepage", "home", "source", "sourcecode", "repository", "code")   # Vorrang unter den Project-URL
LIZENZDATEI = re.compile(r"^(?:licen[cs]e|copying|notice)", re.IGNORECASE)
_ANFORDERUNG = re.compile(r"^\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*(?:\[([^\]]*)\])?")
_KOMMENTAR = re.compile(r"(?:^|\s)#.*$")
_NUR_MIT = re.compile(r"""\bextra\s*==\s*["']([^"']+)["']""")
_SPDX_ZEILE = re.compile(r"SPDX-License-Identifier:\s*(\S.*?)\s*$", re.MULTILINE)


class Paket(BaseModel):
    """Ein installiertes Paket."""

    name: str
    fassung: str
    lizenz: str                 # SPDX-Ausdruck, sonst das kurze Feld License, sonst die Klassifikatoren; leer ohne Angabe
    adresse: str                # Startseite oder Quelle des Pakets; leer ohne Angabe
    ueber: list[str]            # Pakete aus requirements.txt, über die es installiert ist; nur es selbst, wenn es dort steht


class Anforderung(BaseModel):
    """Ein verlangtes Paket mit seinen Extras; mit `nur_mit` gilt es nur, wenn dieses Extra des Verlangenden verlangt ist."""

    name: str                   # normiert
    extras: frozenset[str] = frozenset()
    nur_mit: str = ""


def normiert(name: str) -> str:
    """Der Name, wie pip vergleicht (PEP 503): klein, jede Folge aus - _ . ein -."""
    return re.sub(r"[-_.]+", "-", name).lower()


def anforderung(zeile: str) -> Anforderung | None:
    """Eine Zeile aus requirements.txt oder ein Requires-Dist; Leerzeilen, Kommentare und Optionen (-r, --index-url) sind keine."""
    zeile = _KOMMENTAR.sub("", zeile).strip()
    treffer = _ANFORDERUNG.match(zeile) if zeile and not zeile.startswith("-") else None
    if not treffer:
        return None
    extras = frozenset(normiert(e.strip()) for e in (treffer[2] or "").split(",") if e.strip())
    nur_mit = _NUR_MIT.search(zeile.partition(";")[2])
    return Anforderung(name=normiert(treffer[1]), extras=extras, nur_mit=normiert(nur_mit[1]) if nur_mit else "")


def ueber_aus(wurzeln: Iterable[Anforderung], verlangt: Mapping[str, list[Anforderung]]) -> dict[str, set[str]]:
    """Je installiertes Paket (die Schlüssel von `verlangt`) die Wurzeln, über die es installiert ist; eine Wurzel erreicht sich selbst."""
    erreicht: dict[str, set[str]] = {}
    for wurzel in wurzeln:
        if wurzel.name not in verlangt:
            continue
        offen, gesehen = [wurzel], {(wurzel.name, wurzel.extras)}
        while offen:
            jetzt = offen.pop()
            erreicht.setdefault(jetzt.name, set()).add(wurzel.name)
            for weiter in verlangt[jetzt.name]:
                if weiter.name not in verlangt or (weiter.nur_mit and weiter.nur_mit not in jetzt.extras):
                    continue
                if (weiter.name, weiter.extras) not in gesehen:
                    gesehen.add((weiter.name, weiter.extras))
                    offen.append(weiter)
    return erreicht


def lizenz_aus(angaben: metadata.PackageMetadata, texte: Iterable[str] = ()) -> str:
    """Die Lizenz, wie das Paket sie angibt: SPDX-Ausdruck, sonst ein kurzes Feld License, sonst die Klassifikatoren, sonst die
    Zeile SPDX-License-Identifier in einem seiner Lizenztexte (erst dann gelesen)."""
    if ausdruck := (angaben.get("License-Expression") or "").strip():
        return ausdruck
    feld = (angaben.get("License") or "").strip()
    if feld and "\n" not in feld and len(feld) <= LIZENZFELD_HOECHSTENS and feld.upper() != "UNKNOWN":
        return feld
    klassen = [k.split(" :: ")[-1] for k in angaben.get_all("Classifier") or [] if k.startswith("License :: ") and k != "License :: OSI Approved"]
    if klassen:
        return ", ".join(klassen)
    return next((t[1] for t in map(_SPDX_ZEILE.search, texte) if t), "")


def adresse_aus(angaben: metadata.PackageMetadata) -> str:
    """Startseite, sonst die Project-URL nach `ADRESSEN`, sonst die erste; nur Adressen im Netz."""
    weitere: dict[str, str] = {}
    for eintrag in angaben.get_all("Project-URL") or []:
        name, _, adresse = eintrag.partition(",")
        weitere.setdefault(re.sub(r"[^a-z]", "", name.lower()), adresse.strip())
    kandidaten = [(angaben.get("Home-page") or "").strip(), *(weitere.get(n, "") for n in ADRESSEN), *weitere.values()]
    return next((a for a in kandidaten if a.startswith(("https://", "http://"))), "")


def _lizenztexte(paket: metadata.Distribution) -> Iterable[str]:
    """Die Lizenztexte, die das Paket in einem Ordner `*.dist-info` mitbringt (auch die mitgebrachter Pakete)."""
    for datei in paket.files or []:
        if LIZENZDATEI.match(datei.name) and any(teil.endswith(".dist-info") for teil in datei.parts):
            try:
                yield datei.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue


def wurzeln(datei: Path = ANFORDERUNGEN) -> list[Anforderung]:
    """Die Pakete aus requirements.txt."""
    if not datei.is_file():
        return []
    return [a for a in map(anforderung, datei.read_text(encoding="utf-8").splitlines()) if a]


@cache
def pakete() -> list[Paket]:
    """Alle installierten Pakete nach Namen; je Name das erste, wie Python es auch lädt."""
    installiert: dict[str, metadata.Distribution] = {}
    for paket in metadata.distributions():
        if name := paket.metadata.get("Name"):
            installiert.setdefault(normiert(name), paket)
    anzeige = {n: p.metadata["Name"] for n, p in installiert.items()}
    verlangt = {n: [a for a in map(anforderung, p.requires or []) if a] for n, p in installiert.items()}
    eigene = wurzeln()
    erreicht = ueber_aus(eigene, verlangt)
    direkt = {a.name for a in eigene}

    def ueber(n: str) -> list[str]:
        return [anzeige[n]] if n in direkt else sorted((anzeige[w] for w in erreicht.get(n, ())), key=str.casefold)

    liste = [Paket(name=anzeige[n], fassung=p.version, lizenz=lizenz_aus(p.metadata, _lizenztexte(p)), adresse=adresse_aus(p.metadata),
                   ueber=ueber(n)) for n, p in installiert.items()]
    return sorted(liste, key=lambda p: p.name.casefold())
