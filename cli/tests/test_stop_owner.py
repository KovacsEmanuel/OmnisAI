"""Stop-owner probes use only new private files/processes and synthetic Engine UDS."""

import fcntl
import os
import tempfile
import time
import unittest
from pathlib import Path

from omnis_cli.lifecycle import lifecycle_lock


class StopLockTests(unittest.TestCase):
    def test_original_description_retains_lock_after_launcher_close(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            held = -1
            try:
                with lifecycle_lock(root, time.monotonic() + 2) as original:
                    self.assertIsInstance(original, int, "handoff requires original lock FD")
                    held = os.dup(original)
                challenger = os.open(root / "lifecycle.lock", os.O_RDWR)
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(challenger, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    os.close(held)
                    held = -1
                    fcntl.flock(challenger, fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally:
                    os.close(challenger)
            finally:
                if held >= 0:
                    os.close(held)
