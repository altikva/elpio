# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: kopf handlers for ``ElpioTenant``.

"""kopf handlers for ``ElpioTenant``.

Same declarative model as the ElpioService handler: render the guardrail objects,
set the (cluster-scoped) Tenant as their owner so deleting the Tenant GCs the
namespace and its contents, server-side apply, and write ``.status``.
"""

from __future__ import annotations

from typing import Any, Dict

import kopf

from elpio.k8s import apply_object
from elpio.models.tenant import GROUP, PLURAL, VERSION, TenantSpec
from elpio.tenant import render_tenant


def _owner_reference(name: str, uid: str) -> Dict[str, Any]:
    return {
        "apiVersion": f"{GROUP}/{VERSION}",
        "kind": "ElpioTenant",
        "name": name,
        "uid": uid,
        "controller": True,
        "blockOwnerDeletion": True,
    }


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
@kopf.on.resume(GROUP, VERSION, PLURAL)
def reconcile_tenant(spec, meta, name, patch, logger, **_):
    parsed = TenantSpec.from_cr(dict(spec))
    owner = _owner_reference(name, meta["uid"])

    objects = render_tenant(name, parsed, owner=owner)
    for obj in objects:
        apply_object(obj)
        logger.info("reconciled tenant child %s/%s", obj["kind"], obj["metadata"]["name"])

    patch.status["namespace"] = parsed.namespace_for(name)
    patch.status["observedGeneration"] = meta.get("generation")
    patch.status["ready"] = True
    return {"namespace": parsed.namespace_for(name), "objects": len(objects)}
