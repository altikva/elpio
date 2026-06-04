# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-05
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: Unit tests for the cli.

from click.testing import CliRunner

from elpio.banner import render_banner, render_landing
from elpio.cli import main
from elpio.version import __version__

BANNER_MARK = "_____"  # a slice of the figlet art
ESC = "\033["  # start of an ANSI escape


def test_color_is_opt_in_and_off_by_default():
    plain = render_banner(color=False)
    assert ESC not in plain
    assert BANNER_MARK in plain


def test_colored_banner_emits_ansi_but_keeps_the_art():
    colored = render_banner(color=True)
    assert ESC in colored
    assert "38;5;" in colored  # 256-colour gradient
    assert BANNER_MARK in colored  # art still present under the codes


def test_colored_landing_styles_version_and_sections():
    colored = render_landing("9.9.9", color=True)
    assert ESC in colored
    assert "9.9.9" in colored
    assert "Examples:" in colored


def test_bare_invocation_shows_landing_and_exits_zero():
    res = CliRunner().invoke(main, [])
    assert res.exit_code == 0
    assert BANNER_MARK in res.stderr
    assert "Examples:" in res.stderr
    assert res.stdout == ""  # stdout stays clean


def test_subcommand_routes_banner_to_stderr_keeping_stdout_clean():
    res = CliRunner().invoke(main, ["version"])
    assert res.exit_code == 0
    assert res.stdout.strip() == __version__  # parseable on stdout
    assert BANNER_MARK in res.stderr  # banner header on stderr


def test_version_flag_prints_to_stdout():
    res = CliRunner().invoke(main, ["--version"])
    assert res.exit_code == 0
    assert __version__ in res.stdout
