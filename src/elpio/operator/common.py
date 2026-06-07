# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-07
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Shared helpers for the kopf handlers.

"""Shared helpers for the kopf handlers.

Every Elpio CRD handler builds the same controller ``ownerReference`` (so the
rendered children are garbage-collected with their owner) and runs the same
"apply each rendered object and log it" loop. Factor both out here so the
per-CRD handlers only carry their own status/condition logic.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from elpio.k8s import apply_object
from elpio.models.service import GROUP, VERSION


def owner_reference(kind: str, name: str, uid: str) -> Dict[str, Any]:
    """Return the standard controller ownerReference for an Elpio CRD object."""
    return {
        "apiVersion": f"{GROUP}/{VERSION}",
        "kind": kind,
        "name": name,
        "uid": uid,
        "controller": True,
        "blockOwnerDeletion": True,
    }


def apply_all(objects: Iterable[Dict[str, Any]], logger: Any, label: str) -> int:
    """Server-side apply each rendered object, log it, and return the count."""
    count = 0
    for obj in objects:
        apply_object(obj)
        logger.info(
            "reconciled %s %s/%s",
            label,
            obj["kind"],
            obj["metadata"]["name"],
        )
        count += 1
    return count


def child_ready(child: Optional[Dict[str, Any]]) -> bool:
    """True when a child object reports a ``Ready`` condition of ``"True"``.

    Knative Services and KEDA ScaledObject/HTTPScaledObject all expose a
    ``status.conditions[]`` array with a ``Ready`` condition, so the same read
    works across engines. Returns ``False`` when the child is missing, has no
    status yet, or has no ``Ready`` condition (i.e. it is still progressing).
    """
    if not child:
        return False
    conditions = ((child.get("status") or {}).get("conditions")) or []
    for cond in conditions:
        if isinstance(cond, dict) and cond.get("type") == "Ready":
            return cond.get("status") == "True"
    return False
