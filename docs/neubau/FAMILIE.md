# Familie und Kinder (BF-78): Entscheidungen

BücherFreunde wird familienfreundlich: mehrere Personen teilen eine Bibliothek, jede mit eigenem Profil, und Kinder
bekommen einen kindgerechten, deutlich einfacheren Zugang, der aufs Lesen reduziert ist und mit dem Alter mitwächst.
Grundlage ist eine Recherche zu Gestaltung, Lesehilfen, Altersangaben, Freigaben, Datenschutz und KI für Kinder (Anhang
an der Karte BF-78). Vor dem Bau kommt ein Entwurf zur Abnahme.

## Entscheidungen (26.11.2026, im Gespräch geklärt)

| Frage | Entscheidung |
|---|---|
| Anmeldung | Profile in der App: ein Konto meldet das Gerät an, darin Profile je Person mit eigenem Lesestand, Notizen, Favoriten und Sternen; geht auch ohne Kellerwolke |
| Bibliothek | gemeinsam für alle Erwachsenen; jedes Profil kann einzelne Bücher als privat markieren, die sieht dann nur es selbst |
| Verwalten | Rollen je Profil: Verwaltung (alles, auch Profile und Einstellungen), Erwachsen (lesen, eigene Notizen, Bücher hinzufügen, für eigene Kinder freigeben; nicht löschen, keine Einstellungen), Kind (was die Stufe erlaubt) |
| Geräte | Profilwahl mit Bildern beim Start; Erwachsene mit PIN, auch Kinder mit einer Bild-PIN (drei Bilder antippen); ein Gerät lässt sich fest auf ein Kind stellen, verlassen nur mit Eltern-PIN |
| Stufe | die Eltern stellen sie ein, aus dem Geburtsjahr kommt ein Vorschlag; Lesehilfen getrennt je Kind |
| Stufen | fünf: Vorlesen (bis 6), Erstes Lesen (Klasse 1 und 2), Lesen und Lernen (Klasse 3 und 4), Schule (ab 10), Jugend (ab 14) |
| Freigabe | einzelne Bücher oder ganze Kategorien; die Altersangabe aus den Quellen steht als Hilfe mit Herkunft und lässt sich überschreiben; nichts geht von selbst frei |
| Lesezeit | je Kind Tageszeit und Ruhezeiten, vorbelegt nach der Leitlinie (3 bis 6 Jahre bis 30 Minuten, 6 bis 9 bis 45, 9 bis 12 bis 60, eine Stunde vor dem Schlafen aus), frei änderbar oder ganz aus; Vorlesen zählt mit, wenn eingestellt; sanfter Hinweis statt Abbruch mitten im Satz |
| Einblick der Eltern | abgestuft und für das Kind sichtbar: bis Klasse 4 Titel, Lesezeit, Fortschritt; ab 10 nur Titel und grober Fortschritt, Notizen und Markierungen privat; ab 14 nur, was das Kind teilt |
| KI | keine KI für Kinder |
| Wunschliste | keine; das Kind fragt die Eltern selbst |
| Belohnung | nur ein ruhiger Rückblick: Regal "Gelesen" mit den Umschlägen, ohne Punkte, Abzeichen, Serien oder Mitteilungen |
| Lesehilfen | Vorlesen mit Mitlesen (Tempo von den Eltern einstellbar), farbige Silben (je Kind, Vorgabe aus), Lesezeile, Kinderschrift mit großen Abständen und kurzen Zeilen (Größe nach Stufe, je Kind änderbar) |
| Funktionen | mit der Stufe wachsend: Vorlesen und Erstes Lesen nur Lesen, Vorlesen, ein Lesezeichen; Lesen und Lernen dazu Suche im eigenen Regal und Favoriten; Schule dazu private Markierungen und Notizen; Jugend wie Erwachsene im freigegebenen Bestand, ohne Verwalten |
| Gestaltung | eigene, deutlich kindgerechte Gestaltung; der Aufbau der Seiten deutlich einfacher (wenige große Flächen statt Seitenleiste, Kopf und Werkzeugzeilen) |
| Katze | die eigene Katze samtpfote (github.com/HalloWelt42/samtpfote) als Begleiterin im Kinderbereich: bei der Profilwahl und im Kinderregal, knuddeln; beim Lesen schläft sie leise in der Ecke; in der Ruhezeit schläft sie mit. Je Kind an oder aus, Schnurren nur auf Wunsch, ohne KI. Die Nennung "hallowelt42 / samtpfote" ist sichtbar |

Selbst festgelegt, wo es keine echte Wahl gab: Vergisst ein Erwachsener seine PIN, setzt die Verwaltung sie zurück; die
PIN der Verwaltung setzt eine erneute Anmeldung mit dem Konto des Geräts zurück. Lesestand, Notizen, Favoriten und Sterne
von heute gehören nach dem Umbau dem ersten Profil (Verwaltung). Kein Kinderprofil schickt Daten an fremde Dienste.

## Gestaltung nach der Recherche

| Was | Wert |
|---|---|
| Schrift am Anfang | 24 bis 18 pt (etwa 32 bis 24 px), anfangs fett, serifenlos, einstöckiges a und g |
| Schrift 7 bis 9 Jahre | x-Höhe 4,2 bis 5,0 mm, nie unter 3,3 mm |
| Zeilen am Anfang | 4 bis 6 Wörter je Zeile, Flattersatz, Umbruch nach Sinnschritten |
| Zeilen später | höchstens 80 Zeichen, Zeilenabstand 1,5, Abstände einstellbar (Absatz 2, Buchstabe 0,12, Wort 0,16 der Schriftgröße) |
| Tippflächen | für kleine Kinder 2 x 2 cm, sonst mindestens 44 x 44 px |
| Kontrast | mindestens 4,5 zu 1, Text besser 7 zu 1 |
| Bedienung | Symbole statt Text, immer sichtbar, Rückmeldung mit Bild und Ton, Fehler zeigen statt schreiben |
| Nicht | Spiele im Buch, Punkte, Serien, Push-Hinweise, Werbung, Verweise nach außen ohne Elternhürde |

## Reihenfolge

1. Entwurf zur Abnahme: Profilwahl mit Bild-PIN, Kinderregal und Lesen in Stufe Vorlesen und Lesen und Lernen
   nebeneinander, Elternbereich (Profile, Stufen, Freigaben, Lesezeit, Einblick), die Katze.
2. Datenmodell: Profile, Rollen, Daten je Profil (Lesestand, Notizen, Markierungen, Etiketten, Favoriten, Sterne,
   Vorlesestelle), private Bücher, Freigaben; Umzug der heutigen Daten ins erste Profil.
3. Profilwahl, Rollen und Rechte im Server (jeder Weg prüft das Profil).
4. Kinderbereich nach Entwurf, Lesehilfen, Lesezeit, Einblick, die Katze.
5. Tests je Rolle und Stufe, Ausrollen, Prüfung im Betrieb mit eigenen Probeprofilen.
