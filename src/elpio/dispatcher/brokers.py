# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Broker implementations.

"""Broker implementations.

``MemoryBroker`` backs tests and local dev; ``RedisBroker`` is the first real
backend (a Redis list used as a queue). NATS/RabbitMQ are follow-ups.
"""

from __future__ import annotations

import json
from typing import Iterable, List, Optional

from elpio.dispatcher.core import Broker, Message


class MemoryBroker(Broker):
    def __init__(self, messages: Optional[Iterable[Message]] = None) -> None:
        self._queue: List[Message] = list(messages or [])
        self.acked: List[Message] = []
        self.requeued: List[Message] = []

    def poll(self) -> Optional[Message]:
        return self._queue.pop(0) if self._queue else None

    def ack(self, msg: Message) -> None:
        self.acked.append(msg)

    def nack(self, msg: Message, requeue: bool = True) -> None:
        if requeue:
            self._queue.append(msg)
            self.requeued.append(msg)


class RedisBroker(Broker):
    """A Redis list as a FIFO queue (LPOP to consume, RPUSH to requeue)."""

    def __init__(self, address: str, queue: str) -> None:
        import redis

        host, _, port = address.partition(":")
        self._client = redis.Redis(host=host, port=int(port or 6379))
        self._queue = queue
        self._seq = 0

    def poll(self) -> Optional[Message]:
        raw = self._client.lpop(self._queue)
        if raw is None:
            return None
        self._seq += 1
        return Message(id=f"{self._queue}-{self._seq}", body=json.loads(raw))

    def ack(self, msg: Message) -> None:
        # LPOP already removed it; nothing to do.
        return None

    def nack(self, msg: Message, requeue: bool = True) -> None:
        if requeue:
            self._client.rpush(self._queue, json.dumps(msg.body))
