"""Passt ein Fund zu dem, was gesucht war? Vergleich von Titeln (mit und ohne Untertitel), Namen und Jahren, ohne Rücksicht
auf Groß und klein, Umlautschreibweise und Satzzeichen."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from difflib import SequenceMatcher

from backend.app.quellen.modelle import Angaben, Buchfrage

MIT_AUTOR = 0.8                 # so nah muss der Titel sein, wenn der Autor stimmt
OHNE_AUTOR = 0.92               # und so nah, wenn kein Autor bekannt ist
SICHER = 0.95                   # erst so nah darf ein Hintergrundlauf eine ISBN übernehmen
_HAUPTTITEL = re.compile(r"\s*[:;/|=]\s+|\s+-\s+|\.\s+")
_ZUSAETZE = re.compile(r"\b(hrsg|hg|herausgeber|herausgeberin|ed|eds|prof|dr|phil|jur|med|ing|von und zu)\b\.?", re.IGNORECASE)
_DATEI = re.compile(r"\.(pdf|epub|mobi|txt|md|docx?|indd|qxd|xlsx?|pptx?)\b|^microsoft (word|powerpoint|excel)\b|^(untitled|unbenannt|titel|document|dokument)\d*$|_", re.IGNORECASE)


_UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss", "ẞ": "SS"})


def umschrift(text: str) -> str:
    """Deutsche Umlaute und ß in der Umschrift ("Ölmühle" als "Oelmuehle"), sonst unverändert: so sind "Müller" und "Mueller"
    gleich, auch für einen Index, der Akzente selbst entfernt."""
    return (text or "").translate(_UMSCHRIFT)


def norm(text: str) -> str:
    """Klein, ohne Akzente, ß als ss, Satzzeichen als Leerzeichen."""
    t = unicodedata.normalize("NFKD", (text or "").replace("ß", "ss").replace("ẞ", "ss"))
    t = "".join(z for z in t if not unicodedata.combining(z)).lower()
    return " ".join(re.sub(r"[^\w+#]+", " ", t.replace("_", " ")).split())


def haupttitel(titel: str) -> str:
    return _HAUPTTITEL.split(titel or "", maxsplit=1)[0]


def _naehe(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if set(re.findall(r"\d+", a)) != set(re.findall(r"\d+", b)) and re.search(r"\d", a) and re.search(r"\d", b):
        return 0.6 * SequenceMatcher(None, a, b).ratio()      # anderer Band, andere Auflage, anderes Heft
    return SequenceMatcher(None, a, b).ratio()


def titel_naehe(gesucht: str, titel: str, untertitel: str = "") -> float:
    """0 bis 1. Ganzer Titel gegen ganzen Titel, sonst Haupttitel gegen Haupttitel (etwas weniger wert)."""
    g, t, voll = norm(gesucht), norm(titel), norm(f"{titel} {untertitel}")
    kurz = norm(haupttitel(gesucht))
    ganz = max(_naehe(g, t), _naehe(g, voll))
    teil = max(_naehe(kurz, norm(haupttitel(titel))), _naehe(kurz, t)) if len(kurz) > 5 else 0.0
    return max(ganz, 0.95 * teil)


def gleicher_band(gesucht: str, titel: str) -> bool:
    """Strenger als titel_naehe, für einen bestimmten Band einer Reihe (BF-98): ein gleicher Haupttitel reicht nicht ("Erster Teil"
    und "Dritter Teil" heißen sonst gleich). Der ganze Titel ist fast gleich (andere Zahlen zählen wie bei titel_naehe), oder
    einer ist genau der Haupttitel des anderen, ohne Untertitel."""
    g, t = norm(gesucht), norm(titel)
    return bool(g and t) and (_naehe(g, t) >= SICHER or g == norm(haupttitel(titel)) or t == norm(haupttitel(gesucht)))


def suchbar(titel: str) -> bool:
    """Ein Titel, nach dem sich suchen lässt, und nicht der Name einer Datei."""
    t = (titel or "").strip()
    return len(norm(t)) >= 4 and not _DATEI.search(t)


def nachname(name: str) -> str:
    n = _ZUSAETZE.sub(" ", name or "").strip(" ,;.")
    if "," in n:
        return norm(n.split(",", 1)[0])
    worte = norm(n).split()
    return worte[-1] if worte else ""


def natuerlich(name: str) -> str:
    """"Beispiel, Erika" -> "Erika Beispiel"; ohne Komma bleibt der Name."""
    n = " ".join(unicodedata.normalize("NFC", name or "").split()).strip(" ,;")
    if "," not in n:
        return n
    nach, vor = (t.strip() for t in n.split(",", 1))
    return f"{vor} {nach}".strip()


def namen_gleich(a: str, b: str) -> bool:
    """Derselbe Mensch dem Namen nach: gleicher Nachname, und die Vornamen widersprechen sich nicht."""
    na, nb = norm(natuerlich(a)).split(), norm(natuerlich(b)).split()
    if not na or not nb or na[-1] != nb[-1]:
        return False
    va, vb = na[:-1], nb[:-1]
    return not va or not vb or va[0][0] == vb[0][0] and (len(va[0]) == 1 or len(vb[0]) == 1 or va[0] == vb[0])


def autor_passt(gesucht: Iterable[str], gefunden: Iterable[str]) -> bool | None:
    """Teilen beide einen Nachnamen? None, wenn eine Seite keinen kennt."""
    g, f = {nachname(n) for n in gesucht} - {""}, {nachname(n) for n in gefunden} - {""}
    return bool(g & f) if g and f else None


def _seiten_gleich(a: int, b: int) -> bool:
    return bool(a and b) and abs(a - b) <= max(6, a * 0.03)


def gleiche_ausgabe(frage: Buchfrage, fund: Angaben) -> bool:
    """Jahr oder Umfang stimmen: dann gehören auch Verlag und ISBN zu diesem Buch."""
    return bool(frage.jahr) and frage.jahr == fund.jahr or _seiten_gleich(frage.seiten, fund.seiten)


def punkte(frage: Buchfrage, fund: Angaben) -> float:
    """Wie gut ein Fund passt; 0, wenn er nicht passt."""
    naehe = titel_naehe(frage.titel, fund.titel, fund.untertitel)
    passt = autor_passt(frage.autoren, fund.autoren)
    if passt is False or naehe < (MIT_AUTOR if passt else OHNE_AUTOR):
        return 0.0
    wert = naehe + (0.2 if passt else 0.0)
    if frage.jahr and fund.jahr:
        wert += 0.05 if frage.jahr == fund.jahr else -min(0.04, abs(frage.jahr - fund.jahr) * 0.004)
    if frage.sprache and fund.sprache:
        wert += 0.05 if frage.sprache == fund.sprache else -0.1
    return wert + (0.04 if _seiten_gleich(frage.seiten, fund.seiten) else 0.0)


def bester(frage: Buchfrage, funde: Iterable[Angaben]) -> Angaben | None:
    """Der Fund, der am besten passt, mit der Art des Fundes; None, wenn keiner passt."""
    bewertet = [(punkte(frage, f), -n, f) for n, f in enumerate(funde)]
    if not bewertet or (bestes := max(bewertet, key=lambda b: b[:2]))[0] <= 0:
        return None
    fund = bestes[2]
    sicher = titel_naehe(frage.titel, fund.titel, fund.untertitel) >= SICHER and autor_passt(frage.autoren, fund.autoren) is True
    return fund.model_copy(update={"fund": "titel", "sicher": sicher})
