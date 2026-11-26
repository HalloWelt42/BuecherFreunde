"""Formen des Begleitmaterials (BF-81) für Schnittstelle und Dienst."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, StringConstraints

from backend.app.ablage.namen import VERBOTEN
from backend.app.models.grenzen import MATERIALNAME

Ort = Literal["kellerwolke", "geraet"]
Herkunft = Literal["buchseite", "hochladen", "erkannt"]
Textstand = Literal["offen", "fertig", "ohne", "fehler"]


def _dateiname(wert: str) -> str:
    if VERBOTEN.search(wert) or wert in (".", ".."):
        raise ValueError("ohne / \\ : * ? \" < > | und Steuerzeichen")
    return wert


Materialname = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MATERIALNAME), AfterValidator(_dateiname)]


class Material(BaseModel):
    """Eine Datei Begleitmaterial, wie die Buchseite sie zeigt."""

    id: str
    buch_id: int
    name: str
    art: str                                    # aus material/arten.json
    art_name: str                               # etwa PDF, Bild, Tabelle
    zeichen: str                                # Font Awesome, ohne fa-
    groesse: int
    ort: Ort
    pfad: str                                   # in der Kellerwolke oder auf dem Gerät
    herkunft: Herkunft
    oeffnen: bool                               # öffnet in der App; sonst Herunterladen
    lesbar: bool                                # sein Text kommt in die Suche
    text_stand: Textstand
    text_seiten: int
    angelegt_am: str


class Fund(BaseModel):
    """Eine Datei neben dem Original in der Kellerwolke, die nach dem Namen zum Buch gehört; erst ein Ja macht sie zu Material."""

    knoten: str
    buch_id: int
    name: str
    groesse: int
    pfad: str
    gefunden_am: str


class Materialliste(BaseModel):
    material: list[Material]
    funde: list[Fund]
    ort: Ort                                    # wo neues Material hinkommt
    groesse: int                                # alles zusammen


class Umbenennen(BaseModel):
    name: Materialname


class Materialfolgen(BaseModel):
    """Was Entfernen bewirkt; `stand` braucht DELETE, damit nur gelöscht wird, was die Vorschau zeigte."""

    id: str
    name: str
    buch_id: int
    titel: str
    ort: Ort
    pfad: str
    groesse: int
    papierkorb: bool                            # True: in den Papierkorb der Kellerwolke; False: auf dem Gerät endgültig fort
    suche: bool                                 # sein Text steht in der Suche und fehlt danach
    seiten: int
    stand: str


class Abgleichstand(BaseModel):
    """Der Abgleich neben den Originalen in der Kellerwolke, ein Auftrag im Hintergrund."""

    bereit: bool                                # die Kellerwolke ist angebunden
    laeuft: bool
    ordner: int = 0                             # durchgesehen im laufenden oder letzten Lauf
    ordner_gesamt: int = 0
    gefunden: int = 0                           # offene Funde
    grund: str = ""
    zuletzt: str | None = None


class Textlauf(BaseModel):
    offen: int
    fertig: int
    ohne: int
    fehler: int
    laeuft: bool


class Materialstand(BaseModel):
    abgleich: Abgleichstand
    texte: Textlauf


class Materialtreffer(BaseModel):
    """Ein Treffer der Wortsuche im Begleitmaterial; er nennt das Buch und die Datei."""

    material_id: str
    buch_id: int
    titel: str
    autor: str
    name: str
    seite: int | None
    auszug: str
