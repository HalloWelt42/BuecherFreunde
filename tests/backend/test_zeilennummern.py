"""BF-104: Eine Zahl am Anfang einer Codezeile ist ohne Ausnahme eine Zählung des Buchs und fällt weg, bevor der Code irgendwo
eingesetzt wird; die Einrückung danach bleibt. Gilt beim Erkennen und beim Lesen schon gespeicherter Codestellen."""

from backend.app.codestellen.modelle import Codestelle, Teil, ohne_zeilennummern, pruefsumme


def test_zahl_am_zeilenanfang_faellt_weg_die_einrueckung_bleibt():
    buch = " 9 for i in range(3):\n10     wert = i * 2\n11.    print(wert)\n12: ende = True\n13) x = 1\n"
    assert ohne_zeilennummern(buch) == "for i in range(3):\n    wert = i * 2\n   print(wert)\nende = True\nx = 1\n"


def test_zeilen_ohne_nummer_bleiben_und_eine_zahl_allein_wird_leer():
    assert ohne_zeilennummern('print("Hallo")\n    zahl = 42\n7\n') == 'print("Hallo")\n    zahl = 42\n\n'


def test_auch_gespeicherte_stellen_kommen_ohne_zaehlung_die_kennung_bleibt():
    alt = '1 print("Hallo Welt!")\n2 zahl = 42'
    gespeichert = {"kennung": "s3-120-abcdef12", "teile": [Teil(seite=3).model_dump()], "code": alt, "pruefsumme": pruefsumme(alt)}
    c = Codestelle.model_validate(gespeichert)
    assert c.code == 'print("Hallo Welt!")\nzahl = 42'
    assert c.kennung == "s3-120-abcdef12" and c.pruefsumme == pruefsumme(c.code)
