#!/usr/bin/env python3
"""Screenshot a project's dashboards and build its static GitHub Pages gallery.

Calls Grafana's /render/d/{uid} endpoint for each dashboard in the project's manifest, then writes
projects/<project>/index.html and projects/<project>/screenshots/ - then regenerates the repo-root
landing page from every projects/*/manifest.py present.

Usage:
    GRAFANA_ADMIN_PASSWORD=... python3 scripts/screenshot.py --project darlingperfmon

Environment:
    GRAFANA_URL              default: http://localhost:3000
    GRAFANA_ADMIN_PASSWORD   required
"""

import argparse
import base64
import importlib.util
import json
import os
import re
import struct
import sys
import time
import types
import urllib.error
import urllib.request
import zlib
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = REPO_ROOT / "projects"

GRAFANA = os.environ.get("GRAFANA_URL", "http://localhost:3000").rstrip("/")
ADMIN_PASS = os.environ.get("GRAFANA_ADMIN_PASSWORD", "")
TIME_FROM = os.environ.get("SCREENSHOT_FROM", "now-1h")
TIME_TO = os.environ.get("SCREENSHOT_TO", "now")
SERVER_OVERRIDE = os.environ.get("SCREENSHOT_SERVER", "")
THEME = os.environ.get("SCREENSHOT_THEME", "dark")

PREFERENCE_THEMES = {"tron", "desertbloom", "gildedgrove", "sapphiredusk", "gloom"}

RENDER_WIDTH = 1600
_GRID_PX = 40
_MARGIN_PX = 50


def _auth_header() -> str:
    return "Basic " + base64.b64encode(f"admin:{ADMIN_PASS}".encode()).decode()


def load_manifest(project: str) -> types.ModuleType:
    path = PROJECTS_DIR / project / "manifest.py"
    if not path.is_file():
        sys.exit(f"no manifest at {path}")
    spec = importlib.util.spec_from_file_location(f"manifest_{project}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def list_projects() -> list[str]:
    return sorted(
        p.name for p in PROJECTS_DIR.iterdir() if p.is_dir() and (p / "manifest.py").is_file()
    )


def _get(path: str) -> dict:
    req = urllib.request.Request(f"{GRAFANA}{path}", headers={"Authorization": _auth_header()})
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


def _is_v2_dashboard(dash: dict) -> bool:
    return dash.get("kind") == "Dashboard" and "spec" in dash


def _v2_grid_height(spec: dict) -> int | None:
    layout = spec.get("layout", {})
    if layout.get("kind") != "AutoGridLayout":
        return None
    lspec = layout.get("spec", {})
    items = lspec.get("items", [])
    if not items:
        return None

    count = 1
    var_name = items[0].get("spec", {}).get("repeat", {}).get("value")
    if var_name:
        variables = {
            v["spec"]["name"]: v["spec"]
            for v in spec.get("variables", [])
            if "spec" in v and "name" in v.get("spec", {})
        }
        var = variables.get(var_name)
        if var and var.get("kind", var.get("type")) == "DatasourceVariable":
            m = re.match(r"^/(.*)/([a-z]*)$", var.get("regex") or "")
            pattern = m.group(1) if m else var.get("regex")
            rx = re.compile(pattern) if pattern else None
            names = [ds["name"] for ds in _get("/api/datasources")]
            count = sum(1 for n in names if not rx or rx.search(n)) or 1

    columns = lspec.get("maxColumnCount") or 1
    row_height = lspec.get("rowHeight", _GRID_PX)
    rows = -(-count // columns)  # ceil
    return rows * row_height + _MARGIN_PX


def dashboard_render_height(uid: str) -> int:
    try:
        dash = _get(f"/api/dashboards/uid/{uid}").get("dashboard", {})
        if _is_v2_dashboard(dash):
            height = _v2_grid_height(dash["spec"])
            if height is not None:
                return max(height, 600)
        panels = dash.get("panels", [])
        max_grid = max(
            (p["gridPos"]["y"] + p["gridPos"]["h"] for p in panels if "gridPos" in p),
            default=0,
        )
        return max(max_grid * _GRID_PX + _MARGIN_PX, 600)
    except (urllib.error.URLError, KeyError, ValueError, OSError):
        return 1200


def resolve_server_value(uid: str, name: str) -> str:
    try:
        dash = _get(f"/api/dashboards/uid/{uid}").get("dashboard", {})
        var = next(
            (v for v in dash.get("templating", {}).get("list", []) if v.get("name") == "server"),
            {},
        )
        ds, query = var.get("datasource"), var.get("query")
        if not ds or not isinstance(query, str):
            return name
        body = json.dumps(
            {"queries": [{"refId": "A", "datasource": ds, "rawSql": query, "format": "table"}]}
        ).encode()
        req = urllib.request.Request(
            f"{GRAFANA}/api/ds/query",
            data=body,
            headers={"Authorization": _auth_header(), "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            frame = json.load(r)["results"]["A"]["frames"][0]
        fields = [f["name"] for f in frame["schema"]["fields"]]
        texts = frame["data"]["values"][fields.index("__text")]
        values = frame["data"]["values"][fields.index("__value")]
        return str(dict(zip(texts, values))[name])
    except (urllib.error.URLError, KeyError, IndexError, ValueError, OSError):
        return name


def set_user_theme_preference(theme: str) -> None:
    req = urllib.request.Request(
        f"{GRAFANA}/api/user/preferences",
        data=json.dumps({"theme": theme}).encode(),
        headers={"Authorization": _auth_header(), "Content-Type": "application/json"},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()


_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_CHANNELS_BY_COLOR_TYPE = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _read_png_chunks(data: bytes) -> tuple[dict, bytes]:
    ihdr: dict = {}
    idat = bytearray()
    pos = len(_PNG_SIG)
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        if tag == b"IHDR":
            width, height, bit_depth, color_type, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
            ihdr = {
                "width": width,
                "height": height,
                "bit_depth": bit_depth,
                "color_type": color_type,
                "interlace": interlace,
            }
        elif tag == b"IDAT":
            idat += chunk
        elif tag == b"IEND":
            break
        pos += 12 + length
    return ihdr, bytes(idat)


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


_BADGE_MARGIN_PX = 220
_BLANK_COLOR_THRESHOLD = 12


def _autocrop_png(path: Path, padding: int = 40, min_height: int = 300) -> None:
    raw = path.read_bytes()
    ihdr, idat = _read_png_chunks(raw)
    if not ihdr or ihdr["bit_depth"] != 8 or ihdr["interlace"] != 0:
        return
    channels = _CHANNELS_BY_COLOR_TYPE.get(ihdr["color_type"])
    if channels is None:
        return

    width, height = ihdr["width"], ihdr["height"]
    stride = width * channels
    filtered = zlib.decompress(idat)
    if len(filtered) != height * (stride + 1):
        return

    rows = []
    prev = bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        filter_type = filtered[start]
        scan = filtered[start + 1 : start + 1 + stride]
        recon = bytearray(stride)
        for x in range(stride):
            a = recon[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if filter_type == 0:
                recon[x] = scan[x]
            elif filter_type == 1:
                recon[x] = (scan[x] + a) & 0xFF
            elif filter_type == 2:
                recon[x] = (scan[x] + b) & 0xFF
            elif filter_type == 3:
                recon[x] = (scan[x] + (a + b) // 2) & 0xFF
            elif filter_type == 4:
                recon[x] = (scan[x] + _paeth(a, b, c)) & 0xFF
            else:
                return
        rows.append(bytes(recon))
        prev = recon

    compare_width = max(0, width - _BADGE_MARGIN_PX) or width
    compare_len = compare_width * channels
    last_content_row = None
    for y in range(height - 1, -1, -1):
        row = rows[y]
        colors = {row[x * channels : (x + 1) * channels] for x in range(compare_width)}
        if len(colors) > _BLANK_COLOR_THRESHOLD:
            last_content_row = y
            break
    if last_content_row is None:
        return

    page_bg = rows[-1][:compare_len]
    box_close_row = height - 1
    for y in range(last_content_row + 1, height):
        if rows[y][:compare_len] == page_bg:
            box_close_row = y
            break

    crop_height = max(box_close_row + padding, min_height)
    crop_height = min(crop_height, height)
    if crop_height >= height:
        return

    cropped_filtered = filtered[: crop_height * (stride + 1)]
    new_ihdr = struct.pack(">IIBBBBB", width, crop_height, ihdr["bit_depth"], ihdr["color_type"], 0, 0, 0)
    new_png = (
        _PNG_SIG
        + _png_chunk(b"IHDR", new_ihdr)
        + _png_chunk(b"IDAT", zlib.compress(cropped_filtered, 9))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(new_png)


def render_dashboard(
    uid: str, var_server: str | None, height: int, out_path: Path, theme_param: str | None
) -> bool:
    params = (
        f"orgId=1"
        f"&from={TIME_FROM}&to={TIME_TO}"
        f"&width={RENDER_WIDTH}&height={height}"
        f"&kiosk"
    )
    if theme_param:
        params += f"&theme={theme_param}"
    if var_server:
        params += f"&var-server={var_server}"
    url = f"{GRAFANA}/render/d/{uid}?{params}"
    req = urllib.request.Request(url, headers={"Authorization": _auth_header()})
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
    _autocrop_png(out_path)
    return True


def _png_size(path: Path) -> tuple[int, int] | None:
    try:
        header = path.open("rb").read(24)
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def _card_html(title: str, rel_path: str, ok: bool, png_path: Path) -> str:
    if ok:
        dims = _png_size(png_path)
        style = f' style="aspect-ratio:{dims[0]}/{dims[1]}"' if dims else ""
        img = f'<img src="{rel_path}" alt="{title}" loading="lazy"{style}>'
    else:
        img = (
            '<div class="missing">'
            "Screenshot unavailable - renderer not configured or dashboard had no data."
            "</div>"
        )
    return f'<div class="card flow-item"><div class="card-title">{title}</div>{img}</div>\n'


def write_project_index(
    project: str, manifest: types.ModuleType, results: list[tuple[str, str, str, bool]], stamp: str
) -> None:
    shots_dir = PROJECTS_DIR / project / "screenshots"
    flow_items = ""
    current_group = None
    for uid, title, group, ok in results:
        if group != current_group:
            flow_items += f'<div class="section-header flow-item">{group}</div>\n'
            current_group = group
        flow_items += _card_html(title, f"screenshots/{uid}.png", ok, shots_dir / f"{uid}.png")

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{manifest.TITLE} - Dashboard Gallery</title>
<link rel="stylesheet" href="../../style.css">
</head>
<body>
<header>
  <p><a href="../../index.html">&larr; all projects</a></p>
  <h1>{manifest.TITLE}</h1>
  <p>{manifest.DESCRIPTION}</p>
  <p>Run the demo locally (<a href="{manifest.REPO_URL}">{manifest.REPO_URL}</a>):</p>
  <div class="howto">{manifest.CLONE_SNIPPET.replace(chr(10), "<br>")}</div>
</header>

<section><div class="masonry">
{flow_items}</div></section>

<footer>Generated {stamp} from a live demo run.</footer>
<script src="../../gallery.js" defer></script>
</body>
</html>
"""
    out_dir = PROJECTS_DIR / project
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Wrote {out_dir / 'index.html'}")


def write_landing_index() -> None:
    cards = ""
    for project in list_projects():
        manifest = load_manifest(project)
        cards += (
            f'<div class="card"><div class="card-title">'
            f'<a href="projects/{project}/index.html">{manifest.TITLE}</a>'
            f"</div><p>{manifest.DESCRIPTION}</p></div>\n"
        )

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>screenshot-gallery</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
  <h1>screenshot-gallery</h1>
  <p>Static dashboard-screenshot galleries, one per project.</p>
</header>

<section><div class="grid">{cards}</div></section>
</body>
</html>
"""
    (REPO_ROOT / "index.html").write_text(html, encoding="utf-8")
    print(f"Wrote {REPO_ROOT / 'index.html'}")


def list_dashboards(manifest: types.ModuleType) -> None:
    groups: dict[str, list] = {}
    for uid, title, group, _ in manifest.DASHBOARDS:
        groups.setdefault(group, []).append((uid, title))
    for group, items in groups.items():
        print(f"\n{group}")
        for uid, title in items:
            print(f"  {uid:<40} {title}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, help="directory name under projects/")
    parser.add_argument("--list", action="store_true", help="list dashboard UIDs and exit")
    parser.add_argument("--uids", default="", help="comma-separated UID filter (default: all)")
    args = parser.parse_args()

    manifest = load_manifest(args.project)

    if args.list:
        list_dashboards(manifest)
        return

    if not ADMIN_PASS:
        sys.exit("GRAFANA_ADMIN_PASSWORD env var is required")

    wait_for_grafana()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    shots_dir = PROJECTS_DIR / args.project / "screenshots"
    shots_dir.mkdir(parents=True, exist_ok=True)

    is_preference_theme = THEME in PREFERENCE_THEMES
    theme_param = None if is_preference_theme else THEME
    if is_preference_theme:
        set_user_theme_preference(THEME)

    uid_filter = {u.strip() for u in args.uids.split(",") if u.strip()}
    targets = [d for d in manifest.DASHBOARDS if not uid_filter or d[0] in uid_filter]
    print(f"\nRendering {len(targets)} dashboard(s)...")
    try:
        for uid, title, group, use_server in targets:
            height = dashboard_render_height(uid)
            print(f"  [{uid}]  height={height}px")
            out = shots_dir / f"{uid}.png"
            if isinstance(use_server, str):
                var_server = resolve_server_value(uid, use_server)
            elif use_server:
                var_server = SERVER_OVERRIDE or manifest.PRIMARY_SERVER
            else:
                var_server = None
            ok = render_dashboard(uid, var_server, height, out, theme_param)
            print(f"    -> {'ok' if ok else 'FAILED'}")
    finally:
        if is_preference_theme:
            set_user_theme_preference("dark")

    results = []
    for uid, title, group, _ in manifest.DASHBOARDS:
        ok = (shots_dir / f"{uid}.png").exists()
        results.append((uid, title, group, ok))

    for uid, title, group in getattr(manifest, "PAGE_SCREENSHOTS", []):
        ok = (shots_dir / f"{uid}.png").exists()
        results.append((uid, title, group, ok))

    ok_count = sum(1 for _, _, _, ok in results if ok)
    print(f"\n{ok_count}/{len(manifest.DASHBOARDS)} dashboards rendered successfully.")

    write_project_index(args.project, manifest, results, stamp)
    write_landing_index()


if __name__ == "__main__":
    main()
