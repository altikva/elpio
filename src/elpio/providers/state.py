"""``StateStore`` seam — replaces A4C's Firestore singleton.

In the operator model, desired state lives on the CR and actual state on the
child objects, so the default ``StateStore`` is effectively the Kubernetes API
itself (CR status). This interface exists for the management-API tier that needs
a fleet/registry view across clusters; a Postgres or Firestore implementation
plugs in here without touching the core.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class StateStore(ABC):
    @abstractmethod
    def get(self, collection: str, key: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def put(self, collection: str, key: str, value: Dict[str, Any]) -> None: ...

    @abstractmethod
    def delete(self, collection: str, key: str) -> None: ...

    @abstractmethod
    def list(self, collection: str) -> List[Dict[str, Any]]: ...


class InMemoryStateStore(StateStore):
    """Reference implementation for tests and single-node dev."""

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def get(self, collection: str, key: str) -> Optional[Dict[str, Any]]:
        return self._data.get(collection, {}).get(key)

    def put(self, collection: str, key: str, value: Dict[str, Any]) -> None:
        self._data.setdefault(collection, {})[key] = value

    def delete(self, collection: str, key: str) -> None:
        self._data.get(collection, {}).pop(key, None)

    def list(self, collection: str) -> List[Dict[str, Any]]:
        return list(self._data.get(collection, {}).values())
