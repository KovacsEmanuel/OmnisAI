"""Byte-bounded manifest refusal through the decoder and actual console script."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from omnis_cli.release import ReleaseError, _manifest


class ManifestBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sc02-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.release = self.root / "data/omnis/releases/0.1.0"
        self.release.mkdir(parents=True, mode=0o700)
        (self.root / "data/omnis").chmod(0o700)
        pointer = self.root / "data/omnis/installed.json"
        pointer.write_text('{"format":1,"release":"0.1.0"}')
        pointer.chmod(0o600)
        self.payload = b"[" * 15000 + b"0" + b"]" * 15000
        self.assertEqual(len(self.payload), 30001)
        self.assertLessEqual(len(self.payload), 32768)
        (self.release / "release.json").write_bytes(self.payload)

    def test_deep_manifest_decoder_refuses_with_sanitized_release_error(self):
        with self.assertRaisesRegex(ReleaseError, "^Invalid release manifest$"):
            _manifest(self.release)

    def test_deep_manifest_console_refuses_before_creating_state(self):
        cwd = self.root / "external-cwd"
        cwd.mkdir()
        result = subprocess.run(
            [str(Path(sys.executable).with_name("omnis")), "start", "--no-open", "--json"],
            cwd=cwd,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": str(self.root / "home"),
                "XDG_DATA_HOME": str(self.root / "data"),
                "XDG_STATE_HOME": str(self.root / "state"),
                "XDG_RUNTIME_DIR": str(self.root / "runtime"),
            },
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 2, "Malformed manifest must use the refusal protocol")
        self.assertEqual(
            json.loads(result.stdout),
            {
                "state": "REFUSED",
                "reason": "RELEASE_OR_IMAGE_INVALID",
                "dashboard_ready": False,
                "assessment_ready": False,
                "browser_opened": False,
            },
        )
        self.assertEqual(result.stderr, "")
        self.assertFalse((self.root / "state").exists())
        self.assertFalse((self.root / "runtime").exists())
        self.assertEqual((self.release / "release.json").read_bytes(), self.payload)
        self.assertEqual(
            sorted(p.name for p in (self.root / "data/omnis").iterdir()),
            ["installed.json", "releases"],
        )
