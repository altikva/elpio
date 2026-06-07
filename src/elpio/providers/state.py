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

import json
import os
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
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


class FileStateStore(StateStore):
    """JSON-file-backed store that survives process restarts.

    The whole store is a single JSON document on disk, shaped exactly like
    ``InMemoryStateStore._data`` (``{collection: {key: value}}``). Every
    mutation rewrites the file atomically: the new content is written to a
    temp file in the same directory and then ``os.replace``-d over the target,
    so a crash mid-write never leaves a half-written or empty file. The parent
    directory is created on first use, and a missing or empty file reads back
    as an empty store.

    This is the persistent option for the management-API fleet registry. It is
    not concurrency-safe across processes (no file locking); a Postgres-backed
    store is the intended path for multi-writer deployments.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        self._data: Dict[str, Dict[str, Dict[str, Any]]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        if not raw.strip():
            return {}
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise ValueError(f"corrupt state file {self._path}: expected a JSON object")
        return loaded

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self._path.parent), prefix=f".{self._path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def get(self, collection: str, key: str) -> Optional[Dict[str, Any]]:
        return self._data.get(collection, {}).get(key)

    def put(self, collection: str, key: str, value: Dict[str, Any]) -> None:
        self._data.setdefault(collection, {})[key] = value
        self._flush()

    def delete(self, collection: str, key: str) -> None:
        self._data.get(collection, {}).pop(key, None)
        self._flush()

    def list(self, collection: str) -> List[Dict[str, Any]]:
        return list(self._data.get(collection, {}).values())
