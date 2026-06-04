# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Pure render of an ``ElpioFunction`` into build + serve objects.

"""Pure render of an ``ElpioFunction`` into build + serve objects.

Returns two objects: a Tekton ``PipelineRun`` that builds the source into an
image with Cloud Native Buildpacks (against an ``elpio-buildpacks`` Pipeline the
platform installs), and the ``ElpioService`` that runs that image. Spec in →
object dicts out, no cluster calls, so it is unit-testable without a cluster.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elpio.models.function import FunctionSpec

_MANAGED = {"app.kubernetes.io/managed-by": "elpio"}
_PIPELINE = "elpio-buildpacks"


def _pipeline_run(name: str, namespace: str, spec: FunctionSpec, labels: Dict[str, str]) -> Dict[str, Any]:
    params: List[Dict[str, str]] = [
        {"name": "APP_IMAGE", "value": spec.image},
        {"name": "BUILDER_IMAGE", "value": spec.builder},
    ]
    if spec.source.git:
        params.append({"name": "SOURCE_URL", "value": spec.source.git.url})
        params.append({"name": "SOURCE_REVISION", "value": spec.source.git.revision})
        if spec.source.git.subPath:
            params.append({"name": "SOURCE_SUBPATH", "value": spec.source.git.subPath})
    elif spec.source.archive:
        params.append({"name": "SOURCE_ARCHIVE", "value": spec.source.archive})

    return {
        "apiVersion": "tekton.dev/v1",
        "kind": "PipelineRun",
        "metadata": {"name": f"{name}-build", "namespace": namespace, "labels": labels},
        "spec": {
            "pipelineRef": {"name": _PIPELINE},
            "params": params,
            "workspaces": [
                {
                    "name": "source",
                    "volumeClaimTemplate": {
                        "spec": {
                            "accessModes": ["ReadWriteOnce"],
                            "resources": {"requests": {"storage": "1Gi"}},
                        }
                    },
                }
            ],
        },
    }


def _elpio_service(name: str, namespace: str, spec: FunctionSpec, labels: Dict[str, str]) -> Dict[str, Any]:
    svc_spec: Dict[str, Any] = {
        "image": spec.image,
        "port": spec.port,
        "scaling": spec.scaling.model_dump(),
    }
    if spec.env:
        svc_spec["env"] = [{"name": e.name, "value": e.value} for e in spec.env]
    if spec.serviceAccount:
        svc_spec["serviceAccount"] = spec.serviceAccount
    return {
        "apiVersion": "elpio.io/v1alpha1",
        "kind": "ElpioService",
        "metadata": {"name": name, "namespace": namespace, "labels": labels},
        "spec": svc_spec,
    }


def _with_owner(obj: Dict[str, Any], owner: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if owner:
        obj["metadata"]["ownerReferences"] = [owner]
    return obj


def render_pipeline_run(
    name: str, namespace: str, spec: FunctionSpec, owner: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    labels = {**_MANAGED, "elpio.io/function": name}
    return _with_owner(_pipeline_run(name, namespace, spec, labels), owner)


def render_service(
    name: str, namespace: str, spec: FunctionSpec, owner: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    labels = {**_MANAGED, "elpio.io/function": name}
    return _with_owner(_elpio_service(name, namespace, spec, labels), owner)


def render_function(
    name: str,
    namespace: str,
    spec: FunctionSpec,
    owner: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    return [
        render_pipeline_run(name, namespace, spec, owner),
        render_service(name, namespace, spec, owner),
    ]


def pipelinerun_phase(status: Optional[Dict[str, Any]]) -> str:
    """Map a Tekton PipelineRun ``.status`` to a coarse phase.

    Returns ``Succeeded``/``Failed`` from the terminal ``Succeeded`` condition,
    ``Running`` while it is in progress, or ``Pending`` before the status exists.
    """
    for cond in (status or {}).get("conditions") or []:
        if cond.get("type") == "Succeeded":
            return {"True": "Succeeded", "False": "Failed"}.get(cond.get("status"), "Running")
    return "Pending"


def next_action(phase: str, service_applied: bool) -> str:
    """Decide what the reconciler should do given the build phase.

    ``apply`` (build done, service not yet created), ``fail`` (build failed),
    ``noop`` (already applied), or ``wait`` (still building).
    """
    if phase == "Succeeded":
        return "noop" if service_applied else "apply"
    if phase == "Failed":
        return "fail"
    return "wait"
