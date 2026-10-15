"""One installed H03/batch2 node; existing private runner owns DB/family.

Batch2 collection is inert. Execution stays closed until parent adjudicates two
independent exact-snapshot reviews and explicitly binds BATCH2_REVIEWED.
"""

import argparse
import hashlib
import importlib.util
import os
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
BATCH2_SOURCE_SHA = "2fd30261135e72e0f156a71f7be492e408b78076075d85cd102d2f280fdf8a9c"
BATCH2_REVIEWED: str | None = None
BATCH2_ARTIFACT = BATCH2_ROOT / "native-artifact.json"
BATCH2_ARTIFACT_SHA = "e097a2bc581678345050edfc31c0bf787890a0af527d9be6520436c122b70318"
BATCH2_READER = BATCH2_ROOT / "current-reader.json"
BATCH2_READER_SHA = "5f650e2e555c0e0d90d1e388367aa7fd781de15288bca62db0a936c4ea2b6007"
BATCH2_CASES = ("batch2-release-first", "batch2-stop-first")
CASES = ("runtime-restart", "runtime-restart-no-final", *BATCH2_CASES)


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
        "batch2-installed-attempt1-" if case in BATCH2_CASES else "jsonschema-h03-05ee-attempt1-"
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
        if k not in ("PYTHONPATH", "PYTHONHOME", "MYPYPATH", "PYTEST_ADDOPTS", "PYTEST_PLUGINS")
        and not k.startswith(("OMNIS_H03_", "OMNIS_BATCH2_"))
    }
    clean.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", OMNIS_CONTRACT_METHOD_NATIVE_PG="1")
    batch2 = case in BATCH2_CASES
    namespace = "OMNIS_BATCH2" if batch2 else "OMNIS_H03"
    clean[namespace + "_ARTIFACT"] = str(BATCH2_ARTIFACT if batch2 else ARTIFACT)
    clean[namespace + "_ARTIFACT_SHA"] = BATCH2_ARTIFACT_SHA if batch2 else ARTIFACT_SHA
    clean[namespace + "_API_PREREQUISITES"] = str(BATCH2_READER) if batch2 else API_PREREQUISITES
    digest = BATCH2_REVIEWED if batch2 else REVIEWED
    if reviewed and digest is not None:
        clean[namespace + "_NORMATIVE_REVIEWED"] = digest
        clean[namespace + "_INPUT_REVIEWED"] = digest
    return clean


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=CASES)
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--review-adjudicated", action="store_true")
    args = parser.parse_args()
    batch2 = args.case in BATCH2_CASES
    source = BATCH2_SOURCE_SHA if batch2 else REVIEWED
    if (
        hashlib.sha256((ROOT / "api/tests/test_contract_method_pg.py").read_bytes()).hexdigest()
        != source
    ):
        parser.error("Exact SOURCE snapshot changed; existing reviews cannot authorize it")
    artifact, expected = (
        (BATCH2_ARTIFACT, BATCH2_ARTIFACT_SHA) if batch2 else (ARTIFACT, ARTIFACT_SHA)
    )
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != expected:
        parser.error("Exact installed artifact receipt changed")
    if batch2 and hashlib.sha256(BATCH2_READER.read_bytes()).hexdigest() != BATCH2_READER_SHA:
        parser.error("Exact current reader receipt changed")
    if args.collect_only:
        return subprocess.call(
            selected_argv(args.case, True), cwd=ROOT, env=environment(os.environ, args.case)
        )
    if not args.review_adjudicated or batch2 and BATCH2_REVIEWED != BATCH2_SOURCE_SHA:
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
