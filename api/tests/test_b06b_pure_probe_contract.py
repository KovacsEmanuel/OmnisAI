"""B06b PURE consumer availability is checked before any DB acquisition."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from fixtures.b06b_publication.consumer import canonical, cli_command, new_seed, strict_json
from fixtures.b06b_pure_probe.consumer import ACTUAL_INPUT, EXPECTED_OUTPUTS, require_consumer

ROOT = Path(__file__).resolve().parents[2]
TARGET = "test-b06b-pure-probe-pg"


def test_pure_probe_cli_exists_before_database_acquisition() -> None:
    require_consumer()


def test_new_input_really_differs_from_c01_qualification_without_database() -> None:
    seed = new_seed()
    assert strict_json((seed.directory / "input.json").read_text()) != ACTUAL_INPUT
    supplied = seed.directory / "actual-input.json"
    supplied.write_bytes(canonical(ACTUAL_INPUT))
    result = subprocess.run(
        cli_command(
            "omnis.modules.settings.skill_catalog",
            "evaluate",
            "--package",
            str(seed.package),
            "--profile",
            str(seed.profile),
            "--input",
            str(supplied),
        ),
        cwd=seed.directory,
        env={
            key: value for key, value in seed.environment("").items() if key != "OMNIS_DATABASE_URL"
        },
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0 and result.stderr == ""
    assert strict_json(result.stdout)["outputs"] == EXPECTED_OUTPUTS
    assert not seed.root.exists()


@pytest.mark.parametrize("flag", ["-n", "-t", "-q", "-i"])
def test_scoped_make_target_rejects_nonexecuting_or_ignored_verification(flag: str) -> None:
    result = subprocess.run(
        ["make", "--no-print-directory", flag, TARGET],
        cwd=ROOT,
        env={"PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert "Unsafe Make flags for verification" in result.stderr


def test_scoped_runner_admits_named_target_without_provisioning() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(ROOT / "ops/run_test_db_gate.py"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0 and result.stderr == ""
    assert TARGET in result.stdout
