# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the webhook policy.

import base64
import json

from fastapi.testclient import TestClient

from elpio.webhook.policy import review
from elpio.webhook.server import app


def _ar(obj, uid="uid-1"):
    return {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "request": {"uid": uid, "kind": {"kind": obj.get("kind", "ElpioService")}, "object": obj},
    }


def _svc(spec):
    return {"kind": "ElpioService", "metadata": {"name": "api"}, "spec": spec}


def _patch_ops(resp):
    body = resp["response"]
    if "patch" not in body:
        return []
    return json.loads(base64.b64decode(body["patch"]))


def test_denies_service_without_image():
    resp = review(_ar(_svc({})))
    assert resp["response"]["allowed"] is False
    assert "image" in resp["response"]["status"]["message"]


def test_allows_and_defaults_scale_to_zero():
    resp = review(_ar(_svc({"image": {"repository": "ghcr.io/acme/api", "tag": "1"}})))
    assert resp["response"]["allowed"] is True
    assert {"op": "add", "path": "/spec/scaling", "value": {"minScale": 0}} in _patch_ops(resp)


def test_defaults_minscale_when_scaling_present():
    resp = review(_ar(_svc({"image": "ghcr.io/acme/api:1", "scaling": {"maxScale": 5}})))
    ops = _patch_ops(resp)
    assert {"op": "add", "path": "/spec/scaling/minScale", "value": 0} in ops


def test_no_patch_when_minscale_explicit():
    resp = review(_ar(_svc({"image": "ghcr.io/acme/api:1", "scaling": {"minScale": 1}})))
    assert resp["response"]["allowed"] is True
    assert "patch" not in resp["response"]


def test_registry_allowlist_denies_foreign_image():
    resp = review(_ar(_svc({"image": "docker.io/evil/x:1"})), allowed_registries=["ghcr.io/acme"])
    assert resp["response"]["allowed"] is False
    assert "registry not allowed" in resp["response"]["status"]["message"]


def test_registry_allowlist_permits_listed_image():
    resp = review(_ar(_svc({"image": "ghcr.io/acme/api:1"})), allowed_registries=["ghcr.io/acme"])
    assert resp["response"]["allowed"] is True


def test_uid_is_echoed():
    resp = review(_ar(_svc({"image": "ghcr.io/acme/api:1"}), uid="abc-123"))
    assert resp["response"]["uid"] == "abc-123"


def test_ban_latest_rejects_explicit_latest_tag():
    resp = review(_ar(_svc({"image": "ghcr.io/acme/api:latest"})), ban_latest=True)
    assert resp["response"]["allowed"] is False
    assert "mutable image tag" in resp["response"]["status"]["message"]


def test_ban_latest_rejects_bare_repo():
    resp = review(_ar(_svc({"image": "ghcr.io/acme/api"})), ban_latest=True)
    assert resp["response"]["allowed"] is False
    assert "mutable image tag" in resp["response"]["status"]["message"]


def test_ban_latest_rejects_dict_without_tag():
    resp = review(_ar(_svc({"image": {"repository": "ghcr.io/acme/api"}})), ban_latest=True)
    assert resp["response"]["allowed"] is False


def test_ban_latest_allows_pinned_tag():
    resp = review(_ar(_svc({"image": "ghcr.io/acme/api:1.2"})), ban_latest=True)
    assert resp["response"]["allowed"] is True


def test_ban_latest_off_by_default_allows_latest():
    resp = review(_ar(_svc({"image": "ghcr.io/acme/api:latest"})))
    assert resp["response"]["allowed"] is True


def test_require_requests_rejects_spec_without_requests():
    resp = review(_ar(_svc({"image": "ghcr.io/acme/api:1"})), require_requests=True)
    assert resp["response"]["allowed"] is False
    assert "requests" in resp["response"]["status"]["message"]


def test_require_requests_rejects_partial_requests():
    spec = {"image": "ghcr.io/acme/api:1", "resources": {"requests": {"cpu": "100m"}}}
    resp = review(_ar(_svc(spec)), require_requests=True)
    assert resp["response"]["allowed"] is False


def test_require_requests_allows_spec_with_requests():
    spec = {
        "image": "ghcr.io/acme/api:1",
        "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}},
    }
    resp = review(_ar(_svc(spec)), require_requests=True)
    assert resp["response"]["allowed"] is True


def test_require_requests_off_by_default_allows_missing():
    resp = review(_ar(_svc({"image": "ghcr.io/acme/api:1"})))
    assert resp["response"]["allowed"] is True


def test_server_mutate_and_health():
    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok"}
    r = client.post("/mutate", json=_ar(_svc({"image": "ghcr.io/acme/api:1"})))
    assert r.status_code == 200
    assert r.json()["response"]["allowed"] is True
