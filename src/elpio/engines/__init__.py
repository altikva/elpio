"""Serving engines — the strategy behind ``ElpioService`` (RFC 0001 §4.3).

An engine renders an ``ElpioServiceSpec`` into the concrete Kubernetes objects
that deliver Cloud Run semantics. Knative Serving is the default (closest
parity); KEDA is the lighter-weight alternative. The ``ElpioService`` CRD is the
stable contract regardless of which engine is selected.
"""

from elpio.engines.base import ServingEngine, get_engine

__all__ = ["ServingEngine", "get_engine"]
