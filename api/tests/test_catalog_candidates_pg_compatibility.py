"""Schema compatibility on the existing real, read-only PostgreSQL CLI consumer."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.engine import URL

import test_cli_status as cli_status
import test_control_regressions as control_regressions
import test_migrations as migrations


@pytest.mark.asyncio
async def test_catalog_candidates_pg_finalized_stop_readback_schema_compatibility(
    migrated_database_url: URL, monkeypatch: pytest.MonkeyPatch
) -> None:
    await control_regressions.test_finalized_stop_readback_refuses_committed_current_lease_takeover(
        migrated_database_url, monkeypatch
    )


@pytest.mark.asyncio
async def test_catalog_candidates_pg_upgrade_from_0008(
    empty_database_url: URL, tmp_path: Path
) -> None:
    await migrations.test_upgrade_from_0008_preserves_legacy_and_captures_catalog_ledger(
        empty_database_url, tmp_path
    )


def test_catalog_candidates_pg_installed_cli_status(
    migrated_database_url: URL,
    ipc_directory: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build/install the locked CLI wheel, then reuse the actual outside-checkout consumer."""
    uv = os.environ.get("UV") or shutil.which("uv")
    assert uv is not None, "Pinned uv must be on the runner PATH"
    env = {name: os.environ[name] for name in ("PATH", "HOME", "TMPDIR")}
    version = subprocess.run([uv, "--version"], env=env, capture_output=True, timeout=5)
    assert version.returncode == 0
    assert version.stdout.strip() == b"uv 0.12.19 (x86_64-unknown-linux-gnu)"
    root = Path(__file__).resolve().parents[2]
    wheel_dir, venv = tmp_path / "wheel", tmp_path / "venv"
    commands = [
        [
            uv,
            "build",
            "--no-config",
            "--offline",
            "--wheel",
            str(root / "cli"),
            "--out-dir",
            str(wheel_dir),
        ],
        [uv, "venv", "--no-config", "--no-python-downloads", "--python", sys.executable, str(venv)],
        [
            uv,
            "pip",
            "install",
            "--no-config",
            "--offline",
            "--python",
            str(venv / "bin/python"),
            "--no-deps",
            str(wheel_dir / "omnis_cli-0.1.2-py3-none-any.whl"),
        ],
    ]
    for index, command in enumerate(commands):
        completed = subprocess.run(command, env=env, cwd=tmp_path, capture_output=True, timeout=120)
        assert completed.returncode == 0, f"CLI wheel preparation stage {index} refused"
    monkeypatch.setenv("OMNIS_CLI_BIN", str(venv / "bin/omnis"))
    cli_status.test_installed_cli_status_has_private_identity_and_no_http_claim(
        migrated_database_url, ipc_directory
    )
