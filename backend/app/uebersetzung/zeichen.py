"""Zeichen im deutschen Text (BF-71): gerade Anführungszeichen, einfache Bindestriche, echte Umlaute.

`gerade` macht aus gesetzten Anführungszeichen gerade und aus Gedankenstrichen einfache Bindestriche; das geschieht mit
jeder Übersetzung, bevor sie geprüft wird (vom Modell wie von Hand), denn es ändert nichts am Sinn. `befunde` meldet, was
danach noch stört: gesetzte Zeichen, die `gerade` nicht kennt, ein doppelter Bindestrich im Text und Umlaute, die als ae, oe,
ue geschrieben sind (an den Anfängen häufiger Wörter erkannt, damit "Quelle" oder "neue" nicht auffallen)."""

from __future__ import annotations

import re

GERADE = str.maketrans({
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u00ab": '"', "\u00bb": '"', "\u2033": '"',
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2039": "'", "\u203a": "'", "\u2032": "'",
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2212": "-",
})
GEDANKENSTRICH = re.compile(r"[ \u00a0]*[\u2014\u2015][ \u00a0]*|[ \u00a0]+[\u2013\u2012][ \u00a0]+|[ \u00a0]+--[ \u00a0]+")
GESETZT = re.compile("[\u201c\u201d\u201e\u201f\u00ab\u00bb\u2018\u2019\u201a\u201b\u2039\u203a\u2010-\u2015\u2212]")
DOPPELSTRICH = re.compile(r"(?<=\s)--(?=\s)")
#: Anfänge häufiger Wörter, wie sie mit ae, oe, ue statt Umlaut aussehen
UMLAUT_ERSATZ = re.compile(r"(?<![\w])(?:ueber|fuer|zurueck|rueck|koenn|muess|duerf|wuerd|waehr|waer|haett|groess|aender|natuerl|moeglich|"
                           r"loes|hoeh|frueh|spaet|naechst|laeng|staerk|schluess|pruef|fuehr|ausfuehr|einfueg|hinzufueg|erklaer|zaehl|"
                           r"haeufig|aehnlich|noetig|benoetig|oeffn|schoen|koerper|faell|gefaehr|verfueg|unterstuetz|tatsaech|ueblich|"
                           r"gruend|bestaet|aeusser|aeltest|kuerz|wuensch|grundsaetz)\w*", re.I)


def gerade(text: str) -> str:
    """Gesetzte Anführungszeichen werden gerade, Gedankenstriche ein einfacher Bindestrich mit Leerzeichen."""
    return GEDANKENSTRICH.sub(" - ", text).translate(GERADE)


def befunde(text: str) -> list[tuple[str, str]]:
    """Was an Zeichen stört, je als (Satz, Stelle)."""
    aus: list[tuple[str, str]] = []
    if m := GESETZT.search(text):
        aus.append((f"Gesetztes Zeichen {m.group(0)} statt eines geraden", m.group(0)))
    if DOPPELSTRICH.search(text):
        aus.append(("Doppelter Bindestrich im Text", "--"))
    if m := UMLAUT_ERSATZ.search(text):
        aus.append((f"Umlaut als Ersatz geschrieben: {m.group(0)}", m.group(0)))
    return aus
