# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# __creation__ = 2026-06-04
# __author__ = "jndjama (Joy Ndjama)"
# __copyright__ = "Copyright 2026 ALTIKVA."
# __licence__ = "MIT & CC BY-NC-SA (http://www.altikva.com/licenses/LICENSE-1.0)"
# -#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#-#
# Description: ``elpio`` CLI.

"""``elpio`` CLI.

A thin, kubeconfig-driven client: it authors CRs and shells out to ``kubectl``
for cluster operations (the same model every k8s CLI uses). It never SSHes into
an admin VM — all mutation happens in-cluster via the operator.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click

from elpio.banner import render_banner, render_landing
from elpio.version import __version__


def _repo_deploy_dir() -> Path:
    """Locate the bundled ``deploy/`` dir when running from a source checkout."""
    return Path(__file__).resolve().parents[2] / "deploy"


def _kubectl(*args: str) -> None:
    try:
        subprocess.run(["kubectl", *args], check=True)
    except FileNotFoundError:
        click.echo("error: kubectl not found in PATH", err=True)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)


def _use_color() -> bool:
    """Colour only for a real terminal, and honour the NO_COLOR convention."""
    return sys.stderr.isatty() and not os.environ.get("NO_COLOR")


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="elpio")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Elpio: turn any Kubernetes cluster into a private serverless platform."""
    # Banner goes to stderr so stdout stays clean for piping. A bare invocation
    # shows the full landing screen and exits 0 (never "Missing command").
    color = _use_color()
    if ctx.invoked_subcommand is None:
        click.echo(render_landing(__version__, color=color), err=True)
        ctx.exit(0)
    click.echo(render_banner(color=color), err=True)


@main.command()
def version() -> None:
    """Print the Elpio version."""
    click.echo(__version__)


@main.command()
@click.option(
    "--manifests",
    type=click.Path(exists=True, file_okay=False),
    default=None,
    help="Path to the deploy/ dir (defaults to the source checkout).",
)
def install(manifests: str | None) -> None:
    """Install Elpio CRDs + operator into the current kube-context."""
    deploy = Path(manifests) if manifests else _repo_deploy_dir()
    _kubectl("apply", "-f", str(deploy / "crds"))
    # The operator Deployment is namespaced in elpio-system, which rbac.yaml
    # creates. `kubectl apply -f <dir>` orders files alphabetically, so the
    # Deployment would otherwise race ahead of its namespace. Apply the namespace
    # + RBAC first, then the rest of the operator manifests.
    _kubectl("apply", "-f", str(deploy / "operator" / "rbac.yaml"))
    _kubectl("apply", "-f", str(deploy / "operator"))
    click.echo("elpio: CRDs + operator applied")


@main.command()
@click.option(
    "-f",
    "--file",
    "file",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="ElpioService (or other Elpio CR) YAML to apply.",
)
def deploy(file: str) -> None:
    """Create/update an ElpioService from a YAML file."""
    _kubectl("apply", "-f", file)


@main.command()
@click.option("-n", "--namespace", default=None, help="Limit to one namespace.")
def services(namespace: str | None) -> None:
    """List ElpioServices."""
    args = ["get", "elpioservices.elpio.io"]
    args += ["-n", namespace] if namespace else ["-A"]
    _kubectl(*args)


@main.command()
@click.argument("name")
@click.option("-n", "--namespace", default="default", help="Service namespace.")
def status(name: str, namespace: str) -> None:
    """Show an ElpioService's readiness (ready/engine/url)."""
    _kubectl(
        "get",
        "elpioservice.elpio.io",
        name,
        "-n",
        namespace,
        "-o",
        "custom-columns="
        "NAME:.metadata.name,"
        "READY:.status.ready,"
        "ENGINE:.status.engine,"
        "URL:.status.url",
    )


@main.command()
@click.argument("name")
@click.option("-n", "--namespace", default="default", help="Service namespace.")
@click.option("-f", "--follow", is_flag=True, help="Stream new logs (tail -f).")
def logs(name: str, namespace: str, follow: bool) -> None:
    """Tail logs for an ElpioService's pods."""
    args = [
        "logs",
        "-l",
        f"elpio.io/service={name}",
        "-n",
        namespace,
        "--all-containers",
    ]
    if follow:
        args.append("--follow")
    _kubectl(*args)


@main.command()
@click.argument("name", required=False)
@click.option("-n", "--namespace", default="default", help="Service namespace.")
@click.option(
    "-f",
    "--file",
    "file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Delete the ElpioService(s) defined in this YAML file.",
)
def delete(name: str | None, namespace: str, file: str | None) -> None:
    """Delete an ElpioService by name or from a YAML file."""
    if file and name:
        raise click.UsageError("pass either NAME or -f/--file, not both")
    if file:
        _kubectl("delete", "-f", file)
        return
    if not name:
        raise click.UsageError("give a service NAME or -f/--file")
    _kubectl("delete", "elpioservice.elpio.io", name, "-n", namespace)


@main.command(
    context_settings={"ignore_unknown_options": True},
    short_help="Run the Elpio operator (kopf) in the foreground.",
)
@click.argument("kopf_args", nargs=-1, type=click.UNPROCESSED)
def operator(kopf_args: tuple[str, ...]) -> None:
    """Run the operator. Extra args are passed through to ``kopf run``."""
    os.execvp("kopf", ["kopf", "run", "-m", "elpio.operator.handlers", *kopf_args])


if __name__ == "__main__":
    main()
