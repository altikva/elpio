# Elpio

> Turn any Kubernetes cluster into a private serverless platform.

**Elpio** is an installable, self-hosted **Cloud Run / Cloud Functions / Cloud Tasks** for
your own Kubernetes — scale-to-zero, request-driven autoscaling, simplified cluster + node
autoscaling, and a clean multi-tenant model. GKE-first, **portable by design** (EKS / AKS / k3s).

Elpio is an [Altikva](https://altikva.com) open-source product (MIT for code, CC-BY-4.0 for
docs). The name is a coined mark rooted in Greek *elpis* ("hope") — part of the Altikva family
lineage *ha-tikva* (Hebrew) → *Spero* (Latin) → *Elpio*.

> **Status: alpha (v0.1.0).** This is an early Phase 0/1 scaffold. The `ElpioService` reconciler
> works against Knative/KEDA; `ElpioFunction` and `ElpioTask` are stubs.

## Why

Elpio does **not** reimplement a serverless runtime. It's the opinionated, enterprise control
plane that assembles proven CNCF primitives — **Knative**, **KEDA**, **Tekton**, **cert-manager**,
**Karpenter** — behind a declarative CRD/operator model. Its value is the enterprise wrapper the
public clouds don't give you: on-prem security integration, hard multi-tenancy, golden-path
config, fleet management, and a one-command installer.

## How it works

You declare an `ElpioService`; the **operator** reconciles it onto a serving engine. No SSH, no
imperative `kubectl apply` scripts — just Kubernetes-native reconciliation.

```yaml
apiVersion: elpio.io/v1alpha1
kind: ElpioService
metadata:
  name: hello
spec:
  image: ghcr.io/knative/helloworld-go:latest
  scaling: { minScale: 0, maxScale: 10, target: 100, metric: concurrency }
```

| CRD | Equivalent | Engine |
|-----|-----------|--------|
| `ElpioService` | Cloud Run | Knative Serving (default) or KEDA |
| `ElpioFunction` | Cloud Functions | Tekton + Buildpacks → `ElpioService` *(Phase 3)* |
| `ElpioTask` | Cloud Tasks | KEDA + broker *(Phase 3)* |

The serving engine is a **strategy** (`ELPIO_ENGINE=knative|keda`) behind one stable CRD —
Knative for the highest Cloud Run parity, KEDA for a lighter footprint.

## Quickstart

```bash
# 1. a cluster (any will do)
kind create cluster --config tests/e2e/kind-config.yaml
# 2. install your engine (Knative Serving) per its docs, then Elpio:
pip install -e .
elpio install                      # applies CRDs + operator
# 3. deploy something that scales to zero
elpio deploy -f examples/hello.yaml
elpio services
```

Run the operator locally instead of in-cluster:

```bash
task operator-run        # kopf run -m elpio.operator.handlers
```

## Development

```bash
task dev      # editable install + dev deps
task unit     # unit tests (no cluster)
task lint     # ruff
task e2e      # end-to-end (needs a kind cluster + Knative/KEDA)
```

## Layout

```
src/elpio/
  models/      ElpioService spec (Pydantic mirror of the CRD)
  engines/     serving-engine strategy: base + knative + keda
  providers/   portability seams: StateStore, IdentityProvider
  operator/    kopf reconciler
  cli.py       the `elpio` command
deploy/        CRDs + operator manifests (+ Helm)
docs/          architecture & guides
```

## License

Code: [MIT](LICENSE). Docs & branding: [CC-BY-4.0](LICENSE-docs).
