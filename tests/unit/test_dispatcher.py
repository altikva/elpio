# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the dispatcher.

from elpio.dispatcher.core import Dispatcher, Message
from elpio.dispatcher.brokers import MemoryBroker
from elpio.dispatcher.main import tick


class RecordingPoster:
    def __init__(self, status=200):
        self.status = status
        self.calls = []

    def __call__(self, url, body):
        self.calls.append((url, body))
        return self.status() if callable(self.status) else self.status


def test_empty_queue_step_is_false():
    d = Dispatcher(MemoryBroker(), "http://h", poster=RecordingPoster())
    assert d.step() is False


def test_success_acks_and_posts_body():
    broker = MemoryBroker([Message(id="1", body={"task": "a"})])
    poster = RecordingPoster(200)
    d = Dispatcher(broker, "http://handler", poster=poster)
    assert d.step() is True
    assert poster.calls == [("http://handler", {"task": "a"})]
    assert [m.id for m in broker.acked] == ["1"]
    assert broker.requeued == []


def test_failure_requeues_until_max_then_dead_letters():
    msg = Message(id="1", body={"task": "x"})
    broker = MemoryBroker([msg])
    d = Dispatcher(broker, "http://h", poster=RecordingPoster(500), max_attempts=3)
    # attempt 1 and 2 requeue, attempt 3 hits max and dead-letters
    d.step()
    d.step()
    assert msg in broker.requeued
    assert broker.dead == []
    d.step()
    assert msg.attempts == 3
    assert broker.dead == [msg]
    assert broker.acked == []  # exhausted messages are not silently acked


def test_network_exception_counts_as_failure():
    def boom(url, body):
        raise RuntimeError("connection refused")

    msg = Message(id="1")
    broker = MemoryBroker([msg])
    Dispatcher(broker, "http://h", poster=boom, max_attempts=1).step()
    assert broker.dead == [msg]  # max_attempts=1 → dead-lettered on first failure


def test_rate_limit_sleeps_between_messages():
    slept = []
    broker = MemoryBroker([Message(id="1")])
    d = Dispatcher(broker, "http://h", poster=RecordingPoster(200), rate_limit=4, sleeper=slept.append)
    d.step()
    assert slept == [0.25]  # 1 / rate_limit


def test_default_dead_letter_drops_via_ack():
    # A broker that implements only poll/ack/nack inherits the base dead_letter,
    # which falls back to ack (drop).
    from elpio.dispatcher.core import Broker

    class MinimalBroker(Broker):
        def __init__(self, msg):
            self._msg = msg
            self.acked = []

        def poll(self):
            m, self._msg = self._msg, None
            return m

        def ack(self, msg):
            self.acked.append(msg)

        def nack(self, msg, requeue=True):
            pass

    msg = Message(id="1")
    broker = MinimalBroker(msg)
    Dispatcher(broker, "http://h", poster=RecordingPoster(500), max_attempts=1).step()
    assert broker.acked == [msg]


def test_tick_posts_to_handler(monkeypatch):
    monkeypatch.setenv("ELPIO_HANDLER_URL", "http://handler.demo")
    poster = RecordingPoster(200)
    assert tick(poster=poster) == 200
    assert poster.calls == [("http://handler.demo", {"event": "tick"})]
