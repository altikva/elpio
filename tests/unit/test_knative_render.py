# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the knative render.

import pytest
from pydantic import ValidationError

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


def test_knative_no_host_renders_no_domainmapping():
    objs = KnativeEngine().render("api", "demo", SPEC)
    assert [o["kind"] for o in objs] == ["Service"]


def _host_spec(tls=False):
    return ElpioServiceSpec.from_cr(
        {"image": "x:1", "ingress": {"host": "api.example.com", "tls": tls}}
    )


def test_knative_host_renders_domainmapping_referencing_service():
    objs = KnativeEngine().render("api", "demo", _host_spec())
    by = {o["kind"]: o for o in objs}
    assert set(by) == {"Service", "DomainMapping"}
    dm = by["DomainMapping"]
    assert dm["apiVersion"] == "serving.knative.dev/v1beta1"
    assert dm["metadata"]["name"] == "api.example.com"
    assert dm["metadata"]["namespace"] == "demo"
    assert dm["spec"]["ref"] == {
        "name": "api",
        "kind": "Service",
        "apiVersion": "serving.knative.dev/v1",
    }
    assert "tls" not in dm["spec"]


def test_knative_host_with_tls_adds_tls_and_certificate():
    objs = KnativeEngine().render("api", "demo", _host_spec(tls=True))
    by = {o["kind"]: o for o in objs}
    assert set(by) == {"Service", "DomainMapping", "Certificate"}

    dm = by["DomainMapping"]
    assert dm["spec"]["tls"] == {"secretName": "api-tls"}

    cert = by["Certificate"]
    assert cert["apiVersion"] == "cert-manager.io/v1"
    assert cert["metadata"]["name"] == "api.example.com"
    assert cert["spec"]["secretName"] == "api-tls"
    assert cert["spec"]["dnsNames"] == ["api.example.com"]
    assert cert["spec"]["issuerRef"]["name"] == "letsencrypt"
    assert cert["spec"]["issuerRef"]["kind"] == "ClusterIssuer"


def test_knative_host_owner_reference_propagates_to_all_objects():
    owner = {"apiVersion": "elpio.io/v1alpha1", "kind": "ElpioService", "name": "api", "uid": "abc"}
    objs = KnativeEngine().render("api", "demo", _host_spec(tls=True), owner=owner)
    assert all(o["metadata"]["ownerReferences"] == [owner] for o in objs)


def test_knative_no_traffic_renders_no_explicit_traffic_block():
    svc = KnativeEngine().render("api", "demo", SPEC)[0]
    assert "traffic" not in svc["spec"]


def test_knative_renders_80_20_traffic_split():
    spec = ElpioServiceSpec.from_cr(
        {
            "image": "x:1",
            "traffic": [
                {"revisionName": "api-v1", "percent": 80},
                {"revisionName": "api-v2", "percent": 20, "tag": "canary"},
            ],
        }
    )
    svc = KnativeEngine().render("api", "demo", spec)[0]
    assert svc["spec"]["traffic"] == [
        {"percent": 80, "revisionName": "api-v1"},
        {"percent": 20, "revisionName": "api-v2", "tag": "canary"},
    ]


def test_knative_renders_latest_revision_traffic_target():
    spec = ElpioServiceSpec.from_cr(
        {"image": "x:1", "traffic": [{"latestRevision": True, "percent": 100}]}
    )
    svc = KnativeEngine().render("api", "demo", spec)[0]
    assert svc["spec"]["traffic"] == [{"percent": 100, "latestRevision": True}]


def test_traffic_percents_not_100_raises():
    with pytest.raises(ValidationError, match="sum to 100"):
        ElpioServiceSpec.from_cr(
            {
                "image": "x:1",
                "traffic": [
                    {"revisionName": "api-v1", "percent": 80},
                    {"revisionName": "api-v2", "percent": 10},
                ],
            }
        )


def test_traffic_entry_requires_exactly_one_target():
    with pytest.raises(ValidationError, match="exactly one"):
        ElpioServiceSpec.from_cr(
            {
                "image": "x:1",
                "traffic": [
                    {"revisionName": "api-v1", "latestRevision": True, "percent": 100}
                ],
            }
        )
    with pytest.raises(ValidationError, match="exactly one"):
        ElpioServiceSpec.from_cr(
            {"image": "x:1", "traffic": [{"percent": 100}]}
        )


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


# --- Secret/ConfigMap env + External Secrets (#42) ---


def _knative_container(spec):
    return KnativeEngine().render("api", "demo", spec)[0]["spec"]["template"]["spec"][
        "containers"
    ][0]


def test_env_valuefrom_secret_and_configmap_render():
    spec = ElpioServiceSpec.from_cr(
        {
            "image": "ghcr.io/acme/api:1",
            "env": [
                {"name": "PLAIN", "value": "x"},
                {"name": "PW", "valueFrom": {"secretKeyRef": {"name": "db", "key": "password"}}},
                {"name": "CFG", "valueFrom": {"configMapKeyRef": {"name": "cm", "key": "k"}}},
            ],
        }
    )
    env = _knative_container(spec)["env"]
    assert env[0] == {"name": "PLAIN", "value": "x"}
    assert env[1] == {"name": "PW", "valueFrom": {"secretKeyRef": {"name": "db", "key": "password"}}}
    assert env[2] == {"name": "CFG", "valueFrom": {"configMapKeyRef": {"name": "cm", "key": "k"}}}


def test_envfrom_secret_and_configmap_render():
    spec = ElpioServiceSpec.from_cr(
        {
            "image": "ghcr.io/acme/api:1",
            "envFrom": [
                {"secretRef": {"name": "app-secrets"}},
                {"configMapRef": {"name": "app-config"}, "prefix": "CFG_"},
            ],
        }
    )
    env_from = _knative_container(spec)["envFrom"]
    assert env_from[0] == {"secretRef": {"name": "app-secrets"}}
    assert env_from[1] == {"configMapRef": {"name": "app-config"}, "prefix": "CFG_"}


def test_env_requires_exactly_one_of_value_or_valuefrom():
    with pytest.raises(ValidationError):  # neither
        ElpioServiceSpec.from_cr({"image": "x:1", "env": [{"name": "A"}]})
    with pytest.raises(ValidationError):  # both
        ElpioServiceSpec.from_cr(
            {
                "image": "x:1",
                "env": [{"name": "A", "value": "v", "valueFrom": {"secretKeyRef": {"name": "s", "key": "k"}}}],
            }
        )


def test_valuefrom_requires_exactly_one_source():
    with pytest.raises(ValidationError):
        ElpioServiceSpec.from_cr(
            {
                "image": "x:1",
                "env": [
                    {
                        "name": "A",
                        "valueFrom": {
                            "secretKeyRef": {"name": "s", "key": "k"},
                            "configMapKeyRef": {"name": "c", "key": "k"},
                        },
                    }
                ],
            }
        )


def test_external_secret_rendered_as_sibling_object():
    spec = ElpioServiceSpec.from_cr(
        {
            "image": "ghcr.io/acme/api:1",
            "externalSecrets": [
                {
                    "name": "db-creds",
                    "storeRef": "vault",
                    "storeKind": "ClusterSecretStore",
                    "data": [{"secretKey": "password", "remoteKey": "prod/db", "remoteProperty": "pw"}],
                }
            ],
        }
    )
    objs = KnativeEngine().render("api", "demo", spec)
    es = [o for o in objs if o["kind"] == "ExternalSecret"]
    assert len(es) == 1
    es = es[0]
    assert es["apiVersion"] == "external-secrets.io/v1beta1"
    assert es["spec"]["secretStoreRef"] == {"name": "vault", "kind": "ClusterSecretStore"}
    assert es["spec"]["target"]["name"] == "db-creds"  # defaults to ExternalSecret name
    assert es["spec"]["data"][0] == {
        "secretKey": "password",
        "remoteRef": {"key": "prod/db", "property": "pw"},
    }


def test_external_secret_owner_reference_propagates():
    owner = {"apiVersion": "elpio.io/v1alpha1", "kind": "ElpioService", "name": "api", "uid": "u"}
    spec = ElpioServiceSpec.from_cr(
        {
            "image": "ghcr.io/acme/api:1",
            "externalSecrets": [{"name": "creds", "storeRef": "vault"}],
        }
    )
    objs = KnativeEngine().render("api", "demo", spec, owner=owner)
    assert all(o["metadata"]["ownerReferences"] == [owner] for o in objs)


def test_keda_renders_secret_env_and_external_secret():
    spec = ElpioServiceSpec.from_cr(
        {
            "image": "ghcr.io/acme/api:1",
            "env": [{"name": "PW", "valueFrom": {"secretKeyRef": {"name": "db", "key": "p"}}}],
            "envFrom": [{"secretRef": {"name": "app"}}],
            "externalSecrets": [{"name": "creds", "storeRef": "vault"}],
        }
    )
    objs = KedaEngine().render("api", "demo", spec)
    container = next(o for o in objs if o["kind"] == "Deployment")["spec"]["template"]["spec"][
        "containers"
    ][0]
    assert container["env"][0]["valueFrom"]["secretKeyRef"] == {"name": "db", "key": "p"}
    assert container["envFrom"][0] == {"secretRef": {"name": "app"}}
    assert any(o["kind"] == "ExternalSecret" for o in objs)
