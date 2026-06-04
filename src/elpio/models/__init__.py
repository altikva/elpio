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
