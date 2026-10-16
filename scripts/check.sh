#!/usr/bin/env bash
# Alle Prüfungen, die auch die CI auf agent/main ausführt — lokal, vor dem Push.
#
#   scripts/check.sh            Linting, Tests, Bau der Oberfläche
#   scripts/check.sh --docker   zusätzlich Image bauen und Smoke-Test
#
# Läuft automatisch als pre-push-Hook, sobald einmalig
#   git config core.hooksPath .githooks
# gesetzt ist. Was hier fehlschlägt, schlägt auch in GitHub fehl.

set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

with_docker=false
for arg in "$@"; do
  case "$arg" in
    --docker) with_docker=true ;;
    *)
      echo "Unbekannte Option: $arg (erlaubt: --docker)" >&2
      exit 2
      ;;
  esac
done

if [ -x .venv/bin/python ]; then
  python=.venv/bin/python
else
  python=python3
fi

step() { printf '\n\033[1m▶ %s\033[0m\n' "$*"; }

step "Python: Linting"
"$python" -m ruff check .

step "Python: Formatierung"
"$python" -m ruff format --check .

step "Python: Tests"
"$python" -m pytest -q --cov=skytech_omniai --cov=scripts --cov-report=term:skip-covered

step "Oberfläche: Typprüfung und Bau"
if [ ! -d skytech_omniai/web/node_modules ]; then
  npm ci --prefix skytech_omniai/web
fi
npm run build --prefix skytech_omniai/web

if [ "$with_docker" = true ]; then
  # Gebaut wird für die Architektur des eigenen Rechners, mit demselben
  # Basisimage, das der Supervisor aus build.yaml nimmt.
  case "$(uname -m)" in
    x86_64 | amd64) arch=amd64 ;;
    arm64 | aarch64) arch=aarch64 ;;
    *)
      echo "Architektur $(uname -m) wird vom Add-on nicht unterstützt." >&2
      exit 1
      ;;
  esac
  build_from="$(sed -n "s/^  ${arch}: \"\(.*\)\"$/\1/p" skytech_omniai/build.yaml)"

  step "Docker: Image bauen ($arch)"
  docker build --build-arg "BUILD_FROM=${build_from}" -t skytech-omniai:check skytech_omniai

  step "Docker: Smoke-Test"
  scripts/smoke_test.sh skytech-omniai:check
fi

if [ "$(git config --get core.hooksPath || true)" != ".githooks" ]; then
  printf '\nHinweis: Hooks (commit-msg, pre-push) nicht aktiv. Einmalig: git config core.hooksPath .githooks\n'
fi

printf '\n\033[1;32m✓ Alle Prüfungen bestanden.\033[0m\n'
