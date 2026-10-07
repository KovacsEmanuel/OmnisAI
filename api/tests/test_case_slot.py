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
    "hermes_cli/config_home.py": "85f5e604e745a7b74688b4ae2c930af96f228e661b8100cefd561f2640618e74",
    "hermes_cli/config_backups.py": "a923aeb156eac44b055ebc2cea458dfd4ee1dbfe7cf0694fd7a55da751b3f1aa",
    "hermes_cli/default_soul.py": "b65192a631f0011fcef245c94d9741e0c716defe605d3edfd0e59f26da211d2d",
    "hermes_state_dbfile.py": "317c4e5cbc7469259331f19e0a90f9081b729bbf70e97e81e7670ea6e630f7df",
    "hermes_state_common.py": "e66bdefc2bb58ab1e750a5040245fb95b3176a277773f35c2d2bbb3ef789070c",
    "hermes_state_schema.py": "8712aa97c222cdc2f1ec5ab8d2dadd01756117c43e1597dcfbe43c0645e30ef0",
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
        "schema_version": 2,
        "instance_id": str(instance),
        "approval": "B05_INERT",
        "native_commit": "ee5ee84a345204a3b1d6ef6ba1ab747e602867b9",
        "inventory_sha256": "a2020b35cf5cee08d671c3421b81119b8fc7b1beaae4b39cc488eab4c1874cad",
        "state_policy_sha256": "bcbd8b2ce7ac69064da04ef37eb9961e4a06d19bce342706b99c9dfa17d87c6d",
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
async def test_native_inert_bootstrap_bundle_archives_and_restores(tmp_path: Path) -> None:
    """Observed pinned native layout; filesystem regression, not installed/native QA."""
    instance, owner, case = uuid4(), uuid4(), uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    service = authority()
    first = case_slot.CaseSlot(root, case, instance, owner, 1, 0, str(uuid4()))
    await first.prepare(service)
    await first.observe(snapshot(first))
    payloads = {
        "SOUL.md": (Path(__file__).parent / "fixtures/hermes-default-soul.txt").read_bytes(),
        "backups/config/config.yaml.good.20261007-155245": b"inert: true\n",
        "state.db": b"synthetic DB bytes; actual SessionDB tested by installed QA",
        "state.db.quarantine.lock": b"",
        "state.db.fts_rebuild.lock": b"",
    }
    empty = ("cron", "hooks", "skills", "memories", "pairing", "image_cache", "audio_cache")
    for name in empty:
        (root / "active" / name).mkdir(mode=0o700)
    (root / "active/backups").mkdir(mode=0o700)
    for name, data in payloads.items():
        path = root / "active" / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        private_write(path, data)
    await first.archive(service, 0, snapshot(first, "STOPPED"))
    assert {p.name for p in (root / "active").iterdir()} == case_slot.SHARED
    await first.close()
    restored = case_slot.CaseSlot(root, case, instance, owner, 2, 0, str(uuid4()))
    await restored.prepare(service)
    assert {name: (root / "active" / name).read_bytes() for name in payloads} == payloads
    assert all(not list((root / "active" / name).iterdir()) for name in empty)
    await restored.observe(snapshot(restored))
    await restored.archive(service, 0, snapshot(restored, "STOPPED"))
    await restored.close()


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
@pytest.mark.parametrize("boundary", ["active", "archive"])
@pytest.mark.parametrize(
    "kind",
    [
        "cron",
        "hooks",
        "skills",
        "memories",
        "pairing",
        "image_cache",
        "audio_cache",
        "soul",
        "soul-directory",
        "quarantine-lock",
        "fts-lock",
        "lock-directory",
        "backup-digest",
        "backup-oversize",
        "backup-reason",
        "backup-extra-child",
        "backup-depth",
        "backup-count",
        "backup-auth",
    ],
)
async def test_new_native_families_refuse_unapproved_content_before_moves(
    tmp_path: Path, boundary: str, kind: str
) -> None:
    instance, case, owner = uuid4(), uuid4(), uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    service = authority()
    first = case_slot.CaseSlot(root, case, instance, owner, 1, 0, str(uuid4()))
    await first.prepare(service)
    await first.observe(snapshot(first))
    if boundary == "archive":
        await first.archive(service, 0, snapshot(first, "STOPPED"))
        await first.close()
        base = first.archive_root / "data/active"
        slot = case_slot.CaseSlot(root, case, instance, owner, 2, 0, str(uuid4()))
    else:
        base, slot = root / "active", first
    if kind in {"cron", "hooks", "skills", "memories", "pairing", "image_cache", "audio_cache"}:
        (base / kind).mkdir(mode=0o700)
        private_write(base / kind / "unapproved.txt", b"unapproved")
    elif kind == "soul":
        private_write(base / "SOUL.md", b"custom persona")
    elif kind == "soul-directory":
        (base / "SOUL.md").mkdir(mode=0o700)
    elif kind in {"quarantine-lock", "fts-lock"}:
        name = (
            "state.db.quarantine.lock" if kind == "quarantine-lock" else "state.db.fts_rebuild.lock"
        )
        private_write(base / name, b"holder")
    elif kind == "lock-directory":
        (base / "state.db.quarantine.lock").mkdir(mode=0o700)
    else:
        (base / "backups").mkdir(mode=0o700)
        (base / "backups/config").mkdir(mode=0o700)
        backup = base / "backups/config/config.yaml.good.20261007-155245"
        private_write(backup, b"inert: true\n")
        if kind == "backup-digest":
            private_write(backup, b"unapproved config")
        elif kind == "backup-oversize":
            private_write(backup, b"x" * 65537)
        elif kind == "backup-reason":
            backup.rename(backup.with_name("config.yaml.corrupt.20261007-155245"))
        elif kind == "backup-extra-child":
            private_write(base / "backups/extra", b"unclassified")
        elif kind == "backup-depth":
            (base / "backups/config/extra").mkdir(mode=0o700)
        elif kind == "backup-count":
            for index in range(5):
                private_write(
                    backup.with_name(f"config.yaml.good.20261007-15524{index}"), b"inert: true\n"
                )
        else:
            private_write(base / "backups/config/auth.json", b"synthetic fallback")
    before = json.loads((root / "control/journal.json").read_bytes())
    files = {p: p.read_bytes() for p in base.rglob("*") if p.is_file()}
    expected = (
        "Populated or invalid inert bootstrap directory"
        if kind in {"cron", "hooks", "skills", "memories", "pairing", "image_cache", "audio_cache"}
        else "Unapproved native identity"
        if kind in {"soul", "soul-directory"}
        else "Nonempty or invalid native coordination lock"
        if kind in {"quarantine-lock", "fts-lock", "lock-directory"}
        else "Native config backup count"
        if kind == "backup-count"
        else "Fallback auth or unsafe case path"
        if kind == "backup-auth"
        else "Unapproved native config backup"
    )
    with pytest.raises(ValueError) as denied:
        if boundary == "archive":
            await slot.prepare(service)
        else:
            await slot.archive(service, 0, snapshot(slot, "STOPPED"))
    assert str(denied.value) == expected
    assert {p: p.read_bytes() for p in files} == files
    assert json.loads((root / "control/journal.json").read_bytes()) == before
    await slot.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 1),
        ("schema_version", 2.0),
        ("state_policy_sha256", "0" * 64),
        ("config_sha256", "0" * 64),
    ],
)
def test_native_policy_refuses_legacy_or_unbound_approval(
    tmp_path: Path, field: str, value: object
) -> None:
    root = tmp_path / "slot"
    provision(root, uuid4())
    policy = json.loads((root / "control/policy.json").read_bytes())
    case_slot.Policy.model_validate(policy)
    policy[field] = value
    with pytest.raises(ValueError):
        case_slot.Policy.model_validate(policy)


def test_native_state_policy_provenance_matches_product_and_default_fixture(tmp_path: Path) -> None:
    root = tmp_path / "slot"
    provision(root, uuid4())
    policy = case_slot.Policy.model_validate_json((root / "control/policy.json").read_bytes())
    manifest = Path(__file__).parents[2] / "integrations/hermes/upstream/inert-state-policy.json"
    raw = manifest.read_bytes()
    source = json.loads(raw)
    assert hashlib.sha256(raw).hexdigest() == policy.state_policy_sha256
    assert source["source_files"] == SOURCES == case_slot.SOURCE_FILES
    assert source["config"]["sha256"] == policy.config_sha256
    soul = (Path(__file__).parent / "fixtures/hermes-default-soul.txt").read_bytes()
    assert hashlib.sha256(soul).hexdigest() == source["new_active_children"]["SOUL.md"]["sha256"]


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


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", ["policy", "active", "archive", "journal", "nested_receipt"])
@pytest.mark.parametrize("schema_version", [True, 1.0], ids=["boolean", "float"])
async def test_coerced_state_schema_is_rejected_before_restore(
    tmp_path: Path, metadata: str, schema_version: object
) -> None:
    instance, selected = uuid4(), uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    slot = case_slot.CaseSlot(root, selected, instance, uuid4(), 1, 0, str(uuid4()))
    await slot.prepare(authority())
    await slot.observe(snapshot(slot))
    private_write(root / "active/state.db", b"preserved-case")
    await slot.archive(authority(), 0, snapshot(slot, "STOPPED"))
    await slot.close()
    path = {
        "policy": root / "control/policy.json",
        "active": root / "control/active.json",
        "archive": slot.archive_root / "receipt.json",
        "journal": root / "control/journal.json",
        "nested_receipt": root / "control/journal.json",
    }[metadata]
    value = json.loads(path.read_bytes())
    if metadata == "nested_receipt":
        value["receipt"]["schema_version"] = schema_version
    else:
        value["schema_version"] = schema_version
    private_write(path, json.dumps(value).encode())
    restored = case_slot.CaseSlot(root, selected, instance, uuid4(), 2, 0, str(uuid4()))
    try:
        with pytest.raises(ValueError):
            await restored.prepare(authority())
        assert not (root / "active/state.db").exists()
        assert (slot.archive_root / "data/active/state.db").read_bytes() == b"preserved-case"
    finally:
        await restored.close()


@pytest.mark.parametrize("schema_version", [True, 1.0], ids=["boolean", "float"])
def test_policy_schema_requires_exact_integer(tmp_path: Path, schema_version: object) -> None:
    root = tmp_path / "slot"
    provision(root, uuid4())
    value = json.loads((root / "control/policy.json").read_bytes())
    case_slot.Policy.model_validate(value)
    with pytest.raises(ValueError):
        case_slot.Policy.model_validate({**value, "schema_version": schema_version})


@pytest.mark.asyncio
@pytest.mark.parametrize("cut", ["active", "archive", "guard_exit"])
async def test_failed_final_authority_cannot_leave_an_adoptable_crash_commit(
    tmp_path: Path, cut: str
) -> None:
    import subprocess
    import sys

    instance, selected = uuid4(), uuid4()
    root = tmp_path / "slot"
    provision(root, instance)
    script = """
import asyncio, os, runpy, sys, time
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4
from omnis.supervisor import case_slot
helpers = runpy.run_path(sys.argv[4])
root, instance, selected = Path(sys.argv[1]), UUID(sys.argv[2]), UUID(sys.argv[3])
cut = sys.argv[5]
async def run():
    slot = case_slot.CaseSlot(root, selected, instance, uuid4(), 1, 0, str(uuid4()))
    await slot.prepare(helpers['authority']())
    await slot.observe(helpers['snapshot'](slot))
    helpers['private_write'](root / 'active/state.db', b'preserved-case')
    expiry = 0
    @asynccontextmanager
    async def guard(*args, **kwargs):
        nonlocal expiry
        expiry = time.monotonic_ns() + 500_000_000
        async def verify():
            if time.monotonic_ns() >= expiry:
                raise ValueError('simulated lease expired')
        yield SimpleNamespace(deadline_ns=expiry, verify=verify)
        if cut == 'guard_exit':
            os.write(1, b'cut reached\\n')
            os._exit(74)
        await verify()
    real_write = case_slot._write
    def write(path, value):
        real_write(path, value)
        target = 'active.json' if cut == 'active' else 'receipt.json'
        if cut != 'guard_exit' and path.name == target and value.state == 'ARCHIVED':
            os.write(1, b'cut reached\\n')
            time.sleep(max(0, (expiry - time.monotonic_ns()) / 1e9) + 0.015)
        if path.name == 'journal.json' and value.state == 'COMMITTED':
            os._exit(73)
    case_slot._write = write
    service = helpers['authority']()
    service.case_transition = guard
    try:
        await slot.archive(service, 0, helpers['snapshot'](slot, 'STOPPED'))
    except ValueError:
        os._exit(72)
    os._exit(75)
asyncio.run(run())
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            script,
            str(root),
            str(instance),
            str(selected),
            str(Path(__file__).resolve()),
            cut,
        ],
        timeout=8,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == "cut reached\n", completed.stderr
    assert completed.returncode == (74 if cut == "guard_exit" else 72), completed.stderr
    assert json.loads((root / "control/journal.json").read_bytes())["state"] == "PREPARED"
    assert (
        root / "archives" / str(selected) / "data/active/state.db"
    ).read_bytes() == b"preserved-case"
    restored = case_slot.CaseSlot(root, uuid4(), instance, uuid4(), 2, 0, str(uuid4()))
    try:
        with pytest.raises(ValueError, match="Incomplete"):
            await restored.prepare(authority())
        assert not (root / "active/state.db").exists()
    finally:
        await restored.close()
