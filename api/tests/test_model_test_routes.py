"""ASGI caller/security controls, with session/DB/control doubles and no effects."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from omnis.api import create_app
from omnis.modules.engagements.service import EngagementService
from omnis.modules.runs.model_test_contract import ModelTestView
from omnis.security.sessions import SessionStore


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["entry-start", "entry-max", "entry-read", "entry-cancel", "legacy", "catalog", "run"]
)
@pytest.mark.parametrize(
    "code",
    [
        "GENERATION_CONFLICT",
        "AUTHORITY_DENIED",
        "ANSWER_DENIED",
        "REF_UNAVAILABLE",
        "MODEL_NOT_REGISTERED",
        "DATA_DENIED",
        "REVISION_CONFLICT",
        "CONTROL_UNAVAILABLE",
    ],
)
async def test_control_denial_is_definitive_only_for_its_command(
    monkeypatch: pytest.MonkeyPatch, case: str, code: str
) -> None:
    import asyncio
    import os
    import struct
    from unittest.mock import Mock

    from omnis.modules.runs import model_test_routes as routes
    from omnis.security import host_origin
    from omnis.transport.local_control import decode_control_frame

    identity = str(uuid4())
    body = {
        "operation_id": identity,
        "entry_id": identity,
        "expected_entry_revision": 1,
        "expected_connection_revision": 1,
        "catalog_command_id": identity,
        "expected_generation": 1,
        "consent": True,
    }
    path, method = "/api/v1/model-test/entries", "PUT"
    if case == "entry-max":
        body.update(
            expected_generation=9223372036854775806,
            expected_entry_revision=9223372036854775807,
            expected_connection_revision=9223372036854775807,
        )
    if case == "legacy":
        path = "/api/v1/model-test"
        body = {"operation_id": identity, "expected_selection_revision": 1, "consent": True}
    elif case == "entry-read":
        path, method = path + "/" + identity, "GET"
    elif case == "entry-cancel":
        path, method = path + "/" + identity + "/cancel", "POST"
        body = {"command_id": identity, "expected_state_revision": 1}
    elif case == "catalog":
        path, method = "/api/v1/settings/provider-catalog/search", "POST"
        body = {
            "action": "search",
            "connection_id": identity,
            "connection_revision": 1,
            "query": "",
        }
    elif case == "run":
        path, method = f"/api/v1/runs/{identity}/commands", "POST"
        body = {
            "action": "stop",
            "command_id": identity,
            "run_id": identity,
            "expected_generation": 1,
            "expected_revision": 1,
        }
    reader, writer = Mock(), Mock()
    reader.readuntil = AsyncMock(
        return_value=json.dumps({"ok": False, "error": code}).encode() + b"\n"
    )
    writer.drain, writer.wait_closed = AsyncMock(), AsyncMock()
    writer.get_extra_info.return_value.getsockopt.return_value = struct.pack(
        "3i", 123, os.getuid(), os.getgid()
    )
    monkeypatch.setenv("OMNIS_CONTROL_DIR", "/unused-source-control")
    monkeypatch.setattr(routes, "_read_capability", lambda directory: "a" * 64)
    monkeypatch.setattr(asyncio, "open_unix_connection", AsyncMock(return_value=(reader, writer)))
    monkeypatch.setattr(host_origin, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(
        SessionStore, "authenticate", AsyncMock(return_value=SimpleNamespace(csrf="a" * 64))
    )
    headers = {
        "Origin": "http://127.0.0.1:8765",
        "Cookie": "omnis_session=synthetic",
        "X-CSRF-Token": "a" * 64,
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://127.0.0.1:8765"
    ) as client:
        response = await client.request(
            method, path, headers=headers, json=None if method == "GET" else body
        )
    entry_generation = code == "GENERATION_CONFLICT" and case in {"entry-start", "entry-max"}
    definitive = (
        entry_generation
        or code == "REVISION_CONFLICT"
        or (case == "run" and code != "CONTROL_UNAVAILABLE")
    )
    assert response.status_code == (409 if definitive else 503)
    assert response.json()["error"]["code"] == (
        "REVISION_CONFLICT" if entry_generation else code if definitive else "CONTROL_UNAVAILABLE"
    )
    frame = writer.write.call_args.args[0]
    command = decode_control_frame(frame).command
    if case in {"entry-start", "entry-max"}:
        assert command.model_dump()["expected_generation"] == body["expected_generation"]
    if case == "run":
        assert command.op == "agent_run" and command.model_dump()["request"] == {
            **body,
            "question_id": None,
            "answer": None,
        }
    if case == "entry-max":
        assert len(frame) == 570
        print(f"ENTRY_ACTUAL_WRITER_MAX_BYTES={len(frame)}")
    assert len(frame) <= 4096
    writer.close.assert_called_once()
    writer.wait_closed.assert_awaited_once()


@pytest.mark.asyncio
async def test_latest_entry_read_security_context_and_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omnis.modules.runs import model_test_routes as routes
    from omnis.modules.runs.model_test_contract import EntryTestView
    from omnis.modules.runs.model_test_store import ModelConflict
    from omnis.security import host_origin

    readiness = AsyncMock(return_value=None)
    monkeypatch.setattr(host_origin, "readiness_reason", readiness)
    monkeypatch.setattr(
        SessionStore, "authenticate", AsyncMock(return_value=SimpleNamespace(csrf="a" * 64))
    )
    entry, operation = str(uuid4()), str(uuid4())
    view = EntryTestView(
        operation_id=operation,
        entry_id=entry,
        entry_revision=1,
        connection_id=str(uuid4()),
        connection_revision=1,
        current=True,
        state="FINISHED",
        state_revision=3,
        result_state="COMPLETED",
        requested_provider="openrouter",
        requested_model="Exact/model",
        requested_output_tokens=128,
    )
    exchange = AsyncMock(return_value=view.model_dump(mode="json"))
    monkeypatch.setattr(routes, "control_exchange", exchange)
    path = f"/api/v1/model-test/entries/latest/{entry}"
    headers = {"Cookie": "omnis_session=synthetic", "Origin": "http://127.0.0.1:8765"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://127.0.0.1:8765"
    ) as client:
        for altered, status in (
            ({"Host": "foreign.invalid"}, 400),
            ({"Origin": "https://foreign.invalid"}, 403),
            ({"Cookie": ""}, 401),
        ):
            assert (await client.get(path, headers={**headers, **altered})).status_code == status
        assert (await client.get(path + "?entry_id=other", headers=headers)).status_code == 400
        readiness.return_value = "unavailable"
        assert (await client.get(path, headers=headers)).status_code == 503
        readiness.return_value = None
        exchange.assert_not_awaited()
        response = await client.get(path, headers=headers)
        assert response.status_code == 200
        assert response.json() == view.model_dump(mode="json")
        assert response.headers["cache-control"] == "no-store"
        assert exchange.await_args is not None
        command = exchange.await_args.args[0]
        assert command.op == "entry_model_test" and command.action == "read"
        assert command.entry_id == entry and command.operation_id is None
        exchange.return_value = {**view.model_dump(mode="json"), "entry_id": str(uuid4())}
        assert (await client.get(path, headers=headers)).status_code == 503
        exchange.side_effect = ModelConflict("NOT_FOUND")
        missing = await client.get(path, headers=headers)
        assert missing.status_code == 404 and missing.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_instance_test_requires_no_saved_engagement(monkeypatch: pytest.MonkeyPatch) -> None:
    from omnis.modules.runs import model_test_routes as routes
    from omnis.security import host_origin

    monkeypatch.setattr(host_origin, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(
        SessionStore, "authenticate", AsyncMock(return_value=SimpleNamespace(csrf="a" * 64))
    )
    engagement_read = AsyncMock(
        side_effect=AssertionError("Synthetic connectivity must not read a draft")
    )
    monkeypatch.setattr(EngagementService, "read", engagement_read)
    view = ModelTestView()
    exchange = AsyncMock(return_value=view.model_dump(mode="json"))
    monkeypatch.setattr(routes, "control_exchange", exchange)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://127.0.0.1:8765"
    ) as client:
        response = await client.get(
            "/api/v1/model-test", headers={"Cookie": "omnis_session=synthetic"}
        )
    assert response.status_code == 200
    engagement_read.assert_not_awaited()
    assert response.json() == view.model_dump(mode="json")


@pytest.mark.asyncio
async def test_model_test_route_security_input_and_readback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omnis.modules.runs import model_test_routes as routes
    from omnis.security import host_origin

    identity, operation = str(uuid4()), str(uuid4())
    csrf = "a" * 64
    monkeypatch.setattr(host_origin, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(
        SessionStore, "authenticate", AsyncMock(return_value=SimpleNamespace(csrf=csrf))
    )
    monkeypatch.setattr(EngagementService, "read", AsyncMock())
    view = ModelTestView(
        operation_id=operation,
        state="PENDING",
        state_revision=1,
        selection_revision=1,
        requested_provider="openrouter",
        requested_model="fixture/model",
        requested_output_tokens=64,
    )
    exchange = AsyncMock(return_value=view.model_dump(mode="json"))
    monkeypatch.setattr(routes, "control_exchange", exchange)
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8765"
    ) as client:
        path = "/api/v1/model-test"
        body = {"operation_id": operation, "expected_selection_revision": 1, "consent": True}
        headers = {
            "Origin": "http://127.0.0.1:8765",
            "X-CSRF-Token": csrf,
            "Cookie": "omnis_session=synthetic",
        }
        assert (
            await client.put(path, json=body, headers={**headers, "Host": "foreign.invalid"})
        ).status_code == 400
        assert (
            await client.put(path, json=body, headers={"Origin": headers["Origin"]})
        ).status_code == 401
        assert (
            await client.put(path, json=body, headers={**headers, "X-CSRF-Token": "b" * 64})
        ).status_code == 403
        assert (
            await client.put(
                path, json=body, headers={**headers, "Origin": "https://foreign.invalid"}
            )
        ).status_code == 403
        for invalid in (
            {**body, "prompt": "raw"},
            {**body, "consent": 1},
            {**body, "consent": False},
            {k: v for k, v in body.items() if k != "consent"},
            {k: v for k, v in body.items() if k != "expected_selection_revision"},
            {**body, "expected_selection_revision": 0},
            {**body, "expected_selection_revision": True},
            {**body, "operation_id": True},
            {**body, "engagement_id": identity},
        ):
            assert (await client.put(path, json=invalid, headers=headers)).status_code == 422
        duplicate = (
            '{"operation_id":"'
            + operation
            + '","expected_selection_revision":1,"consent":true,"consent":true}'
        )
        assert (
            await client.put(
                path, content=duplicate, headers={**headers, "Content-Type": "application/json"}
            )
        ).status_code == 422
        assert (
            await client.put(
                path,
                content=json.dumps(body) + " " * 4096,
                headers={**headers, "Content-Type": "application/json"},
            )
        ).status_code == 413
        exchange.assert_not_awaited()
        response = await client.put(path, json=body, headers=headers)
        assert response.status_code == 202 and response.json() == view.model_dump(mode="json")
        assert response.headers["cache-control"] == "no-store"
        assert exchange.await_args is not None and exchange.await_args.args[0].action == "start"
        assert exchange.await_args.args[0].expected_selection_revision == 1
        assert exchange.await_args.args[0].consent is True
        response = await client.get(path, headers=headers)
        assert response.status_code == 200
        assert response.json() == view.model_dump(mode="json")
        assert exchange.await_args is not None and exchange.await_args.args[0].action == "read"
        assert "manifest_ref" not in response.text and "capability" not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["catalog", "entry"])
async def test_new_catalog_entry_same_security_boundary_and_context(
    monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    from omnis.modules.runs import model_test_routes as tests
    from omnis.modules.runs.model_test_contract import EntryTestView
    from omnis.modules.settings import provider_catalog_routes as catalog
    from omnis.modules.settings.provider_catalog_models import CatalogView
    from omnis.security import host_origin

    monkeypatch.setattr(host_origin, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(
        SessionStore, "authenticate", AsyncMock(return_value=SimpleNamespace(csrf="a" * 64))
    )
    identity = str(uuid4())
    method, path = (
        ("POST", "/api/v1/settings/provider-catalog/search")
        if kind == "catalog"
        else ("PUT", "/api/v1/model-test/entries")
    )
    body = (
        {"action": "search", "connection_id": identity, "connection_revision": 1, "query": ""}
        if kind == "catalog"
        else {
            "operation_id": identity,
            "entry_id": identity,
            "expected_generation": 1,
            "expected_entry_revision": 1,
            "expected_connection_revision": 1,
            "catalog_command_id": identity,
            "consent": True,
        }
    )
    view = (
        CatalogView(
            connection_id=identity,
            connection_revision=1,
            provider="openrouter",
            catalog_command_id=None,
            state="NOT_REQUESTED",
            query="",
            offset=0,
            total=0,
            entries=[],
        ).model_dump(mode="json")
        if kind == "catalog"
        else EntryTestView(
            operation_id=identity,
            state="PENDING",
            state_revision=1,
            requested_provider="openrouter",
            requested_model="Exact/model",
            requested_output_tokens=64,
            entry_id=identity,
            entry_revision=1,
            connection_id=identity,
            connection_revision=1,
            current=True,
        ).model_dump(mode="json")
    )
    exchange = AsyncMock(return_value=view)
    monkeypatch.setattr(catalog if kind == "catalog" else tests, "control_exchange", exchange)
    headers = {
        "Origin": "http://127.0.0.1:8765",
        "Cookie": "omnis_session=synthetic",
        "X-CSRF-Token": "a" * 64,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=create_app()), base_url="http://127.0.0.1:8765"
    ) as client:
        for altered, expected in (
            ({"Host": "foreign.invalid"}, 400),
            ({"Origin": "https://foreign.invalid"}, 403),
            ({"X-CSRF-Token": "b" * 64}, 403),
            ({"Cookie": ""}, 401),
        ):
            assert (
                await client.request(method, path, json=body, headers={**headers, **altered})
            ).status_code == expected
        assert (
            await client.request(method, path + "?q=forbidden", json=body, headers=headers)
        ).status_code == 400
        assert (
            await client.request(method, path, json={**body, "owner_epoch": 1}, headers=headers)
        ).status_code == 422
        duplicate = json.dumps(body)[:-1] + ',"' + next(iter(body)) + '":null}'
        assert (
            await client.request(method, path, content=duplicate, headers=headers)
        ).status_code == 422
        assert (
            await client.request(
                method, path, content=json.dumps(body) + " " * 4096, headers=headers
            )
        ).status_code == 413
        if kind == "entry":
            for invalid in (
                {k: v for k, v in body.items() if k != "expected_generation"},
                *(
                    {**body, "expected_generation": value}
                    for value in (None, True, "1", -1, 1.5, 9223372036854775807)
                ),
            ):
                assert (
                    await client.request(method, path, json=invalid, headers=headers)
                ).status_code == 422
        exchange.assert_not_awaited()
        response = await client.request(method, path, json=body, headers=headers)
        assert response.status_code == (200 if kind == "catalog" else 202), response.text
        assert response.json() == view and response.headers["cache-control"] == "no-store"
        if kind == "entry":
            assert (
                exchange.await_args is not None
                and exchange.await_args.args[0].expected_generation == 1
            )
            for generation in (0, 9223372036854775806):
                assert (
                    await client.request(
                        method,
                        path,
                        json={**body, "expected_generation": generation},
                        headers=headers,
                    )
                ).status_code == 202
                assert exchange.await_args.args[0].expected_generation == generation
        exchange.return_value = {**view, "connection_revision": 2}
        assert (await client.request(method, path, json=body, headers=headers)).status_code == 503
