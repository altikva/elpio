# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Knative Serving engine — the default, highest Cloud Run parity.

"""Knative Serving engine — the default, highest Cloud Run parity.

Renders an ElpioService into a single ``serving.knative.dev/v1`` Service.
Knative's KPA gives scale-to-zero, request/concurrency autoscaling, revisions,
traffic splitting and request buffering during cold start out of the box.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elpio.engines.base import ServingEngine, container_resources
from elpio.models.service import ElpioServiceSpec

_LABEL_MANAGED = {"app.kubernetes.io/managed-by": "elpio"}


class KnativeEngine(ServingEngine):
    name = "knative"

    def render(
        self,
        name: str,
        namespace: str,
        spec: ElpioServiceSpec,
        owner: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        annotations = {
            "autoscaling.knative.dev/class": "kpa.autoscaling.knative.dev",
            "autoscaling.knative.dev/min-scale": str(spec.scaling.minScale),
            "autoscaling.knative.dev/metric": spec.scaling.metric,
            "autoscaling.knative.dev/target": str(spec.scaling.target),
        }
        if spec.scaling.maxScale:
            annotations["autoscaling.knative.dev/max-scale"] = str(spec.scaling.maxScale)

        container: Dict[str, Any] = {
            "image": str(spec.image),
            "ports": [{"containerPort": spec.port}],
        }
        if spec.env:
            container["env"] = [{"name": e.name, "value": e.value} for e in spec.env]
        container.update(container_resources(spec))
        if spec.readinessProbe:
            probe: Dict[str, Any] = {
                "httpGet": {"path": spec.readinessProbe.path, "port": spec.port}
            }
            if spec.readinessProbe.initialDelaySeconds is not None:
                probe["initialDelaySeconds"] = spec.readinessProbe.initialDelaySeconds
            if spec.readinessProbe.periodSeconds is not None:
                probe["periodSeconds"] = spec.readinessProbe.periodSeconds
            container["readinessProbe"] = probe

        labels = {**_LABEL_MANAGED, "elpio.io/service": name}
        if spec.ingress.visibility == "cluster-local":
            labels["networking.knative.dev/visibility"] = "cluster-local"

        template_spec: Dict[str, Any] = {"containers": [container]}
        if spec.serviceAccount:
            template_spec["serviceAccountName"] = spec.serviceAccount
        if spec.scaling.metric == "concurrency":
            template_spec["containerConcurrency"] = spec.scaling.target

        obj: Dict[str, Any] = {
            "apiVersion": "serving.knative.dev/v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "template": {
                    "metadata": {"annotations": annotations},
                    "spec": template_spec,
                }
            },
        }
        if owner:
            obj["metadata"]["ownerReferences"] = [owner]
        return [obj]

    def url_for(self, name: str, namespace: str) -> str:
        # The authoritative URL comes from the KnativeService status; this is a
        # cluster-local fallback for status before the route is provisioned.
        return f"http://{name}.{namespace}.svc.cluster.local"
