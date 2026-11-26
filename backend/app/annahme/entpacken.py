"""Eine ZIP auf dem Server auspacken (BF-80): erst das Verzeichnis der ZIP prüfen und einteilen, dann Eintrag für Eintrag
auspacken, nie mehr als erlaubt. Die Grenzen (Anzahl, Größe je Eintrag und zusammen, Tiefe, Verhältnis gegen ZIP-Bomben)
stehen in den Einstellungen (annahme/einstellungen.py).

Pfade aus der ZIP sind nur Hinweise (Ordnernamen schlagen Kategorie, Sammlung oder Etikett vor) und werden nie als Pfad auf
dem Gerät benutzt: wohin ein Eintrag kommt, bestimmt allein, wer auspackt. Ein Eintrag mit `..`, einem absoluten Pfad, als
Verknüpfung oder verschlüsselt wird nicht ausgepackt und steht mit Grund in der Vorschau, ebenso was eine Grenze überschreitet.
Wird beim Auspacken mehr, als das Verzeichnis sagt, bricht der Eintrag ab.

Einteilen: lesbare Buchformate sind Bücher; eine andere Datei, deren Name mit dem Stamm eines Buchs im selben Ordner beginnt
(material/zugehoerig.py), wird sein Begleitmaterial, ebenso ein Buchformat, dessen Rest keinen Band nennt ("X - Schaltpläne.pdf"
zu "X.pdf"); alles andere wird nicht übernommen, mit Grund."""

from __future__ import annotations

import hashlib
import re
import stat
import zipfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from backend.app.annahme.einstellungen import Zipgrenzen
from backend.app.material import arten, zugehoerig
from backend.app.services.sammlungsfinder import erkennen
from backend.app.services.storage import SUPPORTED_FORMATS

STUECK = 1 << 20
VERHAELTNIS_AB = 1 << 20                       # erst ab so viel ausgepackt sagt das Verhältnis etwas (kleine Dateien packen gut)
SYSTEM = {".ds_store", "thumbs.db", "desktop.ini"}
LAUFWERK = re.compile(r"^[A-Za-z]:")
Einteilung = Literal["buch", "material", "rest", "nicht"]   # nicht: wird nicht ausgepackt


class ZipFehler(Exception):
    """Die ganze ZIP geht nicht (unlesbar oder über einer Grenze für die ganze ZIP)."""

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


class ZuGross(Exception):
    """Ein Eintrag wird beim Auspacken größer, als er darf."""


class Eintrag(BaseModel):
    nr: int                                      # Stelle im Verzeichnis der ZIP
    zip_name: str                                # wie er in der ZIP heißt, zum Lesen
    pfad: str                                    # bereinigt, nur als Hinweis
    name: str
    ordner: list[str]
    groesse: int
    gepackt: int
    einteilung: Einteilung = "rest"
    grund: str = ""
    zu: int | None = None                        # bei Material: die Stelle des Buchs

    @property
    def buchformat(self) -> bool:
        return Path(self.name).suffix.lower() in SUPPORTED_FORMATS


def mb(n: int) -> str:
    return f"{n / 1024 / 1024:.1f}".replace(".", ",") + " MB"


def hinweis(name: str) -> tuple[list[str], str] | None:
    """Ordner und Name eines Eintrags, oder None, wenn der Pfad aus der ZIP herausführen könnte."""
    if name.startswith(("/", "\\")) or LAUFWERK.match(name):
        return None
    teile = [t for t in re.split(r"[\\/]+", name) if t not in ("", ".")]
    if not teile or any(t == ".." for t in teile):
        return None
    return teile[:-1], teile[-1]


def _ist_verknuepfung(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def _grund_gegen(info: zipfile.ZipInfo, ordner: list[str], name: str, g: Zipgrenzen) -> str:
    """Warum ein Eintrag nicht ausgepackt wird; leer: er darf."""
    if info.flag_bits & 0x1:
        return "Verschlüsselt, nicht ausgepackt"
    if _ist_verknuepfung(info):
        return "Eine Verknüpfung, keine Datei"
    if ordner and ordner[0] == "__MACOSX" or name.lower() in SYSTEM or name.startswith("._"):
        return "Begleitdatei des Systems"
    if len(ordner) > g.tiefe:
        return f"Liegt {len(ordner)} Ordner tief, erlaubt sind {g.tiefe}"
    if info.file_size > g.datei_bytes:
        return f"Ausgepackt {mb(info.file_size)}, erlaubt sind {g.datei_mb} MB je Datei"
    if info.file_size >= VERHAELTNIS_AB and info.file_size > g.verhaeltnis * max(info.compress_size, 1):
        return f"Auffällig stark gepackt (mehr als {g.verhaeltnis} zu 1), nicht ausgepackt"
    return ""


def verzeichnis(zipdatei: Path, g: Zipgrenzen) -> list[Eintrag]:
    """Alle Dateien der ZIP, geprüft und eingeteilt; ZipFehler, wenn die ganze ZIP nicht geht."""
    try:
        with zipfile.ZipFile(zipdatei) as z:
            infos = [i for i in z.infolist() if not i.is_dir()]
    except (zipfile.BadZipFile, OSError, ValueError) as f:
        raise ZipFehler(f"Die ZIP lässt sich nicht lesen ({type(f).__name__})") from f
    if len(infos) > g.dateien:
        raise ZipFehler(f"Die ZIP hat {len(infos)} Dateien, erlaubt sind {g.dateien}")
    eintraege = []
    for nr, info in enumerate(infos):
        lage = hinweis(info.filename)
        if lage is None:
            eintraege.append(Eintrag(nr=nr, zip_name=info.filename, pfad=Path(info.filename).name or info.filename, name=Path(info.filename).name or "Eintrag",
                                     ordner=[], groesse=info.file_size, gepackt=info.compress_size, einteilung="nicht",
                                     grund="Der Pfad führt aus der ZIP heraus, nicht ausgepackt"))
            continue
        ordner, name = lage
        grund = _grund_gegen(info, ordner, name, g)
        eintraege.append(Eintrag(nr=nr, zip_name=info.filename, pfad="/".join([*ordner, name]), name=name, ordner=ordner, groesse=info.file_size,
                                 gepackt=info.compress_size, einteilung="nicht" if grund else "rest", grund=grund))
    gesamt = sum(e.groesse for e in eintraege if e.einteilung != "nicht")
    if gesamt > g.gesamt_bytes:
        raise ZipFehler(f"Ausgepackt wären es {mb(gesamt)}, erlaubt sind {g.gesamt_mb} MB")
    einteilen(eintraege)
    return eintraege


def _nennt_band(rest: str) -> bool:
    return bool(re.search(r"\d", rest)) or erkennen(f"Reihe {rest.strip(zugehoerig.RAND)}") is not None


def _buch_dazu(e: Eintrag, buecher: list[Eintrag]) -> Eintrag | None:
    """Das Buch im selben Ordner, zu dem der Eintrag nach dem Namen gehört; der längste passende Stamm gewinnt."""
    passend = [(len(zugehoerig.stamm(b.name)), b) for b in buecher
               if b.nr != e.nr and b.ordner == e.ordner and zugehoerig.gehoert_zu(e.name, zugehoerig.stamm(b.name))]
    return max(passend, key=lambda x: x[0])[1] if passend else None


def einteilen(eintraege: list[Eintrag]) -> None:
    offen = [e for e in eintraege if e.einteilung != "nicht"]
    buecher = [e for e in offen if e.buchformat]
    for e in buecher:
        e.einteilung = "buch"
    for e in offen:
        b = _buch_dazu(e, [x for x in buecher if x.einteilung == "buch"])
        if b is None:
            continue
        if e.buchformat and _nennt_band(zugehoerig.rest_hinter(e.name, zugehoerig.stamm(b.name)) or ""):
            continue                                 # "Reihe - Band 2.epub" ist ein eigenes Buch
        e.einteilung, e.zu = "material", b.nr
    for e in offen:
        if e.einteilung == "rest":
            e.grund = f"{arten.von(e.name).name} ohne Buch gleichen Namens"


def auspacken(zipdatei: Path, e: Eintrag, ziel: Path, grenze: int) -> tuple[int, str]:
    """Einen Eintrag nach `ziel`, Stück für Stück; höchstens so viel, wie das Verzeichnis sagt und `grenze` erlaubt (sonst
    ZuGross, `ziel` ist dann fort). Liefert Größe und Prüfsumme."""
    summe, geschrieben = hashlib.sha256(), 0
    hoechstens = min(e.groesse, grenze)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zipdatei) as z, z.open(e.zip_name) as quelle, ziel.open("wb") as aus:
            while stueck := quelle.read(STUECK):
                geschrieben += len(stueck)
                if geschrieben > hoechstens:
                    raise ZuGross()
                summe.update(stueck)
                aus.write(stueck)
    except BaseException:
        ziel.unlink(missing_ok=True)
        raise
    return geschrieben, summe.hexdigest()
