#!/usr/bin/env bash
# Legt die Orte aus der .env an (Vorgabe: daten/ neben dem Programm), baut die Abbilder und startet die Container.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[ -f .env ] || { echo "Abbruch: .env fehlt (Muster: .env.example)" >&2; exit 1; }
wert() { sed -n "s/^$1=//p" .env | tail -1; }
for paar in ORT_BESTAND:bestand ORT_SUCHE:suche ORT_TEXTE:texte ORT_UMSCHLAEGE:umschlaege; do
  ort="$(wert "${paar%%:*}")"
  mkdir -p "${ort:-daten/${paar##*:}}"
done
cd docker
docker compose --env-file ../.env -f pi5b.compose.yml build
docker compose --env-file ../.env -f pi5b.compose.yml up -d
docker compose --env-file ../.env -f pi5b.compose.yml ps
