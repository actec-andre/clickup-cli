Project instructions for `clickup-cli` — a standalone, self-contained, exec-only CLI for
the ClickUp API v2. Modeled on the sibling tools `odoo-cli exec` and `gel-cli`: each is its
own repo, bundles its own client, depends on no shared library, and installs globally via
pipx. This repo does **not** import the separate `clickup` Python library; that library is a
behavioral reference only.

## Architecture

```
clickup_cli/
├── __init__.py     # exports ClickUp, ClickUpError, __version__
├── cli.py          # Click group: exec, check-auth, agent-info (+ shared options)
├── client.py       # self-contained sync ClickUp client (httpx.Client)
├── runner.py       # exec engine: namespace, to_jsonable, run_source, envelope, IDS
├── config.py       # token resolution (--token / --env-file / .env)
└── agent_info.py   # AGENT_INFO reference, built from IDS
```

- **Exec-only / LLM-first:** there is no subcommand per endpoint. The user/agent writes
  Python that runs against a pre-authenticated `cu` client and emits JSON.
- **Client returns raw JSON** (dicts/lists), not Pydantic models. A generic
  `request()/get()/post()/put()/delete()` escape hatch covers the whole API; convenience
  methods (`get_teams`, `get_spaces`, `get_tasks`/`iter_tasks`, `create_task`, …) wrap the
  common endpoints.
- **Sync** (`httpx.Client`) so exec code is plain synchronous Python (no event loop).
- **Construction is offline** — no HTTP until the first call, so a dummy token and
  pure-Python snippets work network-free (used heavily in tests).

## Result contract

The executed code sets `result`, **or** ends with a bare trailing expression whose value
becomes `result` (Jupyter-cell ergonomics, handled via AST rewrite in `runner.py`). stdout
is captured separately. Every run returns a stable envelope:

```json
{"schema":1,"success":true,"result":...,"stdout":"..."}
{"schema":1,"success":false,"error":{"type":...,"message":...,"status":...,"category":...}}
```

Error categories map to exit codes: `config` → 2, `syntax`/`runtime` → 1.

## Key IDs (single source of truth: `runner.IDS`)

- Team/Workspace: `90152385271` (RHHOLDING)
- Space Odoo: `901510167199`
- Space RHHOLDING: `901510675913`
- Default List: `901522542210`

`IDS` and `TEAM_ID` are injected into the exec namespace and drive `agent-info`. Change them
in `runner.py` only.

## API notes

- Base URL: `https://api.clickup.com/api/v2`
- Auth: token sent **directly** as the `Authorization` header (no `Bearer` prefix).
- Rate limit: retries 429 up to 3× honoring `Retry-After`; non-2xx raises `ClickUpError`.
- Tasks paginate at 100/page; `iter_tasks` stops on `last_page` or a short page.

## Quick start

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest -v                                   # all tests are offline (respx-mocked)
clickup-cli agent-info
clickup-cli exec -c "1+1" --json --token dummy     # -> {"schema":1,"success":true,"result":2,"stdout":""}
clickup-cli check-auth                             # needs a real token in .env
```

## Conventions

- Token in `.env` (gitignored); copy `.env.example`.
- CLI-first: every operation reachable headlessly via `exec`.
- Tests must stay offline — use `respx` to mock the API, dummy tokens for pure-Python.
- Docs authored here start at `##` (no lone H1), per house style.

## Sibling repos

- `clickup` (separate repo, `/Users/andre/Documents/dev/claude/clickup`) — the typed,
  async-first Python library + Obsidian sync scripts. Independent from this CLI.
- `odoo-cli`, `gel-cli` — same standalone/pipx pattern for other systems.
