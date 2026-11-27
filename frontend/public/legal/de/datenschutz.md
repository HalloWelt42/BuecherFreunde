# Datenschutz

## Grundsatz

BücherFreunde läuft auf einem Gerät, das du betreibst. Für die Daten verantwortlich ist, wer die App betreibt. Der Urheber der App erhält keine Daten: kein Konto bei ihm, kein Tracking, keine Analytik, keine Telemetrie, keine Werbung, keine Schriften oder Skripte von fremden Rechnern.

## Konten und Profile

- Ein Konto meldet das Gerät an: das Konto der Kellerwolke, mit Kennwort oder als mit einem Code gekoppeltes Gerät, oder ohne Kellerwolke ein eigenes Konto der App. Kennwörter eigener Konten liegen nur als scrypt-Wert vor, Sitzungen nur als Prüfsumme.
- Im Konto gibt es Profile je Person mit Name, Zeichen, Farbe, Rolle, Stufe und Geburtsjahr (aus ihm kommt ein Vorschlag für die Stufe). PIN und Bild-PIN liegen nur als scrypt-Wert vor.
- Je Profil speichert die App Lesestand, Vorlesestelle, Notizen, Markierungen, Etiketten, Favoriten, Sterne, private Bücher und Einstellungen, bei Kindern dazu die Lesezeit je Tag und den Namen ihrer Katze.

## Wo die Daten liegen

| Ort | Inhalt |
|---|---|
| Gerät, Bestand | Datenbank mit Angaben zu Büchern, Regalen, Sammlungen, eigenen Konten, Profilen, allem Persönlichen je Profil, gemerkten Antworten der Quellen und Einstellungen; Sicherungen der Datenbank, eigene Hintergrundbilder und die Schlüsseldatei der App (nur für den Server lesbar) |
| Gerät, Suche, Volltexte, Umschläge | Suchindex; Volltexte, Seiten und Angaben je Buch, die gesprochenen Ansagen des Kinderbereichs; Umschläge |
| Gerät, Zwischenspeicher | Originale auf Zeit, im Betrieb im Arbeitsspeicher |
| Gerät, Ordner `zugang` | Schlüssel aus der Einrichtung für Kellerwolke und Leitstelle |
| Kellerwolke, `Apps/BücherFreunde` | Originale; je Buch ein Begleiter mit Umschlag, Volltext und Angaben und einer mit dem Persönlichen je Profil (Lesestand, Vorlesestelle, Notizen, Markierungen, Etiketten, privat, Freigaben für Kinder); die Profile ohne PIN; Sicherungen; der Eingangsordner |

Ohne Kellerwolke liegen die Originale auf dem Gerät. Persönliches und Profile gehen nur in die Kellerwolke, solange "Persönliches in der Kellerwolke" eingeschaltet ist, Sicherungen nur, solange `SICHERUNG_IN_KELLERWOLKE` gilt (beides anfangs an).

Der Webserver der Oberfläche schreibt Aufrufe von Seiten mit IP-Adresse, Adresse und Browser in das Protokoll seines Containers, Aufrufe der Schnittstelle nicht. Der Server protokolliert Vorgänge und Fehler.

## Im Browser

- Zwei Cookies, technisch nötig, beide HttpOnly, SameSite=Strict und nur für `/api`: `app_inhalt` trägt die Anmeldung für Bilder, Dateien und Ereignisströme (30 Tage), `bf_profil` das gewählte Profil (bis zum Wechsel, höchstens 400 Tage).
- Im Speicher des Browsers: die Sitzung der Anmeldung, der Schlüssel des gewählten Profils, eine zufällige Kennung des Geräts (für die Bindung an ein Kind), Einstellungen der Darstellung und des Lesens, der Suchverlauf (bis zu 50 Begriffe), die Schnellnotiz und geänderte Kopien von Code aus dem Ausführen.
- Im Vorrat des Browsers: die Hülle der App für den Start ohne Netz. Nur mit "Ohne Netz lesen" (anfangs aus) dazu bis zu fünf zuletzt geöffnete Bücher mit Angaben, Datei, Markierungen, Notizen und Etiketten, zusammen höchstens 500 MB.

## Kinder

- Kinderprofile senden nichts an Dienste außerhalb des Hauses. KI (Assistent, Suche nach Bedeutung, Vorschläge, Übersetzen) und Nachschlagen sind für sie gesperrt. Vorgelesen wird ihnen über die Vertonung im Haus oder mit den Stimmen des Geräts.
- Die Eltern sehen einen Einblick, und das Kind sieht, was sie sehen: in den Stufen Vorlesen, Erstes Lesen und Lesen und Lernen Titel, Lesezeit und Fortschritt; in der Stufe Schule Titel und groben Fortschritt; in der Stufe Jugend nur Bücher, die das Kind teilt, mit Titel und grobem Fortschritt. Notizen und Markierungen zeigt der Einblick nie.
- Ein Gerät lässt sich fest auf ein Kind stellen; die App erkennt es an der zufälligen Kennung seines Browsers. Lösen geht nur mit der PIN der Eltern.

## Dienste im Haus

Nur wenn ihre Adresse eingetragen ist.

| Dienst | Wozu | Was er bekommt |
|---|---|---|
| Kellerwolke | Anmeldung, Ablage, Sicherung | die Anmeldung; Originale, Begleiter, Persönliches, Profile, Sicherungen |
| Leitstelle | KI | Angaben zu Büchern (Titel, Autor, Verlag, Dateiname, Schlagworte, Beschreibung) und den Anfang ihres Textes zum Einordnen und für Vorschläge; auf Wunsch den Text eines Buchs in Teilen (Übersetzen); Code aus Büchern (Vorprüfung) |
| Vertonung | Vorlesen und Ansagen | den Text zum Vorlesen mit der gewählten Stimme; für die Ansagen des Kinderbereichs Buchtitel und die Namen der Profile und der Katze; die Vertonung gibt den Text zum Sprechen an Dienste der Leitstelle weiter |
| Fundus | Suche nach Bedeutung, Bestand für andere Apps im Haus | die Suchfrage; Fundus liest Angaben, Volltexte, Umschläge und Originale, private Bücher nie, Lesestand und Zahl der Notizen nur des ersten Profils der Verwaltung |
| Assistent | Gespräch über eine Stelle im Buch | die Stelle und die Frage; das Gespräch bleibt beim Assistenten |
| Nachschlag | Nachschlagen in Lexika | das Suchwort |
| Codeschmiede | Code aus Büchern ausführen | den Code, auch im Hintergrund zur Vorprüfung |

## Quellen im Netz

Die App fragt sie beim Hinzufügen und Ergänzen von Büchern und Autoren, beim Nachschlagen und bei der Suche nach gemeinfreien Büchern, auch in Läufen im Hintergrund (höchstens `QUELLEN_HINTERGRUND_TAG` Anfragen je Quelle und Tag). Jede Anfrage überträgt die IP-Adresse des Servers und die Kennung "BuecherFreunde/Fassung (self-hosted book library)", dazu den Kontakt aus `QUELLEN_KONTAKT`, wenn du einen einträgst. Antworten merkt sich die App eine Zeit lang, damit sie nicht erneut fragt.

| Quelle | Rechner | Was sie bekommt | abschalten |
|---|---|---|---|
| Google Books, nur mit eigenem Schlüssel | www.googleapis.com, books.google.com | ISBN, Titel, Autor, den Schlüssel | `GOOGLE_BOOKS_ENABLED`, ohne `GOOGLE_BOOKS_API_KEY` nie gefragt |
| Open Library | openlibrary.org, covers.openlibrary.org, archive.org | ISBN, Titel, Autor | `OPENLIBRARY_ENABLED` |
| Deutsche Nationalbibliothek | services.dnb.de | ISBN, Titel, Autor | `DNB_ENABLED` |
| K10plus | sru.k10plus.de | ISBN, Titel, Autor | `K10PLUS_ENABLED` |
| Crossref | api.crossref.org | ISBN, DOI, Titel, Autor | `CROSSREF_ENABLED` |
| Wikipedia und Wikidata | www.wikidata.org, de.wikipedia.org, en.wikipedia.org, commons.wikimedia.org, upload.wikimedia.org, thumb.wikimedia.org | Titel, Autorennamen, Kennungen; ohne Nachschlag auch das Suchwort beim Nachschlagen | `WIKIPEDIA_ENABLED` |
| Gemeinsame Normdatei über lobid.org | lobid.org | Autorennamen | `GND_ENABLED` |
| Project Gutenberg über Gutendex | gutendex.com, gutenberg.pglaf.org, aleph.pglaf.org | Suchbegriffe, Nummer des Buchs | `GUTENBERG_ENABLED` |

## Neue Fassungen

Öffnet ein Profil der Verwaltung die App, fragt der Server bei GitHub (raw.githubusercontent.com) nach der neuesten Fassung. Dabei geht die IP-Adresse des Servers mit. Abschalten lässt sich diese Abfrage nicht.

## Löschen

- Ein Buch löscht die App erst nach einer Vorschau der Folgen. Seine Datei geht in den Papierkorb der Kellerwolke und lässt sich dort zurückholen; liegt sie nur auf dem Gerät, ist sie danach fort. Umschlag, Begleiter und Kopien auf dem Gerät gehen mit.
- Profile löscht die Verwaltung nach einer Vorschau der Folgen; mit dem Profil gehen seine persönlichen Daten in der Datenbank des Geräts.
- Schaltest du "Persönliches in der Kellerwolke" mit Entfernen aus, kommen diese Begleiter in den Papierkorb der Kellerwolke.
- Sicherungen in der Kellerwolke löscht die App nie; dort aufzuräumen bleibt dir. Auf dem Gerät behält sie die jüngsten (`SICHERUNG_BEHALTEN`, anfangs drei).
- Im Browser: Abmelden löscht die Anmeldung samt ihrem Cookie, den Schlüssel des Profils und die Bücher für "Ohne Netz lesen". Das Cookie des Profils, Suchverlauf, Schnellnotiz und die übrigen Werte löschst du in den Einstellungen des Browsers.

## Empfehlungen

- Die App nur im Heimnetz betreiben, von außen nur hinter einem Vorbau mit HTTPS.
- Schlüsseldateien nur für den Server lesbar halten (Modus 0600).
