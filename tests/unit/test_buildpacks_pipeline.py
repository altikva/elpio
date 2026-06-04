# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the buildpacks pipeline.

from pathlib import Path

import yaml

from elpio.function import render_pipeline_run
from elpio.models.function import FunctionSpec

PIPELINE = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "deploy/tekton/buildpacks-pipeline.yaml").read_text()
)


def test_pipeline_is_named_what_the_render_references():
    spec = FunctionSpec.from_cr(
        {"source": {"git": {"url": "u"}}, "runtime": "python", "image": "img:1"}
    )
    pr = render_pipeline_run("fn", "demo", spec)
    assert PIPELINE["metadata"]["name"] == pr["spec"]["pipelineRef"]["name"] == "elpio-buildpacks"


def test_pipeline_declares_every_param_the_render_can_send():
    declared = {p["name"] for p in PIPELINE["spec"]["params"]}
    # union of params across git + archive render paths
    git = FunctionSpec.from_cr(
        {"source": {"git": {"url": "u", "subPath": "svc"}}, "runtime": "py", "image": "i:1"}
    )
    arch = FunctionSpec.from_cr(
        {"source": {"archive": "s3://b/x.tgz"}, "runtime": "py", "image": "i:1"}
    )
    sent = set()
    for spec in (git, arch):
        sent |= {p["name"] for p in render_pipeline_run("fn", "demo", spec)["spec"]["params"]}
    missing = sent - declared
    assert not missing, f"PipelineRun would send undeclared params: {missing}"


def test_pipeline_has_clone_then_build():
    tasks = [t["name"] for t in PIPELINE["spec"]["tasks"]]
    assert tasks == ["fetch", "build"]
    build = next(t for t in PIPELINE["spec"]["tasks"] if t["name"] == "build")
    assert build["runAfter"] == ["fetch"]
