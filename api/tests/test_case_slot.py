"""Real bounded filesystem transitions; DB authority simulated here, tested on PG separately."""

import hashlib
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from omnis.supervisor import case_slot

LEAVES = (
    "active",
    "active-support/work",
    "active-support/os-home",
    "active-support/codex",
    "active-support/tmp",
    "active-support/managed-empty",
    "active-support/xdg/config",
    "active-support/xdg/cache",
    "active-support/xdg/state",
    "active-support/xdg/data",
)
ROOTS = (".", "control", "archives", "active-support", "active-support/xdg", *LEAVES)
SOURCES = {
    "hermes_state.py": "134fb1af988fd49407433cf54afa74f2188c93021fc4576bcf2c7174e787c2eb",
    "hermes_state_repair.py": "7af22ad9aa7cf3823e768177c4d56d1827b53f7253d0549e0bd7e3195ff0b14e",
    "hermes_logging.py": "19deccd2c8a71cf0c9cf94f9cc44021a5fb9e8f4dc29df4da30ea7605b9ab84a",
    "hermes_cli/config.py": "854c01bd0e7564dc8e1ff59774993ad2769d1b26ffe6a52a11d91dab5693ff14",
    "hermes_cli/auth.py": "1565d014485f1316e9ed0cf213fa6049c8db3bf6f449b15bfe675219734396b1",
}


def private_write(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    path.chmod(0o600)


def provision(root: Path, instance: UUID) -> None:
    root.mkdir(mode=0o700)
    for leaf in ROOTS[1:]:
        (root / leaf).mkdir(mode=0o700, parents=True, exist_ok=True)
    private_write(root / "active/config.yaml", b"inert: true\n")
    private_write(root / "active/auth.json", b"synthetic-provider-store")
    private_write(root / "active/auth.lock", b"")
    private_write(root / "control/slot.lock", b"")
    policy = {
        "schema_version": 1,
        "instance_id": str(instance),
        "approval": "B05_INERT",
        "native_commit": "ee5ee84a345204a3b1d6ef6ba1ab747e602867b9",
        "inventory_sha256": "a2020b35cf5cee08d671c3421b81119b8fc7b1beaae4b39cc488eab4c1874cad",
        "source_files": SOURCES,
        "families": ["sqlite", "sessions", "logs", "cache", "support"],
        "support_children": {
            leaf: (
                ["trajectory_samples.jsonl", "failed_trajectories.jsonl"]
                if leaf.endswith("/work")
                else ["probe"]
                if leaf.endswith("/tmp") or leaf == "active-support/xdg/cache"
                else []
            )
            for leaf in LEAVES
            if leaf != "active"
        },
        "config_sha256": hashlib.sha256(b"inert: true\n").hexdigest(),
        "roots": {
            name: {"dev": (root / name).stat().st_dev, "ino": (root / name).stat().st_ino}
            for name in ROOTS
        },
    }
    private_write(root / "control/policy.json", json.dumps(policy).encode())


def authority() -> Mock:
    service = Mock()

    @asynccontextmanager
    async def guard(*args: object, **kwargs: object) -> AsyncIterator[SimpleNamespace]:
        yield SimpleNamespace(deadline_ns=time.monotonic_ns() + 2_000_000_000, verify=AsyncMock())

    service.case_transition = guard
    return service


def snapshot(slot: case_slot.CaseSlot, state: str = "READY") -> dict[str, object]:
    return {
        "boot": slot.boot,
        "generation": slot.generation,
        "epoch": slot.epoch,
        "state": state,
        "drained": state == "STOPPED",
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
    }


@pytest.mark.asyncio
async def test_product_slot_a_b_a_preserves_roots_provider_config_and_entire_bundle(
    tmp_path: Path,
) -> None:
    instance, owner, a, b = uuid4(), uuid4(), uuid4(), uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    roots = {n: (root / n).stat().st_ino for n in ROOTS}
    provider = {
        n: (root / "active" / n).read_bytes() for n in ("auth.json", "auth.lock", "config.yaml")
    }
    service = authority()
    first = case_slot.CaseSlot(root, a, instance, owner, 1, 0, str(uuid4()))
    await first.prepare(service)
    await first.observe(snapshot(first))
    payloads = {
        "active/state.db": b"synthetic-sqlite-bytes",
        "active/state.db-wal": b"wal",
        "active/state.db-shm": b"shm",
        "active/state.db-journal": b"journal",
        "active/state.db.repair-attempts.json": b"{}",
        "active/state.db.malformed-backup-123": b"recovery",
        "active/state.db.repair-scratch": b"scratch recovery",
        "active/state.db.repair-scratch-wal": b"scratch wal",
        "active/state.db.repair-scratch-shm": b"scratch shm",
        "active/state.db.repair-scratch-journal": b"scratch journal",
        "active/sessions/sessions.json": b"A sessions",
        "active/logs/gateway.log": b"A logs",
        "active/cache/discovery.json": b"A cache",
        "active-support/work/trajectory_samples.jsonl": b"A trajectory",
        "active-support/tmp/probe": b"A temporary",
        "active-support/xdg/cache/probe": b"A xdg",
    }
    for name, data in payloads.items():
        (root / name).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        private_write(root / name, data)
    (root / "active/state.db").chmod(0o644)
    await first.archive(service, 0, snapshot(first, "STOPPED"))
    await first.close()
    second = case_slot.CaseSlot(root, b, instance, owner, 2, 0, str(uuid4()))
    await second.prepare(service)
    assert all(not (root / n).exists() for n in payloads)
    await second.observe(snapshot(second))
    private_write(root / "active/state.db", b"B")
    await second.archive(service, 0, snapshot(second, "STOPPED"))
    await second.close()
    third = case_slot.CaseSlot(root, a, instance, owner, 3, 0, str(uuid4()))
    await third.prepare(service)
    assert {n: (root / n).read_bytes() for n in payloads} == payloads
    assert (root / "active/state.db").stat().st_mode & 0o777 == 0o600
    assert {n: (root / n).stat().st_ino for n in ROOTS} == roots
    assert {n: (root / "active" / n).read_bytes() for n in provider} == provider
    assert not any(p.name in provider for p in (root / "archives").rglob("*"))
    receipt = json.loads((root / "control/active.json").read_text())
    assert receipt["case_id"] == str(a) and receipt["boot"] == third.boot
    await third.observe(snapshot(third))
    await third.archive(service, 0, snapshot(third, "STOPPED"))
    await third.close()


@pytest.mark.asyncio
async def test_fallback_auth_at_support_top_level_is_refused_before_any_move(
    tmp_path: Path,
) -> None:
    instance = uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 1, 0, str(uuid4()))
    service = authority()
    await slot.prepare(service)
    await slot.observe(snapshot(slot))
    private_write(root / "active-support/work/auth.json", b"synthetic-fallback")
    with pytest.raises(ValueError, match="Fallback|Unclassified"):
        await slot.archive(service, 0, snapshot(slot, "STOPPED"))
    assert (root / "active-support/work/auth.json").exists()
    assert not (slot.archive_root / "receipt.json").exists()
    await slot.close()


@pytest.mark.asyncio
async def test_post_move_guard_exit_loss_retains_prepared_journal(tmp_path: Path) -> None:
    instance = uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 1, 0, str(uuid4()))
    service = authority()
    await slot.prepare(service)
    await slot.observe(snapshot(slot))
    private_write(root / "active/state.db", b"A")

    @asynccontextmanager
    async def lost(*args: object, **kwargs: object) -> AsyncIterator[SimpleNamespace]:
        yield SimpleNamespace(deadline_ns=time.monotonic_ns() + 2_000_000_000, verify=AsyncMock())
        raise ValueError("authority expired on guard exit")

    service.case_transition = lost
    with pytest.raises(ValueError, match="authority expired"):
        await slot.archive(service, 0, snapshot(slot, "STOPPED"))
    assert json.loads((root / "control/journal.json").read_text())["state"] == "PREPARED"
    await slot.close()
    next_slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 2, 0, str(uuid4()))
    with pytest.raises(ValueError, match="Incomplete"):
        await next_slot.prepare(authority())
    await next_slot.close()


@pytest.mark.asyncio
async def test_unknown_support_derivative_is_not_implicitly_approved(tmp_path: Path) -> None:
    instance = uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 1, 0, str(uuid4()))
    await slot.prepare(authority())
    await slot.observe(snapshot(slot))
    private_write(root / "active-support/tmp/unknown", b"synthetic")
    with pytest.raises(ValueError, match="Unclassified"):
        await slot.archive(authority(), 0, snapshot(slot, "STOPPED"))
    assert (root / "active-support/tmp/unknown").exists()
    await slot.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind", ["symlink", "hardlink", "fifo", "unknown", "config", "root", "occupied"]
)
async def test_case_preflight_denials_have_zero_case_moves(tmp_path: Path, kind: str) -> None:
    import os

    instance = uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 1, 0, str(uuid4()))
    service = authority()
    await slot.prepare(service)
    await slot.observe(snapshot(slot))
    data = root / "active/state.db"
    private_write(data, b"original")
    if kind == "symlink":
        (root / "active/sessions").symlink_to(data)
    elif kind == "hardlink":
        (root / "active/state.db-wal").hardlink_to(data)
    elif kind == "fifo":
        os.mkfifo(root / "active/state.db-wal", 0o600)
    elif kind == "unknown":
        private_write(root / "active/unknown.db", b"unknown")
    elif kind == "config":
        private_write(root / "active/config.yaml", b"changed")
    elif kind == "root":
        (root / "active-support/tmp").rename(root / "active-support/tmp-old")
        (root / "active-support/tmp").mkdir(mode=0o700)
    else:
        private_write(slot.archive_root / "data/active/state.db", b"occupied")
    with pytest.raises((ValueError, OSError)):
        await slot.archive(service, 0, snapshot(slot, "STOPPED"))
    assert data.read_bytes() == b"original"
    assert not (slot.archive_root / "receipt.json").exists()
    await slot.close()


@pytest.mark.asyncio
async def test_rename_failure_preserves_partial_data_and_journal_and_refuses_new_boot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 1, 0, str(uuid4()))
    service = authority()
    await slot.prepare(service)
    await slot.observe(snapshot(slot))
    for name in ("state.db", "state.db-wal"):
        private_write(root / "active" / name, name.encode())
    real = case_slot._rename
    calls = 0

    def fault(source: int, target: int, name: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected second rename failure")
        real(source, target, name)

    monkeypatch.setattr(case_slot, "_rename", fault)
    with pytest.raises(OSError, match="second rename"):
        await slot.archive(service, 0, snapshot(slot, "STOPPED"))
    assert not (root / "active/state.db").exists()
    assert (slot.archive_root / "data/active/state.db").read_bytes() == b"state.db"
    assert (root / "active/state.db-wal").read_bytes() == b"state.db-wal"
    assert json.loads((root / "control/journal.json").read_text())["state"] == "PREPARED"
    assert not (slot.archive_root / "receipt.json").exists()
    await slot.close()
    next_slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 2, 0, str(uuid4()))
    with pytest.raises(ValueError, match="Incomplete"):
        await next_slot.prepare(service)
    await next_slot.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["boot", "epoch", "generation", "drain", "inventory"])
async def test_runtime_receipt_denials_have_zero_case_moves(tmp_path: Path, kind: str) -> None:
    instance = uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 1, 0, str(uuid4()))
    await slot.prepare(authority())
    await slot.observe(snapshot(slot))
    private_write(root / "active/state.db", b"original")
    stopped = snapshot(slot, "STOPPED")
    if kind == "boot":
        stopped["boot"] = str(uuid4())
    elif kind in {"epoch", "generation"}:
        stopped[kind] = True
    elif kind == "drain":
        stopped["drained"] = False
    else:
        stopped["bootstrap_inventory"] = None
    with pytest.raises(ValueError):
        await slot.archive(authority(), 0, stopped)
    assert (root / "active/state.db").read_bytes() == b"original"
    assert not (slot.archive_root / "receipt.json").exists()
    await slot.close()


@pytest.mark.asyncio
async def test_archive_unknown_path_is_refused_before_restore(tmp_path: Path) -> None:
    instance, a = uuid4(), uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    slot = case_slot.CaseSlot(root, a, instance, uuid4(), 1, 0, str(uuid4()))
    await slot.prepare(authority())
    await slot.observe(snapshot(slot))
    private_write(root / "active/state.db", b"A")
    await slot.archive(authority(), 0, snapshot(slot, "STOPPED"))
    await slot.close()
    private_write(slot.archive_root / "data/unknown", b"unclassified")
    restored = case_slot.CaseSlot(root, a, instance, uuid4(), 2, 0, str(uuid4()))
    with pytest.raises(ValueError, match="Unknown archive"):
        await restored.prepare(authority())
    assert not (root / "active/state.db").exists()
    await restored.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", ["entries", "bytes", "deadline"])
async def test_finite_budget_denial_precedes_case_moves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    limit: str,
) -> None:
    instance = uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 1, 0, str(uuid4()))
    await slot.prepare(authority())
    await slot.observe(snapshot(slot))
    private_write(root / "active/state.db", b"x" * 256)
    monkeypatch.setattr(
        case_slot,
        {"entries": "MAX_ENTRIES", "bytes": "MAX_BYTES", "deadline": "MAX_SECONDS"}[limit],
        1 if limit != "bytes" else 64,
    )
    if limit == "deadline":
        monkeypatch.setattr(case_slot, "MAX_SECONDS", 0)
    with pytest.raises(ValueError, match="budget"):
        await slot.archive(authority(), 0, snapshot(slot, "STOPPED"))
    assert (root / "active/state.db").read_bytes() == b"x" * 256
    assert not (slot.archive_root / "receipt.json").exists()
    await slot.close()


@pytest.mark.asyncio
async def test_new_idle_host_does_not_adopt_unclosed_active_case(tmp_path: Path) -> None:
    instance = uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 1, 0, str(uuid4()))
    await slot.prepare(authority())
    await slot.observe(snapshot(slot))
    private_write(root / "active/state.db", b"unclosed")
    await slot.close()
    next_slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 2, 0, str(uuid4()))
    with pytest.raises(ValueError, match="Unclosed"):
        await next_slot.prepare(authority())
    assert (root / "active/state.db").read_bytes() == b"unclosed"
    await next_slot.close()


@pytest.mark.asyncio
async def test_case_observe_uses_the_transport_utf8_inventory_budget(tmp_path: Path) -> None:
    from omnis.supervisor.runtime_client import validate_bootstrap_inventory

    instance = uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    slot = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 1, 0, str(uuid4()))
    await slot.prepare(authority())
    observed = snapshot(slot)
    value = observed["bootstrap_inventory"]
    assert isinstance(value, dict)
    value["registry"] = {
        "status": "REGISTERED_SNAPSHOT",
        "generation": 0,
        "count": 50,
        "entries": [{"name": "漢" * 120 + f"{n:03}", "toolset": "set"} for n in range(50)],
    }
    assert validate_bootstrap_inventory(value) == value
    assert len(json.dumps(value, ensure_ascii=False).encode("utf-8")) <= 24 * 1024
    assert len(json.dumps(value).encode("utf-8")) > 24 * 1024
    try:
        await slot.observe(observed)
        assert json.loads((root / "control/active.json").read_bytes())["inventory"] == value
    finally:
        await slot.close()
