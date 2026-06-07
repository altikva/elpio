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

from elpio.engines.base import (
    ServingEngine,
    container_env,
    container_env_from,
    container_resources,
    external_secret,
)
from elpio.models.service import ElpioServiceSpec, TrafficTarget

_LABEL_MANAGED = {"app.kubernetes.io/managed-by": "elpio"}


def _traffic_target(t: TrafficTarget) -> Dict[str, Any]:
    """Render one ElpioService traffic entry as a Knative traffic target."""
    out: Dict[str, Any] = {"percent": t.percent}
    if t.revisionName is not None:
        out["revisionName"] = t.revisionName
    else:
        out["latestRevision"] = bool(t.latestRevision)
    if t.tag is not None:
        out["tag"] = t.tag
    return out


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
            container["env"] = [container_env(e) for e in spec.env]
        if spec.envFrom:
            container["envFrom"] = [container_env_from(f) for f in spec.envFrom]
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

        service_spec: Dict[str, Any] = {
            "template": {
                "metadata": {"annotations": annotations},
                "spec": template_spec,
            }
        }

        # When the spec pins traffic across revisions, emit it as the Knative
        # Service's spec.traffic. Left unset, Knative implicitly routes 100% to
        # the latest revision (today's behavior). The KEDA engine ignores
        # traffic entirely: it has no revision model to split across.
        if spec.traffic:
            service_spec["traffic"] = [_traffic_target(t) for t in spec.traffic]

        obj: Dict[str, Any] = {
            "apiVersion": "serving.knative.dev/v1",
            "kind": "Service",
            "metadata": {"name": name, "namespace": namespace, "labels": labels},
            "spec": service_spec,
        }

        objects: List[Dict[str, Any]] = [obj]

        # External Secrets: sync each referenced external store into a k8s Secret
        # that env / envFrom can then consume. Rendered as sibling objects so they
        # are owned (and GC'd) alongside the Service.
        for es in spec.externalSecrets:
            objects.append(external_secret(es, namespace, labels))

        # A custom ingress host maps to a Knative DomainMapping pointing at this
        # Service. When TLS is requested we also wire up a cert-manager
        # Certificate and reference its secret from the DomainMapping.
        if spec.ingress.host:
            host = spec.ingress.host
            tls_secret = f"{name}-tls"
            mapping: Dict[str, Any] = {
                "apiVersion": "serving.knative.dev/v1beta1",
                "kind": "DomainMapping",
                "metadata": {"name": host, "namespace": namespace, "labels": labels},
                "spec": {
                    "ref": {
                        "name": name,
                        "kind": "Service",
                        "apiVersion": "serving.knative.dev/v1",
                    }
                },
            }
            if spec.ingress.tls:
                mapping["spec"]["tls"] = {"secretName": tls_secret}
                # TODO: the issuer should be configurable (per-tenant/global
                # default) rather than hard-coded to a cluster "letsencrypt".
                certificate: Dict[str, Any] = {
                    "apiVersion": "cert-manager.io/v1",
                    "kind": "Certificate",
                    "metadata": {"name": host, "namespace": namespace, "labels": labels},
                    "spec": {
                        "secretName": tls_secret,
                        "dnsNames": [host],
                        "issuerRef": {
                            "name": "letsencrypt",
                            "kind": "ClusterIssuer",
                            "group": "cert-manager.io",
                        },
                    },
                }
                objects.append(mapping)
                objects.append(certificate)
            else:
                objects.append(mapping)

        if owner:
            for o in objects:
                o["metadata"]["ownerReferences"] = [owner]
        return objects

    def url_for(self, name: str, namespace: str) -> str:
        # The authoritative URL comes from the KnativeService status; this is a
        # cluster-local fallback for status before the route is provisioned.
        return f"http://{name}.{namespace}.svc.cluster.local"
