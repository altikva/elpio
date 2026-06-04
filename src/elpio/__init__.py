# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Elpio — turn any Kubernetes cluster into a private serverless
#              platform.

"""Elpio — turn any Kubernetes cluster into a private serverless platform.

Elpio ships a Kubernetes operator + CRDs (``ElpioService`` / ``ElpioFunction`` /
``ElpioTask``) that reconcile a declarative spec onto a serverless engine
(Knative Serving by default, KEDA as a lighter-weight alternative).
"""

from elpio.version import __version__

__all__ = ["__version__"]
