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
