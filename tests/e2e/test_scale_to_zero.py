# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: End-to-end scale-to-zero test (Phase 0 exit criteria).

"""End-to-end scale-to-zero test (Phase 0 exit criteria).

Skipped unless ``ELPIO_E2E=1`` and a cluster with Knative + the Elpio operator is
up (``task e2e-up`` provisions kind + Knative/KEDA; run the operator in-cluster
or via ``task operator-run``). The flow this asserts end-to-end:

    deploy examples/hello.yaml
        -> ElpioService becomes Ready and a KnativeService exists
        -> a request wakes it: the revision Deployment scales 0 -> N
        -> after the idle window, it scales back to 0.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest

# Knative-engine path: a request to the cluster-local Service is caught by the
# Knative activator, which wakes the scaled-to-zero revision. Skip when the
# operator under test is running a different engine.
_ENGINE = os.getenv("ELPIO_ENGINE", "knative").lower()
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(_ENGINE != "knative", reason=f"knative-engine e2e (ELPIO_ENGINE={_ENGINE})"),
]

NS = "default"
NAME = "hello"
HELLO = Path(__file__).resolve().parents[2] / "examples" / "hello.yaml"


def _kubectl(*args: str, check: bool = True) -> str:
    return subprocess.run(
        ["kubectl", *args], check=check, capture_output=True, text=True
    ).stdout.strip()


def _wait(predicate, *, timeout: float, interval: float = 3.0, what: str = "condition"):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"timed out after {timeout}s waiting for {what} (last={last!r})")


def _revision_replicas() -> int:
    out = _kubectl(
        "get", "deploy", "-n", NS,
        "-l", f"serving.knative.dev/service={NAME}",
        "-o", "jsonpath={.items[*].status.replicas}",
        check=False,
    )
    return sum(int(x) for x in out.split()) if out else 0


@pytest.fixture(scope="module")
def deployed():
    _kubectl("apply", "-f", str(HELLO))
    yield
    _kubectl("delete", "-f", str(HELLO), "--ignore-not-found", check=False)


def test_elpioservice_becomes_ready(deployed):
    _wait(
        lambda: _kubectl(
            "get", "elpioservice", NAME, "-n", NS, "-o", "jsonpath={.status.ready}", check=False
        )
        == "true",
        timeout=120,
        what="ElpioService Ready",
    )
    # The operator rendered a KnativeService.
    assert _kubectl("get", "ksvc", NAME, "-n", NS, "-o", "jsonpath={.metadata.name}") == NAME


def test_request_wakes_then_scales_back_to_zero(deployed):
    # Start idle (or let it settle to zero first).
    _wait(lambda: _revision_replicas() == 0, timeout=180, what="initial scale-to-zero")

    # A single in-cluster request must wake the revision (0 -> N).
    url = f"http://{NAME}.{NS}.svc.cluster.local"
    _kubectl(
        "run", "elpio-e2e-curl", "-n", NS, "--rm", "-i", "--restart=Never",
        "--image=curlimages/curl:8.8.0", "--", "-sS", "-m", "30", url,
    )
    assert _wait(lambda: _revision_replicas() >= 1, timeout=60, what="scale up on request")

    # After the idle window it returns to zero.
    assert _wait(lambda: _revision_replicas() == 0, timeout=180, what="scale back to zero")
