# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the brokers.

import sys
import types

import pytest

from elpio.dispatcher import brokers
from elpio.dispatcher.brokers import (
    BROKERS,
    Credentials,
    TLSConfig,
    credentials_from_env,
    make_broker,
    resolve_credentials,
    tls_from_env,
)


def test_registry_covers_all_broker_types():
    assert set(BROKERS) == {"redis", "rabbitmq", "nats"}


def test_make_broker_dispatches_to_the_registered_class(monkeypatch):
    built = {}

    class FakeBroker:
        def __init__(self, address, queue, dlq=None, *, creds=None, tls=None):
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
        def __init__(self, address, queue, dlq=None, *, creds=None, tls=None):
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


# ---- credential resolution --------------------------------------------------


def test_resolve_credentials_prefers_env_over_inline(monkeypatch):
    monkeypatch.setenv("MY_USER", "from-env")
    monkeypatch.setenv("MY_PASS", "s3cret")
    creds = resolve_credentials(
        username="inline",
        username_env="MY_USER",
        password_env="MY_PASS",
    )
    assert creds.username == "from-env"  # env wins over the inline literal
    assert creds.password == "s3cret"  # password is env-only


def test_resolve_credentials_falls_back_to_inline_when_env_absent():
    creds = resolve_credentials(username="inline", token="tok")
    assert creds.username == "inline"
    assert creds.token == "tok"
    assert creds.password is None


def test_credentials_and_tls_from_env(monkeypatch):
    monkeypatch.setenv("ELPIO_BROKER_PASSWORD_ENV", "PW")
    monkeypatch.setenv("PW", "hunter2")
    monkeypatch.setenv("ELPIO_BROKER_USERNAME", "svc")
    monkeypatch.setenv("ELPIO_BROKER_TLS", "true")
    monkeypatch.setenv("ELPIO_BROKER_TLS_CA", "/etc/ca/ca.pem")
    creds = credentials_from_env()
    tls = tls_from_env()
    assert creds.username == "svc"
    assert creds.password == "hunter2"
    assert tls.enabled is True
    assert tls.ca_cert == "/etc/ca/ca.pem"
    assert tls.insecure_skip_verify is False


# ---- per-broker connection wiring (no real sockets) -------------------------


def test_redis_broker_builds_ssl_and_credential_kwargs(monkeypatch):
    captured = {}

    fake_redis = types.ModuleType("redis")

    class FakeRedis:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_redis.Redis = FakeRedis
    monkeypatch.setitem(sys.modules, "redis", fake_redis)

    brokers.RedisBroker(
        "redis.infra:6380",
        "emails",
        creds=Credentials(username="u", password="p"),
        tls=TLSConfig(enabled=True, ca_cert="/ca.pem"),
    )
    assert captured["host"] == "redis.infra"
    assert captured["port"] == 6380
    assert captured["username"] == "u"
    assert captured["password"] == "p"
    assert captured["ssl"] is True
    assert captured["ssl_ca_certs"] == "/ca.pem"


def test_rabbitmq_broker_builds_credentials_and_ssl_options(monkeypatch):
    captured = {}

    fake_pika = types.ModuleType("pika")

    class FakePlainCredentials:
        def __init__(self, username, password):
            self.username = username
            self.password = password

    class FakeSSLOptions:
        def __init__(self, context, server_hostname=None):
            self.context = context
            self.server_hostname = server_hostname

    class FakeConnectionParameters:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeChannel:
        def queue_declare(self, *a, **k):
            pass

    class FakeBlockingConnection:
        def __init__(self, params):
            pass

        def channel(self):
            return FakeChannel()

    fake_pika.PlainCredentials = FakePlainCredentials
    fake_pika.SSLOptions = FakeSSLOptions
    fake_pika.ConnectionParameters = FakeConnectionParameters
    fake_pika.BlockingConnection = FakeBlockingConnection
    monkeypatch.setitem(sys.modules, "pika", fake_pika)

    brokers.RabbitMQBroker(
        "rabbit.infra:5671",
        "jobs",
        creds=Credentials(username="u", password="p"),
        tls=TLSConfig(enabled=True),
    )
    assert captured["host"] == "rabbit.infra"
    assert captured["port"] == 5671
    assert isinstance(captured["credentials"], FakePlainCredentials)
    assert captured["credentials"].username == "u"
    assert captured["credentials"].password == "p"
    assert isinstance(captured["ssl_options"], FakeSSLOptions)
    assert captured["ssl_options"].server_hostname == "rabbit.infra"


def test_nats_broker_builds_tls_and_auth_connect_kwargs(monkeypatch):
    captured = {}

    fake_nats = types.ModuleType("nats")

    class FakeJS:
        pass

    class FakeNC:
        def jetstream(self):
            return FakeJS()

    async def fake_connect(**kwargs):
        captured.update(kwargs)
        return FakeNC()

    fake_nats.connect = fake_connect
    monkeypatch.setitem(sys.modules, "nats", fake_nats)

    # Stub out pull_subscribe so __init__ completes without a real stream.
    monkeypatch.setattr(
        brokers.NatsBroker,
        "_run_init_subscribe",
        lambda self, js, subject, durable: None,
        raising=False,
    )

    broker = brokers.NatsBroker(
        "nats.infra:4222",
        "jobs",
        creds=Credentials(username="u", password="p", token="tok"),
        tls=TLSConfig(enabled=True),
    )
    try:
        assert captured["servers"] == ["tls://nats.infra:4222"]
        assert captured["user"] == "u"
        assert captured["password"] == "p"
        assert captured["token"] == "tok"
        assert captured["tls"] is not None
    finally:
        broker.close()
