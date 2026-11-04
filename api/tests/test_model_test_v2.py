"""Real paired API/private control/PG/public SDK, owned UDS TLS protocol fixture only."""

import asyncio
import json
import os
import socket as network_socket
import ssl
import subprocess
import sys
import threading
from collections.abc import AsyncIterator
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.api import create_app
from omnis.core.db import database_engine
from omnis.modules.instance.service import InstanceService
from omnis.modules.runs import model_test_operation
from omnis.modules.runs.model_test_models import ModelTestControl
from omnis.modules.settings.provider_catalog_models import CatalogControl
from omnis.modules.settings.provider_key_models import KeySettingsControl
from omnis.modules.settings.provider_key_service import ProviderSettingsOwner
from omnis.modules.settings.provider_model_models import ModelRegistryControl
from omnis.modules.settings.provider_vault import ProviderVault
from omnis.security.sessions import SessionStore, code_digest
from omnis.transport.local_control import LocalControl


def test_production_consumer_exists() -> None:
    assert hasattr(model_test_operation, "ApiKeyModelTest"), "T1 production consumer missing"


def cancel_observation(command: ModelTestControl, observed: dict[str, object]) -> dict[str, object]:
    assert command.op == "entry_model_test" and command.action == "cancel"
    assert observed["operation_id"] == command.operation_id
    return {
        "operation_id": command.operation_id,
        "requested_revision": command.expected_state_revision,
        "observed_state": observed["state"],
        "observed_revision": observed["state_revision"],
    }


def test_cancel_observation_source() -> None:
    identity = str(uuid4())
    command = ModelTestControl(
        op="entry_model_test",
        action="cancel",
        operation_id=identity,
        command_id=str(uuid4()),
        expected_state_revision=1,
    )
    observed: dict[str, object] = {
        "operation_id": identity,
        "state": "RUNNING",
        "state_revision": 2,
        "response_text": "not retained",
    }
    assert cancel_observation(command, observed) == {
        "operation_id": identity,
        "requested_revision": 1,
        "observed_state": "RUNNING",
        "observed_revision": 2,
    }
    assert (
        cancel_observation(command.model_copy(update={"expected_state_revision": 2}), observed)[
            "requested_revision"
        ]
        == 2
    )
    with pytest.raises(AssertionError):
        cancel_observation(command, {**observed, "operation_id": str(uuid4())})
    with pytest.raises(AssertionError):
        cancel_observation(command.model_copy(update={"op": "model_test"}), observed)


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
        "entry_catalog",
        "entry_remove",
        pytest.param(
            "entry_remove_ui",
            marks=pytest.mark.skipif(
                os.environ.get("OMNIS_SETTINGS_REMOVE_UI") != "1",
                reason="Explicit narrow Remove built-browser fixture only",
            ),
        ),
        pytest.param(
            "entry_stop_read_ui",
            marks=pytest.mark.skipif(
                os.environ.get("OMNIS_SETTINGS_STOP_READ_UI") != "1",
                reason="Explicit one-operation Stop then readback fixture only",
            ),
        ),
        "entry_generation_before_first",
        "entry_generation_between",
        "entry_generation_unchanged",
        pytest.param(
            "settings_ui",
            marks=pytest.mark.skipif(
                os.environ.get("OMNIS_SETTINGS_MODELS_UI") != "1",
                reason="Explicit built Settings browser fixture only",
            ),
        ),
        pytest.param(
            "settings_cancel_ui",
            marks=pytest.mark.skipif(
                os.environ.get("OMNIS_SETTINGS_CANCEL_UI") != "1",
                reason="Explicit one-operation Cancel diagnostic only",
            ),
        ),
        pytest.param(
            "settings_cancel_current_ui",
            marks=pytest.mark.skipif(
                os.environ.get("OMNIS_SETTINGS_CANCEL_UI") != "1",
                reason="Explicit one-operation current-revision Cancel control only",
            ),
        ),
        "unknown_usage",
        "negative_usage",
        "unsafe_usage",
        "coerced_usage",
        "invalid_reasoning",
        "secret_long",
        "secret_cross",
        "metadata_refused",
        "metadata_eof",
        "stop_at_body",
        "revoke_at_body",
        "cancel_at_body",
        "relay_cancel_dns",
        "relay_cancel_connect",
        "relay_revoke_dns",
        "relay_stop_dns",
        "relay_expiry_connect",
        "relay_expiry_write",
        "settlement_before_cancel",
    ],
)
async def test_api_pg_sdk_protocol_and_replay(
    migrated_database_url: URL,
    ipc_directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    entry_scenario = scenario.startswith("entry_")
    stop_read = scenario == "entry_stop_read_ui"
    stop_reads: list[dict[str, object]] = []
    peer_completed: list[str] = []
    cancel_probe = scenario in {"settings_cancel_ui", "settings_cancel_current_ui"}
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
    if scenario != "settings_ui":
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
    if not entry_scenario and scenario != "settings_ui" and not cancel_probe:
        await settings.handle(
            ModelRegistryControl.model_validate(
                {
                    "op": "provider_models",
                    "request": {
                        "action": "save_models",
                        "command_id": str(uuid4()),
                        "expected_registry_revision": 0,
                        "connection_id": connection_id,
                        "connection_revision": 1,
                        "models": [
                            {
                                "entry_id": str(uuid4()),
                                "expected_revision": 0,
                                "model": "fixture/model",
                                "output_tokens": 128,
                            }
                        ],
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
    ui_writes: list[tuple[str, int]] = []
    ui_refreshes: list[int] = []
    ui_starts: list[int] = []
    ui_admitted: list[str] = []
    ui_key_command: str | None = None
    ui_key_receipt = False
    tasks: set[asyncio.Task[None]] = set()
    metadata_outage = scenario in {"metadata_refused", "metadata_eof"}
    catalog_mode = "complete"
    catalog_entered, catalog_release = asyncio.Event(), asyncio.Event()
    remove_peer_release = asyncio.Event()
    remove_peer_release.set()
    ui_model_entered, ui_model_release = asyncio.Event(), asyncio.Event()
    cancel_observations: list[dict[str, object]] = []

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
                if (scenario == "settings_ui" or cancel_probe or stop_read) and (
                    b"Authorization: Bearer " + secret.encode() + b"\r\n" not in headers
                ):
                    raise AssertionError("Owned peer authentication mismatch")
                if scenario == "entry_catalog" and catalog_mode == "wait":
                    catalog_entered.set()
                    await catalog_release.wait()
                if metadata_outage:
                    return  # Real TLS peer EOF before any response bytes.
                if (
                    entry_scenario or scenario == "settings_ui" or cancel_probe
                ) and first.startswith("GET /api/v1/models?"):
                    offset = 0 if "offset=0&" in first else 16
                    assert first == f"GET /api/v1/models?offset={offset}&limit=1000 HTTP/1.1"
                    rows = (
                        [
                            {
                                "id": f"fixture/{i:02}",
                                "name": f"Synthetic model {i}",
                                "supported_parameters": ["max_tokens"],
                                "top_provider": {"max_completion_tokens": 128},
                            }
                            for i in range(16)
                        ]
                        if offset == 0
                        else [
                            {
                                "id": "fixture/selected",
                                "name": "Selected exact model",
                                "supported_parameters": ["max_tokens"],
                                "top_provider": {"max_completion_tokens": 128},
                            }
                        ]
                    )
                    next_url = "/api/v1/models?offset=16&limit=1000" if offset == 0 else None
                    if catalog_mode == "foreign":
                        next_url = "https://foreign.invalid/models?offset=16&limit=1000"
                    elif catalog_mode == "loop":
                        next_url = "/api/v1/models?offset=0&limit=1000"
                    payload: dict[str, object] = {
                        "data": rows,
                        "links": {"next": next_url},
                        "total_count": 17,
                    }
                    if scenario == "settings_ui":
                        payload["data"] = [
                            {
                                "id": f"fixture/{i:02}",
                                "name": f"Synthetic model {i}",
                                "supported_parameters": ["max_tokens"],
                                "top_provider": {"max_completion_tokens": 128},
                            }
                            for i in range(offset, offset + 16)
                        ]
                        payload["total_count"] = 32
                    if cancel_probe:
                        assert offset == 0
                        payload = {
                            "data": [
                                {
                                    "id": "fixture/model",
                                    "supported_parameters": ["max_tokens"],
                                    "top_provider": {"max_completion_tokens": 128},
                                }
                            ],
                            "links": {"next": None},
                            "total_count": 1,
                        }
                    if catalog_mode == "unknown":
                        payload.pop("total_count")
                        payload["links"] = {"next": None}
                elif first == "GET /api/v1/models HTTP/1.1":
                    payload = {
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
                    if cancel_probe:
                        ui_model_entered.set()
                        await ui_model_release.wait()
                    if scenario in {"entry_remove", "entry_remove_ui"}:
                        await remove_peer_release.wait()
                    if scenario == "settings_ui":
                        assert data["model"] in {"fixture/02", "fixture/03"}
                    elif scenario.startswith("entry_generation_"):
                        assert data["model"] in {"fixture/selected", "fixture/00"}
                    elif stop_read:
                        assert data["model"] == "fixture/01"
                    elif scenario == "entry_remove_ui":
                        assert data["model"] in {"fixture/selected", "fixture/01"}
                    else:
                        assert data["model"] == (
                            "fixture/selected"
                            if scenario in {"entry_catalog", "entry_remove"}
                            else "fixture/model"
                        )
                    assert data["max_tokens"] == 64
                    assert data["provider"] == {
                        "allow_fallbacks": False,
                        "require_parameters": True,
                    }
                    payload = {
                        "id": "synthetic-protocol-not-provider-live",
                        "object": "chat.completion",
                        "created": 0,
                        "model": data["model"]
                        if scenario in {"settings_ui", "entry_remove_ui", "entry_stop_read_ui"}
                        else "fixture/observed",
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
                if stop_read and first.startswith("POST"):
                    peer_completed.append("fixture/01")
        except ConnectionError:
            return  # Catalog Cancel deliberately closes the authenticated synthetic peer.
        finally:
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()
            tasks.discard(task)

    import importlib

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cli/src"))
    start_relay = importlib.import_module("omnis_cli.forwarder").start_auth_forwarder
    relay_directory = ipc_directory / "r"
    relay_directory.mkdir(mode=0o700)
    relay = await start_relay(relay_directory, model=True)
    socket = relay_directory / "model-egress.sock"
    server = await asyncio.start_server(serve, "127.0.0.1", 0, ssl=server_context)
    address = server.sockets[0].getsockname()
    original_connect = asyncio.get_running_loop().sock_connect
    original_send = network_socket.socket.send
    physical_phase = ""
    physical_entered, physical_release = threading.Event(), threading.Event()
    connected: list[object] = []
    handed: list[int] = []
    upstream_sockets: list[network_socket.socket] = []

    def controlled_dns(
        host: str, port: int, family: int = 0, type: int = 0, proto: int = 0, flags: int = 0
    ) -> list[tuple[object, ...]]:
        assert family in (0, network_socket.AF_INET) and type in (0, network_socket.SOCK_STREAM)
        assert proto in (0, network_socket.IPPROTO_TCP) and flags == 0
        if (
            scenario in {"settings_ui", "entry_remove_ui", "entry_stop_read_ui"} or cancel_probe
        ) and host == "127.0.0.1":
            assert 0 < port <= 65535
            return [
                (
                    network_socket.AF_INET,
                    network_socket.SOCK_STREAM,
                    network_socket.IPPROTO_TCP,
                    "",
                    (host, port),
                )
            ]
        assert host == "openrouter.ai" and port == 443
        if physical_phase == "dns":
            physical_entered.set()
            if not physical_release.wait(2):
                raise OSError("owned DNS fixture deadline")
        return [
            (
                network_socket.AF_INET,
                network_socket.SOCK_STREAM,
                network_socket.IPPROTO_TCP,
                "",
                ("8.8.8.8", 443),
            )
        ]

    async def controlled_connect(
        sock: network_socket.socket, destination: str | tuple[object, ...]
    ) -> None:
        if sock.family == network_socket.AF_UNIX:
            await original_connect(sock, destination)
        else:
            assert destination == ("8.8.8.8", 443)
            upstream_sockets.append(sock)
            if physical_phase == "connect":
                physical_entered.set()
                while not physical_release.is_set():
                    await asyncio.sleep(0.01)
            await original_connect(sock, address)
            connected.append(address)

    def controlled_send(sock: network_socket.socket, data: bytes, flags: int = 0) -> int:
        size = original_send(sock, data, flags)
        if any(sock is upstream for upstream in upstream_sockets):
            handed.append(size)
        return size

    monkeypatch.setattr(network_socket.socket, "send", controlled_send)
    dns_patch = patch.object(network_socket, "getaddrinfo", controlled_dns)
    connect_patch = patch.object(asyncio.get_running_loop(), "sock_connect", controlled_connect)
    dns_patch.start()
    connect_patch.start()
    if scenario == "metadata_refused":
        server.close()
        await server.wait_closed()
    sender = ModelSender(socket, client_context)
    from omnis.supervisor.model_relay_protocol import Scope, decode, encode, utc, validate

    model_opens: list[tuple[Scope, str]] = []
    model_writes: list[tuple[Scope, str, int, str]] = []
    fence_acks: list[tuple[str, Scope]] = []
    original_rpc = sender.transport.backend.relay.rpc

    async def model_rpc(
        action: str,
        scope: Scope,
        connection: str | None = None,
        sequence: int = 0,
        data: bytes = b"",
        size: int = 0,
        timeout: float = 1,
        write_deadline: str | None = None,
        retire_through: int | None = None,
    ) -> tuple[str, bytes]:
        if action == "OPEN" and scope.kind == "MODEL_DISPATCH":
            assert write_deadline is not None
            model_opens.append((scope, write_deadline))
        if action == "WRITE" and scope.kind == "MODEL_DISPATCH":
            if physical_phase == "write":
                physical_entered.set()
                await asyncio.sleep(1)  # Expire local IPC/guard alone, never concurrent Cancel.
        reply = await original_rpc(
            action, scope, connection, sequence, data, size, timeout, write_deadline, retire_through
        )
        if action == "WRITE" and scope.kind == "MODEL_DISPATCH" and reply[0] == "OK":
            assert connection is not None and write_deadline is not None
            model_writes.append((scope, connection, sequence, write_deadline))
        if action in {"FENCE", "DRAIN"} and reply[0] == "OK":
            fence_acks.append((action, scope))
        return reply

    monkeypatch.setattr(sender.transport.backend.relay, "rpc", model_rpc)
    owner = ApiKeyModelTest(settings, sender)
    service.runtime_drain = owner.drain
    monkeypatch.setenv("OMNIS_CONTROL_DIR", str(control_dir))
    monkeypatch.setenv("OMNIS_HTTP_PORT", "8765")
    sessions = SessionStore(engine)
    await sessions.register(code_digest("synthetic-pairing"), issuance_id=uuid4())
    grant = await sessions.exchange("synthetic-pairing")
    released = False
    commands: list[ModelTestControl] = []
    heartbeat_stop = asyncio.Event()

    async def renew(owner_id: UUID, owner_epoch: int) -> None:
        if not entry_scenario and scenario != "settings_ui" and not cancel_probe:
            return
        while not heartbeat_stop.is_set():
            await service.heartbeat(owner_id, owner_epoch)
            try:
                await asyncio.wait_for(heartbeat_stop.wait(), 1)
            except TimeoutError:
                pass

    heartbeat = asyncio.create_task(renew(process, epoch))
    try:
        async with LocalControl(control_dir, service, process, epoch) as control:

            async def model_command(command: ModelTestControl) -> dict[str, object]:
                commands.append(command)
                if stop_read:
                    assert command.action in {"start", "read"}, "Stop continuation must not Cancel"
                    assert sum(c.action == "start" for c in commands) <= 1, "One Start; no retry"
                if cancel_probe and command.action == "start":
                    assert sum(c.action == "start" for c in commands) == 1, "One Start only"
                if cancel_probe and command.action == "cancel":
                    assert sum(c.action == "cancel" for c in commands) == 1, "One Cancel only"
                    await asyncio.wait_for(ui_model_entered.wait(), 3)
                    observed = await owner.view(command.operation_id, entry=True)
                    observation = cancel_observation(command, observed)
                    cancel_observations.append(observation)
                    print("CANCEL_PRE_HANDLE " + json.dumps(observation), flush=True)
                    if scenario == "settings_cancel_current_ui":
                        assert (
                            observation["requested_revision"]
                            == observation["observed_revision"]
                            == 2
                        )
                        assert observation["observed_state"] == "RUNNING"
                if scenario == "settings_ui" and command.action == "start":
                    ui_starts.append(len(received))
                    if ui_admitted:
                        previous = await owner.view(ui_admitted[-1], entry=True)
                        assert (
                            previous["state"] == "FINISHED"
                            and previous["result_state"] == "COMPLETED"
                        )
                try:
                    value = await owner.handle(command)
                    if stop_read:
                        stop_reads.append(
                            {
                                "action": command.action,
                                "requested_operation_id": command.operation_id,
                                "requested_entry_id": command.entry_id,
                                "requested_entry_revision": command.expected_entry_revision,
                                "requested_connection_revision": command.expected_connection_revision,
                                "workers_pending": len(owner.tasks),
                                "settlement_failed": owner.settlement_failed,
                                "peer_completed_models": list(peer_completed),
                                "response": {
                                    key: value.get(key)
                                    for key in (
                                        "operation_id",
                                        "entry_id",
                                        "entry_revision",
                                        "connection_id",
                                        "connection_revision",
                                        "current",
                                        "state",
                                        "state_revision",
                                        "result_state",
                                        "finish_reason",
                                        "requested_model",
                                        "requested_output_tokens",
                                    )
                                },
                            }
                        )
                    if (scenario == "settings_ui" or cancel_probe) and command.action == "start":
                        assert command.operation_id is not None
                        ui_admitted.append(command.operation_id)
                    return value
                except ValidationError as error:
                    print(error.errors(include_input=False, include_url=False))
                    raise
                finally:
                    if cancel_probe and command.action == "cancel":
                        ui_model_release.set()

            control.model_test = model_command

            async def catalog_command(command: CatalogControl) -> dict[str, object]:
                if scenario == "settings_ui" and command.request.action == "refresh":
                    assert ui_key_receipt, "Explicit catalog must follow exact local key receipt"
                    ui_refreshes.append(len(received))
                return await owner.catalog_handle(command)

            control.provider_catalog = catalog_command

            async def provider_command(
                command: KeySettingsControl | ModelRegistryControl,
            ) -> dict[str, object]:
                nonlocal ui_key_command, ui_key_receipt
                before_io = len(received)
                if scenario == "settings_ui":
                    request = command.request
                    if request.action != "read":
                        ui_writes.append((request.action, before_io))
                    if request.action == "save_connection":
                        ui_key_command = request.command_id
                result = await settings.handle(command)
                if (
                    scenario == "settings_ui"
                    and isinstance(command, KeySettingsControl)
                    and command.request.action == "read"
                    and command.request.command_id is not None
                    and command.request.command_id == ui_key_command
                ):
                    ui_key_receipt = True
                return result.model_dump(mode="json")

            control.provider_settings = provider_command

            if stop_read:
                from test_web_e2e import settings_models_browser

                assert not received and not owner.tasks, "Fresh fixture must be inert"
                try:
                    await settings_models_browser(
                        migrated_database_url, control_dir, tmp_path, scenario="settings-stop-read"
                    )
                    async with asyncio.timeout(15):
                        while owner.tasks:
                            await asyncio.sleep(0.01)
                finally:
                    witness = {
                        "commands": [
                            {
                                "action": c.action,
                                "operation_id": c.operation_id,
                                "entry_id": c.entry_id,
                            }
                            for c in commands
                        ],
                        "reads": stop_reads,
                        "peer_requests": [first for first, _ in received],
                        "peer_completed_models": peer_completed,
                        "peer_handlers": len(tasks),
                        "workers": [
                            {"done": t.done(), "cancelled": t.cancelled()} for t in owner.tasks
                        ],
                        "settlement_failed": owner.settlement_failed,
                    }
                    # This runs before the fixture's drain, including a browser assertion failure.
                    (tmp_path / "settings-stop-read-owner.json").write_text(
                        json.dumps(witness, indent=2)
                    )
                    print("SETTINGS_STOP_READ_OWNER " + json.dumps(witness), flush=True)
                assert [c.action for c in commands if c.action != "read"] == ["start"]
                assert [first for first, _ in received] == [
                    "GET /api/v1/models?offset=0&limit=1000 HTTP/1.1",
                    "GET /api/v1/models?offset=16&limit=1000 HTTP/1.1",
                    "POST /api/v1/chat/completions HTTP/1.1",
                ]
                assert peer_completed == ["fixture/01"]
                assert not owner.tasks and not owner.settlement_failed
                browser = json.loads((tmp_path / "settings-stop-read.json").read_text())
                start = next(c for c in commands if c.action == "start")
                assert start.operation_id == browser["exact"]["operation_id"]
                assert start.entry_id == browser["exact"]["entry_id"]
                assert start.expected_generation == generation
                exact = await owner.view(start.operation_id, entry=True)
                latest = await owner.handle(
                    ModelTestControl(
                        op="entry_model_test",
                        action="read",
                        entry_id=start.entry_id,
                    )
                )
                assert latest == exact
                for key, value in browser["exact"].items():
                    if key != "status":
                        assert exact[key] == value, key
                assert exact["state"] == "FINISHED" and exact["state_revision"] == 3
                assert exact["result_state"] == exact["finish_reason"] == "COMPLETED"
                assert exact["current"] is True
                assert exact["entry_revision"] == exact["connection_revision"] == 1
                assert (
                    exact["requested_model"] == "fixture/01"
                    and exact["requested_output_tokens"] == 64
                )
                async with engine.connect() as db:
                    assert (await settings.selection(db)) is None
                    assert (
                        await db.execute(text("SELECT count(*) FROM provider_model_entry"))
                    ).scalar_one() == 2
                    assert (
                        await db.execute(text("SELECT count(*) FROM system_operation"))
                    ).scalar_one() == 1
                    assert (
                        await db.execute(
                            text("SELECT count(*) FROM model_dispatch_event_v2 WHERE state='SENT'")
                        )
                    ).scalar_one() == 1
                return

            if cancel_probe:
                from test_web_e2e import settings_models_browser

                await settings.handle(
                    ModelRegistryControl.model_validate(
                        {
                            "op": "provider_models",
                            "request": {
                                "action": "save_models",
                                "command_id": str(uuid4()),
                                "expected_registry_revision": 0,
                                "connection_id": connection_id,
                                "connection_revision": 1,
                                "models": [
                                    {
                                        "entry_id": str(uuid4()),
                                        "expected_revision": 0,
                                        "model": "fixture/model",
                                        "output_tokens": 64,
                                    }
                                ],
                            },
                        }
                    )
                )
                # One owned TLS metadata prerequisite; no browser Refresh or catalog cycle.
                await owner.catalog_handle(
                    CatalogControl.model_validate(
                        {
                            "op": "provider_catalog",
                            "request": {
                                "action": "refresh",
                                "command_id": str(uuid4()),
                                "connection_id": connection_id,
                                "connection_revision": 1,
                            },
                        }
                    )
                )
                async with asyncio.timeout(15):
                    while owner.tasks:
                        await asyncio.sleep(0.01)
                assert [first for first, _ in received] == [
                    "GET /api/v1/models?offset=0&limit=1000 HTTP/1.1"
                ]
                async with asyncio.timeout(120):
                    await settings_models_browser(
                        migrated_database_url,
                        control_dir,
                        tmp_path,
                        scenario=(
                            "settings-cancel-current"
                            if scenario == "settings_cancel_current_ui"
                            else "settings-cancel-probe"
                        ),
                    )
                assert len(ui_admitted) == len(cancel_observations) == 1
                assert [c.action for c in commands if c.action != "read"] == ["start", "cancel"]
                assert [first for first, _ in received] == [
                    "GET /api/v1/models?offset=0&limit=1000 HTTP/1.1",
                    "POST /api/v1/chat/completions HTTP/1.1",
                ]
                async with engine.connect() as db:
                    assert (await settings.selection(db)) is None
                    assert (
                        await db.execute(text("SELECT count(*) FROM system_operation"))
                    ).scalar_one() == 1
                    assert (
                        await db.execute(text("SELECT count(*) FROM provider_model_entry"))
                    ).scalar_one() == 1
                return

            if scenario == "settings_ui":
                from test_web_e2e import settings_models_browser

                assert not received, "Boot must not contact a provider"
                async with asyncio.timeout(300):
                    await settings_models_browser(migrated_database_url, control_dir, tmp_path)
                assert [first for first, _ in received] == [
                    "GET /api/v1/models?offset=0&limit=1000 HTTP/1.1",
                    "GET /api/v1/models?offset=16&limit=1000 HTTP/1.1",
                    "GET /api/v1/models?offset=0&limit=1000 HTTP/1.1",
                    "GET /api/v1/models?offset=16&limit=1000 HTTP/1.1",
                    "GET /api/v1/models?offset=0&limit=1000 HTTP/1.1",
                    "GET /api/v1/models?offset=16&limit=1000 HTTP/1.1",
                    "POST /api/v1/chat/completions HTTP/1.1",
                    "POST /api/v1/chat/completions HTTP/1.1",
                ]
                assert ui_refreshes == [0, 2, 4, 8]
                assert ui_starts == [6, 7, 8]
                assert len(set(ui_admitted)) == 2
                assert [
                    json.loads(body)["model"]
                    for first, body in received
                    if first.startswith("POST")
                ] == ["fixture/02", "fixture/03"]
                assert ui_writes == [
                    ("save_connection", 0),
                    ("save_models", 2),
                    ("save_selection_v2", 2),
                    ("save_selection", 2),
                    ("save_selection_v2", 2),
                    ("save_models", 4),
                    ("save_models", 6),
                    ("save_selection_v2", 8),
                    ("revoke_connection", 8),
                ]
                async with engine.connect() as db:
                    assert (
                        await db.execute(text("SELECT count(*) FROM provider_model_entry"))
                    ).scalar_one() == 32
                    assert (
                        await db.execute(
                            text("SELECT count(*) FROM model_dispatch_event_v2 WHERE state='SENT'")
                        )
                    ).scalar_one() == 2
                    rows = (
                        await db.execute(
                            text(
                                "SELECT operation_id::text,outcome_ref FROM system_operation ORDER BY deadline"
                            )
                        )
                    ).all()
                    assert [row[0] for row in rows] == ui_admitted
                    assert len({row[1]["id"] for row in rows}) == 2
                    selected = await settings.selection(db)
                    assert selected is not None and selected.brain is not None
                    assert (
                        selected.revision == 3
                        and selected.default.output_tokens == 64
                        and selected.default.model == "fixture/00"
                        and selected.brain.model == "fixture/01"
                        and selected.brain.output_tokens == 37
                    )
                    assert not (await settings.connections(db))[0].enabled
                for identity in ui_admitted:
                    historical = await owner.view(identity, entry=True)
                    latest = await owner.handle(
                        ModelTestControl(
                            op="entry_model_test",
                            action="read",
                            entry_id=str(historical["entry_id"]),
                        )
                    )
                    assert latest == historical and latest["current"] is False
                    assert latest["state"] == "FINISHED" and latest["result_state"] == "COMPLETED"
                return

            async def stop_control() -> None:
                reader, writer = await asyncio.open_unix_connection(control_dir / "control.sock")
                try:
                    writer.write(
                        json.dumps(
                            {
                                "version": 1,
                                "capability": (control_dir / "control.cap").read_text(),
                                "command": {
                                    "op": "shutdown",
                                    "command_id": str(uuid4()),
                                    "instance_id": str(initial.instance_id),
                                    "expected_generation": generation,
                                },
                            }
                        ).encode()
                        + b"\n"
                    )
                    await writer.drain()
                    stopped = json.loads(await reader.readline())
                    assert stopped["ok"] is True, stopped
                    assert stopped["status"]["admission_open"] is False
                    await service.quiesce(process, epoch)  # Actual Supervisor heartbeat consumer.
                finally:
                    writer.close()
                    await writer.wait_closed()

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
                if entry_scenario:
                    catalog_path = "/api/v1/settings/provider-catalog"
                    context = {"connection_id": connection_id, "connection_revision": 1}
                    search = {"action": "search", **context}
                    assert (await http.get("/api/v1/settings/providers")).json()[
                        "selection"
                    ] is None
                    empty = await http.post(catalog_path + "/search", json=search, headers=headers)
                    assert empty.status_code == 200 and empty.json()["state"] == "NOT_REQUESTED"
                    assert not received
                    ids = [str(uuid4()) for _ in range(3)]
                    if scenario == "entry_remove_ui":
                        ids[0] = "ffffffff-ffff-4fff-bfff-ffffffffffff"
                    saved = await http.put(
                        "/api/v1/settings/models",
                        headers=headers,
                        json={
                            "action": "save_models",
                            "command_id": str(uuid4()),
                            "expected_registry_revision": 0,
                            **context,
                            "models": [
                                {
                                    "entry_id": ids[0],
                                    "expected_revision": 0,
                                    "model": "fixture/selected",
                                    "output_tokens": 64,
                                },
                                {
                                    "entry_id": ids[1],
                                    "expected_revision": 0,
                                    "model": "fixture/00",
                                    "output_tokens": 129 if scenario == "entry_catalog" else 64,
                                },
                                {
                                    "entry_id": ids[2],
                                    "expected_revision": 0,
                                    "model": "manual/model",
                                    "output_tokens": 64,
                                },
                            ],
                        },
                    )
                    assert saved.status_code == 200 and not received
                    catalog_id = str(uuid4())
                    refresh_body = {"action": "refresh", "command_id": catalog_id, **context}
                    refreshed = await http.post(
                        catalog_path + "/refresh", json=refresh_body, headers=headers
                    )
                    assert refreshed.status_code == 202
                    async with asyncio.timeout(5):
                        while owner.tasks:
                            await asyncio.sleep(0.02)
                    first = await http.post(
                        catalog_path + "/search",
                        json={**search, "catalog_command_id": catalog_id},
                        headers=headers,
                    )
                    assert first.status_code == 200, first.text
                    assert first.json()["state"] == "READY" and first.json()["total"] == 17
                    assert len(first.json()["entries"]) == 16 and first.json()["next_offset"] == 16
                    second = await http.post(
                        catalog_path + "/search",
                        json={**search, "catalog_command_id": catalog_id, "offset": 16},
                        headers=headers,
                    )
                    assert second.status_code == 200 and [
                        x["model"] for x in second.json()["entries"]
                    ] == ["fixture/selected"]
                    assert second.json()["next_offset"] is None
                    if scenario in {"entry_remove", "entry_remove_ui"}:
                        models = "/api/v1/settings/models"
                        tests = "/api/v1/model-test/entries"
                        providers = "/api/v1/settings/providers"
                        tables = (
                            "provider_connection_revision",
                            "provider_settings_command",
                            "provider_selection_revision",
                            "provider_model_registry_revision",
                            "provider_model_entry",
                            "provider_model_entry_revision",
                            "provider_model_command",
                            "model_record_v2",
                            "model_command_v2",
                            "system_operation",
                            "system_operation_event",
                            "model_dispatch_v2",
                            "model_dispatch_event_v2",
                        )

                        async def census_remove() -> dict[str, list[str]]:
                            async with engine.connect() as db:
                                return {
                                    table: list(
                                        (
                                            await db.execute(
                                                text(
                                                    f"SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text"
                                                )
                                            )
                                        ).scalars()
                                    )
                                    for table in tables
                                }

                        entry_intent = {
                            "operation_id": str(uuid4()),
                            "entry_id": ids[0],
                            "expected_entry_revision": 1,
                            "expected_connection_revision": 1,
                            "catalog_command_id": catalog_id,
                            "expected_generation": generation,
                            "consent": True,
                        }
                        admitted = await http.put(tests, json=entry_intent, headers=headers)
                        assert admitted.status_code == 202
                        async with asyncio.timeout(5):
                            while owner.tasks:
                                await asyncio.sleep(0.02)
                        exact_path = tests + "/" + str(entry_intent["operation_id"])
                        latest_path = tests + "/latest/" + ids[0]
                        exact = (await http.get(exact_path)).json()
                        assert exact["state"] == "FINISHED" and exact["result_state"] == "COMPLETED"
                        assert (
                            exact["usage_state"] == "KNOWN"
                            and exact["input_tokens"] == 9
                            and exact["output_tokens"] == 7
                        )
                        if scenario == "entry_remove_ui":
                            extra = await http.put(
                                models,
                                headers=headers,
                                json={
                                    "action": "save_models",
                                    "command_id": str(uuid4()),
                                    "expected_registry_revision": 1,
                                    **context,
                                    "models": [
                                        {
                                            "entry_id": str(uuid4()),
                                            "expected_revision": 0,
                                            "model": f"fixture/extra-{i:02}",
                                            "output_tokens": 64,
                                        }
                                        for i in range(15)
                                    ],
                                },
                            )
                            assert extra.status_code == 200 and extra.json()["total"] == 18
                            assigned = await http.put(
                                providers,
                                headers=headers,
                                json={
                                    "action": "save_selection",
                                    "command_id": str(uuid4()),
                                    "expected_revision": 0,
                                    "default": {
                                        **context,
                                        "model": "fixture/00",
                                        "output_tokens": 64,
                                    },
                                    "brain": None,
                                    "investigator": None,
                                    "validator": None,
                                },
                            )
                            assert assigned.status_code == 200
                            from test_web_e2e import settings_models_browser

                            traffic = len(received)
                            assert traffic == 3  # Two catalog pages and the original saved test.
                            before_browser = await census_remove()
                            await settings_models_browser(
                                migrated_database_url,
                                control_dir,
                                tmp_path,
                                scenario="settings-remove",
                            )
                            assert [first for first, _ in received[traffic:]] == [
                                "GET /api/v1/models?offset=0&limit=1000 HTTP/1.1",
                                "GET /api/v1/models?offset=16&limit=1000 HTTP/1.1",
                                "GET /api/v1/models?offset=0&limit=1000 HTTP/1.1",
                                "GET /api/v1/models?offset=16&limit=1000 HTTP/1.1",
                                "GET /api/v1/models?offset=0&limit=1000 HTTP/1.1",
                                "GET /api/v1/models?offset=16&limit=1000 HTTP/1.1",
                                "POST /api/v1/chat/completions HTTP/1.1",
                                "POST /api/v1/chat/completions HTTP/1.1",
                                "GET /api/v1/models?offset=0&limit=1000 HTTP/1.1",
                                "GET /api/v1/models?offset=16&limit=1000 HTTP/1.1",
                            ]
                            calls = [
                                json.loads(body)
                                for first, body in received[traffic:]
                                if first.startswith("POST")
                            ]
                            assert [(call["model"], call["max_tokens"]) for call in calls] == [
                                ("fixture/01", 64),
                                ("fixture/selected", 64),
                            ]
                            browser = json.loads((tmp_path / "browser-result.json").read_text())[
                                "catalog"
                            ]
                            starts = [command for command in commands if command.action == "start"]
                            assert [
                                command.action for command in commands if command.action != "read"
                            ] == ["start", "start", "start"]
                            assert [command.operation_id for command in starts[1:]] == [
                                result["operation_id"] for result in browser["results"]
                            ]
                            assert len({command.operation_id for command in starts}) == 3
                            assert [command.expected_generation for command in starts] == [
                                generation
                            ] * 3
                            after_browser = await census_remove()
                            deltas = {
                                "provider_connection_revision": 2,
                                "provider_settings_command": 3,
                                "provider_selection_revision": 1,
                                "provider_model_registry_revision": 3,
                                "provider_model_entry": 2,
                                "provider_model_entry_revision": 2,
                                "provider_model_command": 3,
                                "model_command_v2": 6,
                                "system_operation": 2,
                                "system_operation_event": 6,
                                "model_dispatch_v2": 2,
                                "model_dispatch_event_v2": 6,
                            }
                            for table in tables:
                                if table in deltas:
                                    assert (
                                        len(after_browser[table])
                                        == len(before_browser[table]) + deltas[table]
                                    ), table
                                if table != "provider_model_entry":
                                    assert all(
                                        row in after_browser[table] for row in before_browser[table]
                                    ), f"Baseline changed: {table}"
                            before_entries = [
                                json.loads(row) for row in before_browser["provider_model_entry"]
                            ]
                            after_entries = [
                                json.loads(row) for row in after_browser["provider_model_entry"]
                            ]
                            for previous in before_entries:
                                expected = (
                                    {
                                        **previous,
                                        "removed_registry_revision": extra.json()[
                                            "registry_revision"
                                        ]
                                        + 1,
                                    }
                                    if previous["entry_id"] == ids[0]
                                    else previous
                                )
                                assert expected in after_entries
                            from collections import Counter

                            before_kinds = Counter(
                                json.loads(row)["kind"] for row in before_browser["model_record_v2"]
                            )
                            after_kinds = Counter(
                                json.loads(row)["kind"] for row in after_browser["model_record_v2"]
                            )
                            assert after_kinds == Counter(
                                {
                                    kind: count + 4
                                    if kind in {"catalog-request", "catalog-result"}
                                    else count * 3
                                    for kind, count in before_kinds.items()
                                }
                            )
                            assert (
                                browser["receipt"]["total"] == 17
                                and browser["readdEntries"] == 18
                                and browser["entries"] == 19
                            )
                            (tmp_path / "settings-controls-census.json").write_text(
                                json.dumps(
                                    {
                                        "boundary": "owned API/PG/TLS peer; no external provider",
                                        "before": {
                                            table: len(rows)
                                            for table, rows in before_browser.items()
                                        },
                                        "after": {
                                            table: len(rows)
                                            for table, rows in after_browser.items()
                                        },
                                        "operation_ids": [
                                            command.operation_id for command in starts
                                        ],
                                        "new_calls": [
                                            (call["model"], call["max_tokens"]) for call in calls
                                        ],
                                    },
                                    indent=2,
                                )
                            )
                            return
                        history = await census_remove()
                        settings_before = (await http.get(providers)).json()
                        remove = {
                            "action": "remove_model",
                            "command_id": str(uuid4()),
                            "expected_registry_revision": 1,
                            "entry_id": ids[0],
                            "expected_revision": 1,
                        }
                        retired = await http.put(models, json=remove, headers=headers)
                        assert retired.status_code == 200
                        receipt_path = models + "/commands/" + str(remove["command_id"])
                        receipt = retired.json()
                        archived = (await http.get(exact_path)).json()
                        assert archived == {**exact, "current": False}
                        assert (await http.get(latest_path)).json() == archived
                        removal_after = await census_remove()
                        for table in tables:
                            if table not in {
                                "provider_model_registry_revision",
                                "provider_model_entry",
                                "provider_model_command",
                            }:
                                assert removal_after[table] == history[table]
                        assert (await http.get(providers)).json() == settings_before
                        stale_save = {
                            "action": "save_models",
                            "command_id": str(uuid4()),
                            "expected_registry_revision": 2,
                            **context,
                            "models": [
                                {
                                    "entry_id": ids[0],
                                    "expected_revision": 0,
                                    "model": "fixture/selected",
                                    "output_tokens": 64,
                                }
                            ],
                        }
                        denied = await http.put(models, json=stale_save, headers=headers)
                        assert (
                            denied.status_code == 409
                            and denied.json()["error"]["code"] == "REVISION_CONFLICT"
                        )
                        assert await census_remove() == removal_after
                        new_id = str(uuid4())
                        readd = {
                            **stale_save,
                            "command_id": str(uuid4()),
                            "models": [
                                {
                                    "entry_id": new_id,
                                    "expected_revision": 0,
                                    "model": "fixture/selected",
                                    "output_tokens": 64,
                                }
                            ],
                        }
                        assert (
                            await http.put(models, json=readd, headers=headers)
                        ).status_code == 200
                        absent = await http.get(tests + "/latest/" + new_id)
                        assert (
                            absent.status_code == 404
                            and absent.json()["error"]["code"] == "NOT_FOUND"
                        )
                        assert (await http.get(providers)).json() == settings_before
                        from contextlib import asynccontextmanager

                        def unchanged_except_start(
                            before: dict[str, list[str]],
                            after: dict[str, list[str]],
                            identity: str,
                        ) -> None:
                            from omnis.modules.runs.model_test_contract import (
                                Dispatch,
                                Operation,
                                Ref,
                            )

                            instance = str(initial.instance_id)
                            records: set[tuple[str, str, str, int, str]] = set()
                            dispatches: set[str] = set()
                            for snapshot in (before, after):
                                roots = [json.loads(raw) for raw in snapshot["system_operation"]]
                                op = Operation.model_validate_json(
                                    json.dumps(
                                        next(
                                            row
                                            for row in roots
                                            if row["instance_id"] == instance
                                            and row["operation_id"] == identity
                                        )
                                    )
                                )
                                refs = [op.config_snapshot_ref, op.input_projection_ref]
                                if op.outcome_ref:
                                    refs.append(op.outcome_ref)
                                for raw in snapshot["model_dispatch_v2"]:
                                    row = json.loads(raw)
                                    if (
                                        row["instance_id"] == instance
                                        and row["operation_id"] == identity
                                    ):
                                        dispatch = Dispatch.model_validate_json(
                                            json.dumps(row["payload"])
                                        )
                                        assert (
                                            dispatch.dispatch_attempt_id
                                            == row["dispatch_attempt_id"]
                                        )
                                        dispatches.add(dispatch.dispatch_attempt_id)
                                        refs.extend(
                                            [
                                                dispatch.scope_ref,
                                                dispatch.dispatch_owner_ref,
                                                dispatch.config_snapshot_ref,
                                                dispatch.projection_ref,
                                                dispatch.reservation_ref,
                                            ]
                                        )
                                retained = [json.loads(raw) for raw in snapshot["model_record_v2"]]
                                while refs:
                                    ref = refs.pop()
                                    key = (
                                        ref.instance_id,
                                        ref.id,
                                        ref.kind,
                                        ref.revision,
                                        ref.digest,
                                    )
                                    if key in records:
                                        continue
                                    record = next(
                                        row
                                        for row in retained
                                        if (
                                            row["instance_id"],
                                            row["id"],
                                            row["kind"],
                                            row["revision"],
                                            row["digest"],
                                        )
                                        == key
                                    )
                                    records.add(key)
                                    # Follow only producer reference fields, never text occurring in payloads.
                                    fields = {
                                        "model-entry-snapshot-v1": ("capabilities_ref",),
                                        "model-entry-capabilities-v1": ("catalog_ref",),
                                        "system-operation": (
                                            "config_snapshot_ref",
                                            "input_projection_ref",
                                            "outcome_ref",
                                        ),
                                        "dispatch-owner-v2": ("scope_ref",),
                                        "model-permit-v2": ("scope_ref", "owner_ref", "config_ref"),
                                        "model-outcome-v2": (
                                            "operation_or_run_ref",
                                            "dispatch_ref",
                                            "requested",
                                            "output_ref",
                                        ),
                                        "model-dispatch-v2": (
                                            "scope_ref",
                                            "dispatch_owner_ref",
                                            "config_snapshot_ref",
                                            "projection_ref",
                                            "reservation_ref",
                                        ),
                                    }.get(ref.kind, ())
                                    refs.extend(
                                        Ref.model_validate(record["payload"][field])
                                        for field in fields
                                        if record["payload"].get(field) is not None
                                    )

                            for table in tables:
                                if table in {
                                    "model_record_v2",
                                    "model_command_v2",
                                    "system_operation_event",
                                    "model_dispatch_v2",
                                    "model_dispatch_event_v2",
                                }:
                                    assert set(before[table]).issubset(after[table]), table
                                foreign = []
                                for snapshot in (before, after):
                                    rows = []
                                    for raw in snapshot[table]:
                                        row = json.loads(raw)
                                        owned = False
                                        if row.get("instance_id") == instance:
                                            if table in {
                                                "system_operation",
                                                "system_operation_event",
                                            }:
                                                owned = row["operation_id"] == identity
                                            elif table == "model_command_v2":
                                                owned = (
                                                    row["operation_id"] == identity
                                                    and row["command_id"] == identity
                                                    and row["action"] == "start"
                                                )
                                            elif table in {
                                                "model_dispatch_v2",
                                                "model_dispatch_event_v2",
                                            }:
                                                owned = row["dispatch_attempt_id"] in dispatches
                                            elif table == "model_record_v2":
                                                owned = (
                                                    instance,
                                                    row["id"],
                                                    row["kind"],
                                                    row["revision"],
                                                    row["digest"],
                                                ) in records
                                        if not owned:
                                            rows.append(raw)
                                    foreign.append(rows)
                                assert foreign[0] == foreign[1], table

                        async def overlap(
                            first_path: str,
                            first_body: dict[str, object],
                            second_path: str,
                            second_body: dict[str, object],
                        ) -> str:
                            entered, release, arrived = (
                                asyncio.Event(),
                                asyncio.Event(),
                                asyncio.Event(),
                            )
                            original_admission = service.admission
                            original_settings, original_model = (
                                control.provider_settings,
                                control.model_test,
                            )
                            assert original_settings is not None and original_model is not None
                            armed = True
                            first_snapshot = None

                            @asynccontextmanager
                            async def gated(
                                expected: int, holder: UUID, fencing_epoch: int
                            ) -> AsyncIterator[AsyncConnection]:
                                nonlocal armed, first_snapshot
                                gate, armed = armed, False
                                async with original_admission(
                                    expected, holder, fencing_epoch
                                ) as db:
                                    if gate:
                                        entered.set()
                                        await asyncio.wait_for(release.wait(), 3)
                                    yield db
                                if gate:
                                    first_snapshot = await census_remove()

                            async def settings_arrival(
                                command: KeySettingsControl | ModelRegistryControl,
                            ) -> dict[str, object]:
                                if entered.is_set():
                                    arrived.set()
                                return await original_settings(command)

                            async def model_arrival(command: ModelTestControl) -> dict[str, object]:
                                if entered.is_set():
                                    arrived.set()
                                return await original_model(command)

                            monkeypatch.setattr(service, "admission", gated)
                            control.provider_settings, control.model_test = (
                                settings_arrival,
                                model_arrival,
                            )
                            one = asyncio.create_task(
                                http.put(first_path, json=first_body, headers=headers)
                            )
                            two = None
                            try:
                                await asyncio.wait_for(entered.wait(), 3)
                                two = asyncio.create_task(
                                    http.put(second_path, json=second_body, headers=headers)
                                )
                                await asyncio.wait_for(arrived.wait(), 3)
                                release.set()
                                results = await asyncio.gather(one, two)
                                assert results[0].status_code in (200, 202)
                                assert results[1].status_code in (404, 409)
                                if first_path != tests:
                                    assert await census_remove() == first_snapshot
                                else:
                                    assert first_snapshot is not None
                                    final_snapshot = await census_remove()
                                    identity = str(first_body["operation_id"])
                                    unchanged_except_start(first_snapshot, first_snapshot, identity)
                                    unchanged_except_start(first_snapshot, final_snapshot, identity)
                                    for table in tables:
                                        foreign = json.loads(
                                            (history[table] or first_snapshot[table])[0]
                                        )
                                        if table == "model_record_v2":
                                            # Historical catalog records may be shared by the new start.
                                            foreign["id"] = str(uuid4())
                                            foreign["payload"]["unrelated_bait"] = identity
                                        else:
                                            foreign["unrelated_bait"] = identity
                                        challenged = {
                                            **final_snapshot,
                                            table: [*final_snapshot[table], json.dumps(foreign)],
                                        }
                                        with pytest.raises(AssertionError, match=table):
                                            unchanged_except_start(
                                                first_snapshot, challenged, identity
                                            )
                                reason = results[1].json()["error"]["code"]
                                assert isinstance(reason, str)
                                return reason
                            finally:
                                release.set()
                                await asyncio.gather(
                                    *(task for task in (one, two) if task is not None),
                                    return_exceptions=True,
                                )
                                monkeypatch.setattr(service, "admission", original_admission)
                                control.provider_settings, control.model_test = (
                                    original_settings,
                                    original_model,
                                )

                        race_selection = {
                            "action": "save_selection",
                            "command_id": str(uuid4()),
                            "expected_revision": 0,
                            "default": {
                                **context,
                                "model": "fixture/selected",
                                "output_tokens": 64,
                            },
                            "brain": None,
                            "investigator": None,
                            "validator": None,
                        }
                        remove_new = {
                            **remove,
                            "command_id": str(uuid4()),
                            "entry_id": new_id,
                            "expected_registry_revision": 3,
                        }
                        assert (
                            await overlap(providers, race_selection, models, remove_new)
                            == "MODEL_IN_USE"
                        )
                        race_selection = {
                            **race_selection,
                            "command_id": str(uuid4()),
                            "expected_revision": 1,
                            "default": {**context, "model": "fixture/00", "output_tokens": 64},
                        }
                        assert (
                            await http.put(providers, json=race_selection, headers=headers)
                        ).status_code == 200
                        remove_peer_release.clear()
                        relay_before = (
                            len(model_opens),
                            len(model_writes),
                            len(connected),
                            len(handed),
                            len(received),
                        )
                        start_intent = {
                            **entry_intent,
                            "operation_id": str(uuid4()),
                            "entry_id": new_id,
                        }
                        assert (
                            await overlap(tests, start_intent, models, remove_new)
                            == "OPERATION_ACTIVE"
                        )
                        active_path = tests + "/" + str(start_intent["operation_id"])
                        active = (await http.get(active_path)).json()
                        cancel = await http.post(
                            active_path + "/cancel",
                            json={
                                "command_id": str(uuid4()),
                                "expected_state_revision": active["state_revision"],
                            },
                            headers=headers,
                        )
                        assert cancel.status_code == 202
                        remove_peer_release.set()
                        async with asyncio.timeout(5):
                            while owner.tasks:
                                await asyncio.sleep(0.02)
                        cancelled = (await http.get(active_path)).json()
                        assert cancelled["state"] == "FINISHED"
                        settled = await census_remove()
                        dispatch_rows = [json.loads(raw) for raw in settled["model_dispatch_v2"]]
                        dispatch_id = next(
                            row["dispatch_attempt_id"]
                            for row in dispatch_rows
                            if row["instance_id"] == str(initial.instance_id)
                            and row["operation_id"] == start_intent["operation_id"]
                        )
                        sent = [
                            json.loads(raw)
                            for raw in settled["model_dispatch_event_v2"]
                            if json.loads(raw)["dispatch_attempt_id"] == dispatch_id
                            and json.loads(raw)["state"] == "SENT"
                        ]
                        assert len(sent) in (0, 1)
                        opens, writes, connects, handoffs, traffic = relay_before
                        for scope, _ in model_opens[opens:]:
                            assert (
                                scope.instance_id == str(initial.instance_id)
                                and scope.id == dispatch_id
                            )
                        for scope, _, _, _ in model_writes[writes:]:
                            assert (
                                scope.instance_id == str(initial.instance_id)
                                and scope.id == dispatch_id
                            )
                        assert len(connected) - connects <= len(sent)
                        assert len(received) - traffic <= len(sent)
                        assert all(
                            first == "POST /api/v1/chat/completions HTTP/1.1"
                            and json.loads(body)["model"] == "fixture/selected"
                            for first, body in received[traffic:]
                        )
                        if not sent:
                            assert len(model_opens) == opens and len(model_writes) == writes
                            assert len(handed) == handoffs and len(received) == traffic
                        if len(handed) > handoffs:
                            assert model_writes[writes:] and len(sent) == 1
                        save = {
                            **readd,
                            "command_id": str(uuid4()),
                            "expected_registry_revision": 3,
                            "models": [
                                {
                                    "entry_id": new_id,
                                    "expected_revision": 1,
                                    "model": "fixture/selected",
                                    "output_tokens": 32,
                                }
                            ],
                        }
                        assert (
                            await overlap(models, save, models, remove_new) == "REVISION_CONFLICT"
                        )
                        remove_new = {
                            **remove_new,
                            "command_id": str(uuid4()),
                            "expected_registry_revision": 4,
                            "expected_revision": 2,
                        }
                        save = {
                            **save,
                            "command_id": str(uuid4()),
                            "expected_registry_revision": 4,
                            "models": [
                                {
                                    "entry_id": new_id,
                                    "expected_revision": 2,
                                    "model": "fixture/selected",
                                    "output_tokens": 32,
                                }
                            ],
                        }
                        assert (
                            await overlap(models, remove_new, models, save) == "REVISION_CONFLICT"
                        )
                        race_selection = {
                            **race_selection,
                            "command_id": str(uuid4()),
                            "expected_revision": 2,
                            "default": {
                                **context,
                                "model": "fixture/selected",
                                "output_tokens": 64,
                            },
                        }
                        for other_path, body, code in (
                            (providers, race_selection, "MODEL_NOT_REGISTERED"),
                            (tests, start_intent, "NOT_FOUND"),
                        ):
                            next_id = str(uuid4())
                            revision = (await http.get(models)).json()["registry_revision"]
                            add = {
                                **readd,
                                "command_id": str(uuid4()),
                                "expected_registry_revision": revision,
                                "models": [
                                    {
                                        "entry_id": next_id,
                                        "expected_revision": 0,
                                        "model": "fixture/selected",
                                        "output_tokens": 64,
                                    }
                                ],
                            }
                            assert (
                                await http.put(models, json=add, headers=headers)
                            ).status_code == 200
                            removal = {
                                **remove,
                                "command_id": str(uuid4()),
                                "entry_id": next_id,
                                "expected_registry_revision": revision + 1,
                            }
                            if other_path == tests:
                                body = {**body, "operation_id": str(uuid4()), "entry_id": next_id}
                            traffic = len(received)
                            assert await overlap(models, removal, other_path, body) == code
                            assert len(received) == traffic
                        heartbeat_stop.set()
                        await heartbeat
                        assert await owner.drain()
                        await service.release(process, epoch)
                        released = True
                        fresh_process = uuid4()
                        fresh_epoch = await service.acquire(fresh_process)
                        fresh_settings = ProviderSettingsOwner(
                            service,
                            fresh_process,
                            fresh_epoch,
                            ProviderVault(vault_dir, keys, str(initial.instance_id)),
                        )
                        fresh_sender = ModelSender(socket, client_context)
                        fresh_owner = ApiKeyModelTest(fresh_settings, fresh_sender)
                        try:
                            before_restart, traffic = await census_remove(), len(received)
                            await fresh_owner.reconcile()
                            control.model_test = fresh_owner.handle

                            async def fresh_provider(
                                command: KeySettingsControl | ModelRegistryControl,
                            ) -> dict[str, object]:
                                return (await fresh_settings.handle(command)).model_dump(
                                    mode="json"
                                )

                            control.provider_settings = fresh_provider
                            assert (await http.get(exact_path)).json() == archived
                            assert (await http.get(latest_path)).json() == archived
                            assert (await http.get(receipt_path)).json() == receipt
                            assert (await http.get(tests + "/latest/" + new_id)).json() == {
                                **cancelled,
                                "current": False,
                            }
                            assert (
                                await census_remove() == before_restart and len(received) == traffic
                            )
                        finally:
                            await fresh_owner.drain()
                            await fresh_sender.close()
                            await service.release(fresh_process, fresh_epoch)
                        return
                    if scenario.startswith("entry_generation_"):
                        path = "/api/v1/model-test/entries"
                        intents = [
                            {
                                "operation_id": str(uuid4()),
                                "entry_id": entry_id,
                                "expected_entry_revision": 1,
                                "expected_connection_revision": 1,
                                "catalog_command_id": catalog_id,
                                "expected_generation": generation,
                                "consent": True,
                            }
                            for entry_id in ids[:2]
                        ]

                        async def census() -> dict[str, list[str]]:
                            async with engine.connect() as db:
                                return {
                                    table: list(
                                        (
                                            await db.execute(
                                                text(
                                                    f"SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text"
                                                )
                                            )
                                        ).scalars()
                                    )
                                    for table in (
                                        "model_record_v2",
                                        "model_command_v2",
                                        "system_operation",
                                        "system_operation_event",
                                        "model_dispatch_v2",
                                        "model_dispatch_event_v2",
                                    )
                                }

                        async def complete_entry(
                            client: httpx.AsyncClient,
                            executor: ApiKeyModelTest,
                            intent: dict[str, object],
                        ) -> None:
                            response = await client.put(path, json=intent, headers=headers)
                            assert response.status_code == 202, response.text
                            async with asyncio.timeout(5):
                                while executor.tasks:
                                    await asyncio.sleep(0.02)
                            read = await client.get(path + "/" + str(intent["operation_id"]))
                            assert (
                                read.status_code == 200
                                and read.json()["result_state"] == "COMPLETED"
                            )
                            assert (
                                read.json()["state"] == "FINISHED"
                                and read.json()["current"] is True
                            )

                        if scenario != "entry_generation_before_first":
                            await complete_entry(http, owner, intents[0])
                        if scenario == "entry_generation_unchanged":
                            await complete_entry(http, owner, intents[1])
                            async with engine.connect() as db:
                                assert (
                                    await db.execute(text("SELECT count(*) FROM system_operation"))
                                ).scalar_one() == 2
                                assert (
                                    await db.execute(
                                        text(
                                            "SELECT count(*) FROM model_dispatch_event_v2 WHERE state='SENT'"
                                        )
                                    )
                                ).scalar_one() == 2
                            assert [
                                json.loads(body)["model"]
                                for first, body in received
                                if first.startswith("POST")
                            ] == ["fixture/selected", "fixture/00"]
                            return

                        # Real lifecycle methods and physical sender drain; not a manual generation UPDATE.
                        await stop_control()
                        stopped = await service.owned_status(process, epoch)
                        await service.finalize(uuid4(), stopped.generation, process, epoch)
                        heartbeat_stop.set()
                        await heartbeat
                        await service.release(process, epoch)
                        released = True
                        fresh_process = uuid4()
                        fresh_epoch = await service.acquire(fresh_process)
                        fresh_sender = ModelSender(socket, client_context)
                        fresh_settings = ProviderSettingsOwner(
                            service,
                            fresh_process,
                            fresh_epoch,
                            ProviderVault(vault_dir, keys, str(initial.instance_id)),
                        )
                        fresh_owner = ApiKeyModelTest(fresh_settings, fresh_sender)
                        service.runtime_drain = fresh_owner.drain
                        heartbeat_stop.clear()
                        fresh_heartbeat = asyncio.create_task(renew(fresh_process, fresh_epoch))
                        fresh_directory = ipc_directory / "g"
                        fresh_directory.mkdir(mode=0o700)
                        try:
                            await fresh_owner.reconcile()
                            fresh_generation = await service.open(
                                uuid4(), stopped.generation, fresh_process, fresh_epoch
                            )
                            assert fresh_generation != generation
                            monkeypatch.setenv("OMNIS_CONTROL_DIR", str(fresh_directory))
                            async with LocalControl(
                                fresh_directory, service, fresh_process, fresh_epoch
                            ) as fresh_control:
                                fresh_control.model_test = fresh_owner.handle
                                fresh_control.provider_catalog = fresh_owner.catalog_handle
                                # Same authenticated HTTP session/CSRF, retained catalog, new owning epoch.
                                retained_catalog = await http.post(
                                    catalog_path + "/search",
                                    json={**search, "catalog_command_id": catalog_id},
                                    headers=headers,
                                )
                                assert (
                                    retained_catalog.status_code == 200
                                    and retained_catalog.json() == first.json()
                                )
                                before = await census()
                                generation_traffic = (len(received), len(connected), len(handed))
                                for intent in (
                                    intents
                                    if scenario == "entry_generation_before_first"
                                    else intents[1:]
                                ):
                                    denied = await http.put(path, json=intent, headers=headers)
                                    assert (
                                        denied.status_code == 409
                                        and denied.json()["error"]["code"] == "REVISION_CONFLICT"
                                    )
                                    assert (
                                        await http.get(path + "/" + str(intent["operation_id"]))
                                    ).status_code == 404
                                assert not fresh_owner.tasks
                                assert await census() == before
                                assert (
                                    len(received),
                                    len(connected),
                                    len(handed),
                                ) == generation_traffic
                                if scenario == "entry_generation_between":
                                    generation_replay = await http.put(
                                        path, json=intents[0], headers=headers
                                    )
                                    assert (
                                        generation_replay.status_code == 202
                                        and generation_replay.json()["result_state"] == "COMPLETED"
                                    )
                                    rebound = await http.put(
                                        path,
                                        json={
                                            **intents[0],
                                            "expected_generation": fresh_generation,
                                        },
                                        headers=headers,
                                    )
                                    assert (
                                        rebound.status_code == 409
                                        and rebound.json()["error"]["code"] == "COMMAND_CONFLICT"
                                    )
                                    assert (
                                        await census() == before
                                        and (len(received), len(connected), len(handed))
                                        == generation_traffic
                                    )
                                await complete_entry(
                                    http,
                                    fresh_owner,
                                    {
                                        **intents[1],
                                        "operation_id": str(uuid4()),
                                        "expected_generation": fresh_generation,
                                    },
                                )
                                expected = 1 if scenario == "entry_generation_before_first" else 2
                                async with engine.connect() as db:
                                    assert (
                                        await db.execute(
                                            text("SELECT count(*) FROM system_operation")
                                        )
                                    ).scalar_one() == expected
                                    assert (
                                        await db.execute(
                                            text(
                                                "SELECT count(*) FROM model_dispatch_event_v2 WHERE state='SENT'"
                                            )
                                        )
                                    ).scalar_one() == expected
                                assert len(received) == generation_traffic[0] + 1
                        finally:
                            heartbeat_stop.set()
                            try:
                                await fresh_heartbeat
                            finally:
                                try:
                                    assert await fresh_owner.drain()
                                finally:
                                    try:
                                        await fresh_sender.close()
                                    finally:
                                        await service.release(fresh_process, fresh_epoch)
                        return
                    found = await http.post(
                        catalog_path + "/search",
                        json={
                            **search,
                            "catalog_command_id": catalog_id,
                            "query": "Selected exact",
                        },
                        headers=headers,
                    )
                    assert found.status_code == 200 and found.json()["total"] == 1
                    assert found.json()["entries"][0]["max_output_tokens"] == 128
                    assert (
                        await http.post(
                            catalog_path + "/refresh", json=refresh_body, headers=headers
                        )
                    ).status_code == 202
                    assert len(received) == 2
                    assert (
                        await http.post(
                            catalog_path + "/search",
                            json={**search, "query": "x" * 257},
                            headers=headers,
                        )
                    ).status_code == 422
                    assert (
                        await http.post(
                            catalog_path + "/search", json={**search, "offset": 16}, headers=headers
                        )
                    ).status_code == 422
                    for catalog_mode in ("foreign", "loop", "unknown"):
                        before_traffic = len(received)
                        command_id = str(uuid4())
                        partial = await http.post(
                            catalog_path + "/refresh",
                            json={**refresh_body, "command_id": command_id},
                            headers=headers,
                        )
                        assert partial.status_code == 202
                        async with asyncio.timeout(5):
                            while owner.tasks:
                                await asyncio.sleep(0.02)
                        partial_read = await http.post(
                            catalog_path + "/search",
                            json={**search, "catalog_command_id": command_id},
                            headers=headers,
                        )
                        assert (
                            partial_read.status_code == 200
                            and partial_read.json()["state"] == "PARTIAL"
                        )
                        assert partial_read.json()["reason"] == (
                            "TOTAL_MISMATCH"
                            if catalog_mode == "unknown"
                            else "CONTINUATION_UNSUPPORTED"
                        )
                        assert partial_read.json()["entries"][0]["max_output_tokens"] == 128
                        assert len(received) == before_traffic + 1
                    catalog_mode = "complete"
                    await settings.handle(
                        ModelRegistryControl.model_validate(
                            {
                                "op": "provider_models",
                                "request": {
                                    "action": "save_models",
                                    "command_id": str(uuid4()),
                                    "expected_registry_revision": 1,
                                    "connection_id": connection_id,
                                    "connection_revision": 1,
                                    "models": [
                                        {
                                            "entry_id": str(uuid4()),
                                            "expected_revision": 0,
                                            "model": "fixture/model",
                                            "output_tokens": 128,
                                        }
                                    ],
                                },
                            }
                        )
                    )
                    default = {
                        "connection_id": connection_id,
                        "connection_revision": 1,
                        "model": "fixture/model",
                        "output_tokens": 37,
                    }
                    selection = await http.put(
                        "/api/v1/settings/providers",
                        headers=headers,
                        json={
                            "action": "save_selection",
                            "command_id": str(uuid4()),
                            "expected_revision": 0,
                            "default": default,
                            "brain": {**default, "model": "fixture/00", "output_tokens": 12},
                            "investigator": None,
                            "validator": {**default, "output_tokens": 23},
                        },
                    )
                    assert selection.status_code == 200
                    old_selection = selection.json()["selection"]
                    operation_id = str(uuid4())
                    entry_intent = {
                        "expected_generation": generation,
                        "operation_id": operation_id,
                        "entry_id": ids[0],
                        "expected_entry_revision": 1,
                        "expected_connection_revision": 1,
                        "catalog_command_id": catalog_id,
                        "consent": True,
                    }
                    async with engine.connect() as db:
                        before_denials = (
                            await db.execute(
                                text(
                                    "SELECT (SELECT count(*) FROM model_record_v2),(SELECT count(*) FROM model_command_v2),(SELECT count(*) FROM system_operation),(SELECT count(*) FROM model_dispatch_v2),(SELECT count(*) FROM model_dispatch_event_v2),(SELECT count(*) FROM system_operation_event)"
                                )
                            )
                        ).one()
                    for invalid_entry in (
                        {"expected_entry_revision": 2},
                        {"expected_connection_revision": 2},
                        {"entry_id": ids[1]},
                        {"entry_id": ids[2]},
                    ):
                        denied = await http.put(
                            "/api/v1/model-test/entries",
                            json={**entry_intent, **invalid_entry},
                            headers=headers,
                        )
                        assert denied.status_code == 409, denied.text
                    async with engine.connect() as db:
                        assert (
                            await db.execute(
                                text(
                                    "SELECT (SELECT count(*) FROM model_record_v2),(SELECT count(*) FROM model_command_v2),(SELECT count(*) FROM system_operation),(SELECT count(*) FROM model_dispatch_v2),(SELECT count(*) FROM model_dispatch_event_v2),(SELECT count(*) FROM system_operation_event)"
                                )
                            )
                        ).one() == before_denials
                    before_test = len(received)
                    admitted = await http.put(
                        "/api/v1/model-test/entries", json=entry_intent, headers=headers
                    )
                    assert admitted.status_code == 202, admitted.text
                    async with asyncio.timeout(5):
                        while owner.tasks:
                            await asyncio.sleep(0.02)
                    read_path = "/api/v1/model-test/entries/" + operation_id
                    exact = (await http.get(read_path)).json()
                    assert (
                        exact["result_state"] == "COMPLETED"
                        and exact["requested_model"] == "fixture/selected"
                    )
                    assert (
                        exact["entry_id"] == ids[0]
                        and exact["entry_revision"] == 1
                        and exact["current"] is True
                    )
                    assert (
                        exact["observed_model"] == "fixture/observed"
                        and exact["selection_revision"] is None
                    )
                    assert len(received) == before_test + 1
                    assert (
                        await http.put(
                            "/api/v1/model-test/entries", json=entry_intent, headers=headers
                        )
                    ).json() == exact
                    assert (await http.get("/api/v1/settings/providers")).json()[
                        "selection"
                    ] == old_selection
                    assert (await http.get("/api/v1/model-test")).json()["operation_id"] is None
                    latest_path = f"/api/v1/model-test/entries/latest/{entry_intent['entry_id']}"
                    assert (await http.get(latest_path)).json() == exact
                    absent = await http.get(f"/api/v1/model-test/entries/latest/{uuid4()}")
                    assert (
                        absent.status_code == 404 and absent.json()["error"]["code"] == "NOT_FOUND"
                    )
                    async with engine.connect() as db:
                        operation_row = (
                            await db.execute(
                                text(
                                    "SELECT config_snapshot_ref FROM system_operation WHERE operation_id=:id"
                                ),
                                {"id": operation_id},
                            )
                        ).scalar_one()
                        assert operation_row["kind"] == "model-entry-snapshot-v1"
                        assert (
                            await db.execute(
                                text("SELECT state FROM model_dispatch_event_v2 ORDER BY sequence")
                            )
                        ).scalars().all() == ["RESERVED", "SENT", "SETTLED"]
                        assert (
                            await db.execute(
                                text("SELECT count(*) FROM provider_selection_revision")
                            )
                        ).scalar_one() == 1
                    catalog_mode = "wait"
                    waiting_id = str(uuid4())
                    waiting = await http.post(
                        catalog_path + "/refresh",
                        json={**refresh_body, "command_id": waiting_id},
                        headers=headers,
                    )
                    assert waiting.status_code == 202
                    await asyncio.wait_for(catalog_entered.wait(), 3)
                    active = await http.put(
                        "/api/v1/model-test/entries",
                        json={**entry_intent, "operation_id": str(uuid4())},
                        headers=headers,
                    )
                    assert (
                        active.status_code == 409
                        and active.json()["error"]["code"] == "OPERATION_ACTIVE"
                    )
                    cancelled = await http.post(
                        catalog_path + "/cancel",
                        json={
                            "action": "cancel",
                            **context,
                            "catalog_command_id": waiting_id,
                            "command_id": str(uuid4()),
                        },
                        headers=headers,
                    )
                    assert cancelled.status_code == 202 and cancelled.json()["state"] == "FAILED"
                    assert cancelled.json()["reason"] == "CANCELLED_OR_STOPPED"
                    assert not owner.tasks
                    catalog_release.set()
                    catalog_mode = "complete"
                    before_rotation = len(received)
                    rotated = await http.put(
                        "/api/v1/settings/providers",
                        headers=headers,
                        json={
                            "action": "save_connection",
                            "command_id": str(uuid4()),
                            "connection_id": connection_id,
                            "expected_revision": 1,
                            "provider": "openrouter",
                            "secret": "synthetic-replacement-key",
                        },
                    )
                    assert rotated.status_code == 200
                    stale = await http.post(
                        catalog_path + "/search",
                        json={**search, "catalog_command_id": catalog_id},
                        headers=headers,
                    )
                    assert (
                        stale.status_code == 200
                        and stale.json()["state"] == "STALE"
                        and stale.json()["entries"] == []
                    )
                    historical = (await http.get(read_path)).json()
                    assert (await http.get(latest_path)).json() == historical
                    assert (
                        historical["result_state"] == "COMPLETED" and historical["current"] is False
                    )
                    assert (
                        await http.put(
                            "/api/v1/model-test/entries",
                            json={**entry_intent, "operation_id": str(uuid4())},
                            headers=headers,
                        )
                    ).status_code == 409
                    assert (await http.get("/api/v1/settings/providers")).json()[
                        "selection"
                    ] == old_selection
                    assert len(received) == before_rotation
                    await service.shutdown(uuid4(), generation, process, epoch)
                    await service.quiesce(process, epoch)
                    assert (await http.get(read_path)).json() == historical
                    heartbeat_stop.set()
                    await heartbeat
                    await owner.drain()
                    await service.release(process, epoch)
                    released = True
                    fresh_process = uuid4()
                    fresh_epoch = await service.acquire(fresh_process)
                    heartbeat_stop.clear()
                    fresh_heartbeat = asyncio.create_task(renew(fresh_process, fresh_epoch))
                    fresh_settings = ProviderSettingsOwner(
                        service,
                        fresh_process,
                        fresh_epoch,
                        ProviderVault(vault_dir, keys, str(initial.instance_id)),
                    )
                    fresh_sender = ModelSender(socket, client_context)
                    fresh_owner = ApiKeyModelTest(fresh_settings, fresh_sender)
                    fresh_directory = ipc_directory / "d"
                    fresh_directory.mkdir(mode=0o700)
                    assert len(bytes(fresh_directory / "control.sock")) <= 107
                    monkeypatch.setenv("OMNIS_CONTROL_DIR", str(fresh_directory))
                    try:
                        await fresh_owner.reconcile()
                        async with LocalControl(
                            fresh_directory, service, fresh_process, fresh_epoch
                        ) as fresh_control:
                            fresh_control.model_test = fresh_owner.handle
                            fresh_control.provider_catalog = fresh_owner.catalog_handle
                            fresh_app = create_app()
                            fresh_app.state.db_engine = engine
                            async with httpx.AsyncClient(
                                transport=httpx.ASGITransport(app=fresh_app),
                                base_url="http://127.0.0.1:8765",
                                cookies={"omnis_session": grant.token},
                            ) as fresh_http:
                                assert (await fresh_http.get(read_path)).json() == historical
                                cached = await fresh_http.post(
                                    catalog_path + "/search",
                                    json={**search, "catalog_command_id": catalog_id},
                                    headers=headers,
                                )
                                assert cached.status_code == 200 and cached.json() == stale.json()
                                inert = await fresh_http.post(
                                    catalog_path + "/search",
                                    json={**search, "connection_revision": 2},
                                    headers=headers,
                                )
                                assert (
                                    inert.status_code == 200
                                    and inert.json()["state"] == "NOT_REQUESTED"
                                )
                                assert len(received) == before_rotation
                    finally:
                        heartbeat_stop.set()
                        try:
                            await fresh_heartbeat
                        finally:
                            try:
                                assert await fresh_owner.drain()
                            finally:
                                try:
                                    await fresh_sender.close()
                                finally:
                                    await service.release(fresh_process, fresh_epoch)
                    return
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
                if metadata_outage:
                    failed_command = str(uuid4())
                    failed = await http.post(
                        "/api/v1/model-test/capabilities",
                        json={"command_id": failed_command, "expected_selection_revision": 1},
                        headers=headers,
                    )
                    assert failed.status_code == 202
                    async with asyncio.timeout(5):
                        while owner.tasks:
                            await asyncio.sleep(0.02)
                    failed_receipt = (
                        await http.get("/api/v1/model-test/capabilities/" + failed_command)
                    ).json()
                    assert failed_receipt["metadata_state"] == "FAILED"
                    assert failed_receipt["reason"] == "METADATA_UNAVAILABLE"
                    assert not owner.settlement_failed
                    assert len(received) == (1 if scenario == "metadata_eof" else 0)
                    metadata_outage = False
                    if scenario == "metadata_refused":
                        server = await asyncio.start_server(
                            serve, "127.0.0.1", address[1], ssl=server_context
                        )
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
                traffic = 3 if scenario == "metadata_eof" else 2
                if scenario in {"metadata_refused", "metadata_eof"}:
                    assert (
                        await http.get("/api/v1/model-test/capabilities/" + failed_command)
                    ).json() == failed_receipt
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
                if scenario == "settlement_before_cancel":
                    # The real terminal settlement wins before this stale mutation is sent.
                    terminal = value
                    stale = await http.post(
                        "/api/v1/model-test/" + operation + "/cancel",
                        headers=headers,
                        json={"command_id": str(uuid4()), "expected_state_revision": 2},
                    )
                    assert stale.status_code == 409
                    assert stale.json()["error"]["code"] == "REVISION_CONFLICT"
                    assert (await http.get("/api/v1/model-test/" + operation)).json() == terminal
                    assert len(received) == traffic and not owner.tasks
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
                if scenario.startswith("relay_"):
                    await (
                        sender.transport.aclose()
                    )  # Force the next OPEN through the production resolver.
                    physical_phase = scenario.rsplit("_", 1)[1]
                    before_connect, before_handoff = len(connected), len(handed)
                    second_id = str(uuid4())
                    assert (
                        await http.put(
                            "/api/v1/model-test",
                            json={**intent, "operation_id": second_id},
                            headers=headers,
                        )
                    ).status_code == 202
                    assert await asyncio.to_thread(physical_entered.wait, 2)
                    if scenario.startswith("relay_expiry_"):
                        # No competing Cancel: readiness/IPC expires under its own authority.
                        async with asyncio.timeout(3):
                            while owner.tasks:
                                await asyncio.sleep(0.01)
                        expired = (await http.get("/api/v1/model-test/" + second_id)).json()
                        assert expired["state"] == "FINISHED"
                        assert expired["result_state"] == "UNKNOWN"
                        assert expired["usage_state"] == "UNKNOWN"
                        assert expired["cost_observed"] is None
                        expired_counts = (len(connected), len(handed), len(received))
                        physical_release.set()
                        await asyncio.sleep(0.05)
                        assert (len(connected), len(handed), len(received)) == expired_counts
                        assert len(connected) == before_connect + (physical_phase == "write")
                        assert len(handed) == before_handoff and len(received) == traffic
                        assert not owner.settlement_failed
                    else:
                        assert physical_phase in {"dns", "connect"}
                        before = (await http.get("/api/v1/model-test/" + second_id)).json()
                        connect_scope: Scope | None = None
                        if physical_phase == "connect":
                            assert before["operation_id"] == second_id
                            assert before["state"] == "RUNNING"
                            connect_scope, connect_deadline = model_opens[-1]
                            assert datetime.now(UTC) < min(
                                utc(connect_scope.deadline), utc(connect_deadline)
                            )
                        action: asyncio.Task[httpx.Response] | asyncio.Task[None]
                        if "revoke" in scenario:
                            action = asyncio.create_task(
                                http.put(
                                    "/api/v1/settings/providers",
                                    headers=headers,
                                    json={
                                        "action": "revoke_connection",
                                        "command_id": str(uuid4()),
                                        "connection_id": connection_id,
                                        "expected_revision": 1,
                                    },
                                )
                            )
                        elif "stop" in scenario:
                            action = asyncio.create_task(stop_control())
                        else:
                            action = asyncio.create_task(
                                http.post(
                                    "/api/v1/model-test/" + second_id + "/cancel",
                                    headers=headers,
                                    json={
                                        "command_id": str(uuid4()),
                                        "expected_state_revision": before["state_revision"],
                                    },
                                )
                            )
                        if physical_phase == "dns":
                            await asyncio.sleep(0.1)
                            # Resolver thread is still owned: terminal/drain ACK must wait.
                            assert not action.done()
                            assert (await http.get("/api/v1/model-test/" + second_id)).json()[
                                "state"
                            ] != "FINISHED"
                            physical_release.set()
                        action_reply = await asyncio.wait_for(action, 3)
                        if action_reply is not None:
                            assert action_reply.status_code == (
                                200 if "revoke" in scenario else 202
                            ), action_reply.text
                        if physical_phase == "connect":
                            assert action_reply is not None
                            assert connect_scope is not None
                            assert datetime.now(UTC) < min(
                                utc(connect_scope.deadline), utc(connect_deadline)
                            )
                            assert action_reply.json()["state"] == "FINISHED"
                            assert action_reply.json()["finish_reason"] == "CANCELLED"
                            assert (
                                await http.get("/api/v1/model-test/" + second_id)
                            ).json() == action_reply.json()
                            assert ("FENCE", connect_scope) in fence_acks
                            assert ("DRAIN", connect_scope) in fence_acks
                            assert not physical_release.is_set()
                        ack_counts = (len(connected), len(handed), len(received))
                        async with asyncio.timeout(3):
                            while owner.tasks:
                                await asyncio.sleep(0.01)
                        assert (await http.get("/api/v1/model-test/" + second_id)).json()[
                            "state"
                        ] == "FINISHED"
                        physical_release.set()  # Async connect is cancellable before release.
                        await asyncio.sleep(0.05)
                        assert (len(connected), len(handed), len(received)) == ack_counts
                        assert len(connected) == before_connect
                        assert len(handed) == before_handoff and len(received) == traffic
                        assert not owner.settlement_failed
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
                    captured_scope, captured_connection, captured_sequence, _ = model_writes[-1]
                    if scenario == "stop_at_body":
                        await stop_control()
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
                        assert cancelled.json()["state"] == "FINISHED"
                        assert cancelled.json()["finish_reason"] == "CANCELLED"
                        assert (
                            await http.get("/api/v1/model-test/" + second_id)
                        ).json() == cancelled.json()
                        assert ("FENCE", captured_scope) in fence_acks
                        assert ("DRAIN", captured_scope) in fence_acks
                    ack_counts = (len(connected), len(handed), len(received))
                    reader, writer = await asyncio.open_unix_connection(socket, limit=4096)
                    # Adversarial fixture-only deadline mutation, NOT a new DB grant after Cancel.
                    late_now = datetime.now(UTC)
                    late_deadline = min(
                        utc(captured_scope.deadline), late_now + timedelta(seconds=0.4)
                    )
                    assert late_now < late_deadline <= late_now + timedelta(seconds=0.5)
                    late: dict[str, object] = {
                        "version": 2,
                        "action": "WRITE",
                        "request_id": str(uuid4()),
                        "connection_id": captured_connection,
                        "scope": captured_scope.wire(),
                        "sequence": captured_sequence + 1,
                        "size": len(b"post-ack-replay"),
                        "timeout_ms": 500,
                        "write_deadline": late_deadline.isoformat(),
                        "retire_through": 0,
                        "capability": (relay_directory / "model-relay.cap").read_text(),
                    }
                    try:
                        assert validate(late) == captured_scope
                        assert datetime.now(UTC) < late_deadline
                        writer.write(encode(late) + b"post-ack-replay")
                        await writer.drain()
                        relay_denied = decode(await asyncio.wait_for(reader.readline(), 1))
                        assert datetime.now(UTC) < late_deadline
                        assert relay_denied == {
                            **{
                                k: late[k]
                                for k in (
                                    "version",
                                    "request_id",
                                    "connection_id",
                                    "scope",
                                    "sequence",
                                    "retire_through",
                                )
                            },
                            "status": "DENIED",
                            "size": 0,
                        }
                    finally:
                        writer.close()
                        await writer.wait_closed()
                    release.set()
                    async with asyncio.timeout(4):
                        while (after := (await http.get("/api/v1/model-test/" + second_id)).json())[
                            "state"
                        ] != "FINISHED":
                            await asyncio.sleep(0.02)
                    assert after["result_state"] == "UNKNOWN"
                    assert after["usage_state"] == "UNKNOWN" and after["cost_observed"] is None
                    await asyncio.sleep(0.05)
                    assert (len(connected), len(handed), len(received)) == ack_counts
                    assert (
                        len(received) == traffic
                    )  # Reused TLS headers can arrive; no second body.
                if scenario not in {"stop_at_body", "relay_stop_dns"}:
                    await service.shutdown(uuid4(), generation, process, epoch)
                await service.quiesce(process, epoch)
                assert (await http.get("/api/v1/model-test/" + operation)).json() == value
                assert len(received) == traffic
                async with engine.connect() as db:
                    assert (
                        await db.execute(
                            text("SELECT count(*) FROM model_dispatch_event_v2 WHERE state='SENT'")
                        )
                    ).scalar_one() == (
                        2 if scenario.endswith("at_body") or scenario.startswith("relay_") else 1
                    )
                    assert (
                        await db.execute(text("SELECT count(*) FROM system_operation"))
                    ).scalar_one() == (
                        2 if scenario.endswith("at_body") or scenario.startswith("relay_") else 1
                    )
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
        primary = sys.exception()
        physical_release.set()
        catalog_release.set()
        remove_peer_release.set()
        ui_model_release.set()
        heartbeat_stop.set()
        try:
            try:
                try:
                    await heartbeat
                finally:
                    await owner.drain()
            finally:
                await sender.close()
                relay.close()
                await relay.wait_closed()
                dns_patch.stop()
                connect_patch.stop()
                server.close()
                await server.wait_closed()
                if tasks:
                    await asyncio.wait_for(asyncio.gather(*tasks), 2)
        finally:
            try:
                if not released:
                    await service.release(process, epoch)
            except BaseException as cleanup:
                if primary is not None:
                    primary.add_note(f"Fixture release also failed: {type(cleanup).__name__}")
                else:
                    raise
            finally:
                await engine.dispose()
        assert not socket.exists() and not tasks


@pytest.mark.asyncio
async def test_installed_sent_crash_reconciles_without_resend(
    migrated_database_url: URL,
    ipc_directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Installed API components, synthetic metadata, real PG and receive-only relay."""
    import hashlib
    import importlib
    import signal

    from installed_sent_probe import PROBE, install_probe_wheel

    python = await asyncio.to_thread(install_probe_wheel, tmp_path)
    api = Path(__file__).resolve().parents[1]
    config: dict[str, object] = {
        "modules": {
            str(p.relative_to(api / "src")): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (api / "src/omnis").rglob("*.py")
        },
        "database": migrated_database_url.render_as_string(hide_password=False),
        "operation": str(uuid4()),
        "refresh": str(uuid4()),
        "socket": str(ipc_directory / "model-egress.sock"),
        "vault": str(tmp_path / "vault"),
        "keys": str(tmp_path / "keys"),
    }
    for name in ("home", "tmp", "config", "vault", "keys"):
        (tmp_path / name).mkdir(mode=0o700)
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path / "home"),
        "TMPDIR": str(tmp_path / "tmp"),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
    }
    children: list[int] = []

    async def child(mode: str, expected: int) -> list[dict[str, object]]:
        result = await asyncio.to_thread(
            subprocess.run,
            [str(python), "-I", "-B", "-c", PROBE],
            input=json.dumps({**config, "mode": mode}).encode(),
            cwd=tmp_path,
            env=env,
            capture_output=True,
            timeout=20,
        )
        # Private diagnostics contain no stdin/DSN; don't print child tracebacks into the gate.
        (tmp_path / f"{mode}-{len(children)}.stderr").write_bytes(result.stderr)
        (tmp_path / f"{mode}-{len(children)}.stdout").write_bytes(result.stdout)
        assert result.returncode == expected, f"{mode} exit {result.returncode}"
        assert not result.stderr
        events = [json.loads(line) for line in result.stdout.splitlines()]
        assert events[0]["stage"] == "installed"
        assert events[0]["prefix"] == str(tmp_path / "venv")
        children.append(events[0]["pid"])
        return events

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))

    async def census() -> dict[str, list[object]]:
        async with engine.connect() as db:
            tables = (
                (
                    await db.execute(
                        text(
                            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
                        )
                    )
                )
                .scalars()
                .all()
            )
            result: dict[str, list[object]] = {}
            for table in tables:
                name = engine.dialect.identifier_preparer.quote(table)
                result[table] = list(
                    (
                        await db.execute(
                            text(f"SELECT to_jsonb(t) FROM {name} t ORDER BY to_jsonb(t)::text")
                        )
                    )
                    .scalars()
                    .all()
                )
            return result

    # Reuse the actual host relay; disallow every data-plane verb before DNS/connect.
    monkeypatch.syspath_prepend(str(api.parent / "cli/src"))
    host = importlib.import_module("omnis_cli.model_relay")
    original_validate = host.validate
    actions: list[str] = []

    def receive_only(frame: dict[str, object]) -> object:
        actions.append(str(frame["action"]))
        if frame["action"] not in {"FENCE", "DRAIN"}:
            raise ValueError("test forbids provider IO")
        return original_validate(frame)

    monkeypatch.setattr(host, "validate", receive_only)
    relay = await host.start_model_forwarder(ipc_directory)
    try:
        before = await census()
        negative = await child("deny_send", 79)
        assert negative[-1] == {"stage": "send_denied"}
        assert await census() == before and not actions
        produced = await child("produce", -signal.SIGKILL)
        assert [event["stage"] for event in produced] == ["installed", "ready", "send_entry"]
        config["receipt"] = produced[1]["receipt"]
        cut = await census()  # Separate connection, after OS death: SENT really committed.
        assert {name for name in before if cut[name] != before[name]} == {
            "instance_control",
            "supervisor_lease",
            "instance_command",
            "provider_connection_revision",
            "provider_selection_revision",
            "provider_settings_command",
            "provider_model_registry_revision",
            "provider_model_entry",
            "provider_model_entry_revision",
            "provider_model_command",
            "model_record_v2",
            "model_command_v2",
            "system_operation",
            "system_operation_event",
            "model_dispatch_v2",
            "model_dispatch_event_v2",
        }
        (operation,) = cut["system_operation"]
        assert isinstance(operation, dict)
        assert operation["state"] == "RUNNING" and operation["state_revision"] == 2
        assert operation["outcome_ref"] is operation["finish_reason"] is None
        assert operation["execution_owner_id"] == produced[1]["owner"]
        assert [
            row["state"] for row in cut["model_dispatch_event_v2"] if isinstance(row, dict)
        ] == ["RESERVED", "SENT"]
        assert len(cut["model_dispatch_v2"]) == 1 and len(cut["model_command_v2"]) == 2
        assert len(cut["system_operation_event"]) == 2
        assert not any(
            row["kind"] in {"model-outcome-v2", "model-output-v2"}
            for row in cut["model_record_v2"]
            if isinstance(row, dict)
        )
        assert not actions
        # Let the crashed owner's real five-second lease expire; no DB mutation/release shim.
        async with asyncio.timeout(8):
            while True:
                async with engine.connect() as db:
                    expired = (
                        await db.execute(
                            text(
                                "SELECT expires_at <= clock_timestamp() FROM supervisor_lease WHERE id=1"
                            )
                        )
                    ).scalar_one()
                if expired:
                    break
                await asyncio.sleep(0.05)
        recovered = await child("recover", 0)
        assert recovered[-1]["epoch"] == int(str(produced[1]["epoch"])) + 1
        assert recovered[-1]["owner"] != produced[1]["owner"]
        after = await census()
        assert actions == ["FENCE", "DRAIN"]
        assert {name for name in cut if after[name] != cut[name]} == {
            "instance_control",
            "supervisor_lease",
            "system_operation",
            "system_operation_event",
            "model_record_v2",
            "model_dispatch_event_v2",
        }
        for table in ("model_record_v2", "system_operation_event", "model_dispatch_event_v2"):
            assert all(row in after[table] for row in cut[table])
        assert len(after["model_record_v2"]) == len(cut["model_record_v2"]) + 2
        assert len(after["system_operation_event"]) == 3
        assert [
            row["state"] for row in after["model_dispatch_event_v2"] if isinstance(row, dict)
        ] == ["RESERVED", "SENT", "SETTLED"]
        assert len(after["system_operation"]) == len(after["model_dispatch_v2"]) == 1
        reread = await child("recover", 0)
        assert reread[-1]["view"] == recovered[-1]["view"]
        final = await census()
        assert {name for name in after if final[name] != after[name]} == {"supervisor_lease"}
        assert actions == ["FENCE", "DRAIN"]
        assert len(set(children)) == len(children)
    finally:
        relay.close()
        await asyncio.wait_for(relay.wait_closed(), 3)
        await engine.dispose()
    assert not (ipc_directory / "model-egress.sock").exists()
