# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-08
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Render the `elpio` CLI landing screen to docs/img/elpio-cli.svg,
#              a terminal-window screenshot used in the README. Re-run after the
#              banner/commands change. Needs `rich` (not a runtime dep):
#              `pip install rich && python hack/render-cli-svg.py`.

from __future__ import annotations

import os
from importlib.metadata import version

from rich.console import Console
from rich.text import Text

from elpio.banner import render_landing

OUT = os.path.join("assets", "img", "elpio-cli.svg")


def main() -> None:
    ansi = render_landing(version("elpio"), color=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    # Record the ANSI landing screen into a terminal-styled SVG, without
    # echoing it to the real stdout.
    console = Console(record=True, width=84, file=open(os.devnull, "w"))
    console.print(Text.from_ansi(ansi))
    console.save_svg(OUT, title="elpio")
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
