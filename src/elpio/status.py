# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-05
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Kubernetes-style ``status.conditions`` for Elpio custom
#              resources.

"""Kubernetes-style ``status.conditions`` for Elpio custom resources.

Elpio's CRs reconcile down to Knative/KEDA primitives, and tools that supervise
them (e.g. Spero's elpio-service/-function/-task probes) read a standard
``conditions[]`` array with a ``Ready`` condition. These helpers build and merge
that array idiomatically: ``lastTransitionTime`` only moves when the status flips.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def now_rfc3339() -> str:
    """Current UTC time as an RFC3339 string (``...Z``), for lastTransitionTime."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def condition(cond_type: str, ok: bool, *, reason: str = "", message: str = "") -> Dict[str, Any]:
    """A single condition (without a timestamp; merge_conditions stamps it)."""
    return {
        "type": cond_type,
        "status": "True" if ok else "False",
        "reason": reason or ("Ready" if ok else "NotReady"),
        "message": message,
    }


def merge_conditions(
    existing: Optional[List[Dict[str, Any]]],
    updates: List[Dict[str, Any]],
    now: str,
) -> List[Dict[str, Any]]:
    """Apply ``updates`` onto ``existing`` conditions, keyed by ``type``.

    A condition whose status is unchanged keeps its previous
    ``lastTransitionTime``; a new or flipped condition gets ``now``. Conditions
    not in ``updates`` are preserved.
    """
    existing = [c for c in (existing or []) if isinstance(c, dict)]
    by_type = {c.get("type"): c for c in existing}
    updating = {c["type"] for c in updates}

    out = [c for c in existing if c.get("type") not in updating]
    for cond in updates:
        prev = by_type.get(cond["type"])
        if prev and prev.get("status") == cond["status"] and prev.get("lastTransitionTime"):
            stamp = prev["lastTransitionTime"]
        else:
            stamp = now
        out.append({**cond, "lastTransitionTime": stamp})
    return out
