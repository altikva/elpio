# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the function render.

from elpio.function import (
    next_action,
    pipelinerun_phase,
    render_function,
    render_pipeline_run,
    render_service,
)
from elpio.models.function import FunctionSpec

SPEC = FunctionSpec.from_cr(
    {
        "source": {"git": {"url": "https://github.com/acme/fn", "revision": "v2"}},
        "runtime": "python",
        "image": "ghcr.io/acme/fn:v2",
        "env": [{"name": "STAGE", "value": "prod"}],
        "scaling": {"minScale": 0, "maxScale": 3},
    }
)


def _by_kind(objs):
    return {o["kind"]: o for o in objs}


def test_renders_pipelinerun_and_service():
    objs = render_function("fn", "demo", SPEC)
    by = _by_kind(objs)
    assert set(by) == {"PipelineRun", "ElpioService"}
    assert by["PipelineRun"]["spec"]["pipelineRef"]["name"] == "elpio-buildpacks"


def test_pipelinerun_carries_source_and_image_params():
    pr = _by_kind(render_function("fn", "demo", SPEC))["PipelineRun"]
    params = {p["name"]: p["value"] for p in pr["spec"]["params"]}
    assert params["SOURCE_URL"] == "https://github.com/acme/fn"
    assert params["SOURCE_REVISION"] == "v2"
    assert params["APP_IMAGE"] == "ghcr.io/acme/fn:v2"


def test_derived_service_runs_built_image():
    svc = _by_kind(render_function("fn", "demo", SPEC))["ElpioService"]
    assert svc["apiVersion"] == "elpio.io/v1alpha1"
    assert svc["spec"]["image"] == "ghcr.io/acme/fn:v2"
    assert svc["spec"]["env"] == [{"name": "STAGE", "value": "prod"}]
    assert svc["spec"]["scaling"]["maxScale"] == 3


def test_archive_source_param():
    spec = FunctionSpec.from_cr(
        {"source": {"archive": "s3://bucket/fn.tgz"}, "runtime": "node", "image": "r/fn:1"}
    )
    pr = _by_kind(render_function("fn", "demo", spec))["PipelineRun"]
    params = {p["name"]: p["value"] for p in pr["spec"]["params"]}
    assert params["SOURCE_ARCHIVE"] == "s3://bucket/fn.tgz"


def test_owner_propagates():
    owner = {"apiVersion": "elpio.io/v1alpha1", "kind": "ElpioFunction", "name": "fn", "uid": "u"}
    objs = render_function("fn", "demo", SPEC, owner=owner)
    assert all(o["metadata"]["ownerReferences"] == [owner] for o in objs)


def test_split_renders_match_combined():
    owner = {"apiVersion": "elpio.io/v1alpha1", "kind": "ElpioFunction", "name": "fn", "uid": "u"}
    pr = render_pipeline_run("fn", "demo", SPEC, owner)
    svc = render_service("fn", "demo", SPEC, owner)
    assert pr["kind"] == "PipelineRun" and svc["kind"] == "ElpioService"
    assert render_function("fn", "demo", SPEC, owner) == [pr, svc]


def test_pipelinerun_phase_from_conditions():
    assert pipelinerun_phase(None) == "Pending"
    assert pipelinerun_phase({}) == "Pending"
    assert pipelinerun_phase({"conditions": [{"type": "Succeeded", "status": "Unknown"}]}) == "Running"
    assert pipelinerun_phase({"conditions": [{"type": "Succeeded", "status": "True"}]}) == "Succeeded"
    assert pipelinerun_phase({"conditions": [{"type": "Succeeded", "status": "False"}]}) == "Failed"


def test_next_action_gating():
    assert next_action("Pending", False) == "wait"
    assert next_action("Running", False) == "wait"
    assert next_action("Succeeded", False) == "apply"
    assert next_action("Succeeded", True) == "noop"
    assert next_action("Failed", False) == "fail"
