# Changelog

All notable changes to Elpio are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Initial project scaffold (open-sourced from A4C under Altikva, MIT + CC).
- `ElpioService` CRD (`elpio.io/v1alpha1`) with scale-to-zero defaults.
- Kubernetes operator (kopf) reconciling `ElpioService` onto a serving engine.
- Serving-engine strategy: **Knative** (default) and **KEDA**, behind one CRD.
- Portability seams: `StateStore`, `IdentityProvider` interfaces (RFC 0001 §4.4).
- `elpio` CLI: `install`, `deploy`, `services`, `operator`, `version`.
- `ElpioFunction` / `ElpioTask` stub CRDs (Phase 3).
- Unit tests (model + engine rendering) and a kind-based e2e harness stub.
- Architecture RFCs 0001 (platform) and 0002 (A4C → Elpio rename).

[Unreleased]: https://github.com/altikva/elpio
