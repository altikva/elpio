# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: FastAPI application for the management / fleet tier.

"""FastAPI application for the management / fleet tier.

Endpoints author the same ElpioService CRs the CLI does, across registered
clusters. Every mutating call is authenticated (OIDC bearer token) and authorized
through the ``IdentityProvider`` seam. The app never mutates clusters directly —
it writes CRs the in-cluster operators reconcile.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ValidationError

from elpio.api.gateway import CRGateway, FleetRegistry, InMemoryCRGateway, KubeCRGateway
from elpio.models.service import ElpioServiceSpec
from elpio.providers.identity import IdentityProvider, NullIdentityProvider, Principal


class ClusterCreate(BaseModel):
    name: str
    # Reach the cluster either by kubeconfig context, or directly by server+token.
    context: Optional[str] = None
    server: Optional[str] = None
    token: Optional[str] = None
    ca: Optional[str] = None
    insecure: bool = False  # skip TLS verification (dev only)


class ServiceCreate(BaseModel):
    name: str
    namespace: str = "default"
    spec: Dict[str, Any]


def _default_identity() -> IdentityProvider:
    jwks = os.getenv("ELPIO_OIDC_JWKS_URI")
    if jwks:
        from elpio.providers.identity import OIDCIdentityProvider

        return OIDCIdentityProvider(
            jwks_uri=jwks,
            issuer=os.getenv("ELPIO_OIDC_ISSUER"),
            audience=os.getenv("ELPIO_OIDC_AUDIENCE"),
        )
    return NullIdentityProvider()


def create_app(
    *,
    identity: Optional[IdentityProvider] = None,
    registry: Optional[FleetRegistry] = None,
    gateway: Optional[CRGateway] = None,
) -> FastAPI:
    identity = identity or _default_identity()
    registry = registry or FleetRegistry()
    gateway = gateway or (
        InMemoryCRGateway()
        if isinstance(identity, NullIdentityProvider)
        else KubeCRGateway(registry)
    )

    app = FastAPI(title="elpio-management-api")

    def principal(authorization: str = Header(default="")) -> Principal:
        token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
        who = identity.authenticate(token) if token else None
        if who is None:
            raise HTTPException(status_code=401, detail="invalid or missing token")
        return who

    def require(verb: str):
        def _dep(who: Principal = Depends(principal)) -> Principal:
            if not identity.authorize(who, verb, "elpioservices"):
                raise HTTPException(status_code=403, detail="forbidden")
            return who

        return _dep

    @app.get("/healthz")
    def healthz() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/clusters")
    def list_clusters(_: Principal = Depends(require("list"))) -> List[Dict[str, Any]]:
        return registry.list()

    @app.post("/clusters", status_code=201)
    def add_cluster(body: ClusterCreate, _: Principal = Depends(require("create"))) -> Dict[str, Any]:
        return registry.register(body.name, body.model_dump(exclude={"name"}))

    @app.get("/clusters/{cluster}/services")
    def list_services(
        cluster: str,
        namespace: Optional[str] = None,
        _: Principal = Depends(require("list")),
    ) -> List[Dict[str, Any]]:
        if registry.get(cluster) is None:
            raise HTTPException(status_code=404, detail="unknown cluster")
        return gateway.list_services(cluster, namespace)

    @app.post("/clusters/{cluster}/services", status_code=201)
    def create_service(
        cluster: str,
        body: ServiceCreate,
        _: Principal = Depends(require("create")),
    ) -> Dict[str, Any]:
        if registry.get(cluster) is None:
            raise HTTPException(status_code=404, detail="unknown cluster")
        # Validate the spec against the CRD mirror before authoring the CR.
        try:
            validated = ElpioServiceSpec.from_cr(body.spec).model_dump(exclude_none=True)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
        return gateway.apply_service(cluster, body.name, body.namespace, validated)

    return app


# Module-level app for ``uvicorn elpio.api.app:app``.
app = create_app()
