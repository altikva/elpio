# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Pure render of an ``ElpioTenant`` into namespace-scoped
#              guardrail objects.

"""Pure render of an ``ElpioTenant`` into namespace-scoped guardrail objects.

Spec in → plain Kubernetes object dicts out, no cluster calls — same contract as
the serving engines, so it is unit-testable without a cluster. The reconciler in
``operator/tenant_handlers.py`` server-side applies whatever this returns.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elpio.models.tenant import TenantSpec

_MANAGED = {"app.kubernetes.io/managed-by": "elpio"}
# A Tenant's RBAC level maps onto a built-in Kubernetes ClusterRole.
_ROLE_CLUSTERROLE = {"admin": "admin", "edit": "edit", "view": "view"}
# Opt-in annotation understood by the emberstack reflector controller.
_REFLECT_ANNOTATIONS = {"reflector.v1.k8s.emberstack.com/reflection-allowed": "true"}


def _namespace(ns: str, labels: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": ns, "labels": labels},
    }


def _service_account(sa: str, ns: str, labels: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "ServiceAccount",
        "metadata": {"name": sa, "namespace": ns, "labels": labels},
    }


def _resource_quota(
    spec: TenantSpec, ns: str, labels: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    if not spec.resourceQuota:
        return None
    hard: Dict[str, Any] = {}
    if spec.resourceQuota.cpu:
        hard["requests.cpu"] = spec.resourceQuota.cpu
        hard["limits.cpu"] = spec.resourceQuota.cpu
    if spec.resourceQuota.memory:
        hard["requests.memory"] = spec.resourceQuota.memory
        hard["limits.memory"] = spec.resourceQuota.memory
    if spec.resourceQuota.pods is not None:
        hard["pods"] = str(spec.resourceQuota.pods)
    if not hard:
        return None
    return {
        "apiVersion": "v1",
        "kind": "ResourceQuota",
        "metadata": {"name": "elpio-quota", "namespace": ns, "labels": labels},
        "spec": {"hard": hard},
    }


def _limit_range(
    spec: TenantSpec, ns: str, labels: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    if not spec.limits:
        return None
    return {
        "apiVersion": "v1",
        "kind": "LimitRange",
        "metadata": {"name": "elpio-limits", "namespace": ns, "labels": labels},
        "spec": {
            "limits": [
                {
                    "type": "Container",
                    "default": {
                        "cpu": spec.limits.defaultCpu,
                        "memory": spec.limits.defaultMemory,
                    },
                    "defaultRequest": {
                        "cpu": spec.limits.defaultRequestCpu,
                        "memory": spec.limits.defaultRequestMemory,
                    },
                }
            ]
        },
    }


def _network_policy(
    spec: TenantSpec, ns: str, labels: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    if not spec.networkIsolation:
        return None
    # Default-deny cross-namespace ingress: only same-namespace pods may reach
    # pods in this namespace (an empty ``from.podSelector`` means this ns).
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {"name": "elpio-isolation", "namespace": ns, "labels": labels},
        "spec": {
            "podSelector": {},
            "policyTypes": ["Ingress"],
            "ingress": [{"from": [{"podSelector": {}}]}],
        },
    }


def _role_binding(
    spec: TenantSpec, sa: str, ns: str, labels: Dict[str, Any]
) -> Dict[str, Any]:
    subjects: List[Dict[str, str]] = []
    subjects += [{"kind": "User", "apiGroup": "rbac.authorization.k8s.io", "name": u} for u in spec.rbac.users]
    subjects += [{"kind": "Group", "apiGroup": "rbac.authorization.k8s.io", "name": g} for g in spec.rbac.groups]
    subjects += [{"kind": "ServiceAccount", "name": s, "namespace": ns} for s in spec.rbac.serviceAccounts]
    # The tenant's own bound ServiceAccount always gets the binding.
    subjects.append({"kind": "ServiceAccount", "name": sa, "namespace": ns})
    return {
        "apiVersion": "rbac.authorization.k8s.io/v1",
        "kind": "RoleBinding",
        "metadata": {
            "name": f"elpio-tenant-{spec.rbac.role}",
            "namespace": ns,
            "labels": labels,
        },
        "roleRef": {
            "apiGroup": "rbac.authorization.k8s.io",
            "kind": "ClusterRole",
            "name": _ROLE_CLUSTERROLE[spec.rbac.role],
        },
        "subjects": subjects,
    }


def _secrets(
    spec: TenantSpec, ns: str, labels: Dict[str, Any]
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for s in spec.secrets:
        meta: Dict[str, Any] = {"name": s.name, "namespace": ns, "labels": labels}
        if s.reflect:
            meta["annotations"] = dict(_REFLECT_ANNOTATIONS)
        out.append(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": meta,
                "stringData": s.data,
            }
        )
    return out


def render_tenant(
    name: str,
    spec: TenantSpec,
    owner: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    ns = spec.namespace_for(name)
    sa = spec.service_account_for(name)
    labels = {**_MANAGED, "elpio.io/tenant": name, **spec.labels}

    objs: List[Dict[str, Any]] = [
        _namespace(ns, labels),
        _service_account(sa, ns, labels),
    ]
    for obj in (
        _resource_quota(spec, ns, labels),
        _limit_range(spec, ns, labels),
        _network_policy(spec, ns, labels),
    ):
        if obj is not None:
            objs.append(obj)
    objs.append(_role_binding(spec, sa, ns, labels))
    objs.extend(_secrets(spec, ns, labels))

    if owner:
        for o in objs:
            o["metadata"]["ownerReferences"] = [owner]
    return objs
