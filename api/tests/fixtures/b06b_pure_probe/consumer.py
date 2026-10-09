"""B06b PURE consumer; reuse accepted C01 source/transport without editing it.

Actual execution uses new supplied data. No expected output comes from the
product evaluator; source qualification is only a separate prerequisite.
"""

import importlib.util
import subprocess
from pathlib import Path
from uuid import uuid4

from fixtures.b06b_publication.consumer import (
    Seed,
    canonical,
    cli_command,
    envelope,
    exact_ref,
    mapping,
    sequence,
    sha,
)

MODULE = "omnis.modules.runs.pure_probe"
RECIPE = "publication-probe"
DEFAULT_REQUESTED = {
    "model_key": None,
    "effort": None,
    "requirement": "PREFERRED",
    "on_unavailable": "BLOCK",
}
RECORDS = [
    {"method": "POST", "path": "/b06b/new", "status": 201},
    {"method": "GET", "path": "/b06b/new", "status": 404},
    {"method": "PUT", "path": "/b06b/other", "status": 204},
    {"method": "GET", "path": "/b06b/new", "status": 200},
]
ACTUAL_INPUT = {"capture": canonical(RECORDS).decode()}
EXPECTED_OUTPUTS = [
    {"records": RECORDS},
    {
        "operations": [
            {"method": "GET", "path": "/b06b/new", "statuses": [200, 404]},
            {"method": "POST", "path": "/b06b/new", "statuses": [201]},
            {"method": "PUT", "path": "/b06b/other", "statuses": [204]},
        ]
    },
    {
        "surface_map": [
            {"path": "/b06b/new", "methods": ["GET", "POST"], "operation_count": 2},
            {"path": "/b06b/other", "methods": ["PUT"], "operation_count": 1},
        ]
    },
]


def require_consumer() -> None:
    result = subprocess.run(
        cli_command(MODULE, "--help"),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, "B06b PURE consumer missing before DB acquisition"
    assert result.stderr == ""
    assert all(operation in result.stdout for operation in ("select", "execute", "readback"))


def probe_executor_revision(evaluator_revision: str) -> str:
    """Bind consumer bytes as well as the separate qualification evaluator."""
    spec = importlib.util.find_spec(MODULE)
    assert spec is not None and spec.origin is not None
    root = Path(spec.origin).parents[1]
    return "sha256:" + sha(
        canonical(
            {
                "domain": "omnis-contract-probe-pure-v1",
                "evaluator_revision": evaluator_revision,
                "files": {
                    name: sha((root / name).read_bytes())
                    for name in (
                        "runs/pure_probe.py",
                        "runs/plan_snapshot.py",
                        "tasks/execution_selection.py",
                        "settings/catalog_publication.py",
                        "settings/publication_models.py",
                        "settings/publication_store.py",
                    )
                },
            }
        )
    )


class Probe(Seed):
    """Keep C01's bounded transport, sanitized diagnostics and source ownership."""

    def command(
        self,
        operation: str,
        request: dict[str, object],
        candidate: bool = False,
        raw: bytes | None = None,
    ) -> list[str]:
        assert not candidate, "qualification belongs to the unchanged C01 consumer"
        path = self.directory / f"probe-request-{uuid4().hex}.json"
        path.write_bytes(canonical(request) if raw is None else raw)
        path.chmod(0o600)
        return cli_command(
            MODULE, operation, "--request", str(path), "--catalog-root", str(self.root)
        )


def assert_selection(result: dict[str, object], snapshot: dict[str, object]) -> dict[str, object]:
    assert set(result) == {"selection_ref", "selection"}
    ref = exact_ref(result["selection_ref"])
    assert ref["kind"] == "execution-selection"
    selected = envelope(result["selection"], ref)
    pinned = envelope(snapshot["snapshot"], snapshot["snapshot_ref"])
    assert selected == {
        "snapshot_ref": snapshot["snapshot_ref"],
        "recipe_key": RECIPE,
        "selected_package_refs": pinned["package_refs"],
        "requested": DEFAULT_REQUESTED,
        "effective": None,
        "resolution": "NO_MODEL",
        "reason": "CONTRACT_PROBE_PURE",
        "compatibility_receipt_refs": [],
    }
    return selected


def assert_receipt(
    result: dict[str, object], selection: dict[str, object], executor_revision: str
) -> dict[str, object]:
    assert set(result) == {"receipt_ref", "receipt"}
    ref = exact_ref(result["receipt_ref"])
    assert ref["kind"] == "pure-probe-receipt"
    body = envelope(result["receipt"], ref)
    assert body["status"] == "COMPLETED"
    assert body["selection_ref"] == selection["selection_ref"]
    assert body["executor_revision"] == executor_revision
    exact_ref(body["input_ref"])
    outputs = sequence(body["outputs"])
    assert len(outputs) == len(EXPECTED_OUTPUTS)
    for value, step, expected in zip(
        outputs, ("decode", "group", "map"), EXPECTED_OUTPUTS, strict=True
    ):
        output = mapping(value)
        assert output == {"step_id": step, "output": expected, "digest": sha(canonical(expected))}
    return body


def assert_readback(
    back: dict[str, object], result: dict[str, object], selection: dict[str, object]
) -> None:
    assert set(back) == {
        "receipt_ref",
        "receipt",
        "input_ref",
        "input",
        "selection_ref",
        "selection",
    }
    assert {key: back[key] for key in result} == result
    assert {key: back[key] for key in selection} == selection
    receipt = envelope(back["receipt"], back["receipt_ref"])
    assert receipt["input_ref"] == back["input_ref"]
    supplied = envelope(back["input"], back["input_ref"])
    assert supplied["input"] == ACTUAL_INPUT
