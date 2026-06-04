# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Broker-agnostic dispatch loop.

"""Broker-agnostic dispatch loop.

A ``Dispatcher`` polls a ``Broker`` for a ``Message`` and POSTs it to the handler
URL. 2xx acks; anything else retries up to ``max_attempts`` (then the message is
dropped — a dead-letter queue is a follow-up). Both the broker and the HTTP
poster are injectable, so the loop is testable without a network or a broker.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

Poster = Callable[[str, Dict[str, Any]], int]


@dataclass
class Message:
    id: str
    body: Dict[str, Any] = field(default_factory=dict)
    attempts: int = 0


class Broker(ABC):
    @abstractmethod
    def poll(self) -> Optional[Message]:
        """Return the next message, or None if the queue is empty."""

    @abstractmethod
    def ack(self, msg: Message) -> None:
        """Acknowledge successful processing."""

    @abstractmethod
    def nack(self, msg: Message, requeue: bool = True) -> None:
        """Negative-acknowledge; requeue for another attempt by default."""

    def dead_letter(self, msg: Message) -> None:
        """Route a message that exhausted its retries.

        Default behaviour drops it (acks). Brokers that support a dead-letter
        queue override this to preserve the message for inspection.
        """
        self.ack(msg)


def httpx_poster(timeout: float = 30.0) -> Poster:
    def post(url: str, body: Dict[str, Any]) -> int:
        import httpx

        return httpx.post(url, json=body, timeout=timeout).status_code

    return post


class Dispatcher:
    def __init__(
        self,
        broker: Broker,
        handler_url: str,
        *,
        poster: Optional[Poster] = None,
        max_attempts: int = 3,
        rate_limit: Optional[int] = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._broker = broker
        self._url = handler_url
        self._poster = poster or httpx_poster()
        self._max = max_attempts
        self._rate = rate_limit
        self._sleep = sleeper

    def step(self) -> bool:
        """Process at most one message. Returns False if the queue was empty."""
        msg = self._broker.poll()
        if msg is None:
            return False
        try:
            status = self._poster(self._url, msg.body)
        except Exception:
            status = 0
        if 200 <= status < 300:
            self._broker.ack(msg)
        else:
            msg.attempts += 1
            if msg.attempts >= self._max:
                self._broker.dead_letter(msg)  # exhausted retries → DLQ (or drop)
            else:
                self._broker.nack(msg, requeue=True)
        if self._rate:
            self._sleep(1.0 / self._rate)
        return True

    def run(self, *, idle_sleep: float = 1.0) -> None:  # pragma: no cover - infinite loop
        while True:
            if not self.step():
                self._sleep(idle_sleep)
