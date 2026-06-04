# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Idempotently apply the Altikva license header + a Description
#              block (from each module's docstring) to every Python file
#              under src/ and tests/. Preserves an existing file's
#              __creation__ date; stamps new files with today's date.

from __future__ import annotations

import datetime
import pathlib
import re
import textwrap

BANNER = "# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#"
AUTHOR = '# __author__ = "jndjama (Joy Ndjama)"'
LICENCE = '# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"'
PREFIX, CONT = "# Description: ", "#" + " " * 14
TODAY = datetime.date.today().isoformat()


def _header6(creation: str) -> list[str]:
    year = creation[:4]
    return [
        BANNER,
        f"# __creation__ = {creation}",
        AUTHOR,
        f'# __copyright__ = "Copyright {year} ALTIKVA."',
        LICENCE,
        BANNER,
    ]


def _existing_creation(lines: list[str]) -> str | None:
    if len(lines) >= 2 and lines[0] == BANNER and lines[1].startswith("# __creation__"):
        return lines[1].split("=", 1)[1].strip()
    return None


def _module_docstring(body: list[str]) -> str | None:
    """First line of the module docstring, if the body opens with one.

    Skips leading comments/blank lines; only a docstring that is the first real
    statement counts (never a function's docstring).
    """
    for line in body:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r'[rRbBuU]?("""|\'\'\')(.*)', stripped)
        if m:
            text = m.group(2)
            for quote in ('"""', "'''"):  # one-line docstring: drop closing quotes
                text = text.split(quote, 1)[0]
            return text.strip() or None
        return None  # first statement isn't a docstring
    return None


def _existing_description(lines: list[str]) -> str | None:
    """Recover a hand-written Description block from an already-headered file."""
    i = 6
    if i < len(lines) and lines[i] == "":
        i += 1
    if i >= len(lines) or not lines[i].startswith(PREFIX):
        return None
    parts = [lines[i][len(PREFIX):]]
    i += 1
    while i < len(lines) and lines[i].startswith(CONT):
        parts.append(lines[i][len(CONT):])
        i += 1
    return " ".join(p.strip() for p in parts).strip() or None


def _summary(lines: list[str], body: list[str], path: pathlib.Path) -> str:
    # Prefer a real module docstring; otherwise keep any hand-written
    # Description; only then fall back to a name-based guess.
    return (
        _module_docstring(body)
        or _existing_description(lines)
        or _name_fallback(path)
    )


def _name_fallback(path: pathlib.Path) -> str:
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
            lines = p.read_text().split("\n")
            creation = _existing_creation(lines) or TODAY  # never backdate a file
            body = _strip_existing(lines)
            desc = _summary(lines, body, p)
            wrapped = textwrap.wrap(desc, width=63) or [desc]
            block = [PREFIX + wrapped[0]] + [CONT + w for w in wrapped[1:]]
            p.write_text("\n".join(_header6(creation) + block + [""] + body))
            count += 1
    print(f"applied header + description to {count} files")


if __name__ == "__main__":
    main()
