# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the gateway.

import os

import pytest

from elpio.api.gateway import FleetRegistry, KubeCRGateway
from elpio.k8s import _ca_cert_path, connection_kind


class FakeApi:
    def __init__(self, dyn):
        self.dyn = dyn

    def patch(self, *, body, name, namespace, content_type, field_manager, force):
        self.dyn.applied.append((namespace, name, body))
        return body

    def get(self, namespace=None):
        class _R:
            def to_dict(_self):
                return {"items": [{"metadata": {"name": "svc", "namespace": namespace}}]}

        return _R()


class FakeDyn:
    def __init__(self, record):
        self.record = record
        self.applied = []

        class _Resources:
            def get(_self, api_version, kind):
                return FakeApi(self)

        self.resources = _Resources()


def _factory_recording(seen):
    def factory(record):
        seen.append(record)
        return FakeDyn(record)

    return factory


def test_resolves_registered_record_per_cluster():
    seen = []
    reg = FleetRegistry()
    reg.register("edge-1", {"context": "kind-edge-1"})
    gw = KubeCRGateway(reg, client_factory=_factory_recording(seen))

    gw.apply_service("edge-1", "api", "demo", {"image": "x:1"})
    assert seen == [{"name": "edge-1", "context": "kind-edge-1"}]


def test_apply_targets_the_resolved_client():
    captured = {}

    def factory(record):
        dyn = FakeDyn(record)
        captured[record["name"]] = dyn
        return dyn

    reg = FleetRegistry()
    reg.register("edge-1", {"context": "ctx-a"})
    gw = KubeCRGateway(reg, client_factory=factory)

    obj = gw.apply_service("edge-1", "api", "demo", {"image": "ghcr.io/acme/api:1"})
    assert obj["kind"] == "ElpioService"
    assert captured["edge-1"].applied == [("demo", "api", obj)]


def test_token_record_is_passed_through():
    seen = []
    reg = FleetRegistry()
    reg.register("saas-1", {"server": "https://api.saas:6443", "token": "abc", "ca": "PEM"})
    gw = KubeCRGateway(reg, client_factory=_factory_recording(seen))

    gw.list_services("saas-1")
    record = seen[0]
    assert connection_kind(record) == "token"
    assert record["server"] == "https://api.saas:6443" and record["token"] == "abc"


def test_unknown_cluster_falls_back_to_empty_record():
    seen = []
    gw = KubeCRGateway(FleetRegistry(), client_factory=_factory_recording(seen))
    gw.list_services("ghost")
    assert seen == [{}]  # no record → default connection (context None)
    assert connection_kind(seen[0]) == "context"


def test_connection_kind_classification():
    assert connection_kind(None) == "context"
    assert connection_kind({"context": "x"}) == "context"
    assert connection_kind({"server": "https://a", "token": "t"}) == "token"
    assert connection_kind({"server": "https://a"}) == "context"  # token missing


def test_ca_cert_path_is_deterministic_and_per_user():
    ca = "-----BEGIN CERTIFICATE-----\nPEMDATA\n-----END CERTIFICATE-----\n"
    assert _ca_cert_path(ca) == _ca_cert_path(ca)  # same CA → same file
    assert _ca_cert_path(ca) != _ca_cert_path(ca + "x")  # different CA → different file
    path = _ca_cert_path(ca)
    assert path.endswith(".crt") and os.path.basename(path).startswith("elpio-ca-")
    # Trust material lives under a per-user cache dir, never world-writable /tmp.
    expected_dir = os.path.join(os.path.expanduser("~"), ".cache", "elpio", "ca")
    assert os.path.dirname(path) == expected_dir
    assert oct(os.stat(expected_dir).st_mode & 0o777) == "0o700"


def test_materialize_ca_writes_private_and_verifies_on_reuse(tmp_path, monkeypatch):
    from elpio import k8s

    monkeypatch.setattr(k8s, "_ca_cache_dir", lambda: str(tmp_path))
    ca = "CA-BUNDLE-CONTENT"
    p = k8s._materialize_ca(ca)
    assert open(p).read() == ca
    assert oct(os.stat(p).st_mode & 0o777) == "0o600"  # private file
    assert k8s._materialize_ca(ca) == p  # reuse, contents match → ok
    # A tampered cache file is rejected rather than trusted.
    with open(p, "w") as fh:
        fh.write("ATTACKER-CA")
    with pytest.raises(RuntimeError, match="does not match"):
        k8s._materialize_ca(ca)
