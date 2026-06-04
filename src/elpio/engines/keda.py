# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: KEDA engine — the lighter-weight alternative to Knative.

"""KEDA engine — the lighter-weight alternative to Knative.

Renders a plain Deployment + Service + KEDA ScaledObject. This is the
incremental path for clusters that don't want the full Knative networking layer.

NOTE: a CPU/memory trigger cannot scale to zero. True request-driven
scale-to-zero with KEDA needs the **keda-http-add-on** (an HTTPScaledObject +
interceptor). That is tracked for Phase 1 of the bake-off; this
renderer currently emits a CPU-triggered ScaledObject as the portable baseline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elpio.engines.base import ServingEngine, container_resources
from elpio.models.service import ElpioServiceSpec


class KedaEngine(ServingEngine):
    name = "keda"

    def render(
        self,
        name: str,
        namespace: str,
        spec: ElpioServiceSpec,
        owner: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        labels = {
            "app.kubernetes.io/managed-by": "elpio",
            "elpio.io/service": name,
            "app": name,
        }

        container: Dict[str, Any] = {
            "name": name,
            "image": str(spec.image),
            "ports": [{"containerPort": spec.port}],
        }
        if spec.env:
            container["env"] = [{"name": e.name, "value": e.value} for e in spec.env]
        container.update(container_resources(spec))
        if spec.readinessProbe:
            container["readinessProbe"] = {
                "httpGet": {"path": spec.readinessProbe.path, "port": spec.port}
            }

        pod_spec: Dict[str, Any] = {"containers": [container]}
        if spec.serviceAccount:
            pod_spec["serviceAccountName"] = spec.serviceAccount

        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "replicas": max(spec.scaling.minScale, 0),
                "selector": {"matchLabels": {"app": name}},
                "template": {
                    "metadata": {"labels": labels},
                    "spec": pod_spec,
                },
            },
        }
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "selector": {"app": name},
                "ports": [{"port": spec.port, "targetPort": spec.port}],
            },
        }
        scaled_object = {
            "apiVersion": "keda.sh/v1alpha1",
            "kind": "ScaledObject",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "scaleTargetRef": {"name": name},
                "minReplicaCount": spec.scaling.minScale,
                "maxReplicaCount": spec.scaling.maxScale or 10,
                "triggers": [
                    {
                        "type": "cpu",
                        "metricType": "Utilization",
                        "metadata": {
                            "value": str(
                                spec.scaling.target
                                if spec.scaling.metric == "cpu"
                                else 80
                            )
                        },
                    }
                ],
            },
        }

        objects = [deployment, service, scaled_object]
        if owner:
            for o in objects:
                o["metadata"]["ownerReferences"] = [owner]
        return objects

    def url_for(self, name: str, namespace: str) -> str:
        return f"http://{name}.{namespace}.svc.cluster.local"
