# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: ``ElpioFunction`` spec — source → container (Cloud Functions
#              equivalent).

"""``ElpioFunction`` spec — source → container (Cloud Functions equivalent).

A Function declares where its source lives and which runtime to build it with; a
Tekton + Cloud Native Buildpacks pipeline turns that into an image, and the
operator then produces an ``ElpioService`` from the built image. The Pydantic
model mirrors ``deploy/crds/elpiofunction.yaml`` — keep the two in sync.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from elpio.models.service import EnvVar, Scaling

GROUP = "elpio.io"
VERSION = "v1alpha1"
KIND = "ElpioFunction"
PLURAL = "elpiofunctions"


class GitSource(BaseModel):
    url: str
    revision: str = "main"
    subPath: Optional[str] = None


class SourceConfig(BaseModel):
    git: Optional[GitSource] = None
    archive: Optional[str] = None


class FunctionSpec(BaseModel):
    """Desired state of an ElpioFunction (the CRD ``.spec``)."""

    source: SourceConfig
    runtime: str
    # Target image the build pushes to and the resulting service runs.
    image: str
    entrypoint: Optional[str] = None
    builder: str = "paketobuildpacks/builder-jammy-base"
    port: int = 8080
    env: List[EnvVar] = Field(default_factory=list)
    scaling: Scaling = Field(default_factory=Scaling)
    serviceAccount: Optional[str] = None

    @classmethod
    def from_cr(cls, spec: Optional[dict]) -> "FunctionSpec":
        return cls.model_validate(spec or {})
