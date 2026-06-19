`clickup-cli` is a standalone, self-contained CLI for the [ClickUp API v2](https://clickup.com/api),
built in the **exec-only / LLM-first** shape: instead of one subcommand per endpoint, you
write small Python snippets that run against a pre-authenticated `cu` client and emit JSON.

It bundles its own sync HTTP client (no shared library) and installs globally via pipx,
alongside the sibling tools `odoo-cli` and `gel-cli`.

## Install

```bash
pipx install --editable /Users/andre/Documents/dev/claude/clickup-cli
```

Or for local development:

```bash
cd clickup-cli
uv venv && uv pip install -e ".[dev]"
uv run pytest -v
```

## Token

The CLI reads `CLICKUP_API_TOKEN` from the environment or a `.env` file. Copy the example
and fill in your personal token (`pk_...`):

```bash
cp .env.example .env
# edit .env -> CLICKUP_API_TOKEN=pk_...
```

Resolution order: `--token` flag → `--env-file` path → auto-discovered `.env` / environment.

## Commands

```bash
clickup-cli agent-info          # full namespace + API reference (great first call for an LLM)
clickup-cli check-auth          # verify the token (lists authorized workspaces)
clickup-cli exec -c "<code>"    # run Python against the cu client
```

### exec

The executed code has access to a pre-authenticated `cu` client plus a small namespace:

| Name | Description |
| --- | --- |
| `cu` | Authenticated ClickUp client — use for all API calls |
| `ClickUpError` | Exception raised on API errors (`.status_code`, `.response_json`) |
| `IDS` / `TEAM_ID` | Known RHHOLDING workspace IDs |
| `json`, `os`, `datetime`, `date`, `timedelta`, `pprint` | Stdlib helpers |
| `result` | Set this for structured output (defaults to `None`) |

**The result contract:** set `result`, **or** end your snippet with a bare expression — its
value becomes `result` (Jupyter-cell style). `stdout` is captured separately.

```bash
# Set result explicitly
clickup-cli exec -c "result = cu.get_teams()" --json

# Trailing expression becomes the result
clickup-cli exec -c "[s['name'] for s in cu.get_spaces(TEAM_ID)['spaces']]" --json

# From a file
clickup-cli exec -f report.py --json

# From stdin
echo "cu.get_task('abc123')" | clickup-cli exec --json
```

### The `cu` client

Generic escape hatch over the whole API (paths are relative to
`https://api.clickup.com/api/v2`):

```python
cu.request(method, path, *, params=None, json=None)
cu.get(path, **params)
cu.post(path, json=None, **params)
cu.put(path, json=None, **params)
cu.delete(path, **params)
```

Convenience methods (all return raw dicts/lists):

```python
cu.get_teams()                                  # {"teams": [...]}
cu.get_spaces(team_id)                          # {"spaces": [...]}
cu.get_space(space_id)
cu.get_folders(space_id)                        # {"folders": [...]}
cu.get_lists(folder_id)                         # {"lists": [...]}
cu.get_folderless_lists(space_id)               # {"lists": [...]}
cu.get_tasks(list_id, **filters)                # one page
cu.iter_tasks(list_id, **filters)               # generator, auto-paginates
cu.get_task(task_id)
cu.create_task(list_id, name="...", **fields)
cu.update_task(task_id, **fields)
cu.delete_task(task_id)
```

## Output

With `--json`, every command emits exactly one compact envelope:

```json
{"schema":1,"success":true,"result":2,"stdout":""}
```

On error:

```json
{"schema":1,"success":false,"error":{"type":"ValueError","message":"boom","status":null,"category":"runtime"}}
```

Without `--json`, results render via Rich and errors print in red to stderr. Add
`--traceback` to include a Python traceback in error envelopes.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Syntax or runtime error in the executed code |
| `2` | Configuration error (e.g. missing token) |

## Known IDs (RHHOLDING)

| Key | ID |
| --- | --- |
| `team` (workspace) | `90152385271` |
| `space_odoo` | `901510167199` |
| `space_rhholding` | `901510675913` |
| `default_list` | `901522542210` |
