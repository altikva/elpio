# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Pure admission policy for Elpio resources.

"""Pure admission policy for Elpio resources.

Given a Kubernetes ``AdmissionReview`` request, decide allow/deny and emit any
JSONPatch that enforces Elpio invariants. No cluster calls — fully testable.

Invariants enforced today:
  * ElpioService must declare ``spec.image``.
  * ElpioService images must come from an allowed registry (when configured).
  * ElpioService defaults to scale-to-zero (``spec.scaling.minScale = 0``) when
    the author didn't set it.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _image_repository(image: Any) -> Optional[str]:
    if isinstance(image, dict):
        return image.get("repository")
    if isinstance(image, str):
        return image.split(":", 1)[0]
    return None


def _evaluate(
    kind: str,
    obj: Dict[str, Any],
    allowed_registries: Optional[Sequence[str]],
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    spec = obj.get("spec") or {}
    patches: List[Dict[str, Any]] = []

    if kind == "ElpioService":
        image = spec.get("image")
        repo = _image_repository(image)
        if not repo:
            return False, "spec.image is required", []
        if allowed_registries and not any(repo.startswith(r) for r in allowed_registries):
            return False, f"image registry not allowed: {repo}", []

        scaling = spec.get("scaling")
        if scaling is None:
            patches.append({"op": "add", "path": "/spec/scaling", "value": {"minScale": 0}})
        elif "minScale" not in scaling:
            patches.append({"op": "add", "path": "/spec/scaling/minScale", "value": 0})

    return True, "", patches


def review(
    request: Dict[str, Any],
    allowed_registries: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Build the AdmissionReview response for an incoming AdmissionReview."""
    req = request.get("request") or {}
    uid = req.get("uid", "")
    obj = req.get("object") or {}
    kind = obj.get("kind") or (req.get("kind") or {}).get("kind", "")

    allowed, message, patches = _evaluate(kind, obj, allowed_registries)

    response: Dict[str, Any] = {"uid": uid, "allowed": allowed}
    if message:
        response["status"] = {"message": message}
    if allowed and patches:
        response["patchType"] = "JSONPatch"
        response["patch"] = base64.b64encode(json.dumps(patches).encode()).decode()

    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": response,
    }
