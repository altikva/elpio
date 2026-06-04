# Changelog

All notable changes to Elpio are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Initial project scaffold (Altikva open-source product, MIT + CC).
- `ElpioService` CRD (`elpio.io/v1alpha1`) with scale-to-zero defaults.
- Kubernetes operator (kopf) reconciling `ElpioService` onto a serving engine.
- Serving-engine strategy: **Knative** (default) and **KEDA**, behind one CRD.
- Portability seams: `StateStore`, `IdentityProvider` interfaces.
- `elpio` CLI: `install`, `deploy`, `services`, `operator`, `version`.
- `ElpioFunction` / `ElpioTask` stub CRDs (Phase 3).
- Unit tests (model + engine rendering) and a kind-based e2e harness stub.

[Unreleased]: https://github.com/altikva/elpio
