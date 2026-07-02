#!/usr/bin/env bash
# Take full-page screenshots of all eriksperfmon Grafana dashboards and write
# index.html & screenshots/ into this repo for GitHub Pages.
#
# Prerequisites:
#   - eriksperfmon stack already running with data
#   - Docker with Compose v2
#   - ../eriksperfmon/.env exists
#   - Python 3 on PATH
#
# Usage:
#   ./capture.sh
#   ./capture.sh --list
#   ./capture.sh --dashboard perfmon-queries
#   ./capture.sh --instance perfmon-ds-sql2019 (default: perfmon-ds-sql2022)
#   ./capture.sh --timerange 6h (default: 1h)
#   ./capture.sh --from now-2h --to now-30m

set -euo pipefail

DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
MAIN_DIR="$(cd "$DEMO_DIR/../eriksperfmon" && pwd)"
COMPOSE="docker compose -f $MAIN_DIR/docker-compose.yml -f $DEMO_DIR/docker-compose.yml"

if [ ! -f "$MAIN_DIR/.env" ]; then
  echo "error: $MAIN_DIR/.env not found. Run: cp $MAIN_DIR/.env.example $MAIN_DIR/.env"
  exit 1
fi

set -a; source "$MAIN_DIR/.env"; set +a

INSTANCE="perfmon-ds-sql2022"
DASHBOARD_UIDS=""
TIME_FROM="now-1h"
TIME_TO="now"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --instance)   INSTANCE="$2"; shift ;;
    --dashboard)  DASHBOARD_UIDS="$2"; shift ;;
    --timerange)  TIME_FROM="now-$2"; shift ;;
    --from)       TIME_FROM="$2"; shift ;;
    --to)         TIME_TO="$2"; shift ;;
    --list)       SCREENSHOT_LIST=1 python3 "$DEMO_DIR/scripts/screenshot.py"; exit 0 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

echo "Ensuring renderer is running..."
$COMPOSE up -d renderer grafana

echo "Taking screenshots..."
GRAFANA_URL=http://localhost:3000 \
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD}" \
SCREENSHOT_DS="$INSTANCE" \
SCREENSHOT_UIDS="$DASHBOARD_UIDS" \
SCREENSHOT_FROM="$TIME_FROM" \
SCREENSHOT_TO="$TIME_TO" \
PAGES_DIR="$DEMO_DIR" \
python3 "$DEMO_DIR/scripts/screenshot.py"

echo ""
echo "Done."
