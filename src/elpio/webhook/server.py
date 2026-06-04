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
empty = allow all). Run with: ``uvicorn elpio.webhook.server:app``.
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


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/mutate")
async def mutate(request: Request) -> Dict[str, Any]:
    body = await request.json()
    return review(body, allowed_registries=_allowed_registries() or None)


# Validation shares the same policy (mutating webhooks may also deny).
app.add_api_route("/validate", mutate, methods=["POST"])
