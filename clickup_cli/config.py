"""Token resolution from ``--token``, ``--env-file``, or the environment."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

TOKEN_ENV_VAR = "CLICKUP_API_TOKEN"


class ConfigError(Exception):
    """Raised when no usable ClickUp token can be resolved."""


def resolve_token(token: str | None = None, env_file: str | None = None) -> str:
    """Resolve the ClickUp API token.

    Precedence:
      1. explicit ``token`` argument (``--token``);
      2. ``CLICKUP_API_TOKEN`` from ``--env-file`` (file wins via ``override=True``);
      3. ``CLICKUP_API_TOKEN`` from an auto-discovered ``.env`` / the environment.

    Raises :class:`ConfigError` (never ``KeyError``) when nothing is found.
    """
    if env_file:
        path = Path(env_file)
        if not path.is_file():
            raise ConfigError(f"--env-file not found: {env_file}")
        load_dotenv(path, override=True)
    else:
        load_dotenv()

    resolved = token or os.environ.get(TOKEN_ENV_VAR)
    if not resolved:
        raise ConfigError(
            f"No ClickUp API token found. Set {TOKEN_ENV_VAR} in a .env file, pass "
            "--token, or point --env-file at a file containing it."
        )
    return resolved
