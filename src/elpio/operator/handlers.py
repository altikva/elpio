# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: kopf handlers for ``ElpioService``.

"""kopf handlers for ``ElpioService``.

Reconciliation is declarative: parse the CR spec, render engine objects, and
server-side apply them with the ElpioService as their owner — so Kubernetes
garbage-collects the children when the ElpioService is deleted (no explicit
teardown handler needed). This is a declarative operator model: continuous
reconciliation rather than one-shot, imperative ``kubectl apply``.

``Ready`` mirrors the rendered child's own readiness rather than being set
optimistically: the apply only kicks the engine, so right after it the Knative
Service / KEDA autoscaler is still progressing. ``reconcile`` reports ``Ready``
only once the child says so, and ``settle_service`` re-checks on a timer until
it converges.
"""

from __future__ import annotations

import time
from typing import Tuple

import kopf

from elpio.engines.base import ServingEngine, get_engine
from elpio.k8s import get_object
from elpio.models.service import GROUP, PLURAL, VERSION, ElpioServiceSpec
from elpio.operator import metrics
from elpio.operator.common import apply_all, child_ready, owner_reference
from elpio.status import condition, merge_conditions, now_rfc3339


def _primary_child_ref(engine: ServingEngine, spec: ElpioServiceSpec) -> Tuple[str, str]:
    """``(api_version, kind)`` of the child whose readiness gates ``Ready``.

    Knative serves through a single ``Service``; KEDA's request-driven path
    fronts the Deployment with an ``HTTPScaledObject`` while the cpu path uses a
    plain ``ScaledObject``. Each exposes a ``Ready`` condition we can read back.
    """
    if engine.name == "keda":
        if spec.scaling.metric in ("concurrency", "rps"):
            return "http.keda.sh/v1alpha1", "HTTPScaledObject"
        return "keda.sh/v1alpha1", "ScaledObject"
    return "serving.knative.dev/v1", "Service"


def _readiness_conditions(status, ready: bool, engine_name: str):
    if ready:
        return merge_conditions(
            status.get("conditions"),
            [condition("Ready", True, reason="Reconciled", message=f"served by the {engine_name} engine")],
            now_rfc3339(),
        )
    return merge_conditions(
        status.get("conditions"),
        [condition("Ready", False, reason="Progressing", message=f"waiting for the {engine_name} child to become Ready")],
        now_rfc3339(),
    )


@kopf.on.startup()
def start_observability(logger, **_):
    """Start the Prometheus metrics exporter when ``ELPIO_METRICS`` is set."""
    if metrics.start_metrics_server():
        logger.info("elpio metrics exporter started")


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
@kopf.on.resume(GROUP, VERSION, PLURAL)
def reconcile(spec, meta, name, namespace, patch, logger, status, body, **_):
    started = time.monotonic()
    try:
        parsed = ElpioServiceSpec.from_cr(dict(spec))
        engine = get_engine()
        owner = owner_reference("ElpioService", name, meta["uid"])

        objects = engine.render(name, namespace, parsed, owner=owner)
        apply_all(objects, logger, f"{engine.name} engine")

        api_version, kind = _primary_child_ref(engine, parsed)
        child = get_object(api_version, kind, name, namespace)
        ready = child_ready(child)

        patch.status["engine"] = engine.name
        patch.status["url"] = engine.url_for(name, namespace)
        patch.status["observedGeneration"] = meta.get("generation")
        patch.status["ready"] = ready
        patch.status["conditions"] = _readiness_conditions(status, ready, engine.name)
    except Exception as exc:
        metrics.record_reconcile("ElpioService", "error", time.monotonic() - started)
        kopf.warn(body, reason="ReconcileFailed", message=f"reconcile failed: {exc}")
        raise

    metrics.record_reconcile("ElpioService", "success", time.monotonic() - started)
    kopf.event(
        body,
        type="Normal",
        reason="Reconciled",
        message=f"served by the {engine.name} engine (ready={ready})",
    )
    return {"engine": engine.name, "objects": len(objects), "ready": ready}


@kopf.timer(GROUP, VERSION, PLURAL, interval=15.0)
def settle_service(spec, status, name, namespace, patch, logger, body, **_):
    """Re-check the rendered child and converge ``Ready`` as it comes up."""
    parsed = ElpioServiceSpec.from_cr(dict(spec))
    engine = get_engine()
    api_version, kind = _primary_child_ref(engine, parsed)
    child = get_object(api_version, kind, name, namespace)
    ready = child_ready(child)

    if ready == status.get("ready"):
        return
    logger.info("ElpioService %s/%s child %s readiness -> %s", namespace, name, kind, ready)
    patch.status["ready"] = ready
    patch.status["conditions"] = _readiness_conditions(status, ready, engine.name)
    kopf.event(
        body,
        type="Normal" if ready else "Warning",
        reason="Ready" if ready else "Progressing",
        message=f"{kind} readiness -> {ready}",
    )


@kopf.on.delete(GROUP, VERSION, PLURAL)
def on_delete(name, namespace, logger, **_):
    # Children are garbage-collected via ownerReferences; just log intent.
    logger.info("deleting ElpioService %s/%s (children GC via owner refs)", namespace, name)


# Importing these modules registers their kopf handlers when the operator loads
# this entrypoint (`kopf run -m elpio.operator.handlers`).
from elpio.operator import (  # noqa: E402,F401
    function_handlers,
    task_handlers,
    tenant_handlers,
)
