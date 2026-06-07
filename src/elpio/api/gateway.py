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

import base64
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from elpio.providers.state import InMemoryStateStore, StateStore

_CLUSTERS = "clusters"

# A secret reader fetches one value out of a Kubernetes Secret, given the
# Secret's name, its namespace, and the key inside its ``data`` map. It returns
# the base64-encoded value exactly as the Kubernetes API stores it; the resolver
# decodes it. Injecting this keeps ``resolve_secrets`` pure and unit-testable.
SecretReader = Callable[[str, str, str], str]


def _default_secret_reader(name: str, namespace: str, key: str) -> str:
    """Read a Secret value from the cluster via ``elpio.k8s`` (base64-encoded).

    Imported lazily so the resolver and its tests never need a cluster client.
    """
    from elpio.k8s import get_object

    obj = get_object("v1", "Secret", name, namespace=namespace)
    if obj is None:
        raise KeyError(f"secret {namespace}/{name} not found")
    data = obj.get("data") or {}
    if key not in data:
        raise KeyError(f"secret {namespace}/{name} has no key '{key}'")
    return data[key]


# (registry field, secret-ref field, default key inside the Secret's data map)
_SECRET_REFS = (
    ("token", "tokenSecretRef", "token"),
    ("ca", "caSecretRef", "ca"),
)


def resolve_secrets(
    record: Optional[Dict[str, Any]],
    reader: Optional[SecretReader] = None,
) -> Dict[str, Any]:
    """Return an effective cluster record with secret refs resolved inline.

    A registry record may carry sensitive material indirectly through
    ``tokenSecretRef`` / ``caSecretRef`` (each ``{name, namespace, key?}``)
    instead of an inline ``token`` / ``ca``. For every such ref, this reads the
    referenced Secret value via ``reader``, base64-decodes it, and fills in the
    matching plaintext field on a COPY of the record. The input record is never
    mutated, so the plaintext is never persisted back into the registry. An
    inline ``token`` / ``ca`` still works untouched (back-compat); when both are
    present the explicit secret ref wins.
    """
    record = dict(record or {})
    reader = reader or _default_secret_reader
    for target, ref_field, default_key in _SECRET_REFS:
        ref = record.get(ref_field)
        if not ref:
            continue
        value = reader(ref["name"], ref.get("namespace") or "", ref.get("key") or default_key)
        record[target] = base64.b64decode(value).decode("utf-8")
    return record


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
    a direct ``server`` + ``token`` (+ optional ``ca``). The sensitive ``token``
    and ``ca`` may instead be sourced from a Kubernetes Secret via
    ``tokenSecretRef`` / ``caSecretRef``; those are resolved to plaintext only at
    connection time, on a throwaway copy of the record, so the registry never
    stores the secret material. The gateway resolves a client from that effective
    record so it authors CRs against the right cluster. ``client_factory`` maps a
    record to a DynamicClient and ``secret_reader`` reads Secret values; both are
    injectable for tests.
    """

    def __init__(self, registry: FleetRegistry, client_factory=None, secret_reader=None) -> None:
        self._registry = registry
        if client_factory is None:
            from elpio.k8s import client_for_record

            client_factory = client_for_record
        self._client_factory = client_factory
        self._secret_reader = secret_reader

    def _client(self, cluster: str):
        record = self._registry.get(cluster) or {}
        record = resolve_secrets(record, self._secret_reader)
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
