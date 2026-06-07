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
    assert "╭─" in colored and "Examples" in colored


def test_panels_are_aligned_in_both_modes():
    import re as _re

    strip = lambda s: _re.sub(r"\033\[[0-9;]*m", "", s)  # noqa: E731
    for colored in (False, True):
        landing = render_landing("0.1.0", color=colored)
        box_rows = [r for r in landing.split("\n") if r and strip(r)[0] in "╭│╰"]
        widths = {len(strip(r)) for r in box_rows}
        # every border/body row of a panel shares one width per panel; with two
        # panels we expect at most two distinct widths, and they must be uniform.
        assert len(widths) <= 2, f"misaligned panel rows: {widths}"


def test_bare_invocation_shows_landing_and_exits_zero():
    res = CliRunner().invoke(main, [])
    assert res.exit_code == 0
    assert BANNER_MARK in res.stderr
    assert "Commands" in res.stderr and "Examples" in res.stderr
    assert "╭─" in res.stderr and "╰" in res.stderr  # boxed panels
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


def test_install_applies_namespace_rbac_before_the_operator(monkeypatch):
    import os

    calls = []

    def fake_run(argv, check=False, **kw):
        calls.append(list(argv))

        class _Done:
            returncode = 0

        return _Done()

    monkeypatch.setattr("elpio.cli.subprocess.run", fake_run)
    res = CliRunner().invoke(main, ["install"])
    assert res.exit_code == 0

    targets = [os.path.basename(a[a.index("-f") + 1].rstrip("/")) for a in calls if "-f" in a]
    # CRDs, then the namespace+RBAC, then the operator Deployment dir.
    assert targets == ["crds", "rbac.yaml", "operator"]


def _record_kubectl(monkeypatch):
    """Monkeypatch ``subprocess.run`` to a recorder; return the call list."""
    calls = []

    def fake_run(argv, check=False, **kw):
        calls.append(list(argv))

        class _Done:
            returncode = 0

        return _Done()

    monkeypatch.setattr("elpio.cli.subprocess.run", fake_run)
    return calls


def test_status_gets_the_service_with_readiness_columns(monkeypatch):
    calls = _record_kubectl(monkeypatch)
    res = CliRunner().invoke(main, ["status", "hello", "-n", "demo"])
    assert res.exit_code == 0

    argv = calls[0]
    assert argv[:5] == ["kubectl", "get", "elpioservice.elpio.io", "hello", "-n"]
    assert "demo" in argv
    out_flag = argv[argv.index("-o") + 1]
    for col in (".status.ready", ".status.engine", ".status.url"):
        assert col in out_flag
    assert BANNER_MARK in res.stderr  # banner still on stderr
    assert res.stdout == ""  # stdout stays clean (kubectl owns it)


def test_status_defaults_namespace_to_default(monkeypatch):
    calls = _record_kubectl(monkeypatch)
    res = CliRunner().invoke(main, ["status", "hello"])
    assert res.exit_code == 0
    argv = calls[0]
    assert argv[argv.index("-n") + 1] == "default"


def test_logs_selects_pods_by_service_label(monkeypatch):
    calls = _record_kubectl(monkeypatch)
    res = CliRunner().invoke(main, ["logs", "hello", "-n", "demo"])
    assert res.exit_code == 0
    argv = calls[0]
    assert argv[:2] == ["kubectl", "logs"]
    assert "-l" in argv and argv[argv.index("-l") + 1] == "elpio.io/service=hello"
    assert "--all-containers" in argv
    assert argv[argv.index("-n") + 1] == "demo"
    assert "--follow" not in argv  # not following by default


def test_logs_follow_flag_adds_follow(monkeypatch):
    calls = _record_kubectl(monkeypatch)
    res = CliRunner().invoke(main, ["logs", "hello", "-f"])
    assert res.exit_code == 0
    assert "--follow" in calls[0]


def test_delete_by_name_targets_the_named_service(monkeypatch):
    calls = _record_kubectl(monkeypatch)
    res = CliRunner().invoke(main, ["delete", "hello", "-n", "demo"])
    assert res.exit_code == 0
    argv = calls[0]
    assert argv[:4] == ["kubectl", "delete", "elpioservice.elpio.io", "hello"]
    assert argv[argv.index("-n") + 1] == "demo"


def test_delete_by_file_uses_kubectl_delete_f(monkeypatch, tmp_path):
    manifest = tmp_path / "svc.yaml"
    manifest.write_text("kind: ElpioService\n")
    calls = _record_kubectl(monkeypatch)
    res = CliRunner().invoke(main, ["delete", "-f", str(manifest)])
    assert res.exit_code == 0
    assert calls[0] == ["kubectl", "delete", "-f", str(manifest)]


def test_delete_without_name_or_file_errors(monkeypatch):
    _record_kubectl(monkeypatch)
    res = CliRunner().invoke(main, ["delete"])
    assert res.exit_code != 0


def test_delete_with_both_name_and_file_errors(monkeypatch, tmp_path):
    manifest = tmp_path / "svc.yaml"
    manifest.write_text("kind: ElpioService\n")
    _record_kubectl(monkeypatch)
    res = CliRunner().invoke(main, ["delete", "hello", "-f", str(manifest)])
    assert res.exit_code != 0
