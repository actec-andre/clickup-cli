"""Client tests against a respx-mocked ClickUp API (offline)."""

from __future__ import annotations

import httpx
import pytest
import respx

from clickup_cli.client import ClickUp, ClickUpError

BASE = "https://api.clickup.com/api/v2"


@respx.mock
def test_auth_header_has_no_bearer_prefix():
    route = respx.get(f"{BASE}/team").mock(
        return_value=httpx.Response(200, json={"teams": []})
    )
    with ClickUp("pk_test_123") as cu:
        cu.get_teams()

    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "pk_test_123"
    assert "Bearer" not in request.headers["Authorization"]


@respx.mock
def test_429_retries_then_succeeds():
    route = respx.get(f"{BASE}/team").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}, json={"err": "rate"}),
            httpx.Response(200, json={"teams": [{"name": "RHHOLDING"}]}),
        ]
    )
    with ClickUp("pk") as cu:
        data = cu.get_teams()

    assert data["teams"][0]["name"] == "RHHOLDING"
    assert route.call_count == 2


@respx.mock
def test_persistent_429_raises():
    respx.get(f"{BASE}/team").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"}, json={"err": "rate"})
    )
    with ClickUp("pk", max_retries=2) as cu:
        with pytest.raises(ClickUpError) as exc_info:
            cu.get_teams()
    assert exc_info.value.status_code == 429


@respx.mock
def test_iter_tasks_stops_on_short_page():
    full_page = {"tasks": [{"id": str(i)} for i in range(100)], "last_page": False}
    short_page = {"tasks": [{"id": "last"}], "last_page": False}
    route = respx.get(f"{BASE}/list/L1/task").mock(
        side_effect=[
            httpx.Response(200, json=full_page),
            httpx.Response(200, json=short_page),
        ]
    )
    with ClickUp("pk") as cu:
        tasks = list(cu.iter_tasks("L1"))

    assert len(tasks) == 101
    assert route.call_count == 2


@respx.mock
def test_iter_tasks_respects_last_page_flag():
    route = respx.get(f"{BASE}/list/L1/task").mock(
        return_value=httpx.Response(
            200, json={"tasks": [{"id": str(i)} for i in range(100)], "last_page": True}
        )
    )
    with ClickUp("pk") as cu:
        tasks = list(cu.iter_tasks("L1"))

    assert len(tasks) == 100
    assert route.call_count == 1


@respx.mock
def test_error_response_raises_clickup_error():
    respx.get(f"{BASE}/task/bad").mock(
        return_value=httpx.Response(404, json={"err": "Task not found", "ECODE": "OAUTH_027"})
    )
    with ClickUp("pk") as cu:
        with pytest.raises(ClickUpError) as exc_info:
            cu.get_task("bad")

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value).lower()
    assert exc_info.value.response_json["ECODE"] == "OAUTH_027"


@respx.mock
def test_create_task_posts_json_body():
    route = respx.post(f"{BASE}/list/L1/task").mock(
        return_value=httpx.Response(200, json={"id": "abc", "name": "New"})
    )
    with ClickUp("pk") as cu:
        created = cu.create_task("L1", name="New", status="to do")

    assert created["id"] == "abc"
    sent = route.calls.last.request
    import json

    assert json.loads(sent.content) == {"name": "New", "status": "to do"}


@respx.mock
def test_delete_task_returns_empty_dict_on_204():
    respx.delete(f"{BASE}/task/abc").mock(return_value=httpx.Response(204))
    with ClickUp("pk") as cu:
        assert cu.delete_task("abc") == {}


@respx.mock
def test_generic_get_hits_relative_path():
    route = respx.get(f"{BASE}/team/T1/space").mock(
        return_value=httpx.Response(200, json={"spaces": [{"name": "Odoo"}]})
    )
    with ClickUp("pk") as cu:
        data = cu.get("/team/T1/space")

    assert route.called
    assert data["spaces"][0]["name"] == "Odoo"
