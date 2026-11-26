"""Die neun festen Prüfungen beim Übersetzen (BF-71): je Prüfung Gut- und Schlechtfälle, dazu ihre Bausteine (Zahlen,
Sätze, Sprache, Zeichen). Alle Texte sind erfunden."""

import pytest

from backend.app.uebersetzung import zahlen
from backend.app.uebersetzung.modelle import Begriff, Laengengrenzen
from backend.app.uebersetzung.pruefen import (
    bezeichner, pruefe_begriffe, pruefe_bezeichner, pruefe_einheiten, pruefe_laenge, pruefe_marken, pruefe_sprache,
    pruefe_vollstaendigkeit, pruefe_zahlen, pruefe_zeichen, pruefen,
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
])
def test_einheiten_gut(original, deutsch):
    assert pruefe_einheiten(original, deutsch, begriffe=BEGRIFFE) == []


@pytest.mark.parametrize("original, deutsch, im_text", [
    ("The pipe is 5 feet long.", "Das Rohr ist 5 Fuß (1,5 m) lang.", "m ist hinzugekommen"),
    ("The log is 3 GB.", "Das Protokoll hat 3 MB.", "GB fehlt"),
    ("The pipe is 5 feet long.", "Das Rohr ist 5 feet lang.", "nicht als Fuß"),
    ("It holds 50% more.", "Es fasst 50 mehr.", "% fehlt"),
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


def test_code_im_satz_geht_als_platzhalter_durch():
    """Inline-Code steht als Platzhalter in der Vorlage; was darin steht, prüft keiner nach, er kommt unverändert zurück."""
    assert pruefen("Call <x1/> to start the pump today.", "Rufe <x1/> auf, um die Pumpe heute zu starten.", BEGRIFFE, GRENZEN) == []
    assert arten(pruefen("Call <x1/> to start the pump today.", "Rufe auf, um die Pumpe heute zu starten.", BEGRIFFE, GRENZEN)) == ["marken"]


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


# -- Sprache ------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("original, deutsch", [
    ("You should check the filter before the first run.", "Du solltest den Filter vor dem ersten Lauf prüfen."),
    ("See <t1>The Art of the Garden</t1> for more.", "Mehr dazu in <t1>The Art of the Garden</t1>."),   # ein Titel bleibt
    ("Each thread is cheap.", "Jeder Thread ist billig."),
    ("Python", "Python"),                                                                  # nur ein Name
])
def test_sprache_gut(original, deutsch):
    assert pruefe_sprache(original, deutsch, begriffe=BEGRIFFE) == []


@pytest.mark.parametrize("original, deutsch, stelle", [
    ("Check the filter. Then start the pump and wait for the water.",
     "Prüfe den Filter. Then start the pump and wait for the water.", "Then start the pump and wait for the water."),
    ("You should check the filter before the first run.", "You should check the filter before the first run.",
     "You should check the filter before the first run."),
    ("Check the green filter now", "Check the green filter now", "Check the green filter now"),          # unübersetzt
])
def test_sprache_schlecht(original, deutsch, stelle):
    [befund] = pruefe_sprache(original, deutsch, begriffe=BEGRIFFE)
    assert befund.art == "sprache" and befund.stelle == stelle


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


# -- Alle zusammen ------------------------------------------------------------------------------------------------------------

def test_alle_pruefungen_bestanden_und_leer():
    original = "A small machine can water <t1>16,000</t1> plants in 1.5 hours, which is about 3\u00a0GB of logs.<x2/>"
    deutsch = "Eine kleine Maschine kann <t1>16.000</t1> Pflanzen in 1,5 Stunden gießen, das sind etwa 3\u00a0GB Protokolle.<x2/>"
    assert pruefen(original, deutsch, BEGRIFFE, GRENZEN) == []
    assert arten(pruefen(original, "  ", BEGRIFFE, GRENZEN)) == ["vollstaendigkeit"]
    schlecht = pruefen(original, "A small machine can water <t1>16,000</t1> plants in 1.5 hours, which is about 3 MB of logs.",
                       BEGRIFFE, GRENZEN)
    assert {"marken", "zahlen", "einheiten", "sprache"} <= set(arten(schlecht))
