# Lücken in Sammlungen (BF-75)

Nutzerwunsch: BücherFreunde erkennt fehlende Bände in Sammlungen, schlägt vor, wie man sie besorgt, und nimmt neue Bücher
gezielt in eine Lücke oder als Stapel in eine Sammlung auf.

## Entscheidungen (26.11.2026, im Gespräch geklärt)

1. **Anzeige: Platzhalter im Regal.** Im Regal der Sammlung steht an der Stelle des fehlenden Bands ein blasser Umschlag
   mit der Nummer ("Band 7 fehlt"). Ein Tipp darauf zeigt den Suchvorschlag und das Hochladen.
2. **Zählung je Sprache getrennt.** Jede Sprache hat ihre eigene Zählung, weil Ausgaben anders teilen (Beispiel: eine
   Reihe mit 15 Bänden im Original und 37 in der deutschen Ausgabe). Im Regal stehen die Sprachen als eigene Reihen. Die
   Zählung beginnt bei 1.
3. **Reihenende aus den Quellen, änderbar.** Die Gesamtzahl der Bände je Sprache kommt aus den Quellen, schonend einmal je
   Sammlung abgefragt. Wissen die Quellen sie nicht, trägt der Nutzer sie ein; eine eigene Angabe gewinnt immer. Ohne Zahl
   gelten nur Lücken zwischen dem ersten und dem letzten vorhandenen Band.
4. **Besorgen: Angaben, Kopieren, Suchadresse.** Zum fehlenden Band Titel, Autor, Nummer und ISBN aus den Quellen, soweit
   bekannt, eine Taste zum Kopieren und eine Taste "Suchen" mit einer Suchadresse aus den Einstellungen (Vorlage mit
   Platzhaltern für Titel, Autor, ISBN). Ohne eingetragene Adresse gibt es nur Kopieren.
5. **Ausblenden je Band und je Sammlung.** Am Platzhalter "Gibt es nicht" oder "Brauche ich nicht", dann verschwindet er.
   Zusätzlich lassen sich die Platzhalter einer ganzen Sammlung abschalten. Beides ist jederzeit zurückholbar.
6. **Hochladen über die Vorschau.** Eine Datei auf den Platzhalter ziehen oder ihn antippen, auch mehrere Dateien oder eine
   ZIP auf die Sammlung. Vor dem Übernehmen zeigt die Vorschau aus BF-80 je Datei Sammlung, Band, Sprache und Doppel,
   änderbar. Widersprechen die Angaben der Datei der Lücke (anderer Titel, andere Sprache), steht ein Hinweis dabei. Erst
   die Bestätigung übernimmt. Bei einem Stapel ist die Sammlung gesetzt, die Bände ordnet BücherFreunde nach Titel und
   Nummer zu.
7. **Auch in Sammlungsvorschlägen.** Ein offener Vorschlag zeigt eine kurze Zeile, etwa "vorhanden 1 bis 5 und 8, es
   fehlen 6 und 7", nur aus den eigenen Bandnummern, ohne Abfrage der Quellen. Platzhalter und Suche gibt es erst in der
   angelegten Sammlung.
8. **Gemeinfrei zu haben (BF-98).** Steht der fehlende Band im eigenen Katalog der gemeinfreien Bücher (nur lokal
   abgeglichen, ganzer Titel und Autor), zeigt das Feld "In die Lücke holen" (geholt wie jedes gemeinfreie Buch, dann in der
   Vorschau mit Sammlung, Band und Sprache der Lücke) und "Bei Gemeinfreie Bücher zeigen" (Hinzufügen, Suche gefüllt).

## Offen für den Entwurf

- Gestalt des Platzhalters (blasser Umschlag mit Nummer und Titel, falls bekannt), Reihen je Sprache im Regal, das Feld
  zum fehlenden Band (Angaben, Kopieren, Suchen, Hochladen, Ausblenden), die Einstellung der Suchadresse und der
  Gesamtzahl je Sprache.

## Reihenfolge des Baus

1. BF-80: Vorschau vor dem Übernehmen (Grundlage für das Hochladen in eine Lücke).
2. BF-75: Lücken aus Bandnummer und Sprache, Gesamtzahl aus den Quellen mit eigener Angabe, Platzhalter, Besorgen,
   Ausblenden, Hochladen über die Vorschau, Zeile in den Vorschlägen. Server gebaut (`backend/app/luecken/`,
   `backend/app/quellen/reihen.py`), Wege und Felder in [SCHNITTSTELLE.md](SCHNITTSTELLE.md) (Lücken).
3. Entwurf zur Abnahme vor dem Bau der Oberfläche.

## Was der Server festlegt

- Bandnummern: "3.5" und "3a" sind Zwischenbände hinter Band 3, sie füllen keine Lücke und fehlen nie; "1-2" ist ein
  Doppelband und belegt beide Plätze; Band 0 zählt nicht mit.
- Ein Buch ohne Sprache zählt zur häufigsten Sprache seiner Sammlung.
- Die Zahl der Bände kommt aus den Bibliothekskatalogen: Deutsch aus der Nationalbibliothek, andere Sprachen aus dem
  Verbundkatalog K10plus, je Sammlung und Sprache eine Abfrage im Hintergrund, nie von selbst wiederholt. Gefragt wird nach dem
  Reihennamen, den die Titel dieser Sprache nennen, sonst nach dem Namen der Sammlung. Neben "aus den Quellen" und der eigenen
  Zahl gibt es "keine Zahl" (nur Lücken zwischen vorhandenen Bänden), auch wenn die Quelle eine kennt.
- Ausblenden, Platzhalter und Zahlen gelten für die Sammlung, für alle Profile. Gerechnet wird mit dem, was das Profil sieht.
- Lücken sehen Erwachsene (Fähigkeit `luecken`); keine Stufe eines Kindes hat sie.
