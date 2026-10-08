"""C01 black-box positive gate: reach the feature before acquiring PostgreSQL."""

import copy
import os
import subprocess
from uuid import uuid4

import pytest

from fixtures.b06b_publication.consumer import (
    Qualified,
    Seed,
    canonical,
    cli_command,
    confirmed,
    material_digest,
    new_seed,
    strict_json,
)
from omnis.modules.settings import candidate_store

MODULE = "omnis.modules.settings.catalog_publication"


def test_publication_cli_exists_before_database_acquisition() -> None:
    command = cli_command(MODULE, "--help")
    result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    assert all(
        operation in result.stdout
        for operation in ("head", "confirm", "publish", "readback", "snapshot")
    )


def test_new_owned_fixture_compiles_and_pure_evaluates_without_db() -> None:
    seed = new_seed()
    command = cli_command(
        "omnis.modules.settings.skill_catalog",
        "evaluate",
        "--package",
        str(seed.package),
        "--profile",
        str(seed.profile),
        "--input",
        str(seed.directory / "input.json"),
    )
    result = subprocess.run(
        command, cwd=seed.directory, capture_output=True, text=True, timeout=15, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    report = strict_json(result.stdout)
    assert report["status"] == "PURE_PASS"
    assert report["material_digest"] == material_digest(seed.package, seed.profile)
    assert report["resolution"] == "NO_MODEL" and report["effective"] is None
    outputs = report["outputs"]
    assert isinstance(outputs, list) and len(outputs) == 3
    assert outputs[-1] == {
        "surface_map": [
            {"path": "/b06b/submit", "methods": ["POST"], "operation_count": 1},
            {"path": "/b06b/synthetic", "methods": ["GET"], "operation_count": 1},
        ]
    }
    assert not seed.root.exists(), "non-durable source qualification created catalog material"
    repeated = subprocess.run(
        command, cwd=seed.directory, capture_output=True, text=True, timeout=15, check=False
    )
    assert repeated.returncode == 0 and repeated.stderr == ""
    assert strict_json(repeated.stdout) == report


def test_confirmation_oracle_matches_nested_selection_and_rejects_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Oracle regression only; substituted transport is not TTY/PG authority."""
    seed = new_seed()
    selected: dict[str, object] = {"expected_head_generation": 1, "material_digest": "0" * 64}
    qualified = Qualified(seed, {}, {}, {}, {}, {}, {}, selected)
    body: dict[str, object] = {
        "selection": selected,
        "actor": f"local-operator:{os.getuid()}",
        "author_kind": "OPERATOR",
        "created_by": seed.owner,
    }
    current = body

    def transport(
        self: Seed, request: dict[str, object], database_url: str, answer: str = "yes"
    ) -> tuple[subprocess.CompletedProcess[str], str]:
        record = candidate_store.envelope("operator-confirmation", current)
        result = {"confirmation": record, "confirmation_ref": candidate_store.reference(record)}
        return subprocess.CompletedProcess([], 0, canonical(result).decode(), ""), "operator"

    monkeypatch.setattr(Seed, "confirm", transport)
    confirmed(qualified, "NOT_A_DATABASE_URL")
    for mutation in (
        {"selection": {**selected, "material_digest": "1" * 64}},
        {"selection": {**selected, "unrecognized": True}},
        {"created_by": str(uuid4())},
        {"unrecognized": True},
    ):
        current = {**copy.deepcopy(body), **mutation}
        with pytest.raises(AssertionError):
            confirmed(qualified, "NOT_A_DATABASE_URL")
