"""Regeln des Katalogs (BF-69): jede Art, Groß und klein, Wortgrenzen, Deutsch und Englisch, Sicherheit und das
Zusammenfallen von Regel und KI. Alle Titel sind erfunden."""

from backend.app.katalog.einordnen import regelfunde
from backend.app.katalog.ki_fragen import KiFund
from backend.app.katalog.merkmale import Buchmerkmale, sachgruppen_aus
from backend.app.katalog.modelle import Einordnungskategorie, Regeln
from backend.app.katalog.regeln import Pruefer, Regeltreffer, sicherheit, suchtext
from backend.app.katalog.vorschlaege import zusammenfuehren


def treffer(regeln: Regeln, titel: str = "", verlag: str = "", schlagworte: tuple[str, ...] = (), sachgruppen: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    return [(t.art, t.wert) for t in Pruefer(regeln).treffer(suchtext(titel, verlag, schlagworte, sachgruppen))]


def test_sachgruppe_ist_der_anfang_der_nummer():
    r = Regeln(sachgruppen=["004", "62", "B"])
    assert treffer(r, sachgruppen=("004",)) == [("sachgruppen", "004")]
    assert treffer(r, sachgruppen=("621.3",)) == [("sachgruppen", "62")]
    assert treffer(r, sachgruppen=("b",)) == [("sachgruppen", "B")]
    assert treffer(r, sachgruppen=("0045", "160")) == [("sachgruppen", "004")]
    assert treffer(r, sachgruppen=("600", "K")) == []


def test_schlagwort_ganzes_wort_ohne_gross_und_klein():
    r = Regeln(schlagworte=["Informatik", "Science Fiction", "C++"])
    assert treffer(r, schlagworte=("angewandte INFORMATIK",)) == [("schlagworte", "Informatik")]
    assert treffer(r, schlagworte=("Wirtschaftsinformatik", "Informatiker")) == []          # kein ganzes Wort
    assert treffer(r, schlagworte=("Science-Fiction-Literatur",)) == [("schlagworte", "Science Fiction")]   # Bindestrich wie Leerzeichen
    assert treffer(r, schlagworte=("Programmieren mit C++",)) == [("schlagworte", "C++")]
    assert treffer(r, schlagworte=("Science", "Fiction")) == []                              # nicht über zwei Schlagworte hinweg


def test_schlagwort_englisch_und_deutsch():
    r = Regeln(schlagworte=["Kochen", "Cooking"])
    assert treffer(r, schlagworte=("Cooking, Italian",)) == [("schlagworte", "Cooking")]
    assert treffer(r, schlagworte=("Vegetarisch kochen",)) == [("schlagworte", "Kochen")]
    assert treffer(r, schlagworte=("Kochbuch",)) == []


def test_titelwort_am_wortanfang():
    r = Regeln(titelwoerter=["programmier", "Straße", "IT-Sicherheit"])
    assert treffer(r, titel="Programmierung für alle") == [("titelwoerter", "programmier")]
    assert treffer(r, titel="Wir programmieren") == [("titelwoerter", "programmier")]
    assert treffer(r, titel="Umprogrammiert") == []                                         # nicht mitten im Wort
    assert treffer(r, titel="DIE STRASSE DER MÜHLEN") == [("titelwoerter", "Straße")]          # ß wie ss
    assert treffer(r, titel="Grundkurs IT Sicherheit") == [("titelwoerter", "IT-Sicherheit")]


def test_verlag_enthalten():
    r = Regeln(verlage=["Musterhaus"])
    assert treffer(r, verlag="Verlag Musterhaus Nord") == [("verlage", "Musterhaus")]
    assert treffer(r, verlag="musterhausverlag") == [("verlage", "Musterhaus")]
    assert treffer(r, verlag="Andere Presse") == []


def test_regeln_doppelt_gelten_einmal():
    assert Regeln(schlagworte=["Krimi", "krimi", "KRIMI", "Thriller"]).schlagworte == ["Krimi", "Thriller"]


def test_sicherheit_je_art_und_mehrere_regeln():
    assert sicherheit([]) == 0
    assert sicherheit([Regeltreffer(art="sachgruppen", wert="004")]) == 90
    assert sicherheit([Regeltreffer(art="schlagworte", wert="x")]) == 80
    assert sicherheit([Regeltreffer(art="titelwoerter", wert="x")]) == 70
    assert sicherheit([Regeltreffer(art="verlage", wert="x")]) == 60
    assert sicherheit([Regeltreffer(art="sachgruppen", wert="004"), Regeltreffer(art="schlagworte", wert="x")]) == 93
    viele = [Regeltreffer(art="sachgruppen", wert=str(i)) for i in range(5)]
    assert sicherheit(viele) == 97                                                           # höchstens 97


def test_sachgruppen_aus_namen_der_regale():
    assert sachgruppen_aus(["Informatik", "belletristik", "Fernweh", "Kinder- und Jugendbuch"]) == ["004", "B", "K"]


def test_regel_und_ki_fallen_zusammen():
    regel = {(1, 10): [Regeltreffer(art="schlagworte", wert="Krimi")], (1, 11): [Regeltreffer(art="titelwoerter", wert="Mord")]}
    ki = {(1, 10): KiFund(schluessel="romane/krimi", sicherheit=90, satz="Ein Kommissar ermittelt."),
          (2, 12): KiFund(schluessel="romane/fantasy", sicherheit=40, satz="Es gibt Drachen.")}
    funde = {(f.buch_id, f.kategorie_id): f for f in zusammenfuehren(regel, ki)}
    assert (funde[(1, 10)].quelle, funde[(1, 10)].sicherheit, funde[(1, 10)].gruende) == ("beide", 95, ["Schlagwort Krimi", "Ein Kommissar ermittelt."])
    assert (funde[(1, 11)].quelle, funde[(1, 11)].sicherheit) == ("regel", 70)
    assert (funde[(2, 12)].quelle, funde[(2, 12)].sicherheit, funde[(2, 12)].gruende) == ("ki", 40, ["Es gibt Drachen."])
    hoch = zusammenfuehren({(1, 1): [Regeltreffer(art="sachgruppen", wert="B")] * 3},
                           {(1, 1): KiFund(schluessel="x/y", sicherheit=98, satz="Ganz sicher.")})
    assert hoch[0].sicherheit == 99                                                          # höchstens 99


def test_regeln_nur_fuer_die_art_des_werks():
    roman = Einordnungskategorie(id=1, schluessel="romane/krimi", name="Krimi", ki_beschreibung="", regeln=Regeln(titelwoerter=["Mord"]), arten=[""])
    beleg = Einordnungskategorie(id=2, schluessel="besonderes/belege", name="Belege", ki_beschreibung="", regeln=Regeln(titelwoerter=["Mord"]),
                                 arten=["dokument", "heft"])
    pruefer = [(k, Pruefer(k.regeln)) for k in (roman, beleg)]
    buecher = [Buchmerkmale(id=5, titel="Mord am Deich", typ=""), Buchmerkmale(id=6, titel="Mordsrechnung 2024", typ="dokument")]
    assert set(regelfunde(buecher, pruefer)) == {(5, 1), (6, 2)}


def test_antwort_der_ki_wird_gelesen():
    import pytest

    from backend.app.katalog.ki_fragen import alt_aus, einordnung_aus
    from backend.app.services.ki import KiFehler

    roh = {"buecher": [
        {"nummer": 1, "kategorien": [{"schluessel": "a/x", "sicherheit": 0.85, "satz": "  Passt   gut. "},
                                     {"schluessel": "a/gibtsnicht", "sicherheit": 99, "satz": "Erfunden."},
                                     {"schluessel": "a/y", "sicherheit": 140, "satz": "Sehr."}, {"schluessel": "a/z", "sicherheit": 50, "satz": "Auch."}]},
        {"nummer": 7, "kategorien": [{"schluessel": "a/x", "sicherheit": 90, "satz": "Kein solches Buch."}]},
        {"nummer": 2, "kategorien": [{"schluessel": "a/x", "sicherheit": True, "satz": "Kein Wert."}]}]}
    gelesen = einordnung_aus(roh, 2, {"a/x", "a/y", "a/z"})
    assert [(f.schluessel, f.sicherheit, f.satz) for f in gelesen[1]] == [("a/x", 85, "Passt gut."), ("a/y", 100, "Sehr.")]   # höchstens zwei
    assert gelesen[2] == [] and 7 not in gelesen
    for falsch in ("nein", {"buecher": "alle"}, {"buecher": [{"nummer": 1}]}, {"buecher": [{"nummer": 1, "kategorien": ["a/x"]}]}):
        with pytest.raises(KiFehler, match="passt nicht zur verlangten Form"):
            einordnung_aus(falsch, 1, {"a/x"})
    assert alt_aus({"regale": [{"nummer": 1, "schluessel": "", "satz": "Ein Ort."}, {"nummer": 2, "schluessel": "a/q", "satz": "?"},
                               {"nummer": 3, "schluessel": "a/x", "satz": "Passt."}]}, 3, {"a/x"}) == {1: ("", "Ein Ort."), 3: ("a/x", "Passt.")}
