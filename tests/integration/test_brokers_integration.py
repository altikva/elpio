# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-05
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Round-trip the real broker backends against live services.

"""Round-trip the real broker backends against live services.

Skipped unless ELPIO_INTEGRATION=1 (see conftest). `task integration` and the CI
integration job provide redis/rabbitmq/nats. Each test importorskips its client
and skips cleanly if the service can't be reached, so a partial environment
never hard-fails.
"""

import json
import os

import pytest

from elpio.dispatcher.core import Message

pytestmark = pytest.mark.integration

QUEUE = "elpio-it"


def test_redis_roundtrip_and_dead_letter():
    redis = pytest.importorskip("redis")
    from elpio.dispatcher.brokers import RedisBroker

    addr = os.getenv("ELPIO_REDIS_ADDRESS", "localhost:6379")
    host, _, port = addr.partition(":")
    client = redis.Redis(host=host, port=int(port or 6379))
    try:
        client.ping()
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"redis unavailable: {exc}")

    dlq = f"{QUEUE}:dead"
    client.delete(QUEUE, dlq)
    broker = RedisBroker(addr, QUEUE, dlq=dlq)

    client.rpush(QUEUE, json.dumps({"task": "a"}))
    msg = broker.poll()
    assert msg is not None and msg.body == {"task": "a"}
    broker.ack(msg)
    assert broker.poll() is None

    broker.nack(Message(id="x", body={"task": "b"}), requeue=True)
    assert json.loads(client.lpop(QUEUE)) == {"task": "b"}

    broker.dead_letter(Message(id="y", body={"task": "c"}))
    assert json.loads(client.lpop(dlq)) == {"task": "c"}


def test_rabbitmq_roundtrip_and_dead_letter():
    pytest.importorskip("pika")
    from elpio.dispatcher.brokers import RabbitMQBroker

    addr = os.getenv("ELPIO_RABBITMQ_ADDRESS", "localhost:5672")
    try:
        broker = RabbitMQBroker(addr, QUEUE, dlq=f"{QUEUE}.dead")
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"rabbitmq unavailable: {exc}")

    broker._ch.queue_purge(QUEUE)
    broker._ch.queue_purge(f"{QUEUE}.dead")

    broker._ch.basic_publish(exchange="", routing_key=QUEUE, body=json.dumps({"task": "a"}))
    msg = broker.poll()
    assert msg is not None and msg.body == {"task": "a"}
    broker.ack(msg)

    broker._ch.basic_publish(exchange="", routing_key=QUEUE, body=json.dumps({"task": "c"}))
    doomed = broker.poll()
    broker.dead_letter(doomed)
    _method, _props, body = broker._ch.basic_get(f"{QUEUE}.dead", auto_ack=True)
    assert json.loads(body) == {"task": "c"}


def test_nats_jetstream_roundtrip():
    nats = pytest.importorskip("nats")
    import asyncio

    addr = os.getenv("ELPIO_NATS_ADDRESS", "localhost:4222")

    async def provision_and_publish():
        nc = await nats.connect(f"nats://{addr}")
        js = nc.jetstream()
        try:
            await js.delete_stream(QUEUE)
        except Exception:
            pass
        await js.add_stream(name=QUEUE, subjects=[QUEUE])
        await js.publish(QUEUE, json.dumps({"task": "a"}).encode())
        await nc.close()

    try:
        asyncio.run(provision_and_publish())
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"nats/jetstream unavailable: {exc}")

    from elpio.dispatcher.brokers import NatsBroker

    broker = NatsBroker(addr, QUEUE)
    msg = broker.poll()
    assert msg is not None and msg.body == {"task": "a"}
    broker.ack(msg)
