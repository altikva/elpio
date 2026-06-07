```
 _____ _       _
| ____| |_ __ (_) ___
|  _| | | '_ \| |/ _ \
| |___| | |_) | | (_) |
|_____|_| .__/|_|\___/
        |_|
```

**Turn any Kubernetes cluster into a private serverless platform.**

---

**Elpio** is an installable, self-hosted **Cloud Run / Cloud Functions / Cloud Tasks** for
your own Kubernetes — scale-to-zero, request-driven autoscaling, simplified cluster + node
autoscaling, and a clean multi-tenant model. GKE-first, **portable by design** (EKS / AKS / k3s).

Elpio is an [Altikva](https://altikva.com) open-source product (MIT for code, CC-BY-4.0 for
docs). The name is a coined mark rooted in Greek *elpis* ("hope") — part of the Altikva family
lineage *ha-tikva* (Hebrew) → *Spero* (Latin) → *Elpio*.

> **Status: alpha (v0.1.0).** All four reconcilers ship: `ElpioService` (Knative/KEDA serving),
> `ElpioFunction` (Tekton + Buildpacks), `ElpioTask` (KEDA + broker), and `ElpioTenant` (namespace,
> RBAC, quotas, network isolation). Alongside them: OIDC auth, an admission webhook, a multi-cluster
> management API, a Helm chart, and CI. CRs emit `status.conditions`, so the sibling agent
> [Spero](https://github.com/altikva/spero) can supervise and heal them. The kind-based e2e harness
> is wired and gated behind `ELPIO_E2E=1`.

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
| `ElpioFunction` | Cloud Functions | Tekton + Buildpacks → `ElpioService` |
| `ElpioTask` | Cloud Tasks | KEDA + broker + dispatcher |

The serving engine is a **strategy** (`ELPIO_ENGINE=knative|keda`) behind one stable CRD —
Knative for the highest Cloud Run parity, KEDA for a lighter footprint.

## Security

A few install-time knobs harden a deployment:

- **Restrict images.** Set `webhook.allowedRegistries` to a comma-separated allowlist (for
  example, `ghcr.io/altikva,registry.mycorp.io`) so the admission webhook only admits images
  from registries you trust. Leaving it empty accepts images from any registry, which is the
  default for the base install.
- **Admission webhook needs cert-manager.** The webhook serves over TLS, so the cluster must
  have cert-manager installed for `webhook.enabled: true` to work.
- **Management API requires OIDC.** The fleet management API fails closed: without
  `ELPIO_OIDC_JWKS_URI` (and the matching issuer and audience) configured, it rejects requests
  rather than running unauthenticated.

## Quickstart

```bash
pip install elpio                  # the elpio CLI

# point kubectl at any cluster (kind, minikube, GKE, EKS, ...) that has a
# serving engine installed — Knative Serving (default) or KEDA.
elpio install                      # applies the CRDs + operator
elpio deploy -f hello.yaml         # the ElpioService shown above
elpio services
```

Working from a clone instead? `task e2e-up` provisions kind + Knative/KEDA, and
`task operator-run` runs the operator locally (`kopf run -m elpio.operator.handlers`).

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
