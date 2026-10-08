"""Real PURE transformations, with independent goldens and strict input refusals.

Synthetic captures are supplied data, not HTTP requests or vulnerability evidence.
"""

import json

import pytest

from fixtures.b06a.consumer import (
    FIXTURES,
    MARKER,
    CatalogSeed,
    mapping,
    sequence,
    source_bytes,
    stable_block,
)
from fixtures.b06a.consumer import (
    seed as seed,
)


def golden() -> dict[str, object]:
    value: object = json.loads((FIXTURES / "golden.json").read_text(encoding="utf-8"))
    return mapping(value)


def test_three_real_outputs_match_independent_golden(seed: CatalogSeed) -> None:
    expected = golden()
    before = source_bytes(seed)
    compiled = seed.compile()
    result = seed.evaluate(expected["input"])
    outputs = sequence(result["outputs"])
    assert len(outputs) == 3
    assert outputs == expected["outputs"]
    for name in ("material_digest", "resolved_index_digest", "resolution"):
        assert result[name] == compiled[name]
    assert source_bytes(seed) == before
    assert "vulnerability" not in result and "findings" not in result


def test_same_input_is_deterministic_in_fresh_consumers(seed: CatalogSeed) -> None:
    expected = golden()
    first = seed.evaluate(expected["input"])
    second = seed.evaluate(expected["input"])
    assert first == second
    assert first["outputs"] == expected["outputs"]


@pytest.mark.parametrize(
    "value",
    [
        {},
        {"capture": []},
        {"capture": "[" + MARKER},
        {"capture": '[{"method":"GET","path":"/alpha","status":true}]'},
        {"capture": '[{"method":"get","path":"/alpha","status":200}]'},
        {
            "capture": '[{"method":"GET","path":"https://invalid.example/'
            + MARKER
            + '","status":200}]'
        },
        {"capture": '[{"method":"GET","path":"/alpha","status":600}]'},
    ],
)
def test_invalid_capture_contract_is_not_coerced(seed: CatalogSeed, value: object) -> None:
    seed.evaluate(golden()["input"])
    path = seed.input(value)
    stable_block(seed, "evaluate", "--input", str(path))


def test_input_above_one_mib_is_refused_before_parsing(seed: CatalogSeed) -> None:
    seed.evaluate(golden()["input"])
    path = seed.directory / "oversize-input.json"
    path.write_text(json.dumps({"capture": MARKER + "x" * 1048576}), encoding="utf-8")
    stable_block(seed, "evaluate", "--input", str(path))
