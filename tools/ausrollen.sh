#!/usr/bin/env bash
# Rollt den eingecheckten Stand aus (vom Mac aus). Rechner, Ordner und Name kommen aus dem Verbundverzeichnis (handbuch ziel).
#   1. eingecheckter Stand hinüber, Daten, Zugang und .env bleiben
#   2. bauen und starten (tools/starten.sh)
#   3. Gegenprüfung unter dem Namen der App
set -euo pipefail
HIER="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
handbuch pruefen "$HIER" >/dev/null || { echo "Abbruch: das Handbuch ist nicht in Ordnung" >&2; exit 1; }
wert() { handbuch ziel "$HIER" "$1"; }
RECHNER="$(wert rechner)"; WURZEL="$(wert wurzel)"
NAME="$(handbuch netz --json | python3 -c "import json,sys; print(next(a['hauptname'] for a in json.load(sys.stdin)['apps'] if a['kennung'] == 'buecherfreunde-neu'))")"
STAND="${1:-HEAD}"
echo "[1/3] $(git -C "$HIER" log -1 --format='%h %s' "$STAND" | cut -c1-90)"
git -C "$HIER" archive "$STAND" | ssh -o BatchMode=yes "$RECHNER" "set -e; cd '$WURZEL'; rm -rf .neu; mkdir .neu; tar -x -C .neu; for t in backend frontend docker tools docs tests; do rm -rf \$t; [ -e .neu/\$t ] && mv .neu/\$t .; done; find .neu -maxdepth 1 -type f -exec mv -f {} . \;; rm -rf .neu"
echo "[2/3] bauen und starten"
ssh -o BatchMode=yes "$RECHNER" "cd '$WURZEL' && ./tools/starten.sh" 2>&1 | grep -vE "^#|^$" | tail -4
echo "[3/3] https://$NAME"
for _ in $(seq 1 30); do
  antwort="$(curl -s --cacert "$(mkcert -CAROOT)/rootCA.pem" "https://$NAME/api/health" || true)"
  [[ "$antwort" == *'"ok"'* ]] && { echo "läuft: $antwort"; exit 0; }
  sleep 2
done
echo "antwortet nicht unter https://$NAME" >&2; exit 1
