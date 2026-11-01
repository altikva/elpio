<!--
-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
__creation__ = 2026-11-01
__author__ = "jndjama (Joy Ndjama)"
__copyright__ = "Copyright 2026 ALTIKVA."
__licence__ = "Apache-2.0 (https://www.apache.org/licenses/LICENSE-2.0)"
-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
Description: How to contribute to Elpio: the CLA, the branch and pull request
             flow, and the checks a change must pass.
-->

# Contributing to Elpio

Thanks for helping. Elpio is released under the [Apache License 2.0](./LICENSE).

## Sign the Contributor License Agreement

Before we can merge your first pull request, you need to sign the
[Elpio Individual Contributor License Agreement](./CLA.md). You keep the
copyright on your work; the agreement gives Altikva and Elpio's users a
license to use it.

When you open your first pull request, the CLA Assistant check
(https://cla-assistant.io) posts a comment with a link. Follow it, sign in
with your GitHub account and accept the agreement. The check then passes. You
sign once; later pull requests are covered. If the check does not update,
click "recheck" in the comment.

If you contribute as part of your job, make sure your employer allows it (see
section 4 of the agreement).

## Make a change

1. Fork the repository and create a topic branch off `main`: `feature/...`,
   `fix/...`, `docs/...` or `chore/...`.
2. Install the development environment: `task dev`.
3. Make your change. Keep engine `render()` functions pure, and when you add a
   field to `ElpioService`, update both `src/elpio/models/service.py` and
   `deploy/crds/elpioservice.yaml`, with a unit test.
4. Run the checks: `task lint` and `task unit`.
5. Open a pull request against `main` and describe what changed and why.

New Python files start with the Altikva header block; `task headers` applies
it.
