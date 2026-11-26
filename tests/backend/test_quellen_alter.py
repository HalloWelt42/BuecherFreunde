"""Altersangaben aus den Quellen (BF-78): aus der Zielgruppe im Katalog (MARC 21, Feld 521 und 008/22), mit Herkunft am Buch,
überschreibbar. Die Sätze sind erfunden."""

from __future__ import annotations

import pytest

from backend.app.quellen import alter, marc
from backend.app.quellen.auskunft import zusammenfuehren
from backend.app.quellen.modelle import Angaben, Buchfrage


@pytest.mark.parametrize(("text", "von", "bis"), [
    ("ab 8 J.", 8, None), ("Ab 4 Jahren", 4, None), ("Lesealter 6 - 8 J.", 6, 8), ("Interessenalter: 10-12 Jahre", 10, 12),
    ("ages 9 to 12", 9, 12), ("12+", 12, None), ("bis 6 Jahre", None, 6), ("Kinder von 5 bis 7 Jahren", 5, 7),
])
def test_alter_aus_der_zielgruppe(text, von, bis):
    assert alter.aus_text(text) == alter.Alter(von=von, bis=bis)


@pytest.mark.parametrize("text", ["Band 3-5", "Für Erwachsene", "", "Lesealter 12 - 8 J.", "ab 140 Jahren"])
def test_kein_alter_wo_keins_steht(text):
    assert alter.aus_text(text) is None


def test_kennbuchstabe_der_zielgruppe():
    assert alter.aus_zielgruppe("b") == alter.Alter(von=6, bis=8)
    assert alter.aus_zielgruppe("j") is None and alter.aus_zielgruppe("|") is None


SATZ = """<record xmlns="http://www.loc.gov/MARC21/slim"><leader>00000nam a2200000 c 4500</leader>
<controlfield tag="008">230101s2023    gw ||||| |||| 00||||ger  </controlfield>
<datafield tag="245" ind1="1" ind2="0"><subfield code="a">Die Probe im Wald</subfield></datafield>
<datafield tag="521" ind1="8" ind2=" "><subfield code="a">ab 6 J.</subfield></datafield></record>"""


def test_marc_liest_das_alter():
    s = marc.saetze(f'<s:searchRetrieveResponse xmlns:s="http://www.loc.gov/zing/srw/"><s:records><s:record><s:recordData>{SATZ}'
                    "</s:recordData></s:record></s:records></s:searchRetrieveResponse>".encode())[0]
    assert marc.angaben(s, "dnb").alter == alter.Alter(von=6, bis=None)


def test_zusammengefuehrt_mit_herkunft():
    funde = [Angaben(quelle="dnb", fund="isbn", titel="Die Probe", alter=alter.Alter(von=6), herkunft={"titel": "dnb", "alter": "dnb"}),
             Angaben(quelle="google_books", fund="isbn", titel="Die Probe")]
    a = zusammenfuehren(funde, Buchfrage(isbn="9783000000000"))
    assert a.alter == alter.Alter(von=6) and a.herkunft["alter"] == "dnb"
