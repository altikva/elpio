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
from typing import Any, Dict

from kubernetes import config, dynamic
from kubernetes.client import api_client


@functools.lru_cache(maxsize=1)
def client() -> "dynamic.DynamicClient":
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return dynamic.DynamicClient(api_client.ApiClient())


def apply_object(obj: Dict[str, Any], field_manager: str = "elpio") -> Any:
    """Server-side apply an arbitrary Kubernetes object (CR or built-in)."""
    api = client().resources.get(
        api_version=obj["apiVersion"], kind=obj["kind"]
    )
    namespace = obj.get("metadata", {}).get("namespace")
    return api.patch(
        body=obj,
        name=obj["metadata"]["name"],
        namespace=namespace,
        content_type="application/apply-patch+yaml",
        field_manager=field_manager,
        force=True,
    )
