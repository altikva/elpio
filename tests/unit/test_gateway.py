# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the gateway.

from elpio.api.gateway import FleetRegistry, KubeCRGateway


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
    def __init__(self, context):
        self.context = context
        self.applied = []

        class _Resources:
            def get(_self, api_version, kind):
                return FakeApi(self)

        self.resources = _Resources()


def _factory_recording(seen):
    def factory(context):
        seen.append(context)
        return FakeDyn(context)

    return factory


def test_resolves_registered_context_per_cluster():
    seen = []
    reg = FleetRegistry()
    reg.register("edge-1", {"context": "kind-edge-1"})
    gw = KubeCRGateway(reg, client_factory=_factory_recording(seen))

    gw.apply_service("edge-1", "api", "demo", {"image": "x:1"})
    assert seen == ["kind-edge-1"]


def test_apply_targets_the_right_clients_client():
    captured = {}

    def factory(context):
        dyn = FakeDyn(context)
        captured[context] = dyn
        return dyn

    reg = FleetRegistry()
    reg.register("edge-1", {"context": "ctx-a"})
    gw = KubeCRGateway(reg, client_factory=factory)

    obj = gw.apply_service("edge-1", "api", "demo", {"image": "ghcr.io/acme/api:1"})
    assert obj["kind"] == "ElpioService"
    applied = captured["ctx-a"].applied
    assert applied == [("demo", "api", obj)]


def test_unknown_cluster_falls_back_to_default_context():
    seen = []
    gw = KubeCRGateway(FleetRegistry(), client_factory=_factory_recording(seen))
    gw.list_services("ghost")
    assert seen == [None]  # no record → default (None) context
