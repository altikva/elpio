# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: ``ElpioTenant`` spec — the multi-tenancy object.

"""``ElpioTenant`` spec — the multi-tenancy object.

A Tenant maps to a Namespace plus the guardrails around it: RBAC bindings to the
built-in ``admin``/``edit``/``view`` ClusterRoles, a ResourceQuota + LimitRange, a
default-deny NetworkPolicy, a bound ServiceAccount, and (optionally reflected)
secrets. The Pydantic model mirrors ``deploy/crds/tenant.yaml`` — keep the two in
sync.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# CRD coordinates. Tenants are cluster-scoped (they create a Namespace).
GROUP = "elpio.io"
VERSION = "v1alpha1"
KIND = "ElpioTenant"
PLURAL = "elpiotenants"


class RbacConfig(BaseModel):
    """Who gets access to the tenant namespace, and at what level."""

    role: Literal["admin", "edit", "view"] = "edit"
    users: List[str] = Field(default_factory=list)
    groups: List[str] = Field(default_factory=list)
    serviceAccounts: List[str] = Field(default_factory=list)


class QuotaConfig(BaseModel):
    cpu: Optional[str] = None
    memory: Optional[str] = None
    pods: Optional[int] = None


class LimitsConfig(BaseModel):
    """Per-container defaults applied via a LimitRange."""

    defaultCpu: str = "500m"
    defaultMemory: str = "256Mi"
    defaultRequestCpu: str = "100m"
    defaultRequestMemory: str = "128Mi"


class SecretConfig(BaseModel):
    name: str
    data: Dict[str, str] = Field(default_factory=dict)
    # When true, annotate so a secret-reflection controller may mirror it to
    # other namespaces (opt-in; the controller itself is out of scope).
    reflect: bool = False


class TenantSpec(BaseModel):
    """Desired state of an ElpioTenant (the CRD ``.spec``)."""

    namespace: Optional[str] = None
    labels: Dict[str, str] = Field(default_factory=dict)
    rbac: RbacConfig = Field(default_factory=RbacConfig)
    resourceQuota: Optional[QuotaConfig] = None
    limits: Optional[LimitsConfig] = None
    networkIsolation: bool = True
    serviceAccount: Optional[str] = None
    secrets: List[SecretConfig] = Field(default_factory=list)

    @classmethod
    def from_cr(cls, spec: Optional[dict]) -> "TenantSpec":
        return cls.model_validate(spec or {})

    def namespace_for(self, name: str) -> str:
        return self.namespace or name

    def service_account_for(self, name: str) -> str:
        return self.serviceAccount or f"{name}-sa"
