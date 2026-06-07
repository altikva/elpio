# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: ``IdentityProvider`` seam.

"""``IdentityProvider`` seam.

Authentication is generic OIDC; authorization is Kubernetes-native
(SubjectAccessReview / RBAC) rather than a cloud IAM API. Any enterprise identity
provider plugs in as an OIDC provider, not a baked-in assumption.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence


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


# A SAR reviewer answers "may this principal do <verb> on <resource>?". Injected
# so the OIDC provider is unit-testable without a cluster.
SarReviewer = Callable[[Principal, str, str], bool]

# In a "<group>/<resource>" string, this alias selects the core API group, which
# Kubernetes represents as the empty string "".
_CORE_GROUP_ALIAS = "core"


def _jwks_uri_is_safe(jwks_uri: str) -> bool:
    """https is required; plain http is tolerated only for local dev hosts."""
    from urllib.parse import urlparse

    parsed = urlparse(jwks_uri)
    if parsed.scheme == "https":
        return True
    if parsed.scheme == "http":
        return parsed.hostname in ("localhost", "127.0.0.1", "::1")
    return False


class OIDCIdentityProvider(IdentityProvider):
    """Authenticate via OIDC JWTs; authorize via Kubernetes SubjectAccessReview.

    Pass ``signing_key`` for symmetric (HS*) tokens — handy for tests — or
    ``jwks_uri`` to verify RS*/ES* tokens against a provider's published JWKS.
    ``resource`` strings are ``"<resource>"`` (group defaults to ``elpio.io``) or
    ``"<group>/<resource>"`` (use ``"core/..."`` for the core API group).
    """

    def __init__(
        self,
        *,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
        jwks_uri: Optional[str] = None,
        signing_key: Optional[str] = None,
        algorithms: Sequence[str] = ("RS256",),
        groups_claim: str = "groups",
        default_group: str = "elpio.io",
        sar_reviewer: Optional[SarReviewer] = None,
    ) -> None:
        if not signing_key and not jwks_uri:
            raise ValueError("OIDCIdentityProvider needs signing_key or jwks_uri")
        if jwks_uri and not _jwks_uri_is_safe(jwks_uri):
            raise ValueError(
                "jwks_uri must use https:// (http:// is only allowed for "
                "localhost/127.0.0.1 in development)"
            )
        # Asymmetric (JWKS) is the production path: a bare token replay from
        # another service must not authenticate, so pin issuer and audience.
        if jwks_uri and (issuer is None or audience is None):
            raise ValueError(
                "jwks_uri requires both issuer and audience to be set so tokens "
                "minted for another service are rejected"
            )
        self._issuer = issuer
        self._audience = audience
        self._jwks_uri = jwks_uri
        self._signing_key = signing_key
        self._algorithms = list(algorithms)
        self._groups_claim = groups_claim
        self._default_group = default_group
        self._sar_reviewer = sar_reviewer
        self._jwks_client = None  # lazily built

    def _key_for(self, token: str):
        if self._signing_key is not None:
            return self._signing_key
        import jwt  # lazy: pyjwt lives in the `server` extra, not the lean core

        if self._jwks_client is None:
            self._jwks_client = jwt.PyJWKClient(self._jwks_uri)
        return self._jwks_client.get_signing_key_from_jwt(token).key

    def authenticate(self, token: str) -> Optional[Principal]:
        import jwt  # lazy

        options = {"require": ["sub"], "verify_aud": self._audience is not None}
        try:
            claims = jwt.decode(
                token,
                self._key_for(token),
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options=options,
            )
        except Exception:  # any pyjwt error → unauthenticated
            return None

        groups = claims.get(self._groups_claim) or []
        if isinstance(groups, str):
            groups = [groups]
        return Principal(
            subject=claims["sub"],
            email=claims.get("email"),
            groups=list(groups),
        )

    def authorize(self, principal: Principal, verb: str, resource: str) -> bool:
        reviewer = self._sar_reviewer or self._cluster_sar
        return reviewer(principal, verb, resource)

    def _split_resource(self, resource: str) -> tuple[str, str]:
        if "/" in resource:
            group, res = resource.split("/", 1)
            return ("" if group == _CORE_GROUP_ALIAS else group), res
        return self._default_group, resource

    def _cluster_sar(self, principal: Principal, verb: str, resource: str) -> bool:
        """Default reviewer: a real SubjectAccessReview against the cluster."""
        from kubernetes import client  # lazy: only needed in-cluster

        group, res = self._split_resource(resource)
        review = client.V1SubjectAccessReview(
            spec=client.V1SubjectAccessReviewSpec(
                user=principal.subject,
                groups=principal.groups,
                resource_attributes=client.V1ResourceAttributes(
                    verb=verb, group=group, resource=res
                ),
            )
        )
        resp = client.AuthorizationV1Api().create_subject_access_review(review)
        return bool(resp.status.allowed)
