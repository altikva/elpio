"""``IdentityProvider`` seam — replaces A4C's hard-wired GateApe + Google OAuth2.

Authentication is generic OIDC; authorization is Kubernetes-native
(SubjectAccessReview / RBAC) rather than a cloud IAM API. GateApe becomes one
OIDC plugin, not the assumption (RFC 0001 §4.4).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Principal:
    subject: str
    email: Optional[str] = None
    groups: List[str] = field(default_factory=list)


class IdentityProvider(ABC):
    @abstractmethod
    def authenticate(self, token: str) -> Optional[Principal]:
        """Validate a bearer token and return the Principal, or None."""

    @abstractmethod
    def authorize(self, principal: Principal, verb: str, resource: str) -> bool:
        """Authorize an action (back this with SubjectAccessReview in prod)."""


class NullIdentityProvider(IdentityProvider):
    """Dev-only: authenticate everyone as ``dev``, allow everything.

    NEVER use outside local development. The real provider is OIDC + SAR.
    """

    def authenticate(self, token: str) -> Optional[Principal]:
        return Principal(subject="dev", email="dev@localhost")

    def authorize(self, principal: Principal, verb: str, resource: str) -> bool:
        return True
