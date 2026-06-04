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
