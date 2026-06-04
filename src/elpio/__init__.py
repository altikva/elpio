"""Elpio — turn any Kubernetes cluster into a private serverless platform.

Elpio is the open-source incarnation of A4C (API For Cloud), an Altikva product.
It ships a Kubernetes operator + CRDs (``ElpioService`` / ``ElpioFunction`` /
``ElpioTask``) that reconcile a declarative spec onto a serverless engine
(Knative Serving by default, KEDA as a lighter-weight alternative).

See ``docs/rfc/0001-elpio-private-serverless-platform.md`` for the architecture.
"""

from elpio.version import __version__

__all__ = ["__version__"]
