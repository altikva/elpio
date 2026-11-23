# Changelog

All notable changes to Elpio are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [0.2.0] - 2026-11-23

First release under the Apache License 2.0.

### Changed
- Relicensed under the Apache License 2.0 (`Apache-2.0`), replacing MIT for code and
  CC-BY-4.0 for docs. Releases up to and including 0.1.0 stay available under their
  original terms. Added a `NOTICE` file.
- `ElpioService` reports Ready from its child's actual readiness, not from the apply.
- Operator code: shared owner-reference and apply loop for the kopf handlers,
  per-object tenant builders, a deterministic CA temp file.

### Added
- Contributor License Agreement (`CLA.md`) and a `CONTRIBUTING.md` guide. New
  contributors sign through CLA Assistant on their first pull request.
- `ElpioService`: custom domains with automatic TLS (Knative engine), traffic
  splitting across revisions, and environment from Secrets, ConfigMaps, `envFrom`
  and External Secrets.
- Operator observability: Prometheus metrics, Kubernetes Events, richer
  `status.conditions`.
- `ElpioTask` dispatcher: broker credentials and TLS.
- Opt-in admission checks: ban `:latest` images, require resource requests.
- `FileStateStore`, so the fleet registry survives restarts.
- Cluster token and CA read from a Secret reference.
- Helm chart: optional in-cluster Spero deploy.
- CLI: `status`, `logs` and `delete` commands.
- Release images on GHCR signed with keyless cosign, with SBOMs attached.
- CI: e2e suite on a kind cluster, one cluster per serving engine.

### Security
- Management API: fails closed without OIDC, redacts cluster credentials, and
  authorizes each endpoint against the resource it touches.
- Identity: JWT audience and issuer enforced, JWKS over HTTPS only.
- Operator RBAC: `bind`/`escalate` scoped to the admin, edit and view ClusterRoles.
- `NatsBroker`: hardened sync-over-async lifecycle.
- Every workflow action pinned to a commit; Dependabot keeps them and the Python
  dependencies up to date.

## [0.1.0] - 2026-06-06

### Added
- Initial project scaffold (Altikva open-source product, MIT + CC).
- `ElpioService` CRD (`elpio.io/v1alpha1`) with scale-to-zero defaults.
- Kubernetes operator (kopf) reconciling `ElpioService` onto a serving engine.
- Serving-engine strategy: **Knative** (default) and **KEDA**, behind one CRD.
- Portability seams: `StateStore`, `IdentityProvider` interfaces.
- `elpio` CLI: `install`, `deploy`, `services`, `operator`, `version`.
- `ElpioFunction` / `ElpioTask` stub CRDs (Phase 3).
- Unit tests (model + engine rendering) and a kind-based e2e harness stub.

[Unreleased]: https://github.com/altikva/elpio/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/altikva/elpio/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/altikva/elpio/releases/tag/v0.1.0
