"""Self-contained synchronous ClickUp API v2 client.

No Pydantic, no shared library — every call returns raw JSON (dict/list) so exec
users can manipulate plain data and emit it straight to ``--json``.

Auth follows ClickUp's personal-token scheme: the token is sent **directly** as the
``Authorization`` header (no ``Bearer`` prefix). Construction is offline — no HTTP
happens until the first request, so a dummy token works for tests and ``exec`` of
pure-Python snippets.
"""

from __future__ import annotations

import time
from typing import Any, Iterator

import httpx

BASE_URL = "https://api.clickup.com/api/v2"
MAX_RETRIES = 3
# ClickUp returns up to 100 tasks per page; a short page means we hit the end.
PAGE_SIZE = 100


class ClickUpError(Exception):
    """Raised on a non-2xx ClickUp API response.

    Attributes:
        message: Human-readable error message.
        status_code: HTTP status code (``None`` for transport-level failures).
        response_json: Parsed JSON body of the error response, if any.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_json: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_json = response_json


class ClickUp:
    """Synchronous ClickUp API v2 client.

    Usage::

        with ClickUp(token="pk_...") as cu:
            spaces = cu.get_spaces("90152385271")["spaces"]
    """

    def __init__(
        self,
        token: str,
        *,
        base_url: str = BASE_URL,
        timeout: float = 30,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self._max_retries = max_retries
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": token, "Content-Type": "application/json"},
            timeout=timeout,
        )

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> ClickUp:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # -- generic escape hatch ---------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> Any:
        """Perform a request and return parsed JSON.

        Retries on HTTP 429 up to ``max_retries`` times, honoring ``Retry-After``.
        Raises :class:`ClickUpError` on any non-2xx response.
        """
        response: httpx.Response | None = None
        for attempt in range(self._max_retries + 1):
            response = self._client.request(method, path, params=params, json=json)
            if response.status_code == 429 and attempt < self._max_retries:
                time.sleep(float(response.headers.get("Retry-After", "1")))
                continue
            break

        assert response is not None  # loop always assigns at least once
        if not response.is_success:
            self._raise(response)

        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {}

    def get(self, path: str, **params: Any) -> Any:
        return self.request("GET", path, params=params or None)

    def post(self, path: str, json: Any = None, **params: Any) -> Any:
        return self.request("POST", path, params=params or None, json=json)

    def put(self, path: str, json: Any = None, **params: Any) -> Any:
        return self.request("PUT", path, params=params or None, json=json)

    def delete(self, path: str, **params: Any) -> Any:
        return self.request("DELETE", path, params=params or None)

    @staticmethod
    def _raise(response: httpx.Response) -> None:
        try:
            body = response.json()
        except ValueError:
            body = response.text or None
        message = None
        if isinstance(body, dict):
            message = body.get("err") or body.get("error") or body.get("message")
        raise ClickUpError(
            message or f"ClickUp API error {response.status_code}",
            status_code=response.status_code,
            response_json=body,
        )

    # -- convenience: workspaces / spaces ---------------------------------

    def get_teams(self) -> dict[str, Any]:
        """Authorized workspaces. Returns ``{"teams": [...]}``."""
        return self.get("/team")

    def get_spaces(self, team_id: str, *, archived: bool = False) -> dict[str, Any]:
        """Spaces in a workspace. Returns ``{"spaces": [...]}``."""
        return self.get(f"/team/{team_id}/space", archived=str(archived).lower())

    def get_space(self, space_id: str) -> dict[str, Any]:
        return self.get(f"/space/{space_id}")

    # -- convenience: folders / lists -------------------------------------

    def get_folders(self, space_id: str, *, archived: bool = False) -> dict[str, Any]:
        """Folders in a space. Returns ``{"folders": [...]}``."""
        return self.get(f"/space/{space_id}/folder", archived=str(archived).lower())

    def get_lists(self, folder_id: str, *, archived: bool = False) -> dict[str, Any]:
        """Lists in a folder. Returns ``{"lists": [...]}``."""
        return self.get(f"/folder/{folder_id}/list", archived=str(archived).lower())

    def get_folderless_lists(self, space_id: str, *, archived: bool = False) -> dict[str, Any]:
        """Folderless lists in a space. Returns ``{"lists": [...]}``."""
        return self.get(f"/space/{space_id}/list", archived=str(archived).lower())

    # -- convenience: tasks -----------------------------------------------

    def get_tasks(self, list_id: str, **filters: Any) -> dict[str, Any]:
        """One page of tasks in a list. Returns ``{"tasks": [...], "last_page": bool}``.

        ``filters`` are passed through as query params (e.g. ``page``, ``archived``,
        ``include_closed``, ``order_by``, ``subtasks``).
        """
        return self.get(f"/list/{list_id}/task", **filters)

    def iter_tasks(self, list_id: str, **filters: Any) -> Iterator[dict[str, Any]]:
        """Yield every task in a list, auto-paginating via ``page``.

        Stops when the API reports ``last_page`` or returns a short (< 100) page.
        """
        page = filters.pop("page", 0)
        while True:
            data = self.get_tasks(list_id, page=page, **filters)
            tasks = data.get("tasks", [])
            yield from tasks
            if data.get("last_page") or len(tasks) < PAGE_SIZE:
                break
            page += 1

    def get_task(self, task_id: str, **params: Any) -> dict[str, Any]:
        return self.get(f"/task/{task_id}", **params)

    def create_task(self, list_id: str, **fields: Any) -> dict[str, Any]:
        """Create a task. ``name`` is required by ClickUp; other fields pass through."""
        return self.post(f"/list/{list_id}/task", json=fields)

    def update_task(self, task_id: str, **fields: Any) -> dict[str, Any]:
        return self.put(f"/task/{task_id}", json=fields)

    def delete_task(self, task_id: str) -> dict[str, Any]:
        return self.delete(f"/task/{task_id}")
