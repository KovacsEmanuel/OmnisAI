"""Finite stopped T1/S1 upgrades; durable uncertainty is never a retry ticket."""

import hashlib
import json
import os
import re
import subprocess
import tarfile
import time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from .backup import (
    backup,
    cold_identity,
    private_bytes,
    restore,
    snapshot_metadata,
)
from .compose import _install_locked as install_image
from .compose import _record as image_record
from .config import load_config
from .instance import control_dir, load_instance, private_dir, state_dir
from .lifecycle import StartError, lifecycle_lock, mapping, read_record, write_record
from .release import (
    PROVIDER_SETTINGS_PROFILE,
    S1_RELEASE,
    S1_SCHEMA,
    T1_RELEASE,
    _install_locked,
    _manifest,
    _put,
    _sync_dir,
    installed_version,
    publish_directory,
)
from .restart import _prepare_reconciliation
from .start_runtime import ControlRuntime, private_identity
from .stop import readback_stopped
from .stop_receipt import completed_receipt, encoded, receipt_path, uuid, validate_grant


def persist(data: Path, intent: dict[str, object], state: str) -> None:
    intent["state"] = state
    write_record(data / "upgrade.json", intent, replace=True)
    if read_record(data / "upgrade.json") != intent:
        raise StartError("UPGRADE_INTENT_CHANGED", 4)


def migration(
    runtime: ControlRuntime,
    root: Path,
    control: Path,
    stopped: dict[str, object],
    intent: dict[str, object],
    data: Path,
) -> None:
    from .start import _check_pgdata, environment, service_ids, validate_config

    source = load_instance(data / str(intent["saved"]))
    if (source.release, source.schema, runtime.receipt.release, runtime.schema) not in {
        ("0.1.0", "0016_provider_models", T1_RELEASE, "0017_model_removal"),
        (T1_RELEASE, "0017_model_removal", S1_RELEASE, S1_SCHEMA),
    }:
        raise StartError("UPGRADE_SOURCE_INCOMPATIBLE", 4)
    flag = "--upgrade-s1" if runtime.run_catalog else "--upgrade-t1"
    runtime.attempt = str(intent["upgrade_id"])
    runtime.upgrading = True
    port = int(str(stopped["port"]))
    env = environment(runtime, root, control, port)
    validate_config(runtime, env)
    persist(data, intent, "DATABASE_PENDING")
    runtime.compose(
        env, "create", "--no-recreate", "--no-build", "--pull", "never", "db", effect=True
    )
    ids = service_ids(runtime, root, control, port)
    if set(ids) != {"db"}:
        raise StartError("UPGRADE_RESOURCE_MISMATCH", 4)
    db = ids["db"]
    _check_pgdata(root, stopped)
    runtime.run("start", db, effect=True)
    runtime.wait_container(db, healthy=True)
    if (
        runtime.psql(db, "SELECT system_identifier FROM pg_control_system()")
        != stopped["system_id"]
        or runtime.psql(db, "SELECT instance_id FROM instance_control WHERE id=1")
        != stopped["instance_id"]
        or runtime.psql(db, "SELECT version_num FROM alembic_version") != source.schema
    ):
        raise StartError("UPGRADE_DATABASE_MISMATCH", 4)
    completion = read_record(receipt_path(root, stopped))
    payload = {
        "version": 1,
        "reconciliation_id": str(intent["upgrade_id"]),
        "system_identifier": stopped["system_id"],
        "grant": completion["grant"],
        "completion_sha256": hashlib.sha256(
            private_bytes(receipt_path(root, stopped), 16384)
        ).hexdigest(),
    }
    persist(data, intent, "MIGRATION_PENDING")
    job = runtime.run(
        "create",
        "--name",
        runtime.receipt.project + "-migrate",
        "--label",
        "com.docker.compose.project=" + runtime.receipt.project,
        "--label",
        "com.docker.compose.service=migrate",
        "--label",
        "org.omnis.start-attempt=" + str(runtime.attempt),
        "--network",
        runtime.receipt.project + "_control",
        "--pull",
        "never",
        "--platform",
        "linux/amd64",
        "--restart",
        "no",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--interactive",
        "--attach",
        "stdin",
        "--attach",
        "stdout",
        "--attach",
        "stderr",
        "--env",
        "OMNIS_DATABASE_URL",
        "--env",
        "OMNIS_EXPECTED_SYSTEM_ID",
        runtime.receipt.image_id,
        "python",
        "-I",
        "-m",
        "omnis.migrate",
        flag,
        env={
            "OMNIS_DATABASE_URL": env["OMNIS_DATABASE_URL"],
            "OMNIS_EXPECTED_SYSTEM_ID": str(stopped["system_id"]),
        },
        effect=True,
    ).stdout.strip()
    if re.fullmatch(r"[0-9a-f]{64}", job) is None:
        raise StartError("UPGRADE_JOB_UNCERTAIN", 4)
    intent["job"] = job
    persist(data, intent, "MIGRATION_PENDING")
    # Exact immutable image/argv, no mounts or alternate entrypoint.
    item = runtime.attest(job, "migrate", root, control, port)
    config = mapping(mapping(item).get("Config"))
    if (
        mapping(item).get("Image") != runtime.receipt.image_id
        or config.get("Cmd") != ["python", "-I", "-m", "omnis.migrate", flag]
        or config.get("Entrypoint") not in (None, [])
        or mapping(mapping(item).get("State")).get("Status") != "created"
        or set(runtime.ids()) != {db, job}
    ):
        raise StartError("UPGRADE_JOB_UNCERTAIN", 4)
    result = runtime.run(
        "start",
        "--attach",
        "--interactive",
        job,
        stdin=encoded(payload) + b"\n",
        cap=30,
        effect=True,
    )
    after = runtime.attest(job, "migrate", root, control, port)
    state = mapping(mapping(after).get("State"))
    if (
        result.returncode != 0
        or result.stderr
        or len(result.stdout.encode()) > 16384
        or state.get("Status") != "exited"
        or state.get("ExitCode") != 0
        or state.get("Running") is not False
        or runtime.uncertain
        or not runtime.family_drained
        or json.loads(result.stdout) != {"ok": True, "schema": runtime.schema, "request": payload}
        or runtime.psql(db, "SELECT version_num FROM alembic_version") != runtime.schema
    ):
        raise StartError("UPGRADE_MIGRATION_UNCERTAIN", 4)
    persist(data, intent, "MIGRATED")
    for ident in (job, db):
        if ident == db:
            runtime.run("container", "stop", "--time", "15", ident, cap=22, effect=True)
            if (
                mapping(mapping(runtime.inspect("container", ident)).get("State")).get("Running")
                is not False
            ):
                raise StartError("UPGRADE_CLEANUP_UNCERTAIN", 4)
        runtime.run("container", "rm", ident, effect=True)
        if runtime.inspect("container", ident) is not None:
            raise StartError("UPGRADE_CLEANUP_UNCERTAIN", 4)
    net = runtime.network(set())
    if net is not None:
        runtime.run("network", "rm", net, effect=True)
    absent(runtime)
    if cold_identity(runtime, root) != stopped["system_id"]:
        raise StartError("UPGRADE_DATABASE_MISMATCH", 4)


def absent(runtime: ControlRuntime) -> None:
    runtime.check_daemon()
    if (
        runtime.uncertain
        or not runtime.family_drained
        or runtime.ids()
        or runtime.inspect("network", runtime.receipt.project + "_control") is not None
    ):
        raise StartError("UPGRADE_RESOURCES_UNCERTAIN", 4)


def prepare_restart(
    runtime: ControlRuntime,
    root: Path,
    stopped: dict[str, object],
    attempt: str,
    intent: dict[str, object],
) -> dict[str, object]:
    data = runtime.release.parents[1]
    saved = data / str(intent["saved"])
    raw = private_bytes(saved / "startup.json", 16384)
    completion = private_bytes(saved / "completion.json", 16384)
    if (
        read_record(data / "upgrade.json") != intent
        or intent["state"] != "STARTING"
        or private_bytes(root / "startup.json", 16384) != raw
        or private_bytes(receipt_path(root, stopped), 16384) != completion
        or runtime.digest != intent["target_digest"]
        or (
            getattr(runtime, "run_catalog", False)
            and private_identity(root / "catalog") != intent.get("catalog_identity")
        )
    ):
        raise StartError("UPGRADE_INTENT_CHANGED", 4)
    return _prepare_reconciliation(root, stopped, attempt, raw, completion)


def rollback(runtime: ControlRuntime, data: Path, root: Path, intent: dict[str, object]) -> None:
    # Only an acknowledged, drained pre-OPEN failure is reversible automatically.
    if intent.get("state") not in {"IMAGE_READY", "MIGRATED", "PUBLISHED", "STARTING"}:
        raise StartError("UPGRADE_ROLLBACK_REFUSED", 4)
    absent(runtime)
    if os.path.lexists(root / "startup.json") and "open_command" in read_record(
        root / "startup.json"
    ):
        current = read_record(root / "startup.json")
        if current.get("attempt") != intent["old_attempt"]:
            raise StartError("UPGRADE_ROLLBACK_REFUSED", 4)
    saved = data / str(intent["saved"])
    old = ControlRuntime(
        data.parent,
        time.monotonic() + 180,
        upgrade_id=str(intent["upgrade_id"]),
        binding=saved,
        version=installed_version(saved),
    )
    snapshot = Path(str(intent["backup"]))
    snapshot_metadata(old, snapshot, full=True)
    key = root / "vault-key/master.key"
    private_bytes(key, 32)
    quarantine = root.with_name("omnis-upgrade-failed-" + str(intent["upgrade_id"]))
    if os.path.lexists(quarantine):
        raise StartError("UPGRADE_ROLLBACK_REFUSED", 4)
    persist(data, intent, "ROLLBACK_PENDING")
    publish_directory(root, quarantine)
    _sync_dir(root.parent)
    restore(old, root, snapshot, quarantine / "vault-key/master.key")
    write_record(data / "image.json", read_record(saved / "image.json"), replace=True)
    write_record(data / "installed.json", read_record(saved / "installed.json"), replace=True)
    intent["quarantine"] = str(quarantine)
    persist(data, intent, "ROLLED_BACK")


def completed_history(data: Path, old: ControlRuntime, stopped: dict[str, object]) -> bytes:
    from .stop import _stopping_record

    path = data / "upgrade.json"
    raw = private_bytes(path, 16384)
    previous = read_record(path)
    if (
        set(previous)
        != {
            "version",
            "state",
            "upgrade_id",
            "saved",
            "backup",
            "target_digest",
            "source_digest",
            "old_attempt",
            "instance_id",
            "restore_probe",
            "job",
        }
        or type(previous["version"]) is not int
        or previous["version"] != 1
        or previous["state"] != "COMPLETE"
        or previous["target_digest"] != old.digest
        or previous["instance_id"] != stopped["instance_id"]
        or not isinstance(previous["saved"], str)
        or not previous["saved"].startswith("upgrade-source-")
    ):
        raise StartError("UPGRADE_RECOVERY_REQUIRED", 4)
    uuid(previous["upgrade_id"])
    uuid(previous["saved"].removeprefix("upgrade-source-"))
    saved = data / previous["saved"]
    private_dir(saved)
    source = load_instance(saved)
    image = image_record(saved / "image.json", str(previous["source_digest"]), complete=True)
    record = read_record(saved / "startup.json")
    _stopping_record(record)
    grant = mapping(read_record(saved / "completion.json").get("grant"))
    validate_grant(grant, record, mapping(grant.get("inventory")))
    completed_receipt(saved / "completion.json", grant)
    if (
        installed_version(saved) != "0.1.0"
        or (source.release, source.schema) != ("0.1.0", "0016_provider_models")
        or source.instance_id != stopped["instance_id"]
        or record.get("phase") != "STOPPED"
        or record.get("format") != 5
        or record.get("instance_id") != source.instance_id
        or record.get("system_id") != stopped["system_id"]
        or record.get("attempt") != previous["old_attempt"]
        or record.get("release_digest") != previous["source_digest"]
        or image is None
        or image.release != source.release
        or image.profile != PROVIDER_SETTINGS_PROFILE
        or image.project != old.receipt.project
        or image.image_id != record.get("image_id")
        or image.docker_id != old.receipt.docker_id
        or image.docker_host != old.host
        or re.fullmatch(r"[0-9a-f]{64}", str(previous["job"])) is None
        or any(
            not isinstance(previous[name], str) or not Path(str(previous[name])).is_absolute()
            for name in ("backup", "restore_probe")
        )
    ):
        raise StartError("UPGRADE_RECOVERY_REQUIRED", 4)
    return raw


def upgrade(bundle: Path, snapshot: Path) -> dict[str, object]:
    from .start import start_instance

    manifest, payloads = _manifest(bundle)
    target = mapping(json.loads(manifest))
    version = str(target.get("release"))
    if (version, target.get("schema")) not in {
        (T1_RELEASE, "0017_model_removal"),
        (S1_RELEASE, S1_SCHEMA),
    } or target.get("profile") != PROVIDER_SETTINGS_PROFILE:
        raise StartError("UPGRADE_TARGET_INCOMPATIBLE", 2)
    private_dir(snapshot.parent)
    if not snapshot.is_absolute() or snapshot.resolve() != snapshot or os.path.lexists(snapshot):
        raise StartError("UPGRADE_BACKUP_DESTINATION_INVALID", 2)
    data_home = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    data = data_home / "omnis"
    root = state_dir()
    config = load_config()
    config.check_instance(root)
    old = ControlRuntime(data_home, time.monotonic() + 300)
    expected_source = (
        (T1_RELEASE, "0017_model_removal")
        if version == S1_RELEASE
        else ("0.1.0", "0016_provider_models")
    )
    if not old.provider_settings or (installed_version(data), old.schema) != expected_source:
        raise StartError("UPGRADE_SOURCE_INCOMPATIBLE", 2)
    intent: dict[str, object] = {}
    with lifecycle_lock(data, old.deadline), lifecycle_lock(root, old.deadline):
        previous = None
        if os.path.lexists(data / "upgrade.json") and version != S1_RELEASE:
            raise StartError("UPGRADE_RECOVERY_REQUIRED", 4)
        stopped = read_record(root / "startup.json")
        readback_stopped(old, root, control_dir(root), stopped)
        if stopped.get("format") != 5:
            raise StartError("UPGRADE_SOURCE_INCOMPATIBLE", 2)
        if os.path.lexists(data / "upgrade.json"):
            previous = completed_history(data, old, stopped)
        if version == S1_RELEASE and os.path.lexists(root / "catalog"):
            raise StartError("UPGRADE_CATALOG_EXISTS", 4)
        key = root / "vault-key/master.key"
        if len(private_bytes(key, 32)) != 32:
            raise StartError("UPGRADE_MASTER_KEY_REQUIRED", 2)
        for location in (bundle, snapshot):
            if (
                location == root
                or root in location.parents
                or location in root.parents
                or location == data
                or data in location.parents
                or location in data.parents
            ):
                raise StartError("UPGRADE_PATH_OVERLAP", 2)
        saved = data / ("upgrade-source-" + str(uuid4()))
        saved.mkdir(mode=0o700)
        for name, source in (
            ("startup.json", root / "startup.json"),
            ("completion.json", receipt_path(root, stopped)),
            ("image.json", data / "image.json"),
            ("installed.json", data / "installed.json"),
            ("instance.json", root / "instance.json"),
        ):
            _put(saved / name, private_bytes(source, 16384))
        if previous is not None:
            _put(saved / "upgrade.json", previous)
        _sync_dir(saved)
        intent = {
            "version": 1,
            "state": "BACKUP_PENDING",
            "upgrade_id": str(uuid4()),
            "saved": saved.name,
            "backup": str(snapshot),
            "target_digest": hashlib.sha256(manifest).hexdigest(),
            "source_digest": old.digest,
            "old_attempt": stopped["attempt"],
            "instance_id": stopped["instance_id"],
        }
        if previous is not None and private_bytes(data / "upgrade.json", 16384) != previous:
            raise StartError("UPGRADE_INTENT_CHANGED", 4)
        write_record(data / "upgrade.json", intent, replace=previous is not None)
        # Reuse the exact source runtime; the durable fence excludes all other callers.
        backup(old, root, snapshot)
        trial = root.with_name("omnis-upgrade-restore-" + str(intent["upgrade_id"]))
        restore(old, trial, snapshot, key)
        intent["restore_probe"] = str(trial)
        persist(data, intent, "BACKUP_VERIFIED")
        release = _install_locked(data, manifest, payloads, activate=False)
        binding = data / ("upgrade-target-" + str(intent["upgrade_id"]))
        binding.mkdir(mode=0o700)
        persist(data, intent, "IMAGE_PENDING")
        image = install_image(
            binding,
            release,
            str(intent["target_digest"]),
            profile=PROVIDER_SETTINGS_PROFILE,
            project=old.receipt.project,
            version=version,
        )
        if image.docker_id != old.receipt.docker_id or image.docker_host != old.host:
            raise StartError("UPGRADE_DAEMON_CHANGED", 4)
        persist(data, intent, "IMAGE_READY")
        runtime = ControlRuntime(
            data_home,
            time.monotonic() + 300,
            upgrade_id=str(intent["upgrade_id"]),
            binding=binding,
            version=version,
        )
        if runtime.run_catalog:
            (root / "catalog").mkdir(mode=0o700)
            runtime.upgrade_catalog_identity = private_identity(root / "catalog")
            intent["catalog_identity"] = runtime.upgrade_catalog_identity
            _sync_dir(root)
            persist(data, intent, "IMAGE_READY")
        migration(runtime, root, control_dir(root), stopped, intent, data)
        # A durable fence makes these separate atomic publications inaccessible to other callers.
        persist(data, intent, "PUBLISH_PENDING")
        write_record(data / "image.json", read_record(binding / "image.json"), replace=True)
        write_record(data / "installed.json", {"format": 1, "release": version}, replace=True)
        instance = asdict(load_instance(root))
        instance.update(release=version, schema=runtime.schema)
        write_record(root / "instance.json", {"version": 1, **instance}, replace=True)
        persist(data, intent, "STARTING")
    result = start_instance(_upgrade=intent)
    persist(data, intent, "COMPLETE")
    return {**result, "upgrade": "COMPLETED", "backup_verified": True}


def upgrade_command(bundle: Path, snapshot: Path, *, as_json: bool) -> int:
    try:
        result = upgrade(bundle, snapshot)
        code = 0
    except (
        OSError,
        ValueError,
        subprocess.SubprocessError,
        tarfile.TarError,
        KeyboardInterrupt,
    ) as exc:
        code = exc.code if isinstance(exc, StartError) else 2
        data = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "omnis"
        if os.path.lexists(data / "upgrade.json"):
            intent = read_record(data / "upgrade.json")
            if intent.get("state") not in {"COMPLETE", "ROLLED_BACK", "REFUSED"}:
                code = 4
        result = {
            "state": "UNCERTAIN" if code == 4 else "REFUSED",
            "reason": exc.reason if isinstance(exc, StartError) else "UPGRADE_REFUSED",
            "dashboard_ready": False,
        }
        # Persisted intent is deliberately retained even when output or cleanup fails.
    print(
        json.dumps(result, sort_keys=True)
        if as_json
        else f"Omnis: {result['state']} ({result.get('reason', 'upgrade completed')})"
    )
    return code
