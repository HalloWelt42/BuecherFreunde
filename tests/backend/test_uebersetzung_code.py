"""Code in einfachen Absätzen und Code in Backticks (BF-71): Zeilen wie Code, Prosa mit Codewörtern, Zäune aus Markdown mit
und ohne Ende, Folgen von Codezeilen, Festbreitenschrift aus dem CSS. Alle Texte sind selbst geschrieben."""

import pytest

from backend.app.uebersetzung.codeabsaetze import STARK, Absatz, erkennen, festbreit_klassen, staerke
from backend.app.uebersetzung.modelle import pruefsumme
from backend.app.uebersetzung.setzen import Satz, Uebersetzt, setzen
from backend.app.uebersetzung.zerlegen_epub import zerlegen
from tests.uebersetzung_probe import dateien, probe_epub

KAPITEL1 = "OEBPS/text/kapitel 1.xhtml"
NBSP = "\u00a0"


# -- Zeilen -------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("zeile", [
    "pip install gardenkit", "for bed in beds:", "if moisture < 30:", "elif moisture >= 30 and moisture < 60:", "else:",
    'print("The bed is dry.")', 'plants = ["tomato", "basil", "mint"]', "pump.start(speed=3)", "water_level += 5",
    "def water(bed):", "from garden import Pump", "import garden as g", "venv\\Scripts\\activate", "source venv/bin/activate",
    "python3 -m venv venv", 'git commit -m "Water the beds"', "SELECT name FROM beds WHERE dry = 1;", "const total = beds.length;",
    '"name": "Tomato",', "if bed is not None:", "class Pump(Machine):", "$ gardenkit run", "cd my_garden",
    f"pump.stop(){NBSP}{NBSP}{NBSP}Stop the pump",                     # Kommentar, dem das Zeichen fehlt
])
def test_zeilen_wie_code(zeile):
    assert staerke(zeile) == STARK


@pytest.mark.parametrize("zeile", [
    "Make sure the pump is switched off before you start.", "make sure the pump is switched off",
    "git is a tool that keeps track of your changes", "cd into the garden folder and run the script",
    "If you want to water the beds, call the pump first:", "python is a friendly language", "Select a bed",
    "Variables:", "Data Types:", "For example:", "Represents whole numbers (e.g., 42).", "Here are the main parts of the kit:",
    "for more details on this topic, see the next chapter:", "export the readings to a file", "Note: Version 3.12 is required.",
    "Use print() to show the water level", "Water early, water deep.",
])
def test_prosa_mit_codewoertern_ist_kein_starker_code(zeile):
    assert staerke(zeile) < STARK


def test_schwache_merkmale_nur_zwischen_code():
    """return und ein Aufruf mitten im Satz sind schwach: zwischen zwei Codezeilen Code, allein nicht."""
    def code(*texte):
        return erkennen([Absatz(text=t, kandidat=True) for t in texte])
    assert code("if dry:", "return bed", "print(bed)") == {0, 1, 2}
    assert code("Some text here about beds.", "return bed", "More text about the pump.") == set()
    assert code("for bed in beds:", "Use print() to show the water level") == {0}
    assert code("Heading", "return bed") == set()
    assert erkennen([Absatz("if dry:", True), Absatz("return bed", False), Absatz("print(bed)", True)]) == {0, 2}


# -- Zäune --------------------------------------------------------------------------------------------------------------------

def zaeune(*texte: str) -> set[int]:
    return erkennen([Absatz(text=t, kandidat=True) for t in texte])


def test_zaun_mit_ende_umschliesst_auch_kommentare_ohne_zeichen():
    assert zaeune("Write this loop.", "```python", "Initialize the pump", "pump = Pump()", "```",
                  "In the above code, the pump starts once.") == {1, 2, 3, 4}


def test_zaun_mit_sprache_schliesst_nie_den_vorigen_block():
    """Fehlt das Ende, beginnt der nächste Zaun mit Sprache einen neuen Block; Prosa dazwischen bleibt Text."""
    assert zaeune("```python", "pump.start()", "In the above code, the pump starts.", "2. Water the Beds:",
                  "Then the beds get their water in turn.", "```python", "for bed in beds:") == {0, 1, 5, 6}


def test_zaun_ohne_ende_reicht_bis_zur_prosa_oder_zwischenzeile():
    assert zaeune("```shell", "gardenkit run --dry", "gardenkit check", "2. Check the Beds:", "pump.start()") == {0, 1, 2, 4}
    assert zaeune("```", "Water early, water deep.") == {0}


def test_zwischen_zaeunen_muss_ueberwiegend_code_stehen():
    """Ein verirrter Zaun macht keine Prosa zu Code: dann gelten nur die Zäune selbst."""
    assert zaeune("```", "The beds are wet today.", "The pump rests in the shed.", "Nothing else to do here.", "```") == {0, 4}


# -- Festbreitenschrift -------------------------------------------------------------------------------------------------------

def test_klassen_mit_festbreitenschrift_aus_dem_css():
    css = """/* Kommentar .falsch { font-family: monospace } */
    p.listing, .mono { font-family: "Courier New", monospace; margin: 0 }
    @media screen { .klein code, .befehl { font-family: Menlo } }
    .text { font-family: Georgia, serif }"""
    assert festbreit_klassen(css) == {"listing", "mono", "klein", "befehl"}


def test_festbreitenschrift_als_grundschrift_ist_kein_zeichen_fuer_code():
    zwischen = [Absatz("pump.start()", True, True), Absatz("water the tomatoes", True, True), Absatz("pump.stop()", True, True)]
    assert erkennen(zwischen) == {0, 1, 2}
    roman = [Absatz(f"Line {i} of the letter", True, True) for i in range(9)] + [Absatz("pump.start()", True, True)]
    assert erkennen(roman) == {9}


# -- Im Buch ------------------------------------------------------------------------------------------------------------------

KAPITEL = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">
<head><title>Watering by Script</title><link rel="stylesheet" type="text/css" href="../stil.css"/></head>
<body>
  <h1>Watering by Script</h1>
  <p>Install the garden kit first:</p>
  <p>pip install gardenkit</p>
  <p>Then write a small loop. It waters every bed once.</p>
  <p>```python</p>
  <p>import gardenkit</p>
  <p>Initialize the pump</p>
  <p>pump = gardenkit.Pump()</p>
  <p>for bed in beds:</p>
  <p>pump.water(bed)</p>
  <p>```</p>
  <p>In the above code, the loop calls <code>water</code> for each bed.</p>
  <p>Each value is checked with `moisture &lt; 30` before the `pump` starts.</p>
  <p>```shell</p>
  <p>gardenkit run --dry</p>
  <p>2. Check the Beds:</p>
  <p>Look at the beds every morning and note how wet the soil is.</p>
  <p class="mono">Water deep, water early, and never at noon.</p>
  <p class="mono">pump.start()</p>
  <p class="mono">water the tomatoes</p>
  <p class="mono">pump.stop()</p>
  <p>Edit <span class="mono">gardenkit.cfg</span> and the screen shows <span class="mono">ALL BEDS WET</span> in green.</p>
  <p style="font-family: Consolas, monospace">gardenkit log --tail</p>
</body>
</html>
"""
STIL = ".mono { font-family: 'Courier New', monospace; }\n"


def test_code_im_buch_wird_kein_block_und_bleibt_wie_er_ist():
    original = probe_epub({KAPITEL1: KAPITEL, "OEBPS/stil.css": STIL})
    z = zerlegen(original, frozenset())
    vorlagen = [b.vorlage for b in z.bloecke() if b.kapitel == 2]
    assert vorlagen == [
        "Watering by Script", "Install the garden kit first:", "Then write a small loop. It waters every bed once.",
        "In the above code, the loop calls <x1/> for each bed.",
        "Each value is checked with <x1/> before the <x2/> starts.",              # Backticks als Platzhalter
        "2. Check the Beds:", "Look at the beds every morning and note how wet the soil is.",
        "Water deep, water early, and never at noon.",                             # Prosa in Festbreitenschrift bleibt Text
        "Edit <x1/> and the screen shows <t2>ALL BEDS WET</t2> in green.",        # ein Wort in Festbreite ist Code, ein Satz nicht
    ]
    # gesetzt mit einer Übersetzung je Block: Code, Zäune und Backticks Zeichen für Zeichen wie im Original
    deutsch = {b.kennung: Uebersetzt(pruefsumme=pruefsumme(b.vorlage), text=b.vorlage) for b in z.bloecke()}
    deutsch["2.5"] = Uebersetzt(pruefsumme=pruefsumme(vorlagen[4]), text="Jeder Wert wird mit <x1/> geprüft, bevor <x2/> anläuft.")
    k1 = dateien(setzen(original, z, Satz(deutsch=deutsch)))[KAPITEL1].decode()
    for stueck in ("<p>pip install gardenkit</p>", "<p>```python</p>", "<p>Initialize the pump</p>", "<p>```</p>",
                   "<p>gardenkit run --dry</p>", '<p class="mono">water the tomatoes</p>',
                   '<p style="font-family: Consolas, monospace">gardenkit log --tail</p>'):
        assert stueck in k1
    assert "<p>Jeder Wert wird mit `moisture &lt; 30` geprüft, bevor `pump` anläuft.</p>" in k1
