#!/usr/bin/env bash
# Startet das fertige Add-on-Image und prüft, ob es wirklich läuft.
#
# Die Unit-Tests sehen nur den Python-Code. Ob das Bild startet, alle Module
# enthält, die Oberfläche ausliefert und beide Befehlszeilen mitbringt, zeigt
# erst ein laufender Container. Wird lokal von scripts/check.sh --docker und in
# GitHub vom Job "docker" in .github/workflows/ci.yaml aufgerufen.
#
# Aufruf: scripts/smoke_test.sh <image>

set -euo pipefail

image="${1:?Aufruf: scripts/smoke_test.sh <image>}"
name="omniai-smoke-$$"
timeout_s=60

fail() {
  echo "::error::Smoke-Test: $*" >&2
  echo "--- Log des Containers ---" >&2
  docker logs "$name" >&2 || true
  exit 1
}

cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "Starte $image …"
# Zufälliger freier Port auf dem Host, nur lokal erreichbar.
docker run -d --name "$name" -p 127.0.0.1::8000 "$image" >/dev/null
port="$(docker port "$name" 8000/tcp | head -n1 | sed 's/.*://')"
base="http://127.0.0.1:${port}"

# Warten, bis die Schnittstelle antwortet — Polling mit Frist statt festem sleep.
deadline=$((SECONDS + timeout_s))
until curl -fsS "$base/health" >/dev/null 2>&1; do
  if [ "$(docker inspect -f '{{.State.Running}}' "$name")" != "true" ]; then
    fail "Container hat sich beendet, bevor /health antwortete."
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    fail "/health antwortet nach ${timeout_s} s nicht."
  fi
  sleep 1
done
echo "✓ /health antwortet"

health="$(curl -fsS "$base/health")"
[ "$health" = '{"status":"ok"}' ] || fail "/health liefert unerwartet: $health"

curl -fsS "$base/models" | grep -q '"providers"' || fail "/models liefert keine Anbieterliste."
echo "✓ /models liefert die Anbieter"

# Über den Ingress setzt der Server ein passendes <base> vor alle Verweise.
ingress="/api/hassio_ingress/smoke-test"
index="$(curl -fsS -H "X-Ingress-Path: $ingress" "$base/")"
grep -q "<base href=\"$ingress/\">" <<<"$index" || fail "Startseite ohne Ingress-<base>."
echo "✓ Startseite über den Ingress"

# Das gebaute Bündel muss im Bild liegen, nicht nur die index.html.
asset="$(grep -o 'assets/index-[A-Za-z0-9_-]*\.js' <<<"$index" | head -n1)"
[ -n "$asset" ] || fail "Startseite verweist auf kein Skript-Bündel."
curl -fsS -o /dev/null "$base/$asset" || fail "Bündel $asset fehlt im Bild."
echo "✓ Bündel der Oberfläche ausgeliefert"

docker exec "$name" claude --version >/dev/null || fail "Claude-CLI fehlt im Bild."
docker exec "$name" codex --version >/dev/null || fail "Codex-CLI fehlt im Bild."
docker exec "$name" agy --version >/dev/null || fail "Antigravity-CLI fehlt im Bild."
echo "✓ Claude-, Codex- und Antigravity-CLI vorhanden"

# Ohne tzdata und TZ stünden die Log-Zeiten in UTC (eiserne Regel 9).
zone="$(docker exec "$name" date +%Z)"
case "$zone" in
  CET | CEST) echo "✓ Zeitzone des Containers" ;;
  *) fail "Container läuft nicht in deutscher Zeit (date +%Z ergab $zone)." ;;
esac

# Den HEALTHCHECK wertet der Supervisor aus, um das Add-on neu zu starten. Er
# muss gesetzt sein und jetzt schon gelingen — auf sein erstes Intervall zu
# warten, hielte den Test eine halbe Minute auf.
health_cmd="$(docker inspect -f '{{if .Config.Healthcheck}}{{join .Config.Healthcheck.Test " "}}{{end}}' "$name")"
[ -n "$health_cmd" ] || fail "Image hat keinen HEALTHCHECK."
docker exec "$name" curl -fsS http://127.0.0.1:8000/health >/dev/null \
  || fail "HEALTHCHECK-Befehl schlägt im Container fehl."
echo "✓ HEALTHCHECK gesetzt und erfolgreich"

if docker logs "$name" 2>&1 | grep -q "Traceback"; then
  fail "Im Log steht ein Traceback."
fi
echo "✓ Log ohne Traceback"

echo "Smoke-Test bestanden."
