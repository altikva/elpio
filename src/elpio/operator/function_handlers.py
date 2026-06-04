# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: kopf handlers for ``ElpioFunction``.

"""kopf handlers for ``ElpioFunction``.

Render the build PipelineRun + the derived ElpioService, own them, and apply.
The ElpioService is itself reconciled by the service handler once the build has
pushed the image, so the chain is: Function → (PipelineRun, ElpioService) →
Knative/KEDA objects.
"""

from __future__ import annotations

from typing import Any, Dict

import kopf

from elpio.function import render_function
from elpio.k8s import apply_object
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
    parsed = FunctionSpec.from_cr(dict(spec))
    owner = _owner_reference(name, meta["uid"])

    objects = render_function(name, namespace, parsed, owner=owner)
    for obj in objects:
        apply_object(obj)
        logger.info("reconciled function child %s/%s", obj["kind"], obj["metadata"]["name"])

    patch.status["image"] = parsed.image
    patch.status["build"] = f"{name}-build"
    patch.status["observedGeneration"] = meta.get("generation")
    patch.status["ready"] = True
    return {"image": parsed.image, "objects": len(objects)}
