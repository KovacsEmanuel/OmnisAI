"""Pure build provenance checks; no runtime, network or package installation."""

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UPSTREAM = ROOT / "integrations/hermes/upstream"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_managed_patch_is_separate_and_exactly_pinned():
    pin = json.loads((ROOT / "integrations/hermes/pin.json").read_text())
    manifest = json.loads((UPSTREAM / "managed-patch-manifest.json").read_text())
    assert pin["managed_patch_manifest_sha256"] == sha(UPSTREAM / "managed-patch-manifest.json")
    assert (
        pin["managed_patch_sha256"]
        == manifest["patch_sha256"]
        == sha(UPSTREAM / "omnis-managed.patch")
    )
    assert manifest["base_commit"] == pin["commit"]
    assert manifest["applies_after"] == "omnis-inert.patch"
    for name, hashes in manifest["files"].items():
        assert sha(UPSTREAM / "managed-source" / name) == hashes["patched_sha256"]
    assert set(manifest["files"]) == {
        "run_agent.py",
        "agent/cold_admission.py",
        "agent/subagent_lifecycle.py",
        "agent/managed_admission_rpc.py",
        "tui_gateway/rpc_dispatch.py",
        "providers/__init__.py",
    }


def test_overlay_rejects_original_mismatch_before_any_write(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "managed_prepare", ROOT / "ops/prepare_hermes_runtime.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "run_agent.py").write_text("foreign original")
    import pytest

    with pytest.raises((ValueError, FileNotFoundError)):
        module.apply_managed_overlay(tmp_path)
    assert (tmp_path / "run_agent.py").read_text() == "foreign original"
    assert not (tmp_path / "agent/cold_admission.py").exists()
