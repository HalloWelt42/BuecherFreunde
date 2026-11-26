"""Die zehn festen Prüfungen beim Übersetzen (BF-71): je Prüfung Gut- und Schlechtfälle, dazu ihre Bausteine (Zahlen,
Zahlwörter, Sätze, Sprache, stehengebliebenes Englisch, Zeichen, Anrede, Zeichen für das Modell) und die Reparatur der Marken
vor den Prüfungen. Alle Texte sind erfunden."""

import pytest

from backend.app.uebersetzung import zahlen
from backend.app.uebersetzung.marken import aus_modell, fuer_modell, gesichert
from backend.app.uebersetzung.modelle import Begriff, Laengengrenzen, Reparatur
from backend.app.uebersetzung.pruefen import (
    bezeichner, englisch_aus_dem_original, pruefe_anrede, pruefe_begriffe, pruefe_bezeichner, pruefe_einheiten, pruefe_laenge, pruefe_marken,
    pruefe_sprache, pruefe_vollstaendigkeit, pruefe_zahlen, pruefe_zeichen, pruefen, reparieren, stehengeblieben, unuebersetzt,
)
from backend.app.uebersetzung.sprache import buch_ist_englisch, englischer_satz, ist_englisch, saetze
from backend.app.uebersetzung.zeichen import gerade

GRENZEN = Laengengrenzen()
BEGRIFFE = [Begriff(englisch="thread", bleibt=True), Begriff(englisch="event loop", bleibt=True),
            Begriff(englisch="return value", deutsch="Rückgabewert"), Begriff(englisch="feet", deutsch="Fuß", art="einheit"),
            Begriff(englisch="mile", deutsch="Meile", art="einheit"), Begriff(englisch="miles", deutsch="Meile", art="einheit")]


def arten(befunde) -> list[str]:
    return [b.art for b in befunde]


# -- Marken -------------------------------------------------------------------------------------------------------------------

VORLAGE = "Check the <t1>filter <t2>twice</t2></t1> and call <x3/> before <t4>noon</t4>."


@pytest.mark.parametrize("deutsch", [
    "Prüfe den <t1>Filter <t2>zweimal</t2></t1> und rufe <x3/> vor <t4>Mittag</t4> auf.",
    "Vor <t4>Mittag</t4> rufe <x3/> auf und prüfe den <t1>Filter <t2>zweimal</t2></t1>.",     # Stellung darf sich ändern
    "Prüfe den <t1><t2>zweimal</t2> den Filter</t1>, rufe <x3/> vor <t4>Mittag</t4> auf.",
])
def test_marken_gut(deutsch):
    assert pruefe_marken(VORLAGE, deutsch) == []


@pytest.mark.parametrize("deutsch, grund, stelle", [
    ("Prüfe den <t1>Filter</t1> <t2>zweimal</t2> und rufe <x3/> vor <t4>Mittag</t4> auf.", "anders geschachtelt", "<t2>"),
    ("Prüfe den <t1>Filter <t2>zweimal</t2></t1> und rufe vor <t4>Mittag</t4> auf.", "Marke 3 fehlt", "<x3/>"),
    ("Prüfe den <t1>Filter <t2>zweimal</t2></t1> und <x3/> <x3/> vor <t4>Mittag</t4>.", "doppelt", "<x3/>"),
    ("Prüfe den <t1>Filter <t2>zweimal</t2></t1> und <x3/> vor <t4>Mittag</t4> <x9/>.", "gibt es im Original nicht", "<x9/>"),
    ("Prüfe den <t1>Filter <t2>zweimal</t1></t2> und <x3/> vor <t4>Mittag</t4>.", "falsch geschlossen", "</t1>"),
    ("Prüfe den <t1>Filter <t2>zweimal</t2></t1> und <x3/> vor <t4>Mittag.", "nicht geschlossen", "<t4>"),
    ("Prüfe den <t1>Filter <x2/></t1> und <x3/> vor <t4>Mittag</t4>.", "falsche Art", "<x2/>"),
    ("Prüfe den <b>Filter</b> <t1><t2>zweimal</t2></t1> und <x3/> vor <t4>Mittag</t4>.", "Fremde Auszeichnung", "<b>"),
])
def test_marken_schlecht(deutsch, grund, stelle):
    [befund] = pruefe_marken(VORLAGE, deutsch)
    assert befund.art == "marken" and grund in befund.text and befund.stelle == stelle


def test_ein_fehlender_platzhalter_nennt_seine_stelle_im_original():
    [befund] = pruefe_marken("Tools such as <x1/> and more. Also, <x2/>you can add your own.", "Werkzeuge wie <x1/> und mehr. Du kannst eigene ergänzen.")
    assert befund.text == 'Die Marke 2 fehlt; im Original steht sie so: "and more. Also, <x2/>you can add"' and befund.stelle == "<x2/>"


DOPPELT = "Doppelt: nur die Stelle, die zum Original passt, behält die Marke; der Text bleibt"


@pytest.mark.parametrize("vorlage, deutsch, repariert, stellen", [
    # doppelt: dasselbe Wort wie im Original behält die Marke, das andere Vorkommen nur den Text
    ("<t1>Leaf mode</t1> is new. Then leaf mode starts.", "<t1>Leaf mode</t1> ist neu. Dann startet <t1>Leaf mode</t1>.",
     "<t1>Leaf mode</t1> ist neu. Dann startet Leaf mode.", ["Leaf mode"]),
    ("Then <t1>leaf mode</t1> starts.", "<t1>Blattmodus</t1> ist neu. Dann startet <t1>leaf mode</t1>.",       # das passende, nicht das erste
     "Blattmodus ist neu. Dann startet <t1>leaf mode</t1>.", ["Blattmodus"]),
    ("A <t1>leaf</t1> and a leaf.", "Ein <t1>Blatt</t1> und ein <t1>Blatt</t1>.", "Ein <t1>Blatt</t1> und ein Blatt.", ["Blatt"]),
    # ein Stück ohne Gegenstück neben einem ganzen Paar fällt weg
    ("<t1>Leaf mode</t1> is old, called <t2>stem mode</t2>. Then enter leaf mode.",
     "<t1>Leaf mode</t1> ist alt, genannt <t2>stem mode</t2>. Dann starte <t2>Leaf mode</t1>.",
     "<t1>Leaf mode</t1> ist alt, genannt <t2>stem mode</t2>. Dann starte Leaf mode.", ["<t2>", "</t1>"]),
    # erfunden: eine Klammer, die es nicht gibt, auch mit der Nummer eines Platzhalters
    ("<x1/> A flag for leaf mode.", "<x1/> Ein Flag für <t1>Leaf mode</t1>.", "<x1/> Ein Flag für Leaf mode.", ["Leaf mode"]),
    ("As shown in", "Wie in <t1>...</t1>", "Wie in ...", ["..."]),
])
def test_marken_werden_verlustfrei_repariert(vorlage, deutsch, repariert, stellen):
    text, reparaturen = reparieren(vorlage, deutsch)
    assert text == repariert and pruefe_marken(vorlage, text) == []
    assert [r.stelle for r in reparaturen] == stellen and all(r.art == "marken" for r in reparaturen)


def test_reparatur_nennt_den_grund_und_fasst_platzhalter_nie_an():
    _, [doppelt] = reparieren("A <t1>leaf</t1>.", "Ein <t1>Blatt</t1>, ein <t1>Blatt</t1>.")
    assert doppelt == Reparatur(art="marken", text="Die Marke 1 stand doppelt da: sie bleibt nur an der Stelle, die zum Original "
                                                   "passt; hier fiel sie weg, der Text bleibt", stelle="Blatt")
    _, [erfunden] = reparieren("A leaf.", "Ein <t3>Blatt</t3>.")
    assert erfunden.text == "Die Marke 3 gibt es im Original nicht: entfernt, der Text bleibt"
    for deutsch in ("Ein Blatt.", "Ein Blatt <x1/> <x1/>.", "Ein Blatt <x1/> <x2/>.", "Ein <t2>Blatt.", "Ein <t2>Blatt</t2> <x1/>"):
        assert reparieren("A <t2>leaf</t2> <x1/>.", deutsch) == (deutsch, [])     # fehlt, doppelt, fremd, offen: bleibt ein Befund
    assert reparieren("A <t1>leaf</t1>.", "Ein <t1>Blatt</t1>.") == ("Ein <t1>Blatt</t1>.", [])


# -- Zeichen für das Modell ---------------------------------------------------------------------------------------------------

def test_das_modell_sieht_zeichen_und_seine_antwort_wird_wieder_maskiert():
    vorlage = "Water the bed if moisture &lt; 30 &amp; the <t1>pump</t1> is on."
    assert fuer_modell(vorlage) == "Water the bed if moisture < 30 & the <t1>pump</t1> is on."
    antwort = "Gieße das Beet, wenn die Feuchte < 30 ist & die <t1>Pumpe</t1> läuft."
    gespeichert = aus_modell(antwort, vorlage)
    assert gespeichert == "Gieße das Beet, wenn die Feuchte &lt; 30 ist &amp; die <t1>Pumpe</t1> läuft."
    assert pruefe_marken(vorlage, gespeichert) == [] and pruefe_zeichen(vorlage, gespeichert) == []
    assert fuer_modell("Write &lt;t1&gt; by hand.") == "Write &lt;t1&gt; by hand."          # sähe als Zeichen wie eine Marke aus


def test_fremde_auszeichnung_bleibt_roh_text_aus_dem_original_nicht():
    vorlage = "Use the &lt;div&gt; element for each bed."
    assert aus_modell("Nimm das <div>-Element für jedes Beet.", vorlage) == "Nimm das &lt;div&gt;-Element für jedes Beet."
    roh = aus_modell("Nimm das <b>Element</b> für jedes Beet.", vorlage)
    assert roh == "Nimm das <b>Element</b> für jedes Beet."
    [befund] = pruefe_marken(vorlage, roh)
    assert "Fremde Auszeichnung" in befund.text and befund.stelle == "<b>"
    assert aus_modell("Gieße, wenn x <t1>klein</t1> ist.", "Water if x is <t1>small</t1>.") == "Gieße, wenn x <t1>klein</t1> ist."


def test_eine_fruehere_antwort_mit_rohen_zeichen_wird_sicher_geschrieben():
    """Frühere Antworten (oder Text von Hand) können rohe Zeichen und Zeichenreferenzen mischen; das Ergebnis besteht die
    Prüfung Marken und ändert sich beim zweiten Mal nicht mehr."""
    vorlage = "<x1/>: Less than, if a &lt; b &amp;&amp; c."
    alt = "<x1/>: Kleiner als, wenn a < b &amp;& c."
    neu = gesichert(alt, vorlage)
    assert neu == "<x1/>: Kleiner als, wenn a &lt; b &amp;&amp; c." and gesichert(neu, vorlage) == neu
    assert pruefe_marken(vorlage, alt) != [] and pruefe_marken(vorlage, neu) == []


def test_zeichenreferenz_als_text_faellt_auf():
    """Schreibt das Modell &lt; statt <, steht nach dem Maskieren &amp;lt; da, also "&lt;" als Text im Buch."""
    vorlage = "Water if moisture &lt; 30."
    [befund] = pruefe_zeichen(vorlage, aus_modell("Gieße, wenn die Feuchte &lt; 30 ist.", vorlage))
    assert befund.art == "zeichen" and "&lt;" in befund.text
    buch_ueber_html = "Write &amp;lt; for a less-than sign."                         # das Original führt sie selbst als Text
    assert pruefe_zeichen(buch_ueber_html, aus_modell("Schreibe &lt; für ein Kleiner-Zeichen.", buch_ueber_html)) == []


# -- Zahlen -------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("original, deutsch", [
    ("It waters 16,000 plants in 1.5 hours.", "Sie gießt 16.000 Pflanzen in 1,5 Stunden."),
    ("It waters 16,000 plants.", "Sie gießt 16\u202f000 Pflanzen."),                        # mit schmalem Leerzeichen
    ("It costs 1,000.50 dollars.", "Es kostet 1.000,50 Dollar."),
    ("Use Python 3.12.1 since 2020.", "Nimm Python 3.12.1 seit 2020."),                     # Version bleibt
    ("Python 3.12 is out.", "Python 3.12 ist da."),
    ("It is 1.5 times faster.", "Es ist 1.5-mal schneller."),                               # gleich geschrieben, kein anderer Sinn
    ("It happened on 11/26/2026.", "Es geschah am 26.11.2026."),                           # Datum umgestellt
    ("Step <t1>2</t1> of 3.", "Schritt <t1>2</t1> von 3."),
    ("Three plants.", "Drei Pflanzen."),
    ("Three plants.", "3 Pflanzen."),                                                        # Zahlwort im Original
    ("The robot walks a 4-level maze of 512 cells.", "Der Roboter läuft durch ein vierstufiges Labyrinth aus 512 Zellen."),
    ("A 2-way valve with 3D sensors.", "Ein Zweiwegeventil mit dreidimensionalen Sensoren."),
    ("Fill 1 tank.", "Fülle einen Tank."),
    ("Two levels and two rows.", "Zwei Ebenen und zwei Reihen."),                           # Zahlwörter allein fordern nichts
])
def test_zahlen_gut(original, deutsch):
    assert pruefe_zahlen(original, deutsch) == []


@pytest.mark.parametrize("original, deutsch, im_text", [
    ("It waters 16,000 plants.", "Sie gießt 17.000 Pflanzen.", "im Original 16,000; in der Übersetzung 17.000"),
    ("It waters 16,000 plants.", "Sie gießt Pflanzen.", "im Original 16,000"),
    ("It waters plants.", "Sie gießt 40 Pflanzen.", "in der Übersetzung 40"),
    ("It takes 1.5 hours.", "Es dauert 15 Stunden.", "im Original 1.5"),
    ("It waters 16,000 plants.", "Sie gießt 16,000 Pflanzen.", "englischer Schreibweise"),  # hieße 16
    ("Add 1.500 litres.", "Gib 1.500 Liter dazu.", "englischer Schreibweise"),             # hieße 1500
    ("A 4-level maze.", "Ein vierzehnstufiges Labyrinth.", "im Original 4"),                  # vierzehn ist nicht vier
    ("Wait 8 hours.", "Achte auf die Stunden.", "im Original 8"),                             # achten ist keine Zahl
    ("Cut 2 branches.", "Schneide Zweige.", "im Original 2"),                                 # Zweig ist keine Zahl
    ("Fill 3 tanks.", "Fülle einige Tanks.", "im Original 3"),
])
def test_zahlen_schlecht(original, deutsch, im_text):
    befunde = pruefe_zahlen(original, deutsch)
    assert arten(befunde) == ["zahlen"] and im_text in befunde[0].text


def test_zahlen_werte_beider_schreibweisen():
    assert zahlen.wert_englisch("16,000") == zahlen.wert_deutsch("16.000") == "16000"
    assert zahlen.wert_englisch("1.5") == zahlen.wert_deutsch("1,5") == "1.5"
    assert zahlen.wert_englisch("3.12.1") is None and zahlen.wert_deutsch("3.12.1") is None


# -- Einheiten ----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("original, deutsch", [
    ("The log is 3 GB and the pipe 5 m long.", "Das Protokoll hat 3 GB und das Rohr ist 5 m lang."),
    ("It holds 50% more at 20 °C.", "Es fasst 50 Prozent mehr bei 20 °C."),
    ("The pipe is 5 feet long.", "Das Rohr ist 5 Fuß lang."),
    ("The road is 3 miles long.", "Die Straße ist 3 Meilen lang."),
    ("Wait 5 s.", "Warte 5 s."),
    ("In the 1990s it was slow.", "In den 1990ern war es langsam."),                        # kein s für Sekunden
    ("Set the flag, BIT.LA[bit 12].<t1>1</t1> A small robot uses it.",                     # Fußnotenzeichen, kein Ampere
     "Setze das Flag, BIT.LA[Bit 12].<t1>1</t1> Ein kleiner Roboter nutzt es."),
    ("See BNDx.<t1>2</t1> A bed is chosen.", "Siehe BNDx.<t1>2</t1> Ein Beet wird gewählt."),
])
def test_einheiten_gut(original, deutsch):
    assert pruefe_einheiten(original, deutsch, begriffe=BEGRIFFE) == []


@pytest.mark.parametrize("original, deutsch, im_text", [
    ("The pipe is 5 feet long.", "Das Rohr ist 5 Fuß (1,5 m) lang.", "m ist hinzugekommen"),
    ("The log is 3 GB.", "Das Protokoll hat 3 MB.", "GB fehlt"),
    ("The pipe is 5 feet long.", "Das Rohr ist 5 feet lang.", "nicht als Fuß"),
    ("It holds 50% more.", "Es fasst 50 mehr.", "% fehlt"),
    ("The pump draws 5 A. Then it rests.", "Die Pumpe zieht 5. Dann ruht sie.", "A fehlt"),              # Ampere bleibt Ampere
])
def test_einheiten_schlecht(original, deutsch, im_text):
    befunde = pruefe_einheiten(original, deutsch, begriffe=BEGRIFFE)
    assert "einheiten" in arten(befunde) and any(im_text in b.text for b in befunde)


# -- Bezeichner ---------------------------------------------------------------------------------------------------------------

def test_bezeichner_werden_gefunden():
    text = ("Use os.path.join() on /etc/hosts, see https://example.org/a, mail team@example.org, set MAX_SIZE, "
            "call getValue in HttpClient v2.0 with --verbose and read config.yaml via the HTTP API.")
    assert bezeichner(text) == ["os.path.join()", "/etc/hosts", "https://example.org/a", "team@example.org", "MAX_SIZE", "getValue",
                                "HttpClient", "v2.0", "--verbose", "config.yaml", "HTTP", "API"]


@pytest.mark.parametrize("original, deutsch", [
    ("Call water_all() and read config.yaml with --verbose.", "Rufe water_all() auf und lies config.yaml mit --verbose."),
    ("The APIs speak JSON.", "Die APIs sprechen JSON."),
    ("The API speaks JSON.", "Die HTTP-API spricht JSON."),
    ("THE PUMP MUST STAY ON.", "DIE PUMPE MUSS AN BLEIBEN."),                             # Großbuchstaben sind hier keine Abkürzungen
    ("Visit https://example.org/garden today.", "Besuche heute https://example.org/garden."),
])
def test_bezeichner_gut(original, deutsch):
    assert pruefe_bezeichner(original, deutsch, begriffe=BEGRIFFE) == []


@pytest.mark.parametrize("original, deutsch, token", [
    ("Call water_all() first.", "Rufe zuerst wasser_alle() auf.", "water_all()"),
    ("Use the --verbose option.", "Nimm die Option -verbose.", "--verbose"),
    ("Edit config.yaml now.", "Bearbeite jetzt die Konfiguration.", "config.yaml"),
    ("Call getValue twice.", "Rufe zweimal get_value auf.", "getValue"),
    ("The HTTP server runs.", "Der Webserver läuft.", "HTTP"),
])
def test_bezeichner_schlecht(original, deutsch, token):
    [befund] = pruefe_bezeichner(original, deutsch, begriffe=BEGRIFFE)
    assert befund.art == "bezeichner" and befund.text.startswith(token)


@pytest.mark.parametrize("original, deutsch", [
    # ein verlorener Bindestrich in einer Zeile aus großen Wörtern: kein Bezeichner
    ("2. MultiPlayer Modes: The engine is ready for many players.", "2. Mehrspieler-Modi: Die Engine ist für viele Spieler bereit."),
    ("4. InApp Shop (WellKnown Patterns):", "4. Laden in der App (bekannte Muster):"),
    ("The SetUp Guide", "Die Anleitung zur Einrichtung"),
    # das Original schreibt das Wort auch klein
    ("The PlugIn system makes the tool a plugin host.", "Das System für Erweiterungen macht das Werkzeug zum Erweiterungswirt."),
    # eine Abkürzung mit deutscher Form in der Begriffsliste fordert keiner
    ("Game AI and route finding", "Spiele-KI und Wegfindung"),
])
def test_bezeichner_gut_ohne_verlorene_bindestriche(original, deutsch):
    begriffe = [*BEGRIFFE, Begriff(englisch="AI", deutsch="KI | künstliche Intelligenz")]
    assert pruefe_bezeichner(original, deutsch, begriffe=begriffe) == []


@pytest.mark.parametrize("original, deutsch, token", [
    ("Call the GameState object first.", "Rufe zuerst das Objekt Spielzustand auf.", "GameState"),        # im Satz: Bezeichner
    ("Using the HttpRequestHandler Class", "Die Klasse für Anfragen nutzen", "HttpRequestHandler"),      # drei Teile
    ("Game AI and route finding", "Spiel und Wegfindung", "AI"),                                          # ohne Begriff
])
def test_bezeichner_schlecht_trotz_ueberschrift(original, deutsch, token):
    [befund] = pruefe_bezeichner(original, deutsch, begriffe=BEGRIFFE)
    assert befund.text.startswith(token)


def test_code_im_satz_geht_als_platzhalter_durch():
    """Inline-Code steht als Platzhalter in der Vorlage; was darin steht, prüft keiner nach, er kommt unverändert zurück."""
    assert pruefen("Call <x1/> to start the pump today.", "Rufe <x1/> auf, um die Pumpe heute zu starten.", BEGRIFFE, GRENZEN, "du") == []
    assert arten(pruefen("Call <x1/> to start the pump today.", "Rufe auf, um die Pumpe heute zu starten.", BEGRIFFE, GRENZEN, "du")) == ["marken"]


# -- Begriffe -----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("original, deutsch", [
    ("Each thread has a return value.", "Jeder Thread hat einen Rückgabewert."),
    ("Threads are cheap.", "Threads sind billig."),                                       # Satzanfang, Mehrzahl
    ("The thread pool is full.", "Der Thread-Pool ist voll."),                            # zusammengesetzt
    ("Return values are kept.", "Rückgabewerte bleiben erhalten."),                       # Satzanfang, gebeugt
    ("The event loop waits.", "Die Event-Loop wartet."),                                 # Bindestrich statt Leerzeichen
])
def test_begriffe_gut(original, deutsch):
    assert pruefe_begriffe(original, deutsch, begriffe=BEGRIFFE) == []


@pytest.mark.parametrize("original, deutsch, im_text", [
    ("Each thread is cheap.", "Jeder Faden ist billig.", "thread bleibt englisch"),
    ("Threads are cheap.", "Fäden sind billig.", "thread bleibt englisch"),
    ("It has a return value.", "Es hat einen Ergebniswert.", "heißt hier Rückgabewert"),
])
def test_begriffe_schlecht(original, deutsch, im_text):
    [befund] = pruefe_begriffe(original, deutsch, begriffe=BEGRIFFE)
    assert befund.art == "begriffe" and im_text in befund.text


GEBEUGT = [Begriff(englisch="engaging games", deutsch="ansprechende Spiele"), Begriff(englisch="platforms", deutsch="Plattformen"),
           Begriff(englisch="critical reviews", deutsch="kritische Rezensionen"), Begriff(englisch="directory", deutsch="Verzeichnis"),
           Begriff(englisch="operators", deutsch="Operatoren"), Begriff(englisch="game", deutsch="Spiel"),
           Begriff(englisch="AI", deutsch="KI | künstliche Intelligenz"), Begriff(englisch="obstacles", deutsch="Hindernisse")]


@pytest.mark.parametrize("original, deutsch", [
    ("The world of engaging games is large.", "Die Welt ansprechender Spiele ist groß."),                 # Beugung
    ("It builds engaging games.", "Es baut ansprechende Spiele."),
    ("Publish on platforms like these.", "Veröffentliche auf solchen Spieleplattformen."),                # hinten im Wort
    ("Platforms differ.", "Plattformen unterscheiden sich."),
    ("Only short critical reviews are allowed.", "Erlaubt sind nur kurze Zitate in kritischen Rezensionen."),
    ("Open the project directory.", "Öffne das Projektverzeichnis."),
    ("Name the directory.", "Benenne den Namen des Verzeichnisses."),                                    # Genitiv auf -ses
    ("Assignment operators change a value.", "Zuweisungsoperatoren ändern einen Wert."),
    ("The game starts.", "Das Spiel beginnt."),
    ("The game starts.", "Die Spielrunde beginnt."),                                                     # vorn im Wort
    ("AI routines help.", "KI-Routinen helfen."),                                                        # Abkürzung im Wort
    ("AI is everywhere.", "Künstliche Intelligenz ist überall."),                                        # die zweite Form
    ("Avoid the obstacles.", "Weiche den Hindernissen aus."),
])
def test_begriffe_gebeugt_und_zusammengesetzt(original, deutsch):
    assert pruefe_begriffe(original, deutsch, begriffe=GEBEUGT) == []


@pytest.mark.parametrize("original, deutsch, im_text", [
    ("The world of engaging games is large.", "Die Welt guter Spiele ist groß.", "heißt hier ansprechende Spiele"),
    ("Publish on platforms like these.", "Veröffentliche auf solchen Bühnen.", "heißt hier Plattformen"),
    ("The game starts.", "Ein Beispiel beginnt.", "heißt hier Spiel"),                     # kurzer Stamm steckt nicht in Beispiel
    ("AI is everywhere.", "Das Kino ist überall.", "heißt hier KI oder künstliche Intelligenz"),
    ("AI is everywhere.", "AI ist überall.", "heißt hier KI oder künstliche Intelligenz"),
    ("Avoid the obstacles.", "Weiche den Hindernis aus.", None),                           # Einzahl statt Mehrzahl: erlaubt
])
def test_begriffe_schlecht_trotz_beugung(original, deutsch, im_text):
    befunde = pruefe_begriffe(original, deutsch, begriffe=GEBEUGT)
    if im_text is None:
        assert befunde == []
    else:
        [befund] = befunde
        assert im_text in befund.text


RAND = [Begriff(englisch="5-Level Paging", bleibt=True), Begriff(englisch="IA-32e mode", bleibt=True),
        Begriff(englisch="x86-64", bleibt=True), Begriff(englisch="C++", bleibt=True), Begriff(englisch=".NET", bleibt=True),
        Begriff(englisch="paging", deutsch="Seitenverwaltung"), Begriff(englisch="server", bleibt=True)]


@pytest.mark.parametrize("original, deutsch", [
    ("It uses 5-level paging.", "Er nutzt 5-Level Paging."),
    ("It uses 5- level paging.", "Er nutzt 5-Level-Paging."),                              # Zeilenumbruch im PDF, Bindestrich
    ("It uses 5\u2013level paging.", "Er nutzt 5-Level Paging."),                          # Strich im Original
    ("(5-level paging) is new.", "(5-Level Paging) ist neu."),
    ("Enter IA-32e mode now.", "Wechsle jetzt in den IA-32e mode."),
    ("It runs on x86-64.", "Es läuft auf x86-64."),
    ("Write C++ code.", "Schreibe C++-Code."),
    ("Use .NET here.", "Nutze hier .NET."),
    # Teil eines längeren Begriffs: paging in 5-level paging zählt für den längeren, nicht für sich
    ("With 5-level paging the hierarchy grows.", "Mit 5-Level Paging wächst die Hierarchie."),
    # Server bleibt englisch, auch vorn und hinten in einem zusammengesetzten Wort
    ("Scale the server infrastructure.", "Skaliere die Serverinfrastruktur."),
    ("Each web server answers.", "Jeder Webserver antwortet."),
])
def test_begriffe_an_wortgrenzen_mit_ziffern_und_zeichen(original, deutsch):
    assert pruefe_begriffe(original, deutsch, begriffe=RAND) == []


@pytest.mark.parametrize("original, deutsch, im_text", [
    ("It uses 5-level paging.", "Er nutzt die 5-Level Seitenverwaltung.", "5-Level Paging bleibt englisch"),
    ("Enter IA-32e mode now.", "Wechsle jetzt in den IA-32-Modus.", "IA-32e mode bleibt englisch"),
    ("It runs on x86-64.", "Es läuft auf x86.", "x86-64 bleibt englisch"),
    ("Write C++ code.", "Schreibe C-Code.", "C++ bleibt englisch"),
    ("Use .NET here.", "Nutze hier NETZ.", ".NET bleibt englisch"),
    ("With 5-level paging and paging alone.", "Mit 5-Level Paging und Paging allein.", "paging heißt hier Seitenverwaltung"),
    ("Scale the server.", "Skaliere den Service.", "server bleibt englisch"),            # Serv steckt nicht in Service
])
def test_begriffe_an_wortgrenzen_schlecht(original, deutsch, im_text):
    [befund] = pruefe_begriffe(original, deutsch, begriffe=RAND)
    assert im_text in befund.text


# -- Sprache ------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("original, deutsch", [
    ("You should check the filter before the first run.", "Du solltest den Filter vor dem ersten Lauf prüfen."),
    ("See <t1>The Art of the Garden</t1> for more.", "Mehr dazu in <t1>The Art of the Garden</t1>."),   # ein Titel bleibt
    ("Each thread is cheap.", "Jeder Thread ist billig."),
    ("Python", "Python"),                                                                  # nur ein Name
    ("<t1>5-Level Paging</t1>", "<t1>5-Level Paging</t1>"),                                  # nur ein Begriff, der bleibt
])
def test_sprache_gut(original, deutsch):
    assert pruefe_sprache(original, deutsch, begriffe=[*BEGRIFFE, *RAND]) == []


def test_unveraendert_mit_gedankenstrich_ist_unuebersetzt():
    """Jede Antwort bekommt gerade Zeichen: ein abgeschriebener Block mit Gedankenstrich ist danach nicht mehr zeichengleich und
    gilt trotzdem als unübersetzt."""
    en = "A tank fault \u2014 #TF \u2014 occurs if the lid is open."
    assert unuebersetzt(en, gerade(en), []) and unuebersetzt("Introduction", "Introduction", [])
    assert not unuebersetzt("Gardenix", "Gardenix", []) and not unuebersetzt(en, "Ein Tankfehler tritt auf.", [])


@pytest.mark.parametrize("original, deutsch, stelle", [
    ("Check the filter. Then start the pump and wait for the water.",
     "Prüfe den Filter. Then start the pump and wait for the water.", "Then start the pump and wait for the water."),
    ("You should check the filter before the first run.", "You should check the filter before the first run.",
     "You should check the filter before the first run."),
    ("Check the green filter now", "Check the green filter now", "Check the green filter now"),          # unübersetzt
    ("<t1>2.1 5-Level Paging: Introduction</t1>", "<t1>2.1 5-Level Paging: Introduction</t1>",           # ein Alltagswort
     "2.1 5-Level Paging: Introduction"),
])
def test_sprache_schlecht(original, deutsch, stelle):
    [befund] = pruefe_sprache(original, deutsch, begriffe=BEGRIFFE)
    assert befund.art == "sprache" and befund.stelle == stelle


@pytest.mark.parametrize("original, deutsch, gruppen", [
    ("The tool offers features like file loading, error handling, and sound output.",
     "Das Werkzeug bietet Funktionen wie file loading, error handling und sound output.", ["file loading", "error handling", "sound output"]),
    ("It has platform-specific helpers.", "Es hat platform-specific helpers.", ["platform-specific helpers"]),
])
def test_stehengebliebenes_englisch(original, deutsch, gruppen):
    assert stehengeblieben(original, deutsch, BEGRIFFE) == gruppen
    befunde = pruefe_sprache(original, deutsch, begriffe=BEGRIFFE)
    assert [(b.art, b.stelle) for b in befunde] == [("sprache", g) for g in gruppen]
    assert befunde[0].text == f'Englisch stehen geblieben: "{gruppen[0]}" hat im Deutschen eine übliche Form'


@pytest.mark.parametrize("original, deutsch", [
    ("Similar to null in other languages.", "Ähnlich wie null in anderen Sprachen."),          # null, in: auch deutsch
    ("The Garden Store sells seeds.", "Der Garden Store verkauft Samen."),                     # ein Name: im Original groß
    ("The scene management runs.", "Das Scene Management läuft."),                             # groß: urteilt der Prüfer
    ("A value called the <t1>leaf budget limit</t1>.", "Ein Wert namens <t1>leaf budget limit</t1>."),   # benannter Begriff
    ('The field "leaf budget limit" is set.', 'Das Feld "leaf budget limit" ist gesetzt.'),    # in Anführungszeichen
    ("Each event loop runs in a game loop.", "Jede event loop läuft in einer game loop."),     # Begriff und eingeführtes Fachwort
    ("The thread pool is full.", "Der thread pool ist voll."),                                 # thread: eingeführtes Fachwort
    ("Python offers a for loop.", "Python bietet eine for-Schleife."),                          # nur ein Wort aus dem Original
    ("Call setup_tank() and read_level() now.", "Rufe setup_tank() und read_level() auf."),     # Bezeichner
])
def test_kein_stehengebliebenes_englisch(original, deutsch):
    assert stehengeblieben(original, deutsch, BEGRIFFE) == []


def test_englisch_aus_dem_original_fuer_den_pruefer():
    assert englisch_aus_dem_original("Scene Management und Game Loop", "It offers scene management and a game loop.", []) == ["Scene", "Management"]
    assert englisch_aus_dem_original("Thread im Cache", "A thread in the cache.", BEGRIFFE) == []
    assert englisch_aus_dem_original("Wasserfluss", "The water flow.", []) == []


def test_namen_mit_abkuerzung_duerfen_bleiben():
    assert pruefe_sprache("1. Spring Garden Days (SGD):", "1. Spring Garden Days (SGD):", begriffe=[]) == []
    [befund] = pruefe_sprache("Garden Watering Helpers:", "Garden Watering Helpers:", begriffe=[])   # kein Name: unübersetzt
    assert befund.text == "Der Block ist unübersetzt"


def test_sprache_eines_buchs():
    englisch = "The garden is small and the pump is old, but it waters all of the beds that we have in the yard. " * 3
    deutsch = "Der Garten ist klein und die Pumpe ist alt, aber sie gießt alle Beete, die wir im Hof haben. " * 3
    assert ist_englisch(englisch) and not ist_englisch(deutsch)
    assert buch_ist_englisch("en-US", "") and buch_ist_englisch("eng", "") and buch_ist_englisch("English", deutsch)
    assert not buch_ist_englisch("de", englisch)
    assert buch_ist_englisch("", englisch) and not buch_ist_englisch(None, deutsch)
    assert englischer_satz("Then start the pump and wait for the water.") and not englischer_satz("Starte dann die Pumpe.")


# -- Länge und Vollständigkeit ------------------------------------------------------------------------------------------------

def test_laenge():
    original = "This is a fairly long sentence about pumps that needs a proper translation into German."
    assert pruefe_laenge(original, "Dies ist ein recht langer Satz über Pumpen, der eine gute Übersetzung ins Deutsche braucht.",
                         grenzen=GRENZEN) == []
    [kurz] = pruefe_laenge(original, "Pumpen.", grenzen=GRENZEN)
    assert kurz.art == "laenge" and "kürzer" in kurz.text and "0,8 bis 1,8" in kurz.text
    [lang] = pruefe_laenge("A short but complete sentence about the old garden pump today.", "Ein " + "sehr " * 40 + "langer Satz.",
                           grenzen=GRENZEN)
    assert "länger" in lang.text
    assert pruefe_laenge("Yes.", "Jawohl, so ist es.", grenzen=GRENZEN) == []                 # zu kurz, um etwas zu sagen


def test_saetze_mit_abkuerzungen():
    assert len(saetze("Check the filter, e.g. twice a week. Dr. Example agrees. J. R. Doe too.")) == 3
    assert len(saetze("Prüfe den Filter, z. B. zweimal pro Woche. Siehe Abb. 3 dazu. Fertig!")) == 3
    assert len(saetze("Version 1.5 is out. Use it.")) == 2


@pytest.mark.parametrize("original, deutsch, gut", [
    ("Check the filter. Start the pump. Wait.", "Prüfe den Filter. Starte die Pumpe. Warte.", True),
    ("Check the filter. Start the pump.", "Prüfe den Filter und starte die Pumpe.", True),     # Abweichung eins
    ("Check the filter. Start the pump. Wait for water. Then rest.", "Prüfe den Filter, starte die Pumpe.", False),
    ("Check it.", "Prüfe ihn. Starte die Pumpe. Warte auf Wasser.", False),                  # hinzugefügt
])
def test_vollstaendigkeit(original, deutsch, gut):
    befunde = pruefe_vollstaendigkeit(original, deutsch)
    assert (befunde == []) is gut and (gut or befunde[0].art == "vollstaendigkeit")


# -- Zeichen ------------------------------------------------------------------------------------------------------------------

def test_gerade_macht_gesetzte_zeichen_gerade():
    assert gerade("\u201ePrüfe\u201c den \u201aFilter\u2018 \u2013 jetzt\u2014sofort, 10\u201320 Mal") == "\"Prüfe\" den 'Filter' - jetzt - sofort, 10-20 Mal"
    assert gerade("Die Pumpe -- alt") == "Die Pumpe - alt"


@pytest.mark.parametrize("deutsch", ["Prüfe den \"Filter\" - jetzt.", "Die Quelle ist neu und aktuell.", "Nimm --verbose."])
def test_zeichen_gut(deutsch):
    assert pruefe_zeichen("x", deutsch) == []


@pytest.mark.parametrize("deutsch, im_text", [
    ("\u201ePrüfe\u201c den Filter.", "Gesetztes Zeichen"),
    ("Prüfe den Filter \u2013 jetzt.", "Gesetztes Zeichen"),
    ("Das gilt fuer alle Beete.", "Umlaut als Ersatz geschrieben: fuer"),
    ("Die Groesse zaehlt.", "Umlaut als Ersatz"),
    ("Die Pumpe -- alt.", "Doppelter Bindestrich"),
])
def test_zeichen_schlecht(deutsch, im_text):
    befunde = pruefe_zeichen("x", deutsch)
    assert befunde and befunde[0].art == "zeichen" and im_text in befunde[0].text


# -- Anrede -------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("original, deutsch", [
    ("You water the beds.", "Du gießt die Beete."),
    ("Install the pump first.", "Installiere zuerst die Pumpe."),
    ("The pump is old. It still works.", "Die Pumpe ist alt. Sie läuft noch."),                     # dritte Person am Satzanfang
    ("Pumps are cheap. They last long.", "Pumpen sind billig. Sie halten lange."),                  # ohne Anrede im Original
    ("You need the pumps. They work hard.", "Du brauchst die Pumpen. Sie arbeiten viel."),          # du im Block: Sie ist sie
    ("The gardener lost her key.", "Die Gärtnerin hat ihren Schlüssel verloren."),                 # ihr klein: dritte Person
    ("The note says: Sie gießen hier.", "Der Zettel sagt: Sie gießen hier."),                         # steht so im Original
])
def test_anrede_du_gut(original, deutsch):
    assert pruefe_anrede(original, deutsch, anrede="du") == []


@pytest.mark.parametrize("original, deutsch, form, stelle", [
    ("Install the pump first.", "Installieren Sie zuerst die Pumpe.", "Sie", "Installieren Sie"),
    ("This helps you.", "Das hilft Ihnen.", "Ihnen", "hilft Ihnen"),
    ("Check your pump.", "Prüfe Ihre Pumpe.", "Ihre", "Prüfe Ihre"),
    ("Well done! You can water now.", "Gut gemacht! Sie können jetzt gießen.", "Sie", "gemacht! Sie"),   # Satzanfang, you
])
def test_anrede_du_schlecht(original, deutsch, form, stelle):
    [befund] = pruefe_anrede(original, deutsch, anrede="du")
    assert befund.art == "anrede" and f'hier steht "{form}"' in befund.text and befund.stelle == stelle


def test_anrede_sie():
    assert pruefe_anrede("Install the pump first.", "Installieren Sie zuerst die Pumpe.", anrede="Sie") == []
    assert pruefe_anrede("Use the DIR command.", "Nutze den Befehl DIR.", anrede="Sie") == []                # Großbuchstaben
    assert pruefe_anrede("Type dir to list it.", "Tippe dir, um es zu zeigen.", anrede="Sie") == []          # Original: dir
    befunde = pruefe_anrede("You water your beds.", "Du gießt deine Beete, dann ruhst du dich aus.", anrede="Sie")
    assert [b.stelle for b in befunde] == ["Du", "gießt deine", "du dich"]                    # je Form einmal
    assert {b.text for b in befunde} == {'Der Leser wird mit "Sie" angesprochen, hier steht "Du"',
                                         'Der Leser wird mit "Sie" angesprochen, hier steht "deine"',
                                         'Der Leser wird mit "Sie" angesprochen, hier steht "dich"'}


# -- Alle zusammen ------------------------------------------------------------------------------------------------------------

def test_alle_pruefungen_bestanden_und_leer():
    original = "A small machine can water <t1>16,000</t1> plants in 1.5 hours, which is about 3\u00a0GB of logs.<x2/>"
    deutsch = "Eine kleine Maschine kann <t1>16.000</t1> Pflanzen in 1,5 Stunden gießen, das sind etwa 3\u00a0GB Protokolle.<x2/>"
    assert pruefen(original, deutsch, BEGRIFFE, GRENZEN, "du") == []
    assert arten(pruefen(original, "  ", BEGRIFFE, GRENZEN, "du")) == ["vollstaendigkeit"]
    schlecht = pruefen(original, "A small machine can water <t1>16,000</t1> plants in 1.5 hours, which is about 3 MB of logs.",
                       BEGRIFFE, GRENZEN, "du")
    assert {"marken", "zahlen", "einheiten", "sprache"} <= set(arten(schlecht))
