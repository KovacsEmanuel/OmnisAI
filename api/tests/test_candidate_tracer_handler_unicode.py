"""Decoded capture text must fail as a domain outcome, not an encoding traceback."""

import json
from pathlib import Path

import pytest

from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.skill_catalog import compile_catalog, evaluate_pure


@pytest.mark.parametrize("text", ["\ud800", "\udfff"])
def test_candidate_tracer_handler_decoded_surrogate(text: str) -> None:
    root = Path(__file__).resolve().parents[2]
    compiled = compile_catalog(
        (root / "skills/recon-mapping-contract",), root / "profiles/recon-mapping-contract.yaml"
    )
    control = {"capture": json.dumps([{"method": "GET", "path": "/ok", "status": 200}])}
    assert len(evaluate_pure(compiled, control).outputs_json) == 3
    admitted = {"capture": json.dumps([{"method": "GET", "path": "/" + text, "status": 200}])}
    # The outer string is ASCII; the malformed scalar appears only after load_json.
    assert admitted["capture"].isascii()
    with pytest.raises(CatalogError, match="^INVALID_PURE_INPUT$"):
        evaluate_pure(compiled, admitted)


def test_candidate_tracer_handler_paired_surrogates_are_valid_unicode() -> None:
    root = Path(__file__).resolve().parents[2]
    compiled = compile_catalog(
        (root / "skills/recon-mapping-contract",), root / "profiles/recon-mapping-contract.yaml"
    )
    value = {"capture": r'[{"method":"GET","path":"/\ud83d\ude00","status":200}]'}
    assert len(evaluate_pure(compiled, value).outputs_json) == 3
