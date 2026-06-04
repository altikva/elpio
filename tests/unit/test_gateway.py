# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the gateway.

from elpio.api.gateway import FleetRegistry, KubeCRGateway
from elpio.k8s import connection_kind


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
