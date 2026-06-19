"""Click entry point: ``exec``, ``check-auth``, ``agent-info``."""

from __future__ import annotations

import json as json_module
import sys
from pathlib import Path
from typing import Any, Callable

import click
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel

from clickup_cli import __version__
from clickup_cli.agent_info import build_agent_info
from clickup_cli.client import ClickUp
from clickup_cli.config import ConfigError, resolve_token
from clickup_cli.runner import config_error_envelope, exit_code_for, run_source


def common_options(func: Callable) -> Callable:
    """Attach the shared token/output options to a command."""
    func = click.option("--token", default=None, help="ClickUp API token (overrides env).")(func)
    func = click.option(
        "--env-file",
        default=None,
        help="Path to a .env file with CLICKUP_API_TOKEN (file wins over the environment).",
    )(func)
    func = click.option("--json", "json_out", is_flag=True, help="Emit a single compact JSON envelope.")(func)
    func = click.option("--traceback", is_flag=True, help="Include a Python traceback in error envelopes.")(func)
    return func


@click.group()
@click.version_option(__version__, prog_name="clickup-cli")
def cli() -> None:
    """LLM-first exec interface for the ClickUp API v2.

    \b
    Write Python that runs against a pre-authenticated `cu` client:
        clickup-cli exec -c "result = cu.get_teams()" --json

    Run `clickup-cli agent-info` for the full namespace and API reference.
    """


def _emit(envelope: dict[str, Any], *, json_out: bool) -> None:
    """Render an envelope: one compact JSON line, or Rich for humans."""
    if json_out:
        click.echo(json_module.dumps(envelope, separators=(",", ":")))
        return

    out = Console()
    err = Console(stderr=True)
    stdout = envelope.get("stdout", "")
    if stdout:
        out.print(stdout, end="" if stdout.endswith("\n") else "\n")

    if envelope.get("success"):
        result = envelope.get("result")
        if result is not None:
            out.print(JSON(json_module.dumps(result)))
        elif not stdout:
            out.print("[dim](no result)[/dim]")
    else:
        error = envelope.get("error", {})
        err.print(
            Panel(
                f"[bold]{error.get('type', 'Error')}[/bold]: {error.get('message', '')}",
                title=f"[red]{error.get('category', 'error')}[/red]",
                border_style="red",
            )
        )
        if error.get("traceback"):
            err.print(error["traceback"], style="dim")


def _run_with_client(
    src: str,
    *,
    token: str | None,
    env_file: str | None,
    traceback: bool,
) -> dict[str, Any]:
    """Resolve the token, open a client, run ``src``, and return the envelope."""
    try:
        resolved = resolve_token(token, env_file)
    except ConfigError as exc:
        return config_error_envelope(str(exc))

    with ClickUp(resolved) as cu:
        return run_source(src, cu, with_traceback=traceback)


def _read_source(code: str | None, file_: str | None, json_out: bool) -> str:
    """Resolve exec source from -c, -f, or stdin; exit with a friendly error if none."""
    if code is not None:
        return code
    if file_ is not None:
        return Path(file_).read_text()
    if not sys.stdin.isatty():
        piped = sys.stdin.read()
        if piped.strip():
            return piped
    envelope = config_error_envelope(
        "No code provided. Use -c/--code, -f/--file, or pipe code via stdin."
    )
    _emit(envelope, json_out=json_out)
    sys.exit(exit_code_for(envelope))


@cli.command("exec")
@common_options
@click.option("-c", "--code", default=None, help="Inline Python code to execute.")
@click.option(
    "-f",
    "--file",
    "file_",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to a Python file to execute.",
)
def exec_cmd(
    token: str | None,
    env_file: str | None,
    json_out: bool,
    traceback: bool,
    code: str | None,
    file_: str | None,
) -> None:
    """Execute Python against a pre-authenticated `cu` client.

    \b
    Set `result` (or end with a bare expression) for structured output:
        clickup-cli exec -c "result = cu.get_spaces(TEAM_ID)" --json
        clickup-cli exec -f report.py --json
        echo "cu.get_teams()" | clickup-cli exec --json
    """
    src = _read_source(code, file_, json_out)
    envelope = _run_with_client(src, token=token, env_file=env_file, traceback=traceback)
    _emit(envelope, json_out=json_out)
    sys.exit(exit_code_for(envelope))


@cli.command("check-auth")
@common_options
def check_auth(token: str | None, env_file: str | None, json_out: bool, traceback: bool) -> None:
    """Verify the API token by listing authorized workspaces (a safe read probe)."""
    src = "result = {'teams': [t.get('name') for t in cu.get_teams().get('teams', [])]}"
    envelope = _run_with_client(src, token=token, env_file=env_file, traceback=traceback)
    _emit(envelope, json_out=json_out)
    sys.exit(exit_code_for(envelope))


@cli.command("agent-info")
@click.option("--json", "json_out", is_flag=True, help="Emit the reference as compact JSON.")
def agent_info(json_out: bool) -> None:
    """Print the LLM bootstrap reference (namespace, API surface, known IDs)."""
    info = build_agent_info()
    if json_out:
        click.echo(json_module.dumps(info, separators=(",", ":")))
    else:
        Console().print(JSON(json_module.dumps(info)))


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
