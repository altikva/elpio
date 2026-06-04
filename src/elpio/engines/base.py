"""Serving-engine interface + selector."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from elpio.models.service import ElpioServiceSpec, ResourceUnits


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


def container_resources(spec: ElpioServiceSpec) -> Dict[str, Any]:
    if not spec.resources:
        return {}
    res: Dict[str, Any] = {}
    if spec.resources.requests:
        res["requests"] = resource_units(spec.resources.requests)
    if spec.resources.limits:
        res["limits"] = resource_units(spec.resources.limits)
    return {"resources": res} if res else {}
