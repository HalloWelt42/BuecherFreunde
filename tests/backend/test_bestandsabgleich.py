"""Regeln des Abgleichs mit dem Bestand (BF-119), ohne Datenbank. Bücher und Personen sind erfunden."""

import pytest

from backend.app.bestandsabgleich.dienst import suchwoerter
from backend.app.bestandsabgleich.modelle import Angebot, Fundart
from backend.app.bestandsabgleich.regeln import Bestandsbuch, auflage, einstufen, freitext, isbn13, ohne_klammern

WERFT = Bestandsbuch(id=1, title="Die Werft am Fluss", author="Okke Harms", autoren=("Okke Harms",), year=2019,
                     isbn13=frozenset({"9783946417705"}), formate=("epub",))


@pytest.mark.parametrize("roh, sauber", [
    ("Die Werft am Fluss (German Edition)", "Die Werft am Fluss"),
    ("Die Werft am Fluss [Taschenbuch]", "Die Werft am Fluss"),
    ("Die Inselchronik (Band 3)", "Die Inselchronik (Band 3)"),          # eine Zahl in Klammern nennt den Band
])
def test_klammern_ohne_zahl_zaehlen_nicht(roh, sauber):
    assert ohne_klammern(roh) == sauber


@pytest.mark.parametrize("text, nummer", [("2., erweiterte Auflage", 2), ("3. überarbeitete und erweiterte Auflage", 3), ("4. Aufl.", 4),
                                          ("2nd edition", 2), ("3rd revised edition", 3), ("Band 2", None), ("Roman", None)])
def test_auflage(text, nummer):
    assert auflage(text) == nummer


def test_isbn_in_allen_schreibweisen():
    assert isbn13(["978-3-946417-70-5", "3946417701", "keine"]) == {"9783946417705"}
    assert isbn13("ISBN 978-3-946417-70-5 und 978-3-946417-71-2") == {"9783946417705", "9783946417712"}


def test_vorhanden_ahnlich_und_kein_treffer():
    e = einstufen(Angebot(nr=0, titel="Die Werft am Fluss: Roman", autoren=["Harms, Okke"]), WERFT, 0.8)
    assert (e.art, e.grund) == (Fundart.VORHANDEN, "Titel und Autor passen")
    e = einstufen(Angebot(nr=0, titel="Die Werft am Fluss. 2. Auflage", autoren=["Okke Harms"], jahr=2024), WERFT, 0.8)
    assert (e.art, e.grund) == (Fundart.AEHNLICH, "andere Auflage: 2024 statt 2019")
    e = einstufen(Angebot(nr=0, titel="Die Werft am Fluss"), WERFT, 0.8)
    assert (e.art, e.grund) == (Fundart.AEHNLICH, "Titel gleich, ohne Autor")
    e = einstufen(Angebot(nr=0, titel="Die Werft am Fluss", autoren=["Zora Fremd"]), WERFT, 0.8)
    assert (e.art, e.grund) == (Fundart.AEHNLICH, "gleicher Titel, anderer Autor")
    assert einstufen(Angebot(nr=0, titel="Werften der Elbe", autoren=["Okke Harms"]), WERFT, 0.8) is None
    e = einstufen(Angebot(nr=0, titel="Ganz anders", isbn=["3-946417-70-1"]), WERFT, 0.8)
    assert (e.art, e.grund) == (Fundart.VORHANDEN, "gleiche ISBN")


def test_die_grenze_fuer_aehnlich_ist_einstellbar():
    angebot = Angebot(nr=0, titel="Die Werft am alten Fluss")
    assert einstufen(angebot, WERFT, 0.7) is not None
    assert einstufen(angebot, WERFT, 0.95) is None


def test_freitext_nennt_titel_oder_autor():
    assert freitext("Okke Harms", WERFT, 0.8).grund == "Autor passt"
    assert freitext("Harms Okke", WERFT, 0.8).grund == "Autor passt"
    assert freitext("Werft am Fluss", WERFT, 0.8).art is Fundart.VORHANDEN
    assert freitext("Harms", WERFT, 0.8) is None                         # ein Wort allein ist kein Name


def test_suchwoerter_ohne_fuellwoerter_die_laengsten_zuerst():
    assert suchwoerter("Die Werft am Fluss: Roman (German Edition)") == ["werft", "fluss"]
    assert suchwoerter("Es") == ["es"]
