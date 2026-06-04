# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the api.

import pytest
from fastapi.testclient import TestClient

from elpio.api.app import create_app
from elpio.api.gateway import FleetRegistry, InMemoryCRGateway
from elpio.providers.identity import IdentityProvider, NullIdentityProvider, Principal

AUTH = {"Authorization": "Bearer dev-token"}


@pytest.fixture
def client():
    return TestClient(
        create_app(
            identity=NullIdentityProvider(),
            registry=FleetRegistry(),
            gateway=InMemoryCRGateway(),
        )
    )


def test_health_is_open(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_requires_a_token(client):
    assert client.get("/clusters").status_code == 401


def test_register_and_list_clusters(client):
    assert client.post("/clusters", json={"name": "edge-1"}, headers=AUTH).status_code == 201
    names = [c["name"] for c in client.get("/clusters", headers=AUTH).json()]
    assert names == ["edge-1"]


def test_author_service_cr_round_trips(client):
    client.post("/clusters", json={"name": "edge-1"}, headers=AUTH)
    r = client.post(
        "/clusters/edge-1/services",
        json={"name": "api", "namespace": "demo", "spec": {"image": "ghcr.io/acme/api:1"}},
        headers=AUTH,
    )
    assert r.status_code == 201
    assert r.json()["kind"] == "ElpioService"

    listed = client.get("/clusters/edge-1/services", headers=AUTH).json()
    assert [s["metadata"]["name"] for s in listed] == ["api"]


def test_unknown_cluster_is_404(client):
    r = client.post(
        "/clusters/nope/services",
        json={"name": "api", "namespace": "demo", "spec": {"image": "x:1"}},
        headers=AUTH,
    )
    assert r.status_code == 404


def test_invalid_spec_is_422(client):
    client.post("/clusters", json={"name": "edge-1"}, headers=AUTH)
    r = client.post(
        "/clusters/edge-1/services",
        json={"name": "api", "namespace": "demo", "spec": {"port": 8080}},  # no image
        headers=AUTH,
    )
    assert r.status_code == 422


class _DenyAll(IdentityProvider):
    def authenticate(self, token):
        return Principal(subject="alice") if token else None

    def authorize(self, principal, verb, resource):
        return False


def test_authorization_is_enforced():
    client = TestClient(create_app(identity=_DenyAll(), gateway=InMemoryCRGateway()))
    # authenticates (200-path) but authorize() denies → 403
    assert client.get("/clusters", headers=AUTH).status_code == 403
