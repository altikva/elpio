# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Skip e2e tests unless ELPIO_E2E=1 (they need a live cluster).

import os

import pytest


def pytest_collection_modifyitems(config, items):
    """Skip e2e tests unless ELPIO_E2E=1 (they need a live cluster)."""
    if os.getenv("ELPIO_E2E") == "1":
        return
    skip = pytest.mark.skip(reason="e2e: set ELPIO_E2E=1 and provide a kind cluster")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)
