"""Bootstrap reference for LLM agents — built from the single-source-of-truth IDS."""

from __future__ import annotations

from typing import Any

from clickup_cli import __version__
from clickup_cli.runner import IDS


def build_agent_info() -> dict[str, Any]:
    """Return the structured agent-info reference."""
    return {
        "tool": "clickup-cli",
        "version": __version__,
        "architecture": "exec-only (LLM-first)",
        "description": "Self-contained exec CLI for the ClickUp API v2.",
        "primary_command": {
            "name": "exec",
            "usage": [
                'clickup-cli exec -c "result = cu.get_teams()" --json',
                "clickup-cli exec -c \"result = [s['name'] for s in cu.get_spaces(TEAM_ID)['spaces']]\" --json",
                "clickup-cli exec -f script.py --json",
                'echo "cu.get_task(\'abc123\')" | clickup-cli exec --json',
            ],
            "contract": (
                "Set the `result` variable for structured output, OR end your code with a "
                "bare expression (its value becomes `result`, Jupyter-style). stdout is "
                "captured and returned in the envelope's `stdout` field."
            ),
        },
        "namespace": {
            "cu": "Pre-authenticated ClickUp client — use this for ALL API calls.",
            "ClickUpError": "Exception type raised on API errors (has .status_code, .response_json).",
            "IDS": "Dict of known RHHOLDING IDs (see known_ids below).",
            "TEAM_ID": "Shortcut for IDS['team'] (the RHHOLDING workspace).",
            "json": "json module.",
            "os": "os module.",
            "datetime": "datetime class.",
            "date": "date class.",
            "timedelta": "timedelta class.",
            "pprint": "Pretty printer.",
            "result": "Set this for structured JSON output (defaults to None).",
        },
        "client_api": {
            "generic": {
                "request": "cu.request(method, path, *, params=None, json=None) -> parsed JSON",
                "get": "cu.get(path, **params)",
                "post": "cu.post(path, json=None, **params)",
                "put": "cu.put(path, json=None, **params)",
                "delete": "cu.delete(path, **params)",
                "note": "All paths are relative to https://api.clickup.com/api/v2 — e.g. cu.get('/team').",
            },
            "convenience": {
                "get_teams": "cu.get_teams() -> {'teams': [...]}",
                "get_spaces": "cu.get_spaces(team_id, *, archived=False) -> {'spaces': [...]}",
                "get_space": "cu.get_space(space_id) -> {...}",
                "get_folders": "cu.get_folders(space_id, *, archived=False) -> {'folders': [...]}",
                "get_lists": "cu.get_lists(folder_id, *, archived=False) -> {'lists': [...]}",
                "get_folderless_lists": "cu.get_folderless_lists(space_id, *, archived=False) -> {'lists': [...]}",
                "get_tasks": "cu.get_tasks(list_id, **filters) -> {'tasks': [...], 'last_page': bool}",
                "iter_tasks": "cu.iter_tasks(list_id, **filters) -> generator of task dicts (auto-paginates)",
                "get_task": "cu.get_task(task_id, **params) -> {...}",
                "create_task": "cu.create_task(list_id, name='...', **fields) -> {...}",
                "update_task": "cu.update_task(task_id, **fields) -> {...}",
                "delete_task": "cu.delete_task(task_id) -> {}",
            },
        },
        "known_ids": IDS,
        "patterns": {
            "list_spaces": "result = [s['name'] for s in cu.get_spaces(TEAM_ID)['spaces']]",
            "discover_lists": "result = cu.get_folderless_lists(IDS['space_odoo'])['lists']  # -> list ids",
            "list_tasks": "result = list(cu.iter_tasks('901521388085'))  # pass a list_id explicitly (e.g. Odoo/Backlog)",
            "create_task": "result = cu.create_task('901521388085', name='New task', status='to do')  # list_id",
            "update_status": "result = cu.update_task('TASK_ID', status='in progress')",
            "raw_endpoint": "result = cu.get('/team/{}/space'.format(TEAM_ID))",
        },
        "write_warning": (
            "create_task / update_task / delete_task and any POST/PUT/DELETE mutate live "
            "ClickUp data. There is no dry-run — double-check IDs before writing."
        ),
        "commands": {
            "exec": "Execute Python with the pre-authenticated `cu` client (PRIMARY).",
            "check-auth": "Probe the API (cu.get_teams) to verify the token works.",
            "agent-info": "This reference.",
        },
        "exit_codes": {
            "0": "Success",
            "1": "Syntax or runtime error in the executed code",
            "2": "Configuration error (e.g. missing token)",
        },
    }
