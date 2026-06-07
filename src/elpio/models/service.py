# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: ``ElpioService`` spec — the Cloud Run-equivalent object.

"""``ElpioService`` spec — the Cloud Run-equivalent object.

Re-centred on serverless semantics: scale-to-zero by default, concurrency-driven
autoscaling, and a portable ingress model. This Pydantic model is the in-process
mirror of the ``ElpioService`` CRD schema in ``deploy/crds/elpioservice.yaml`` —
keep the two in sync.
"""

from __future__ import annotations

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator

# CRD coordinates — referenced by the operator and CLI.
GROUP = "elpio.io"
VERSION = "v1alpha1"
KIND = "ElpioService"
PLURAL = "elpioservices"


class ImageRef(BaseModel):
    """A container image. Accepts a plain ``"repo:tag"`` string or an object."""

    repository: str
    tag: Optional[str] = None

    @classmethod
    def coerce(cls, value: Union[str, dict, "ImageRef"]) -> "ImageRef":
        if isinstance(value, ImageRef):
            return value
        if isinstance(value, str):
            repo, _, tag = value.partition(":")
            return cls(repository=repo, tag=tag or None)
        return cls.model_validate(value)

    def __str__(self) -> str:
        return f"{self.repository}:{self.tag}" if self.tag else self.repository


class EnvVar(BaseModel):
    name: str
    value: str


class ResourceUnits(BaseModel):
    cpu: Optional[Union[int, str]] = None
    memory: Optional[Union[int, str]] = None


class Resources(BaseModel):
    requests: Optional[ResourceUnits] = None
    limits: Optional[ResourceUnits] = None


class ReadinessProbe(BaseModel):
    path: str = "/"
    initialDelaySeconds: Optional[int] = None
    periodSeconds: Optional[int] = None


class Scaling(BaseModel):
    """Autoscaling intent. Defaults to true Cloud Run semantics: scale-to-zero,
    concurrency-driven. ``maxScale = 0`` means unbounded (engine default)."""

    minScale: int = 0
    maxScale: int = 0
    target: int = 100
    metric: Literal["concurrency", "rps", "cpu"] = "concurrency"


class Ingress(BaseModel):
    enabled: bool = True
    visibility: Literal["external", "cluster-local"] = "external"
    host: Optional[str] = None
    tls: bool = False


class ElpioServiceSpec(BaseModel):
    """Desired state of an ElpioService (the CRD ``.spec``)."""

    image: ImageRef
    port: int = 8080
    env: List[EnvVar] = Field(default_factory=list)
    resources: Optional[Resources] = None
    readinessProbe: Optional[ReadinessProbe] = None
    scaling: Scaling = Field(default_factory=Scaling)
    ingress: Ingress = Field(default_factory=Ingress)
    serviceAccount: Optional[str] = None

    @field_validator("image", mode="before")
    @classmethod
    def _coerce_image(cls, v):
        return ImageRef.coerce(v)

    @classmethod
    def from_cr(cls, spec: Optional[dict]) -> "ElpioServiceSpec":
        """Build a spec from a raw CRD ``.spec`` dict (as kopf hands it over)."""
        return cls.model_validate(spec or {})
