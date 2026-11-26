"""Regeln des Sammlungsfinders (BF-66): Reihe und Band aus Titel und Dateiname, normierte Schlüssel, Mindestzahl. Alle Titel,
Autoren und Reihen sind erfunden."""

import pytest

from backend.app.core.config import settings
from backend.app.services.sammlungsfinder import (
    Buchzeile, autor_schluessel, erkennen, erster_autor, normiert, ohne_autor, regelfunde, reicht,
)


@pytest.mark.parametrize("text, reihe, band, titel", [
    ("Sternenfahrer 01 - Der Aufbruch", "Sternenfahrer", "1", "Der Aufbruch"),
    ("Sternenfahrer - 12 - Die Rückkehr", "Sternenfahrer", "12", "Die Rückkehr"),
    ("Sternenfahrer Band 3 - Das Tor", "Sternenfahrer", "3", "Das Tor"),
    ("Sternenfahrer Bd. 6: Neue Welten", "Sternenfahrer", "6", "Neue Welten"),
    ("Sternenfahrer 3. Das Tor", "Sternenfahrer", "3", "Das Tor"),
    ("Das Tor (Sternenfahrer 4)", "Sternenfahrer", "4", "Das Tor"),
    ("Das Tor (Sternenfahrer, Band 4)", "Sternenfahrer", "4", "Das Tor"),
    ("Sternenfahrer (Band 4)", "Sternenfahrer", "4", ""),
    ("Sternenfahrer, Band 2", "Sternenfahrer", "2", ""),
    ("Die Chroniken von Ödland 2 - Der Turm", "Die Chroniken von Ödland", "2", "Der Turm"),
])
def test_muster(text, reihe, band, titel):
    e = erkennen(text)
    assert e is not None and (e.reihe, e.band, e.titel) == (reihe, band, titel)


@pytest.mark.parametrize("text", ["Einfacher Titel", "Band 3 - Ohne Reihe", "Die 3. Generation", "Bericht 2019 - Jahreszahlen",
                                  "Werkzeug 10-Handbuch", "Kochen (2. Auflage)", ""])
def test_keine_reihe(text):
    assert erkennen(text) is None


def test_autor_normiert():
    gleich = {autor_schluessel(erster_autor(a)) for a in ("Beispiel, Erna", "Erna Beispiel", "ERNA  BEISPIEL", "Erna Beispiel; Otto Muster")}
    assert gleich == {"beispiel erna"}
    assert autor_schluessel(erster_autor("Jörg Häßler")) == autor_schluessel(erster_autor("Haessler, Joerg"))
    assert normiert("Die Chroniken von Ödland!") == normiert("die chroniken, von oedland") == "die chroniken von oedland"
    assert normiert("Sternen-Fahrer") == normiert("Sternenfahrer") == "sternenfahrer"


def test_dateiname_ohne_autor_und_endung():
    schluessel = autor_schluessel("Erna Beispiel")
    assert ohne_autor("Beispiel, Erna - Sternenfahrer 01 - Der Aufbruch.epub", schluessel) == "Sternenfahrer 01 - Der Aufbruch"
    assert ohne_autor("Sternenfahrer_02_-_Der_Turm.pdf", "") == "Sternenfahrer 02 - Der Turm"


def buecher(*angaben: tuple[str, str] | tuple[str, str, str]) -> list[Buchzeile]:
    return [Buchzeile(id=i, title=a[0], author=a[1], file_name=a[2] if len(a) > 2 else f"{i}.epub") for i, a in enumerate(angaben, 1)]


def test_gleiche_reihe_und_gleicher_autor_in_anderer_schreibweise():
    funde = regelfunde(buecher(("Sternenfahrer 01 - Der Aufbruch", "Beispiel, Erna"),
                               ("STERNENFAHRER - 2 - Der Turm", "Erna Beispiel"),
                               ("Das Tor (Sternen-Fahrer 3)", "Erna Beispiel"),
                               ("Der Aufbruch", "Otto Muster", "Muster, Otto - Sternenfahrer 1 - Der Aufbruch.pdf"),
                               ("Ganz für sich", "Erna Beispiel")), set())
    erna, otto = funde                                                       # ein anderer Autor ist eine andere Reihe
    assert erna.schluessel == ["sternenfahrer|beispiel erna"] and erna.name == "Sternenfahrer" and erna.autor == "Erna Beispiel"
    assert [f.buch_id for f in erna.funde] == [1, 2, 3] and [f.band for f in erna.funde] == ["1", "2", "3"]
    assert erna.wege() == ["Reihe und Band im Titel bei 3 Büchern", "Name der Reihe in 3 Schreibweisen", "Autor in 2 Schreibweisen"]
    assert otto.funde[0].quelle == "dateiname" and otto.funde[0].titel == "Der Aufbruch"
    assert otto.wege() == ["Reihe und Band im Dateinamen bei 1 Buch"]


def test_mindestzahl_und_verschiedene_baende(monkeypatch):
    zwei, drei, gleich = regelfunde(buecher(("Mondgarten 1 - Saat", "Erna Beispiel"), ("Mondgarten 2 - Ernte", "Erna Beispiel"),
                                            ("Sternenfahrer 1 - A", "Otto Muster"), ("Sternenfahrer 2 - B", "Otto Muster"),
                                            ("Sternenfahrer 3 - C", "Otto Muster"),
                                            ("Werkzeug 3 - Erste Schritte", "Berta Probe"), ("Werkzeug 3 - Rezepte", "Berta Probe"),
                                            ("Werkzeug 3 - Tipps", "Berta Probe")), set())
    assert (reicht(zwei), reicht(drei), reicht(gleich)) == (False, True, False)          # drei Bücher, aber alle Band 3
    monkeypatch.setattr(settings, "sammlung_vorschlag_ab", 2)
    assert reicht(zwei)


def test_angelegte_und_verworfene_schluessel_bleiben_draussen():
    alle = buecher(("Mondgarten 1 - Saat", "Erna Beispiel"), ("Sternenfahrer 1 - A", "Otto Muster"))
    assert [k.name for k in regelfunde(alle, {"mondgarten|beispiel erna"})] == ["Sternenfahrer"]
