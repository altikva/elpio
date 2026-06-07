# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-07
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Prometheus metrics for the Elpio operator.

"""Prometheus metrics for the Elpio operator.

A tiny, dependency-light surface so the operator is observable: a counter of
reconcile outcomes, a histogram of how long a reconcile takes, and a gauge of
how many ElpioServices currently report Ready. The recording helpers are pure
(they only touch the in-process registry), so they unit-test without a running
server. ``start_metrics_server`` is opt-in via ``ELPIO_METRICS=1`` and binds an
HTTP exporter on ``ELPIO_METRICS_PORT`` (default 9095).
"""

from __future__ import annotations

import logging
import os

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger("elpio.metrics")

DEFAULT_METRICS_PORT = 9095

# elpio_reconcile_total{kind,result}: every reconcile attempt, labelled by the
# CR kind ("ElpioService", "ElpioFunction", ...) and its outcome
# ("success" / "error").
RECONCILE_TOTAL = Counter(
    "elpio_reconcile_total",
    "Total ElpioService/Function/Task reconcile attempts.",
    ["kind", "result"],
)

# elpio_reconcile_duration_seconds{kind}: wall-clock time spent in a reconcile.
RECONCILE_DURATION = Histogram(
    "elpio_reconcile_duration_seconds",
    "Time spent reconciling an Elpio CR.",
    ["kind"],
)

# elpio_services_ready: how many ElpioServices currently report Ready=True.
SERVICES_READY = Gauge(
    "elpio_services_ready",
    "Number of ElpioServices currently reporting Ready.",
)


def record_reconcile(kind: str, result: str, seconds: float | None = None) -> None:
    """Record one reconcile outcome (and, if given, its duration).

    Pure with respect to the cluster: it only mutates the in-process Prometheus
    registry, so tests can read the counter/histogram values back directly.
    """
    RECONCILE_TOTAL.labels(kind=kind, result=result).inc()
    if seconds is not None:
        RECONCILE_DURATION.labels(kind=kind).observe(seconds)


def set_services_ready(count: int) -> None:
    """Set the gauge of currently-ready ElpioServices."""
    SERVICES_READY.set(count)


def metrics_enabled() -> bool:
    """True when metrics are opted in via ``ELPIO_METRICS=1``."""
    return os.environ.get("ELPIO_METRICS", "").strip() in ("1", "true", "True", "yes")


def metrics_port() -> int:
    """The exporter port from ``ELPIO_METRICS_PORT`` (default 9095)."""
    raw = os.environ.get("ELPIO_METRICS_PORT", "").strip()
    if not raw:
        return DEFAULT_METRICS_PORT
    try:
        return int(raw)
    except ValueError:
        logger.warning("ELPIO_METRICS_PORT=%r is not an int; using %d", raw, DEFAULT_METRICS_PORT)
        return DEFAULT_METRICS_PORT


def start_metrics_server(port: int | None = None) -> bool:
    """Start the Prometheus HTTP exporter unless metrics are disabled.

    Returns True if the server was started. A no-op (returns False) when
    ``ELPIO_METRICS`` is not set, so importing this module never opens a socket.
    """
    if not metrics_enabled():
        return False

    # Imported lazily so the module import stays socket-free for unit tests.
    from prometheus_client import start_http_server

    bind_port = port if port is not None else metrics_port()
    start_http_server(bind_port)
    logger.info("elpio metrics exporter listening on :%d", bind_port)
    return True
