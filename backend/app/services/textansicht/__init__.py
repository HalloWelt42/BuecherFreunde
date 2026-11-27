"""Textansicht eines PDF: jede Seite als Folge von Bausteinen zum Lesen am Telefon, statt fester Zeilen.

Gelesen wird direkt aus der PDF-Datei (Textschicht ohne Ligaturen, auch falsch abgebildete, services/pdfseite.py), in
Lesereihenfolge von oben nach unten:
- Zeilen: was in einem Block der Textschicht auf einer Grundlinie steht, ist eine Zeile (auch wenn die Textschicht sie bei
  Blocksatz in Stücke teilt). Die Blöcke selbst zählen nicht: viele PDF (aus E-Books gedruckt) legen jede Zeile als eigenen
  Block ab.
- Absätze (BF-103): Zeilen derselben Spalte gehören zusammen, solange kein echter Absatz beginnt. Die nächste Zeile steht
  in derselben Schrift gleich darunter (höchstens ENG mal der übliche Zeilenabstand der Seite), beginnt nicht weiter
  eingerückt als die vorige und nicht mit einem Aufzählungszeichen, und die vorige war voll (ihr fehlte der Platz für das
  erste Wort der nächsten) oder endet mit einer Trennung. Hängend eingerückt nach einer vollen ersten Zeile mitten im Satz
  geht der Absatz weiter (Fußnoten), ebenso die Folgezeilen eines Listenpunkts. Festbreite mitten im Satz (Code im Text, an
  den Zeilenanfang umbrochen) gehört zum Absatz.
- Trennung am Zeilenende: "dage-" + "gen" wird "dagegen". Der Bindestrich bleibt vor einem Großbuchstaben ("Caret-" +
  "Zeichen"), nach einer Ziffer oder Abkürzung ("UTF-" + "8", "HTML-" + "basiert") und wenn die Seite das Wort sonst mit
  Bindestrich schreibt; Wörter werden nie erfunden.
- Über den Seitenwechsel (`seiten_lesen`): endet eine Seite mit einem Absatz mitten im Satz (ohne Satzzeichen am Ende) und
  beginnt die nächste mit einem Absatz, steht der Absatz ganz am Anfang der nächsten Seite. So bleibt der Text jeder Seite
  bei ihr, und jede Seite lässt sich für sich laden (es zählen nur die Nachbarseiten). Eine Seite, die nur aus diesem einen
  Absatz besteht, gibt ihn nicht weiter (sonst hinge eine Seite an beliebig vielen davor).
- Überschriften: Absätze in deutlich größerer Schrift als der Fließtext.
- Bildunterschriften: Absätze, die mit "Abbildung", "Abb." oder "Tabelle" beginnen.
- Code: Zeilen in Festbreitenschrift (nach dem Namen der Schrift) bleiben Zeilen, als Baustein "code" (die Erkennung der
  Codestellen übernimmt ihn als Stelle, codestellen/erkennung.py; bis dahin ohne Kennung); ebenso
  der Text einer Tafel, die Code trägt (siehe unten), und Code, den das Buch wie Fließtext setzt: ein Lauf einzelner Zeilen
  ohne Satz, von denen mindestens die Hälfte nach Code aussieht (Zuweisung, Aufruf, Klammern, "else:"). Einrückung aus der
  Lage, Leerzeilen höchstens LEERZEILEN_HOECHSTENS. Gedruckte Zeilennummern nimmt die Codestelle selbst ab
  (codestellen/modelle.py); hier bleibt eine Zahl am Zeilenanfang Code ("7 ** 2").
- Tafeln: eine Fläche nur aus Rechtecken und geraden Linien (Hintergrund, Bänder, Rahmen), ohne Bild, auf deren Füllung
  Zeilen untereinander stehen. Trägt sie Festbreite oder kurze Zeilen mit Zeichen des Codes und keinen Fließtext, ist sie
  Code; mit Fließtext ein Kasten; nur mit großer Schrift (ein Band hinter einer Überschrift) bleibt ihr Text Text. Ein
  Zierstück ohne Text darauf (Schieber, Symbol) gehört zur Tafel.
- Abbildungen: Rasterbilder und Zeichnungen (nahe beieinander liegende Linien und Flächen, samt ihrer kurzen
  Beschriftungen) werden als Ausschnitt der Originalseite gezeigt; die Oberfläche holt ihn über den Bild-Endpunkt. Der
  Ausschnitt liegt eng um den Inhalt: Rand in der Farbe des Hintergrunds und ein dünner Rahmen ringsum fallen weg, gemessen
  an einem kleinen Bild des Ausschnitts; das Seitenverhältnis des Bausteins ist das des ausgelieferten Bilds. Zeichnungen
  zählen auf die Seite beschnitten (ein Kasten über den Seitenwechsel); ohne Text ist eine solche, die über den Rand geht,
  nur das Ende eines Kastens, und eine Fläche, die nur erkannte Codestellen trägt, ihr Hintergrund: beides keine Abbildung.
- Kästen: eine Zeichnung, die einen längeren Text umrahmt ("Merke", "Fachbegriff"), bleibt Text, als Kasten mit
  seinem Titel (einzeilig, auf oder knapp über dem Rahmen).
- Abgesetzte Formeln (mittig, mit mathematischen Schriftzeichen) zerfallen als Text; sie werden wie Abbildungen als
  Ausschnitt gezeigt, auch innerhalb eines Kastens.
- Hochgestellte Ziffern im Fließtext werden zu Hochzahlen ("m/s2" wird "m/s" mit hochgestellter 2).
- Kopf- und Fußzeilen (Zeilen im oberen und unteren Rand) fallen weg.
- Codestellen (BF-29, erkannt in codestellen/): wo die Erkennung ein Listing gefunden hat, steht ein Baustein "code" mit
  den Zeilen dieses Teils, der Sprache, der Kennung der Stelle und der Nummer des Teils, statt Text und Ausschnitt.
  Alles im Kasten (Kastentitel, Zeilennummern, Rahmen) gehört dazu. Ohne erkannte Codestellen bleibt die Seite, wie sie war.

Seiten ohne lesbaren Text (Scan ohne Textschicht, oder eine Schrift ohne Zeichenzuordnung, die nur Steuer- und
Sonderzeichen liefert) tragen keine Textbausteine; die Oberfläche weist dann auf die Originalansicht hin.

Die Abbildungen einer Seite entstehen bei jedem Aufruf gleich aus `seitenaufbau`; der Bild-Endpunkt nutzt dieselbe
Funktion, damit Nummer und Ausschnitt immer zusammenpassen.

Aufbau: zeilen.py (Zeilen, Maße der Seite, Absätze, Trennung), code.py (Tafeln, Festbreite, lose Codezeilen), zuschnitt.py
(Ausschnitt der Abbildungen), aufbau.py (die Seite aus allem, Seitenwechsel, Lesen und Bild-Endpunkt), modelle.py.
"""

from backend.app.services.textansicht.aufbau import abbildung_png, abbildungen, seiten_lesen, seitenaufbau, ueber_seitenwechsel
from backend.app.services.textansicht.modelle import Baustein, Codeteil
from backend.app.services.textansicht.zeilen import lesbar, verbinde

__all__ = ["Baustein", "Codeteil", "abbildung_png", "abbildungen", "lesbar", "seiten_lesen", "seitenaufbau",
           "ueber_seitenwechsel", "verbinde"]
