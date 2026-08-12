# screenshot-gallery

Static, multi-project screenshot gallery hosted on GitHub Pages. Each project gets its own
directory under `projects/` with a small manifest describing its dashboards; the same renderer
and scripts capture and publish all of them.

Hosted at: https://argpna.github.io/screenshot-gallery/

## Contents

| Path | Purpose |
|---|---|
| `index.html` | Landing page listing every project (generated) |
| `style.css` | Shared styling for the landing page and every project gallery |
| `projects/<name>/manifest.py` | Per-project config: title, dashboard list, target repo location |
| `projects/<name>/index.html` | Per-project gallery page (generated) |
| `projects/<name>/screenshots/*.png` | Full-page dashboard screenshots (generated) |
| `scripts/screenshot.py` | Renders PNGs via Grafana's image renderer, writes gallery pages |
| `docker-compose.yml` | Compose overlay that adds the image renderer to a target project's stack |
| `capture.sh` | Screenshot helper: ensures the renderer is running, takes screenshots |

## Onboarding a new project

1. Clone the target project next to this repo (`../<project-name>`).
2. Add `projects/<project-name>/manifest.py`. Copy an existing one (e.g.
   `projects/darlingperfmon/manifest.py`) as a template - it needs `TITLE`, `DESCRIPTION`,
   `REPO_URL`, `CLONE_SNIPPET`, `SIBLING_DIR` (relative path to the clone), `DASHBOARDS`, and
   optionally `PAGE_SCREENSHOTS`/`PRIMARY_SERVER`/`GRAFANA_SERVICE_NAME`.
3. The target project's compose file must name its Grafana service `grafana` - that's the
   convention the renderer overlay (`docker-compose.yml`) relies on to attach itself.
4. Run `./capture.sh --project <project-name>`.

## Refreshing a gallery

Prerequisites: Docker with Compose v2, Python 3, the target project's `.env` exists.

```bash
# bring up the target project's own stack with data (see its README for exact invocation)

# screenshot all of a project's dashboards
./capture.sh --project darlingperfmon

# list a project's available dashboard UIDs
./capture.sh --project darlingperfmon --list

# screenshot a single dashboard
./capture.sh --project darlingperfmon --dashboard darling-queries

# screenshot against a different server (default: manifest's PRIMARY_SERVER)
./capture.sh --project darlingperfmon --server SQL2025

# change the time range (default: 1h)
./capture.sh --project darlingperfmon --timerange 6h
./capture.sh --project darlingperfmon --timerange 24h
./capture.sh --project darlingperfmon --timerange 7d

# arbitrary from/to for precise windows
./capture.sh --project darlingperfmon --from now-2h --to now-30m

# render in Grafana's light theme (default: dark)
./capture.sh --project darlingperfmon --theme light
```

Each run regenerates that project's `index.html` and the repo-root landing page.
