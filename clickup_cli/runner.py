"""Exec engine: build the namespace, run user code, and return a JSON envelope.

The contract for ``exec``:
  * code runs against a pre-authenticated ``cu`` client;
  * set ``result`` (or end with a bare expression) to return structured data;
  * stdout is captured and returned alongside the result.

Every run returns an *envelope* dict with a stable ``schema`` so callers (humans
and LLMs) can parse outcomes uniformly. Errors are categorized so the CLI can map
them to exit codes.
"""

from __future__ import annotations

import ast
import contextlib
import io
import json as json_module
import os
import traceback as traceback_module
from datetime import date, datetime, timedelta
from pprint import pprint
from typing import Any

from clickup_cli.client import ClickUp, ClickUpError

SCHEMA = 1

# Single source of truth for the RHHOLDING workspace IDs. Used by the exec
# namespace and by `agent-info`.
IDS = {
    "team": "90152385271",
    "space_odoo": "901510167199",
    "space_rhholding": "901510675913",
}
TEAM_ID = IDS["team"]

# Error category -> process exit code.
EXIT_CODES = {"config": 2, "syntax": 1, "runtime": 1}


def to_jsonable(obj: Any, _seen: set[int] | None = None) -> Any:
    """Best-effort conversion of ``obj`` into JSON-serializable primitives.

    Recurses through dict/list/tuple/set with an ``id()`` cycle guard. Dates become
    ISO strings, bytes are decoded, primitives pass through, and anything else falls
    back to ``str()``.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")

    if _seen is None:
        _seen = set()
    obj_id = id(obj)
    if obj_id in _seen:
        return "<cycle>"

    if isinstance(obj, dict):
        _seen.add(obj_id)
        try:
            return {str(k): to_jsonable(v, _seen) for k, v in obj.items()}
        finally:
            _seen.discard(obj_id)

    if isinstance(obj, (list, tuple, set)):
        _seen.add(obj_id)
        try:
            return [to_jsonable(v, _seen) for v in obj]
        finally:
            _seen.discard(obj_id)

    return str(obj)


def _build_namespace(client: ClickUp) -> dict[str, Any]:
    return {
        "cu": client,
        "ClickUpError": ClickUpError,
        "IDS": IDS,
        "TEAM_ID": TEAM_ID,
        "json": json_module,
        "os": os,
        "datetime": datetime,
        "date": date,
        "timedelta": timedelta,
        "pprint": pprint,
        "result": None,
    }


def _assigns_result(module: ast.Module) -> bool:
    """True if the code explicitly assigns to a name ``result`` anywhere."""
    for node in ast.walk(module):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "result":
                return True
    return False


def _capture_trailing_expr(module: ast.Module) -> None:
    """Turn a bare trailing expression into ``result = <expr>`` (Jupyter-cell feel).

    Only applied when the user did not explicitly assign ``result`` themselves.
    """
    if not module.body:
        return
    last = module.body[-1]
    if not isinstance(last, ast.Expr) or _assigns_result(module):
        return
    assign = ast.Assign(
        targets=[ast.Name(id="result", ctx=ast.Store())],
        value=last.value,
    )
    ast.copy_location(assign, last)
    module.body[-1] = assign
    ast.fix_missing_locations(module)


def _error_envelope(
    *,
    error_type: str,
    message: str,
    category: str,
    status: int | None = None,
    with_traceback: bool = False,
    exc: BaseException | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "type": error_type,
        "message": message,
        "status": status,
        "category": category,
    }
    if with_traceback and exc is not None:
        error["traceback"] = "".join(
            traceback_module.format_exception(type(exc), exc, exc.__traceback__)
        )
    return {"schema": SCHEMA, "success": False, "error": error}


def run_source(src: str, client: ClickUp, *, with_traceback: bool = False) -> dict[str, Any]:
    """Compile and run ``src`` against ``client``; return a result/error envelope."""
    try:
        module = ast.parse(src, mode="exec")
    except SyntaxError as exc:
        return _error_envelope(
            error_type="SyntaxError",
            message=_format_syntax_error(exc),
            category="syntax",
            with_traceback=with_traceback,
            exc=exc,
        )

    _capture_trailing_expr(module)

    try:
        code = compile(module, filename="<exec>", mode="exec")
    except SyntaxError as exc:  # pragma: no cover - parse already validates
        return _error_envelope(
            error_type="SyntaxError",
            message=_format_syntax_error(exc),
            category="syntax",
            with_traceback=with_traceback,
            exc=exc,
        )

    namespace = _build_namespace(client)
    stdout_buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_buf):
            exec(code, namespace)
    except ClickUpError as exc:
        return {
            **_error_envelope(
                error_type="ClickUpError",
                message=str(exc),
                category="runtime",
                status=exc.status_code,
                with_traceback=with_traceback,
                exc=exc,
            ),
            "stdout": stdout_buf.getvalue(),
        }
    except Exception as exc:
        return {
            **_error_envelope(
                error_type=type(exc).__name__,
                message=str(exc),
                category="runtime",
                with_traceback=with_traceback,
                exc=exc,
            ),
            "stdout": stdout_buf.getvalue(),
        }

    return {
        "schema": SCHEMA,
        "success": True,
        "result": to_jsonable(namespace.get("result")),
        "stdout": stdout_buf.getvalue(),
    }


def _format_syntax_error(exc: SyntaxError) -> str:
    location = f" (line {exc.lineno})" if exc.lineno else ""
    return f"{exc.msg}{location}"


def config_error_envelope(message: str, *, with_traceback: bool = False) -> dict[str, Any]:
    """Envelope for a configuration failure (e.g. missing token)."""
    return _error_envelope(
        error_type="ConfigError",
        message=message,
        category="config",
        with_traceback=with_traceback,
    )


def exit_code_for(envelope: dict[str, Any]) -> int:
    if envelope.get("success"):
        return 0
    category = envelope.get("error", {}).get("category", "runtime")
    return EXIT_CODES.get(category, 1)
