# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the tenant render.

from elpio.models.tenant import TenantSpec
from elpio.tenant import render_tenant

FULL = TenantSpec.from_cr(
    {
        "namespace": "team-acme",
        "rbac": {"role": "admin", "users": ["alice@acme.io"], "groups": ["acme-devs"]},
        "resourceQuota": {"cpu": "4", "memory": "8Gi", "pods": 20},
        "limits": {"defaultCpu": "1"},
        "secrets": [{"name": "registry", "data": {"token": "s3cr3t"}, "reflect": True}],
    }
)


def _by_kind(objs):
    out = {}
    for o in objs:
        out.setdefault(o["kind"], []).append(o)
    return out


def test_renders_full_guardrail_set():
    objs = render_tenant("acme", FULL)
    kinds = {o["kind"] for o in objs}
    assert kinds == {
        "Namespace",
        "ServiceAccount",
        "ResourceQuota",
        "LimitRange",
        "NetworkPolicy",
        "RoleBinding",
        "Secret",
    }
    # namespace override is honoured everywhere
    ns_names = {o["metadata"].get("namespace") for o in objs if o["kind"] != "Namespace"}
    assert ns_names == {"team-acme"}
    assert _by_kind(objs)["Namespace"][0]["metadata"]["name"] == "team-acme"


def test_rbac_binds_users_groups_and_bound_sa():
    rb = _by_kind(render_tenant("acme", FULL))["RoleBinding"][0]
    assert rb["roleRef"]["name"] == "admin"
    subjects = {(s["kind"], s["name"]) for s in rb["subjects"]}
    assert ("User", "alice@acme.io") in subjects
    assert ("Group", "acme-devs") in subjects
    assert ("ServiceAccount", "acme-sa") in subjects  # the bound SA is always included


def test_quota_maps_requests_and_limits():
    hard = _by_kind(render_tenant("acme", FULL))["ResourceQuota"][0]["spec"]["hard"]
    assert hard["requests.cpu"] == "4" and hard["limits.cpu"] == "4"
    assert hard["requests.memory"] == "8Gi" and hard["limits.memory"] == "8Gi"
    assert hard["pods"] == "20"


def test_reflected_secret_is_annotated():
    secret = _by_kind(render_tenant("acme", FULL))["Secret"][0]
    assert secret["stringData"] == {"token": "s3cr3t"}
    assert secret["metadata"]["annotations"]["reflector.v1.k8s.emberstack.com/reflection-allowed"] == "true"


def test_owner_reference_propagates_to_all_children():
    owner = {"apiVersion": "elpio.io/v1alpha1", "kind": "ElpioTenant", "name": "acme", "uid": "u1"}
    objs = render_tenant("acme", FULL, owner=owner)
    assert all(o["metadata"]["ownerReferences"] == [owner] for o in objs)


def test_defaults_minimal_tenant():
    objs = render_tenant("solo", TenantSpec.from_cr({}))
    kinds = {o["kind"] for o in objs}
    # no quota/limits/secrets requested → just ns + sa + isolation + rbac
    assert kinds == {"Namespace", "ServiceAccount", "NetworkPolicy", "RoleBinding"}
    assert objs[0]["metadata"]["name"] == "solo"
