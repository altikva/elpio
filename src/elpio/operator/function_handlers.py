# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: kopf handlers for ``ElpioFunction``.

# kopf handlers for ``ElpioFunction``.
#
# Render the build PipelineRun + the derived ElpioService, own them, and apply.
# The ElpioService is itself reconciled by the service handler once the build has
# pushed the image, so the chain is: Function → (PipelineRun, ElpioService) →
# Knative/KEDA objects.


from __future__ import annotations

from typing import Any, Dict

import kopf

from elpio.function import (
    next_action,
    pipelinerun_phase,
    render_pipeline_run,
    render_service,
)
from elpio.k8s import apply_object, get_object
from elpio.models.function import GROUP, PLURAL, VERSION, FunctionSpec


def _owner_reference(name: str, uid: str) -> Dict[str, Any]:
    return {
        "apiVersion": f"{GROUP}/{VERSION}",
        "kind": "ElpioFunction",
        "name": name,
        "uid": uid,
        "controller": True,
        "blockOwnerDeletion": True,
    }


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
@kopf.on.resume(GROUP, VERSION, PLURAL)
def reconcile_function(spec, meta, name, namespace, patch, logger, **_):
    """Kick off the build. The ElpioService is created later, once it succeeds."""
    parsed = FunctionSpec.from_cr(dict(spec))
    owner = _owner_reference(name, meta["uid"])

    apply_object(render_pipeline_run(name, namespace, parsed, owner=owner))
    logger.info("started build %s-build for function %s/%s", name, namespace, name)

    patch.status["image"] = parsed.image
    patch.status["build"] = f"{name}-build"
    patch.status["phase"] = "Building"
    patch.status["observedGeneration"] = meta.get("generation")
    patch.status["ready"] = False
    return {"image": parsed.image, "phase": "Building"}


@kopf.timer(GROUP, VERSION, PLURAL, interval=15.0)
def settle_function(spec, status, meta, name, namespace, patch, logger, **_):
    """Poll the build; publish the ElpioService only once it has succeeded."""
    if status.get("serviceApplied"):
        return
    pr = get_object("tekton.dev/v1", "PipelineRun", f"{name}-build", namespace)
    phase = pipelinerun_phase((pr or {}).get("status"))
    action = next_action(phase, bool(status.get("serviceApplied")))

    if action == "apply":
        parsed = FunctionSpec.from_cr(dict(spec))
        owner = _owner_reference(name, meta["uid"])
        apply_object(render_service(name, namespace, parsed, owner=owner))
        logger.info("build for %s/%s succeeded; published ElpioService", namespace, name)
        patch.status["serviceApplied"] = True
        patch.status["phase"] = "Ready"
        patch.status["ready"] = True
    elif action == "fail":
        patch.status["phase"] = "BuildFailed"
        patch.status["ready"] = False
    else:
        patch.status["phase"] = "Building"
