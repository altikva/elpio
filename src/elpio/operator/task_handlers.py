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

import kopf

from elpio.models.task import GROUP, PLURAL, VERSION, TaskSpec
from elpio.operator.common import apply_all, owner_reference
from elpio.status import condition, merge_conditions, now_rfc3339
from elpio.task import render_task


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
@kopf.on.resume(GROUP, VERSION, PLURAL)
def reconcile_task(spec, meta, name, namespace, patch, logger, status, **_):
    parsed = TaskSpec.from_cr(dict(spec))
    owner = owner_reference("ElpioTask", name, meta["uid"])

    objects = render_task(name, namespace, parsed, owner=owner)
    apply_all(objects, logger, "task child")

    patch.status["queue"] = parsed.queue
    patch.status["scheduled"] = bool(parsed.schedule)
    patch.status["observedGeneration"] = meta.get("generation")
    patch.status["ready"] = True
    patch.status["conditions"] = merge_conditions(
        status.get("conditions"),
        [condition("Ready", True, reason="Reconciled", message=f"dispatcher on queue {parsed.queue}")],
        now_rfc3339(),
    )
    return {"queue": parsed.queue, "objects": len(objects)}
