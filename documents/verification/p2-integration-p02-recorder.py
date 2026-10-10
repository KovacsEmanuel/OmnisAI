"""P02 metadata recorder around the existing private DB owner, not a new runner.

Executed only from the hash-bound integration/record-p02.py copy after a separate
coordinator grant and copy-install preflight. No provision/cleanup implementation
is duplicated here. The owner writes its original fixture manifest; this wrapper
records filesystem identities before returning control to its gate/DDL path.
"""

import hashlib
import json
import os
import runpy
import signal
import stat
from pathlib import Path

REPO = Path("/home/kali/OmnisAI")
CONTROL = Path("/home/kali/.hermes/run/omnis-p2-critical-20261010")
INTEGRATION = CONTROL / "integration"
ATTEMPT = Path("/home/kali/.hermes/cache/scratch/p2i-bd68319d3025/p02")
SID = "20261010_215158_76ea2f"
NONCE = "295aaa52911f4d1f8e9b8302bc424bf7"
UV = "/home/kali/.hermes/cache/scratch/r3-5gjabhuw/tools/uv"
TARGET = "test-model-projection-pg"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def registry():
    value = read(INTEGRATION / "resources.json")
    matches = [a for a in value["attempts"] if a["id"] == "p02"]
    if len(matches) != 1 or matches[0]["intent_nonce"] != NONCE:
        raise ValueError("P02 registration mismatch")
    return value, matches[0]


def write_registry(value):
    path = INTEGRATION / "resources.json"
    temporary = INTEGRATION / ("resources-p02-" + NONCE + ".new")
    raw = (json.dumps(value, indent=2) + "\n").encode()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)
    directory = os.open(INTEGRATION, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    if path.read_bytes() != raw:
        raise ValueError("P02 registration readback mismatch")


def require_grant():
    from datetime import UTC, datetime

    effects = read(CONTROL / "effects.json")
    if effects.get("holder") != "integration" or type(effects.get("fixture_grant_path")) is not str:
        raise ValueError("P02 effect not granted")
    grant_path = Path(effects["fixture_grant_path"])
    if grant_path.parent != INTEGRATION:
        raise ValueError("P02 grant locator mismatch")
    grant_raw = grant_path.read_bytes()
    grant = json.loads(grant_raw)
    request_raw = (INTEGRATION / "fixture-request-p02.json").read_bytes()
    if (
        effects["holder"] != "integration"
        or effects["holder_session_id"] != SID
        or effects["grant_nonce"] != NONCE
        or grant["intent_nonce"] != NONCE
        or grant["owner_session_id"] != SID
        or effects["fixture_grant_sha256"] != sha(grant_raw)
        or grant["request_sha256"] != sha(request_raw)
        or effects["fixture_request_sha256"] != sha(request_raw)
        or effects["allowed_new_attempt"] != str(ATTEMPT)
        or TARGET not in effects["allowed_worker_fixture_targets"]
        or TARGET not in grant["targets"]
        or datetime.now(UTC) >= datetime.fromisoformat(grant["deadline"])
    ):
        raise ValueError("P02 effect not granted")
    value, attempt = registry()
    if sha(Path(__file__).read_bytes()) != attempt["recorder_sha256"]:
        raise ValueError("P02 recorder changed")
    info = ATTEMPT.lstat()
    pinned = attempt["filesystem_identities"][str(ATTEMPT)]
    if (
        not stat.S_ISDIR(info.st_mode)
        or (info.st_dev, info.st_ino) != (pinned["dev"], pinned["ino"])
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ValueError("P02 root identity changed")
    return value, attempt


def main():
    value, attempt = require_grant()
    if attempt["state"] != "COPY_INSTALLED_ATTESTED_READY_FOR_SINGLE_GATE":
        raise ValueError("P02 gate already used or not prepared")
    if os.environ.get("TMPDIR") != str(ATTEMPT / "tmp") or os.environ.get("HOME") != str(
        ATTEMPT / "home"
    ):
        raise ValueError("P02 environment mismatch")
    manifest_path = Path(attempt["input_manifest"])
    if manifest_path.parent != INTEGRATION:
        raise ValueError("P02 source manifest locator changed")
    manifest_raw = manifest_path.read_bytes()
    if sha(manifest_raw) != attempt["input_manifest_sha256"]:
        raise ValueError("P02 source manifest changed")
    inputs = json.loads(manifest_raw)
    for name, expected in inputs["inputs"].items():
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.name == "Omnis_Notite_Originale.html"
            or any(
                p.startswith(".env")
                or p in {"auth.json", "credentials.json", "dumps", "raw", "bug-bounty-triage"}
                for p in relative.parts
            )
        ):
            raise ValueError("P02 source path outside scope")
        path = REPO / relative
        if path.resolve() != path or sha(path.read_bytes()) != expected:
            raise ValueError("P02 source changed")
    for name, expected in attempt["artifact_hashes"].items():
        path = Path(name)
        if (
            path.resolve() != path
            or not path.is_relative_to(ATTEMPT)
            or sha(path.read_bytes()) != expected
        ):
            raise ValueError("P02 installed artifact changed")
    # Atomic retained consumption: two valid READY readers must not both
    # enter provisioning. A crash/write error consumes conservatively too;
    # never remove this marker to retry the same grant.
    consumed = ATTEMPT / ("consumed-" + NONCE + ".json")
    fd = os.open(consumed, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump({"owner_session_id": SID, "intent_nonce": NONCE, "target": TARGET}, output)
        output.flush()
        os.fsync(output.fileno())
    directory = os.open(ATTEMPT, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    attempt["consumed_marker"] = str(consumed)
    attempt["state"] = "GATE_SUBMITTED_ONCE"
    write_registry(value)
    namespace = runpy.run_path(str(REPO / "ops/run_test_db_gate.py"))
    owner = namespace["prove_private_fixture"].__globals__
    original_manifest = owner["write_fixture_manifest"]

    def registered_manifest(paths, project, cid, image_id, endpoint, daemon_id, identity):
        value, attempt = require_grant()
        if attempt["state"] != "GATE_SUBMITTED_ONCE" or Path(paths.root).parent != ATTEMPT / "tmp":
            raise ValueError("P02 generated root mismatch")
        result = original_manifest(paths, project, cid, image_id, endpoint, daemon_id, identity)
        identities = {}
        for path in (
            Path(paths.root),
            Path(paths.data),
            Path(paths.data) / "18/docker",
            Path(paths.socket),
        ):
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or path.resolve() != path:
                raise ValueError("P02 generated filesystem identity mismatch")
            identities[str(path)] = {
                "dev": info.st_dev,
                "ino": info.st_ino,
                "uid": info.st_uid,
                "mode": oct(stat.S_IMODE(info.st_mode)),
            }
        attempt.update(
            state="FIXTURE_ATTESTED_REGISTERED_BEFORE_GATE_DDL",
            project=project,
            cid=cid,
            daemon={"endpoint": endpoint, "identity": daemon_id},
            image_id=image_id,
            system_identifier=identity,
            fixture_manifest=str(result),
            fixture_manifest_sha256=sha(result.read_bytes()),
            generated_filesystem_before_ddl=identities,
            data=str(Path(paths.data) / "18/docker"),
            ipc=str(paths.socket),
            family_receipt=str(Path(paths.root) / "gate.log.result.json"),
        )
        write_registry(value)
        return result

    owner["write_fixture_manifest"] = registered_manifest
    signal.signal(signal.SIGINT, owner["_request_stop"])
    signal.signal(signal.SIGTERM, owner["_request_stop"])
    result = owner["prove_private_fixture"](TARGET, UV, 900)
    value, attempt = registry()
    attempt["outer_exit"] = result
    attempt["state"] = "GATE_EXITED_READBACK_PENDING"
    write_registry(value)
    return result


if __name__ == "__main__":
    try:
        result = main()
    except (OSError, ValueError, KeyError, TypeError):
        print("P02_RECORDER_BLOCKED_READBACK_REQUIRED")
        result = 2
    raise SystemExit(result)
