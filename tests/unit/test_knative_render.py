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


def test_keda_renders_deployment_service_scaledobject():
    kinds = {o["kind"] for o in KedaEngine().render("api", "demo", SPEC)}
    assert kinds == {"Deployment", "Service", "ScaledObject"}
