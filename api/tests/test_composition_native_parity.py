"""Exact API/native source-byte parity, separate from installed/PG evidence."""

import importlib
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from omnis.modules.settings import candidate_store as records
from omnis.modules.tasks import managed_composition, managed_contract
from test_managed_composition import inputs
from test_managed_contract import ref


def test_real_composer_pin_and_two_skill_producer_native_acceptance() -> None:
    import sys

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "integrations/hermes/src"))
    try:
        native = importlib.import_module("omnis_hermes.managed_admission_contract")
        composer = importlib.import_module("omnis_hermes.prompt_bundle")
    finally:
        sys.path.pop(0)
    assert composer.__file__ is not None
    assert (
        managed_composition.COMPOSER_REVISION
        == sha256(Path(composer.__file__).read_bytes()).hexdigest()
    )
    assert managed_composition.PROVENANCE == composer.PROVENANCE
    selection, bindings, packages, procedure = inputs(two=True)
    built = managed_contract.build_records(
        selection,
        ref("native-preparation-receipt"),
        managed_contract.mapping(
            next(b["ref"] for b in bindings if b["entity_kind"] == "procedure")
        ),
        procedure,
        bindings,
        "b06b-publish-contract",
        "RECON",
        1,
        datetime(2026, 10, 9, tzinfo=UTC),
        composition_packages=packages,
    )
    wire = managed_composition.stage_payload(built[-1], built)
    admitted = native.validate_stage(wire)
    assert admitted == built[-1]
    composition = next(r for r in built if r["kind"] == "prompt-composition")
    entry = managed_contract.mapping(
        managed_contract.sequence(managed_contract.mapping(admitted["payload"])["entries"])[0]
    )
    assert (
        composer.validate_composition(composition, admitted, entry)
        == managed_contract.text(
            managed_contract.mapping(composition["payload"])["text"], 65536
        ).encode()
    )
    assert entry["composition_ref"] == records.reference(composition)
