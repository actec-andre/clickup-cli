Project instructions for `clickup-cli` — a standalone, self-contained, exec-only CLI for
the ClickUp API v2. Modeled on the sibling tools `odoo-cli exec` and `gel-cli`: each is its
own repo, bundles its own client, depends on no shared library, and installs globally via
pipx. It is self-contained — no shared library. (An older `clickup` typed-library/sync repo
was retired in favor of this CLI; see the retirement note under "Sibling repos".)

## Simplicity first (owner's standing preference)

Andre wants this kept **as simple as possible — always**. Fewer concepts, fewer moving parts,
and less to understand beat more features. Concretely:

- **Default to exec-only.** Don't add subcommands or flags unless they *remove* complexity
  rather than add surface area — `exec` already covers the long tail.
- **Prefer removing over adding.** We retired the old `clickup` repo, dropped the `sync`
  command, and removed the stale `default_list` ID for exactly this reason.
- **One place to learn the tool:** `agent-info`. Keep it current instead of growing docs.
- **When in doubt, ship the smaller thing.**

This applies to the ClickUp *workflow* too, not just the CLI — and there the audience is what
matters: **ClickUp is primarily for the (often non-technical) remaining staff to work with**, not
for Andre or the CLI/agents. The CLI is just one way in; the staff in the web/mobile UI are the
real users. So design the board for *them* — few plain-language status stages, few lists, few
required fields, and exactly one clear owner per task so each person can see "what's mine".

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

- `odoo-cli`, `gel-cli` — same standalone/pipx pattern for other systems.

> Note: an older `clickup` repo (typed async library + a git-tracked `docs/` task
> mirror) was retired in favor of this CLI. ClickUp is the source of truth; reach it
> live via `clickup-cli` — there are no maintained local task copies anymore.
