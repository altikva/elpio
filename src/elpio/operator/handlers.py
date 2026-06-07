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
"""

from __future__ import annotations

import kopf

from elpio.engines.base import get_engine
from elpio.models.service import GROUP, PLURAL, VERSION, ElpioServiceSpec
from elpio.operator.common import apply_all, owner_reference
from elpio.status import condition, merge_conditions, now_rfc3339


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
@kopf.on.resume(GROUP, VERSION, PLURAL)
def reconcile(spec, meta, name, namespace, patch, logger, status, **_):
    parsed = ElpioServiceSpec.from_cr(dict(spec))
    engine = get_engine()
    owner = owner_reference("ElpioService", name, meta["uid"])

    objects = engine.render(name, namespace, parsed, owner=owner)
    apply_all(objects, logger, f"{engine.name} engine")

    patch.status["engine"] = engine.name
    patch.status["url"] = engine.url_for(name, namespace)
    patch.status["observedGeneration"] = meta.get("generation")
    patch.status["ready"] = True
    patch.status["conditions"] = merge_conditions(
        status.get("conditions"),
        [condition("Ready", True, reason="Reconciled", message=f"served by the {engine.name} engine")],
        now_rfc3339(),
    )
    return {"engine": engine.name, "objects": len(objects)}


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
