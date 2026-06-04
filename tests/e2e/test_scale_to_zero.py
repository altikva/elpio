"""End-to-end smoke test (Phase 0 harness).

Skipped unless ``ELPIO_E2E=1`` and a kind cluster with Knative (or KEDA) is up.
The flow this asserts, per RFC 0001 Phase 0 exit criteria:

    kind up -> elpio install -> elpio deploy examples/hello.yaml
            -> ElpioService becomes Ready -> a KnativeService exists
            -> after idle, replicas scale to zero.

This is intentionally a thin executable spec for now; wire the assertions to the
cluster as the reconciler lands in Phase 1.
"""

import subprocess

import pytest

pytestmark = pytest.mark.e2e


def _kubectl(*args: str) -> str:
    return subprocess.run(
        ["kubectl", *args], check=True, capture_output=True, text=True
    ).stdout


def test_elpioservice_reconciles_to_knative():
    # Assumes `elpio install` + `elpio deploy -f examples/hello.yaml` already ran.
    out = _kubectl("get", "elpioservice", "hello", "-n", "default", "-o", "jsonpath={.status.ready}")
    assert out == "true"

    ksvc = _kubectl("get", "ksvc", "hello", "-n", "default", "-o", "jsonpath={.metadata.name}")
    assert ksvc == "hello"
