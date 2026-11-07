"""SOURCE: real ASGI boundary and bounded OS pipe, no services/DB/browser."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from omnis.api import create_app
from omnis.modules.diagnostics import reader, service
from omnis.modules.diagnostics.reader import read_records, validate_owner
from omnis.modules.diagnostics.schemas import UiEvent
from omnis.security import host_origin
from omnis.security.sessions import SessionGrant, SessionStore

ORIGIN = "http://127.0.0.1:8765"
PATH = "/api/v1/diagnostics/ui-events"


def event() -> dict[str, object]:
    return {
        "version": 1,
        "source": "browser_untrusted",
        "event_id": str(uuid4()),
        "surface": "engagement_overview",
        "site": "stop_request",
        "action": "REQUEST",
        "outcome": "UNCONFIRMED",
        "error_code": None,
        "correlation_id": None,
        "run_id": str(uuid4()),
        "command_id": str(uuid4()),
    }


@pytest.mark.parametrize(
    "change",
    [
        {"message": "synthetic_secret_must_not_enter_log"},
        {"version": True},
        {"site": "synthetic_secret_must_not_enter_log"},
        {"run_id": "not-uuid"},
        {"outcome": 1},
        {"error_code": "invented"},
        {"source": "server_authoritative"},
    ],
)
def test_strict_event_refuses_free_text_and_wrong_types(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        UiEvent.model_validate_json(json.dumps(event() | change))


@pytest.mark.asyncio
async def test_asgi_sink_reader_same_correlation_and_all_boundary_denials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    grant = SessionGrant("source-only-synthetic-session")
    monkeypatch.setattr(host_origin, "readiness_reason", AsyncMock(return_value=None))
    monkeypatch.setattr(SessionStore, "authenticate", AsyncMock(return_value=grant))
    read, write = os.pipe2(os.O_NONBLOCK)
    monkeypatch.setattr(service, "stderr_fd", lambda: os.dup(write))
    app = create_app()
    headers = {"origin": ORIGIN, "x-csrf-token": grant.csrf}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as http:
            http.cookies.set("omnis_session", "source-only-cookie")
            good = event()
            response = await http.post(PATH, json=good, headers=headers)
            assert response.status_code == 202
            assert response.json()["state"] == "RECORDED"
            records = read_records(os.read(read, 8192))
            assert len(records) == 1
            assert records[0].event.model_dump(mode="json") == good
            assert records[0].request_correlation_id == response.headers["x-correlation-id"]
            assert records[0].source == "browser_untrusted"
            encoded = json.dumps(good).encode()
            assert len(encoded) < 4096
            padded = await http.post(
                PATH,
                content=encoded.ljust(4096),
                headers={**headers, "content-type": "application/json"},
            )
            assert padded.status_code == 202 and padded.json()["state"] == "RECORDED"
            assert len(read_records(os.read(read, 8192))) == 1
            denied = [
                await http.post(PATH, json=good, headers={**headers, "host": "foreign.invalid"}),
                await http.post(
                    PATH, json=good, headers={**headers, "origin": "https://foreign.invalid"}
                ),
                await http.post(PATH, json=good, headers={"origin": ORIGIN}),
                await http.post(PATH + "?after=1", json=good, headers=headers),
                await http.post(
                    PATH, content=json.dumps(good)[:-1] + ',"version":1}', headers=headers
                ),
                await http.post(PATH, content=b" " * 4097, headers=headers),
                await http.post(
                    PATH,
                    json=good | {"message": "synthetic_secret_must_not_enter_log"},
                    headers=headers,
                ),
            ]
            assert [r.status_code for r in denied] == [400, 403, 403, 400, 422, 413, 422]
            monkeypatch.setattr(service, "stderr_fd", lambda: (_ for _ in ()).throw(OSError()))
            unavailable = await http.post(PATH, json=good, headers=headers)
            assert unavailable.status_code == 202
            assert unavailable.json()["accepted"] is True
            assert unavailable.json()["state"] == "UNAVAILABLE"
            http.cookies.clear()
            assert (await http.post(PATH, json=good, headers=headers)).status_code == 401
            with pytest.raises(BlockingIOError):
                os.read(read, 8192)
            assert all("synthetic_secret" not in r.text for r in denied)
    finally:
        os.close(read)
        os.close(write)


def test_atomic_nonblocking_rate_budget_failure_and_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read, write = os.pipe2(os.O_NONBLOCK)
    monkeypatch.setattr(service, "stderr_fd", lambda: os.dup(write))
    payload = UiEvent.model_validate_json(json.dumps(event()))
    sink = service.DiagnosticSink()
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(lambda _: sink.emit(payload, str(uuid4())), range(32)))
        assert outcomes.count("RECORDED") <= service.BURST
        assert set(outcomes) <= {"RECORDED", "BUSY", "RATE_LIMITED"}
        assert len(read_records(os.read(read, 65536))) == outcomes.count("RECORDED")
        assert sink.lock.acquire(blocking=False)
        try:
            assert sink.emit(payload, str(uuid4())) == "BUSY"
        finally:
            sink.lock.release()
        for _ in range(service.BURST):
            sink.emit(payload, str(uuid4()))
        assert sink.emit(payload, str(uuid4())) == "RATE_LIMITED"
        charged = service.DiagnosticSink()
        charged.bytes = service.TOTAL_BYTES
        assert charged.emit(payload, str(uuid4())) == "BUDGET_EXHAUSTED"
        for _ in range(service.ATTEMPTS):
            sink.emit(payload, str(uuid4()))
        assert sink.emit(payload, str(uuid4())) == "BUDGET_EXHAUSTED"
        monkeypatch.setattr(service, "stderr_fd", lambda: (_ for _ in ()).throw(OSError()))
        assert service.DiagnosticSink().emit(payload, str(uuid4())) == "UNAVAILABLE"
        monkeypatch.setattr(service, "stderr_fd", lambda: os.dup(write))
        while True:
            try:
                os.write(write, b"x" * 4096)
            except BlockingIOError:
                break
        assert service.DiagnosticSink().emit(payload, str(uuid4())) == "BACKPRESSURED"
    finally:
        os.close(read)
        os.close(write)


def test_reader_refuses_wrong_owner_and_marked_secret_records() -> None:
    owner = {
        "Id": "a" * 64,
        "Config": {
            "Labels": {
                "com.docker.compose.project": "omnis-fixture",
                "com.docker.compose.service": "api",
                "org.omnis.start-attempt": "b" * 32,
            },
            "Tty": False,
        },
        "HostConfig": {"LogConfig": {"Type": "json-file"}},
    }
    validate_owner(owner, "a" * 64, "omnis-fixture", "b" * 32)
    with pytest.raises(ValueError):
        validate_owner(owner, "c" * 64, "omnis-fixture", "b" * 32)
    with pytest.raises(ValueError):
        validate_owner(owner, "a" * 64, "other-project", "b" * 32)
    with pytest.raises(ValueError):
        read_records(b'{"marker":"OMNIS_UI_DIAGNOSTIC_V1","message":"synthetic_secret"}\n')
    assert read_records(b"unmarked operational line\n") == []
    with pytest.raises(ValueError):
        read_records(b'{"marker":"OMNIS_UI_DIAGNOSTIC_V1"')


@pytest.mark.parametrize("field", list(event()))
def test_all_event_fields_are_required(field: str) -> None:
    value = event()
    del value[field]
    with pytest.raises(ValidationError):
        UiEvent.model_validate_json(json.dumps(value))


def test_create_app_export_is_inert_and_reopened_pipe_flags_are_independent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service,
        "stderr_fd",
        lambda: (_ for _ in ()).throw(AssertionError("unexpected sink effect")),
    )
    assert PATH in create_app().openapi()["paths"]
    read, write = os.pipe()
    other = os.open(f"/proc/self/fd/{write}", os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        assert os.get_blocking(write) is True
        assert os.get_blocking(other) is False
    finally:
        os.close(other)
        os.close(write)
        os.close(read)


def test_sink_close_failure_is_not_a_recorded_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    read, write = os.pipe2(os.O_NONBLOCK)
    real_close = os.close
    monkeypatch.setattr(service, "stderr_fd", lambda: os.dup(write))

    def failed_close(fd: int) -> None:
        real_close(fd)
        raise OSError("synthetic close failure")

    try:
        monkeypatch.setattr(os, "close", failed_close)
        sink = service.DiagnosticSink()
        assert (
            sink.emit(UiEvent.model_validate_json(json.dumps(event())), str(uuid4()))
            == "UNAVAILABLE"
        )
        assert sink.lock.acquire(blocking=False)
        sink.lock.release()
    finally:
        monkeypatch.setattr(os, "close", real_close)
        real_close(read)
        real_close(write)


@pytest.mark.parametrize(
    "field,value", [("com.docker.compose.service", "db"), ("org.omnis.start-attempt", "c" * 32)]
)
def test_reader_role_and_start_attempt_are_exact(field: str, value: str) -> None:
    labels = {
        "com.docker.compose.project": "omnis-fixture",
        "com.docker.compose.service": "api",
        "org.omnis.start-attempt": "b" * 32,
    }
    owner = {
        "Id": "a" * 64,
        "Config": {"Labels": labels, "Tty": False},
        "HostConfig": {"LogConfig": {"Type": "json-file"}},
    }
    labels[field] = value
    with pytest.raises(ValueError):
        validate_owner(owner, "a" * 64, "omnis-fixture", "b" * 32)


def test_reader_transport_filters_stderr_and_has_a_restored_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import signal
    import stat
    import time
    from pathlib import Path
    from types import SimpleNamespace

    before = signal.getsignal(signal.SIGALRM)
    owner = {
        "Id": "a" * 64,
        "Config": {
            "Labels": {
                "com.docker.compose.project": "omnis-fixture",
                "com.docker.compose.service": "api",
                "org.omnis.start-attempt": "b" * 32,
            },
            "Tty": False,
        },
        "HostConfig": {"LogConfig": {"Type": "json-file"}},
    }
    resources: list[str] = []
    monkeypatch.setattr(
        Path, "stat", lambda *a, **k: SimpleNamespace(st_mode=stat.S_IFSOCK, st_uid=os.getuid())
    )

    def response(path: str, resource: str, deadline: float, limit: int) -> bytes:
        resources.append(resource)
        assert 0 < deadline - time.monotonic() <= 6
        if resource.endswith("/json"):
            return json.dumps(owner).encode()
        return b"\x02\0\0\0\0\0\0\x04test"

    monkeypatch.setattr(reader, "_get", response)
    assert reader.read_docker("unix:///owned.sock", "a" * 64, "omnis-fixture", "b" * 32) == []
    assert resources[-1].endswith("stdout=0&stderr=1&tail=256&timestamps=0")
    assert signal.getsignal(signal.SIGALRM) == before
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    with pytest.raises(ValueError):
        reader.read_docker("tcp://foreign.invalid", "a" * 64, "omnis-fixture", "b" * 32)
    assert len(resources) == 2
