# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-06
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: e2e for the KEDA-engine request-driven scale-to-zero path: a
#              request through the keda-http-add-on interceptor wakes a
#              0-replica ElpioService, which then settles back to zero.
"""End-to-end request-driven scale-to-zero on the KEDA engine.

Skipped unless ``ELPIO_E2E=1``. Prerequisites in the cluster:
  * KEDA + the keda-http-add-on (``task keda-http-install``),
  * the Elpio operator running with ``ELPIO_ENGINE=keda``.

The flow this asserts:

    deploy examples/hello-keda.yaml
        -> the operator renders an HTTPScaledObject (+ Deployment, Service)
        -> idle: the Deployment sits at 0 replicas
        -> a request through the add-on interceptor wakes it: 0 -> N
        -> after the scaledown window, it settles back to 0.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest

# KEDA-engine path: the wake request must traverse the keda-http-add-on
# interceptor. Skip unless the operator under test is running the keda engine.
_ENGINE = os.getenv("ELPIO_ENGINE", "knative").lower()
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(_ENGINE != "keda", reason=f"keda-engine e2e (ELPIO_ENGINE={_ENGINE})"),
]

NS = "default"
NAME = "hello-keda"
HOST = f"{NAME}.{NS}"  # matches the HTTPScaledObject host the engine renders
INTERCEPTOR = "keda-add-ons-http-interceptor-proxy.keda:8080"
MANIFEST = Path(__file__).resolve().parents[2] / "examples" / "hello-keda.yaml"


def _kubectl(*args: str, check: bool = True) -> str:
    return subprocess.run(
        ["kubectl", *args], check=check, capture_output=True, text=True
    ).stdout.strip()


def _wait(predicate, *, timeout: float, interval: float = 5.0, what: str = "condition"):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"timed out after {timeout}s waiting for {what} (last={last!r})")


def _replicas() -> int:
    out = _kubectl(
        "get", "deploy", NAME, "-n", NS, "-o", "jsonpath={.status.replicas}", check=False
    )
    return int(out) if out.strip() else 0


def _curl_through_interceptor() -> None:
    # An in-cluster request to the add-on interceptor with the app's Host header
    # is what wakes a scaled-to-zero HTTPScaledObject target.
    _kubectl(
        "run", "elpio-keda-curl", "-n", NS, "--rm", "-i", "--restart=Never",
        "--image=curlimages/curl:8.8.0", "--",
        "-sS", "-m", "60", "-H", f"Host: {HOST}", f"http://{INTERCEPTOR}/",
    )


@pytest.fixture(scope="module")
def deployed():
    _kubectl("apply", "-f", str(MANIFEST))
    _wait(
        lambda: _kubectl(
            "get", "httpscaledobject", NAME, "-n", NS, "-o", "jsonpath={.metadata.name}", check=False
        )
        == NAME,
        timeout=60,
        what="HTTPScaledObject created",
    )
    yield
    _kubectl("delete", "-f", str(MANIFEST), "--ignore-not-found", check=False)


def test_request_wakes_then_scales_back_to_zero(deployed):
    # Idle: the add-on holds the target at zero.
    _wait(lambda: _replicas() == 0, timeout=180, what="initial scale-to-zero")

    # A request through the interceptor must wake it.
    _curl_through_interceptor()
    assert _wait(lambda: _replicas() >= 1, timeout=90, what="scale up on request")

    # After the scaledown window it returns to zero.
    assert _wait(lambda: _replicas() == 0, timeout=420, what="scale back to zero")
