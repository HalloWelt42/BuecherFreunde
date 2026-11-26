"""Anweisungen und Antwortformen für die KI beim Übersetzen (BF-71). An der Güte wird hier gefeilt, und nur hier.

`FASSUNG` zählt die Anweisungen: steigt sie, gelten Übersetzungen im Zwischenspeicher nicht mehr, und jede Fassung eines
Buchs nennt die, mit der sie übersetzt wurde."""

from __future__ import annotations

from typing import Any

from backend.app.uebersetzung.modelle import KI_ARTEN, Anrede

FASSUNG = 3
#: die Art, unter der der Prüfer nennen kann, worüber er nicht urteilt; solche Urteile gelten nicht (pruefer.py)
ANDERES = "anderes"

UEBERSETZEN = """Du übersetzt ein Fachbuch aus dem Englischen ins Deutsche, Block für Block. Ein Block ist eine Überschrift, ein
Absatz, ein Listenpunkt, eine Tabellenzelle, eine Bildunterschrift oder eine Fußnote, in der Reihenfolge des Buchs.

Regeln für jeden Block:
- Übersetze vollständig und genau: nichts weglassen, nichts hinzufügen, nichts erklären. Gleich viele Sätze wie im Original.
- Marken wie <t1>...</t1> umschließen ausgezeichneten Text (kursiv, fett, Verweis). Übersetze den Text darin und behalte jede
  Marke genau einmal, mit derselben Nummer und derselben Schachtelung; die Stellung im Satz darf sich ändern. Kommt das
  ausgezeichnete Wort mehrmals vor, trägt nur die Stelle die Marke, die sie im Original trägt.
- Platzhalter wie <x2/> stehen für Code (auch Code in Backticks), Formeln, Bilder und Verweise. Übernimm jeden genau einmal
  an die passende Stelle.
- Setze keine eigenen Marken und keine andere Auszeichnung: nur die Marken und Platzhalter des Originals, keine neuen
  <tN> oder <xN/>, auch nicht um Code, Fachwörter oder Zeichen.
- Der Text steht als Zeichen da: <, > und & außerhalb der Marken sind gewöhnliche Zeichen (etwa "x < 18") und bleiben
  Zeichen; schreibe sie nicht als &lt; &gt; &amp;.
- Zahlen bleiben dieselben, in deutscher Schreibweise: 16,000 wird 16.000, 1.5 wird 1,5. Jahreszahlen, Versionen und
  Adressen bleiben, wie sie sind.
- Einheiten bleiben dieselben, ohne Umrechnung (5 km bleibt 5 km); englische Namen von Einheiten wie in der Begriffsliste.
- Unverändert bleiben: Code im Text, Namen von Funktionen, Klassen, Variablen, Dateien und Pfaden, Befehle, Optionen,
  Abkürzungen in Großbuchstaben (außer die Begriffsliste gibt ihnen eine deutsche Form, etwa AI: KI) und Produktnamen.
- Die Begriffsliste ist verbindlich: was dort englisch bleibt, bleibt englisch (groß geschrieben, wo das Deutsche es
  verlangt); was dort eine deutsche Form hat, steht in dieser Form.
- Echte Umlaute und ß; nur gerade Anführungszeichen (") und einfache Bindestriche (-).
- {anrede}
- Unverändert zurück kommt nur ein Block, der ganz aus einem Namen, aus Code oder aus deutschem Text besteht. Jeder
  englische Satz wird übersetzt, auch neben Code, Platzhaltern, Fachwörtern, Zeichen wie #GP und Strichen.

"zusammenhang" sind die Sätze vor den Blöcken; sie dienen nur dem Verständnis und werden nicht übersetzt.{nacharbeit}{unuebersetzt}

Antworte nur mit dem JSON-Objekt {{"bloecke": [...]}}: genau {anzahl} übersetzte Blöcke in derselben Reihenfolge."""

NACHARBEIT = """

"beanstandet" nennt eine frühere Übersetzung dieses Blocks und ihre Mängel. Übersetze den Block neu und behebe jeden
genannten Mangel; was an der früheren Übersetzung richtig war, darf bleiben."""

UNUEBERSETZT = """

Dieser Block kam eben unverändert englisch zurück. Er ist englischer Text und muss ins Deutsche: übersetze jeden Satz
vollständig. Englisch bleiben nur Code, Platzhalter, Namen und die Begriffe, die die Begriffsliste als "bleibt englisch"
führt. "beanstandet" nennt, falls vorhanden, was am letzten Versuch auffiel."""

PRUEFEN = """Du prüfst die Übersetzung eines Fachbuchs aus dem Englischen ins Deutsche. Du bekommst Paare aus Original und
Übersetzung, je ein Block. Vergleiche Satz für Satz und urteile je Paar nur über den Inhalt.

- Ein Mangel ist nur: sinn (der Sinn ist verändert oder falsch, auch ein Fachwort in falscher Bedeutung), ausgelassen (etwas
  aus dem Original fehlt), hinzugefuegt (etwas steht da, das nicht im Original steht).
- Alles andere prüfen feste Prüfungen, es ist hier kein Mangel: ob Fachbegriffe englisch bleiben oder wie sie übersetzt sind,
  Rechtschreibung, Groß- und Kleinschreibung, Zeichen und Striche, Zahlen, die Anrede (du oder Sie) und der Stil. Fällt dir
  so etwas auf, urteile "in_ordnung" true oder nenne es mit der Art "anderes".
- Marken wie <t1>...</t1> und <x2/> stehen für Auszeichnungen und Code; sie sind schon geprüft.
- Begründe nur mit dem, was im Original steht und in der Übersetzung anders ist, nie mit einer Liste oder Regel.

Antworte nur mit dem JSON-Objekt {{"urteile": [...]}}: genau {anzahl} Urteile in derselben Reihenfolge. Je Urteil:
"in_ordnung" (true oder false), "art" (leer, wenn in Ordnung), "grund" (ein kurzer deutscher Satz, leer, wenn in Ordnung)
und "stelle" (das beanstandete Stück aus der Übersetzung, wörtlich, leer, wenn in Ordnung)."""

BEGRIFFE = """Du stellst die Begriffsliste für die Übersetzung eines englischen Fachbuchs ins Deutsche zusammen. Aus
Inhaltsverzeichnis, Stichwortverzeichnis und Textproben nennst du die Fachbegriffe, die im ganzen Buch einheitlich übersetzt
werden müssen, höchstens {hoechstens}.

Je Begriff: "englisch" (wie er im Buch steht, in der Grundform), "bleibt", "deutsch" (die deutsche Form, wenn er nicht
bleibt, sonst leer), "nur_deutsch" und "grund" (ein kurzer deutscher Satz).

- Fachbegriffe, die im deutschen Fachtext gebräuchlich englisch bleiben, bleiben englisch ("bleibt" true), etwa Paging,
  Cache, Interrupt, Thread, Exception als Fachwort, Listing, Event Loop; ebenso Namen von Produkten, Bibliotheken, Befehlen
  und Dateien (etwa Pygame, pip, setup.py).
- Eine deutsche Form nur, wenn sie im Fach üblich ist (etwa directory: Verzeichnis, dependency: Abhängigkeit). Sind mehrere
  üblich, stehen sie mit | getrennt, die übliche zuerst.
- Neben der deutschen Form ist das englische Wort erlaubt. "nur_deutsch" ist true nur, wenn das englische Wort im deutschen
  Fachtext falsch wäre; sonst false.
- Gewöhnliche Wörter werden übersetzt und gehören nicht in die Liste, auch wenn sie in Überschriften stehen (etwa
  fundamentals, introduction, overview, guide, basics, example, games, reviews).
- Überschriften und Titel sind keine Begriffe (etwa "Introduction to Garden Robots", "Sensor Basics"); ein Begriff ist ein
  Fachwort oder eine feste Wortgruppe aus dem Text.
- Begriffe, die schon in der Liste stehen ("vorhanden"), nennst du nicht noch einmal.

Antworte nur mit dem JSON-Objekt {{"begriffe": [...]}}."""


#: wie der Leser angesprochen wird, je Anrede ein Satz für den Übersetzer
ANREDE: dict[Anrede, str] = {
    "du": 'Sprich den Leser durchgehend mit "du" an (du, dich, dir, dein; Aufforderungen in der du-Form wie "Installiere '
          'Python"), nie mit "Sie", auch wo das Original unpersönlich klingt.',
    "Sie": 'Sprich den Leser durchgehend mit "Sie" an (Sie, Ihnen, Ihr, immer groß; Aufforderungen wie "Installieren Sie '
           'Python"), nie mit "du".',
}


def uebersetzen(anzahl: int, anrede: Anrede, nacharbeit: bool = False, unuebersetzt: bool = False) -> str:
    """Die Anweisung zum Übersetzen; `nacharbeit` mit der früheren Übersetzung und ihren Mängeln, `unuebersetzt` für einen
    Block, der unverändert englisch zurückkam."""
    return UEBERSETZEN.format(anzahl=anzahl, anrede=ANREDE[anrede], nacharbeit=NACHARBEIT if nacharbeit else "",
                              unuebersetzt=UNUEBERSETZT if unuebersetzt else "")


def pruefen(anzahl: int) -> str:
    return PRUEFEN.format(anzahl=anzahl)


def begriffe(hoechstens: int) -> str:
    return BEGRIFFE.format(hoechstens=hoechstens)


def schema_texte(anzahl: int) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": ["bloecke"],
            "properties": {"bloecke": {"type": "array", "items": {"type": "string"}, "minItems": anzahl, "maxItems": anzahl}}}


def schema_urteile(anzahl: int) -> dict[str, Any]:
    urteil = {"type": "object", "additionalProperties": False, "required": ["in_ordnung", "art", "grund", "stelle"],
              "properties": {"in_ordnung": {"type": "boolean"}, "art": {"type": "string", "enum": ["", *KI_ARTEN, ANDERES]},
                             "grund": {"type": "string"}, "stelle": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False, "required": ["urteile"],
            "properties": {"urteile": {"type": "array", "items": urteil, "minItems": anzahl, "maxItems": anzahl}}}
