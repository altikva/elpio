# Changelog

All notable changes to Elpio are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Changed
- Relicensed under the Apache License 2.0 (`Apache-2.0`), replacing MIT for code and
  CC-BY-4.0 for docs. Releases up to and including 0.1.0 stay available under their
  original terms. Added a `NOTICE` file.

### Added
- Contributor License Agreement (`CLA.md`) and a `CONTRIBUTING.md` guide. New
  contributors sign through CLA Assistant on their first pull request.
- Initial project scaffold (Altikva open-source product, MIT + CC).
- `ElpioService` CRD (`elpio.io/v1alpha1`) with scale-to-zero defaults.
- Kubernetes operator (kopf) reconciling `ElpioService` onto a serving engine.
- Serving-engine strategy: **Knative** (default) and **KEDA**, behind one CRD.
- Portability seams: `StateStore`, `IdentityProvider` interfaces.
- `elpio` CLI: `install`, `deploy`, `services`, `operator`, `version`.
- `ElpioFunction` / `ElpioTask` stub CRDs (Phase 3).
- Unit tests (model + engine rendering) and a kind-based e2e harness stub.

[Unreleased]: https://github.com/altikva/elpio
