"""The Reticle smoke must refuse missing prerequisites before launching tools."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ReticleLauncherTests(unittest.TestCase):
    def test_missing_browser_fails_closed(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/development/reticle/run_probe.py"),
             "--browser", str(ROOT / "nonexistent-browser-for-test")],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Browser executable not found", result.stderr)
        self.assertNotIn("RUN_DIR=", result.stdout)


if __name__ == "__main__":
    unittest.main()
