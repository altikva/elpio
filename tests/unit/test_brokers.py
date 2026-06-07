# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the brokers.

import pytest

from elpio.dispatcher import brokers
from elpio.dispatcher.brokers import BROKERS, make_broker


def test_registry_covers_all_broker_types():
    assert set(BROKERS) == {"redis", "rabbitmq", "nats"}


def test_make_broker_dispatches_to_the_registered_class(monkeypatch):
    built = {}

    class FakeBroker:
        def __init__(self, address, queue, dlq=None):
            built.update(address=address, queue=queue, dlq=dlq)

    monkeypatch.setitem(BROKERS, "redis", FakeBroker)
    b = make_broker("redis", "redis.infra:6379", "emails", dlq="emails:dead")
    assert isinstance(b, FakeBroker)
    assert built == {"address": "redis.infra:6379", "queue": "emails", "dlq": "emails:dead"}


def test_make_broker_unknown_type_exits():
    with pytest.raises(SystemExit):
        make_broker("kafka", "k:9092", "q")


def test_build_from_env_uses_the_registry(monkeypatch):
    built = {}

    class FakeBroker:
        def __init__(self, address, queue, dlq=None):
            built.update(type="rabbitmq", address=address, queue=queue, dlq=dlq)

    monkeypatch.setitem(BROKERS, "rabbitmq", FakeBroker)
    monkeypatch.setenv("ELPIO_BROKER_TYPE", "rabbitmq")
    monkeypatch.setenv("ELPIO_BROKER_ADDRESS", "rabbit.infra:5672")
    monkeypatch.setenv("ELPIO_QUEUE", "jobs")
    monkeypatch.setenv("ELPIO_HANDLER_URL", "http://worker.demo")
    monkeypatch.setenv("ELPIO_DLQ", "jobs.dead")

    from elpio.dispatcher.main import build_from_env

    dispatcher = build_from_env()
    assert dispatcher is not None
    assert built == {
        "type": "rabbitmq",
        "address": "rabbit.infra:5672",
        "queue": "jobs",
        "dlq": "jobs.dead",
    }


def test_broker_classes_are_importable_without_their_libs():
    # Referencing the registry must not import pika/nats/redis.
    assert brokers.BROKERS["nats"].__name__ == "NatsBroker"
    assert brokers.BROKERS["rabbitmq"].__name__ == "RabbitMQBroker"


class _FakeLoop:
    """Stands in for an asyncio loop: tracks close() calls without a real loop."""

    def __init__(self):
        self.closed = False
        self.run_calls = 0

    def is_closed(self):
        return self.closed

    def run_until_complete(self, coro):
        self.run_calls += 1
        return None

    def close(self):
        self.closed = True


class _FakeConn:
    def __init__(self):
        self.close_count = 0

    def close(self):
        # The real client's close() is a coroutine, but the fake loop never
        # awaits it; return a plain sentinel so no un-awaited-coroutine warning
        # is raised. The fake loop's run_until_complete ignores the argument.
        self.close_count += 1
        return None


def _make_nats_broker_without_connecting():
    """Build a NatsBroker without touching the nats package or a real loop.

    __init__ would import nats and open a connection, so we bypass it and wire
    in the minimum attributes close() and __del__ rely on.
    """
    broker = brokers.NatsBroker.__new__(brokers.NatsBroker)
    broker._loop = _FakeLoop()
    broker._nc = _FakeConn()
    broker._closed = False
    return broker


def test_nats_close_is_idempotent_and_safe_when_called_twice():
    broker = _make_nats_broker_without_connecting()

    broker.close()
    assert broker._loop.closed is True
    assert broker._closed is True
    runs_after_first = broker._loop.run_calls

    # Second close must be a no-op: no extra run_until_complete, no error.
    broker.close()
    assert broker._loop.run_calls == runs_after_first
    assert broker._loop.closed is True


def test_nats_del_never_raises_even_when_half_constructed():
    # A NatsBroker whose __init__ failed early may be missing attributes; __del__
    # must swallow the resulting AttributeError rather than propagate it.
    broker = brokers.NatsBroker.__new__(brokers.NatsBroker)
    broker.__del__()  # must not raise
