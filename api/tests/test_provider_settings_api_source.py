"""SOURCE simulation on actual public ASGI + private control UDS, without PG/native."""

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest

from omnis.api import create_app
from omnis.modules.instance.service import RuntimeAuthority
from omnis.modules.settings.provider_models import SettingsControl
from omnis.security import host_origin
from omnis.security.sessions import SessionGrant, SessionStore
from omnis.supervisor.runtime_client import RuntimeClient
from omnis.transport import local_control
from omnis.transport.local_control import LocalControl


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_action", [None, "auth_read", "logout"])
async def test_public_settings_same_owner_save_readback_and_boundaries(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, auth_action: str | None
) -> None:
    monkeypatch.syspath_prepend(
        str(Path(__file__).resolve().parents[2] / "integrations/hermes/src")
    )
    from omnis_hermes.runtime_host import RuntimeHost

    runtime_dir, control_dir = ipc_directory / "r", ipc_directory / "c"
    runtime_dir.mkdir(mode=0o700)
    control_dir.mkdir(mode=0o700)
    monkeypatch.setenv("OMNIS_CONTROL_DIR", str(control_dir))
    monkeypatch.setenv("OMNIS_HTTP_PORT", "8765")
    grant = SessionGrant("source-synthetic-session")
    monkeypatch.setattr(host_origin, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(local_control, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(SessionStore, "authenticate", AsyncMock(return_value=grant))
    service = Mock()
    service.runtime_authority = AsyncMock(
        side_effect=lambda *a, **k: RuntimeAuthority(0, 1, time.monotonic_ns() + 4_000_000_000)
    )
    owner = uuid4()
    host = RuntimeHost(runtime_dir)
    stored: dict[str, object] | None = None
    writes = 0
    auth_calls: list[str] = []

    async def native(action: str, selection: object) -> dict[str, object] | None:
        nonlocal stored, writes
        if action in {"auth_read", "logout"}:
            auth_calls.append(action)
            return {
                "selection": stored,
                "authenticated": "ABSENT" if action == "logout" else "LOCAL_PRESENT",
            }
        if action == "save":
            assert type(selection) is dict
            stored = selection
            writes += 1
        return stored

    monkeypatch.setattr(host, "_settings_native", native)
    async with host:
        client = RuntimeClient(runtime_dir, generation=0, epoch=1)
        await client.connect()
        try:
            async with LocalControl(control_dir, service, owner, 1) as control:

                async def handle(command: SettingsControl) -> dict[str, object]:
                    if command.command is None:
                        return await client.settings_status(command.operation_id)
                    return await client.settings(
                        service, owner, command.command.model_dump(mode="json")
                    )

                control.settings = handle
                app = create_app()
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8765"
                ) as http:
                    path = "/api/v1/settings/provider"
                    operation_id = str(uuid4())
                    selected = {
                        "provider": "openai-codex",
                        "model": "gpt-6.1-sol",
                        "effort": "xhigh",
                    }
                    payload: dict[str, object] = {
                        "operation_id": operation_id,
                        "action": "save",
                        "selection": selected,
                    }
                    headers = {
                        "Origin": "http://127.0.0.1:8765",
                        "Content-Type": "application/json",
                    }
                    assert (await http.put(path, json=payload, headers=headers)).status_code == 401
                    http.cookies.set("omnis_session", grant.token)
                    assert (await http.put(path, json=payload, headers=headers)).status_code == 403
                    headers["X-CSRF-Token"] = grant.csrf
                    assert (
                        await http.put(path + "?profile=foreign", json=payload, headers=headers)
                    ).status_code == 400
                    assert (
                        await http.put(
                            path, json={**payload, "profile": "foreign"}, headers=headers
                        )
                    ).status_code == 422
                    assert (
                        await http.put(
                            path,
                            json={**payload, "selection": {**selected, "effort": "high"}},
                            headers=headers,
                        )
                    ).status_code == 422
                    raw = json.dumps(payload).encode()
                    duplicate = raw[:-1] + b',"action":"save"}'
                    assert (
                        await http.put(path, content=duplicate, headers=headers)
                    ).status_code == 422
                    assert (
                        await http.put(
                            path, content=raw + b" " * (4097 - len(raw)), headers=headers
                        )
                    ).status_code == 413
                    assert writes == 0
                    result = await http.put(
                        path, content=raw + b" " * (4096 - len(raw)), headers=headers
                    )
                    assert result.status_code == 200
                    assert result.json()["status"] == "PENDING"
                    assert result.headers["cache-control"] == "no-store"
                    for _ in range(20):
                        read = await http.get(path + "/operations/" + operation_id)
                        if read.json()["status"] != "PENDING":
                            break
                        await asyncio.sleep(0.01)
                    assert read.json()["status"] == "CONFIRMED"
                    assert read.json()["selection"] == payload["selection"]
                    assert read.json()["authenticated"] == "NOT_VERIFIED"
                    assert read.json()["reachable"] == "NOT_VERIFIED"
                    assert read.json()["inference_ready"] is False
                    # Same operation is retained, not replayed into the native writer.
                    assert (await http.put(path, json=payload, headers=headers)).json()[
                        "status"
                    ] == "CONFIRMED"
                    assert writes == 1
                    fresh_id = str(uuid4())
                    fresh = {"operation_id": fresh_id, "action": "read", "selection": None}
                    assert (await http.put(path, json=fresh, headers=headers)).status_code == 200
                    await asyncio.sleep(0.01)
                    result = await http.get(path + "/operations/" + fresh_id)
                    assert result.json()["selection"] == payload["selection"]
                    assert writes == 1
                    # Unchanged private frame cap: exact max and max+1 on the real UDS.
                    probe = json.dumps(
                        {
                            "version": 1,
                            "capability": control.capability,
                            "command": {
                                "op": "settings",
                                "command": None,
                                "operation_id": fresh_id,
                            },
                        }
                    ).encode()
                    for size, accepted in ((4096, True), (4097, False)):
                        reader, writer = await asyncio.open_unix_connection(
                            control_dir / "control.sock"
                        )
                        try:
                            writer.write(probe + b" " * (size - len(probe) - 1) + b"\n")
                            await writer.drain()
                            reply = json.loads(await asyncio.wait_for(reader.readuntil(b"\n"), 2))
                            assert reply["ok"] is accepted
                            if accepted:
                                assert reply["settings"]["selection"] == selected
                            else:
                                assert reply["error"] == "INVALID_REQUEST"
                        finally:
                            writer.close()
                            await writer.wait_closed()
                    assert writes == 1
                    if auth_action is not None:
                        auth_id = str(uuid4())
                        auth_payload = {
                            "operation_id": auth_id,
                            "action": auth_action,
                            "selection": None,
                        }
                        start = await http.put(path, json=auth_payload, headers=headers)
                        assert start.status_code == 200
                        async with asyncio.timeout(1):
                            while True:
                                auth_result = await http.get(path + "/operations/" + auth_id)
                                if auth_result.json()["status"] != "PENDING":
                                    break
                                await asyncio.sleep(0.001)
                        assert auth_result.json()["status"] == "CONFIRMED"
                        assert auth_result.json()["authenticated"] == (
                            "ABSENT" if auth_action == "logout" else "LOCAL_PRESENT"
                        )
                        assert auth_result.json()["selection"] == selected
                        assert auth_result.json()["reachable"] == "NOT_VERIFIED"
                        assert auth_result.json()["inference_ready"] is False
                        assert auth_result.headers["cache-control"] == "no-store"
                        assert (
                            await http.put(path, json=auth_payload, headers=headers)
                        ).json() == auth_result.json()
                        assert auth_calls == [auth_action]
                        assert writes == 1
        finally:
            await client.close()
