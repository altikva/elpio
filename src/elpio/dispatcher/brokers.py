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
import logging
from typing import Any, Iterable, List, Optional

from elpio.dispatcher.core import Broker, Message

logger = logging.getLogger(__name__)


class MemoryBroker(Broker):
    def __init__(self, messages: Optional[Iterable[Message]] = None) -> None:
        self._queue: List[Message] = list(messages or [])
        self.acked: List[Message] = []
        self.requeued: List[Message] = []
        self.dead: List[Message] = []

    def poll(self) -> Optional[Message]:
        return self._queue.pop(0) if self._queue else None

    def ack(self, msg: Message) -> None:
        self.acked.append(msg)

    def nack(self, msg: Message, requeue: bool = True) -> None:
        if requeue:
            self._queue.append(msg)
            self.requeued.append(msg)

    def dead_letter(self, msg: Message) -> None:
        self.dead.append(msg)


class RedisBroker(Broker):
    """A Redis list as a FIFO queue (LPOP to consume, RPUSH to requeue).

    Messages that exhaust their retries are RPUSHed to a dead-letter list
    (``dlq``, defaulting to ``"<queue>:dead"``) instead of being dropped.
    """

    def __init__(self, address: str, queue: str, dlq: Optional[str] = None) -> None:
        import redis

        host, _, port = address.partition(":")
        self._client = redis.Redis(host=host, port=int(port or 6379))
        self._queue = queue
        self._dlq = dlq or f"{queue}:dead"
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

    def dead_letter(self, msg: Message) -> None:
        self._client.rpush(self._dlq, json.dumps(msg.body))


class RabbitMQBroker(Broker):
    """A durable RabbitMQ queue consumed one message at a time (basic_get)."""

    def __init__(self, address: str, queue: str, dlq: Optional[str] = None) -> None:
        import pika

        host, _, port = address.partition(":")
        self._conn = pika.BlockingConnection(
            pika.ConnectionParameters(host=host, port=int(port or 5672))
        )
        self._ch = self._conn.channel()
        self._queue = queue
        self._dlq = dlq or f"{queue}.dead"
        self._ch.queue_declare(queue=queue, durable=True)
        self._ch.queue_declare(queue=self._dlq, durable=True)
        self._inflight: dict = {}

    def poll(self) -> Optional[Message]:
        method, _props, body = self._ch.basic_get(self._queue, auto_ack=False)
        if method is None:
            return None
        mid = str(method.delivery_tag)
        self._inflight[mid] = method.delivery_tag
        return Message(id=mid, body=json.loads(body))

    def ack(self, msg: Message) -> None:
        tag = self._inflight.pop(msg.id, None)
        if tag is not None:
            self._ch.basic_ack(tag)

    def nack(self, msg: Message, requeue: bool = True) -> None:
        tag = self._inflight.pop(msg.id, None)
        if tag is not None:
            self._ch.basic_nack(tag, requeue=requeue)

    def dead_letter(self, msg: Message) -> None:
        self._ch.basic_publish(exchange="", routing_key=self._dlq, body=json.dumps(msg.body))
        tag = self._inflight.pop(msg.id, None)
        if tag is not None:
            self._ch.basic_ack(tag)


class NatsBroker(Broker):
    """A NATS JetStream pull consumer, driven synchronously over a private loop.

    nats is an async client, but the ``Broker`` interface (and the dispatcher
    loop that drives it) is synchronous. We bridge the two by owning a private
    event loop and pumping each coroutine through ``run_until_complete``. That
    sync-over-async bridge is a deliberate tradeoff: it keeps the broker contract
    uniform across redis/rabbitmq/nats at the cost of a private loop and the
    fragility of running one coroutine at a time. The cleaner long-term path is
    an async dispatcher core that awaits the nats client natively; until then we
    guard every ``run_until_complete`` so a transient failure (a dropped
    connection mid-ack, say) logs and is swallowed instead of crashing the loop.
    """

    def __init__(self, address: str, queue: str, dlq: Optional[str] = None) -> None:
        import asyncio

        import nats

        url = address if "://" in address else f"nats://{address}"
        self._loop = asyncio.new_event_loop()
        self._closed = False
        self._nc = self._loop.run_until_complete(nats.connect(servers=[url]))
        self._js = self._nc.jetstream()
        self._subject = queue
        self._dlq = dlq or f"{queue}.dead"
        self._sub = self._loop.run_until_complete(
            self._js.pull_subscribe(self._subject, durable=f"{queue}-workers")
        )
        self._inflight: dict = {}
        self._seq = 0

    def _run(self, coro: Any, *, what: str) -> Any:
        """Drive a coroutine to completion, swallowing transient errors.

        A broken connection during ack/nack/dead_letter/poll must not crash the
        dispatcher loop; we log and return ``None`` so the caller can carry on.
        """
        try:
            return self._loop.run_until_complete(coro)
        except Exception:
            logger.exception("NatsBroker: %s failed", what)
            return None

    def poll(self) -> Optional[Message]:
        msgs = self._run(self._sub.fetch(1, timeout=1), what="poll")
        if not msgs:
            return None
        raw = msgs[0]
        self._seq += 1
        mid = str(self._seq)
        self._inflight[mid] = raw
        return Message(id=mid, body=json.loads(raw.data))

    def ack(self, msg: Message) -> None:
        raw = self._inflight.pop(msg.id, None)
        if raw is not None:
            self._run(raw.ack(), what="ack")

    def nack(self, msg: Message, requeue: bool = True) -> None:
        raw = self._inflight.pop(msg.id, None)
        if raw is not None:
            self._run(raw.nak() if requeue else raw.term(), what="nack")

    def dead_letter(self, msg: Message) -> None:
        self._run(
            self._js.publish(self._dlq, json.dumps(msg.body).encode()),
            what="dead_letter publish",
        )
        raw = self._inflight.pop(msg.id, None)
        if raw is not None:
            self._run(raw.ack(), what="dead_letter ack")

    def close(self) -> None:
        """Close the NATS connection, then the loop. Idempotent.

        Closing the connection first stops the client's background flusher; doing
        it the other way round leaves a coroutine to be GC'd against a closed loop
        ("Event loop is closed"). Safe to call more than once: the ``_closed``
        guard and ``loop.is_closed()`` check both short-circuit a repeat call.
        """
        if self._closed or self._loop.is_closed():
            self._closed = True
            return
        self._closed = True
        try:
            self._loop.run_until_complete(self._nc.close())
        except Exception:
            logger.exception("NatsBroker: close failed")
        finally:
            self._loop.close()

    def __del__(self) -> None:
        # Best-effort safety net for callers that forget close(). Never raise
        # from a finalizer — a partially built object may be missing attrs.
        try:
            self.close()
        except Exception:
            pass


# Broker registry — keyed by ELPIO_BROKER_TYPE. Each class lazily imports its
# client library, so referencing the registry doesn't require every dependency.
BROKERS = {
    "redis": RedisBroker,
    "rabbitmq": RabbitMQBroker,
    "nats": NatsBroker,
}


def make_broker(broker_type: str, address: str, queue: str, dlq: Optional[str] = None) -> Broker:
    try:
        cls = BROKERS[broker_type]
    except KeyError:
        raise SystemExit(
            f"dispatcher: unknown broker {broker_type!r} (expected {sorted(BROKERS)})"
        )
    return cls(address, queue, dlq=dlq)
