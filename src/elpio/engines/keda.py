# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: KEDA engine — the lighter-weight alternative to Knative.

"""KEDA engine — the lighter-weight alternative to Knative.

Renders a Deployment + Service plus an autoscaler chosen by the scaling metric:

- **concurrency / rps** (request-driven): an ``HTTPScaledObject`` from the
  keda-http-add-on. Traffic flows through the add-on's interceptor, which gives
  true request-driven **scale-to-zero** (0 ↔ N on load). Requires the
  keda-http-add-on in the cluster (``task keda-http-install``).
- **cpu**: a plain KEDA ``ScaledObject`` with a cpu trigger. A cpu/memory trigger
  cannot scale to zero (KEDA's webhook rejects ``minReplicaCount=0``), so the
  floor is 1.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elpio.engines.base import ServingEngine, container_resources
from elpio.models.service import ElpioServiceSpec

# Request-driven metrics route through the keda-http-add-on (scale-to-zero);
# everything else falls back to a cpu-triggered ScaledObject.
_HTTP_METRICS = ("concurrency", "rps")


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
        http = spec.scaling.metric in _HTTP_METRICS

        deployment = self._deployment(name, namespace, spec, labels, http)
        service = self._service(name, namespace, spec, labels)
        autoscaler = (
            self._http_scaled_object(name, namespace, spec, labels)
            if http
            else self._cpu_scaled_object(name, namespace, spec, labels)
        )

        objects = [deployment, service, autoscaler]
        if owner:
            for o in objects:
                o["metadata"]["ownerReferences"] = [owner]
        return objects

    def _deployment(self, name, namespace, spec, labels, http) -> Dict[str, Any]:
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

        # The HTTP add-on can hold the deployment at 0; a cpu ScaledObject can't.
        replicas = spec.scaling.minScale if http else max(spec.scaling.minScale, 1)
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": {"app": name}},
                "template": {"metadata": {"labels": labels}, "spec": pod_spec},
            },
        }

    def _service(self, name, namespace, spec, labels) -> Dict[str, Any]:
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "selector": {"app": name},
                "ports": [{"port": spec.port, "targetPort": spec.port}],
            },
        }

    def _http_scaled_object(self, name, namespace, spec, labels) -> Dict[str, Any]:
        # NB: custom-domain + automatic-TLS (DomainMapping / cert-manager
        # Certificate) is a Knative-engine feature. The KEDA path only uses
        # ingress.host as the interceptor routing host and ignores ingress.tls.
        host = spec.ingress.host or f"{name}.{namespace}"
        if spec.scaling.metric == "rps":
            scaling_metric = {
                "requestRate": {
                    "granularity": "1s",
                    "targetValue": spec.scaling.target,
                    "window": "1m",
                }
            }
        else:  # concurrency
            scaling_metric = {"concurrency": {"targetValue": spec.scaling.target}}

        return {
            "apiVersion": "http.keda.sh/v1alpha1",
            "kind": "HTTPScaledObject",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "hosts": [host],
                "scaleTargetRef": {
                    "name": name,
                    "kind": "Deployment",
                    "apiVersion": "apps/v1",
                    "service": name,
                    "port": spec.port,
                },
                "replicas": {"min": spec.scaling.minScale, "max": spec.scaling.maxScale or 10},
                "scaledownPeriod": 300,
                "scalingMetric": scaling_metric,
            },
        }

    def _cpu_scaled_object(self, name, namespace, spec, labels) -> Dict[str, Any]:
        return {
            "apiVersion": "keda.sh/v1alpha1",
            "kind": "ScaledObject",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": {
                "scaleTargetRef": {"name": name},
                # A cpu/memory trigger cannot scale to zero; KEDA rejects min 0.
                "minReplicaCount": max(spec.scaling.minScale, 1),
                "maxReplicaCount": spec.scaling.maxScale or 10,
                "triggers": [
                    {
                        "type": "cpu",
                        "metricType": "Utilization",
                        "metadata": {"value": str(spec.scaling.target)},
                    }
                ],
            },
        }

    def url_for(self, name: str, namespace: str) -> str:
        return f"http://{name}.{namespace}.svc.cluster.local"
