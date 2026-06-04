# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Domain models — the declarative spec behind the Elpio CRDs.

"""Domain models — the declarative spec behind the Elpio CRDs."""

from elpio.models.service import (
    GROUP,
    VERSION,
    KIND,
    PLURAL,
    ElpioServiceSpec,
    ImageRef,
    EnvVar,
    Resources,
    ResourceUnits,
    ReadinessProbe,
    Scaling,
    Ingress,
)

__all__ = [
    "GROUP",
    "VERSION",
    "KIND",
    "PLURAL",
    "ElpioServiceSpec",
    "ImageRef",
    "EnvVar",
    "Resources",
    "ResourceUnits",
    "ReadinessProbe",
    "Scaling",
    "Ingress",
]
