# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: FastAPI wrapper around the admission policy.

"""FastAPI wrapper around the admission policy.

The MutatingWebhookConfiguration POSTs AdmissionReviews to ``/mutate``; the
allowed-registry list comes from ``ELPIO_ALLOWED_REGISTRIES`` (comma-separated,
empty = allow all). Two opt-in checks are toggled by env vars, both off by
default: ``ELPIO_BAN_LATEST`` (reject mutable ``:latest`` tags) and
``ELPIO_REQUIRE_REQUESTS`` (reject services missing CPU/memory requests). Run
with: ``uvicorn elpio.webhook.server:app``.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import FastAPI, Request

from elpio.webhook.policy import review

app = FastAPI(title="elpio-admission")


def _allowed_registries() -> List[str]:
    raw = os.getenv("ELPIO_ALLOWED_REGISTRIES", "").strip()
    return [r.strip() for r in raw.split(",") if r.strip()]


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/mutate")
async def mutate(request: Request) -> Dict[str, Any]:
    body = await request.json()
    return review(
        body,
        allowed_registries=_allowed_registries() or None,
        ban_latest=_env_flag("ELPIO_BAN_LATEST"),
        require_requests=_env_flag("ELPIO_REQUIRE_REQUESTS"),
    )


# Validation shares the same policy (mutating webhooks may also deny).
app.add_api_route("/validate", mutate, methods=["POST"])
