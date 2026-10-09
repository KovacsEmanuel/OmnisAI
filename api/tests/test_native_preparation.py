"""Native preparation boundary tests; PG tests require the attested parent fixture."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL

from fixtures.b06b_publication.consumer import SOURCE
from omnis.modules.instance.schemas import ControlRequest
from omnis.modules.settings.candidate_material import capture
from omnis.modules.settings.catalog_models import CatalogError


def command() -> dict[str, object]:
    return {
        "op": "native_prepare",
        "schema_version": 1,
        "owner_id": str(uuid4()),
        "command_id": str(uuid4()),
        "instance_id": str(uuid4()),
        "expected_generation": 0,
        "expected_epoch": 1,
        "selection_ref": {
            "kind": "execution-selection",
            "id": str(uuid4()),
            "revision": 1,
            "digest": "a" * 64,
        },
    }


def test_control_accepts_explicit_native_prepare() -> None:
    value = command()
    parsed = ControlRequest.model_validate({"version": 1, "capability": "a" * 64, "command": value})
    assert parsed.command.model_dump(mode="json") == value


@pytest.mark.asyncio
async def test_existing_control_socket_dispatches_injected_preparer(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import AsyncMock, Mock

    from sqlalchemy.ext.asyncio import AsyncEngine

    import omnis.transport.local_control as control
    from omnis.modules.instance.service import InstanceService
    from omnis.transport.local_control import LocalControl
    from test_local_control import request

    monkeypatch.setattr(control, "readiness_reason", AsyncMock(return_value=None))
    service = InstanceService(Mock(spec=AsyncEngine))
    value = command()

    async def prepare(cmd: object) -> dict[str, object]:
        return {"ok": True, "preparation_status": "PREPARED"}

    # Existing socket handler is exercised; only DB readiness and consumer are boundary doubles.
    assert "native_prepare" in __import__("inspect").signature(LocalControl).parameters, (
        "native dispatch seam missing"
    )
    async with LocalControl(ipc_directory, service, uuid4(), 1, native_prepare=prepare) as local:
        reply = await request(ipc_directory, local.capability, value)
        assert reply["ok"] is True


@pytest.mark.parametrize(
    "extra_files,extra_bytes,accepted",
    [(6, 0, True), (7, 0, False), (1, 16384, True), (1, 16385, False)],
)
def test_declared_file_and_aggregate_limits_are_exact(
    extra_files: int, extra_bytes: int, accepted: bool
) -> None:
    from omnis.modules.runs.native_preparation_models import mapping, prepare_packages, sequence
    from omnis.modules.settings.candidate_material import digest
    from omnis.modules.settings.catalog_schema import canonical, load_json

    material, sources, _ = capture(
        [str(SOURCE / "b06b-publish-contract")], str(SOURCE / "profile.yaml")
    )
    source = sources[0]
    manifest = mapping(load_json(material["packages/0/omnis.yaml"]))
    added = [f"assets/extra-{index}.txt" for index in range(extra_files)]
    manifest["support_files"] = [*sequence(manifest["support_files"]), *added]
    material["packages/0/omnis.yaml"] = canonical(manifest)
    for name in added:
        material["packages/0/" + name] = b""
    if extra_bytes:
        present = sum(len(raw) for path, raw in material.items() if path.startswith("packages/0/"))
        material["packages/0/" + added[0]] = b"x" * (extra_bytes - present)
    listing = [
        {"path": path.removeprefix("packages/0/"), "size": len(raw), "sha256": digest(raw)}
        for path, raw in sorted(material.items())
        if path.startswith("packages/0/")
    ]
    source = {**source, "files": listing, "package_digest": digest(canonical(listing))}
    ref = {"kind": "package", "id": str(uuid4()), "revision": 1, "digest": source["package_digest"]}
    if accepted:
        result = prepare_packages(material, [(ref, source)])
        assert len(sequence(result[0]["files"])) == 10 + extra_files
    else:
        with pytest.raises(CatalogError):
            prepare_packages(material, [(ref, source)])


def test_catalog_root_rejects_replaceable_ancestor(tmp_path: Path) -> None:
    from omnis.modules.runs.native_preparation import existing_private_root

    parent = tmp_path / "shared"
    parent.mkdir(mode=0o777)
    parent.chmod(0o777)
    child = parent / "private"
    child.mkdir(mode=0o700)
    with pytest.raises(ValueError):
        existing_private_root(child)


def test_worker_echo_ref_rejects_boolean_revision() -> None:
    from omnis.modules.runs.native_preparation_models import mapping, validate_worker
    from omnis.modules.settings import candidate_store as store

    bundle = bundle_fixture()
    result = worker_fixture(bundle)
    result["bundle_ref"] = {**mapping(result["bundle_ref"]), "revision": True}
    with pytest.raises(CatalogError):
        validate_worker(result, store.reference(bundle), bundle)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("expected_epoch", True),
        ("expected_generation", True),
        ("schema_version", True),
        ("owner_id", "not-a-uuid"),
        ("unknown", None),
    ],
)
def test_prepare_request_rejects_before_io(field: str, bad: object) -> None:
    from omnis.modules.runs.native_preparation import validate_request

    value = {k: v for k, v in command().items() if k != "op"}
    value[field] = bad
    with pytest.raises(CatalogError):
        validate_request("prepare", value)


@pytest.mark.parametrize(
    "field", ["metadata", "requirements", "credentials", "setup", "preprocess"]
)
def test_native_frontmatter_directives_denied(field: str) -> None:
    from omnis.modules.runs.native_preparation_models import frontmatter

    with pytest.raises(CatalogError):
        frontmatter(
            f"---\nname: probe\ndescription: inert\n{field}: forbidden\n---\nbody\n".encode(),
            "probe",
        )


@pytest.mark.parametrize(
    "raw", [b"\xef\xbb\xbftext", b"text\r\n", b"text\x00", b"\xff", b"a" * 8193]
)
def test_native_documents_reject_normalization_and_overflow(raw: bytes) -> None:
    from omnis.modules.runs.native_preparation_models import document

    with pytest.raises(CatalogError):
        document(raw)


@pytest.mark.asyncio
async def test_private_cli_prepare_only_uses_control_socket(
    ipc_directory: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import asyncio
    import os
    from unittest.mock import AsyncMock, Mock

    from sqlalchemy.ext.asyncio import AsyncEngine

    import omnis.transport.local_control as control
    from fixtures.b06b_publication.consumer import cli_command
    from omnis.modules.instance.schemas import NativePrepareCommand
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.settings import candidate_store as store
    from omnis.modules.settings.catalog_schema import canonical, load_json
    from omnis.transport.local_control import LocalControl

    monkeypatch.setattr(control, "readiness_reason", AsyncMock(return_value=None))
    called: list[dict[str, object]] = []
    expected = {
        "ok": True,
        "preparation_status": "PREPARED",
        "bundle_ref": store.reference(bundle_fixture()),
        "receipt_ref": {
            "kind": "native-preparation-receipt",
            "id": str(uuid4()),
            "revision": 1,
            "digest": "d" * 64,
        },
    }

    async def prepare(value: NativePrepareCommand) -> dict[str, object]:
        called.append(value.model_dump(mode="json"))
        return dict(expected)

    value = command()
    request_file = tmp_path / "request.json"
    request_file.write_bytes(canonical({k: v for k, v in value.items() if k != "op"}))
    request_file.chmod(0o600)
    async with LocalControl(
        ipc_directory, InstanceService(Mock(spec=AsyncEngine)), uuid4(), 1, native_prepare=prepare
    ):
        child = await asyncio.create_subprocess_exec(
            *cli_command(
                "omnis.modules.runs.native_preparation",
                "prepare",
                "--request",
                str(request_file),
                "--control-dir",
                str(ipc_directory),
            ),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "OMNIS_DATABASE_URL": "deliberately-invalid-no-database"},
        )
        stdout, stderr = await asyncio.wait_for(child.communicate(), 10)
        assert child.returncode == 0, stderr
        from omnis.modules.runs.native_preparation_models import mapping

        response = mapping(load_json(stdout))
        assert {k: v for k, v in response.items() if k != "correlation_id"} == expected
        assert called == [value]
    assert not (ipc_directory / "runtime.sock").exists()


def test_bundle_and_worker_exact_validation() -> None:
    from omnis.modules.runs import native_preparation_models as models

    assert callable(getattr(models, "validate_bundle", None)), "bundle validator missing"
    bundle = bundle_fixture()
    ref = {k: bundle[k] for k in ("kind", "id", "revision", "digest")}
    assert models.validate_bundle(ref, bundle) == bundle
    result = worker_fixture(bundle)
    assert models.validate_worker(result, ref, bundle) == result
    import copy

    corrupt = copy.deepcopy(result)
    rows = corrupt["loaded"]
    assert isinstance(rows, list)
    rows[0]["content_b64"] = "eA=="
    with pytest.raises(CatalogError):
        models.validate_worker(corrupt, ref, bundle)
    corrupt = {**result, "native": {**models.mapping(result["native"]), "base_commit": "0" * 40}}
    with pytest.raises(CatalogError):
        models.validate_worker(corrupt, ref, bundle)


@pytest.mark.asyncio
async def test_fenced_transaction_rechecks_owner_after_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from sqlalchemy.ext.asyncio import AsyncEngine

    from omnis.modules.instance.domain import ControlCode, ControlConflict
    from omnis.modules.instance.service import InstanceService

    service = InstanceService(Mock(spec=AsyncEngine))
    assert callable(getattr(service, "native_preparation_commit", None)), (
        "transaction fence missing"
    )
    connection = object()

    @asynccontextmanager
    async def locked() -> AsyncIterator[tuple[object, SimpleNamespace, object]]:
        yield connection, SimpleNamespace(generation=0, shutdown_command_id=None), object()

    verify = AsyncMock(side_effect=[None, ControlConflict(ControlCode.LEASE_LOST)])
    monkeypatch.setattr(service, "_locked", locked)
    monkeypatch.setattr(service, "_require_owner", verify)
    monkeypatch.setattr(service, "_stop_fence", AsyncMock())
    reached = False
    with pytest.raises(ControlConflict, match="LEASE_LOST"):
        async with service.native_preparation_commit(uuid4(), 1, 0) as actual:
            assert actual is connection
            reached = True
    assert reached and verify.await_count == 2


@pytest.mark.asyncio
async def test_runtime_prepare_uses_same_connection_and_fresh_authority(
    ipc_directory: Path,
) -> None:
    import asyncio
    import json
    import time
    from unittest.mock import AsyncMock, Mock

    from omnis.modules.instance.service import InstanceService, RuntimeAuthority
    from omnis.modules.settings import candidate_store as store
    from omnis.supervisor.runtime_client import RuntimeClient

    runtime = RuntimeClient(ipc_directory, generation=0, epoch=1)
    assert callable(getattr(runtime, "prepare", None)), "runtime prepare bridge missing"
    bundle = bundle_fixture()
    runtime.boot, runtime.capability = str(uuid4()), "a" * 64
    seen: list[dict[str, object]] = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        request = json.loads(await reader.readline())
        seen.append(request)
        writer.write(
            json.dumps(
                {
                    "id": request["id"],
                    "boot": runtime.boot,
                    "ok": True,
                    "state": "READY",
                    "drained": False,
                    "assessment_ready": False,
                    "generation": 0,
                    "epoch": 1,
                    "bootstrap_inventory": {
                        "schema_version": 1,
                        "observation": "NATIVE_BOOTSTRAP",
                        "scope": "/state/active",
                        "registry": {
                            "status": "NOT_INITIALIZED",
                            "generation": None,
                            "count": None,
                            "entries": None,
                        },
                        "plugins": {"status": "NOT_INITIALIZED", "count": None, "entries": None},
                    },
                    "preparation": worker_fixture(bundle),
                }
            ).encode()
            + b"\n"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_unix_server(handle, path=str(ipc_directory / "test.sock"))
    service = Mock(spec=InstanceService)
    deadline = time.monotonic_ns() + 4_000_000_000
    service.runtime_authority = AsyncMock(return_value=RuntimeAuthority(0, 1, deadline))
    owner = uuid4()
    try:
        runtime.reader, runtime.writer = await asyncio.open_unix_connection(
            str(ipc_directory / "test.sock")
        )
        result = await runtime.prepare(service, owner, store.reference(bundle), bundle)
        assert result["preparation"] == worker_fixture(bundle)
        service.runtime_authority.assert_awaited_once_with(owner, 1, 0, inert_probe=True)
        assert seen[0]["payload"] == {"bundle_ref": store.reference(bundle), "bundle": bundle}
        assert seen[0]["deadline_ns"] == deadline
    finally:
        await runtime.close()
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_supervisor_catalog_optin_refuses_without_inert_runtime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from unittest.mock import Mock

    import omnis.supervisor.__main__ as supervisor
    from omnis.supervisor.__main__ import run

    monkeypatch.setenv("OMNIS_DATABASE_URL", "unused")
    monkeypatch.setenv("OMNIS_CONTROL_DIR", str(tmp_path))
    monkeypatch.setenv("OMNIS_NATIVE_PREPARATION_CATALOG_ROOT", str(tmp_path))
    monkeypatch.delenv("OMNIS_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("OMNIS_RUNTIME_INERT_PROBE", raising=False)
    acquire = Mock(side_effect=AssertionError("DB accessed before opt-in validation"))
    monkeypatch.setattr(supervisor, "database_engine", acquire)
    with pytest.raises(ValueError, match="preparation opt-in"):
        await run()
    acquire.assert_not_called()


def test_native_consumer_cli_preflight() -> None:
    import subprocess

    from fixtures.b06b_publication.consumer import cli_command

    process = subprocess.run(
        cli_command("omnis.modules.runs.native_preparation", "--help"),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert process.returncode == 0, process.stderr
    assert "prepare" in process.stdout and "readback" in process.stdout


@pytest.mark.parametrize("fault", ["none", "after_t1", "stopped", "wrong_bytes"])
def test_pg_bundle_receipt_and_no_respawn(request: pytest.FixtureRequest, fault: str) -> None:
    # Parent runs under existing attested fixture only. No native execution claimed by double.
    import asyncio

    from omnis.core.db import database_engine
    from omnis.modules.instance.schemas import NativePrepareCommand
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.runs.native_preparation import NativePreparation, readback
    from omnis.modules.settings.catalog_models import CatalogError
    from test_b06b_pure_probe_pg import setup

    p = setup(request)
    _, selected = p.selected()

    async def run() -> None:
        from omnis.supervisor.runtime_client import RuntimeClient

        class RuntimeDouble(RuntimeClient):
            calls = 0

            async def prepare(
                self,
                service: InstanceService,
                supervisor_owner: object,
                bundle_ref: dict[str, object],
                bundle: dict[str, object],
            ) -> dict[str, object]:
                self.calls += 1
                # T1 must already be durable from another connection before IPC.
                with pytest.raises(CatalogError, match="PREPARATION_INDETERMINATE"):
                    await readback(
                        engine,
                        {
                            "schema_version": 1,
                            "owner_id": p.probe.owner,
                            "command_id": value.command_id,
                        },
                    )
                with pytest.raises(CatalogError, match="PREPARATION_INDETERMINATE"):
                    await consumer.prepare(value)
                if fault == "after_t1":
                    from omnis.supervisor.runtime_client import RuntimeUnavailable

                    raise RuntimeUnavailable("synthetic transport loss")
                if fault == "stopped":
                    await service.shutdown(uuid4(), status.generation, owner, epoch)
                prepared = worker_fixture(bundle)
                if fault == "wrong_bytes":
                    prepared["loaded"] = []
                return {"preparation": prepared}

        engine = database_engine(p.dsn)
        service, owner = InstanceService(engine), uuid4()
        try:
            epoch = await service.acquire(owner)
            status = await service.owned_status(owner, epoch)
            runtime = RuntimeDouble(p.probe.directory, generation=status.generation, epoch=epoch)
            runtime.boot = str(uuid4())
            consumer = NativePreparation(engine, p.probe.root, service, owner, epoch, runtime)
            value = NativePrepareCommand.model_validate(
                {
                    **command(),
                    "owner_id": p.probe.owner,
                    "instance_id": str(status.instance_id),
                    "expected_epoch": epoch,
                    "expected_generation": status.generation,
                    "selection_ref": selected["selection_ref"],
                }
            )
            from omnis.modules.instance.domain import ControlConflict

            if fault != "none":
                with pytest.raises((CatalogError, ControlConflict)):
                    await consumer.prepare(value)
                with pytest.raises(CatalogError, match="PREPARATION_INDETERMINATE"):
                    await consumer.prepare(value)
                assert runtime.calls == 1
                with pytest.raises(CatalogError, match="PREPARATION_INDETERMINATE"):
                    await readback(
                        engine,
                        {
                            "schema_version": 1,
                            "owner_id": p.probe.owner,
                            "command_id": value.command_id,
                        },
                    )
                return
            result = await consumer.prepare(value)
            assert result["preparation_status"] == "PREPARED"
            assert await consumer.prepare(value) == result
            assert runtime.calls == 1
            from omnis.modules.runs.native_preparation_models import mapping

            bad = value.model_dump(mode="json")
            bad["selection_ref"] = {**mapping(bad["selection_ref"]), "digest": "0" * 64}
            with pytest.raises(CatalogError, match="COMMAND_CONFLICT"):
                await consumer.prepare(NativePrepareCommand.model_validate(bad))
            await service.release(owner, epoch)
            back = await readback(
                engine,
                {"schema_version": 1, "owner_id": p.probe.owner, "command_id": value.command_id},
            )
            assert back["receipt_ref"] == result["receipt_ref"]
            import os

            from fixtures.b06b_publication.consumer import cli_command
            from omnis.modules.settings.catalog_schema import canonical, load_json

            request_file = p.probe.directory / "native-readback.json"
            request_file.write_bytes(
                canonical(
                    {"schema_version": 1, "owner_id": p.probe.owner, "command_id": value.command_id}
                )
            )
            request_file.chmod(0o600)
            child = await asyncio.create_subprocess_exec(
                *cli_command(
                    "omnis.modules.runs.native_preparation",
                    "readback",
                    "--request",
                    str(request_file),
                ),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "OMNIS_DATABASE_URL": p.dsn},
            )
            output, errors = await asyncio.wait_for(child.communicate(), 10)
            assert child.returncode == 0, errors
            assert load_json(output) == back
            assert runtime.calls == 1
        finally:
            await engine.dispose()

    asyncio.run(run())


@pytest.mark.asyncio
async def test_pg_final_transaction_lease_expiry_rolls_back(migrated_database_url: "URL") -> None:
    from sqlalchemy import text

    from omnis.core.db import database_engine
    from omnis.modules.instance.domain import ControlConflict
    from omnis.modules.instance.service import InstanceService
    from omnis.modules.settings import candidate_store as store

    engine = database_engine(migrated_database_url.render_as_string(hide_password=False))
    service, owner = InstanceService(engine), uuid4()
    marker = store.envelope("native-preparation-guard-test", {})
    try:
        epoch = await service.acquire(owner)
        status = await service.owned_status(owner, epoch)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE supervisor_lease SET expires_at=clock_timestamp()+interval '0.4 seconds' WHERE id=1"
                )
            )
        with pytest.raises(ControlConflict, match="LEASE_LOST"):
            async with service.native_preparation_commit(
                owner, epoch, status.generation
            ) as connection:
                await store.lock(connection, "owner:" + str(owner))
                await store.put(connection, str(owner), str(uuid4()), marker)
                await connection.execute(text("SELECT pg_sleep(0.5)"))
        async with engine.connect() as connection:
            count = (
                await connection.execute(
                    text("SELECT count(*) FROM catalog_record WHERE id=:id"), {"id": marker["id"]}
                )
            ).scalar_one()
            assert count == 0
    finally:
        await engine.dispose()


def bundle_fixture() -> dict[str, object]:
    from omnis.modules.runs.native_preparation_models import LIMITS, prepare_packages
    from omnis.modules.settings import candidate_store as store

    material, sources, material_digest = capture(
        [str(SOURCE / "b06b-publish-contract")], str(SOURCE / "profile.yaml")
    )
    ref = {
        "kind": "package",
        "id": str(uuid4()),
        "revision": 1,
        "digest": sources[0]["package_digest"],
    }
    body: dict[str, object] = {
        "protocol": "omnis-native-preparation-v1",
        "owner_id": str(uuid4()),
        "recipe_key": "recipe",
        "material_digest": material_digest,
        "resolved_index_digest": "a" * 64,
        "resolution": "NO_MODEL",
        "effective": None,
        "preprocess": False,
        "limits": LIMITS,
        "packages": prepare_packages(material, [(ref, sources[0])]),
    }
    for field, kind in (
        ("selection_ref", "execution-selection"),
        ("snapshot_ref", "run-snapshot"),
        ("publication_ref", "catalog-publication"),
        ("candidate_snapshot_ref", "candidate-snapshot"),
    ):
        body[field] = {"kind": kind, "id": str(uuid4()), "revision": 1, "digest": "b" * 64}
    return store.envelope("native-preparation-bundle", body)


def worker_fixture(bundle: dict[str, object]) -> dict[str, object]:
    from omnis.modules.runs.native_preparation_models import (
        BASE_COMMIT,
        PATCH_SHA256,
        SKILLS_TOOL_SHA256,
        mapping,
        sequence,
    )
    from omnis.modules.settings import candidate_store as store

    loaded = []
    for item in sequence(mapping(bundle["payload"])["packages"]):
        package = mapping(item)
        for file in sequence(package["files"]):
            loaded.append(
                {
                    "package_ref": package["package_ref"],
                    "native_name": package["native_name"],
                    **mapping(file),
                }
            )
    return {
        "schema_version": 1,
        "status": "PREPARED",
        "bundle_ref": store.reference(bundle),
        "loader": "tools.skills_tool.skill_view",
        "preprocess": False,
        "loaded": loaded,
        "native": {
            "base_commit": BASE_COMMIT,
            "patch_sha256": PATCH_SHA256,
            "skills_tool_sha256": SKILLS_TOOL_SHA256,
            "worker_revision": "c" * 64,
        },
    }


def test_seed_packages_retain_all_declared_files() -> None:
    assert importlib.util.find_spec("omnis.modules.runs.native_preparation_models") is not None, (
        "bundle consumer missing"
    )
    from omnis.modules.runs.native_preparation_models import prepare_packages

    material, sources, _ = capture(
        [str(SOURCE / "b06b-publish-contract")], str(SOURCE / "profile.yaml")
    )
    source = sources[0]
    ref = {"kind": "package", "id": str(uuid4()), "revision": 1, "digest": source["package_digest"]}
    packages = prepare_packages(material, [(ref, source)])
    files = packages[0]["files"]
    assert isinstance(files, list)
    assert len(files) == 10
    assert sum(f["size"] for f in files) == 9703
    changed = dict(material)
    changed["packages/0/SKILL.md"] = (
        b"---\nname: malicious\ndescription: test\nmetadata: {}\n---\nbody\n"
    )
    with pytest.raises(CatalogError):
        prepare_packages(changed, [(ref, source)])
