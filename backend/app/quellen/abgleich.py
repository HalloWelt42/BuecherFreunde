"""Passt ein Fund zu dem, was gesucht war? Vergleich von Titeln (mit und ohne Untertitel), Namen und Jahren, ohne Rücksicht
auf Groß und klein, Umlautschreibweise und Satzzeichen. Dazu die Stufe einer ISBN gegen Titel und Autor des Buchs (BF-111), aus
dem, was eine Quelle zu ihr nennt, oder aus dem Text um ihre Fundstelle; beide Wege enden in denselben vier Stufen."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from difflib import SequenceMatcher
from enum import StrEnum

from pydantic import BaseModel, Field

from backend.app.quellen.modelle import Angaben, Buchfrage

MIT_AUTOR = 0.8                 # so nah muss der Titel sein, wenn der Autor stimmt
OHNE_AUTOR = 0.92               # und so nah, wenn kein Autor bekannt ist
SICHER = 0.95                   # erst so nah darf ein Hintergrundlauf eine ISBN übernehmen
ISBN_TITEL = 0.6                # so nah muss der Titel eines Fundes über die ISBN sein, sonst muss der Autor gleich sein
#: Namen in Autorenfeldern, die keinen Menschen nennen (aus Dateiangaben)
KEIN_NAME = frozenset({"unbekannt", "anonym", "unknown", "anonymous", "administrator", "admin", "user", "benutzer"})
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


# -- Stufe einer ISBN gegen das Buch (BF-111) ---------------------------------------------------------------------------
class Stufe(StrEnum):
    """Wie gut eine ISBN zu Titel und Autor des Buchs passt; die Reihenfolge ist die Rangfolge."""

    PASST = "passt"              # Titel und Autor stimmen
    AEHNLICH = "aehnlich"        # stimmt nur ungefähr: Untertitel, ohne Artikel, Vorname abgekürzt, Autor fehlt
    UNBEKANNT = "unbekannt"      # nichts sagt etwas über das Buch zu dieser Nummer
    FREMD = "fremd"              # ein anderer Titel, auch bei gleichem Autor


STUFEN: tuple[Stufe, ...] = tuple(Stufe)
_ARTIKEL = frozenset({"der", "die", "das", "ein", "eine", "the", "a", "an", "le", "la", "les", "il", "lo", "el", "los", "las", "de", "het"})
TITEL_IM_TEXT_MINDESTENS = 6     # so viele Zeichen braucht ein Teil des Titels, um im Text als Titel zu zählen


class Abgleich(BaseModel):
    """Ergebnis eines Abgleichs: die Stufe, warum (kurze Wörter für die Oberfläche) und welche Teile abweichen."""

    stufe: Stufe
    gruende: list[str] = Field(default_factory=list)
    titel_anders: bool = False
    autor_anders: bool = False


def echte_autoren(autoren: Iterable[str]) -> list[str]:
    """Ohne Platzhalter wie "unbekannt", die keinen Menschen nennen."""
    return [a for a in autoren if norm(a) and norm(a) not in KEIN_NAME]


def ohne_artikel(normiert: str) -> str:
    worte = normiert.split()
    return " ".join(worte[1:]) if len(worte) > 1 and worte[0] in _ARTIKEL else normiert


def _titelgruende(gesucht: str, titel: str, untertitel: str) -> list[str]:
    g, t, voll = norm(umschrift(gesucht)), norm(umschrift(titel)), norm(umschrift(f"{titel} {untertitel}"))
    if g in (t, voll):
        return []
    if ohne_artikel(g) in (ohne_artikel(t), ohne_artikel(voll)):
        return ["Titel ohne Artikel"]
    if norm(umschrift(haupttitel(gesucht))) == t or g == norm(umschrift(haupttitel(titel))):
        return ["Untertitel anders"]
    return ["Titel weicht ab"]


def _vorname(a: str, b: str) -> str:
    """Wie sich zwei Namen mit gleichem Nachnamen unterscheiden; leer, wenn gar nicht."""
    na, nb = norm(umschrift(natuerlich(a))), norm(umschrift(natuerlich(b)))
    if na == nb:
        return ""
    if not namen_gleich(a, b):
        return "anderer Vorname"
    kurz = [w for w in (na.split()[:-1] + nb.split()[:-1]) if len(w) == 1]
    return "Vorname abgekürzt" if kurz else "Vorname fehlt"


def _autorgruende(autoren: list[str], gefunden: list[str], passt: bool | None) -> list[str]:
    if passt is None:
        return ["Autor fehlt"] if autoren and not gefunden else []
    if passt is False:
        return ["anderer Autor"]
    paare = [(a, b) for a in autoren for b in gefunden if nachname(a) == nachname(b)]       # wie autor_passt
    unterschiede = [u for a, b in paare if (u := _vorname(a, b))]
    return unterschiede[:1] if len(unterschiede) == len(paare) else []


def isbn_abgleich(frage: Buchfrage, fund: Angaben) -> Abgleich:
    """Die Stufe eines Fundes über die ISBN. Ein Titel unter `ISBN_TITEL` ist ein anderes Buch, auch bei gleichem Autor (etwa
    ein anderes Buch derselben Autorin aus der Verlagsanzeige); passt nur, was ohne jeden Unterschied stimmt. Ohne lesbaren
    Titel entscheidet der Autor, ohne beides ist die Stufe unbekannt. Platzhalter wie "unbekannt" zählen nicht als Autor."""
    autoren = echte_autoren(frage.autoren)
    autor = autor_passt(autoren, fund.autoren)
    autorgruende = _autorgruende(autoren, fund.autoren, autor)
    autor_anders = autor is False or any(g != "Autor fehlt" for g in autorgruende)
    if suchbar(frage.titel) and fund.titel:
        if titel_naehe(frage.titel, fund.titel, fund.untertitel) < ISBN_TITEL:
            return Abgleich(stufe=Stufe.FREMD, gruende=["anderer Titel", *(["gleicher Autor"] if autor else [])], titel_anders=True, autor_anders=autor is False)
        titelgruende = _titelgruende(frage.titel, fund.titel, fund.untertitel)
        gruende = titelgruende + autorgruende
        return Abgleich(stufe=Stufe.AEHNLICH if gruende else Stufe.PASST, gruende=gruende, titel_anders=bool(titelgruende), autor_anders=autor_anders)
    if autor is False:
        return Abgleich(stufe=Stufe.FREMD, gruende=["anderer Autor"], autor_anders=True)
    if autor is True:
        return Abgleich(stufe=Stufe.AEHNLICH, gruende=["Titel nicht vergleichbar", *autorgruende], autor_anders=autor_anders)
    return Abgleich(stufe=Stufe.UNBEKANNT)


def isbn_fund_passt(frage: Buchfrage, fund: Angaben) -> bool:
    """Gehört ein Fund über die ISBN zu diesem Buch? Eine ISBN aus dem Buch kann einem anderen gehören, etwa aus einer
    Literaturliste oder Verlagsanzeige (BF-111): alles außer der Stufe fremd (isbn_abgleich)."""
    return isbn_abgleich(frage, fund).stufe is not Stufe.FREMD


def _im_text(teil: str, text: str) -> bool:
    return bool(teil) and f" {teil} " in text


def titel_im_text(titel: str, text: str) -> str:
    """Steht der Titel im Text? "voll", "haupt" (nur der Haupttitel), "ohne_artikel" oder leer. `text` ist mit `textform` vorbereitet."""
    t = norm(umschrift(titel))
    if _im_text(t, text):
        return "voll"
    h = norm(umschrift(haupttitel(titel)))
    if h != t and len(h) >= TITEL_IM_TEXT_MINDESTENS and _im_text(h, text):
        return "haupt"
    o = ohne_artikel(t)
    if o != t and len(o) >= TITEL_IM_TEXT_MINDESTENS and _im_text(o, text):
        return "ohne_artikel"
    return ""


def textform(text: str) -> str:
    """Ein Text, vorbereitet für titel_im_text und autor_im_text: normiert, mit Leerzeichen an den Rändern."""
    return f" {norm(umschrift(text))} "


def autor_im_text(autoren: Iterable[str], text: str) -> bool:
    return any(_im_text(nachname(umschrift(a)), text) for a in autoren)


def text_abgleich(frage: Buchfrage, umfeld: str, fremdes_umfeld: bool) -> Abgleich:
    """Die Stufe einer ISBN aus dem Text um ihre Fundstelle. Passt, wenn Titel und Autor daneben stehen (ohne bekannten Autor genügt
    der ganze Titel, nur nicht in einer Literaturliste oder Verlagsanzeige: `fremdes_umfeld`). Dort ist eine Nummer ohne den Titel des
    Buchs fremd, auch wenn sein Autor daneben steht; anderswo ist sie unbekannt."""
    text = textform(umfeld)
    autoren = echte_autoren(frage.autoren)
    titel = titel_im_text(frage.titel, text) if suchbar(frage.titel) else ""
    autor: bool | None = autor_im_text(autoren, text) if autoren else None
    if titel == "voll" and (autor is True or (autor is None and not fremdes_umfeld)):
        return Abgleich(stufe=Stufe.PASST)
    if titel:
        gruende = {"haupt": ["nur der Haupttitel"], "ohne_artikel": ["Titel ohne Artikel"]}.get(titel, [])
        gruende += ["Autor steht nicht daneben"] if autor is not True else []
        return Abgleich(stufe=Stufe.AEHNLICH, gruende=gruende, titel_anders=titel != "voll")
    if autor:
        if fremdes_umfeld and suchbar(frage.titel):
            return Abgleich(stufe=Stufe.FREMD, gruende=["anderer Titel", "gleicher Autor"], titel_anders=True)
        return Abgleich(stufe=Stufe.AEHNLICH, gruende=["nur der Autor steht daneben"], titel_anders=True)
    if fremdes_umfeld:
        return Abgleich(stufe=Stufe.FREMD, gruende=["anderer Titel"], titel_anders=True)
    return Abgleich(stufe=Stufe.UNBEKANNT)


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
