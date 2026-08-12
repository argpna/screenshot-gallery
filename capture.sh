#!/usr/bin/env bash
# Take full-page screenshots of a project's Grafana dashboards and write
# projects/<project>/index.html & screenshots/ into this repo for GitHub Pages.
#
# Prerequisites:
#   - the target project's stack already running with data (SIBLING_DIR in its manifest.py)
#   - Docker with Compose v2
#   - the target project's .env exists
#   - Python 3 on PATH
#
# Usage:
#   ./capture.sh --project darlingperfmon
#   ./capture.sh --project darlingperfmon --list
#   ./capture.sh --project darlingperfmon --dashboard darling-queries
#   ./capture.sh --project darlingperfmon --server SQL2025 (default: manifest's PRIMARY_SERVER)
#   ./capture.sh --project darlingperfmon --timerange 6h (default: 1h)
#   ./capture.sh --project darlingperfmon --from now-2h --to now-30m
#   ./capture.sh --project darlingperfmon --theme light (default: dark)
#   ./capture.sh --project darlingperfmon --theme tron (novelty theme via user preference)

set -euo pipefail

GALLERY_DIR="$(cd "$(dirname "$0")" && pwd)"

PROJECT=""
SERVER_OVERRIDE=""
DASHBOARD_UIDS=""
TIME_FROM="now-1h"
TIME_TO="now"
THEME="dark"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)    PROJECT="$2"; shift ;;
    --server)     SERVER_OVERRIDE="$2"; shift ;;
    --dashboard)  DASHBOARD_UIDS="$2"; shift ;;
    --timerange)  TIME_FROM="now-$2"; shift ;;
    --from)       TIME_FROM="$2"; shift ;;
    --to)         TIME_TO="$2"; shift ;;
    --theme)      THEME="$2"; shift ;;
    --list)       LIST_ONLY=1 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

if [ -z "$PROJECT" ]; then
  echo "error: --project is required, e.g. --project darlingperfmon"
  exit 1
fi

MANIFEST="$GALLERY_DIR/projects/$PROJECT/manifest.py"
if [ ! -f "$MANIFEST" ]; then
  echo "error: no manifest at $MANIFEST"
  exit 1
fi

if [ -n "${LIST_ONLY:-}" ]; then
  python3 "$GALLERY_DIR/scripts/screenshot.py" --project "$PROJECT" --list
  exit 0
fi

read -r SIBLING_DIR GRAFANA_SERVICE_NAME < <(python3 -c "
import sys
sys.path.insert(0, '$GALLERY_DIR/scripts')
from screenshot import load_manifest
m = load_manifest('$PROJECT')
print(m.SIBLING_DIR, getattr(m, 'GRAFANA_SERVICE_NAME', 'grafana'))
")

MAIN_DIR="$(cd "$GALLERY_DIR/$SIBLING_DIR" && pwd)"

if [ ! -f "$MAIN_DIR/.env" ]; then
  echo "error: $MAIN_DIR/.env not found. Run: cp $MAIN_DIR/.env.example $MAIN_DIR/.env"
  exit 1
fi

set -a; source "$MAIN_DIR/.env"; set +a

COMPOSE="docker compose -f $MAIN_DIR/docker-compose.yml -f $GALLERY_DIR/docker-compose.yml"

echo "Ensuring renderer is running..."
$COMPOSE up -d renderer "$GRAFANA_SERVICE_NAME"

echo "Taking screenshots..."
GRAFANA_URL=http://localhost:3000 \
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD}" \
SCREENSHOT_FROM="$TIME_FROM" \
SCREENSHOT_TO="$TIME_TO" \
SCREENSHOT_SERVER="$SERVER_OVERRIDE" \
SCREENSHOT_THEME="$THEME" \
python3 "$GALLERY_DIR/scripts/screenshot.py" --project "$PROJECT" --uids "$DASHBOARD_UIDS"

echo ""
echo "Done."
