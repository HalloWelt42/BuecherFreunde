"""Vorlesen über die Vertonung (BF-14, docs/neubau/STIMMEN.md): die eine Stelle, an der BücherFreunde spricht. Die Vertonung hält
die Stimmen samt ihren Freigaben (privat, fremd, eingebaut) und spricht auch Klonstimmen; BücherFreunde ruft sie mit dem
App-Zugang der Kellerwolke über den Verbund des Appkerns.

- `zugang.py`: Adresse und Verbund (`appkern.verbund`), ob die Vertonung bereit ist.
- `modelle.py`: Stimmen, Bereiche, Beschreibung der Einstellungen, Form der Stimmwerte.
- `stimmen.py`: die Stimmen je Aufruf aus der Vertonung, mit Bereichen und dem Hinweis zur Freigabe privater Stimmen.
- `sprechen.py`: der Strom Satz für Satz (Vorlesen) und ein kurzer Text als Ton (feste Ansagen, Probe).
- `beschreibung.py`: was die Vertonung zum Sprechen anbietet (Tempo, Sprache und mehr), mit deutschen Namen aus
  `beschriftungen.json`.

Ohne Vertonung bleibt nur die Stimme des Geräts, als ausdrückliche Wahl; die spricht die Oberfläche selbst."""
