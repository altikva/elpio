# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-07
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the shared operator helpers.

"""Unit tests for the shared operator helpers."""

import logging

from elpio.models.service import GROUP, VERSION
from elpio.operator import common


def test_owner_reference_shape_service():
    ref = common.owner_reference("ElpioService", "hello", "uid-123")
    assert ref == {
        "apiVersion": f"{GROUP}/{VERSION}",
        "kind": "ElpioService",
        "name": "hello",
        "uid": "uid-123",
        "controller": True,
        "blockOwnerDeletion": True,
    }


def test_owner_reference_shape_task():
    ref = common.owner_reference("ElpioTask", "worker", "uid-456")
    assert ref["apiVersion"] == "elpio.io/v1alpha1"
    assert ref["kind"] == "ElpioTask"
    assert ref["name"] == "worker"
    assert ref["uid"] == "uid-456"
    assert ref["controller"] is True
    assert ref["blockOwnerDeletion"] is True


def test_apply_all_applies_each_object(monkeypatch):
    applied = []
    monkeypatch.setattr(common, "apply_object", applied.append)

    objects = [
        {"kind": "Service", "metadata": {"name": "a"}},
        {"kind": "ConfigMap", "metadata": {"name": "b"}},
    ]
    count = common.apply_all(objects, logging.getLogger("test"), "child")

    assert count == 2
    assert applied == objects


def test_apply_all_empty(monkeypatch):
    monkeypatch.setattr(common, "apply_object", lambda obj: None)
    assert common.apply_all([], logging.getLogger("test"), "child") == 0
