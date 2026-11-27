"""Modelle der Familie (BF-78): Profile mit ihren Einstellungen, was die Schnittstelle zeigt und annimmt. Geheimnisse (PIN,
Bild-PIN, Profilschlüssel) stehen in keinem Modell, das hinausgeht; `hat_pin` sagt nur, ob es eine gibt.

Einstellungen gibt es zweimal: gespeichert steht nur, was die Eltern gewählt haben (`Einstellungen`, ohne Wahl gilt die Stufe
oder die Vorgabe nach dem Alter); hinaus geht, was wirkt (`Profileinstellungen`)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator

from backend.app.familie.stufen import (
    Darstellung, Einblickart, Gestaltungsart, Lesehilfen, Leseschrift, Rollenname, Schriftwahl, Uhrart, Uhrzeit, stufenbuch,
)
from backend.app.models.book import BookListItem
from backend.app.models.grenzen import FarbeOderLeer, Nr
from backend.app.vorlesen.modelle import Stimmwahl, Vorlesestand, Vorlesewahl


def _stufe_gibt_es(schluessel: str) -> str:
    if not stufenbuch().hat_stufe(schluessel):
        raise ValueError(f"erlaubt ist {', '.join(s.schluessel for s in stufenbuch().stufen)}")
    return schluessel


def _geburtsjahr(jahr: int) -> int:
    if not date.today().year - 120 <= jahr <= date.today().year:
        raise ValueError(f"zwischen {date.today().year - 120} und {date.today().year}")
    return jahr


def _ziffern(pin: str) -> str:
    z = stufenbuch().zugang
    if not pin.isdigit() or not z.pin_stellen_von <= len(pin) <= z.pin_stellen_bis:
        raise ValueError(f"{z.pin_stellen_von} bis {z.pin_stellen_bis} Ziffern")
    return pin


def _bilder(bilder: list[str]) -> list[str]:
    z = stufenbuch().zugang
    if len(bilder) != z.bild_pin_anzahl:
        raise ValueError(f"genau {z.bild_pin_anzahl} Bilder")
    if fremd := [b for b in bilder if b not in z.bilder]:
        raise ValueError(f"unbekannte Bilder: {', '.join(fremd)}")
    return bilder


Profilname = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Zeichen = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50, pattern=r"^[a-z0-9-]*$")]
Stufenname = Annotated[str, AfterValidator(_stufe_gibt_es)]
Geburtsjahr = Annotated[int, AfterValidator(_geburtsjahr)]
Pin = Annotated[str, StringConstraints(max_length=20), AfterValidator(_ziffern)]
BildPin = Annotated[list[Annotated[str, StringConstraints(max_length=30)]], Field(max_length=10), AfterValidator(_bilder)]
Profilkennung = Annotated[str, StringConstraints(pattern=r"^[0-9a-f-]{36}$")]
Katzenname = Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)]
Geheimnis = Annotated[str, StringConstraints(max_length=20)]


# -- Einstellungen je Profil ---------------------------------------------------------------------------------------------------

class LesehilfenWahl(BaseModel):
    """Was die Eltern je Kind anders wollen als die Stufe; leer: wie die Stufe."""

    mitlesen: bool | None = None
    tempo: float | None = Field(None, ge=0.5, le=1.5)
    silben: bool | None = None
    lesezeile: bool | None = None
    schrift: Schriftwahl | None = None
    schrift_wahl: Leseschrift | None = None                  # normal oder Kinderschrift; in Groß ändert das Kind sie selbst
    hinweise_sprechen: bool | None = None
    tasten_ansagen: bool | None = None
    stimme: Stimmwahl | None = None                          # eine der Vertonung oder die des Geräts; leer: die Stimme der Familie


class Lesezeitregel(BaseModel):
    """Lesezeit je Kind: Grenze am Tag und eine Ruhezeit (bis vor von: über Mitternacht). Ganz aus: an und ruhe_an false."""

    an: bool = True                                          # aus: keine Grenze am Tag
    minuten: int = Field(30, ge=1, le=24 * 60)
    ruhe_an: bool = True
    ruhe_von: Uhrzeit = "18:00"
    ruhe_bis: Uhrzeit = "06:30"
    vorlesen_zaehlt: bool = True


class KatzeWahl(BaseModel):
    an: bool | None = None                                   # leer: an für Kinder
    name: Katzenname = ""
    schnurren: bool = False                                  # nur auf Wunsch


class Einstellungen(BaseModel):
    """Gespeichert (profil.einstellungen): nur die Wahl der Eltern."""

    lesehilfen: LesehilfenWahl = Field(default_factory=LesehilfenWahl)
    lesezeit: Lesezeitregel | None = None                    # leer: die Vorgabe nach dem Alter
    katze: KatzeWahl = Field(default_factory=KatzeWahl)
    gestaltung: Gestaltungsart | None = None                 # leer: wie die Stufe (BF-88)
    uhr: Uhrart | None = None                                # leer: wie die Stufe
    vorlesen: Vorlesewahl = Field(default_factory=Vorlesewahl)   # Stimme im Leser (Erwachsene) und Werte der Vertonung (BF-14)


class EinstellungenEingabe(BaseModel):
    """Beim Anlegen und Ändern: jeder genannte Teil ersetzt den gespeicherten, die übrigen bleiben."""

    lesehilfen: LesehilfenWahl | None = None
    lesezeit: Lesezeitregel | None = None
    katze: KatzeWahl | None = None
    gestaltung: Gestaltungsart | None = None
    uhr: Uhrart | None = None
    vorlesen: Vorlesewahl | None = None


class Katze(BaseModel):
    an: bool
    name: str
    schnurren: bool
    name_eingabe: Literal["vorschlaege", "tippen"] = "tippen"   # Vorlesealter: aus vorgelesenen Vorschlägen wählen


class Profileinstellungen(BaseModel):
    """Was für ein Kind wirkt: Lesehilfen der Stufe mit der Wahl der Eltern, Lesezeit (Wahl oder Vorgabe), Katze, Gestaltung
    und Uhr im Kopf."""

    lesehilfen: Lesehilfen
    lesezeit: Lesezeitregel
    katze: Katze
    gestaltung: Gestaltungsart | None                        # leer: kein Kinderbereich (Jugend)
    uhr: Uhrart
    vorlesen: Vorlesewahl                                    # Werte der Vertonung für Vorlesen (BF-14); die Stimme steht in lesehilfen


# -- Profile -------------------------------------------------------------------------------------------------------------------

class Profil(BaseModel):
    """Ein Profil, wie der Server es kennt, ohne Geheimnisse; geht so nie hinaus (dafür `ProfilEintrag`)."""

    id: str
    name: str
    zeichen: str
    farbe: str
    rolle: Rollenname
    stufe: str | None
    hat_pin: bool
    hat_bild_pin: bool
    geburtsjahr: int | None
    einstellungen: Einstellungen
    sortierung: int
    angelegt_am: str
    name_vom_konto: bool = False                             # der Name kommt beim nächsten Anmelden aus dem Konto

    @property
    def kind(self) -> bool:
        return self.rolle == "kind"

    @property
    def erwachsen(self) -> bool:
        return not self.kind


class ProfilEintrag(BaseModel):
    """Ein Profil, wie es hinausgeht. Geburtsjahr und Einstellungen nur für die, die es ändern dürfen (und es selbst)."""

    id: str
    name: str
    zeichen: str
    farbe: str
    rolle: Rollenname
    stufe: str | None
    hat_pin: bool
    hat_bild_pin: bool
    geburtsjahr: int | None = None
    einstellungen: Profileinstellungen | None = None         # nur Kinder


class Geraetestand(BaseModel):
    gebunden_an: str | None = None                           # das Gerät öffnet nur dieses Profil; leer auch, solange es offen ist
    fest_auf: str | None = None                              # worauf es fest gestellt ist, auch wenn es gerade offen ist
    offen: bool = False                                      # nach der Eltern-PIN darf hier eine Weile jemand anders wählen


class Familie(BaseModel):
    profile: list[ProfilEintrag]
    braucht_wahl: bool                                       # ohne Wahl geht es nicht (mehrere Profile oder eine PIN)
    aktiv: str | None = None                                 # das Profil des mitgeschickten Schlüssels, wenn er gilt
    geraet: Geraetestand
    stimme: str = ""                                         # Vorlesestimme der Familie für die Ansagen; leer: keine


class Lesezeitstand(BaseModel):
    an: bool                                                 # es gilt eine Grenze oder Ruhezeit
    heute_s: int                                             # gezählt heute (Vorlesen, wenn es mitzählt)
    grenze_s: int | None                                     # leer: ohne Grenze
    rest_s: int | None
    hinweis_ab_s: int | None                                 # ab so viel heute_s der sanfte Hinweis
    ruht: bool                                               # jetzt ist Ruhezeit
    ruhe_bis: str | None                                     # wann sie endet, HH:MM


class Ich(BaseModel):
    profil: ProfilEintrag
    faehigkeiten: list[str]
    darstellung: Darstellung | dict                          # Kinder: nach Stufe und Schriftwahl; Erwachsene: leer
    lesehilfen: Lesehilfen | None
    lesezeit: Lesezeitstand
    katze: Katze
    einblick: list[Einblickart]                              # was die Eltern sehen, für das Kind sichtbar; leer bei Erwachsenen
    gestaltung: Gestaltungsart | None = None                 # Kinderbereich klein oder groß; leer: die Oberfläche der App
    uhr: Uhrart | None = None                                # Uhr im Kopf der Gestaltung groß; leer bei Erwachsenen
    vorlesen: Vorlesestand                                   # Stimme und Werte, mit denen dieses Profil vorgelesen bekommt (BF-14)


# -- Stufen für die Oberfläche --------------------------------------------------------------------------------------------------

class Stufenvorgaben(BaseModel):
    lesehilfen: Lesehilfen
    lesezeit: Lesezeitregel                                  # für das Alter, ab dem die Stufe gilt
    katze: Katze
    gestaltung: Gestaltungsart | None                        # leer: kein Kinderbereich
    uhr: Uhrart


class Stufenangabe(BaseModel):
    schluessel: str
    name: str
    alter: str
    alter_von: int
    alter_bis: int | None
    faehigkeiten: list[str]
    einblick: list[Einblickart]
    darstellung: Darstellung
    lesezeichen_je_buch: int | None
    vorgaben: Stufenvorgaben


class Lesezeitvorgabe(BaseModel):
    alter_von: int
    alter_bis: int | None
    minuten: int
    an: bool


class Zugangsangaben(BaseModel):
    pin_stellen_von: int
    pin_stellen_bis: int
    bild_pin_anzahl: int
    bilder: list[str]


class Stufenansicht(BaseModel):
    """GET /api/familie/stufen: alles aus stufen.json, was die Oberfläche braucht."""

    stufen: list[Stufenangabe]
    lesezeit: list[Lesezeitvorgabe]
    rollen: dict[str, list[str]]                             # Rolle -> Fähigkeiten
    faehigkeiten: dict[str, str]                             # Fähigkeit -> was sie erlaubt
    zugang: Zugangsangaben
    katze_vorschlaege: list[str]
    katze_nennung: str


# -- Eingaben ------------------------------------------------------------------------------------------------------------------

class Wahl(BaseModel):
    profil_id: Profilkennung
    pin: Geheimnis | None = None
    bild_pin: list[Annotated[str, StringConstraints(max_length=30)]] | None = Field(None, max_length=10)


class Gewaehlt(BaseModel):
    schluessel: str
    profil: Ich


class Verlassen(BaseModel):
    eltern_pin: Geheimnis | None = None


class ProfilNeu(BaseModel):
    name: Profilname
    zeichen: Zeichen = ""
    farbe: FarbeOderLeer = ""
    rolle: Rollenname
    geburtsjahr: Geburtsjahr | None = None
    stufe: Stufenname | None = None
    einstellungen: EinstellungenEingabe = Field(default_factory=EinstellungenEingabe)


class ProfilAenderung(BaseModel):
    name: Profilname | None = None
    zeichen: Zeichen | None = None
    farbe: FarbeOderLeer | None = None
    rolle: Rollenname | None = None
    geburtsjahr: Geburtsjahr | None = None
    stufe: Stufenname | None = None
    einstellungen: EinstellungenEingabe | None = None


class PinSetzen(BaseModel):
    pin: Pin | None = None
    bild_pin: BildPin | None = None
    entfernen: bool = False

    @model_validator(mode="after")
    def _genau_eins(self) -> PinSetzen:
        if sum((self.pin is not None, self.bild_pin is not None, self.entfernen)) != 1:
            raise ValueError("genau eins von pin, bild_pin oder entfernen")
        return self


class PinVergessen(BaseModel):
    kennung: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    passwort: Annotated[str, StringConstraints(min_length=1, max_length=500)]


class GeraetBinden(BaseModel):
    profil_id: Profilkennung
    eltern_pin: Geheimnis


class GeraetLoesen(BaseModel):
    eltern_pin: Geheimnis | None = None                      # ohne: nur, wenn das gewählte Profil Profile verwalten darf


class Lesezeitmeldung(BaseModel):
    sekunden: int = Field(ge=1, le=24 * 60 * 60)             # gekappt auf den Takt aus stufen.json
    vorlesen: bool = False


class KatzeName(BaseModel):
    name: Katzenname


class Schriftwechsel(BaseModel):
    schrift_wahl: Leseschrift


class Freigabeauftrag(BaseModel):
    art: Literal["buch", "kategorie"]
    ziel_ids: list[Nr] = Field(min_length=1, max_length=10_000)


class Privat(BaseModel):
    privat: bool


class Geteilt(BaseModel):
    geteilt: bool


# -- Antworten -----------------------------------------------------------------------------------------------------------------

class Loeschfolgen(BaseModel):
    profil: ProfilEintrag
    notizen: int
    markierungen: int
    etiketten: int
    lesestaende: int                                         # Bücher mit Lesestand, Favorit, Sternen oder Lesesofa
    vorlesestellen: int
    fassungen_gelesen: int                                   # Lesestände in Übersetzungen
    freigaben: int
    private_buecher: int                                     # kein Buch wird gelöscht; sie sind danach für alle sichtbar
    lesezeit_tage: int
    geraete: int                                             # fest auf dieses Profil gestellte Geräte, werden gelöst
    stand: str                                               # mit DELETE ?stand= zurückgeben; ändert sich etwas, gilt er nicht mehr


class FreigabeKategorie(BaseModel):
    id: int
    name: str
    zeichen: str
    anzahl: int                                              # Bücher darin und in allem darunter


class Freigaben(BaseModel):
    kategorien: list[FreigabeKategorie]
    buecher: list[BookListItem]                              # nur die einzeln freigegebenen


class Buchzeile(BaseModel):
    """Ein Buch im Einblick."""

    id: int
    title: str
    author: str
    typ: str = ""
    year: int | None = None
    page_count: int = 0
    alter_von: int | None = None
    alter_bis: int | None = None
    alter_quelle: str = ""


class Einblickseintrag(BaseModel):
    buch: Buchzeile
    fortschritt: float | None = None                         # 0 bis 1; grob in Schritten, je nach Stufe
    seite: int | None = None                                 # nur mit genauem Fortschritt
    seiten: int | None = None
    fertig: bool = False                                     # fertig gelesen (familie/lesestand.py)
    zuletzt: str | None = None


class Einblicksantwort(BaseModel):
    sichtbar: list[Einblickart]
    lesezeit_heute_s: int | None = None                      # je Kind und Tag, nicht je Buch
    eintraege: list[Einblickseintrag]


# -- Ansagen (familie/ansagen.py) ----------------------------------------------------------------------------------------------

class Stimmeingabe(BaseModel):
    stimme: Stimmwahl


class Ansageeintrag(BaseModel):
    text: str
    url: str | None                                          # leer: die Stimme des Geräts spricht den Text


class Ansagen(BaseModel):
    stimme: str                                              # leer: keine Stimme gewählt, die Ansagen schweigen
    fertig: int
    gesamt: int
    laeuft: bool                                             # der Auftrag "Ansagen erstellen" spricht gerade für diese Stimme
    eintraege: dict[str, Ansageeintrag]                      # nur fertige


class Ansagestand(BaseModel):
    """Der Auftrag "Ansagen erstellen" je Stimme, wie die übrigen Läufe der App: was, wie weit, seit wann."""

    was: str = "Ansagen erstellen"
    stimme: str
    stand: Literal["wartet", "laeuft", "fertig", "fehler"]
    gesamt: int
    fertig: int
    grund: str = ""
    begonnen: str | None = None
    geaendert: str | None = None
    fertig_am: str | None = None
