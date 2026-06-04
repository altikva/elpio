# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Fleet registry + CR gateway seams for the management API.

"""Fleet registry + CR gateway seams for the management API.

The registry tracks which clusters exist (backed by a ``StateStore``); the
gateway authors/reads Custom Resources in a named cluster. Both are interfaces so
the API is testable without a cluster — the in-memory implementations back the
unit tests, and ``KubeCRGateway`` is the real one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from elpio.providers.state import InMemoryStateStore, StateStore

_CLUSTERS = "clusters"


class FleetRegistry:
    def __init__(self, store: Optional[StateStore] = None) -> None:
        self._store = store or InMemoryStateStore()

    def register(self, name: str, info: Dict[str, Any]) -> Dict[str, Any]:
        record = {"name": name, **info}
        self._store.put(_CLUSTERS, name, record)
        return record

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        return self._store.get(_CLUSTERS, name)

    def list(self) -> List[Dict[str, Any]]:
        return self._store.list(_CLUSTERS)


class CRGateway(ABC):
    """Authors/reads Elpio CRs in a target cluster."""

    @abstractmethod
    def list_services(self, cluster: str, namespace: Optional[str] = None) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def apply_service(
        self, cluster: str, name: str, namespace: str, spec: Dict[str, Any]
    ) -> Dict[str, Any]: ...


class InMemoryCRGateway(CRGateway):
    """Reference gateway for tests and single-node dev."""

    def __init__(self) -> None:
        self._svcs: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def list_services(self, cluster: str, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        items = list(self._svcs.get(cluster, {}).values())
        if namespace:
            items = [s for s in items if s["metadata"]["namespace"] == namespace]
        return items

    def apply_service(
        self, cluster: str, name: str, namespace: str, spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        obj = {
            "apiVersion": "elpio.io/v1alpha1",
            "kind": "ElpioService",
            "metadata": {"name": name, "namespace": namespace},
            "spec": spec,
        }
        self._svcs.setdefault(cluster, {})[f"{namespace}/{name}"] = obj
        return obj


class KubeCRGateway(CRGateway):
    """Real gateway: server-side applies CRs via the Kubernetes API.

    Each registered cluster carries connection info — a kubeconfig ``context`` or
    a direct ``server`` + ``token`` (+ optional ``ca``). The gateway resolves a
    client from that record so it authors CRs against the right cluster.
    ``client_factory`` maps a cluster record to a DynamicClient and is injectable
    for tests.
    """

    def __init__(self, registry: FleetRegistry, client_factory=None) -> None:
        self._registry = registry
        if client_factory is None:
            from elpio.k8s import client_for_record

            client_factory = client_for_record
        self._client_factory = client_factory

    def _client(self, cluster: str):
        record = self._registry.get(cluster) or {}
        return self._client_factory(record)

    def list_services(self, cluster: str, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        api = self._client(cluster).resources.get(
            api_version="elpio.io/v1alpha1", kind="ElpioService"
        )
        return api.get(namespace=namespace).to_dict().get("items", [])

    def apply_service(
        self, cluster: str, name: str, namespace: str, spec: Dict[str, Any]
    ) -> Dict[str, Any]:
        from elpio.k8s import apply_object

        obj = {
            "apiVersion": "elpio.io/v1alpha1",
            "kind": "ElpioService",
            "metadata": {"name": name, "namespace": namespace},
            "spec": spec,
        }
        apply_object(obj, dyn=self._client(cluster))
        return obj
