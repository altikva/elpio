# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Skip e2e tests unless ELPIO_E2E=1 (they need a live cluster).

import os

import pytest


# Marked suites that need external infrastructure: (marker, env gate, reason).
_GATES = [
    ("e2e", "ELPIO_E2E", "e2e: set ELPIO_E2E=1 and provide a kind cluster"),
    ("integration", "ELPIO_INTEGRATION", "integration: set ELPIO_INTEGRATION=1 and provide brokers"),
]


def pytest_collection_modifyitems(config, items):
    """Skip infra-dependent suites unless their env gate is set to 1."""
    for keyword, env, reason in _GATES:
        if os.getenv(env) == "1":
            continue
        skip = pytest.mark.skip(reason=reason)
        for item in items:
            if keyword in item.keywords:
                item.add_marker(skip)
