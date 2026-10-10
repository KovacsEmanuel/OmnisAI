"""C03 wire encoding must refuse before any database request, not normalize BOM."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from omnis.modules.runs import contract_inputs, managed_admission
from omnis.modules.settings import candidate_catalog
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks.managed_contract import mapping
from test_c03_managed_capture import request


@pytest.mark.parametrize("module_name", ["input", "assignment", "evaluation"])
def test_c03_private_cli_bom_denied_before_database(
    module_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("OMNIS_DATABASE_URL", raising=False)
    value = request()
    if module_name == "input":
        main = contract_inputs.main
        operation = "create-input"
        value = {
            "schema_version": 1,
            "owner_id": str(uuid4()),
            "command_id": str(uuid4()),
            "context_ref": value["context_ref"],
            "input": {"capture": "[]"},
        }
    elif module_name == "assignment":
        main = managed_admission.main
        operation = "prepare-composed"
    else:
        main = candidate_catalog.main
        operation = "admit-evaluation-capture"
        value = {
            "schema_version": 2,
            "owner_id": str(uuid4()),
            "command_id": str(uuid4()),
            "snapshot_ref": {**mapping(value["selection_ref"]), "kind": "candidate-snapshot"},
            "value": {"capture": "[]"},
        }
    path = tmp_path / "request.json"
    args = [operation, "--request", str(path), "--catalog-root", str(tmp_path / "catalog")]
    path.write_bytes(canonical(value))
    assert main(args) == 2
    positive = capsys.readouterr()
    assert not positive.out and json.loads(positive.err)["reason"] == "DATABASE_UNAVAILABLE"
    path.write_bytes(b"\xef\xbb\xbf" + canonical(value))
    assert main(args) == 2
    denial = capsys.readouterr()
    assert not denial.out and json.loads(denial.err)["reason"] == "INVALID_JSON"
