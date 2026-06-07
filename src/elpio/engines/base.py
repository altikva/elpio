# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Serving-engine interface + selector.

"""Serving-engine interface + selector."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from elpio.models.service import (
    ElpioServiceSpec,
    EnvFromSource,
    EnvVar,
    ExternalSecret,
    ResourceUnits,
)


class ServingEngine(ABC):
    """Renders an ElpioService spec into concrete Kubernetes objects."""

    name: str

    @abstractmethod
    def render(
        self,
        name: str,
        namespace: str,
        spec: ElpioServiceSpec,
        owner: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Return the list of Kubernetes objects to server-side apply."""

    @abstractmethod
    def url_for(self, name: str, namespace: str) -> str:
        """Best-effort in-cluster URL for the service (for ``.status.url``)."""


def get_engine(name: Optional[str] = None) -> ServingEngine:
    """Resolve the active engine from an explicit name or ``ELPIO_ENGINE``."""
    name = (name or os.getenv("ELPIO_ENGINE", "knative")).lower()
    if name == "knative":
        from elpio.engines.knative import KnativeEngine

        return KnativeEngine()
    if name == "keda":
        from elpio.engines.keda import KedaEngine

        return KedaEngine()
    raise ValueError(
        f"unknown ELPIO_ENGINE {name!r} (expected 'knative' or 'keda')"
    )


def resource_units(u: ResourceUnits) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if u.cpu is not None:
        out["cpu"] = str(u.cpu)
    if u.memory is not None:
        out["memory"] = str(u.memory)
    return out


def container_env(e: EnvVar) -> Dict[str, Any]:
    """Render one env entry: a literal value or a Secret/ConfigMap reference."""
    if e.value is not None:
        return {"name": e.name, "value": e.value}
    src = e.valueFrom
    sel = src.secretKeyRef or src.configMapKeyRef
    key = "secretKeyRef" if src.secretKeyRef else "configMapKeyRef"
    ref: Dict[str, Any] = {"name": sel.name, "key": sel.key}
    if sel.optional is not None:
        ref["optional"] = sel.optional
    return {"name": e.name, "valueFrom": {key: ref}}


def container_env_from(f: EnvFromSource) -> Dict[str, Any]:
    """Render one envFrom entry: bulk-inject a Secret or ConfigMap."""
    ref_obj = f.secretRef or f.configMapRef
    key = "secretRef" if f.secretRef else "configMapRef"
    ref: Dict[str, Any] = {"name": ref_obj.name}
    if ref_obj.optional is not None:
        ref["optional"] = ref_obj.optional
    out: Dict[str, Any] = {key: ref}
    if f.prefix is not None:
        out["prefix"] = f.prefix
    return out


def external_secret(
    es: ExternalSecret, namespace: str, labels: Dict[str, Any]
) -> Dict[str, Any]:
    """Render an External Secrets Operator ExternalSecret CR.

    The operator materializes it into a Kubernetes Secret named ``secretName``
    (default: the ExternalSecret name) that env / envFrom can then consume.
    """
    spec: Dict[str, Any] = {
        "refreshInterval": es.refreshInterval,
        "secretStoreRef": {"name": es.storeRef, "kind": es.storeKind},
        "target": {"name": es.secretName or es.name},
    }
    if es.data:
        spec["data"] = [
            {
                "secretKey": d.secretKey,
                "remoteRef": (
                    {"key": d.remoteKey, "property": d.remoteProperty}
                    if d.remoteProperty is not None
                    else {"key": d.remoteKey}
                ),
            }
            for d in es.data
        ]
    return {
        "apiVersion": "external-secrets.io/v1beta1",
        "kind": "ExternalSecret",
        "metadata": {"name": es.name, "namespace": namespace, "labels": labels},
        "spec": spec,
    }


def container_resources(spec: ElpioServiceSpec) -> Dict[str, Any]:
    if not spec.resources:
        return {}
    res: Dict[str, Any] = {}
    if spec.resources.requests:
        res["requests"] = resource_units(spec.resources.requests)
    if spec.resources.limits:
        res["limits"] = resource_units(spec.resources.limits)
    return {"resources": res} if res else {}
