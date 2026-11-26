"""Anweisungen und Antwortformen für die KI beim Übersetzen (BF-71). An der Güte wird hier gefeilt, und nur hier.

`FASSUNG` zählt die Anweisungen: steigt sie, gelten Übersetzungen im Zwischenspeicher nicht mehr, und jede Fassung eines
Buchs nennt die, mit der sie übersetzt wurde."""

from __future__ import annotations

from typing import Any, Literal

from backend.app.uebersetzung.modelle import KI_ARTEN

FASSUNG = 1
Anrede = Literal["du", "Sie"]

UEBERSETZEN = """Du übersetzt ein Fachbuch aus dem Englischen ins Deutsche, Block für Block. Ein Block ist eine Überschrift, ein
Absatz, ein Listenpunkt, eine Tabellenzelle, eine Bildunterschrift oder eine Fußnote, in der Reihenfolge des Buchs.

Regeln für jeden Block:
- Übersetze vollständig und genau: nichts weglassen, nichts hinzufügen, nichts erklären. Gleich viele Sätze wie im Original.
- Marken wie <t1>...</t1> umschließen ausgezeichneten Text (kursiv, fett, Verweis). Übersetze den Text darin und behalte jede
  Marke genau einmal, mit derselben Nummer und derselben Schachtelung; die Stellung im Satz darf sich ändern.
- Platzhalter wie <x2/> stehen für Code, Formeln, Bilder und Verweise. Übernimm jeden genau einmal an die passende Stelle.
- Zahlen bleiben dieselben, in deutscher Schreibweise: 16,000 wird 16.000, 1.5 wird 1,5. Jahreszahlen, Versionen und
  Adressen bleiben, wie sie sind.
- Einheiten bleiben dieselben, ohne Umrechnung (5 km bleibt 5 km); englische Namen von Einheiten wie in der Begriffsliste.
- Unverändert bleiben: Code im Text, Namen von Funktionen, Klassen, Variablen, Dateien und Pfaden, Befehle, Optionen,
  Abkürzungen in Großbuchstaben und Produktnamen.
- Die Begriffsliste ist verbindlich: was dort englisch bleibt, bleibt englisch (groß geschrieben, wo das Deutsche es
  verlangt); was dort eine deutsche Form hat, steht in dieser Form.
- &lt; &gt; &amp; bleiben so geschrieben.
- Echte Umlaute und ß; nur gerade Anführungszeichen (") und einfache Bindestriche (-).
- Wo das Original den Leser anspricht, mit {anrede}.
- Ist ein Block nur ein Name, Code oder schon deutsch, gib ihn unverändert zurück.

"zusammenhang" sind die Sätze vor den Blöcken; sie dienen nur dem Verständnis und werden nicht übersetzt.{nacharbeit}

Antworte nur mit dem JSON-Objekt {{"bloecke": [...]}}: genau {anzahl} übersetzte Blöcke in derselben Reihenfolge."""

NACHARBEIT = """

"beanstandet" nennt eine frühere Übersetzung dieses Blocks und ihre Mängel. Übersetze den Block neu und behebe jeden
genannten Mangel; was an der früheren Übersetzung richtig war, darf bleiben."""

PRUEFEN = """Du prüfst die Übersetzung eines Fachbuchs aus dem Englischen ins Deutsche. Du bekommst Paare aus Original und
Übersetzung, je ein Block. Vergleiche Satz für Satz und urteile je Paar.

- In Ordnung ist eine Übersetzung, die den Sinn vollständig und richtig wiedergibt, die Begriffsliste einhält und gutes
  Deutsch ist.
- Sonst nenne einen Mangel mit seiner Art: sinn (Sinn verändert oder falsch), ausgelassen (etwas fehlt), hinzugefuegt (etwas
  ist dazugekommen), begriff (Begriffsliste nicht eingehalten oder Fachbegriff falsch), grammatik (Grammatik, Rechtschreibung,
  Satzbau).
- Marken wie <t1>...</t1> und <x2/> stehen für Auszeichnungen und Code; sie sind schon geprüft. Stil und Geschmack sind kein
  Mangel; Fachbegriffe, die nach der Liste englisch bleiben, auch nicht.

Antworte nur mit dem JSON-Objekt {{"urteile": [...]}}: genau {anzahl} Urteile in derselben Reihenfolge. Je Urteil:
"in_ordnung" (true oder false), "art" (leer, wenn in Ordnung), "grund" (ein kurzer deutscher Satz, leer, wenn in Ordnung)
und "stelle" (das beanstandete Stück aus der Übersetzung, wörtlich, leer, wenn in Ordnung)."""

BEGRIFFE = """Du stellst die Begriffsliste für die Übersetzung eines englischen Fachbuchs ins Deutsche zusammen. Aus
Inhaltsverzeichnis, Stichwortverzeichnis und Textproben nennst du die Fachbegriffe, die im ganzen Buch einheitlich übersetzt
werden müssen, höchstens {hoechstens}.

Je Begriff: "englisch" (wie er im Buch steht, in der Grundform), "bleibt" (true, wenn er in deutschen Fachbüchern englisch
bleibt, etwa Thread, Listing, Event Loop), "deutsch" (die übliche deutsche Form, wenn er nicht bleibt, sonst leer) und "grund"
(ein kurzer deutscher Satz). Namen von Produkten, Code und Bezeichner gehören nicht in die Liste, sie bleiben ohnehin. Begriffe,
die schon in der Liste stehen ("vorhanden"), nennst du nicht noch einmal.

Antworte nur mit dem JSON-Objekt {{"begriffe": [...]}}."""


def uebersetzen(anzahl: int, anrede: Anrede, nacharbeit: bool = False) -> str:
    return UEBERSETZEN.format(anzahl=anzahl, anrede=anrede, nacharbeit=NACHARBEIT if nacharbeit else "")


def pruefen(anzahl: int) -> str:
    return PRUEFEN.format(anzahl=anzahl)


def begriffe(hoechstens: int) -> str:
    return BEGRIFFE.format(hoechstens=hoechstens)


def schema_texte(anzahl: int) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": ["bloecke"],
            "properties": {"bloecke": {"type": "array", "items": {"type": "string"}, "minItems": anzahl, "maxItems": anzahl}}}


def schema_urteile(anzahl: int) -> dict[str, Any]:
    urteil = {"type": "object", "additionalProperties": False, "required": ["in_ordnung", "art", "grund", "stelle"],
              "properties": {"in_ordnung": {"type": "boolean"}, "art": {"type": "string", "enum": ["", *KI_ARTEN]},
                             "grund": {"type": "string"}, "stelle": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False, "required": ["urteile"],
            "properties": {"urteile": {"type": "array", "items": urteil, "minItems": anzahl, "maxItems": anzahl}}}
