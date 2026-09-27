"""Generated Omnis contracts are deterministic and check mode never rewrites drift."""

import json
import subprocess
import sys
from pathlib import Path

from omnis.api import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_openapi_export_and_drift_check(tmp_path: Path) -> None:
    output = tmp_path / "omnis.openapi.json"
    command = [
        sys.executable,
        "-I",
        str(ROOT / "scripts/export_contracts.py"),
        "--output",
        str(output),
    ]
    exported = subprocess.run(command, capture_output=True, timeout=10)
    assert exported.returncode == 0, "The Omnis OpenAPI exporter must run successfully"
    assert json.loads(output.read_text()) == create_app().openapi()
    original = output.read_bytes()
    checked = subprocess.run([*command, "--check"], capture_output=True, timeout=10)
    assert checked.returncode == 0
    assert output.read_bytes() == original
    output.write_text("{}\n")
    drift = subprocess.run([*command, "--check"], capture_output=True, timeout=10)
    assert drift.returncode == 1
    assert b"OpenAPI drift" in drift.stderr
    assert output.read_text() == "{}\n"


def test_committed_contract_matches_current_routes() -> None:
    path = ROOT / "contracts/omnis.openapi.json"
    assert path.is_file(), "The first web consumer requires a versioned OpenAPI contract"
    assert json.loads(path.read_text()) == create_app().openapi()
