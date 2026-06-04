# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: ``ElpioTask`` spec — a durable queue with retries/scheduling
#              (Cloud Tasks).

"""``ElpioTask`` spec — a durable queue with retries/scheduling (Cloud Tasks).

A Task binds a broker queue to an ElpioService handler. It reconciles to a
dispatcher Deployment scaled by KEDA off the queue depth, plus an optional
CronJob for scheduled dispatch. The Pydantic model mirrors
``deploy/crds/elpiotask.yaml`` — keep the two in sync.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

GROUP = "elpio.io"
VERSION = "v1alpha1"
KIND = "ElpioTask"
PLURAL = "elpiotasks"


class RetryConfig(BaseModel):
    maxAttempts: int = 3


class BrokerConfig(BaseModel):
    type: Literal["nats", "redis", "rabbitmq"] = "nats"
    address: str


class TaskSpec(BaseModel):
    """Desired state of an ElpioTask (the CRD ``.spec``)."""

    broker: BrokerConfig
    queue: str
    handlerService: str
    rateLimit: Optional[int] = None
    retry: RetryConfig = Field(default_factory=RetryConfig)
    schedule: Optional[str] = None
    minReplicas: int = 0
    maxReplicas: int = 10
    dispatcherImage: str = "ghcr.io/altikva/elpio-dispatcher:latest"

    @classmethod
    def from_cr(cls, spec: Optional[dict]) -> "TaskSpec":
        return cls.model_validate(spec or {})
