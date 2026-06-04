# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the task render.

from elpio.models.task import TaskSpec
from elpio.task import render_task

REDIS = TaskSpec.from_cr(
    {
        "broker": {"type": "redis", "address": "redis.infra:6379"},
        "queue": "emails",
        "handlerService": "mailer",
        "rateLimit": 50,
        "retry": {"maxAttempts": 5},
    }
)


def _by_kind(objs):
    out = {}
    for o in objs:
        out.setdefault(o["kind"], []).append(o)
    return out


def test_renders_dispatcher_and_scaledobject():
    by = _by_kind(render_task("emailq", "demo", REDIS))
    assert set(by) == {"Deployment", "ScaledObject"}


def test_dispatcher_points_at_handler_service():
    dep = _by_kind(render_task("emailq", "demo", REDIS))["Deployment"][0]
    env = {e["name"]: e["value"] for e in dep["spec"]["template"]["spec"]["containers"][0]["env"]}
    assert env["ELPIO_HANDLER_URL"] == "http://mailer.demo.svc.cluster.local"
    assert env["ELPIO_QUEUE"] == "emails"
    assert env["ELPIO_MAX_ATTEMPTS"] == "5"


def test_redis_trigger_shape():
    so = _by_kind(render_task("emailq", "demo", REDIS))["ScaledObject"][0]
    trig = so["spec"]["triggers"][0]
    assert trig["type"] == "redis"
    assert trig["metadata"]["listName"] == "emails"
    assert trig["metadata"]["listLength"] == "50"


def test_nats_is_the_default_trigger():
    spec = TaskSpec.from_cr(
        {"broker": {"type": "nats", "address": "nats.infra:8222"}, "queue": "jobs", "handlerService": "worker"}
    )
    trig = _by_kind(render_task("jobs", "demo", spec))["ScaledObject"][0]["spec"]["triggers"][0]
    assert trig["type"] == "nats-jetstream"
    assert trig["metadata"]["stream"] == "jobs"


def test_schedule_adds_cronjob():
    spec = TaskSpec.from_cr(
        {
            "broker": {"type": "redis", "address": "r:6379"},
            "queue": "q",
            "handlerService": "h",
            "schedule": "*/5 * * * *",
        }
    )
    by = _by_kind(render_task("t", "demo", spec))
    assert "CronJob" in by
    assert by["CronJob"][0]["spec"]["schedule"] == "*/5 * * * *"


def test_no_schedule_no_cronjob():
    assert "CronJob" not in _by_kind(render_task("emailq", "demo", REDIS))


def test_owner_propagates():
    owner = {"apiVersion": "elpio.io/v1alpha1", "kind": "ElpioTask", "name": "t", "uid": "u"}
    objs = render_task("t", "demo", REDIS, owner=owner)
    assert all(o["metadata"]["ownerReferences"] == [owner] for o in objs)
