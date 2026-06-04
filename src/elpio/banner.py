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

_COMMANDS = [
    ("install", "Apply the CRDs + operator to the current kube-context"),
    ("deploy", "Create or update an ElpioService from a YAML file"),
    ("services", "List ElpioServices"),
    ("operator", "Run the Elpio operator (kopf) in the foreground"),
    ("version", "Print the Elpio version"),
]

_EXAMPLES = [
    "elpio install",
    "elpio deploy -f examples/hello.yaml",
    "elpio services -A",
]


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
    width = max(len(name) for name, _ in _COMMANDS)

    if color:
        version_line = f"{_fg('v' + version, 44, bold=True)}  ---  {_dim(_TAGLINE)}"
        cmd_lines = [f"  {_fg(name.ljust(width), 37, bold=True)}  {desc}" for name, desc in _COMMANDS]
        headers = (_bold("Commands:"), _bold("Examples:"))
    else:
        version_line = f"v{version}  ---  {_TAGLINE}"
        cmd_lines = [f"  {name.ljust(width)}  {desc}" for name, desc in _COMMANDS]
        headers = ("Commands:", "Examples:")

    lines = [render_banner(color=color), "", version_line, "", headers[0]]
    lines += cmd_lines
    lines += ["", headers[1]]
    lines += [f"  {ex}" for ex in _EXAMPLES]
    return "\n".join(lines)
