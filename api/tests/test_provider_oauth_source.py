"""SOURCE tests of trusted fixed OAuth client and worker ownership; no provider IO."""

import importlib
import threading
import time
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import httpx
import pytest


def test_host_lifeline_expiry_and_renewal_without_watchdog(tmp_path: Path) -> None:
    import os

    from omnis_hermes.management_oauth import NativeOAuth
    from omnis_hermes.runtime_host import RuntimeHost

    host = RuntimeHost(tmp_path)
    host.deadline_ns = time.monotonic_ns() + 40_000_000
    reader = host._open_management_lifeline()
    try:
        owner = NativeOAuth.from_owner_fd(reader)
        owner._owner_alive()
        host.deadline_ns = host._grant({"deadline_ns": time.monotonic_ns() + 150_000_000})
        time.sleep(0.06)
        owner._owner_alive()  # same authority observes the stock renewed Host deadline
        time.sleep(0.12)
        with pytest.raises(ValueError):
            owner._owner_alive()  # writer still open; Host watchdog has never run
        host._revoke_management_lifeline()
        with pytest.raises(ValueError):
            owner._owner_alive()
    finally:
        host._revoke_management_lifeline()
        os.close(reader)


@pytest.mark.parametrize("fault", [None, "truncated", "eof"])
def test_host_lifeline_drains_stock_renewal_backlog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str | None
) -> None:
    import os
    from types import SimpleNamespace

    from omnis_hermes import management_oauth, runtime_host

    clock = [10_000_000_000]
    timer = SimpleNamespace(monotonic_ns=lambda: clock[0])
    monkeypatch.setattr(runtime_host, "time", timer)
    monkeypatch.setattr(management_oauth, "time", timer)
    host = runtime_host.RuntimeHost(tmp_path)
    host.deadline_ns = clock[0] + 4_500_000_000
    reader = host._open_management_lifeline()
    try:
        owner = management_oauth.NativeOAuth.from_owner_fd(reader)
        assert host.watchdog is None
        for _ in range(560):
            clock[0] += 500_000_000
            host.deadline_ns = host._grant({"deadline_ns": clock[0] + 4_500_000_000})
        assert clock[0] == 290_000_000_000
        assert host.management_lifeline_write is not None
        if fault == "truncated":
            os.write(host.management_lifeline_write, b"x")
        elif fault == "eof":
            host._revoke_management_lifeline()
        if fault is None:
            owner._owner_alive()  # first read must see all 4480 queued bytes
            assert owner.owner_deadline_ns == host.deadline_ns
            owner._owner_alive()
            clock[0] += 4_500_000_000
            with pytest.raises(ValueError):
                owner._owner_alive()
        else:
            with pytest.raises(ValueError):
                owner._owner_alive()
    finally:
        host._revoke_management_lifeline()
        os.close(reader)


@pytest.mark.asyncio
async def test_host_connect_poll_cancel_uses_one_slot_and_current_read(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio
    from unittest.mock import AsyncMock, Mock

    from omnis_hermes import runtime_host
    from omnis_hermes.management_contract import SELECTION

    from omnis.modules.instance.service import RuntimeAuthority
    from omnis.supervisor.runtime_client import RuntimeClient

    host = runtime_host.RuntimeHost(ipc_directory)
    host.management_port = 1

    async def native(action: str, selected: object) -> dict[str, object]:
        return (
            dict(SELECTION)
            if action == "read"
            else {"selection": dict(SELECTION), "authenticated": "ABSENT"}
        )

    monkeypatch.setattr(host, "_settings_native", native)
    calls: list[str] = []

    async def endpoint(
        port: int,
        token: str,
        method: str,
        path: str,
        payload: dict[str, object],
        *,
        dispatch_guard: Callable[[], None],
    ) -> dict[str, object]:
        dispatch_guard()
        assert payload["boot"] == host.boot
        assert payload["deadline_ns"] == host.deadline_ns
        action = path.rsplit("/", 1)[1]
        calls.append(action)
        return (
            {"oauth": "CANCELLED", "challenge": None}
            if action == "cancel"
            else {
                "oauth": "CHALLENGE",
                "challenge": {"code": "ABCD-EFGH", "url": "https://auth.openai.com/codex/device"},
            }
        )

    monkeypatch.setattr(runtime_host, "request", endpoint)
    service = Mock(
        runtime_authority=AsyncMock(
            side_effect=lambda *a, **k: RuntimeAuthority(0, 1, time.monotonic_ns() + 4_000_000_000)
        )
    )
    async with host:
        client = RuntimeClient(ipc_directory, generation=0, epoch=1)
        await client.connect()
        try:
            operation = str(uuid4())
            body: dict[str, object] = {
                "operation_id": operation,
                "action": "connect",
                "selection": None,
            }
            assert (await client.settings(service, uuid4(), body))["status"] == "PENDING"
            for _ in range(100):
                result = await client.settings_status(operation)
                if result["oauth"] == "CHALLENGE":
                    break
                await asyncio.sleep(0.005)
            assert result["oauth"] == "CHALLENGE"
            assert (await client.settings_status("00000000-0000-0000-0000-000000000000"))[
                "operation_id"
            ] == operation
            for _ in range(70):
                assert (await client.settings_status(operation))["status"] == "PENDING"
            assert len(host.settings_seen) == 1
            assert (
                await client.settings(
                    service,
                    uuid4(),
                    {
                        **body,
                        "operation_id": str(uuid4()),
                        "action": "save",
                        "selection": dict(SELECTION),
                    },
                )
            )["status"] == "BUSY"
            await client.settings(service, uuid4(), {**body, "action": "cancel"})
            async with asyncio.timeout(2):
                while (result := await client.settings_status(operation))["status"] == "PENDING":
                    await asyncio.sleep(0.01)
            assert result["oauth"] == "CANCELLED" and result["challenge"] is None
            assert calls.count("connect") == 1 and len(host.settings_seen) == 1
        finally:
            await client.close()


def test_connect_contract_is_finite_and_terminal_projection_clears_challenge() -> None:
    from omnis_hermes.management_contract import command, view

    from omnis.modules.settings.provider_models import ProviderCommand, ProviderView

    operation = str(uuid4())
    for action in ("connect", "cancel"):
        body = ProviderCommand.model_validate(
            {"operation_id": operation, "action": action, "selection": None}
        )
        assert command(body.model_dump())["action"] == action
    challenge = {"code": "ABCD-EFGH", "url": "https://auth.openai.com/codex/device"}
    pending = view(operation, "PENDING", oauth="CHALLENGE", challenge=challenge)
    assert ProviderView.model_validate(pending).oauth == "CHALLENGE"
    with pytest.raises(ValueError):
        view(operation, "CONFIRMED", oauth="CANCELLED", challenge=challenge)


def test_fixed_client_refuses_redirects_host_extensions_before_transport() -> None:
    from omnis_hermes import management_oauth

    sent: list[httpx.Request] = []

    def send(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"ok": True})

    # Synthetic transport replaces only the HTTPX wire constructor, never product policy.
    from unittest.mock import patch

    with patch.object(httpx, "HTTPTransport", return_value=httpx.MockTransport(send)):
        client = management_oauth.FixedClient(lambda: None)
        with client:
            assert (
                client.post(
                    "https://auth.openai.com/api/accounts/deviceauth/usercode",
                    json={"client_id": "synthetic"},
                    headers={"Content-Type": "application/json"},
                ).status_code
                == 200
            )
            for url, kwargs in (
                ("https://example.invalid/oauth/token", {}),
                ("http://auth.openai.com/oauth/token", {}),
                ("https://auth.openai.com/v1/responses", {}),
                ("https://auth.openai.com/oauth/token?x=1", {}),
                ("https://auth.openai.com/oauth/token", {"headers": {"Host": "example.invalid"}}),
                ("https://auth.openai.com/oauth/token", {"extensions": {"sni_hostname": "evil"}}),
                ("https://auth.openai.com/oauth/token", {"follow_redirects": True}),
            ):
                with pytest.raises(ValueError):
                    client.post(url, **kwargs)
        assert len(sent) == 1


def test_fixed_client_retires_each_poll_before_the_next_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ssl
    from typing import Self

    from httpcore import NetworkStream
    from httpcore._backends.sync import SyncBackend
    from omnis_hermes.management_oauth import FixedClient

    statuses = iter((403, 404))

    class Stream(NetworkStream):
        closed = False

        def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
            return f"HTTP/1.1 {next(statuses)} Pending\r\nContent-Length: 0\r\n\r\n".encode()

        def write(self, buffer: bytes, timeout: float | None = None) -> None:
            assert not self.closed

        def close(self) -> None:
            self.closed = True

        def start_tls(
            self,
            ssl_context: ssl.SSLContext,
            server_hostname: str | None = None,
            timeout: float | None = None,
        ) -> Self:
            assert server_hostname == "auth.openai.com"
            assert ssl_context.verify_mode == ssl.CERT_REQUIRED
            assert ssl_context.check_hostname
            return self  # Synthetic wire only; real TLS/UDS is exercised separately.

        def get_extra_info(self, info: str) -> None:
            return None

    opened: list[Stream] = []

    def connect(
        backend: SyncBackend,
        path: str,
        timeout: float | None = None,
        socket_options: object = None,
    ) -> Stream:
        assert path == "/runtime/auth-egress.sock"
        stream = Stream()
        opened.append(stream)
        return stream

    def deny_tcp(*args: object, **kwargs: object) -> None:
        raise AssertionError("Only the synthetic UDS backend is permitted")

    monkeypatch.setattr(SyncBackend, "connect_unix_socket", connect)
    monkeypatch.setattr(SyncBackend, "connect_tcp", deny_tcp)
    with FixedClient(lambda: None) as client:
        transport = client.client._transport
        assert (
            isinstance(transport, httpx.HTTPTransport) and transport._pool._max_connections == 100
        )
        for status in (403, 404):
            assert (
                client.post("https://auth.openai.com/api/accounts/deviceauth/token").status_code
                == status
            )
            assert opened[-1].closed, "A poll must not retain the relay's 15s connection budget"
        assert len(opened) == 2


@pytest.mark.parametrize(
    "size,redirect", [(1024 * 1024, False), (1024 * 1024 + 1, False), (0, True)]
)
def test_fixed_client_decoded_body_limit_and_redirect(size: int, redirect: bool) -> None:
    from unittest.mock import patch

    from omnis_hermes.management_oauth import FixedClient

    def response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302 if redirect else 200,
            content=b"x" * size,
            headers={"Location": "https://example.invalid"} if redirect else {},
        )

    with (
        patch.object(httpx, "HTTPTransport", return_value=httpx.MockTransport(response)),
        FixedClient(lambda: None) as client,
    ):
        if redirect or size > 1024 * 1024:
            with pytest.raises(ValueError):
                client.post("https://auth.openai.com/oauth/token")
        else:
            assert len(client.post("https://auth.openai.com/oauth/token").content) == size


def test_fixed_client_post_tls_trace_rechecks_current_authority() -> None:
    from unittest.mock import patch

    from omnis_hermes.management_oauth import FixedClient

    expired = False

    def guard() -> None:
        if expired:
            raise ValueError("Expired owner")

    def wire(request: httpx.Request) -> httpx.Response:
        nonlocal expired
        expired = True  # A synchronous transport cut after the HTTPX request hook.
        request.extensions["trace"]("http11.send_request_headers.started", {})
        raise AssertionError("Expired authority reached HTTP headers")

    with (
        patch.object(httpx, "HTTPTransport", return_value=httpx.MockTransport(wire)),
        FixedClient(guard) as client,
    ):
        with pytest.raises(ValueError, match="Expired owner"):
            client.post("https://auth.openai.com/oauth/token")


@pytest.mark.asyncio
async def test_stop_lifeline_revokes_at_real_http_cleanup(tmp_path: Path) -> None:
    import asyncio
    import os
    from unittest.mock import patch

    from httpcore import NetworkStream, Origin, Request
    from httpcore._sync.http11 import HTTP11Connection
    from omnis_hermes import management_http, runtime_host
    from omnis_hermes.management_oauth import FixedClient, NativeOAuth

    host = runtime_host.RuntimeHost(tmp_path)
    host.state = "MANAGEMENT"
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000
    read_fd = host._open_management_lifeline()
    owner = NativeOAuth.from_owner_fd(read_fd)
    owner.session = {"cancelled": False}
    owner.deadline_ns = host.deadline_ns
    owner.expires_ns = host.deadline_ns
    writes: list[bytes] = []

    class Stream(NetworkStream):
        def write(self, data: bytes, timeout: object = None) -> None:
            writes.append(data)

        def read(self, max_bytes: int, timeout: object = None) -> bytes:
            return b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"

        def close(self) -> None:
            pass

        def get_extra_info(self, info: str) -> None:
            return None

    def send() -> None:
        with FixedClient(owner.guard) as client:
            connection = HTTP11Connection(Origin(b"https", b"auth.openai.com", 443), Stream())
            try:
                response = connection.handle_request(
                    Request(
                        b"POST",
                        b"https://auth.openai.com/oauth/token",
                        headers=[(b"Host", b"auth.openai.com"), (b"Content-Length", b"0")],
                        content=b"",
                        extensions={"trace": client._trace},
                    )
                )
                response.close()
            finally:
                connection.close()

    sent, closing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class Reader:
        async def readuntil(self, sep: bytes) -> bytes:
            sent.set()
            await asyncio.Event().wait()
            return b""

    class Writer:
        def write(self, raw: bytes) -> None:
            pass

        async def drain(self) -> None:
            pass

        def close(self) -> None:
            pass

        async def wait_closed(self) -> None:
            closing.set()
            await release.wait()

    async def connect(*args: object, **kwargs: object) -> tuple[Reader, Writer]:
        return Reader(), Writer()

    try:
        send()
        assert sum(bool(x) for x in writes) == 1
        writes.clear()

        async def pending_request() -> None:
            await management_http.request(
                1,
                "synthetic",
                "POST",
                "/api/auth/codex/flow/status",
                {},
                dispatch_guard=lambda: None,
            )

        with patch.object(asyncio, "open_connection", connect):
            host.settings_task = asyncio.create_task(pending_request())
            await asyncio.wait_for(sent.wait(), 1)
            stopper = asyncio.create_task(host.stop())
            try:
                await asyncio.wait_for(closing.wait(), 1)
                assert host.state == "STOPPING"
                with pytest.raises(ValueError):
                    send()
                assert writes == []
            finally:
                release.set()
                await asyncio.wait_for(stopper, 1)
    finally:
        host._revoke_management_lifeline()
        os.close(read_fd)


@pytest.mark.asyncio
async def test_lifeline_child_observes_owner_eof_without_signal(tmp_path: Path) -> None:
    import asyncio
    import os
    import sys

    from omnis_hermes import management_oauth, runtime_host

    host = runtime_host.RuntimeHost(tmp_path)
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000
    reader = host._open_management_lifeline()
    source = str(Path(management_oauth.__file__).resolve().parents[1])
    code = (
        "import sys,time,select;sys.path.insert(0," + repr(source) + ");"
        "from omnis_hermes.management_oauth import NativeOAuth;"
        "o=NativeOAuth.from_owner_fd(0);o.session={'cancelled':False};"
        "o.deadline_ns=o.expires_ns=time.monotonic_ns()+4_000_000_000;"
        "o.guard();print('ALLOWED',flush=True);select.select([0],[],[],2);\n"
        "try:o.guard()\n"
        "except ValueError:print('DENIED',flush=True)\n"
        "else:raise AssertionError('owner EOF admitted')\n"
    )
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-B",
        "-c",
        code,
        stdin=reader,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        close_fds=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
    )
    os.close(reader)
    try:
        assert child.stdout is not None
        assert await asyncio.wait_for(child.stdout.readline(), 1) == b"ALLOWED\n"
        await host.stop()
        output, errors = await asyncio.wait_for(child.communicate(), 3)
        assert child.returncode == 0 and output == b"DENIED\n" and errors == b""
    finally:
        host._revoke_management_lifeline()
        if child.returncode is None:
            child.kill()
        await child.wait()


def test_lifeline_missing_wrong_mode_identity_and_eof_fail_closed(tmp_path: Path) -> None:
    import os

    from omnis_hermes.management_oauth import NativeOAuth
    from omnis_hermes.runtime_host import RuntimeHost

    with pytest.raises(ValueError):
        NativeOAuth().guard()
    host = RuntimeHost(tmp_path)
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000
    reader = host._open_management_lifeline()
    try:
        assert host.management_lifeline_write is not None
        with pytest.raises(ValueError):
            NativeOAuth.from_owner_fd(host.management_lifeline_write)
        owner = NativeOAuth.from_owner_fd(reader)
        owner.session = {"cancelled": False}
        owner.deadline_ns = owner.expires_ns = time.monotonic_ns() + 4_000_000_000
        owner.guard()
        identity = owner.owner_identity
        owner.owner_identity = (0, 0)
        with pytest.raises(ValueError):
            owner.guard()
        owner.owner_identity = identity
        owner.guard()
        host._revoke_management_lifeline()
        with pytest.raises(ValueError):
            owner.guard()
    finally:
        host._revoke_management_lifeline()
        os.close(reader)


def test_typed_presend_denial_does_not_mask_postheader_uncertainty() -> None:
    from omnis_hermes.management_oauth import AuthAdmissionDenied, FixedClient

    denied = False

    def guard() -> None:
        if denied:
            raise AuthAdmissionDenied("synthetic revoked owner")

    with FixedClient(guard) as client:
        denied = True
        with pytest.raises(AuthAdmissionDenied):
            client.trace("http11.send_request_headers.started", {})
        denied = False
        client.trace("http11.send_request_headers.started", {})
        denied = True
        with pytest.raises(ValueError) as error:
            client.trace("http11.send_request_body.started", {})
        assert not isinstance(error.value, AuthAdmissionDenied)


@pytest.mark.asyncio
async def test_management_spawn_failure_closes_lifeline(tmp_path: Path) -> None:
    from omnis_hermes.runtime_host import RuntimeHost, TestLaunch

    host = RuntimeHost(tmp_path, _test_management=TestLaunch((str(tmp_path / "absent"),), tmp_path))
    host.state = "MANAGEMENT"
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000
    with pytest.raises(OSError):
        await host._settings_native("read", None)
    assert host.management_lifeline_write is None
    assert host.process is None


def test_native_handle_retained_before_worker_and_cancel_waits_for_settlement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from omnis_hermes import management_oauth

    entered, release = threading.Event(), threading.Event()
    sessions: dict[str, dict[str, object]] = {}
    lock = threading.RLock()

    def worker(sid: str) -> None:
        assert sid in sessions
        entered.set()
        release.wait(2)

    from types import SimpleNamespace

    native = SimpleNamespace(
        _oauth_sessions=sessions, _oauth_sessions_lock=lock, _codex_full_login_worker=worker
    )
    original = importlib.import_module
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: native if name == "hermes_cli.web_routers.oauth" else original(name),
    )
    import os

    from omnis_hermes.runtime_host import RuntimeHost

    host = RuntimeHost(Path("unused"))
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000
    reader = host._open_management_lifeline()
    owner = management_oauth.NativeOAuth.from_owner_fd(reader)
    assert hasattr(owner, "revoke"), "Native Stop fence missing"
    lease = {
        "operation_id": str(uuid4()),
        "boot": str(uuid4()),
        "generation": 1,
        "epoch": 1,
        "deadline_ns": time.monotonic_ns() + 1_000_000_000,
    }
    try:
        assert owner.operate("connect", lease)["oauth"] == "STARTING"
        assert entered.wait(1)
        owner.revoke()
        with pytest.raises(ValueError, match="expired"):
            owner.guard()
        assert owner.operate("cancel", lease)["oauth"] == "CANCELLING"
        with pytest.raises(ValueError):
            owner.operate("connect", {**lease, "operation_id": str(uuid4())})
        release.set()
        assert owner.thread is not None
        owner.thread.join(1)
        assert owner.operate("status", lease)["oauth"] == "CANCELLED"
        assert len(sessions) == 0
    finally:
        release.set()
        if owner.thread:
            owner.thread.join(2)
        host._revoke_management_lifeline()
        os.close(reader)


@pytest.mark.parametrize("fault", ["transport", "status", "subclass"])
def test_native_oauth_failure_marker_is_finite_and_secret_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], fault: str
) -> None:
    import os
    from types import SimpleNamespace

    from omnis_hermes import management_oauth
    from omnis_hermes.runtime_host import RuntimeHost

    secret = "PRIVATE_DIAGNOSTIC_SENTINEL"

    class PrivateReadError(httpx.ReadError):
        def __str__(self) -> str:
            raise AssertionError("Exception text must not be inspected")

    sessions: dict[str, dict[str, object]] = {}

    def wire(request: httpx.Request) -> httpx.Response:
        if fault == "status":
            return httpx.Response(502, content=secret.encode())
        raise (PrivateReadError if fault == "subclass" else httpx.ReadError)(secret)

    def worker(sid: str) -> None:
        try:
            with management_oauth.client_factory() as client:
                response = client.post("https://auth.openai.com/api/accounts/deviceauth/token")
                if response.status_code != 200:
                    raise RuntimeError(secret)
        except Exception:
            sessions[sid]["status"] = "error"  # Native worker's swallowed-error seam.

    native = SimpleNamespace(
        _oauth_sessions=sessions,
        _oauth_sessions_lock=threading.RLock(),
        _codex_full_login_worker=worker,
    )
    original = importlib.import_module
    monkeypatch.setattr(
        importlib,
        "import_module",
        lambda name: native if name == "hermes_cli.web_routers.oauth" else original(name),
    )
    monkeypatch.setattr(httpx, "HTTPTransport", lambda **kwargs: httpx.MockTransport(wire))
    host = RuntimeHost(tmp_path)
    host.deadline_ns = time.monotonic_ns() + 4_000_000_000
    reader = host._open_management_lifeline()
    owner = management_oauth.NativeOAuth.from_owner_fd(reader)
    lease = {
        "operation_id": str(uuid4()),
        "boot": str(uuid4()),
        "generation": 1,
        "epoch": 1,
        "deadline_ns": host.deadline_ns,
    }
    try:
        owner.operate("connect", lease)
        assert owner.thread is not None
        owner.thread.join(1)
        assert not owner.active
        assert owner.operate("status", lease)["oauth"] == "INDETERMINATE"
        output = capsys.readouterr()
        expected = {
            "transport": "ReadError 0",
            "status": "HTTP_STATUS 502",
            "subclass": "UNKNOWN 0",
        }[fault]
        assert output.out == ""
        assert output.err == f"OMNIS_OAUTH_FAILURE TOKEN_POLL {expected}\n"
        assert secret not in output.err
    finally:
        if owner.thread:
            owner.thread.join(1)
        host._revoke_management_lifeline()
        os.close(reader)


@pytest.mark.asyncio
async def test_oauth_host_failure_and_management_discard_channel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from omnis_hermes import management_oauth, runtime_host
    from omnis_hermes.management_contract import SELECTION

    host = runtime_host.RuntimeHost(tmp_path)
    host.state = "MANAGEMENT"
    monkeypatch.setattr(host, "_settings_native", AsyncMock(return_value=dict(SELECTION)))
    await host._settings_run({"operation_id": str(uuid4()), "action": "connect"})
    assert host.settings_result is not None and host.settings_result["status"] == "INDETERMINATE"
    assert capsys.readouterr().err == "OMNIS_OAUTH_FAILURE HOST LEASE 0\n"

    host = runtime_host.RuntimeHost(tmp_path)
    stream = asyncio.StreamReader()
    stream.feed_data(b"PRIVATE_SENTINEL\nOMNIS_OAUTH_FAILURE TOKEN_POLL PRIVATE_SENTINEL 0\n")
    stream.feed_data(
        b"OMNIS_OAUTH_FAILURE TOKEN_POLL ReadError 00\nOMNIS_OAUTH_FAILURE TOKEN_POLL HTTP_STATUS 999\n"
    )
    stream.feed_data(b"OMNIS_OAUTH_FAILURE TOKEN_")
    stream.feed_data(b"POLL ReadError 0\nOMNIS_OAUTH_FAILURE TOKEN_POLL ReadError 0\n")
    stream.feed_eof()
    await host._discard_management_output(stream)
    assert capsys.readouterr().err == "OMNIS_OAUTH_FAILURE TOKEN_POLL ReadError 0\n"

    class PrivateString(str):
        pass

    assert management_oauth.oauth_failure(PrivateString("TOKEN_POLL"), "ReadError", 0) is None
    assert management_oauth.oauth_failure("TOKEN_POLL", "HTTP_STATUS", True) is None
    assert management_oauth.oauth_failure("TOKEN_POLL", "PRIVATE_SENTINEL", 0) is None

    import sys
    from types import SimpleNamespace
    from unittest.mock import patch

    def broken_write(value: str) -> None:
        raise OSError("PRIVATE_SENTINEL")

    host = runtime_host.RuntimeHost(tmp_path)
    host.state = "MANAGEMENT"
    monkeypatch.setattr(host, "_settings_native", AsyncMock(return_value=dict(SELECTION)))
    with patch.object(sys, "stderr", SimpleNamespace(write=broken_write)):
        await host._settings_run({"operation_id": str(uuid4()), "action": "connect"})
    assert host.settings_result is not None and host.settings_result["status"] == "INDETERMINATE"
