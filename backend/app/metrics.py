"""Prometheus instrumentation.

Metrics are served on their own port (METRICS_PORT, default 9100), not on the
API port. The public Ingress only routes to port 8000, so /metrics is reachable
from inside the cluster and from nowhere else. Serving it on the app port would
publish your endpoint names, traffic volume and latency profile to the internet.

Everything registers into prometheus_client's default REGISTRY, which is what
start_http_server() serves.
"""

import time

from prometheus_client import Counter, Gauge, Histogram, start_http_server
from starlette.requests import Request

# --- HTTP ------------------------------------------------------------------
# A Counter only ever goes up. Rates are derived in PromQL with rate(), so the
# app never has to compute "requests per second" itself.
REQUESTS = Counter(
    "tack_http_requests_total",
    "HTTP requests handled, by route template and status code.",
    ["method", "path", "status"],
)

# A Histogram buckets observations so Prometheus can estimate percentiles.
# The buckets are chosen around what this API actually does: most calls are a
# few SQLite reads, so the interesting detail lives between 5ms and 250ms.
LATENCY = Histogram(
    "tack_http_request_duration_seconds",
    "Wall-clock time to handle a request.",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

# --- app-specific ----------------------------------------------------------
# A Gauge goes up and down — it is a reading, not a total.
WS_CONNECTIONS = Gauge("tack_websocket_connections", "Board sockets currently open.")
WS_ROOMS = Gauge("tack_websocket_rooms", "Boards with at least one viewer.")

COMMENTS_CREATED = Counter("tack_comments_created_total", "Comments created over the socket.")
SIGNUPS = Counter("tack_signups_total", "Accounts created.")


async def track_requests(request: Request, call_next):
    """Middleware: count and time every request."""
    started = time.perf_counter()
    status = 500  # if call_next raises, that is what the client sees
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        # route.path is the TEMPLATE — "/boards/{board_id}", not "/boards/417".
        # Labelling with the raw URL would mint a brand-new time series for
        # every board id in the database and eventually take Prometheus down.
        # This is the most common way people break their own monitoring.
        route = request.scope.get("route")
        path = getattr(route, "path", "__unmatched__")
        REQUESTS.labels(request.method, path, str(status)).inc()
        LATENCY.labels(request.method, path).observe(time.perf_counter() - started)


def start_metrics_server(port: int) -> None:
    """Serve /metrics on its own port, in a background thread."""
    if port <= 0:  # set METRICS_PORT=0 to switch it off
        return
    try:
        start_http_server(port)
    except OSError:
        # `uvicorn --reload` can run the lifespan twice; the second bind fails
        # and does not matter
        pass
