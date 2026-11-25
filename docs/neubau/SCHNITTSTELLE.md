# Neue Schnittstellen des Neubaus (BF-7 bis BF-10)

Alle Wege brauchen die Anmeldung (`Authorization: Bearer` oder `X-Kellerwolke-Sitzung`). Bilder, Dateien und Ereignisströme lesen sie aus dem Inhalts-Cookie von `POST /api/anmeldung/zugang`; in Adressen steht sie nie.
Fehler kommen als `{"detail": "deutscher Satz"}`. Die vorhandenen Wege bleiben unverändert.

## Annahme (Hochladen)

Ein Eintrag je Datei:

```
{ "id": 7, "name": "Buch.epub", "groesse": 50541233, "sha256": "...", "empfangen": 31457280, "teil_groesse": 4194304,
  "stand": "laedt", "schritt": 1, "anteil": 0.62, "text": "Wird in der Kellerwolke abgelegt, 30,0 von 48,2 MB",
  "buch_id": null, "angelegt_am": "2026-11-25T21:00:00Z", "geaendert_am": "..." }
```

`stand`: `wartet`, `laedt`, `angehalten`, `liest`, `angaben`, `regal`, `wissen` (in der Bibliothek, Bedeutung folgt),
`fertig`, `ohne_text` (in der Bibliothek, kein Text gefunden), `da` (gibt es schon, `buch_id` gesetzt), `format` (nicht
möglich), `kaputt` (leer oder unlesbar, nicht eingetragen), `fehler` (mit Grund in `text`, erneut möglich).
`schritt` 0 bis 6: Prüfen, Wolke, Lesen, Angaben, Regal, Wissen, alles fertig.

| Weg | Zweck |
|---|---|
| `GET /api/annahme` | `{eintraege: [...], zaehler: {alle, laeuft, klaeren, da, fertig}}`, neueste zuerst |
| `POST /api/annahme` `{name, groesse, sha256}` | anlegen; antwortet sofort mit `da`, `format` oder `kaputt`, wenn nichts hochzuladen ist |
| `PATCH /api/annahme/{id}` Kopf `Upload-Offset`, Körper roh | nächstes Teil; 409 `{detail, empfangen}` nennt den wahren Stand |
| `GET /api/annahme/{id}` | Stand, sagt wo es weitergeht |
| `POST /api/annahme/{id}/erneut` | Auswertung noch einmal |
| `DELETE /api/annahme/{id}` | Eintrag entfernen, laufenden Upload abbrechen; ein eingetragenes Buch bleibt |
| `POST /api/annahme/ausblenden` | fertige und schon vorhandene ausblenden (bleiben im Verlauf) |
| `GET /api/annahme/eingangsordner` | `{bereit, pfad, dateien: [{name, groesse, stand, text, buch_id}]}`, was im Eingangsordner der Kellerwolke liegt |
| `POST /api/annahme/eingangsordner` | jetzt nachsehen, sonst jede Minute; `{neu}` |
| `GET /api/annahme/ereignisse` | Ereignisstrom, je Änderung `data: {eintraege, zaehler}` |

Der Browser rechnet den sha256 stückweise (npm `hash-wasm`), schickt Teile zu `teil_groesse` nacheinander, höchstens zwei
Dateien zugleich, und setzt nach Verbindungsverlust am Stand des Servers fort. Wer die Seite neu lädt, wählt die Datei
erneut; gleicher sha256 und Name findet den angefangenen Eintrag wieder (POST liefert ihn mit `empfangen`).

## Suche nach Bedeutung

`GET /api/suche/bedeutung?q=&n=20&buch=` liefert
`{verfuegbar, grund, treffer: [{buch_id, titel, autor, seite, gedruckt, auszug, naehe: "sehr nah" | "verwandt", wert}]}`.
Ist der Rechner aus, gilt `verfuegbar: false` mit `grund`; die Suche nach Wörtern geht weiter.

## Verbindungen, Orte, Ablage eines Buchs

- `GET /api/verbindungen` -> `[{kennung, name, stand: "gut" | "warn" | "schlecht", text}]` (kellerwolke, fundus, rechner)
- `GET /api/orte` -> `[{kennung, name, pfad, belegt, frei, stand}]` (bestand, suche, texte, umschlaege, zwischen)
- `GET /api/books/{id}/ablage` -> `{wolke: {pfad, groesse, sha256}, volltext: {seiten, zeichen}, wissen: {stand, text}}`
- `GET /api/config/oberflaeche` -> `{assistent: "https://..."}` Adresse des Assistenten für "Im Assistenten fragen"
