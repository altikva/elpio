# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-07
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the operator metrics surface.

"""Unit tests for the operator metrics surface.

The recording helpers are pure with respect to the cluster: they only touch the
in-process Prometheus registry, so we read the counter/histogram/gauge values
straight back instead of scraping an HTTP endpoint.
"""

from prometheus_client import REGISTRY

from elpio.operator import metrics


def _counter(kind: str, result: str) -> float:
    value = REGISTRY.get_sample_value(
        "elpio_reconcile_total", {"kind": kind, "result": result}
    )
    return value or 0.0


def _hist_count(kind: str) -> float:
    value = REGISTRY.get_sample_value(
        "elpio_reconcile_duration_seconds_count", {"kind": kind}
    )
    return value or 0.0


def test_record_reconcile_increments_success_counter():
    before = _counter("ElpioService", "success")
    metrics.record_reconcile("ElpioService", "success", 0.5)
    assert _counter("ElpioService", "success") == before + 1


def test_record_reconcile_increments_error_counter_separately():
    ok_before = _counter("ElpioService", "success")
    err_before = _counter("ElpioService", "error")
    metrics.record_reconcile("ElpioService", "error", 1.0)
    assert _counter("ElpioService", "error") == err_before + 1
    assert _counter("ElpioService", "success") == ok_before  # untouched


def test_record_reconcile_labels_by_kind():
    before = _counter("ElpioFunction", "success")
    metrics.record_reconcile("ElpioFunction", "success", 0.1)
    assert _counter("ElpioFunction", "success") == before + 1


def test_record_reconcile_observes_duration():
    before = _hist_count("ElpioService")
    metrics.record_reconcile("ElpioService", "success", 0.25)
    assert _hist_count("ElpioService") == before + 1


def test_record_reconcile_without_duration_skips_histogram():
    before = _hist_count("ElpioTask")
    metrics.record_reconcile("ElpioTask", "success")
    # counter still moves, histogram does not
    assert _counter("ElpioTask", "success") >= 1
    assert _hist_count("ElpioTask") == before


def test_set_services_ready_gauge():
    metrics.set_services_ready(3)
    assert REGISTRY.get_sample_value("elpio_services_ready") == 3
    metrics.set_services_ready(0)
    assert REGISTRY.get_sample_value("elpio_services_ready") == 0


def test_metrics_enabled_reads_env(monkeypatch):
    monkeypatch.delenv("ELPIO_METRICS", raising=False)
    assert metrics.metrics_enabled() is False
    monkeypatch.setenv("ELPIO_METRICS", "1")
    assert metrics.metrics_enabled() is True
    monkeypatch.setenv("ELPIO_METRICS", "true")
    assert metrics.metrics_enabled() is True
    monkeypatch.setenv("ELPIO_METRICS", "0")
    assert metrics.metrics_enabled() is False


def test_metrics_port_default(monkeypatch):
    monkeypatch.delenv("ELPIO_METRICS_PORT", raising=False)
    assert metrics.metrics_port() == metrics.DEFAULT_METRICS_PORT


def test_metrics_port_from_env(monkeypatch):
    monkeypatch.setenv("ELPIO_METRICS_PORT", "9123")
    assert metrics.metrics_port() == 9123


def test_metrics_port_bad_value_falls_back(monkeypatch):
    monkeypatch.setenv("ELPIO_METRICS_PORT", "not-a-port")
    assert metrics.metrics_port() == metrics.DEFAULT_METRICS_PORT


def test_start_metrics_server_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("ELPIO_METRICS", raising=False)
    # Must not open a socket; returns False.
    assert metrics.start_metrics_server() is False
