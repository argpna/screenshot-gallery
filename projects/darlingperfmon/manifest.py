"""Gallery manifest for darlingperfmon.

Consumed by scripts/screenshot.py --project darlingperfmon and capture.sh --project darlingperfmon.
"""

TITLE = "darlingperfmon"
DESCRIPTION = (
    "Grafana dashboards for Erik Darling's "
    '<a href="https://github.com/erikdarlingdata/PerformanceMonitor">PerformanceMonitor</a>, '
    "Darling edition."
)
REPO_URL = "https://github.com/argpna/darlingperfmon"
CLONE_SNIPPET = (
    "git clone https://github.com/argpna/darlingperfmon.git\n"
    "cd darlingperfmon\n"
    "cp .env.example .env && docker compose --profile darling up -d"
)

SIBLING_DIR = "../darlingperfmon"

GRAFANA_SERVICE_NAME = "grafana"

PRIMARY_SERVER = "SQL2022"

DASHBOARDS = [
    ("darling-fleet", "Fleet", "Overview", False),
    ("darling-overview", "Overview", "Overview", True),
    ("darling-administration", "Administration", "Overview", True),
    ("darling-collection-health", "Collection Health", "Overview", True),
    ("darling-collection-log-detail", "Collection Log Detail", "Overview", True),
    ("darling-cpu-memory-sessions", "CPU, Memory & Sessions", "Overview", True),
    ("darling-storage-tempdb", "Storage & tempdb", "Overview", True),
    ("darling-system-events", "System Events", "Overview", "sysevdemo-01-appsrv"),
    ("darling-availability-groups", "Availability Groups", "Overview", "sql-win-cluster-n01"),
    ("darling-availability-group-detail", "Availability Group Detail", "Overview", "sql-win-cluster-n01"),
    ("darling-wait-analysis", "Wait Analysis", "Waits & Blocking", True),
    ("darling-wait-drill-down", "Wait Drill-down", "Waits & Blocking", True),
    ("darling-blocking-deadlocks", "Blocking & Deadlocks", "Waits & Blocking", True),
    ("darling-deadlock-detail", "Deadlock Detail", "Waits & Blocking", True),
    ("darling-queries", "Queries", "Queries", True),
    ("darling-procedure-history", "Procedure History", "Queries", True),
    ("darling-query-stats-history", "Query Stats History", "Queries", True),
    ("darling-query-store-history", "Query Store History", "Queries", True),
    ("darling-finops-recommendations", "Recommendations", "FinOps", True),
    ("darling-finops-utilization", "Utilization", "FinOps", True),
    ("darling-finops-capacity-growth", "Capacity Growth", "FinOps", True),
    ("darling-finops-object-sizes", "Object Sizes", "FinOps", True),
    ("darling-finops-index-usage", "Index Usage", "FinOps", True),
    ("darling-finops-optimization-indexing", "Optimization / Indexing", "FinOps", True),
    ("darling-finops-workload-contention", "Workload Contention", "FinOps", True),
    ("darling-finops-server-inventory", "Server Inventory", "FinOps", True),
]

# Manually captured pages
PAGE_SCREENSHOTS = [
    ("page-alert-rules", "Alerting Rules", "Alerting"),
    ("page-active-notifications", "Active Notifications", "Alerting"),
    ("page-contact-points", "Contact Points", "Alerting"),
    ("page-notification-policies", "Notification Policies", "Alerting"),
]
