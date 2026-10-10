"""Independent resealing of actual API-origin material at the native boundary."""

import importlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_composition
from omnis.modules.tasks.managed_contract import mapping, sequence
from test_c03_managed_capture import capture_graph


def native_tools() -> tuple[ModuleType, ModuleType]:
    root = Path(__file__).resolve().parents[2]
    paths = [str(root / "integrations/hermes/src"), str(root / "integrations/hermes/tests")]
    sys.path[:0] = paths
    try:
        native = importlib.import_module("omnis_hermes.managed_admission_contract")
        helpers = importlib.import_module("test_c03_case_input")
    finally:
        del sys.path[:2]
    return native, helpers


def test_native_rejects_input_envelope_overflow_below_unchanged_frame_cap() -> None:
    native, helpers = native_tools()
    graph = capture_graph("\t" * 3600)
    stage = managed_composition.stage_payload(graph[-1], graph)
    assert native.validate_stage(stage) == graph[-1]
    composition = mapping(sequence(stage["compositions"])[0])
    sections = sequence(json.loads(str(mapping(composition["payload"])["text"])))
    material = mapping(sections[4])
    item = mapping(material["input"])
    item["payload"] = {**mapping(item["payload"]), "value": {"capture": "\t" * 3800}}
    material["input"] = item
    sections[4] = material
    helpers.relink(stage, sections)
    assert len(canonical(item)) > 8192
    assert len(canonical(stage)) < 32768
    with pytest.raises(CatalogError, match="CASE_INPUT_LIMIT"):
        managed_composition.validate(sequence(stage["compositions"])[0])
    with pytest.raises(ValueError):
        native.validate_stage(stage)
