"""Real paired API/private control/PG/public SDK, owned UDS TLS protocol fixture only."""

import asyncio
import json
import os
import ssl
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import URL

from omnis.api import create_app
from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs import model_test_operation
from omnis.modules.runs.model_test_models import ModelTestControl
from omnis.modules.settings.provider_key_models import KeySettingsControl
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from omnis.modules.settings.provider_vault import ProviderVault
from omnis.security.sessions import SessionStore, code_digest
from omnis.transport.local_control import LocalControl


def test_production_consumer_exists() -> None:
    assert hasattr(model_test_operation, "ApiKeyModelTest"), "T1 production consumer missing"


def tls_contexts(root: Path) -> tuple[ssl.SSLContext, ssl.SSLContext]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "openrouter.ai")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("openrouter.ai")]), True)
        .sign(key, hashes.SHA256())
    )
    public, private = root / "cert.pem", root / "key.pem"
    public.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public.chmod(0o600)
    private.chmod(0o600)
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(public, private)
    return server, ssl.create_default_context(cafile=str(public))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "complete",
        "unknown_usage",
        "negative_usage",
        "unsafe_usage",
        "coerced_usage",
        "invalid_reasoning",
        "secret_long",
        "secret_cross",
        "stop_at_body",
        "revoke_at_body",
        "cancel_at_body",
    ],
)
async def test_api_pg_sdk_protocol_and_replay(
    migrated_database_url: URL,
    ipc_directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    # RED is the absent production consumer, not a fabricated repository response.
    assert hasattr(model_test_operation, "ApiKeyModelTest"), "T1 production consumer missing"
    from omnis.modules.runs.model_test_operation import ApiKeyModelTest
    from omnis.supervisor.model_sender import ModelSender

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service = InstanceService(engine)
    process = uuid4()
    epoch = await service.acquire(process)
    initial = await service.owned_status(process, epoch)
    generation = await service.open(uuid4(), initial.generation, process, epoch)
    control_dir = ipc_directory / "c"
    control_dir.mkdir(mode=0o700)
    vault_dir, keys = tmp_path / "vault", tmp_path / "keys"
    vault_dir.mkdir(mode=0o700)
    keys.mkdir(mode=0o700)
    settings = ProviderSettingsOwner(
        service, process, epoch, ProviderVault(vault_dir, keys, str(initial.instance_id))
    )
    connection_id = str(uuid4())
    secret = (
        "Bcanary-" + "Z" * 504
        if scenario == "secret_long"
        else "canary-" + "Q" * 24
        if scenario == "secret_cross"
        else "synthetic-not-provider-key"
    )
    await settings.handle(
        KeySettingsControl.model_validate(
            {
                "op": "provider_settings",
                "request": {
                    "action": "save_connection",
                    "command_id": str(uuid4()),
                    "connection_id": connection_id,
                    "expected_revision": 0,
                    "provider": "openrouter",
                    "secret": secret,
                },
            }
        )
    )
    await settings.handle(
        KeySettingsControl.model_validate(
            {
                "op": "provider_settings",
                "request": {
                    "action": "save_selection",
                    "command_id": str(uuid4()),
                    "expected_revision": 0,
                    "default": {
                        "connection_id": connection_id,
                        "connection_revision": 1,
                        "model": "fixture/model",
                        "output_tokens": 64,
                    },
                    "brain": None,
                    "investigator": None,
                    "validator": None,
                },
            }
        )
    )
    server_context, client_context = tls_contexts(tmp_path)
    socket = ipc_directory / "p"
    assert len(bytes(socket)) <= 107
    received: list[tuple[str, bytes]] = []
    tasks: set[asyncio.Task[None]] = set()

    async def serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        tasks.add(task)
        try:
            while True:
                try:
                    headers = await reader.readuntil(b"\r\n\r\n")
                    first = headers.split(b"\r\n", 1)[0].decode()
                    lengths = [
                        line.split(b":", 1)[1].strip()
                        for line in headers.split(b"\r\n")
                        if line.lower().startswith(b"content-length:")
                    ]
                    body = await reader.readexactly(int(lengths[0])) if lengths else b""
                except asyncio.IncompleteReadError:
                    return
                received.append((first, body))
                if first == "GET /api/v1/models HTTP/1.1":
                    payload: dict[str, object] = {
                        "data": [
                            {
                                "id": "fixture/model",
                                "supported_parameters": ["max_tokens"],
                                "top_provider": {"max_completion_tokens": 128},
                            }
                        ]
                    }
                else:
                    assert first == "POST /api/v1/chat/completions HTTP/1.1"
                    data = json.loads(body)
                    assert data["model"] == "fixture/model" and data["max_tokens"] == 64
                    assert data["provider"] == {
                        "allow_fallbacks": False,
                        "require_parameters": True,
                    }
                    payload = {
                        "id": "synthetic-protocol-not-provider-live",
                        "object": "chat.completion",
                        "created": 0,
                        "model": "fixture/observed",
                        "choices": [
                            {
                                "index": 0,
                                "message": {"role": "assistant", "content": "OMNIS_MODEL_TEST_OK"},
                                "finish_reason": "stop",
                            }
                        ],
                        "usage": {"prompt_tokens": 9, "completion_tokens": 7, "total_tokens": 16},
                    }
                if first.startswith("POST") and scenario.startswith("secret_"):
                    echoed = ("x" * 250 if scenario == "secret_cross" else "") + secret
                    payload["model"] = echoed
                    payload["id"] = echoed
                if scenario == "unknown_usage":
                    payload.pop("usage", None)
                if first.startswith("POST"):
                    if scenario in {"negative_usage", "unsafe_usage", "coerced_usage"}:
                        payload["usage"] = {
                            "prompt_tokens": {
                                "negative_usage": -1,
                                "unsafe_usage": 9007199254740992,
                                "coerced_usage": "9",
                            }[scenario],
                            "completion_tokens": 7,
                            "total_tokens": 16,
                        }
                    elif scenario == "invalid_reasoning":
                        payload["usage"] = {
                            "prompt_tokens": 9,
                            "completion_tokens": 7,
                            "total_tokens": 16,
                            "completion_tokens_details": {"reasoning_tokens": True},
                        }
                raw = json.dumps(payload).encode()
                writer.write(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                    + str(len(raw)).encode()
                    + b"\r\n\r\n"
                    + raw
                )
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.discard(task)

    server = await asyncio.start_unix_server(serve, socket, ssl=server_context)
    sender = ModelSender(socket, client_context)
    owner = ApiKeyModelTest(settings, sender)
    service.runtime_drain = owner.drain
    monkeypatch.setenv("OMNIS_CONTROL_DIR", str(control_dir))
    monkeypatch.setenv("OMNIS_HTTP_PORT", "8765")
    sessions = SessionStore(engine)
    await sessions.register(code_digest("synthetic-pairing"), issuance_id=uuid4())
    grant = await sessions.exchange("synthetic-pairing")
    released = False
    commands: list[ModelTestControl] = []
    try:
        async with LocalControl(control_dir, service, process, epoch) as control:

            async def model_command(command: ModelTestControl) -> dict[str, object]:
                commands.append(command)
                try:
                    return await owner.handle(command)
                except ValidationError as error:
                    print(error.errors(include_input=False, include_url=False))
                    raise

            control.model_test = model_command
            app = create_app()
            app.state.db_engine = engine
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8765"
            ) as http:
                operation = str(uuid4())
                intent = {
                    "operation_id": operation,
                    "expected_selection_revision": 1,
                    "consent": True,
                }
                headers = {"Origin": "http://127.0.0.1:8765", "Content-Type": "application/json"}
                assert (
                    await http.put("/api/v1/model-test", json=intent, headers=headers)
                ).status_code == 401
                http.cookies.set("omnis_session", grant.token)
                assert (
                    await http.put("/api/v1/model-test", json=intent, headers=headers)
                ).status_code == 403
                headers["X-CSRF-Token"] = grant.csrf
                assert not received  # Save, boot and read never refresh implicitly.
                assert (await http.get("/api/v1/model-test")).status_code == 200
                refused = await http.put("/api/v1/model-test", json=intent, headers=headers)
                assert refused.status_code == 409 and not received
                if scenario == "complete":
                    before_commands = len(commands)
                    async with engine.connect() as db:
                        before_rows = (
                            await db.execute(
                                text(
                                    "SELECT (SELECT count(*) FROM model_record_v2), "
                                    "(SELECT count(*) FROM model_command_v2), "
                                    "(SELECT count(*) FROM system_operation), "
                                    "(SELECT count(*) FROM model_dispatch_v2), "
                                    "(SELECT count(*) FROM model_dispatch_event_v2)"
                                )
                            )
                        ).one()
                    for method, path, body in (
                        (
                            "POST",
                            "/api/v1/model-test/capabilities",
                            {
                                "command_id": str(uuid4()),
                                "expected_selection_revision": 1,
                            },
                        ),
                        (
                            "POST",
                            f"/api/v1/model-test/{operation}/cancel",
                            {
                                "command_id": str(uuid4()),
                                "expected_state_revision": 1,
                            },
                        ),
                        ("PUT", "/api/v1/model-test", intent),
                    ):
                        field = next(iter(body))
                        for invalid in ('"duplicate"', "NaN", "Infinity", "-Infinity"):
                            raw = (
                                "{" + json.dumps(field) + ":" + invalid + "," + json.dumps(body)[1:]
                            )
                            denied = await http.request(method, path, content=raw, headers=headers)
                            assert denied.status_code == 422, denied.text
                            assert len(commands) == before_commands and not received
                    async with engine.connect() as db:
                        assert (
                            await db.execute(
                                text(
                                    "SELECT (SELECT count(*) FROM model_record_v2), "
                                    "(SELECT count(*) FROM model_command_v2), "
                                    "(SELECT count(*) FROM system_operation), "
                                    "(SELECT count(*) FROM model_dispatch_v2), "
                                    "(SELECT count(*) FROM model_dispatch_event_v2)"
                                )
                            )
                        ).one() == before_rows
                refresh_a = str(uuid4())
                refresh_intent = {"command_id": refresh_a, "expected_selection_revision": 1}
                refresh = await http.post(
                    "/api/v1/model-test/capabilities",
                    json=refresh_intent,
                    headers=headers,
                )
                assert refresh.status_code == 202
                async with asyncio.timeout(5):
                    while (await http.get("/api/v1/model-test")).json()[
                        "metadata_state"
                    ] == "PENDING":
                        await asyncio.sleep(0.02)
                receipt_a = (await http.get("/api/v1/model-test")).json()
                traffic = 2
                if scenario == "complete":
                    refresh_b = await http.post(
                        "/api/v1/model-test/capabilities",
                        json={"command_id": str(uuid4()), "expected_selection_revision": 1},
                        headers=headers,
                    )
                    assert refresh_b.status_code == 202
                    async with asyncio.timeout(5):
                        while owner.tasks:
                            await asyncio.sleep(0.02)
                    replay_a = await http.post(
                        "/api/v1/model-test/capabilities", json=refresh_intent, headers=headers
                    )
                    assert replay_a.status_code == 202 and replay_a.json() == receipt_a
                    read_a = await http.get("/api/v1/model-test/capabilities/" + refresh_a)
                    assert read_a.status_code == 200 and read_a.json() == receipt_a
                    assert (
                        await http.get("/api/v1/model-test/capabilities/" + str(uuid4()))
                    ).status_code == 404
                    changed = await http.post(
                        "/api/v1/model-test/capabilities",
                        json={**refresh_intent, "expected_selection_revision": 2},
                        headers=headers,
                    )
                    assert changed.status_code == 409 and len(received) == 2
                    traffic = 3
                admitted = await http.put("/api/v1/model-test", json=intent, headers=headers)
                assert admitted.status_code == 202, admitted.text
                async with asyncio.timeout(5):
                    while True:
                        result = await http.get("/api/v1/model-test/" + operation)
                        if result.json()["state"] == "FINISHED":
                            break
                        await asyncio.sleep(0.02)
                value = result.json()
                assert value["operation_id"] == operation
                assert (
                    value["result_state"] == "COMPLETED"
                    and value["response_text"] == "OMNIS_MODEL_TEST_OK"
                )
                if scenario.startswith("secret_"):
                    expected_model = (
                        ("x" * 250 if scenario == "secret_cross" else "") + "[REDACTED]"
                    )[:256]
                    assert value["observed_model"] == expected_model
                    async with engine.connect() as db:
                        stored = (
                            (await db.execute(text("SELECT payload FROM model_record_v2")))
                            .scalars()
                            .all()
                        )
                    retained = json.dumps(stored) + result.text
                    leaked = secret in retained or secret[:6] in retained
                    assert not leaked
                else:
                    assert value["observed_model"] == "fixture/observed"
                assert value["input_tokens"] == (
                    None
                    if scenario
                    in {"unknown_usage", "negative_usage", "unsafe_usage", "coerced_usage"}
                    else 9
                )
                assert value["output_tokens"] == (None if scenario == "unknown_usage" else 7)
                assert value["usage_state"] == (
                    "UNKNOWN"
                    if scenario == "unknown_usage"
                    else "PARTIAL"
                    if scenario
                    in {"negative_usage", "unsafe_usage", "coerced_usage", "invalid_reasoning"}
                    else "KNOWN"
                )
                assert value["cost_observed"] is None  # Unknown is not zero.
                assert value["reasoning_tokens"] is None
                assert not owner.settlement_failed and not owner.tasks
                if scenario in {
                    "negative_usage",
                    "unsafe_usage",
                    "coerced_usage",
                    "invalid_reasoning",
                }:
                    assert value["reason"] == "USAGE_INVALID"
                assert len(received) == traffic
                replay = await http.put("/api/v1/model-test", json=intent, headers=headers)
                assert replay.status_code == 202 and replay.json() == value
                conflict = await http.put(
                    "/api/v1/model-test",
                    json={**intent, "expected_selection_revision": 2},
                    headers=headers,
                )
                assert conflict.status_code == 409 and len(received) == traffic
                if scenario == "complete":
                    await settings.handle(
                        KeySettingsControl.model_validate(
                            {
                                "op": "provider_settings",
                                "request": {
                                    "action": "save_selection",
                                    "command_id": str(uuid4()),
                                    "expected_revision": 1,
                                    "default": {
                                        "connection_id": connection_id,
                                        "connection_revision": 1,
                                        "model": "fixture/model",
                                        "output_tokens": 63,
                                    },
                                    "brain": None,
                                    "investigator": None,
                                    "validator": None,
                                },
                            }
                        )
                    )
                    assert (
                        await http.get("/api/v1/model-test/capabilities/" + refresh_a)
                    ).json() == receipt_a
                    assert (
                        await http.post(
                            "/api/v1/model-test/capabilities", json=refresh_intent, headers=headers
                        )
                    ).json() == receipt_a
                    value = (await http.get("/api/v1/model-test/" + operation)).json()
                    assert (
                        value["selection_revision"] == 2
                        and value["metadata_state"] == "NOT_REQUESTED"
                    )
                    assert len(received) == traffic
                if scenario.endswith("at_body"):
                    from omnis.supervisor.model_sender import Stream

                    paused, release = asyncio.Event(), asyncio.Event()
                    original_write = Stream.write

                    async def write(
                        stream: Stream, buffer: bytes, timeout: float | None = None
                    ) -> None:
                        if buffer.startswith(b"{"):
                            paused.set()
                            await release.wait()
                        await original_write(stream, buffer, timeout)

                    monkeypatch.setattr(Stream, "write", write)
                    second_id = str(uuid4())
                    second = await http.put(
                        "/api/v1/model-test",
                        json={**intent, "operation_id": second_id},
                        headers=headers,
                    )
                    assert second.status_code == 202
                    await asyncio.wait_for(paused.wait(), 3)
                    if scenario == "stop_at_body":
                        await service.shutdown(uuid4(), generation, process, epoch)
                    elif scenario == "revoke_at_body":
                        await settings.handle(
                            KeySettingsControl.model_validate(
                                {
                                    "op": "provider_settings",
                                    "request": {
                                        "action": "revoke_connection",
                                        "command_id": str(uuid4()),
                                        "connection_id": connection_id,
                                        "expected_revision": 1,
                                    },
                                }
                            )
                        )
                    else:
                        before = (await http.get("/api/v1/model-test/" + second_id)).json()
                        cancelled = await http.post(
                            "/api/v1/model-test/" + second_id + "/cancel",
                            json={
                                "command_id": str(uuid4()),
                                "expected_state_revision": before["state_revision"],
                            },
                            headers=headers,
                        )
                        assert cancelled.status_code == 202
                    release.set()
                    async with asyncio.timeout(4):
                        while (after := (await http.get("/api/v1/model-test/" + second_id)).json())[
                            "state"
                        ] != "FINISHED":
                            await asyncio.sleep(0.02)
                    assert after["result_state"] == "UNKNOWN"
                    assert after["usage_state"] == "UNKNOWN" and after["cost_observed"] is None
                    assert (
                        len(received) == traffic
                    )  # Reused TLS headers can arrive; no second body.
                if scenario != "stop_at_body":
                    await service.shutdown(uuid4(), generation, process, epoch)
                await service.quiesce(process, epoch)
                assert (await http.get("/api/v1/model-test/" + operation)).json() == value
                assert len(received) == traffic
                async with engine.connect() as db:
                    assert (
                        await db.execute(
                            text("SELECT count(*) FROM model_dispatch_event_v2 WHERE state='SENT'")
                        )
                    ).scalar_one() == (2 if scenario.endswith("at_body") else 1)
                    assert (
                        await db.execute(text("SELECT count(*) FROM system_operation"))
                    ).scalar_one() == (2 if scenario.endswith("at_body") else 1)
                if scenario == "complete":
                    await service.release(process, epoch)
                    released = True
                    script = """
import asyncio,json,sys
from pathlib import Path
config=json.loads(sys.stdin.buffer.read())
sys.path.insert(0, config["source"])
from uuid import uuid4
from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from omnis.modules.settings.provider_vault import ProviderVault
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from omnis.modules.runs.model_test_runtime import ApiKeyModelTest
from omnis.modules.runs.model_test_models import ModelTestControl
from omnis.supervisor.model_sender import ModelSender
async def main():
    engine=database_engine(config["database"])
    service=InstanceService(engine)
    owner=uuid4()
    epoch=await service.acquire(owner)
    status=await service.owned_status(owner,epoch)
    settings=ProviderSettingsOwner(service,owner,epoch,ProviderVault(Path(config["vault"]),Path(config["keys"]),str(status.instance_id)))
    sender=ModelSender(Path(config["socket"]))
    runtime=ApiKeyModelTest(settings,sender)
    try:
        await runtime.reconcile()
        view=await runtime.handle(ModelTestControl(op="model_test",action="start",operation_id=config["operation"],expected_selection_revision=1,consent=True))
        replay=await runtime.handle(ModelTestControl(op="model_test",action="refresh",command_id=config["refresh"],expected_selection_revision=1))
        read=await runtime.handle(ModelTestControl(op="model_test",action="read",command_id=config["refresh"]))
        assert replay == read == config["receipt"]
        print(json.dumps(view))
    finally:
        await runtime.drain()
        await sender.close()
        await service.release(owner,epoch)
        await engine.dispose()
asyncio.run(main())
"""
                    child = await asyncio.to_thread(
                        subprocess.run,
                        [sys.executable, "-I", "-B", "-c", script],
                        input=json.dumps(
                            {
                                "source": str(Path(__file__).resolve().parents[1] / "src"),
                                "database": migrated_database_url.render_as_string(
                                    hide_password=False
                                ),
                                "vault": str(vault_dir),
                                "keys": str(keys),
                                "socket": str(socket),
                                "operation": operation,
                                "refresh": refresh_a,
                                "receipt": receipt_a,
                            }
                        ).encode(),
                        cwd=tmp_path,
                        env={"PATH": os.environ["PATH"], "TMPDIR": os.environ["TMPDIR"]},
                        capture_output=True,
                        timeout=15,
                    )
                    assert child.returncode == 0
                    assert json.loads(child.stdout) == value
                    assert (
                        len(received) == traffic
                    )  # A new OS process and fencing owner read/replay only.
    finally:
        await owner.drain()
        await sender.close()
        server.close()
        await server.wait_closed()
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks), 2)
        if not released:
            await service.release(process, epoch)
        await engine.dispose()
    assert not socket.exists() and not tasks
