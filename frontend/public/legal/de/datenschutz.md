# Datenschutz

## Grundsatz

BücherFreunde ist eine selbst gehostete Anwendung. Alle Daten werden ausschließlich lokal auf deinem Server gespeichert. Es gibt keine zentrale Datenerfassung, keine Benutzerkonten und keine Analytik.

## Lokale Datenspeicherung

Folgende Daten werden lokal auf deinem Server gespeichert:

- **Buchdateien** (PDF, EPUB, MOBI, TXT, MD) im Hash-basierten Speicher
- **Metadaten** (Titel, Autor, ISBN, Beschreibung) in der SQLite-Datenbank
- **Nutzerdaten** (Leseposition, Favoriten, Bewertungen, Notizen, Markierungen)
- **Cover-Bilder** als extrahierte oder heruntergeladene JPEG-Dateien
- **Volltexte** für die FTS5-Suchindizierung
- **Konfiguration** in der .env-Datei

Es werden keine Cookies gesetzt. Der API-Token wird nur lokal im Browser (localStorage) gespeichert.

## Externe Verbindungen

BücherFreunde kommuniziert nur in folgenden Fällen mit externen Servern:

| Dienst | URL | Gesendete Daten | Empfangene Daten | Deaktivierbar |
|--------|-----|-----------------|------------------|---------------|
| Open Library | openlibrary.org | ISBN, Titel, Autor | Bibliografische Metadaten | Ja (.env) |
| Google Books | googleapis.com | ISBN, Titel | Metadaten, Cover-URLs | Ja (.env) |
| Wikipedia/Wikidata | wikidata.org | Autorennamen, ISBN | Biografien, Fotos, Werklisten | Ja (.env) |
| Gutendex | gutendex.com | Suchbegriffe | Buchdaten, Dateien | Ja (nicht nutzen) |
| GitHub | raw.githubusercontent.com | Nichts Personenbezogenes | Versionsnummer | Ja (ignorieren) |
| LM Studio | Konfigurierbar | Titel, Autor, Textauszug | Kategorie-Vorschläge | Ja (.env) |

Alle externen Verbindungen können in den Einstellungen oder der `.env`-Datei einzeln deaktiviert werden. Die Anwendung funktioniert vollständig offline.

## Keine Tracking-Mechanismen

BücherFreunde verwendet:

- Keine Cookies
- Kein Tracking
- Keine Analytik
- Keine Telemetrie
- Keine Werbung
- Keine externen Schriften oder CDNs (alle Ressourcen sind lokal gebündelt)

## Datenlöschung

Alle Daten können jederzeit vollständig gelöscht werden:

- **Einzelne Bücher:** Über die Buchdetailseite oder Massenlöschung
- **Gesamte Datenbank:** Durch Löschen der SQLite-Datei
- **Buchdateien:** Durch Löschen des Storage-Verzeichnisses
- **Browser-Daten:** Durch Löschen des localStorage-Eintrags

## Verantwortung

Da BücherFreunde selbst gehostet wird, bist du als Betreiber für den Schutz der auf deinem Server gespeicherten Daten selbst verantwortlich. Empfehlungen:

- Server nur im lokalen Netzwerk betreiben oder hinter VPN/Reverse-Proxy
- Regelmäßige Backups erstellen
- API-Token sicher aufbewahren und bei Bedarf ändern

