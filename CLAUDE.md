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

**Keep sensitive data out of ClickUp.** Access is flat — every workspace member sees every
space/list/task — so task names, descriptions and comments must NOT carry internal financial
figures (€ amounts, exposure, PO values), personal/HR/health/disciplinary info, or security
secrets (keys, IPs, passwords). There's little to hide org-wide, but flat visibility leaks
sensitive detail to everyone. Keep tasks operational and put the sensitive detail in the
access-controlled `obsidian-rh` vault, linked from the task via `Quelle: <vault path>` instead.

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
  methods (`get_teams`, `get_spaces`, `get_members`, `get_list`, `get_tasks`/`iter_tasks`,
  `iter_space_tasks`, `create_task`, `update_task`, `assign`, …) wrap the common endpoints.
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

## IDs: resolve them, do not hard-code them

The workspace is the only id the code holds: `TEAM_ID` in `runner.py`, overridable with the
`CLICKUP_TEAM_ID` environment variable. It is injected into the exec namespace together with
`IDS` (which now contains just that one key) and drives `agent-info`.

**Space, list and member ids are resolved live.** This file used to list four spaces; two of
them had been deleted and returned "Space not found" to anyone who trusted the list. ClickUp is
the source of truth, so ask it:

```bash
clickup-cli exec -c "result = spaces()" --json                       # {name: id}
clickup-cli exec -c "result = cu.get_folderless_lists(spaces()['Magento'])['lists']" --json
clickup-cli exec -c "result = {m['email']: m['id'] for m in cu.get_members(TEAM_ID)}" --json
```

## API notes

- Base URL: `https://api.clickup.com/api/v2`
- Auth: token sent **directly** as the `Authorization` header (no `Bearer` prefix).
- Rate limit: retries 429 up to 3× honoring `Retry-After`; non-2xx raises `ClickUpError`.
- Tasks paginate at 100/page; `iter_tasks` stops on `last_page` or a short page;
  `iter_space_tasks` chains that across every list in a space.
- Assignees use an add/rem dict on update: `assignees={"add":[id],"rem":[id]}` (IDs are ints);
  `cu.assign(task_id, add=[...], rem=[...])` wraps it.
- **Status SETS are UI-only:** API v2 cannot create/edit/delete the status options at
  space/folder/list level. You can only set a task's status *value* (to one already on its
  list). List deletion is irreversible; clean list *archiving* isn't exposed in v2.
- **Cross-space moves are UI-only:** there is no endpoint to move a task/list into another
  space. `update_task(list=...)` is a no-op; the multi-list endpoint is 403 unless that paid
  feature is on. Recreate+delete is the only (lossy) CLI workaround.

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
