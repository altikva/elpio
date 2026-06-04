# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-05
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: ASCII banner and landing screen for the ``elpio`` CLI.

"""ASCII banner and landing screen for the ``elpio`` CLI.

The banner is a static pyfiglet "Standard" rendering of "Elpio", hardcoded so the
CLI needs no runtime figlet dependency. It is sent to stderr so stdout stays
clean for piping (``elpio version``, list output, etc.).
"""

from __future__ import annotations

import re

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

_BANNER = (
    " _____ _       _       \n"
    "| ____| |_ __ (_) ___  \n"
    "|  _| | | '_ \\| |/ _ \\ \n"
    "| |___| | |_) | | (_) |\n"
    "|_____|_| .__/|_|\\___/ \n"
    "        |_|            "
)

_TAGLINE = "turn any Kubernetes cluster into a private serverless platform"

# Mid-luminance teal/cyan 256-colours: bright enough on a dark background, dark
# enough on a light one. A per-line gradient down the figlet art.
_RESET = "\033[0m"
_GRADIENT = [39, 38, 44, 43, 37, 36]


def _fg(text: str, code: int, *, bold: bool = False) -> str:
    weight = "1;" if bold else ""
    return f"\033[{weight}38;5;{code}m{text}{_RESET}"


def _bold(text: str) -> str:
    return f"\033[1m{text}{_RESET}"


def _dim(text: str) -> str:
    return f"\033[2m{text}{_RESET}"


_ACCENT = 44  # teal, for panel borders/titles and command names

_COMMANDS = [
    ("install", "Apply the CRDs + operator to the current kube-context"),
    ("deploy", "Create or update an ElpioService from a YAML file"),
    ("services", "List ElpioServices"),
    ("operator", "Run the Elpio operator (kopf) in the foreground"),
    ("version", "Print the Elpio version"),
]

_EXAMPLES = [
    ("elpio install", "apply the CRDs + operator to the cluster"),
    ("elpio deploy -f examples/hello.yaml", "create an ElpioService"),
    ("elpio services -A", "list ElpioServices in all namespaces"),
    ("elpio operator", "run the reconciler in the foreground"),
]


def _visible_len(text: str) -> int:
    return len(_ANSI_RE.sub("", text))


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _visible_len(text))


def _two_col(pairs: list[tuple[str, str]], color: bool) -> list[str]:
    left_w = max(len(left) for left, _ in pairs)
    rows = []
    for left, right in pairs:
        left_cell = _fg(left.ljust(left_w), _ACCENT, bold=True) if color else left.ljust(left_w)
        rows.append(f"{left_cell}  {right}")
    return rows


def _panel(title: str, rows: list[str], color: bool) -> str:
    """A rounded box (Spero-style) around ``rows``, fit to content."""
    content_w = max([_visible_len(r) for r in rows] + [len(title) + 1])
    total = content_w + 4  # │ + space + content + space + │
    fill = total - (len(title) + 4) - 1  # after "╭─ {title} ", before "╮"

    if color:
        top = (
            _fg("╭─ ", _ACCENT)
            + _fg(title, _ACCENT, bold=True)
            + _fg(" " + "─" * fill + "╮", _ACCENT)
        )
        bottom = _fg("╰" + "─" * (total - 2) + "╯", _ACCENT)
        bar = _fg("│", _ACCENT)
        body = [f"{bar} {_pad(r, content_w)} {bar}" for r in rows]
    else:
        top = f"╭─ {title} " + "─" * fill + "╮"
        bottom = "╰" + "─" * (total - 2) + "╯"
        body = [f"│ {_pad(r, content_w)} │" for r in rows]

    return "\n".join([top, *body, bottom])


def render_banner(color: bool = False) -> str:
    """The figlet header, shown before every command's output.

    ``color`` adds the teal gradient (callers pass it only for a real terminal).
    """
    if not color:
        return _BANNER
    return "\n".join(
        _fg(line, _GRADIENT[i % len(_GRADIENT)], bold=True)
        for i, line in enumerate(_BANNER.split("\n"))
    )


def render_landing(version: str, color: bool = False) -> str:
    """The full landing screen shown on a bare ``elpio`` invocation."""
    if color:
        version_line = f"{_fg('v' + version, _ACCENT, bold=True)}  ---  {_dim(_TAGLINE)}"
    else:
        version_line = f"v{version}  ---  {_TAGLINE}"

    return "\n".join(
        [
            render_banner(color=color),
            "",
            version_line,
            "",
            _panel("Commands", _two_col(_COMMANDS, color), color),
            "",
            _panel("Examples", _two_col(_EXAMPLES, color), color),
        ]
    )
