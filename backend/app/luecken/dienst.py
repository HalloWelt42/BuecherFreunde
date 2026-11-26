"""Lücken einer Sammlung, wie ein Profil sie sieht (BF-75): je Sprache eine Reihe mit eigener Zählung ab 1, die Bücher und die
fehlenden Bände in der Folge der Bände, mit den Angaben der Quelle, dem Text zum Kopieren und der fertigen Suchadresse.

Gerechnet wird nur mit den Büchern, die das Profil sieht (familie/sichtbar.py): ein Band, den ein anderes Profil privat hat,
ist für es eine Lücke, ein unsichtbarer Band zeigt sich nie als vorhanden. Die Hauptsprache (für Bücher ohne Sprache) und ob
eine Sprache Nummern hat, gelten für die ganze Sammlung, damit Nachschlagen und Ansicht dieselben Reihen meinen. Dazu die
kurze Zeile der Sammlungsvorschläge und die Hinweise, wenn eine Datei nicht zu ihrer Lücke passt."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from backend.app.familie.modelle import Profil
from backend.app.familie.sichtbar import Sicht, nur_sichtbare
from backend.app.core.database import db
from backend.app.luecken import speicher, suchadresse
from backend.app.luecken.bandnummer import Bandnummer, lesen, platz
from backend.app.luecken.modelle import Buchband, Luecke, Nachschlagen, Platz, Quellband, Reihe, Reihenstand, Sammlungsluecken
from backend.app.luecken.rechnen import belegt, fehlen_satz, fehlende, vorschlagszeile
from backend.app.luecken.sprachen import folge, hauptsprache, sprache_von, sprachname
from backend.app.quellen import isbn as nummern
from backend.app.quellen import reihen as reihen_der_quellen
from backend.app.quellen.abgleich import MIT_AUTOR, SICHER, titel_naehe
from backend.app.quellen.regeln import REGELN
from backend.app.quellen.sprache import kuerzel
from backend.app.services.sammlungsfinder import autor_schluessel, erkennen, erster_autor, ohne_autor

AUS = "Die Platzhalter dieser Sammlung sind aus"
OHNE_NUMMER = "Kein Band dieser Sprache hat eine Nummer"


def haeufigster_autor(baende: list[Buchband]) -> str:
    """Der erste Autor, der in den Büchern am häufigsten steht ("Vorname Nachname"); leer, wenn keiner dasteht. Die Ansicht gibt
    nur, was das Profil sieht; für eine Frage an eine Quelle zählen private Bücher nie."""
    zahlen = Counter(a for b in baende if (a := erster_autor(b.autor)))
    return zahlen.most_common(1)[0][0] if zahlen else ""


def reihenname(baende: list[Buchband], sammlung: str) -> str:
    """Nach welchem Namen die Quelle für diese Bände gefragt wird: der Reihe, die ihre Titel am häufigsten nennen ("Lighthouse
    Quay, Book 2"), sonst der Sammlung. Eine Übersetzung heißt oft anders als die Sammlung. Ist der häufigste Name nur eine
    Abkürzung aus Dateinamen ("DRdZ 17 - ..."), kennt ihn kein Katalog; dann gilt der Name der Sammlung. Private Bücher zählen
    nie mit."""
    zahlen = Counter(e.reihe for b in baende if not b.privat and (e := erkennen(b.titel)))
    if not zahlen:
        return sammlung
    name = zahlen.most_common(1)[0][0]
    return sammlung if sammlung and abkuerzung(name) else name


def abkuerzung(name: str) -> bool:
    """Ein einzelnes kurzes Wort mit mehreren Großbuchstaben, etwa "DRdZ" oder "HdR"; kein Katalog führt eine Reihe so."""
    wort = name.strip()
    return " " not in wort and 2 <= len(wort) <= 6 and sum(z.isupper() for z in wort) >= 2


def luecke(reihe: str, sprache: str, nummer: int, q: Quellband | None, autor: str, vorlage: str) -> Luecke:
    """Ein fehlender Band: Angaben der Quelle, sonst Reihe, Autor der Sammlung und Nummer (auch zum Kopieren und Suchen)."""
    titel, isbn = (q.titel, q.isbn) if q else ("", "")
    autor = (q.autor if q and q.autor else "") or autor
    reihe_und_band = f"{reihe} Band {nummer}"
    zeigen = nummern.mit_strichen(isbn) or isbn
    kopieren = ", ".join(t for t in (titel or reihe_und_band, autor, reihe_und_band if titel else "", f"ISBN {zeigen}" if zeigen else "") if t)
    werte = {"titel": titel or reihe_und_band, "autor": autor, "isbn": nummern.sauber(isbn), "band": str(nummer), "reihe": reihe, "sprache": sprache}
    return Luecke(sprache=sprache, nummer=nummer, titel=titel, autor=autor, isbn=zeigen, jahr=q.jahr if q else None, quelle=q.quelle if q else "",
                  kopieren=kopieren, suchadresse=suchadresse.fuellen(vorlage, werte))


def _nachschlagen(st: Reihenstand | None, an: bool, mit_nummern: bool, sprache: str, reihe: str) -> Nachschlagen:
    if st is not None and st.stand != "offen":
        return Nachschlagen(stand=st.stand, quelle=st.quelle, quelle_name=REGELN[st.quelle].name if st.quelle in REGELN else st.quelle,
                            reihe=st.gefragt, grund=st.grund, am=st.nachgeschlagen_am)
    if not an:
        return Nachschlagen(stand="nicht", grund=AUS)
    if not mit_nummern:
        return Nachschlagen(stand="nicht", grund=OHNE_NUMMER)
    katalog = reihen_der_quellen.fuer_sprache(sprache)
    if katalog is None:
        return Nachschlagen(stand="offen", reihe=reihe, grund=f"{reihen_der_quellen.katalogname(sprache)} ist abgeschaltet")
    return Nachschlagen(stand="offen", quelle=katalog.regel.kennung, quelle_name=katalog.regel.name, reihe=reihe)


@dataclass(frozen=True)
class Reihenlage:
    """Was für eine Sprache einer Sammlung feststeht, bevor das Regal gebaut wird."""

    sammlung: dict
    sprache: str
    buecher: list[Buchband]                     # die das Profil sieht; aus ihnen Name der Reihe und Autor dieser Sprache
    alle: list[Buchband]                        # alle dieser Sprache: ob es Nummern gibt, gilt für die ganze Sammlung
    stand: Reihenstand | None
    quelle: dict[tuple[str, int], Quellband]
    ausgeblendet: set[int]
    autor: str                                  # der Sammlung, falls die Bücher dieser Sprache keinen nennen
    vorlage: str

    def reihe(self) -> Reihe:
        an = bool(self.sammlung["luecken"])
        nummer = {b.id: lesen(b.band) for b in self.buecher}
        plaetze = belegt(nummer.values())
        st = self.stand or Reihenstand(sprache=self.sprache)
        gesamt, herkunft = st.gilt()
        fehlen = fehlende(plaetze, gesamt, self.ausgeblendet) if an else []
        name = reihenname(self.buecher, self.sammlung["name"])
        autor = haeufigster_autor(self.buecher) or self.autor
        eintraege: list[tuple[tuple, Platz]] = [
            ((nummer[b.id].ordnung, 0, b.titel.casefold(), b.id),
             Platz(art="buch", band=b.band, nummer=nummer[b.id].von, zwischen=nummer[b.id].zwischen, buch_id=b.id)) for b in self.buecher]
        eintraege += [((platz(n).ordnung, 1, "", 0),
                       Platz(art="luecke", band=str(n), nummer=n,
                             luecke=luecke(name, self.sprache, n, self.quelle.get((self.sprache, n)), autor, self.vorlage)))
                      for n in fehlen]
        mit_nummern = any(lesen(b.band).plaetze for b in self.alle)
        return Reihe(sprache=self.sprache, name=sprachname(self.sprache), reihe=name, gesamt=gesamt, herkunft=herkunft,
                     quelle_gesamt=st.quelle_gesamt, eigene=st.eigene, buecher=len(self.buecher),
                     nachschlagen=_nachschlagen(self.stand, an, mit_nummern, self.sprache, name),
                     belegt=len(plaetze), fehlen=fehlen, zeile=fehlen_satz(fehlen), eintraege=[p for _, p in sorted(eintraege, key=lambda e: e[0])])


async def ansicht(sammlung_id: int, p: Profil, vorlage: str | None = None) -> Sammlungsluecken:
    """Die Lücken der Sammlung für dieses Profil; ein Kind sieht eine Sammlung ohne freigegebene Bücher nicht (SammlungFehlt).
    `vorlage`: eine andere Suchadresse als die gemerkte (Probe)."""
    sammlung = await speicher.sammlung(sammlung_id)
    alle = await speicher.buchbaende(sammlung_id)
    sichtbar = set(await nur_sichtbare(Sicht.von(p), [b.id for b in alle]))
    if p.kind and not sichtbar:
        raise speicher.SammlungFehlt("Sammlung nicht gefunden")
    haupt = hauptsprache(b.sprache for b in alle)
    gesehen = speicher.je_sprache([b for b in alle if b.id in sichtbar], haupt)
    ganz = speicher.je_sprache(alle, haupt)
    staende, quelle = await speicher.reihenstaende(sammlung_id), await speicher.quellbaende(sammlung_id)
    ausgeblendet = await speicher.ausgeblendete(sammlung_id)
    weg: dict[str, set[int]] = defaultdict(set)
    for a in ausgeblendet:
        weg[a.sprache].add(a.nummer)
    autor = haeufigster_autor([b for liste in gesehen.values() for b in liste])
    vorlage = await suchadresse.lesen() if vorlage is None else vorlage
    reihen = [Reihenlage(sammlung, s, gesehen[s], ganz.get(s, []), staende.get(s), quelle, weg[s], autor, vorlage).reihe()
              for s in folge(gesehen, haupt)]
    return Sammlungsluecken(sammlung_id=sammlung_id, name=sammlung["name"], autor=autor, an=bool(sammlung["luecken"]), reihen=reihen,
                            ausgeblendet=ausgeblendet)


async def erste_luecke(p: Profil, vorlage: str) -> tuple[str, Luecke] | None:
    """Ein fehlender Band, den das Profil sieht, mit der Adresse nach dieser Vorlage (Probe der Suchadresse): der erste mit
    bekanntem Titel, sonst der erste."""
    ohne_titel = None
    for z in await db.fetch_all("SELECT id FROM collections WHERE luecken = 1 ORDER BY sort_order, name, id"):
        try:
            a = await ansicht(z["id"], p, vorlage)
        except speicher.SammlungFehlt:
            continue
        for r in a.reihen:
            for e in r.eintraege:
                if e.luecke is not None and e.luecke.titel:
                    return a.name, e.luecke
                if e.luecke is not None and ohne_titel is None:
                    ohne_titel = (a.name, e.luecke)
    return ohne_titel


# -- Sammlungsvorschläge ----------------------------------------------------------------------------------------------------

async def vorschlagszeilen(vorschlaege: dict[int, list[tuple[int, str]]]) -> dict[int, str]:
    """Je Vorschlag die kurze Zeile aus den erkannten Bandnummern seiner Bücher (Buch, Band), je Sprache gezählt; keine Quelle."""
    ids = sorted({b for liste in vorschlaege.values() for b, _ in liste})
    sprachen = {z["id"]: z["sprache"] for z in await db.fetch_all(
        f"SELECT id, COALESCE(language, '') AS sprache FROM books WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))} if ids else {}
    aus = {}
    for nr, liste in vorschlaege.items():
        haupt = hauptsprache(sprachen.get(b, "") for b, _ in liste)
        je: dict[str, list[Bandnummer]] = defaultdict(list)
        for b, band in liste:
            je[sprache_von(sprachen.get(b, ""), haupt)].append(lesen(band))
        aus[nr] = vorschlagszeile(dict(je))
    return aus


# -- Hochladen in eine Lücke ---------------------------------------------------------------------------------------------------

def _titel_passt(titel: str, ohne_reihe: str, erwartet: str) -> bool:
    return max(titel_naehe(erwartet, t) for t in (titel, ohne_reihe) if t) >= MIT_AUTOR


async def abweichungen(sammlung_id: int, band: str, sprache: str, titel: str, dateiname: str, autor: str) -> list[str]:
    """Kurze Sätze, wenn eine Datei nicht zu ihrer Lücke passt: sie nennt einen anderen Band, oder ihr Titel ist ein anderer als
    der, den die Quelle für die Lücke kennt. Die Sprache vergleicht die Vorschau selbst (annahme/zuordnen.py)."""
    nummer = lesen(band).von
    if nummer is None:
        return []
    erkannt = erkennen(titel) or erkennen(ohne_autor(dateiname, autor_schluessel(erster_autor(autor))))
    aus = []
    if erkannt and (genannt := lesen(erkannt.band).von) is not None and genannt != nummer:
        aus.append(f"Die Datei nennt Band {erkannt.band}, die Lücke ist Band {band}")
    sprache = kuerzel(sprache) or await speicher.hauptsprache_der_sammlung(sammlung_id)
    erwartet = await speicher.quellband(sammlung_id, sprache, nummer)
    if erwartet and erwartet.titel and titel and not _titel_passt(titel, erkannt.titel if erkannt else "", erwartet.titel):
        aus.append(f"Die Datei heißt {titel}, die Lücke {erwartet.titel}")
    return aus


async def band_nach_titel(sammlung_id: int, sprache: str, titel: str) -> int | None:
    """Für einen Stapel in eine Sammlung: der Band, den die Quelle unter diesem Titel kennt (sicher gleich, wie bei den Quellen);
    None, wenn keiner so heißt."""
    if not titel:
        return None
    sprache = kuerzel(sprache) or await speicher.hauptsprache_der_sammlung(sammlung_id)
    naehe, nummer = max(((titel_naehe(q.titel, titel), q.nummer) for (s, _), q in (await speicher.quellbaende(sammlung_id)).items()
                         if s == sprache and q.titel), default=(0.0, None))
    return nummer if naehe >= SICHER else None
