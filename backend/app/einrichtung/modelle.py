"""Formen der Ersteinrichtung (BF-82): was die Schnittstelle zeigt und annimmt. Kein Modell, das hinausgeht, trägt einen
Schlüssel; der Einmalcode des Umzugs steht nur in der Antwort auf "Umzug vorbereiten"."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

from backend.app.core.schluessel import Schluesselstand

Modus = Literal["neu", "wartung", "aus"]
Ausgangslagename = Literal["neu", "sicherung", "kellerwolke", "umzug"]
Schrittstand = Literal["offen", "erledigt", "uebersprungen", "entfaellt"]
Anschlussart = Literal["kellerwolke", "leitstelle", "vertonung", "nachschlag"]
Auftragsart = Literal["pruefung", "neuaufbau", "kopieren"]
Auftragsstandart = Literal["", "wartet", "laeuft", "pause", "fertig", "fehler"]


def _adresse(wert: str) -> str:
    wert = wert.strip().rstrip("/")
    if wert and not re.match(r"^https?://[^\s/?#]+(/[^\s?#]*)?$", wert):
        raise ValueError("eine Adresse mit http:// oder https:// und Rechner")
    return wert


Dienstadresse = Annotated[str, StringConstraints(max_length=500), AfterValidator(_adresse)]
Schluesselwert = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=4096)]
Einmalcode = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=4, max_length=40)]
Ordnerpfad = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


# -- Zustand und Schritte -------------------------------------------------------------------------------------------------

class Schritt(BaseModel):
    schluessel: str
    name: str
    pflicht: bool
    stand: Schrittstand
    text: str = ""                    # was eingerichtet ist oder warum übersprungen, für den Abschluss
    weiter: bool = True               # ob "Weiter" geht; sonst steht der Grund da
    grund: str = ""


class Ausgangslage(BaseModel):
    schluessel: Ausgangslagename
    name: str
    beschreibung: str
    schritte: list[str]


class Einrichtung(BaseModel):
    """`zeigen`: die Oberfläche öffnet den Assistenten (neue Installation, noch nicht abgeschlossen, oder wieder geöffnet)."""

    modus: Modus
    zeigen: bool
    ausgangslage: Ausgangslagename | None = None
    schritt: str | None = None        # der erste offene Schritt
    schritte: list[Schritt] = Field(default_factory=list)
    ausgangslagen: list[Ausgangslage] = Field(default_factory=list)
    konto: bool = False               # es gibt ein Konto, mit dem man sich anmelden kann
    anmeldung: Literal["eigen", "kellerwolke"] = "eigen"
    aenderungen: int = 0              # Wartung: so viele warten auf die Bestätigung
    begonnen_am: str | None = None
    abgeschlossen_am: str | None = None


class AusgangslageWahl(BaseModel):
    ausgangslage: Ausgangslagename


class SchrittAktion(BaseModel):
    aktion: Literal["erledigt", "ueberspringen"]


# -- Orte -----------------------------------------------------------------------------------------------------------------

class Ortstand(BaseModel):
    kennung: str
    name: str
    pfad: str
    belegt: int = 0
    frei: int = 0
    stand: Literal["gut", "warn", "schlecht"]
    dauerhaft: bool
    marker: bool
    text: str = ""


class Orte(BaseModel):
    orte: list[Ortstand]
    weiter: bool
    grund: str = ""


# -- Anschlüsse -----------------------------------------------------------------------------------------------------------

class Verbindungspruefung(BaseModel):
    ok: bool
    text: str = ""                    # etwa "BücherFreunde, Konto anna", "KI mit 3 Modellen" oder "Stimmen: 9 eingebaut, 2 fremd"
    grund: str = ""                   # warum nicht
    am: str | None = None
    app: str = ""                     # nur Kellerwolke: der Name der App und das Konto, dem der App-Zugang gehört
    konto: str = ""


class Anschluss(BaseModel):
    art: Anschlussart
    name: str
    adresse: str
    herkunft: Literal["app", "einrichtung", ""]       # woher die Adresse kommt; leer: keine
    schluessel: Schluesselstand | None                # None: dieser Anschluss hat keinen (Nachschlag)
    hinweis: str = ""
    pruefung: Verbindungspruefung | None = None                  # die letzte Prüfung seit dem Start


class AnschlussEingabe(BaseModel):
    adresse: Dienstadresse
    schluessel: Schluesselwert | None = None          # nur neu oder zum Ersetzen; fehlt er, gilt der eingetragene


class AnschlussPruefen(BaseModel):
    adresse: Dienstadresse | None = None              # ohne: die eingetragene
    schluessel: Schluesselwert | None = None


class Kontoverbindung(BaseModel):
    """Schritt Konto mit der Kellerwolke: Adresse und App-Zugang kommen gleich hier."""

    adresse: Dienstadresse = Field(min_length=1)
    schluessel: Schluesselwert


class Kontostand(BaseModel):
    anmeldung: Literal["eigen", "kellerwolke"]
    app: str = ""
    besitzer: str = ""


# -- Katalog, Familie -----------------------------------------------------------------------------------------------------

class KatalogWahl(BaseModel):
    wahl: Literal["standard", "leer", "bestand"]


# -- Wartung: Änderungen erst nach Bestätigung ----------------------------------------------------------------------------

class Aenderung(BaseModel):
    id: str
    schritt: str
    art: Literal["anschluss", "katalog", "profil", "stimme"]
    was: str                          # ein Satz, etwa "Leitstelle: neue Adresse und neuer Schlüssel"
    alt: str = ""
    neu: str = ""


class Aenderungen(BaseModel):
    aenderungen: list[Aenderung]
    unveraendert: list[str]           # Schritte ohne Änderung
    stand: str


class Uebernehmen(BaseModel):
    stand: str
    ids: list[str] = Field(default_factory=list, max_length=200)


class Uebernommen(BaseModel):
    uebernommen: list[Aenderung]
    verworfen: int


class Vorgemerkt(BaseModel):
    """Antwort eines Schritts: angewandt (neue Installation) oder vorgemerkt (Wartung)."""

    angewandt: bool
    aenderung: Aenderung | None = None


# -- Aufträge -------------------------------------------------------------------------------------------------------------

class Teil(BaseModel):
    schluessel: str
    name: str
    gesamt: int = 0
    fertig: int = 0


class Auftragsstand(BaseModel):
    art: str
    was: str
    stand: Auftragsstandart
    gesamt: int = 0
    fertig: int = 0
    teile: list[Teil] = Field(default_factory=list)
    aktuell: str = ""
    grund: str = ""
    begonnen: str | None = None
    geaendert: str | None = None
    fertig_am: str | None = None


# -- Sicherungen und Wiederherstellen -------------------------------------------------------------------------------------

Sicherungsquelle = Literal["datei", "geraet", "kellerwolke"]


class Sicherung(BaseModel):
    quelle: Sicherungsquelle
    kennung: str                      # geraet: der Name, kellerwolke: der Knoten
    name: str
    groesse: int | None = None
    angelegt_am: str | None = None
    buecher: int | None = None
    profile: int | None = None
    version: str = ""


class Sicherungsliste(BaseModel):
    quelle: Sicherungsquelle
    bereit: bool
    grund: str = ""
    sicherungen: list[Sicherung] = Field(default_factory=list)


class Wiederherstellen(BaseModel):
    quelle: Literal["datei", "geraet", "kellerwolke"]
    kennung: Annotated[str, StringConstraints(min_length=1, max_length=300)]     # datei: die Kennung des Hochladens
    stand: str = ""                   # aus den Folgen


class Wiederherstellfolgen(BaseModel):
    sicherung: Sicherung
    ersetzt: list[str]                # Sätze, was ersetzt wird; leer: auf dem Gerät ist noch nichts
    vorher_sichern: bool              # vorher entsteht eine Sicherung des jetzigen Stands
    stand: str


class Wiederhergestellt(BaseModel):
    name: str
    buecher: int
    profile: int
    version: str
    vorher: str = ""                  # die Sicherung des Stands davor (nur beim Ersetzen)


class Wiederherstellstand(BaseModel):
    auftrag: Auftragsstand
    ergebnis: Wiederhergestellt | None


class Befund(BaseModel):
    buch_id: int
    titel: str
    autor: str
    ergebnis: Literal["erreichbar", "wiedergefunden", "fehlt"]
    ort: str = ""                     # kellerwolke, geraet
    pfad: str = ""
    text: str = ""


class Pruefbericht(BaseModel):
    auftrag: Auftragsstand
    erreichbar: int
    wiedergefunden: int
    fehlt: int
    texte: int                        # Bücher, deren Volltext oder Umschlag aus dem Auszug zurückkam
    eintraege: list[Befund]           # wiedergefunden und fehlend; erreichbare stehen nur in der Zahl


class PruefungStarten(BaseModel):
    pruefsummen: bool = False         # auch Originale auf dem Gerät ganz lesen und ihre Prüfsumme vergleichen


# -- Neuaufbau aus der Kellerwolke ----------------------------------------------------------------------------------------

class OrdnerWahl(BaseModel):
    pfad: Ordnerpfad = "Bücher"       # unter dem Ordner der App in der Kellerwolke


class Ordnerpruefung(BaseModel):
    pfad: str
    buecher: int
    mit_auszug: int
    ohne_auszug: int
    mit_persoenlichem: int            # mit Begleiter persoenlich
    schon_da: int
    groesse: int
    profile: list[str]                # Namen aus der Datei der Profile
    profile_datei: bool


class Ohneauszug(BaseModel):
    buch_id: int | None
    name: str
    pfad: str


class Neuaufbaubericht(BaseModel):
    auftrag: Auftragsstand
    buecher: int
    mit_auszug: int
    ohne_auszug: list[Ohneauszug]
    fehler: list[Ohneauszug]
    profile: int


# -- Umzug ----------------------------------------------------------------------------------------------------------------

class UmzugVorbereitet(BaseModel):
    code: str                         # nur hier, ein einziges Mal
    gilt_bis: str
    sicherung: str
    groesse: int


class Umzugsstand(BaseModel):
    vorbereitet: bool
    gilt_bis: str | None = None
    versuche_frei: int = 0
    sicherung: str = ""
    eingeloest_am: str | None = None
    sitzung_bis: str | None = None
    gesperrt: bool = False


class UmzugVerbinden(BaseModel):
    adresse: Dienstadresse = Field(min_length=1)
    code: Einmalcode


class Einloesen(BaseModel):
    """Was das neue Gerät dem alten schickt."""

    code: Einmalcode


class Originalort(BaseModel):
    ort: Literal["kellerwolke", "geraet"]
    anzahl: int
    groesse: int


class Umzugspaket(BaseModel):
    """Was das alte Gerät nach dem Code schickt; nur über die gesicherte Verbindung, nie an die Oberfläche."""

    sitzung: str
    sitzung_bis: str
    sicherung: str
    groesse: int
    sha256: str
    schluessel: dict[str, str]
    anschluesse: dict[str, str]
    originale: Originalort


class Umzugsergebnis(BaseModel):
    sicherung: str
    einstellungen: list[str]          # welche Anschlüsse das alte Gerät nennt
    schluessel: list[str]             # welche Schlüssel in die Schlüsseldatei kamen (Namen, nie Werte)
    originale: Originalort
    einspielen: Auftragsstand         # der Auftrag "Sicherung einspielen"; danach mit Kellerwolke die Prüfung der Originale


class OriginaleWahl(BaseModel):
    weg: Literal["kopieren", "ort"]


# -- Einstellungen der Kellerwolke ----------------------------------------------------------------------------------------

class Kellerwolkeneinstellungen(BaseModel):
    persoenlich: bool                 # Persönliches je Buch und Profil als Begleiter in der Kellerwolke, dazu die Datei der Profile
    sicherungen_ablegen: bool


class KellerwolkeneinstellungenEingabe(BaseModel):
    persoenlich: bool | None = None   # Einschalten und Ausschalten mit Entfernen nur mit `stand` aus den Folgen
    sicherungen_ablegen: bool | None = None
    entfernen: bool = False           # beim Ausschalten: die Begleiter in den Papierkorb der Kellerwolke
    stand: str = ""


class ProfilZahl(BaseModel):
    id: str
    name: str
    buecher: int


class Persoenlichfolgen(BaseModel):
    """Was Einschalten in die Kellerwolke schreibt und Ausschalten mit Entfernen dort in den Papierkorb legt."""

    buecher: int                      # Bücher in der Kellerwolke mit Persönlichem: so viele Begleiter
    profile_datei: str                # die Datei der Profile
    profile: list[ProfilZahl]
    lesestaende: int
    vorlesestellen: int
    notizen: int
    markierungen: int
    etiketten: int
    private: int
    freigaben: int
    stand: str
