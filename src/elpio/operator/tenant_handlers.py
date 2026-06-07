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

import kopf

from elpio.models.tenant import GROUP, PLURAL, VERSION, TenantSpec
from elpio.operator.common import apply_all, owner_reference
from elpio.status import condition, merge_conditions, now_rfc3339
from elpio.tenant import render_tenant


@kopf.on.create(GROUP, VERSION, PLURAL)
@kopf.on.update(GROUP, VERSION, PLURAL)
@kopf.on.resume(GROUP, VERSION, PLURAL)
def reconcile_tenant(spec, meta, name, patch, logger, status, **_):
    parsed = TenantSpec.from_cr(dict(spec))
    owner = owner_reference("ElpioTenant", name, meta["uid"])

    objects = render_tenant(name, parsed, owner=owner)
    apply_all(objects, logger, "tenant child")

    ns = parsed.namespace_for(name)
    patch.status["namespace"] = ns
    patch.status["observedGeneration"] = meta.get("generation")
    patch.status["ready"] = True
    patch.status["conditions"] = merge_conditions(
        status.get("conditions"),
        [condition("Ready", True, reason="Reconciled", message=f"namespace {ns} provisioned")],
        now_rfc3339(),
    )
    return {"namespace": ns, "objects": len(objects)}
