# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: ``StateStore`` seam.

"""``StateStore`` seam.

In the operator model, desired state lives on the CR and actual state on the
child objects, so the default ``StateStore`` is effectively the Kubernetes API
itself (CR status). This interface exists for the management-API tier that needs
a fleet/registry view across clusters; a Postgres or other backing store plugs
in here without touching the core.
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
