# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Serving engines — the strategy behind ``ElpioService``.

"""Serving engines — the strategy behind ``ElpioService``.

An engine renders an ``ElpioServiceSpec`` into the concrete Kubernetes objects
that deliver Cloud Run semantics. Knative Serving is the default (closest
parity); KEDA is the lighter-weight alternative. The ``ElpioService`` CRD is the
stable contract regardless of which engine is selected.
"""

from elpio.engines.base import ServingEngine, get_engine

__all__ = ["ServingEngine", "get_engine"]
