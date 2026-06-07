# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the gateway.

import base64
import os

import pytest

from elpio.api.gateway import FleetRegistry, KubeCRGateway, resolve_secrets
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


def _b64(value):
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _fake_reader(secrets):
    """A reader over an in-memory ``{(name, namespace, key): b64value}`` map."""
    calls = []

    def reader(name, namespace, key):
        calls.append((name, namespace, key))
        return secrets[(name, namespace, key)]

    reader.calls = calls
    return reader


def test_token_secret_ref_resolves_to_inline_token():
    reader = _fake_reader({("edge-creds", "elpio", "token"): _b64("s3cr3t")})
    record = {
        "name": "edge-1",
        "server": "https://api:6443",
        "tokenSecretRef": {"name": "edge-creds", "namespace": "elpio"},
    }
    eff = resolve_secrets(record, reader)
    assert eff["token"] == "s3cr3t"
    assert connection_kind(eff) == "token"
    assert reader.calls == [("edge-creds", "elpio", "token")]


def test_ca_secret_ref_uses_custom_key():
    reader = _fake_reader(
        {
            ("creds", "elpio", "token"): _b64("tok"),
            ("creds", "elpio", "ca.crt"): _b64("PEM-DATA"),
        }
    )
    record = {
        "server": "https://api:6443",
        "tokenSecretRef": {"name": "creds", "namespace": "elpio"},
        "caSecretRef": {"name": "creds", "namespace": "elpio", "key": "ca.crt"},
    }
    eff = resolve_secrets(record, reader)
    assert eff["token"] == "tok" and eff["ca"] == "PEM-DATA"


def test_inline_token_still_works_without_a_reader():
    record = {"server": "https://api:6443", "token": "plain", "ca": "PEM"}
    eff = resolve_secrets(record, reader=None)  # no ref → reader never invoked
    assert eff == record and eff is not record  # copy, not the same object


def test_resolver_does_not_mutate_or_persist_plaintext():
    reader = _fake_reader({("c", "ns", "token"): _b64("opensesame")})
    reg = FleetRegistry()
    reg.register("edge-1", {"server": "https://api:6443", "tokenSecretRef": {"name": "c", "namespace": "ns"}})

    seen = []
    gw = KubeCRGateway(reg, client_factory=_factory_recording(seen), secret_reader=reader)
    gw.list_services("edge-1")

    # The client sees a resolved token...
    assert seen[0]["token"] == "opensesame"
    # ...but the persisted registry record still carries only the ref.
    stored = reg.get("edge-1")
    assert "token" not in stored
    assert stored["tokenSecretRef"] == {"name": "c", "namespace": "ns"}


def test_explicit_ref_overrides_a_stale_inline_token():
    reader = _fake_reader({("c", "ns", "token"): _b64("fresh")})
    record = {"server": "https://api:6443", "token": "stale", "tokenSecretRef": {"name": "c", "namespace": "ns"}}
    assert resolve_secrets(record, reader)["token"] == "fresh"


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
