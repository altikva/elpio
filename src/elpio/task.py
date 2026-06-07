# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Pure render of an ``ElpioTask`` into dispatcher + autoscaler (+
#              schedule).

"""Pure render of an ``ElpioTask`` into dispatcher + autoscaler (+ schedule).

Returns a dispatcher Deployment (pulls from the broker queue and POSTs to the
handler ElpioService), a KEDA ScaledObject that scales the dispatcher off queue
depth, and — when ``schedule`` is set — a CronJob that enqueues a periodic tick.
Spec in → object dicts out, no cluster calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from elpio.models.task import TaskSpec

_MANAGED = {"app.kubernetes.io/managed-by": "elpio"}


def _keda_trigger(spec: TaskSpec) -> Dict[str, Any]:
    """Translate the broker into a KEDA trigger. Queue-depth driven."""
    depth = str(spec.rateLimit or 5)
    if spec.broker.type == "redis":
        return {
            "type": "redis",
            "metadata": {
                "address": spec.broker.address,
                "listName": spec.queue,
                "listLength": depth,
            },
        }
    if spec.broker.type == "rabbitmq":
        return {
            "type": "rabbitmq",
            "metadata": {
                "host": spec.broker.address,
                "queueName": spec.queue,
                "queueLength": depth,
            },
        }
    # default: nats jetstream
    return {
        "type": "nats-jetstream",
        "metadata": {
            "natsServerMonitoringEndpoint": spec.broker.address,
            "stream": spec.queue,
            "consumer": f"{spec.queue}-workers",
            "lagThreshold": depth,
        },
    }


def _dispatcher_env(name: str, namespace: str, spec: TaskSpec) -> List[Dict[str, str]]:
    handler_url = f"http://{spec.handlerService}.{namespace}.svc.cluster.local"
    env = [
        {"name": "ELPIO_BROKER_TYPE", "value": spec.broker.type},
        {"name": "ELPIO_BROKER_ADDRESS", "value": spec.broker.address},
        {"name": "ELPIO_QUEUE", "value": spec.queue},
        {"name": "ELPIO_HANDLER_URL", "value": handler_url},
        {"name": "ELPIO_MAX_ATTEMPTS", "value": str(spec.retry.maxAttempts)},
    ]
    if spec.rateLimit is not None:
        env.append({"name": "ELPIO_RATE_LIMIT", "value": str(spec.rateLimit)})
    env.extend(_broker_auth_env(spec))
    return env


def _broker_auth_env(spec: TaskSpec) -> List[Dict[str, str]]:
    """Map the broker auth/TLS spec to dispatcher env vars.

    Secrets are passed by reference: the ``*_ENV`` vars carry the *name* of the
    env var the dispatcher pod gets from a Secret, never the secret value. The
    operator is responsible for projecting that Secret into the pod (the
    referenced var must exist at runtime); only the var name flows through here.
    """
    auth = spec.broker.auth
    tls = spec.broker.tls
    env: List[Dict[str, str]] = []
    if auth.username:
        env.append({"name": "ELPIO_BROKER_USERNAME", "value": auth.username})
    if auth.usernameEnv:
        env.append({"name": "ELPIO_BROKER_USERNAME_ENV", "value": auth.usernameEnv})
    if auth.passwordEnv:
        env.append({"name": "ELPIO_BROKER_PASSWORD_ENV", "value": auth.passwordEnv})
    if auth.token:
        env.append({"name": "ELPIO_BROKER_TOKEN", "value": auth.token})
    if auth.tokenEnv:
        env.append({"name": "ELPIO_BROKER_TOKEN_ENV", "value": auth.tokenEnv})
    if tls.enabled:
        env.append({"name": "ELPIO_BROKER_TLS", "value": "true"})
        if tls.caCert:
            env.append({"name": "ELPIO_BROKER_TLS_CA", "value": tls.caCert})
        if tls.insecureSkipVerify:
            env.append({"name": "ELPIO_BROKER_TLS_INSECURE", "value": "true"})
    return env


def render_task(
    name: str,
    namespace: str,
    spec: TaskSpec,
    owner: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    labels = {**_MANAGED, "elpio.io/task": name, "app": name}
    env = _dispatcher_env(name, namespace, spec)

    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "namespace": namespace, "labels": labels},
        "spec": {
            "replicas": spec.minReplicas,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "containers": [
                        {"name": "dispatcher", "image": spec.dispatcherImage, "env": env}
                    ]
                },
            },
        },
    }
    scaled_object = {
        "apiVersion": "keda.sh/v1alpha1",
        "kind": "ScaledObject",
        "metadata": {"name": name, "namespace": namespace, "labels": labels},
        "spec": {
            "scaleTargetRef": {"name": name},
            "minReplicaCount": spec.minReplicas,
            "maxReplicaCount": spec.maxReplicas,
            "triggers": [_keda_trigger(spec)],
        },
    }
    objs: List[Dict[str, Any]] = [deployment, scaled_object]

    if spec.schedule:
        objs.append(
            {
                "apiVersion": "batch/v1",
                "kind": "CronJob",
                "metadata": {"name": f"{name}-tick", "namespace": namespace, "labels": labels},
                "spec": {
                    "schedule": spec.schedule,
                    "jobTemplate": {
                        "spec": {
                            "template": {
                                "spec": {
                                    "restartPolicy": "Never",
                                    "containers": [
                                        {
                                            "name": "tick",
                                            "image": spec.dispatcherImage,
                                            "args": ["tick"],
                                            "env": env,
                                        }
                                    ],
                                }
                            }
                        }
                    },
                },
            }
        )

    if owner:
        for o in objs:
            o["metadata"]["ownerReferences"] = [owner]
    return objs
