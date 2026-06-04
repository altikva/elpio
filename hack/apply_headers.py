# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Idempotently apply the Altikva license header + a Description
#              block (derived from each module's docstring) to every Python
#              file under src/ and tests/. Run via `task headers`.

from __future__ import annotations

import pathlib
import re
import textwrap

BANNER = "# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#"
HEADER6 = [
    BANNER,
    "# __creation__ = 2026-06-04",
    '# __author__ = "jndjama (Joy Ndjama)"',
    '# __copyright__ = "Copyright 2026 ALTIKVA."',
    '# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"',
    BANNER,
]
PREFIX, CONT = "# Description: ", "#" + " " * 14


def _summary(body_text: str, path: pathlib.Path) -> str:
    m = re.search(r'"""(.*?)(?:\n|""")', body_text, re.S)
    if m and m.group(1).strip():
        return m.group(1).strip().splitlines()[0].strip()
    stem = path.stem
    if stem.startswith("test_"):
        return f"Unit tests for the {stem[5:].replace('_', ' ')}."
    if stem == "conftest":
        return "Pytest fixtures and shared test configuration."
    if stem == "__init__":
        return f"{path.parent.name} package."
    return f"{stem} module."


def _strip_existing(lines: list[str]) -> list[str]:
    if len(lines) >= 6 and lines[0] == BANNER and lines[5] == BANNER:
        i = 6
        if i < len(lines) and lines[i] == "" and i + 1 < len(lines) and lines[i + 1].startswith(PREFIX):
            i += 1
        if i < len(lines) and lines[i].startswith(PREFIX):
            i += 1
            while i < len(lines) and lines[i].startswith(CONT):
                i += 1
        while i < len(lines) and lines[i] == "":
            i += 1
        return lines[i:]
    return lines


def main() -> None:
    count = 0
    for root in (pathlib.Path("src"), pathlib.Path("tests")):
        for p in sorted(root.rglob("*.py")):
            body = _strip_existing(p.read_text().split("\n"))
            desc = _summary("\n".join(body), p)
            wrapped = textwrap.wrap(desc, width=63) or [desc]
            block = [PREFIX + wrapped[0]] + [CONT + w for w in wrapped[1:]]
            p.write_text("\n".join(HEADER6 + block + [""] + body))
            count += 1
    print(f"applied header + description to {count} files")


if __name__ == "__main__":
    main()
