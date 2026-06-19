"""Runner unit tests: serialization, trailing-expr capture, error envelopes."""

from __future__ import annotations

from datetime import datetime

import pytest

from clickup_cli.client import ClickUp
from clickup_cli.runner import exit_code_for, run_source, to_jsonable


@pytest.fixture
def cu():
    client = ClickUp("dummy")  # offline — pure-Python snippets make no HTTP calls
    yield client
    client.close()


# -- to_jsonable -----------------------------------------------------------


def test_to_jsonable_primitives_passthrough():
    assert to_jsonable({"n": 1, "f": 1.5, "b": True, "s": "x", "z": None}) == {
        "n": 1,
        "f": 1.5,
        "b": True,
        "s": "x",
        "z": None,
    }


def test_to_jsonable_datetime_isoformat():
    assert to_jsonable(datetime(2026, 6, 19, 12, 0)) == "2026-06-19T12:00:00"


def test_to_jsonable_nested_tuple_and_set():
    out = to_jsonable({"a": (1, 2), "b": {3, 4}})
    assert out["a"] == [1, 2]
    assert sorted(out["b"]) == [3, 4]


def test_to_jsonable_bytes_decoded():
    assert to_jsonable(b"hi") == "hi"


def test_to_jsonable_cycle_guard():
    d: dict = {}
    d["self"] = d
    assert to_jsonable(d) == {"self": "<cycle>"}


def test_to_jsonable_fallback_str():
    class Weird:
        def __str__(self) -> str:
            return "weird!"

    assert to_jsonable(Weird()) == "weird!"


# -- run_source ------------------------------------------------------------


def test_trailing_expr_becomes_result(cu):
    env = run_source("1 + 1", cu)
    assert env["success"] is True
    assert env["result"] == 2
    assert env["schema"] == 1


def test_explicit_result_takes_precedence_over_trailing_expr(cu):
    env = run_source("result = 5\n10", cu)
    assert env["result"] == 5


def test_explicit_result_assignment(cu):
    env = run_source("result = {'ok': True}", cu)
    assert env["result"] == {"ok": True}


def test_stdout_is_captured(cu):
    env = run_source("print('hi')", cu)
    assert env["success"] is True
    assert env["stdout"] == "hi\n"
    assert env["result"] is None


def test_runtime_error_envelope(cu):
    env = run_source("raise ValueError('boom')", cu)
    assert env["success"] is False
    assert env["error"]["category"] == "runtime"
    assert env["error"]["type"] == "ValueError"
    assert "boom" in env["error"]["message"]
    assert exit_code_for(env) == 1


def test_syntax_error_envelope(cu):
    env = run_source("def (", cu)
    assert env["success"] is False
    assert env["error"]["category"] == "syntax"
    assert exit_code_for(env) == 1


def test_traceback_included_when_requested(cu):
    env = run_source("1/0", cu, with_traceback=True)
    assert env["error"]["category"] == "runtime"
    assert "ZeroDivisionError" in env["error"]["traceback"]


def test_namespace_exposes_ids(cu):
    env = run_source("result = TEAM_ID", cu)
    assert env["result"] == "90152385271"
