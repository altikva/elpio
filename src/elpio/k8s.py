# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Thin Kubernetes access layer.

"""Thin Kubernetes access layer.

Generic on purpose: in-cluster config when running as the operator, kubeconfig
otherwise — no cloud-provider assumption (this is the ``ClusterAccess`` seam).
Objects are applied with **server-side apply**, so reconciliation
is idempotent and field-ownership is tracked under the ``elpio`` field manager.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Dict, Optional

from kubernetes import config, dynamic
from kubernetes.client import api_client

logger = logging.getLogger("elpio.k8s")


@functools.lru_cache(maxsize=1)
def client() -> "dynamic.DynamicClient":
    """The default client: in-cluster when running as the operator, else kubeconfig."""
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return dynamic.DynamicClient(api_client.ApiClient())


@functools.lru_cache(maxsize=None)
def client_for(context: Optional[str] = None) -> "dynamic.DynamicClient":
    """A client for a named kubeconfig context.

    ``None`` returns the default client (in-cluster or current context); a
    context name selects that entry from the kubeconfig — this is how the
    management API reaches each cluster in the fleet.
    """
    if context is None:
        return client()
    config.load_kube_config(context=context)
    return dynamic.DynamicClient(api_client.ApiClient())


def connection_kind(record: Optional[Dict[str, Any]]) -> str:
    """How to reach a cluster from its registry record: ``token`` or ``context``."""
    record = record or {}
    if record.get("server") and record.get("token"):
        return "token"
    return "context"


@functools.lru_cache(maxsize=None)
def _client_from_token(
    server: str, token: str, ca_cert: Optional[str] = None, insecure: bool = False
) -> "dynamic.DynamicClient":
    import tempfile

    from kubernetes import client as kclient

    cfg = kclient.Configuration()
    cfg.host = server
    cfg.api_key = {"authorization": token}
    cfg.api_key_prefix = {"authorization": "Bearer"}
    if ca_cert:
        handle = tempfile.NamedTemporaryFile("w", suffix=".crt", delete=False)
        handle.write(ca_cert)
        handle.close()
        cfg.ssl_ca_cert = handle.name
    elif insecure:
        # Explicit opt-in only (local/dev). Never the silent default.
        logger.warning("TLS verification disabled for %s (insecure=true)", server)
        cfg.verify_ssl = False
    else:
        # No CA given: verify against the system trust store.
        cfg.verify_ssl = True
    return dynamic.DynamicClient(api_client.ApiClient(cfg))


def client_for_record(record: Optional[Dict[str, Any]]) -> "dynamic.DynamicClient":
    """Resolve a client from a fleet-registry cluster record.

    A record with ``server`` + ``token`` (and optional ``ca``) connects directly;
    otherwise it falls back to the kubeconfig ``context`` (or the default client).
    Set ``insecure: true`` on the record to skip TLS verification (dev only).
    """
    record = record or {}
    if connection_kind(record) == "token":
        return _client_from_token(
            record["server"], record["token"], record.get("ca"), bool(record.get("insecure"))
        )
    return client_for(record.get("context"))


def get_object(
    api_version: str,
    kind: str,
    name: str,
    namespace: Optional[str] = None,
    dyn: Optional["dynamic.DynamicClient"] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch an object as a dict, or ``None`` if it doesn't exist yet."""
    dyn = dyn or client()
    api = dyn.resources.get(api_version=api_version, kind=kind)
    try:
        return api.get(name=name, namespace=namespace).to_dict()
    except Exception:
        return None


def apply_object(
    obj: Dict[str, Any],
    field_manager: str = "elpio",
    dyn: Optional["dynamic.DynamicClient"] = None,
) -> Any:
    """Server-side apply an arbitrary Kubernetes object (CR or built-in).

    ``dyn`` lets a caller target a specific cluster's client; it defaults to the
    in-cluster/default client.
    """
    dyn = dyn or client()
    api = dyn.resources.get(api_version=obj["apiVersion"], kind=obj["kind"])
    namespace = obj.get("metadata", {}).get("namespace")
    return api.patch(
        body=obj,
        name=obj["metadata"]["name"],
        namespace=namespace,
        content_type="application/apply-patch+yaml",
        field_manager=field_manager,
        force=True,
    )
