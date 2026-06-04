# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Portability seams.

"""Portability seams.

Elpio depends on these interfaces, never on a cloud SDK directly. GKE-first, but
no GCP assumption is baked into the core — the same install must run on EKS, AKS
or k3s. Concrete provider implementations live behind each interface.
"""

from elpio.providers.identity import (
    IdentityProvider,
    NullIdentityProvider,
    OIDCIdentityProvider,
    Principal,
)
from elpio.providers.state import InMemoryStateStore, StateStore

__all__ = [
    "IdentityProvider",
    "NullIdentityProvider",
    "OIDCIdentityProvider",
    "Principal",
    "StateStore",
    "InMemoryStateStore",
]
