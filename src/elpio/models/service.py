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

from pydantic import BaseModel, Field, field_validator, model_validator

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


class KeySelector(BaseModel):
    """Reference to a single key in a Secret or ConfigMap."""

    name: str
    key: str
    optional: Optional[bool] = None


class EnvVarSource(BaseModel):
    """Where a container env var draws its value from (one source only)."""

    secretKeyRef: Optional[KeySelector] = None
    configMapKeyRef: Optional[KeySelector] = None

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "EnvVarSource":
        sources = [self.secretKeyRef, self.configMapKeyRef]
        if sum(s is not None for s in sources) != 1:
            raise ValueError(
                "valueFrom must set exactly one of secretKeyRef or configMapKeyRef"
            )
        return self


class EnvVar(BaseModel):
    """A container env var: a literal ``value`` or a ``valueFrom`` reference."""

    name: str
    value: Optional[str] = None
    valueFrom: Optional[EnvVarSource] = None

    @model_validator(mode="after")
    def _value_xor_valuefrom(self) -> "EnvVar":
        if (self.value is None) == (self.valueFrom is None):
            raise ValueError("env entry must set exactly one of value or valueFrom")
        return self


class NamedRef(BaseModel):
    name: str
    optional: Optional[bool] = None


class EnvFromSource(BaseModel):
    """Bulk-inject every key of a Secret or ConfigMap as env vars."""

    secretRef: Optional[NamedRef] = None
    configMapRef: Optional[NamedRef] = None
    prefix: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one_ref(self) -> "EnvFromSource":
        refs = [self.secretRef, self.configMapRef]
        if sum(r is not None for r in refs) != 1:
            raise ValueError(
                "envFrom entry must set exactly one of secretRef or configMapRef"
            )
        return self


class ExternalSecretData(BaseModel):
    """One key mapped from an external secret store into the synced Secret."""

    secretKey: str
    remoteKey: str
    remoteProperty: Optional[str] = None


class ExternalSecret(BaseModel):
    """Sync a Secret from an external store (External Secrets Operator).

    Renders an ``external-secrets.io/v1beta1`` ExternalSecret that the operator
    materializes into a Kubernetes Secret of name ``secretName`` (default: the
    ExternalSecret name), which env entries can then reference via ``valueFrom``
    / ``envFrom``.
    """

    name: str
    storeRef: str
    storeKind: Literal["SecretStore", "ClusterSecretStore"] = "SecretStore"
    secretName: Optional[str] = None
    refreshInterval: str = "1h"
    data: List[ExternalSecretData] = Field(default_factory=list)


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


class TrafficTarget(BaseModel):
    """One entry of a Knative-style traffic split.

    Each entry routes ``percent`` of requests to either a named revision
    (``revisionName``) or the latest ready revision (``latestRevision: true``),
    optionally exposing it under a sub-route ``tag``. Exactly one of
    ``revisionName`` / ``latestRevision`` must be set.
    """

    revisionName: Optional[str] = None
    latestRevision: Optional[bool] = None
    percent: int
    tag: Optional[str] = None

    @field_validator("percent")
    @classmethod
    def _percent_in_range(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("percent must be between 0 and 100")
        return v

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "TrafficTarget":
        pins = self.revisionName is not None
        latest = self.latestRevision is not None
        if pins == latest:
            raise ValueError(
                "a traffic entry must set exactly one of revisionName or latestRevision"
            )
        return self


class ElpioServiceSpec(BaseModel):
    """Desired state of an ElpioService (the CRD ``.spec``)."""

    image: ImageRef
    port: int = 8080
    env: List[EnvVar] = Field(default_factory=list)
    envFrom: List[EnvFromSource] = Field(default_factory=list)
    externalSecrets: List[ExternalSecret] = Field(default_factory=list)
    resources: Optional[Resources] = None
    readinessProbe: Optional[ReadinessProbe] = None
    scaling: Scaling = Field(default_factory=Scaling)
    ingress: Ingress = Field(default_factory=Ingress)
    serviceAccount: Optional[str] = None
    traffic: List[TrafficTarget] = Field(default_factory=list)

    @field_validator("image", mode="before")
    @classmethod
    def _coerce_image(cls, v):
        return ImageRef.coerce(v)

    @field_validator("traffic")
    @classmethod
    def _traffic_sums_to_100(cls, v: List[TrafficTarget]) -> List[TrafficTarget]:
        if v and sum(t.percent for t in v) != 100:
            raise ValueError("traffic percents must sum to 100")
        return v

    @classmethod
    def from_cr(cls, spec: Optional[dict]) -> "ElpioServiceSpec":
        """Build a spec from a raw CRD ``.spec`` dict (as kopf hands it over)."""
        return cls.model_validate(spec or {})
