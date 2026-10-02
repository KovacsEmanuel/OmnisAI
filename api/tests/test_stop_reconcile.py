"""Reconciliation input and process boundary; no live database or Docker."""

import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from omnis.modules.instance.domain import ControlConflict
from omnis.modules.instance.records import InstanceRecord, LeaseRecord
from omnis.modules.instance.service import InstanceService
from omnis.modules.instance.stop_contract import StopReconciliation
from test_stop_control import arm_command


def reconciliation_payload() -> dict[str, object]:
    command = arm_command()
    command.pop("op")
    return {
        "version": 1,
        "reconciliation_id": str(uuid4()),
        "system_identifier": "123456789",
        "grant": {**command, "version": 1, "state": "STOP_PENDING", "owner_uuid": str(uuid4())},
        "completion_sha256": "b" * 64,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", 1.0),
        ("reconciliation_id", "not-a-uuid"),
        ("system_identifier", 123456789),
        ("completion_sha256", "B" * 64),
        ("sql", "DROP TABLE instance_control"),
    ],
)
def test_reconciliation_dto_refuses_coercion_or_unknown_fields(field: str, value: object) -> None:
    body = reconciliation_payload()
    StopReconciliation.model_validate(body)
    with pytest.raises(ValidationError):
        StopReconciliation.model_validate({**body, field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("generation", 2.0),
        ("owner_epoch", True),
        ("state", []),
        ("capability", "synthetic-marker"),
        ("owner_uuid", "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"),
        ("inventory", {"inode": 1.0}),
    ],
)
def test_reconciliation_grant_is_exact(field: str, value: object) -> None:
    body = reconciliation_payload()
    grant = body["grant"]
    assert isinstance(grant, dict)
    with pytest.raises(ValidationError):
        StopReconciliation.model_validate({**body, "grant": {**grant, field: value}})


def test_job_requires_eof_within_total_input_deadline(tmp_path: Path) -> None:
    with subprocess.Popen(
        [sys.executable, "-I", "-m", "omnis.stop_reconcile"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={},
        cwd=tmp_path,
    ) as process:
        assert process.stdin is not None
        process.stdin.write(json.dumps(reconciliation_payload()).encode())
        process.stdin.flush()
        try:
            process.wait(timeout=7)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
            pytest.fail("Job failed to bound unclosed stdin")
        assert process.returncode == 4
        assert process.stdout is not None
        reply = json.loads(process.stdout.read())
        assert reply["error"] == "RECONCILIATION_TIMEOUT"


@pytest.mark.parametrize("case", ["missing_env", "foreign_system", "ambient_pg", "query", "argv"])
def test_valid_job_input_refuses_unsafe_configuration_before_io(tmp_path: Path, case: str) -> None:
    body = reconciliation_payload()
    env = {"OMNIS_DATABASE_URL": "synthetic_secret_marker", "OMNIS_EXPECTED_SYSTEM_ID": "123456789"}
    args: list[str] = []
    if case == "missing_env":
        env = {}
    elif case == "foreign_system":
        env["OMNIS_EXPECTED_SYSTEM_ID"] = "1"
    elif case == "ambient_pg":
        env["PGHOSTADDR"] = "synthetic_secret_marker"
    elif case == "query":
        env["OMNIS_DATABASE_URL"] = (
            "postgresql+psycopg://localhost/db?password=synthetic_secret_marker"
        )
    else:
        args = ["--sql", "synthetic_secret_marker"]
    result = subprocess.run(
        [sys.executable, "-I", "-m", "omnis.stop_reconcile", *args],
        input=json.dumps(body).encode(),
        capture_output=True,
        env=env,
        cwd=tmp_path,
        timeout=8,
    )
    assert result.returncode == 4 and result.stderr == b""
    reply = json.loads(result.stdout)
    assert reply["ok"] is False
    if case != "argv":
        assert reply["correlation_id"] == body["reconciliation_id"]
    assert b"synthetic_secret_marker" not in result.stdout


@pytest.mark.asyncio
async def test_uncertain_grant_refuses_before_any_database_operation() -> None:
    body = reconciliation_payload()
    grant = body["grant"]
    assert isinstance(grant, dict)
    grant["state"] = "STOP_UNCERTAIN"
    engine = Mock(spec=AsyncEngine)
    with pytest.raises(ControlConflict):
        await InstanceService(engine).reconcile_stop(StopReconciliation.model_validate(body))
    engine.begin.assert_not_called()


@pytest.mark.parametrize(
    "mutation", [None, "epoch", "generation", "admission", "owner", "finalized"]
)
@pytest.mark.asyncio
async def test_closed_reconciliation_checks_exact_state_not_lease_liveness(
    mutation: str | None,
) -> None:
    request = StopReconciliation.model_validate(reconciliation_payload())
    grant = request.grant
    instance = InstanceRecord(
        id=1,
        instance_id=grant.instance_id,
        admission_open=mutation == "admission",
        shutdown_command_id=grant.command_id,
        generation=3 if mutation == "generation" else grant.generation,
        quiesced_generation=grant.generation,
        quiesced_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    lease = LeaseRecord(
        id=1,
        owner=uuid4() if mutation == "owner" else None,
        epoch=2 if mutation == "epoch" else grant.owner_epoch,
        expires_at=None,
    )
    shutdown = {
        "command_id": grant.command_id,
        "kind": "SHUTDOWN",
        "expected_generation": grant.generation - 1,
        "result_generation": grant.generation,
        "owner_epoch": grant.owner_epoch,
    }
    finalized = {
        "command_id": grant.finalize_command_id,
        "kind": "FINALIZE",
        "expected_generation": grant.generation,
        "result_generation": grant.generation,
        "owner_epoch": 99 if mutation == "finalized" else grant.owner_epoch,
    }
    results = []
    for row in (shutdown, finalized):
        result = Mock()
        result.mappings.return_value.one_or_none.return_value = row
        results.append(result)
    connection = Mock(spec=AsyncConnection)
    connection.execute = AsyncMock(side_effect=results)
    service = InstanceService(Mock(spec=AsyncEngine))
    if mutation is None:
        await service._closed_stop(connection, instance, lease, grant)
        assert connection.execute.await_count == 2
    else:
        with pytest.raises(ControlConflict):
            await service._closed_stop(connection, instance, lease, grant)


def test_job_hard_deadline_survives_a_blocked_async_client(tmp_path: Path) -> None:
    script = """import sys, time
import omnis.stop_reconcile as job
sys.argv = ["stop_reconcile"]
job.JOB_SECONDS = 1
async def blocked(request):
    time.sleep(30)
job.execute = blocked
raise SystemExit(job.main())
"""
    body = reconciliation_payload()
    result = subprocess.run(
        [sys.executable, "-I", "-c", script],
        input=json.dumps(body).encode(),
        env={},
        cwd=tmp_path,
        capture_output=True,
        timeout=5,
    )
    assert result.returncode == 4 and result.stderr == b""
    assert json.loads(result.stdout) == {
        "ok": False,
        "correlation_id": body["reconciliation_id"],
        "error": "RECONCILIATION_TIMEOUT",
    }


@pytest.mark.parametrize("size,accepted", [(16384, True), (16385, False)])
def test_stdin_exact_byte_boundary(tmp_path: Path, size: int, accepted: bool) -> None:
    from omnis.stop_reconcile import read_request

    body = reconciliation_payload()
    data = json.dumps(body).encode()
    path = tmp_path / "input.json"
    path.write_bytes(data + b" " * (size - len(data)))
    with path.open("rb") as stream:
        if accepted:
            assert read_request(stream.fileno()).model_dump(mode="json") == body
        else:
            with pytest.raises(ValueError):
                read_request(stream.fileno())


def test_reconciliation_has_real_service_and_fixed_entrypoint() -> None:
    assert callable(getattr(InstanceService, "reconcile_stop", None))
    assert importlib.util.find_spec("omnis.stop_reconcile") is not None


@pytest.mark.parametrize(
    "data",
    [b"{}", b'{"version":1,"version":1}', b" " * 16385],
    ids=["empty", "duplicate", "oversize"],
)
def test_job_invalid_input_is_sanitized_and_never_uses_ambient_config(
    tmp_path: Path,
    data: bytes,
) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-m", "omnis.stop_reconcile"],
        input=data,
        env={
            "OMNIS_DATABASE_URL": "synthetic_secret_marker",
            "OMNIS_EXPECTED_SYSTEM_ID": "123456789",
        },
        capture_output=True,
        cwd=tmp_path,
        timeout=8,
    )
    assert result.returncode == 4
    reply = json.loads(result.stdout)
    assert reply["ok"] is False
    assert set(reply) == {"ok", "correlation_id", "error"}
    assert b"synthetic_secret_marker" not in result.stdout + result.stderr
    assert result.stderr == b""
