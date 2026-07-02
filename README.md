# eriksperfmon-demo

Static screenshot gallery for [eriksperfmon](https://github.com/argpna/eriksperfmon) -
Grafana dashboards for Erik Darling's
[PerformanceMonitor](https://github.com/erikdarlingdata/PerformanceMonitor) (Full Edition).

Hosted at: https://argpna.github.io/eriksperfmon-demo/

## Contents

| File | Purpose |
|---|---|
| `index.html` | Gallery landing page (generated) |
| `screenshots/*.png` | Full-page dashboard screenshots (generated) |
| `scripts/screenshot.py` | Renders PNGs via Grafana image renderer, writes `index.html` |
| `docker-compose.yml` | Compose overlay that adds the image renderer to the main stack |
| `capture.sh` | Screenshot helper: ensures renderer is running, takes screenshots |

## Refreshing the gallery

This repo must be cloned next to `eriksperfmon`:

```
projects/
  eriksperfmon/
  eriksperfmon-demo/
```

Prerequisites: Docker with Compose v2, Python 3, `../eriksperfmon/.env` exists.

```bash
# first time only
cp ../eriksperfmon/.env.example ../eriksperfmon/.env

# start the eriksperfmon stack and wait for data in ../eriksperfmon
docker compose up -d

# screenshot all dashboards
./capture.sh

# list available dashboard UIDs
./capture.sh --list

# screenshot a single dashboard
./capture.sh --dashboard perfmon-queries

# screenshot against a different SQL Server instance (default: perfmon-ds-sql2022)
./capture.sh --instance perfmon-ds-sql2025

# change the time range (default: 1h)
./capture.sh --timerange 6h
./capture.sh --timerange 24h
./capture.sh --timerange 7d

# arbitrary from/to for precise windows
./capture.sh --from now-2h --to now-30m

# combine flags
./capture.sh --dashboard perfmon-queries --instance perfmon-ds-sql2019 --timerange 6h

```
