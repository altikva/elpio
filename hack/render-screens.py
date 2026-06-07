# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-08
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Render the README's terminal screenshots (CLI usage session +
#              operator reconcile log) to assets/img/*.svg. The transcripts below
#              are real output captured from a live minikube run (operator on the
#              knative engine), kept here so the images regenerate without a
#              cluster. Needs `rich` (not a runtime dep):
#              `pip install rich && python hack/render-screens.py`.

from __future__ import annotations

import os

from rich.console import Console
from rich.text import Text

OUT_DIR = os.path.join("assets", "img")

# Real `elpio services` / `elpio status` stdout (the banner goes to stderr, so
# stdout is clean by design).
_SERVICES = [
    "NAMESPACE   NAME         READY   ENGINE    URL                                           AGE",
    "default     hello        true    knative   http://hello.default.svc.cluster.local        55s",
    "default     hello-keda   true    knative   http://hello-keda.default.svc.cluster.local   54s",
]
_STATUS = [
    "NAME    READY   ENGINE    URL",
    "hello   true    knative   http://hello.default.svc.cluster.local",
]

# Real kopf reconcile log lines (elpio-operator, knative engine).
_OPERATOR = [
    ("22:52:35", "default/hello", "reconciled Service/hello via knative engine"),
    ("22:52:35", "default/hello", "Handler 'reconcile' succeeded."),
    ("22:52:35", "default/hello", "Creation is processed: 1 succeeded; 0 failed."),
    ("22:52:35", "default/hello-keda", "reconciled Service/hello-keda via knative engine"),
    ("22:52:35", "default/hello-keda", "Handler 'reconcile' succeeded."),
    ("22:52:35", "default/hello-keda", "Creation is processed: 1 succeeded; 0 failed."),
]


def _prompt(cmd: str) -> Text:
    line = Text()
    line.append("$ ", style="bold green")
    line.append("elpio ", style="bold")
    line.append(cmd, style="bold white")
    return line


def _table(rows: list[str]) -> Text:
    out = Text()
    out.append(rows[0] + "\n", style="bold cyan")  # header
    for r in rows[1:]:
        out.append(r + "\n")
    return out


def render_usage() -> Text:
    body = Text()
    body.append_text(_prompt("services"))
    body.append("\n")
    body.append_text(_table(_SERVICES))
    body.append("\n")
    body.append_text(_prompt("status hello"))
    body.append("\n")
    body.append_text(_table(_STATUS))
    return body


def render_operator() -> Text:
    body = Text()
    for ts, obj, msg in _OPERATOR:
        body.append(ts + " ", style="dim")
        body.append("INFO  ", style="green")
        body.append(f"[{obj}] ", style="cyan")
        body.append(msg + "\n")
    return body


def _save(body: Text, name: str, title: str, width: int) -> None:
    console = Console(record=True, width=width, file=open(os.devnull, "w"))
    console.print(body)
    path = os.path.join(OUT_DIR, name)
    console.save_svg(path, title=title)
    print(f"wrote {path} ({os.path.getsize(path)} bytes)")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    _save(render_usage(), "elpio-usage.svg", "elpio", width=96)
    _save(render_operator(), "elpio-operator.svg", "elpio-operator", width=78)


if __name__ == "__main__":
    main()
