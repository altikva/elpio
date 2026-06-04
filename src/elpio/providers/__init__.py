"""Portability seams (RFC 0001 §4.4).

Elpio depends on these interfaces, never on a cloud SDK directly. GKE-first, but
no GCP assumption is baked into the core — the same install must run on EKS, AKS
or k3s. Concrete provider implementations live behind each interface.
"""

from elpio.providers.identity import IdentityProvider, NullIdentityProvider, Principal
from elpio.providers.state import InMemoryStateStore, StateStore

__all__ = [
    "IdentityProvider",
    "NullIdentityProvider",
    "Principal",
    "StateStore",
    "InMemoryStateStore",
]
