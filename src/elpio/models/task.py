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


class BrokerTLS(BaseModel):
    """TLS settings for a broker connection.

    ``caCert`` is a PEM bundle path mounted into the dispatcher pod (for example
    from a Secret). ``insecureSkipVerify`` disables certificate verification and
    is meant for local/dev clusters only.
    """

    enabled: bool = False
    caCert: Optional[str] = None
    insecureSkipVerify: bool = False


class BrokerAuth(BaseModel):
    """Broker credentials, sourced from the environment, never inline plaintext.

    Precedence for each value: the ``*Env`` field names an env var read at
    connect time and wins; the inline literal (``username``/``token``) is a
    convenience fallback for non-sensitive values. Passwords have no inline
    field on purpose — they must come from ``passwordEnv`` (an env var the
    dispatcher pod gets from a Secret).
    """

    username: Optional[str] = None
    usernameEnv: Optional[str] = None
    passwordEnv: Optional[str] = None
    token: Optional[str] = None
    tokenEnv: Optional[str] = None


class BrokerConfig(BaseModel):
    type: Literal["nats", "redis", "rabbitmq"] = "nats"
    address: str
    tls: BrokerTLS = Field(default_factory=BrokerTLS)
    auth: BrokerAuth = Field(default_factory=BrokerAuth)


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
