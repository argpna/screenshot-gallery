#!/usr/bin/env python3
"""Screenshot all dashboards and build a static GitHub Pages gallery.

Calls Grafana's /render/d/{uid} endpoint for each dashboard, then writes
index.html & screenshots/ into PAGES_DIR.

The rendered height is computed per dashboard from the Grafana API so the full
scrollable dashboard is captured regardless of how many panels it contains.

Use capture.sh in this repo to orchestrate the full flow. Direct usage:
    GRAFANA_ADMIN_PASSWORD=GrafanaAdmin1 python3 scripts/screenshot.py

Environment:
    GRAFANA_URL              default: http://localhost:3000
    GRAFANA_ADMIN_PASSWORD   required
    SCREENSHOT_DS            default: perfmon-ds-sql2022 ($instance var value)
    PAGES_DIR                default: parent of this script
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GRAFANA = os.environ.get("GRAFANA_URL", "http://localhost:3000").rstrip("/")
ADMIN_PASS = os.environ.get("GRAFANA_ADMIN_PASSWORD", "")
PRIMARY_DS = os.environ.get("SCREENSHOT_DS", "perfmon-ds-sql2022")
PAGES_DIR = Path(os.environ.get("PAGES_DIR", Path(__file__).resolve().parent.parent))
_UID_FILTER = {u.strip() for u in os.environ.get("SCREENSHOT_UIDS", "").split(",") if u.strip()}
TIME_FROM = os.environ.get("SCREENSHOT_FROM", "now-1h")
TIME_TO = os.environ.get("SCREENSHOT_TO", "now")

_AUTH = "Basic " + base64.b64encode(f"admin:{ADMIN_PASS}".encode()).decode()

RENDER_WIDTH = 1600
_GRID_PX = 40
_MARGIN_PX = 50

# Manually captured pages.
# Drop the PNG into screenshots/ and it will appear in the gallery.
# (uid, title, group)
PAGE_SCREENSHOTS = [
    ("page-alert-rules",           "Alerting Rules",        "Alerting"),
    ("page-active-notifications",  "Active Notifications",  "Alerting"),
    ("page-contact-points",        "Contact Points",        "Alerting"),
    ("page-notification-policies", "Notification Policies", "Alerting"),
]

DASHBOARDS = [
    ("perfmon-fleet",                  "Fleet Overview",          "PerfMon", False),
    ("perfmon-instance",               "Instance Overview",       "PerfMon", True),
    ("perfmon-queries",                "Queries",                 "PerfMon", True),
    ("perfmon-waits",                  "Resource Metrics",        "PerfMon", True),
    ("perfmon-blocking",               "Locking",                 "PerfMon", True),
    ("perfmon-memory",                 "Memory",                  "PerfMon", True),
    ("perfmon-collection",             "Collection Health",       "PerfMon", True),
    ("perfmon-system-events",          "System Events",           "PerfMon", True),
    ("finops-recommendations",         "Recommendations",         "FinOps",  True),
    ("finops-utilization",             "Utilization",             "FinOps",  True),
    ("finops-database-resources",      "Database Resources",      "FinOps",  True),
    ("finops-storage-growth",          "Storage Growth",          "FinOps",  True),
    ("finops-object-sizes",            "Object Sizes & Growth",   "FinOps",  True),
    ("finops-index-usage",             "Index Usage",             "FinOps",  True),
    ("finops-locking",                 "Locking & Contention",    "FinOps",  True),
    ("finops-database-sizes",          "Database Sizes",          "FinOps",  True),
    ("finops-index-analysis",          "Index Analysis",          "FinOps",  True),
    ("finops-optimization",            "Optimization",            "FinOps",  True),
    ("finops-high-impact",             "High Impact",             "FinOps",  True),
    ("finops-application-connections", "Application Connections", "FinOps",  True),
    ("finops-server-inventory",        "Server Inventory",        "FinOps",  True),
]


def _get(path: str) -> dict:
    req = urllib.request.Request(
        f"{GRAFANA}{path}",
        headers={"Authorization": _AUTH},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def wait_for_grafana(timeout: int = 180) -> None:
    print(f"Waiting for Grafana at {GRAFANA}...", end="", flush=True)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if _get("/api/health").get("database") == "ok":
                print(" ready.")
                return
        except (urllib.error.URLError, OSError):
            pass
        print(".", end="", flush=True)
        time.sleep(5)
    sys.exit("Grafana not ready after 180s")


def dashboard_render_height(uid: str) -> int:
    """Return the pixel height needed to capture the full dashboard.

    Queries the dashboard JSON, finds the bottom edge of the lowest panel and
    converts to pixels using Grafana's grid unit size plus a top-margin buffer.
    """
    try:
        panels = _get(f"/api/dashboards/uid/{uid}")["dashboard"].get("panels", [])
        max_grid = max(
            (p["gridPos"]["y"] + p["gridPos"]["h"] for p in panels if "gridPos" in p),
            default=0,
        )
        return max(max_grid * _GRID_PX + _MARGIN_PX, 600)
    except (urllib.error.URLError, KeyError, ValueError, OSError):
        return 1200


def render_dashboard(uid: str, use_instance: bool, height: int, out_path: Path) -> bool:
    """Fetch a rendered PNG via Grafana's image renderer and write it to out_path."""
    params = (
        f"orgId=1"
        f"&from={TIME_FROM}&to={TIME_TO}"
        f"&width={RENDER_WIDTH}&height={height}"
        f"&theme=dark"
        f"&kiosk"
    )
    if use_instance:
        params += f"&var-instance={PRIMARY_DS}"
    url = f"{GRAFANA}/render/d/{uid}?{params}"
    req = urllib.request.Request(url, headers={"Authorization": _AUTH})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        print(f"      error: {e}")
        return False

    if not data.startswith(b"\x89PNG"):
        print(f"      warn: response is not a PNG ({len(data)} bytes) - renderer may not be ready")
        return False

    out_path.write_bytes(data)
    return True


def _card_html(title: str, rel_path: str, ok: bool) -> str:
    if ok:
        img = f'<img src="{rel_path}" alt="{title}" loading="lazy">'
    else:
        img = (
            '<div class="missing">'
            "Screenshot unavailable - renderer not configured or dashboard had no data."
            "</div>"
        )
    return (
        f'<div class="card">'
        f'<div class="card-title">{title}</div>'
        f"{img}"
        f"</div>\n"
    )


def write_index_html(results: list[tuple[str, str, str, bool]], stamp: str) -> None:
    shots_rel = "screenshots"
    groups: dict[str, list] = {}
    for uid, title, group, ok in results:
        groups.setdefault(group, []).append((uid, title, ok))

    sections = ""
    for group, items in groups.items():
        cards = "".join(
            _card_html(title, f"{shots_rel}/{uid}.png", ok)
            for uid, title, ok in items
        )
        sections += (
            f'<section>\n'
            f'<h2>{group}</h2>\n'
            f'<div class="grid">{cards}</div>\n'
            f'</section>\n'
        )

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>eriksperfmon - Dashboard Gallery</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
  <h1>eriksperfmon</h1>
  <p>
    Grafana dashboards for
    <a href="https://github.com/erikdarlingdata/PerformanceMonitor">Erik Darling's PerformanceMonitor</a>
    (Full Edition). Screenshots from a demo running SQL Server 2017-2025 with a
    synthetic workload: wait stats, blocking pairs, deadlocks, memory pressure etc.
  </p>
  <p>Run the full demo locally (Get it from GitHub - <a href="https://github.com/argpna/eriksperfmon">argpna/eriksperfmon</a>):</p>
  <div class="howto">git clone git@github.com:argpna/eriksperfmon<br>cd eriksperfmon<br>cp .env.example .env &amp;&amp; docker compose up -d</div>
</header>

{sections}

<footer>Generated {stamp} from a live demo run.</footer>
</body>
</html>
"""
    index_path = PAGES_DIR / "index.html"
    index_path.write_text(html, encoding="utf-8")
    print(f"Wrote {index_path}")


def list_dashboards() -> None:
    groups: dict[str, list] = {}
    for uid, title, group, _ in DASHBOARDS:
        groups.setdefault(group, []).append((uid, title))
    for group, items in groups.items():
        print(f"\n{group}")
        for uid, title in items:
            print(f"  {uid:<40} {title}")
    print()


def main() -> None:
    if os.environ.get("SCREENSHOT_LIST"):
        list_dashboards()
        return

    if not ADMIN_PASS:
        sys.exit("GRAFANA_ADMIN_PASSWORD env var is required")

    wait_for_grafana()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    shots_dir = PAGES_DIR / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    targets = [d for d in DASHBOARDS if not _UID_FILTER or d[0] in _UID_FILTER]
    print(f"\nRendering {len(targets)} dashboard(s)...")
    rendered: dict[str, bool] = {}
    for uid, title, group, use_instance in targets:
        height = dashboard_render_height(uid)
        print(f"  [{uid}]  height={height}px")
        out = shots_dir / f"{uid}.png"
        ok = render_dashboard(uid, use_instance, height, out)
        print(f"    -> {'ok' if ok else 'FAILED'}")
        rendered[uid] = ok

    results = []
    for uid, title, group, _ in DASHBOARDS:
        if uid in rendered:
            ok = rendered[uid]
        else:
            ok = (shots_dir / f"{uid}.png").exists()
        results.append((uid, title, group, ok))

    for uid, title, group in PAGE_SCREENSHOTS:
        ok = (shots_dir / f"{uid}.png").exists()
        results.append((uid, title, group, ok))

    ok_count = sum(1 for _, _, _, ok in results if ok)
    print(f"\n{ok_count}/{len(DASHBOARDS)} dashboards rendered successfully.")

    write_index_html(results, stamp)


if __name__ == "__main__":
    main()
