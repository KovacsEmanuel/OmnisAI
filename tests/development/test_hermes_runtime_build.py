"""Preparation and OCI input controls; no native gateway/process is launched."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class RuntimeBuildControls(unittest.TestCase):
    def prepare_module(self):
        path = ROOT / "ops/prepare_hermes_runtime.py"
        self.assertTrue(path.is_file(), "separate verified native preparation is missing")
        spec = importlib.util.spec_from_file_location("prepare_native", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_wrong_archive_is_refused_before_extract_or_output(self):
        module = self.prepare_module()
        with tempfile.TemporaryDirectory(dir=ROOT / "integrations/hermes/upstream") as raw:
            base = Path(raw)
            archive = base / "bad.tar"
            archive.write_bytes(b"not the pinned archive")
            output = base / "output"
            with self.assertRaisesRegex(ValueError, "archive.*SHA256"):
                module.prepare(archive, output)
            self.assertFalse(output.exists())

    def test_overlay_requires_exact_original_bytes(self):
        module = self.prepare_module()
        with tempfile.TemporaryDirectory(dir=ROOT / "integrations/hermes/upstream") as raw:
            source = Path(raw)
            path = source / "tui_gateway/entry.py"
            path.parent.mkdir(parents=True)
            path.write_text("untrusted modification\n")
            with self.assertRaisesRegex(ValueError, "original.*SHA256"):
                module.apply_inert_overlay(source)
            self.assertEqual(path.read_text(), "untrusted modification\n")

    def test_oci_creates_fixed_native_state_paths(self):
        import ast
        host = ROOT / "integrations/hermes/src/omnis_hermes/runtime_host.py"
        tree = ast.parse(host.read_text())
        env_node = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "NATIVE_ENV" for t in n.targets))
        native_env = ast.literal_eval(env_node.value)
        text = (ROOT / "ops/Dockerfile.hermes").read_text()
        for key in ("HOME", "HERMES_HOME", "CODEX_HOME"):
            self.assertIn(native_env[key], text, f"OCI does not provision native {key}")
        self.assertIn("/state/work", text, "fixed native cwd is missing")

    def test_oci_defaults_are_separate_offline_and_nonroot(self):
        file = ROOT / "ops/Dockerfile.hermes"
        self.assertTrue(file.is_file(), "native OCI recipe is missing")
        text = file.read_text()
        for required in ["@sha256:", "--require-hashes", "--no-deps", "--no-index", "/opt/hermes/venv", "USER ${RUNTIME_UID}:${RUNTIME_GID}", '"-I", "-m", "omnis_hermes.runtime_host"', "HERMES_OMNIS_INERT=1"]:
            self.assertIn(required, text)
        self.assertNotIn("apt-get", text)
        self.assertNotIn("latest", text)
        self.assertNotIn("EXPOSE", text)
        self.assertNotIn("COPY .", text)

if __name__ == "__main__":
    unittest.main()
