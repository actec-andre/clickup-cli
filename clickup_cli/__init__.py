"""clickup-cli — self-contained, LLM-first exec CLI for the ClickUp API v2."""

from clickup_cli.client import ClickUp, ClickUpError

__version__ = "0.2.0"

__all__ = ["ClickUp", "ClickUpError", "__version__"]
