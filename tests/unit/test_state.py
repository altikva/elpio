# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-07
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the StateStore seam (FileStateStore +
#              InMemoryStateStore).

"""Unit tests for the StateStore seam (FileStateStore + InMemoryStateStore)."""

from __future__ import annotations

import pytest

from elpio.providers import FileStateStore, InMemoryStateStore
from elpio.providers.state import StateStore


@pytest.fixture(params=["memory", "file"])
def store(request, tmp_path):
    if request.param == "memory":
        return InMemoryStateStore()
    return FileStateStore(tmp_path / "fleet" / "state.json")


def test_round_trip(store: StateStore):
    assert store.get("clusters", "a") is None
    store.put("clusters", "a", {"endpoint": "https://a.example"})
    store.put("clusters", "b", {"endpoint": "https://b.example"})

    assert store.get("clusters", "a") == {"endpoint": "https://a.example"}
    listed = store.list("clusters")
    assert len(listed) == 2
    assert {"endpoint": "https://a.example"} in listed
    assert {"endpoint": "https://b.example"} in listed

    store.delete("clusters", "a")
    assert store.get("clusters", "a") is None
    assert store.list("clusters") == [{"endpoint": "https://b.example"}]


def test_empty_collection_lists_nothing(store: StateStore):
    assert store.list("nope") == []
    # delete of a missing key is a no-op, never raises.
    store.delete("nope", "missing")


def test_file_store_creates_dir_and_file_on_first_use(tmp_path):
    path = tmp_path / "a" / "b" / "state.json"
    assert not path.exists()
    store = FileStateStore(path)
    # No write yet, so nothing on disk; a read still works.
    assert store.list("clusters") == []
    store.put("clusters", "a", {"v": 1})
    assert path.exists()


def test_file_store_persists_across_instances(tmp_path):
    path = tmp_path / "state.json"
    first = FileStateStore(path)
    first.put("clusters", "a", {"endpoint": "https://a.example"})
    first.put("tenants", "acme", {"quota": 10})

    # A fresh instance pointing at the same path reads what was written.
    second = FileStateStore(path)
    assert second.get("clusters", "a") == {"endpoint": "https://a.example"}
    assert second.get("tenants", "acme") == {"quota": 10}

    second.delete("clusters", "a")

    third = FileStateStore(path)
    assert third.get("clusters", "a") is None
    assert third.get("tenants", "acme") == {"quota": 10}


def test_file_store_tolerates_missing_file(tmp_path):
    store = FileStateStore(tmp_path / "does-not-exist.json")
    assert store.list("clusters") == []
    assert store.get("clusters", "a") is None


def test_file_store_tolerates_empty_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("", encoding="utf-8")
    store = FileStateStore(path)
    assert store.list("clusters") == []
    store.put("clusters", "a", {"v": 1})
    assert FileStateStore(path).get("clusters", "a") == {"v": 1}


def test_file_store_rejects_corrupt_file(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        FileStateStore(path)


def test_file_store_no_leftover_temp_files(tmp_path):
    path = tmp_path / "state.json"
    store = FileStateStore(path)
    store.put("clusters", "a", {"v": 1})
    store.put("clusters", "b", {"v": 2})
    # Atomic write replaces in place; no temp artifacts left behind.
    assert [p.name for p in tmp_path.iterdir()] == ["state.json"]
