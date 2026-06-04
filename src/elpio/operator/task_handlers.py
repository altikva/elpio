# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: kopf handlers for ``ElpioTask``.

"""kopf handlers for ``ElpioTask``.

Render the dispatcher Deployment + KEDA ScaledObject (+ CronJob when scheduled),
own them, and server-side apply. Same declarative model as the other handlers.
"""

from __future__ import annotations

from typing import Any, Dict

import kopf

from elpio.k8s import apply_object
from elpio.models.task import GROUP, PLURAL, VERSION, TaskSpec
from elpio.task import render_task


def _owner_reference(name: str, uid: str) -> Dict[str, Any]:
    return {
        "apiVersion": f"{GROUP}/{VERSION}",
        "kind": "ElpioTask",
        "name": name,
        "uid": uid,
        "controller": True,
        "blockOwnerDeletion": True,
    }


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
@kopf.on.resume(GROUP, VERSION, PLURAL)
def reconcile_task(spec, meta, name, namespace, patch, logger, **_):
    parsed = TaskSpec.from_cr(dict(spec))
    owner = _owner_reference(name, meta["uid"])

    objects = render_task(name, namespace, parsed, owner=owner)
    for obj in objects:
        apply_object(obj)
        logger.info("reconciled task child %s/%s", obj["kind"], obj["metadata"]["name"])

    patch.status["queue"] = parsed.queue
    patch.status["scheduled"] = bool(parsed.schedule)
    patch.status["observedGeneration"] = meta.get("generation")
    patch.status["ready"] = True
    return {"queue": parsed.queue, "objects": len(objects)}
