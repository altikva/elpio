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
    """A NATS JetStream pull consumer, driven synchronously over a private loop."""

    def __init__(self, address: str, queue: str, dlq: Optional[str] = None) -> None:
        import asyncio

        import nats

        url = address if "://" in address else f"nats://{address}"
        self._loop = asyncio.new_event_loop()
        self._nc = self._loop.run_until_complete(nats.connect(servers=[url]))
        self._js = self._nc.jetstream()
        self._subject = queue
        self._dlq = dlq or f"{queue}.dead"
        self._sub = self._loop.run_until_complete(
            self._js.pull_subscribe(self._subject, durable=f"{queue}-workers")
        )
        self._inflight: dict = {}
        self._seq = 0

    def poll(self) -> Optional[Message]:
        try:
            msgs = self._loop.run_until_complete(self._sub.fetch(1, timeout=1))
        except Exception:
            return None
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
            self._loop.run_until_complete(raw.ack())

    def nack(self, msg: Message, requeue: bool = True) -> None:
        raw = self._inflight.pop(msg.id, None)
        if raw is not None:
            self._loop.run_until_complete(raw.nak() if requeue else raw.term())

    def dead_letter(self, msg: Message) -> None:
        self._loop.run_until_complete(self._js.publish(self._dlq, json.dumps(msg.body).encode()))
        raw = self._inflight.pop(msg.id, None)
        if raw is not None:
            self._loop.run_until_complete(raw.ack())

    def close(self) -> None:
        """Close the NATS connection, then the loop.

        Closing the connection first stops the client's background flusher; doing
        it the other way round leaves a coroutine to be GC'd against a closed loop
        ("Event loop is closed"). Safe to call more than once.
        """
        if self._loop.is_closed():
            return
        try:
            self._loop.run_until_complete(self._nc.close())
        except Exception:
            pass
        finally:
            self._loop.close()


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
