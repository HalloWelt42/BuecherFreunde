# Ersteinrichtung nach einer Neuinstallation (BF-82)

Nutzerwunsch: Die Ersteinrichtung nach einer Neuinstallation mitdenken, mit allem, was inzwischen dazugekommen ist
(Familie und Kinder, Stimmen, Katalog, Anschlüsse, Begleitmaterial).

## Grundregel

Die Ersteinrichtung erscheint nur bei einer wirklich neuen Installation: leerer Bestand ohne Markerdatei
(`ablage/orte.py`). Eine laufende Installation sieht sie nie und wird durch sie nie verändert. Unter Einstellungen,
Wartung lässt sich der Assistent später wieder öffnen; er ändert dann nur, was man in ihm ausdrücklich bestätigt, und
löscht nichts.

## Entscheidungen (26.11.2026, im Gespräch geklärt)

1. **Ausgangslagen:** alle vier.
   - Neu beginnen.
   - Aus Sicherung wiederherstellen.
   - Ablage in der Kellerwolke übernehmen (Neuaufbau ohne Sicherung).
   - Umzug von einer anderen Installation.
2. **Form:** geführte Schritte mit Fortschritt. Konto und Speicherorte sind Pflicht, mit Vorschlag. Alles Übrige ist
   überspringbar und steht danach in den Einstellungen.
3. **Schritte beim Neubeginn** neben Konto und Orten:
   - Anschlüsse: Kellerwolke, KI und Sprechdienst über die Leitstelle, Nachschlag. Jeweils Adresse eintragen und
     Verbindung prüfen; ohne sie läuft die App voll.
   - Katalog: mitgelieferter Katalog, leer beginnen oder später aus dem Bestand vorschlagen.
   - Familie und Kinder: allein oder Familie; Profile mit Rolle und PIN, für Kinder Stufe, Freigaben und Stimme der
     Ansagen, dazu die Stimme der Familie.
   - Erste Bücher: Hochladen mit Vorschau (BF-80), Eingangsordner, Ordner auf dem Gerät, gemeinfreie Bücher.
4. **Sicherung:** Sie kommt aus einer hochgeladenen Datei, aus dem Sicherungsordner des Geräts (neueste zuerst) oder aus
   der Kellerwolke. Für die Kellerwolke legt die App ihre Sicherungen künftig auch dort ab (HELF-21).
5. **Persönliches im Auszug:** Notizen, Markierungen, Etiketten, Lesestand und Freigaben stehen zusätzlich je Buch und
   Profil im Auszug in der Kellerwolke, laufend nachgeführt, damit ein Neuaufbau ohne Sicherung sie zurückholt. Wer die
   Kellerwolke verwaltet, könnte sie lesen; das steht im Schritt Anschlüsse dabei.
6. **Schlüssel:** Den Schlüssel für Kellerwolke und Leitstelle fügt man im Assistenten einmal ein. Der Server prüft die
   Verbindung und legt ihn in seiner eigenen Schlüsseldatei ab, die nur er lesen kann. Die Oberfläche zeigt danach nur
   "eingetragen" und "ersetzen", nie den Schlüssel selbst.
7. **Umzug direkt mit Einmalcode:** Auf dem alten Gerät "Umzug vorbereiten" legt eine frische Sicherung an und zeigt
   einen Einmalcode. Im Assistenten des neuen Geräts trägt man Adresse und Code ein, es holt Sicherung und Einstellungen
   direkt. Originale in der Kellerwolke bleiben, wo sie sind. Das alte Gerät bleibt unverändert, bis man es selbst
   abschaltet.
8. **Originale ohne Kellerwolke:** wählbar. Entweder kopiert der Umzug sie als sichtbarer Auftrag (Fortschritt,
   fortsetzbar, mit Prüfsummen), oder man hängt die Platte um und zeigt dem neuen Gerät den Ort; dann prüft es nur, ob
   alles da ist.

## Weitere Regeln

- **Nach dem Wiederherstellen** oder Neuaufbau prüft die App, ob jedes Original erreichbar ist. Fehlende stehen in einem
  Bericht und werden über ihre Prüfsumme in der Kellerwolke gesucht. Es wird nichts gelöscht.
- **Darstellung:** Hell, Dunkel, System und die Schriftgröße sind im Assistenten von Anfang an über das übliche
  Bedienelement im Kopf erreichbar.
- **Abschluss:** eine Übersicht, was eingerichtet und was übersprungen ist, mit Verweisen in die Einstellungen.
- **Handbuch:** Die Ersteinrichtung und jede Ausgangslage stehen im Handbuch.
- **Prüfung nur isoliert** (Vorgabe des Nutzers: "achte darauf, dass du jetzt nicht meinen ist zustand veränderst und
  teste alles nur isoliert"): Getestet wird nur an eigenen Prüfinstallationen mit eigenen Orten, eigener Datenbank und
  eigenen Sicherungen. Für die Kellerwolke dient eine Attrappe oder eine eigene Prüfinstanz. Die echte Datenbank, die
  echte Ablage der Kellerwolke und die Sicherungen des Betriebs fasst kein Test an.

## Reihenfolge des Baus

1. Entwurf zur Abnahme: Ausgangslage, Schritte, Umzug mit Einmalcode, Bericht nach dem Wiederherstellen, Abschluss.
2. Server: Erkennen der neuen Installation, Schritte als Schnittstelle, Schlüsseldatei, Wiederherstellen aus drei
   Quellen, Neuaufbau aus dem Auszug, persönliche Daten im Auszug, Umzug mit Einmalcode, Prüfung der Originale.
3. Oberfläche nach dem Entwurf, Handbuch, Prüfung an Prüfinstallationen.
