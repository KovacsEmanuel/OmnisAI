"""One installed H03/batch2/H04 node; existing private runner owns DB/family.

Batch2 collection is inert. Execution stays closed until parent adjudicates two
independent exact-snapshot reviews and explicitly binds BATCH2_REVIEWED.
H04 uses fresh singleton roots and its own closed H04_REVIEWED fence.
"""

import argparse
import hashlib
import importlib.util
import os
import stat
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path("/home/kali/OmnisAI")
PYTHON = ROOT / "api/.venv/bin/python"
UV = "/home/kali/.local/share/omnis-toolchains/bin/uv"
REVIEWED = "05ee180c0b11287c1b275c71fa63da1bdc3eaff8e8e2df59f1233ccbc5570c77"
ARTIFACT = Path(
    "/home/kali/.hermes/cache/scratch/jsonschema-packaging-c19198cc5fa9474cb9f0f507d11f84c7/h03-artifact.json"
)
ARTIFACT_SHA = "2eb29fc2d45210390caf0ba5037d590f2cc9adbcf2e3d80bce7e60bbe5ed32c1"
API_PREREQUISITES = (
    "/home/kali/.hermes/cache/scratch/h01-h02-installed-3913234cdfbd/prerequisites.json"
)
BATCH2_ROOT = Path(
    "/home/kali/.hermes/cache/scratch/p2-batch2-cdbfa74/installed-c6eac5f5a13440ffa6bcb35a6e853ab0"
)
BATCH2_SOURCE_SHA = "504e2ff667e2938e470cc67b14b33df86625df60b3dea5cce84de7b642eec05e"
BATCH2_REVIEWED: str | None = None
STARTUP_REVIEWED: str | None = None
STARTUP_SOURCE_SHA = "504e2ff667e2938e470cc67b14b33df86625df60b3dea5cce84de7b642eec05e"
STARTUP_CASE = "batch2-startup-only"
BATCH2_ARTIFACT = BATCH2_ROOT / "native-artifact.json"
BATCH2_ARTIFACT_SHA = "e097a2bc581678345050edfc31c0bf787890a0af527d9be6520436c122b70318"
BATCH2_READER = BATCH2_ROOT / "current-reader.json"
BATCH2_READER_SHA = "5f650e2e555c0e0d90d1e388367aa7fd781de15288bca62db0a936c4ea2b6007"
BATCH2_CASES = ("batch2-release-first", "batch2-stop-first")
H04_CASES = (
    "h04-inventory",
    "h04-root-lineage",
    "h04-child-lineage",
    "h04-guard-false",
    "h04-guard-exception",
)
H04_SOURCE_SHA = "6b1ec3f800b33f53af4f0b5b29f8f9eb0d8ef6deae6e3c6e7237fa49b3190886"
H04_REVIEWED: str | None = None
# Parent binds BOTH only after Admission API bytes are frozen and API-only
# build/origin readback completed. Never reuse/overwrite the batch2 reader.
H04_READER: Path | None = Path(
    "/home/kali/.hermes/cache/scratch/h04-api-reader-Htmt7Hzk/h04-current-reader.json"
)
H04_READER_SHA: str | None = "71c7b332043cb3dc34e1cf0706687b2fbfce2dc3f59ed6a6756ca703fac0620b"
CASES = ("runtime-restart", "runtime-restart-no-final", *BATCH2_CASES, STARTUP_CASE, *H04_CASES)


def selected_argv(case: str, collect_only: bool = False) -> list[str]:
    if case not in CASES:
        raise ValueError("Unsupported installed case")
    node = (
        str(ROOT / "api/tests/test_contract_method_pg.py")
        + "::test_contract_method_real_native_pg_owner_receipts_check_inbox["
        + case
        + "]"
    )
    leaf = (
        "h04-stock1-attempt1-"
        if case in H04_CASES
        else "batch2-stock1-"
        if case == STARTUP_CASE
        else "batch2-stock4-"
        if case in BATCH2_CASES
        else "jsonschema-h03-05ee-attempt1-"
    ) + case
    return [
        str(PYTHON),
        "-I",
        "-B",
        "-m",
        "pytest",
        "-p",
        "pytest_asyncio.plugin",
        "-p",
        "no:cacheprovider",
        "-c",
        str(ROOT / "api/pyproject.toml"),
        node,
        "-q",
        "--tb=line",
        "--basetemp=/home/kali/.hermes/cache/scratch/" + leaf,
        *(["--collect-only"] if collect_only else []),
    ]


def environment(base: Mapping[str, str], case: str, *, reviewed: bool = False) -> dict[str, str]:
    clean = {
        k: v
        for k, v in base.items()
        if k
        not in (
            "PYTHONPATH",
            "PYTHONHOME",
            "MYPYPATH",
            "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS",
        )
        and not k.startswith(("OMNIS_H03_", "OMNIS_BATCH2_"))
    }
    clean.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", OMNIS_CONTRACT_METHOD_NATIVE_PG="1")
    batch2 = case in BATCH2_CASES or case == STARTUP_CASE or case in H04_CASES
    namespace = "OMNIS_BATCH2" if batch2 else "OMNIS_H03"
    clean[namespace + "_ARTIFACT"] = str(BATCH2_ARTIFACT if batch2 else ARTIFACT)
    clean[namespace + "_ARTIFACT_SHA"] = BATCH2_ARTIFACT_SHA if batch2 else ARTIFACT_SHA
    if case in H04_CASES:
        if H04_READER is not None and H04_READER_SHA is not None:
            clean[namespace + "_API_PREREQUISITES"] = str(H04_READER)
            clean[namespace + "_API_PREREQUISITES_SHA"] = H04_READER_SHA
    else:
        clean[namespace + "_API_PREREQUISITES"] = (
            str(BATCH2_READER) if batch2 else API_PREREQUISITES
        )
        if batch2:
            clean[namespace + "_API_PREREQUISITES_SHA"] = BATCH2_READER_SHA
    digest = (
        H04_REVIEWED
        if case in H04_CASES
        else STARTUP_REVIEWED
        if case == STARTUP_CASE
        else BATCH2_REVIEWED
        if batch2
        else REVIEWED
    )
    if reviewed and digest is not None:
        clean[namespace + "_NORMATIVE_REVIEWED"] = digest
        clean[namespace + "_INPUT_REVIEWED"] = digest
    return clean


def _pinned_sha256(path: Path, maximum: int) -> str:
    """Only the fixed entry receipts/source below; no CLI-selected file authority."""
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Physical absolute path required")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    directory = os.open(path.anchor, flags | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(path.name, flags | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    try:
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.getuid()
            or not 0 <= before.st_size <= maximum
        ):
            raise ValueError("Owned single-link bounded regular file required")
        raw = bytearray()
        while len(raw) < maximum:
            chunk = os.read(fd, min(65536, maximum - len(raw)))
            if not chunk:
                break
            raw.extend(chunk)
        after = os.fstat(fd)
        stable = (
            "st_dev",
            "st_ino",
            "st_mode",
            "st_uid",
            "st_gid",
            "st_nlink",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if len(raw) != before.st_size or any(
            getattr(before, field) != getattr(after, field) for field in stable
        ):
            raise ValueError("Entry file changed while reading")
        return hashlib.sha256(raw).hexdigest()
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=CASES)
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--review-adjudicated", action="store_true")
    args = parser.parse_args()
    startup = args.case == STARTUP_CASE
    h04 = args.case in H04_CASES
    batch2 = args.case in BATCH2_CASES or startup or h04
    source = (
        H04_SOURCE_SHA
        if h04
        else STARTUP_SOURCE_SHA
        if startup
        else BATCH2_SOURCE_SHA
        if batch2
        else REVIEWED
    )
    artifact, expected = (
        (BATCH2_ARTIFACT, BATCH2_ARTIFACT_SHA) if batch2 else (ARTIFACT, ARTIFACT_SHA)
    )
    # Measured source393896, native receipts20477/19332, current reader15342 bytes.
    # Finite QA material bounds only; exact hashes remain mandatory.
    try:
        if _pinned_sha256(ROOT / "api/tests/test_contract_method_pg.py", 524288) != source:
            parser.error("Exact SOURCE snapshot changed; existing reviews cannot authorize it")
        if _pinned_sha256(artifact, 32768) != expected:
            parser.error("Exact installed artifact receipt changed")
        if batch2:
            reader = H04_READER if h04 else BATCH2_READER
            reader_sha = H04_READER_SHA if h04 else BATCH2_READER_SHA
            if reader is None or reader_sha is None:
                parser.error("Final frozen H04 API reader not bound")
            if _pinned_sha256(reader, 32768) != reader_sha:
                parser.error("Exact current reader receipt changed")
    except (OSError, ValueError):
        parser.error("Pinned entry file is unavailable, unsafe, oversized or unstable")
    if args.collect_only:
        return subprocess.call(
            selected_argv(args.case, True),
            cwd=ROOT,
            env=environment(os.environ, args.case),
        )
    approved = (
        H04_REVIEWED
        if h04
        else STARTUP_REVIEWED
        if startup
        else BATCH2_REVIEWED
        if batch2
        else REVIEWED
    )
    if not args.review_adjudicated or approved != source:
        parser.error(
            "Parent adjudication of both exact complementary reviews required; flag is not approval"
        )
    spec = importlib.util.spec_from_file_location("db_gate", ROOT / "ops/run_test_db_gate.py")
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    original_gate = runner.run_gate

    def selected_gate(
        command: object, base: Mapping[str, str], log: object, timeout_seconds: int
    ) -> object:
        return original_gate(
            selected_argv(args.case),
            environment(base, args.case, reviewed=True),
            log,
            timeout_seconds,
        )

    runner.__dict__["run_gate"] = selected_gate
    result: int = runner.prove_private_fixture("test-contract-method-native-pg", UV, 240)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
