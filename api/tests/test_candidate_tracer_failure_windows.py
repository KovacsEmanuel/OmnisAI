"""Bounded real finalize/SQL seams and postcommit loss, NOT physical power loss."""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection

from conftest import connect_test_database
from fixtures.b06a.consumer import mapping, sequence
from fixtures.b06a_durable.consumer import (
    MODULE,
    canonical,
    copy_seed,
    envelope,
    freeze,
    readback,
    scratch_directory,
)
from fixtures.b06a_durable.overlap import ledger
from omnis.core.db import database_engine
from omnis.modules.settings import candidate_catalog as module
from omnis.modules.settings import candidate_material as material
from omnis.modules.settings import candidate_store as store
from omnis.modules.settings.candidate_catalog import CandidateCatalog
from omnis.modules.settings.catalog_models import CatalogError

WINDOWS = (
    "before_finalize",
    "after_finalize",
    "before_file_fsync",
    "after_file_fsync",
    "before_rename",
    "after_rename",
    "before_input_insert",
    "after_input_insert",
    "before_receipt_insert",
    "after_receipt_insert",
    "before_command_insert",
    "after_command_insert",
    "cancel_after_input_insert",
)


def orphan_bytes(root: Path) -> dict[str, bytes]:
    # Inspect only test-owned receipt/staging namespaces; retain all partial bytes.
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for namespace in ("staging", "receipts")
        for path in (root / namespace).rglob("*")
        if path.is_file()
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("window", WINDOWS)
async def test_candidate_tracer_evaluation_rollback_inert_orphans(
    migrated_database_url: URL,
    monkeypatch: pytest.MonkeyPatch,
    window: str,
) -> None:
    seed = copy_seed(scratch_directory() / "evaluation-window")
    url = migrated_database_url.render_as_string(hide_password=False)
    frozen = freeze(seed, url)
    golden = mapping(json.loads((seed.directory / "golden.json").read_bytes()))
    command = seed.write_request(
        snapshot_ref=frozen["snapshot_ref"],
        evaluation_kind="PURE",
        input=golden["input"],
    )
    engine = database_engine(url)
    catalog = CandidateCatalog(engine, seed.catalog_root)
    before = ledger(migrated_database_url)
    actual_finalize, actual_put, actual_complete = material.finalize, store.put, store.complete
    actual_fsync, actual_sync = os.fsync, material.sync_directory
    reached: list[str] = []

    def fail() -> None:
        reached.append(window)
        if window == "cancel_after_input_insert":
            raise asyncio.CancelledError
        raise CatalogError("INJECTED_EVALUATION_WINDOW")

    def finalize(root: Path, namespace: str, identity: str, files: dict[str, bytes]) -> Path:
        assert namespace == "receipts"
        if window == "before_finalize":
            fail()
        result = actual_finalize(root, namespace, identity, files)
        if window == "after_finalize":
            fail()
        return result

    def fsync(fd: int) -> None:
        path = Path(os.readlink(f"/proc/self/fd/{fd}"))
        in_stage = seed.catalog_root / "staging" in path.parents and path.is_file()
        if in_stage and window == "before_file_fsync":
            fail()
        actual_fsync(fd)  # Delegate the real syscall at every non-injected boundary.
        if in_stage and window == "after_file_fsync":
            fail()

    def sync(path: Path) -> None:
        actual_sync(path)
        if path.parent == seed.catalog_root / "staging" and window == "before_rename":
            fail()  # Last bottom-up stage directory sync immediately precedes renameat2.
        if path.parent == seed.catalog_root / "receipts" and window == "after_rename":
            fail()  # Actual rename and first target-directory fsync have succeeded.

    async def put(
        connection: AsyncConnection,
        owner: str,
        group: str,
        record: dict[str, object],
    ) -> None:
        kind = record["kind"]
        seam = "input" if kind == "evaluation-input" else "receipt"
        if window == f"before_{seam}_insert":
            fail()
        await actual_put(connection, owner, group, record)
        if window == f"after_{seam}_insert" or (
            window == "cancel_after_input_insert" and kind == "evaluation-input"
        ):
            fail()

    async def complete(
        connection: AsyncConnection,
        owner: str,
        identity: str,
        operation: str,
        request: object,
        result: dict[str, object],
    ) -> None:
        assert operation == "evaluate"
        if window == "before_command_insert":
            fail()
        await actual_complete(connection, owner, identity, operation, request, result)
        if window == "after_command_insert":
            fail()

    try:
        with monkeypatch.context() as patcher:
            patcher.setattr(module, "finalize", finalize)
            patcher.setattr(os, "fsync", fsync)
            patcher.setattr(material, "sync_directory", sync)
            patcher.setattr(store, "put", put)
            patcher.setattr(store, "complete", complete)
            if window == "cancel_after_input_insert":
                with pytest.raises(asyncio.CancelledError):
                    await catalog.dispatch("evaluate", command)
            else:
                with pytest.raises(CatalogError, match="INJECTED_EVALUATION_WINDOW"):
                    await catalog.dispatch("evaluate", command)
        assert reached == [window], "the requested real failure seam was not exercised"
        assert ledger(migrated_database_url) == before, (
            "partial input/receipt/command escaped rollback"
        )
        orphans = orphan_bytes(seed.catalog_root)
        if window == "before_finalize":
            assert orphans == {}
        else:
            assert orphans, "failure lost the retained inert orphan evidence"
        old_directories = set((seed.catalog_root / "receipts").iterdir())
        assert readback(seed, url, frozen)["evaluations"] == []
        retry = await catalog.dispatch("evaluate", command)
        assert retry["status"] == "PURE_PASS"
        assert retry["outputs"] == [
            canonical(item).decode() for item in sequence(golden["outputs"])
        ]
        ref = mapping(retry["evaluation_ref"])
        committed = seed.catalog_root / "receipts" / str(ref["id"])
        assert committed not in old_directories, "retry adopted an orphan receipt namespace"
        for name, raw in orphans.items():
            assert (seed.catalog_root / name).read_bytes() == raw, (
                "retry removed/overwrote an orphan"
            )
        assert set((seed.catalog_root / "receipts").iterdir()) == old_directories | {committed}
        after = ledger(migrated_database_url)
        assert len(after["catalog_record"]) == len(before["catalog_record"]) + 2
        assert len(after["catalog_command"]) == len(before["catalog_command"]) + 1
        assert after["catalog_reservation"] == before["catalog_reservation"]
        assert seed.success("evaluate", command, url) == retry
        assert ledger(migrated_database_url) == after
        back = readback(seed, url, frozen)
        assert back["evaluations"] == [retry["evaluation"]]
    finally:
        await engine.dispose()


@pytest.mark.parametrize("operation", ["freeze", "evaluate"])
def test_candidate_tracer_committed_response_discard_fresh_process_replay(
    migrated_database_url: URL,
    operation: str,
) -> None:
    """Actual CLI writes stdout to a pipe; caller discards it AFTER observed commit.

    No fake receipt or direct dispatch is the loss producer. This is a client
    response-discard boundary, not SIGKILL, physical crash or a network failure.
    """
    from fixtures.b06a_durable.consumer import freeze_request, reviewed

    seed = copy_seed(scratch_directory() / "committed-response-loss")
    url = migrated_database_url.render_as_string(hide_password=False)
    if operation == "freeze":
        captured, review = reviewed(seed, url)
        command = freeze_request(seed, captured, review)
    else:
        frozen = freeze(seed, url)
        golden = mapping(json.loads((seed.directory / "golden.json").read_bytes()))
        command = seed.write_request(
            snapshot_ref=frozen["snapshot_ref"],
            evaluation_kind="PURE",
            input=golden["input"],
        )
    path = seed.directory / f"lost-response-{uuid4().hex}.json"
    path.write_bytes(canonical(command))
    before = ledger(migrated_database_url)
    # Attest before launching the real consumer; no credentials in argv or diagnostics.
    with connect_test_database(migrated_database_url, autocommit=True) as observer:
        child = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-B",
                "-m",
                MODULE,
                operation,
                "--request",
                str(path),
                "--catalog-root",
                str(seed.catalog_root),
            ],
            cwd=seed.directory,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(seed.directory),
                "TMPDIR": str(seed.directory),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "OMNIS_DATABASE_URL": url,
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            committed_result: dict[str, object] | None = None
            until = time.monotonic() + 15
            while time.monotonic() < until:
                row = observer.execute(
                    "SELECT result FROM catalog_command WHERE owner_id=%s AND command_id=%s",
                    (seed.owner_id, command["command_id"]),
                ).fetchone()
                if row is not None:
                    committed_result = mapping(row[0])
                    break
                time.sleep(0.01)
            assert committed_result is not None, "real consumer did not produce a committed command"
            # Intentionally drain/discard stdout only after the DB commit is independently visible.
            lost_bytes, diagnostic = child.communicate(timeout=20)
            discarded_bytes = len(lost_bytes)
            del lost_bytes  # Never decode or use the lost response as the replay oracle.
            assert child.returncode == 0 and diagnostic == b"", "lost-response producer failed"
            assert discarded_bytes > 0, "no real successful response was discarded"
        finally:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
            if child.stdout is not None:
                child.stdout.close()
            if child.stderr is not None:
                child.stderr.close()
    after_commit = ledger(migrated_database_url)
    assert len(after_commit["catalog_command"]) == len(before["catalog_command"]) + 1
    assert len(after_commit["catalog_record"]) == len(before["catalog_record"]) + (
        1 if operation == "freeze" else 2
    )
    retained = {
        path.relative_to(seed.catalog_root).as_posix(): path.read_bytes()
        for namespace in ("candidates", "receipts")
        for path in (seed.catalog_root / namespace).rglob("*")
        if path.is_file()
    }
    # Each success is a NEW joined -I -B consumer process; first owner already joined.
    replay = seed.success(operation, command, url)
    assert replay == committed_result
    assert ledger(migrated_database_url) == after_commit
    replay_files = {
        path.relative_to(seed.catalog_root).as_posix(): path.read_bytes()
        for namespace in ("candidates", "receipts")
        for path in (seed.catalog_root / namespace).rglob("*")
        if path.is_file()
    }
    assert replay_files == retained, "fresh replay created, removed or changed immutable files"
    if operation == "evaluate":
        receipt = envelope(replay["evaluation"], replay["evaluation_ref"])
        receipt_path = seed.catalog_root / "receipts" / str(mapping(replay["evaluation_ref"])["id"])
        assert (receipt_path / "receipt.json").read_bytes() == canonical(replay["evaluation"])
        assert (receipt_path / "outputs.json").read_bytes() == canonical(replay["outputs"])
        assert (
            mapping(json.loads((receipt_path / "input.json").read_bytes()))["digest"]
            == (mapping(receipt["input_ref"])["digest"])
        )
        assert readback(seed, url, frozen)["evaluations"] == [replay["evaluation"]]
    else:
        assert readback(seed, url, replay)["snapshot"] == replay["snapshot"]
