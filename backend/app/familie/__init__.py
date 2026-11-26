"""Familie mit Profilen und Kinderzugang (BF-78, docs/neubau/FAMILIE.md).

Ein Konto meldet das Gerät an (core/anmeldung.py), darin wählt man ein Profil (`profile`, `sitzung`, `pin`, `geraet`). Was ein
Profil darf, ergibt sich aus Rolle und Stufe (`stufen.json`, `stufen`, `rechte`); welche Bücher es sieht, entscheidet `sichtbar`.
Persönliche Daten hängen am Profil (`schema`, `umbau`). Für Kinder: Freigaben, Lesezeit, Einblick der Eltern, die Katze."""
