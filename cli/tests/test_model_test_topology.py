"""SOURCE-only catalog topology/retention; no Docker, native runtime or child process."""

import json
import os
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from omnis_cli.lifecycle import StartError, write_record
from omnis_cli.model_test_source import PACKAGE, PACKAGE_FILES, SOURCE_FILES
from omnis_cli.start import native_fields
from omnis_cli.start_runtime import check_native_paths, private_identity, settings_overlay


class ModelTestTopologyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(TemporaryDirectory(dir=os.environ["TMPDIR"])))

    def test_model_test_catalog_mount_identity_and_retention(self) -> None:
        root = self.tmp_path / "instance"
        root.mkdir(mode=0o700)
        for leaf in ("provider", "native-ipc", "catalog"):
            (root / leaf).mkdir(mode=0o700)
        marker = root / "catalog" / "retained"
        marker.write_text("synthetic publication sentinel")
        record = {
            "format": 4,
            "provider_identity": private_identity(root / "provider"),
            "runtime_dir_identity": private_identity(root / "native-ipc"),
            "catalog_identity": private_identity(root / "catalog"),
        }
        write_record(root / "startup.json", record)
        runtime = SimpleNamespace(
            model_test=True,
            receipt=SimpleNamespace(runtime_image_id="sha256:" + "a" * 64),
            attempt="synthetic",
        )
        overlay = settings_overlay(runtime, {"OMNIS_STATE_ROOT": str(root)})
        supervisor = overlay["services"]["supervisor"]
        assert supervisor["environment"] == {
            "OMNIS_RUNTIME_DIR": "/runtime",
            "OMNIS_NATIVE_PREPARATION_CATALOG_ROOT": "/catalog",
            "OMNIS_MANAGED_TASKS": "1",
            "OMNIS_MODEL_TEST_SOURCE_ROOT": "/opt/omnis/model-test",
        }
        assert supervisor["volumes"][-1] == {
            "type": "bind",
            "source": str(root / "catalog"),
            "target": "/catalog",
        }
        assert "catalog_identity" in native_fields(record)
        assert "OMNIS_RUNTIME_INERT_PROBE" not in json.dumps(overlay)
        check_native_paths(root, record)
        assert marker.read_text() == "synthetic publication sentinel"
        changed = deepcopy(record)
        changed["catalog_identity"] = [0, 1, os.getuid(), os.getgid(), 0o700]
        with self.assertRaisesRegex(StartError, "NATIVE_PATH_IDENTITY_MISMATCH"):
            check_native_paths(root, changed)
        (root / "catalog").rename(root / "retained-catalog")
        with self.assertRaises(OSError):
            settings_overlay(runtime, {"OMNIS_STATE_ROOT": str(root)})
        assert (root / "retained-catalog/retained").read_text() == "synthetic publication sentinel"

    def test_bundle_inventory_is_complete_first_party_source(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        assert len(SOURCE_FILES) == len(PACKAGE_FILES) + 1
        assert all((repository / "skills" / PACKAGE / name).is_file() for name in PACKAGE_FILES)
        assert (repository / "profiles" / (PACKAGE + ".yaml")).is_file()
        assert not any(".hermes" in name or "tests" in name for name in SOURCE_FILES)
