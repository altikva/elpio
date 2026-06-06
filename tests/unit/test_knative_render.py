# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the knative render.

from elpio.engines.knative import KnativeEngine
from elpio.engines.keda import KedaEngine
from elpio.models.service import ElpioServiceSpec

SPEC = ElpioServiceSpec.from_cr(
    {
        "image": "ghcr.io/acme/api:1.0",
        "port": 9000,
        "env": [{"name": "TARGET", "value": "Elpio"}],
        "scaling": {"minScale": 0, "maxScale": 5, "target": 50, "metric": "concurrency"},
    }
)


def test_knative_renders_a_service():
    objs = KnativeEngine().render("api", "demo", SPEC)
    assert len(objs) == 1
    svc = objs[0]
    assert svc["apiVersion"] == "serving.knative.dev/v1"
    assert svc["kind"] == "Service"
    assert svc["metadata"]["name"] == "api"

    ann = svc["spec"]["template"]["metadata"]["annotations"]
    assert ann["autoscaling.knative.dev/min-scale"] == "0"
    assert ann["autoscaling.knative.dev/max-scale"] == "5"
    assert ann["autoscaling.knative.dev/metric"] == "concurrency"
    assert ann["autoscaling.knative.dev/target"] == "50"

    container = svc["spec"]["template"]["spec"]["containers"][0]
    assert container["image"] == "ghcr.io/acme/api:1.0"
    assert container["ports"][0]["containerPort"] == 9000
    assert container["env"][0] == {"name": "TARGET", "value": "Elpio"}
    assert svc["spec"]["template"]["spec"]["containerConcurrency"] == 50


def test_knative_owner_reference_propagates():
    owner = {"apiVersion": "elpio.io/v1alpha1", "kind": "ElpioService", "name": "api", "uid": "abc"}
    svc = KnativeEngine().render("api", "demo", SPEC, owner=owner)[0]
    assert svc["metadata"]["ownerReferences"] == [owner]


def _cr(metric, minscale=0):
    return ElpioServiceSpec.from_cr(
        {"image": "x:1", "port": 8080, "scaling": {"minScale": minscale, "maxScale": 5, "target": 50, "metric": metric}}
    )


def test_keda_concurrency_renders_http_scaled_object_with_scale_to_zero():
    # The default (concurrency) metric is request-driven → keda-http-add-on, which
    # gives true scale-to-zero (replicas.min == 0).
    objs = KedaEngine().render("api", "demo", SPEC)
    by = {o["kind"]: o for o in objs}
    assert set(by) == {"Deployment", "Service", "HTTPScaledObject"}
    hso = by["HTTPScaledObject"]
    assert hso["apiVersion"] == "http.keda.sh/v1alpha1"
    assert hso["spec"]["replicas"]["min"] == 0  # scales to zero
    assert hso["spec"]["scalingMetric"]["concurrency"]["targetValue"] == 50
    assert hso["spec"]["scaleTargetRef"] == {
        "name": "api", "kind": "Deployment", "apiVersion": "apps/v1", "service": "api", "port": 9000
    }
    assert by["Deployment"]["spec"]["replicas"] == 0  # the add-on holds it at zero


def test_keda_rps_uses_request_rate_metric():
    hso = next(o for o in KedaEngine().render("api", "demo", _cr("rps")) if o["kind"] == "HTTPScaledObject")
    assert hso["spec"]["scalingMetric"]["requestRate"]["targetValue"] == 50


def test_keda_cpu_metric_uses_cpu_scaledobject_floored_at_one():
    objs = KedaEngine().render("api", "demo", _cr("cpu", minscale=0))
    by = {o["kind"]: o for o in objs}
    assert set(by) == {"Deployment", "Service", "ScaledObject"}
    so = by["ScaledObject"]
    assert so["spec"]["triggers"][0]["type"] == "cpu"
    assert so["spec"]["minReplicaCount"] == 1  # cpu can't scale to zero
    assert by["Deployment"]["spec"]["replicas"] == 1


def test_keda_http_owner_propagates():
    owner = {"apiVersion": "elpio.io/v1alpha1", "kind": "ElpioService", "name": "api", "uid": "u"}
    objs = KedaEngine().render("api", "demo", SPEC, owner=owner)
    assert all(o["metadata"]["ownerReferences"] == [owner] for o in objs)
