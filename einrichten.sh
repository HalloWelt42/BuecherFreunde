#!/usr/bin/env bash
# Einrichten von BücherFreunde. Schritte und Proben der Neueinrichtung stehen in docs/handbuch.md.
#
#   ./einrichten.sh                                       wie ./install.sh auf dem Zielrechner: fragt Ordner, Port und
#                                                         Kellerwolke ab (schreibt .env, nur wenn keine da ist), baut und
#                                                         startet die Container, bietet den systemd-Dienst an
#   ./einrichten.sh --probe --ziel DIR --port-versatz N   Probelauf des Handbuchs: .env ohne Fragen mit allen Ordnern in
#                                                         DIR, ohne Kellerwolke, ohne Open Library und LM Studio, Port um
#                                                         N verschoben und nur an 127.0.0.1; bauen und starten wie
#                                                         install.sh, das Backend abgeschottet (docker/probelauf.compose.yml)
#   ./einrichten.sh --probe --ziel DIR --abbauen          entfernt Container, Netze und die gebauten Abbilder
set -euo pipefail
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WARTEN_S=240
PROBE_COMPOSE=(--env-file ../.env -f docker-compose.yml -f probelauf.compose.yml)

# Vorgabe des Ports der Oberfläche aus docker/docker-compose.yml (EXTERNAL_PORT), damit er nur dort steht
grundport() {
  sed -n 's/.*\${EXTERNAL_PORT:-\([0-9][0-9]*\)}.*/\1/p' "$1/docker/docker-compose.yml" | head -1
}

probe_aufbauen() {
  local ziel="$1" versatz="$2" port
  port=$(( $(grundport "$ziel") + versatz ))
  mkdir -p "$ziel/storage" "$ziel/external" "$ziel/import" "$ziel/database" "$ziel/zugang"
  cat > "$ziel/.env" <<EOF
# Probelauf des Handbuchs: alle Ordner im Probeordner, keine Gegenstellen
HOST=0.0.0.0
PORT=8000
EXTERNAL_PORT=$port
KELLERWOLKE_URL=
KELLERWOLKE_CA=
KELLERWOLKE_SCHLUESSEL_DATEI=
FUNDUS_APPS=Fundus
STORAGE_DIR=$ziel/storage
EXTERNAL_DIR=$ziel/external
IMPORT_DIR=$ziel/import
DATABASE_DIR=$ziel/database
OPENLIBRARY_ENABLED=false
LM_STUDIO_ENABLED=false
LOG_LEVEL=info
EOF
  cd "$ziel/docker"
  if ! docker compose "${PROBE_COMPOSE[@]}" up -d --build --force-recreate --quiet-pull; then
    docker compose "${PROBE_COMPOSE[@]}" logs --tail 40 >&2 || true
    return 1
  fi
  local ende=$(( $(date +%s) + WARTEN_S ))
  while [ "$(date +%s)" -lt "$ende" ]; do
    if curl -sf "http://127.0.0.1:$port/api/health" >/dev/null; then
      echo "ANTWORTET http://127.0.0.1:$port/api/health"
      return 0
    fi
    sleep 2
  done
  echo "BücherFreunde antwortet nach $WARTEN_S s nicht" >&2
  docker compose "${PROBE_COMPOSE[@]}" logs --tail 40 >&2 || true
  return 1
}

probe_abbauen() {
  [ -f "$1/.env" ] || return 0
  cd "$1/docker"
  docker compose "${PROBE_COMPOSE[@]}" down --volumes --remove-orphans --rmi local
}

probe=0; abbauen=0; ziel=""; versatz=""
while [ $# -gt 0 ]; do
  case "$1" in
    --probe) probe=1 ;;
    --abbauen) abbauen=1 ;;
    --ziel) ziel="${2:?--ziel braucht einen Ordner}"; shift ;;
    --port-versatz) versatz="${2:?--port-versatz braucht eine Zahl}"; shift ;;
    *) echo "unbekannte Angabe: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$probe" = 0 ]; then
  exec "$HIER/install.sh"
elif [ -z "$ziel" ] || [ ! -d "$ziel" ]; then
  echo "--probe braucht --ziel mit einem vorhandenen Ordner" >&2; exit 2
elif [ "$abbauen" = 1 ]; then
  probe_abbauen "$(cd "$ziel" && pwd)"
else
  probe_aufbauen "$(cd "$ziel" && pwd)" "${versatz:?--port-versatz fehlt}"
fi
