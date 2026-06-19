"""CLI tests via Click's CliRunner (offline — dummy token, pure-Python snippets)."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from clickup_cli.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def _envelope(result):
    """Parse the single JSON line emitted by --json."""
    return json.loads(result.output.strip().splitlines()[-1])


def test_exec_happy_path(runner):
    result = runner.invoke(cli, ["exec", "-c", "result = 2 + 3", "--json", "--token", "dummy"])
    assert result.exit_code == 0
    env = _envelope(result)
    assert env == {"schema": 1, "success": True, "result": 5, "stdout": ""}


def test_exec_trailing_expression(runner):
    result = runner.invoke(cli, ["exec", "-c", "1 + 1", "--json", "--token", "dummy"])
    assert result.exit_code == 0
    assert _envelope(result)["result"] == 2


def test_exec_stdout_capture(runner):
    result = runner.invoke(cli, ["exec", "-c", "print('hello')", "--json", "--token", "dummy"])
    assert result.exit_code == 0
    env = _envelope(result)
    assert env["stdout"] == "hello\n"
    assert env["result"] is None


def test_exec_runtime_error(runner):
    result = runner.invoke(
        cli, ["exec", "-c", "raise ValueError('boom')", "--json", "--token", "dummy"]
    )
    assert result.exit_code == 1
    env = _envelope(result)
    assert env["success"] is False
    assert env["error"]["type"] == "ValueError"
    assert env["error"]["category"] == "runtime"


def test_exec_syntax_error(runner):
    result = runner.invoke(cli, ["exec", "-c", "def (", "--json", "--token", "dummy"])
    assert result.exit_code == 1
    assert _envelope(result)["error"]["category"] == "syntax"


def test_exec_missing_token_exits_2(runner, monkeypatch, tmp_path):
    monkeypatch.delenv("CLICKUP_API_TOKEN", raising=False)
    empty_env = tmp_path / "empty.env"
    empty_env.write_text("UNRELATED=1\n")
    result = runner.invoke(
        cli, ["exec", "-c", "1 + 1", "--json", "--env-file", str(empty_env)]
    )
    assert result.exit_code == 2
    env = _envelope(result)
    assert env["success"] is False
    assert env["error"]["category"] == "config"


def test_exec_no_code_exits_2(runner):
    # No -c, no -f, empty stdin -> friendly config error.
    result = runner.invoke(cli, ["exec", "--json", "--token", "dummy"], input="")
    assert result.exit_code == 2
    assert _envelope(result)["error"]["category"] == "config"


def test_exec_from_stdin(runner):
    result = runner.invoke(
        cli, ["exec", "--json", "--token", "dummy"], input="result = 7 * 6\n"
    )
    assert result.exit_code == 0
    assert _envelope(result)["result"] == 42


def test_exec_from_file(runner, tmp_path):
    script = tmp_path / "snippet.py"
    script.write_text("result = sum(range(5))\n")
    result = runner.invoke(
        cli, ["exec", "-f", str(script), "--json", "--token", "dummy"]
    )
    assert result.exit_code == 0
    assert _envelope(result)["result"] == 10


def test_agent_info_mentions_cu_and_result(runner):
    result = runner.invoke(cli, ["agent-info", "--json"])
    assert result.exit_code == 0
    info = json.loads(result.output.strip())
    assert "cu" in info["namespace"]
    assert "result" in info["namespace"]
    assert info["known_ids"]["team"] == "90152385271"
    assert "get_tasks" in info["client_api"]["convenience"]


def test_human_output_renders_result(runner):
    result = runner.invoke(cli, ["exec", "-c", "result = {'ok': 1}", "--token", "dummy"])
    assert result.exit_code == 0
    assert "ok" in result.output
