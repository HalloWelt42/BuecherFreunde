"""Übersetzen in Portionen, KI-Prüfer und Begriffsliste (BF-71) mit einem nachgestellten Modell: feste Anzahl je Antwort,
Halbieren bei unpassender Antwort, gleiche Blöcke einmal, Nacharbeit mit den Mängeln im Auftrag. Alle Texte sind erfunden."""

import json

import pytest

from backend.app.uebersetzung import anweisungen, begriffe
from backend.app.uebersetzung.begriffe import Buchtext
from backend.app.uebersetzung.modelle import Befund, Begriff, Block, Kandidat, Unbrauchbar
from backend.app.uebersetzung.pruefer import UNBEURTEILT, Urteil, gilt, pruefen_lassen, urteile_aus
from backend.app.uebersetzung.uebersetzen import Auftrag, nacharbeiten, portionen, speicherschluessel, texte_aus, uebersetzen, zusammenhang

TABELLE = {"Fill the tank.": "Fülle den Tank.", "Use clean water.": "Nimm sauberes Wasser.", "Start the pump.": "Starte die Pumpe.",
           "Wait for the water.": "Warte auf das Wasser.", "Check the thread.": "Prüfe den Thread."}


def bloecke(*vorlagen: str) -> list[Block]:
    return [Block(kennung=f"2.{i}", kapitel=2, nr=i, art="absatz", vorlage=v, woerter=len(v.split())) for i, v in enumerate(vorlagen, 1)]


class Modell:
    """Nachgestellt: übersetzt nach der Tabelle; `kaputt` liefert bei mehr als einem Block einen zu wenig."""

    def __init__(self, kaputt: bool = False, fehler: Exception | None = None) -> None:
        self.kaputt, self.fehler = kaputt, fehler
        self.aufrufe: list[dict] = []

    async def __call__(self, system, nutzer, *, schema_name, schema, titel, modell=""):
        daten = json.loads(nutzer)
        self.aufrufe.append({"art": schema_name, "daten": daten, "modell": modell, "system": system, "titel": titel, "schema": schema})
        if self.fehler:
            raise self.fehler
        texte = [TABELLE.get(v, v) for v in daten["bloecke"]]
        if self.kaputt and len(texte) > 1:
            texte = texte[:-1]
        return {"bloecke": texte}


AUFTRAG = Auftrag(kapitel="Watering", begriffe=[Begriff(englisch="thread", bleibt=True), Begriff(englisch="pump", deutsch="Pumpe")])


def test_portionen_an_blockgrenzen():
    b = bloecke("a" * 1000, "b" * 1000, "c" * 1000, "d", "e")
    assert [[x.kennung for x in p] for p in portionen(b, 2500, 30)] == [["2.1", "2.2"], ["2.3", "2.4", "2.5"]]
    assert [len(p) for p in portionen(bloecke(*"abcdefg"), 2500, 3)] == [3, 3, 1]
    assert [len(p) for p in portionen(bloecke("x" * 5000), 2500, 30)] == [1]           # ein großer Block bleibt ganz


async def test_eine_portion_mit_fester_anzahl_und_zusammenhang():
    m = Modell()
    vorher = bloecke("Fill the tank. Use clean water. Start the pump.")
    portion = [b.model_copy(update={"kennung": f"2.{i + 2}", "nr": i + 2}) for i, b in enumerate(bloecke("Check the thread.", "Wait for the water."))]
    assert await uebersetzen(m, portion, AUFTRAG, vorher) == {"2.2": "Prüfe den Thread.", "2.3": "Warte auf das Wasser."}
    [a] = m.aufrufe
    assert a["art"] == "uebersetzung" and a["schema"] == anweisungen.schema_texte(2) and "genau 2 übersetzte Blöcke" in a["system"]
    assert a["daten"]["kapitel"] == "Watering" and a["daten"]["zusammenhang"] == "Use clean water. Start the pump."
    assert a["daten"]["begriffe"] == {"thread": "bleibt englisch"}                   # nur, was in der Portion vorkommt
    assert zusammenhang([]) == ""


async def test_unpassende_antwort_wird_halbiert_bis_einzeln():
    m = Modell(kaputt=True)
    b = bloecke("Fill the tank.", "Use clean water.", "Start the pump.", "Wait for the water.")
    aus = await uebersetzen(m, b, AUFTRAG)
    assert aus == {"2.1": "Fülle den Tank.", "2.2": "Nimm sauberes Wasser.", "2.3": "Starte die Pumpe.", "2.4": "Warte auf das Wasser."}
    assert [len(a["daten"]["bloecke"]) for a in m.aufrufe] == [4, 2, 1, 1, 2, 1, 1]


async def test_ohne_brauchbare_antwort_bleibt_der_block_ohne_uebersetzung():
    m = Modell(fehler=Unbrauchbar("kein JSON"))
    assert await uebersetzen(m, bloecke("Fill the tank.", "Use clean water."), AUFTRAG) == {"2.1": None, "2.2": None}
    assert len(m.aufrufe) == 3


async def test_gleiche_bloecke_gehen_einmal_hinaus():
    m = Modell()
    aus = await uebersetzen(m, bloecke("Fill the tank.", "Start the pump.", "Fill the tank."), AUFTRAG)
    assert aus == {"2.1": "Fülle den Tank.", "2.2": "Starte die Pumpe.", "2.3": "Fülle den Tank."}
    assert m.aufrufe[0]["daten"]["bloecke"] == ["Fill the tank.", "Start the pump."]


async def test_antworten_werden_gerade_gemacht_und_geprueft():
    with pytest.raises(Unbrauchbar):
        texte_aus({"bloecke": ["a"]}, 2)
    with pytest.raises(Unbrauchbar):
        texte_aus(["a", "b"], 2)
    assert texte_aus({"bloecke": [" \u201eFülle\u201c den Tank \u2013 jetzt. "]}, 1) == ['"Fülle" den Tank - jetzt.']


async def test_das_modell_sieht_zeichen_und_keine_eigenen_marken():
    """Text geht als Zeichen hinaus, die Antwort kommt in der Schreibweise der Vorlagen zurück; die Anweisung verbietet neue
    Marken und nennt die Anrede."""
    TABELLE["Water if moisture < 30 & <t1>soon</t1>."] = "Gieße, wenn die Feuchte < 30 ist & <t1>bald</t1>."
    try:
        m = Modell()
        aus = await uebersetzen(m, bloecke("Water if moisture &lt; 30 &amp; <t1>soon</t1>."), AUFTRAG)
    finally:
        del TABELLE["Water if moisture < 30 & <t1>soon</t1>."]
    assert aus == {"2.1": "Gieße, wenn die Feuchte &lt; 30 ist &amp; <t1>bald</t1>."}
    [a] = m.aufrufe
    assert a["daten"]["bloecke"] == ["Water if moisture < 30 & <t1>soon</t1>."]
    assert "keine neuen\n  <tN> oder <xN/>" in a["system"] and 'mit "du" an' in a["system"]
    assert 'mit "Sie" an' in anweisungen.uebersetzen(1, "Sie") and "die Anrede (du oder Sie)" in anweisungen.pruefen(1)
    assert "trägt nur die Stelle die Marke" in a["system"] and "auch neben Code, Platzhaltern" in a["system"]


async def test_nacharbeit_nennt_die_maengel():
    m = Modell()
    befunde = [Befund(art="zahlen", quelle="pruefung", text="Die Zahlen weichen ab", stelle="17"),
               Befund(art="sinn", quelle="ki", text="Der Tank wird nicht gefüllt")]
    assert await nacharbeiten(m, bloecke("Fill the tank.")[0], "Leere den Tank.", befunde, AUFTRAG) == "Fülle den Tank."
    [a] = m.aufrufe
    assert a["art"] == "nacharbeit" and "beanstandet" in a["system"]
    assert a["daten"]["beanstandet"] == {"uebersetzung": "Leere den Tank.",
                                         "maengel": ["Die Zahlen weichen ab (Stelle: 17)", "Der Tank wird nicht gefüllt"]}
    assert await nacharbeiten(Modell(fehler=Unbrauchbar("x")), bloecke("Fill the tank.")[0], "", befunde, AUFTRAG) is None


ECHO = "In general, an attempt to read the tank causes a sensor fault (#SF) \u2014 or #TF \u2014 if the lid is open."
ECHO_DE = "Im Allgemeinen löst ein Versuch, den Tank zu lesen, einen Sensorfehler (#SF) aus - oder #TF -, wenn der Deckel offen ist."


class Abschreiber(Modell):
    """Gibt einen Block unverändert zurück, bis eine Anfrage ihn als unübersetzt nennt; `stur` schreibt auch dann ab."""

    def __init__(self, stur: bool = False) -> None:
        super().__init__()
        self.stur = stur

    async def __call__(self, system, nutzer, *, schema_name, schema, titel, modell=""):
        antwort = await super().__call__(system, nutzer, schema_name=schema_name, schema=schema, titel=titel, modell=modell)
        if "unverändert englisch zurück" in system and not self.stur:
            antwort["bloecke"] = [ECHO_DE if v == ECHO else t for v, t in zip(json.loads(nutzer)["bloecke"], antwort["bloecke"])]
        return antwort


async def test_unveraendert_zurueck_wird_einzeln_mit_klarer_anweisung_neu_angefragt():
    """Ein Block, der in einer Portion unverändert englisch zurückkommt, geht gleich noch einmal einzeln hinaus, mit der
    Anweisung für unübersetzte Blöcke; ein Name oder schon Deutsches bleibt, wie es ist."""
    m = Abschreiber()
    aus = await uebersetzen(m, bloecke("Fill the tank.", ECHO, "Gardenix", "Use clean water."), AUFTRAG)
    assert aus == {"2.1": "Fülle den Tank.", "2.2": ECHO_DE, "2.3": "Gardenix", "2.4": "Nimm sauberes Wasser."}
    assert [a["daten"]["bloecke"] for a in m.aufrufe] == [["Fill the tank.", ECHO, "Gardenix", "Use clean water."], [ECHO]]
    einzeln = m.aufrufe[1]
    assert "unverändert englisch zurück" in einzeln["system"] and "genau 1 übersetzte Blöcke" in einzeln["system"]
    assert einzeln["daten"]["zusammenhang"] == "Fill the tank." and "beanstandet" not in einzeln["daten"]
    # bleibt er auch dann englisch, bleibt die Antwort stehen (die Prüfung meldet ihn, die Nacharbeit folgt)
    stur = Abschreiber(stur=True)
    assert (await uebersetzen(stur, bloecke(ECHO), AUFTRAG)) == {"2.1": ECHO.replace("\u2014", "-")}
    assert len(stur.aufrufe) == 2


async def test_nacharbeit_eines_unuebersetzten_blocks_ohne_die_kopie_als_fruehere_uebersetzung():
    """Die Kopie des Originals als "frühere Übersetzung" lädt nur zum Abschreiben ein: die Nacharbeit bekommt die Anweisung
    für unübersetzte Blöcke und die Mängel, nicht die Kopie."""
    m = Abschreiber()
    befunde = [Befund(art="sprache", quelle="pruefung", text="Der Block ist unübersetzt", stelle="In general")]
    assert await nacharbeiten(m, bloecke(ECHO)[0], ECHO.replace("\u2014", "-"), befunde, AUFTRAG) == ECHO_DE
    [a] = m.aufrufe
    assert a["art"] == "nacharbeit" and "unverändert englisch zurück" in a["system"]
    assert a["daten"]["beanstandet"] == {"maengel": ["Der Block ist unübersetzt (Stelle: In general)"]}


def test_zwischenspeicher_haengt_an_vorlage_und_begriffen():
    a = speicherschluessel("Check the thread.", AUFTRAG)
    assert a == speicherschluessel("Check the thread.", AUFTRAG.model_copy(update={"kapitel": "Anders"}))
    assert a != speicherschluessel("Check the thread.", AUFTRAG.model_copy(update={"begriffe": []}))
    assert a != speicherschluessel("Check the thread.", AUFTRAG.model_copy(update={"anrede": "Sie"}))
    assert speicherschluessel("Fill the tank.", AUFTRAG) == speicherschluessel("Fill the tank.", AUFTRAG.model_copy(update={"begriffe": []}))


# -- KI-Prüfer ----------------------------------------------------------------------------------------------------------------

class Pruefer:
    def __init__(self, urteile, kaputt_ab: int = 99) -> None:
        self.urteile, self.kaputt_ab, self.aufrufe = urteile, kaputt_ab, []

    async def __call__(self, system, nutzer, *, schema_name, schema, titel, modell=""):
        daten = json.loads(nutzer)
        self.aufrufe.append({"daten": daten, "modell": modell, "schema": schema})
        paare = daten["paare"]
        if len(paare) >= self.kaputt_ab:
            return {"urteile": []}
        return {"urteile": [self.urteile.get(p["deutsch"], {"in_ordnung": True, "art": "", "grund": "", "stelle": ""}) for p in paare]}


async def test_pruefer_urteilt_je_block():
    mangel = {"in_ordnung": False, "art": "ausgelassen", "grund": "Das Wasser fehlt", "stelle": "Nimm sauberes"}
    p = Pruefer({"Nimm sauberes.": mangel})
    b = bloecke("Fill the tank.", "Use clean water.")
    auftrag = AUFTRAG.model_copy(update={"modell": "qwen/qwen3-coder-next"})
    aus = await pruefen_lassen(p, [(b[0], "Fülle den Tank."), (b[1], "Nimm sauberes.")], auftrag)
    assert aus == {"2.1": Urteil(), "2.2": Urteil(mangel=Befund(art="ausgelassen", quelle="ki", text="Das Wasser fehlt", stelle="Nimm sauberes"))}
    assert p.aufrufe[0]["modell"] == "qwen/qwen3-coder-next" and p.aufrufe[0]["schema"] == anweisungen.schema_urteile(2)
    assert p.aufrufe[0]["daten"]["paare"][1] == {"original": "Use clean water.", "deutsch": "Nimm sauberes."}
    assert set(p.aufrufe[0]["daten"]) == {"kapitel", "paare"}                    # keine Begriffsliste als Anlass für Befunde


async def test_pruefer_urteilt_nur_ueber_sinn_ausgelassenes_und_hinzugefuegtes():
    """Einwände anderer Art (Begriffe, Schreibung, Anrede) und solche, die sich auf eine Begriffsliste berufen, gelten nicht:
    sie werden verworfen und gezählt, der Block ist in Ordnung."""
    p = Pruefer({
        "Prüfe die Bits.": {"in_ordnung": False, "art": "anderes", "grund": "Bits muss klein geschrieben werden", "stelle": "Bits"},
        "Prüfe den Thread.": {"in_ordnung": False, "art": "sinn", "grund": "Thread muss gemäß Begriffsliste Faden heißen",
                              "stelle": "Thread"},
        "Fülle den Eimer.": {"in_ordnung": False, "art": "sinn", "grund": "Ein Eimer ist kein Tank", "stelle": "Eimer"},
    })
    b = bloecke("Check the bits.", "Check the thread.", "Fill the tank.")
    aus = await pruefen_lassen(p, [(b[0], "Prüfe die Bits."), (b[1], "Prüfe den Thread."), (b[2], "Fülle den Eimer.")], AUFTRAG)
    assert aus == {"2.1": Urteil(verworfen=1), "2.2": Urteil(verworfen=1),
                   "2.3": Urteil(mangel=Befund(art="sinn", quelle="ki", text="Ein Eimer ist kein Tank", stelle="Eimer"))}
    assert anweisungen.schema_urteile(1)["properties"]["urteile"]["items"]["properties"]["art"]["enum"] == [
        "", "sinn", "ausgelassen", "hinzugefuegt", "anderes"]
    prompt = anweisungen.pruefen(3)
    assert "Ein Mangel ist nur: sinn" in prompt and "Rechtschreibung, Groß- und Kleinschreibung" in prompt
    # Befunde aus der Zeit, als der Prüfer auch über Begriffe und Grammatik urteilte, gelten nicht mehr
    assert not gilt(Befund(art="begriff", quelle="ki", text="Iteration bleibt englisch"))
    assert not gilt(Befund(art="grammatik", quelle="ki", text="Bits klein"))
    assert not gilt(Befund(art="sinn", quelle="ki", text="Laut Begriffsliste falsch"))
    assert gilt(Befund(art="sinn", quelle="ki", text="Der Tank wird geleert")) and gilt(Befund(art="pruefer", quelle="ki", text=UNBEURTEILT))
    assert gilt(Befund(art="begriffe", quelle="pruefung", text="Der Begriff thread bleibt englisch"))


async def test_pruefer_halbiert_und_nennt_unbeurteiltes():
    p = Pruefer({}, kaputt_ab=2)
    b = bloecke("Fill the tank.", "Use clean water.", "Start the pump.")
    aus = await pruefen_lassen(p, [(x, "Text.") for x in b], AUFTRAG)
    assert aus == {"2.1": Urteil(), "2.2": Urteil(), "2.3": Urteil()} and [len(a["daten"]["paare"]) for a in p.aufrufe] == [3, 1, 2, 1, 1]
    nie = Pruefer({}, kaputt_ab=1)
    assert await pruefen_lassen(nie, [(b[0], "Text.")], AUFTRAG) == {
        "2.1": Urteil(mangel=Befund(art="pruefer", quelle="ki", text=UNBEURTEILT))}


def test_urteile_lesen():
    assert urteile_aus({"urteile": [{"in_ordnung": False, "art": "", "grund": "", "stelle": ""}]}, 1) == [
        Urteil(mangel=Befund(art="sinn", quelle="ki", text="Der Prüfer nennt einen Mangel ohne Grund"))]
    assert urteile_aus({"urteile": [{"in_ordnung": False, "art": "grammatik", "grund": "Satzbau", "stelle": ""}]}, 1) == [Urteil(verworfen=1)]
    for roh in ({"urteile": [{"in_ordnung": "ja"}]}, {"urteile": []}, []):
        with pytest.raises(Unbrauchbar):
            urteile_aus(roh, 1)


# -- Begriffsliste ------------------------------------------------------------------------------------------------------------

def test_namen_nach_regeln():
    texte = ["We run Gardenix on every bed. Then Gardenix waters the beds.", "Most people like Gardenix a lot.",
             "Install Gardenix and Rainbox. Rainbox is old.", "The Pump is big. A pump helps.",          # pump auch klein: kein Name
             "On Monday we water. On Monday we rest. On Monday we sleep.",                                 # Tag: kein Name
             ]
    b = bloecke(*texte) + [Block(kennung="2.9", kapitel=2, nr=9, art="ueberschrift", vorlage="Using Gardenix With Rainbox Every Day")]
    namen = begriffe.namen(b, vorhanden=set())
    assert [(k.englisch, k.bleibt, k.stellen, k.herkunft) for k in namen] == [("Gardenix", True, 4, "regel")]
    assert begriffe.namen(b, vorhanden={"gardenix"}) == []


def test_namen_nur_aus_fliesstext():
    """Überschriften, Einträge im Verzeichnis, Tabellenköpfe und Zeilen aus lauter großen Wörtern schreiben jedes Wort groß:
    daraus kommt kein Name. Gewöhnliche Wörter sind nie Namen, auch wenn sie mitten im Satz groß stehen."""
    titel = ["<t1>2.2 Sorting and Watering</t1>", "<t1>2.3 Sorting by Size</t1>", "4.1 Watering: Sorting the Beds",
             "Bed Position(s)", "Motion and Position:", "Garden Robot Basics"]
    b = (bloecke(*titel)
         + [Block(kennung="3.1", kapitel=3, nr=1, art="ueberschrift", vorlage="Sorting the Beds With Rainbox"),
            Block(kennung="3.2", kapitel=3, nr=2, art="tabellenzelle", vorlage="Bed Position(s)")]
         + bloecke("We trust Rainbox here. Then Rainbox rests. All of it uses Rainbox.", "Read the Basics first. See Basics again. "
                   "Use Basics daily.", "Step one: Finally, water.", "Step two: Finally, rest.", "Step three: Finally, sleep."))
    assert [k.englisch for k in begriffe.namen(b, set(), alltag=frozenset({"basics"}))] == ["Rainbox"]
    assert [k.englisch for k in begriffe.namen(b, set())] == ["Basics", "Rainbox"]           # ohne Liste wäre Basics ein Name
    assert begriffe.titelzeile("2.2 Sorting and Watering") and begriffe.titelzeile("Motion and Position:")
    assert begriffe.titelzeile("5-Level Paging and 5-Level EPT") and begriffe.titelzeile("Garden Robot (GR)")
    assert not begriffe.titelzeile("We trust Rainbox here.") and not begriffe.titelzeile("Install Gardenix And Rainbox.")
    assert not begriffe.titelzeile("Game AI and pathfinding")


def text_aus(*vorlagen: str, titel: tuple[str, ...] = ()) -> Buchtext:
    return Buchtext.aus(bloecke(*vorlagen) + [Block(kennung=f"9.{i}", kapitel=9, nr=i, art="ueberschrift", vorlage=t)
                                              for i, t in enumerate(titel, 1)])


def test_vorschlaege_der_ki_werden_geprueft():
    text = text_aus("The event loop runs. Each callback waits for the event loop.", "A thread pool helps.")
    roh = {"begriffe": [
        {"englisch": "event loop", "bleibt": True, "deutsch": "", "nur_deutsch": False, "grund": "Fachbegriff, bleibt englisch"},
        {"englisch": "callback", "bleibt": False, "deutsch": "Rückruf", "nur_deutsch": True, "grund": "eingedeutscht"},
        {"englisch": "thread", "bleibt": False, "deutsch": "", "nur_deutsch": False, "grund": "ohne Form"},   # weder bleibt noch Form
        {"englisch": "garbage collector", "bleibt": True, "deutsch": "", "nur_deutsch": False, "grund": "steht nicht im Buch"},
        {"englisch": "Event Loop", "bleibt": True, "deutsch": "", "nur_deutsch": False, "grund": "doppelt"},
        {"englisch": "pool", "bleibt": True, "deutsch": "", "nur_deutsch": False, "grund": "schon da"},
    ]}
    aus = begriffe.vorschlaege_aus(roh, text, vorhanden={"pool"})
    assert [(k.englisch, k.bleibt, k.deutsch, k.stellen, k.herkunft) for k in aus] == [
        ("event loop", True, "", 2, "ki"), ("callback", False, "Rückruf", 1, "ki")]
    with pytest.raises(ValueError):
        begriffe.vorschlaege_aus({"falsch": []}, text, set())


def test_vorschlag_mit_mehreren_formen_und_dem_englischen_wort():
    """Mehrere deutsche Formen mit |, das englische Wort gilt als weitere erlaubte Form, außer die KI verbietet es."""
    text = text_aus("Each directory has a dependency. The garden sensor reads the soil.")
    roh = {"begriffe": [
        {"englisch": "dependency", "bleibt": False, "deutsch": "Abhängigkeit | Dependency", "nur_deutsch": False, "grund": "üblich"},
        {"englisch": "directory", "bleibt": False, "deutsch": "Verzeichnis", "nur_deutsch": True, "grund": "nur deutsch"},
        {"englisch": "garden sensor", "bleibt": False, "deutsch": "Gartensensor", "grund": "ohne Angabe: englisch erlaubt"},
    ]}
    aus = {k.englisch: k.deutsch for k in begriffe.vorschlaege_aus(roh, text, set())}
    assert aus == {"dependency": "Abhängigkeit | Dependency", "directory": "Verzeichnis", "garden sensor": "Gartensensor | garden sensor"}


def test_vorschlag_ohne_deutsche_form_fuer_fachwoerter_die_englisch_bleiben_und_ohne_ueberschriften():
    """Fachwörter, die im deutschen Fachtext englisch bleiben (Paging, Cache), bekommen keine deutsche Form; eine Überschrift
    ist kein Begriff."""
    text = text_aus("Paging maps pages. The paging structures and the cache stay small. A cache line helps.",
                    titel=("Sensor Basics for Garden Robots", "Paging"))
    im_fach = frozenset({"paging", "cache"})
    roh = {"begriffe": [
        {"englisch": "paging", "bleibt": False, "deutsch": "Seitenverwaltung", "nur_deutsch": False, "grund": "deutsch"},
        {"englisch": "paging structures", "bleibt": False, "deutsch": "Paging-Strukturen", "nur_deutsch": False, "grund": "üblich"},
        {"englisch": "cache line", "bleibt": False, "deutsch": "Zwischenspeicherzeile", "nur_deutsch": False, "grund": "deutsch"},
        {"englisch": "Sensor Basics for Garden Robots", "bleibt": False, "deutsch": "Sensorgrundlagen", "nur_deutsch": False,
         "grund": "Überschrift"},
    ]}
    aus = begriffe.vorschlaege_aus(roh, text, set(), im_fach=im_fach)
    assert [k.englisch for k in aus] == ["paging structures"]
    assert begriffe.verstoss(Kandidat(englisch="caches", bleibt=False, deutsch="Zwischenspeicher"), text, frozenset(), im_fach) == (
        "Cache bleibt im deutschen Fachtext gebräuchlich englisch")
    assert begriffe.verstoss(Kandidat(englisch="caches", bleibt=False, deutsch="Caches | Zwischenspeicher"), text, frozenset(), im_fach) == ""
    vorschlag = anweisungen.begriffe(60)
    assert "Cache, Interrupt, Thread, Exception als Fachwort" in vorschlag and "Überschriften und Titel sind keine Begriffe" in vorschlag


def test_fragwuerdige_eintraege_nach_den_regeln_von_heute():
    """Bestehende Einträge von Regel und KI, die die Regeln nicht mehr bestehen, sind fragwürdig, mit Grund; Einträge von Hand
    und gute Einträge nicht."""
    text = text_aus("We trust Rainbox here. Then Rainbox rests. All of it uses Rainbox.", "Paging maps pages fast.",
                    "<t1>2.2 Sorting and Watering</t1>", "<t1>2.3 Sorting by Size</t1>", "<t1>2.4 Sorting Again</t1>",
                    titel=("Sorting Basics", "Garden Robot Fundamentals"))
    eintraege = [Kandidat(englisch="Rainbox", herkunft="regel"), Kandidat(englisch="Sorting", herkunft="regel"),
                 Kandidat(englisch="Fundamentals", herkunft="regel"),
                 Kandidat(englisch="paging", bleibt=False, deutsch="Seitenverwaltung", herkunft="ki"),
                 Kandidat(englisch="Garden Robot Fundamentals", bleibt=False, deutsch="Grundlagen der Gartenroboter", herkunft="ki"),
                 Kandidat(englisch="basics", bleibt=True, herkunft="ki"), Kandidat(englisch="pages", bleibt=False, deutsch="Seiten", herkunft="ki")]
    assert begriffe.fragwuerdig(eintraege, text, frozenset({"basics", "fundamentals"}), frozenset({"paging"})) == {
        "sorting": begriffe.GRUND_KEIN_NAME, "fundamentals": begriffe.GRUND_ALLTAG,
        "paging": "Paging bleibt im deutschen Fachtext gebräuchlich englisch",
        "garden robot fundamentals": begriffe.GRUND_UEBERSCHRIFT, "basics": begriffe.GRUND_ALLTAG}


def test_vorschlag_bleibt_englisch_nie_fuer_alltagswoerter():
    """Gewöhnliche Wörter werden übersetzt: "bleibt englisch" aus lauter Alltagswörtern wird verworfen, mit deutscher Form
    oder als Fachbegriff bleibt der Vorschlag."""
    text = text_aus("Garden Basics and Fundamentals", "The event loop and the Getting Started guide.", "Read the fundamentals twice.",
                    "Learn the basics first.")
    alltag = frozenset({"fundamental", "fundamentals", "basics", "guide", "getting", "started"})
    roh = {"begriffe": [
        {"englisch": "Fundamentals", "bleibt": True, "deutsch": "", "grund": "Überschrift"},
        {"englisch": "Getting Started", "bleibt": True, "deutsch": "", "grund": "Überschrift"},
        {"englisch": "basics", "bleibt": False, "deutsch": "Grundlagen", "grund": "übersetzt"},
        {"englisch": "event loop", "bleibt": True, "deutsch": "", "grund": "Fachbegriff"},
    ]}
    aus = begriffe.vorschlaege_aus(roh, text, vorhanden=set(), alltag=alltag)
    assert [(k.englisch, k.bleibt) for k in aus] == [("basics", False), ("event loop", True)]
    assert "Gewöhnliche Wörter werden übersetzt" in anweisungen.begriffe(60)


def test_buch_ueberschreibt_die_liste_fuer_alle():
    allgemein = [Begriff(englisch="thread", deutsch="Faden"), Begriff(englisch="feet", deutsch="Fuß", art="einheit")]
    buch = [Begriff(englisch="Thread", bleibt=True)]
    assert begriffe.gelten(allgemein, buch) == [Begriff(englisch="Thread", bleibt=True), Begriff(englisch="feet", deutsch="Fuß", art="einheit")]
    assert begriffe.stellen("thread", ["Threads and a thread.", "No threading here."]) == 2
