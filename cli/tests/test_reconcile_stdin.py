"""Bounded stdin through the existing runner; owned local children, no Docker."""

import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.lifecycle import StartError
from omnis_cli.start_runtime import ControlRuntime


def runtime():
    result = ControlRuntime.__new__(ControlRuntime)
    result.deadline = time.monotonic() + 3
    result.uncertain, result.family_drained = False, True
    result.docker = Path("/not-executed/docker")
    result.release = Path(os.environ["TMPDIR"])
    result.host = "unix:///not-contacted"
    return result


class StdinRunnerTest(unittest.TestCase):
    def test_exact_limit_is_written_and_eof_delivered_before_ack(self):
        original = subprocess.Popen
        children = []

        def spawn(_argv, **kwargs):
            child = original(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    "import sys; b=sys.stdin.buffer.read(); print(len(b)); print('ack',file=sys.stderr)",
                ],
                **kwargs,
            )
            children.append(child)
            return child

        owner = runtime()
        with patch("subprocess.Popen", side_effect=spawn):
            result = owner.run("synthetic", stdin=b"x" * 16384, effect=True)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "16384\n", "ack\n"))
        self.assertFalse(owner.uncertain)
        self.assertTrue(owner.family_drained)
        self.assertTrue(children[0].stdin.closed)
        self.assertEqual(children[0].returncode, 0)

    def test_oversize_refuses_before_spawn(self):
        owner = runtime()
        with patch("subprocess.Popen", side_effect=AssertionError("spawned")) as spawn:
            with self.assertRaisesRegex(StartError, "COMMAND_INPUT_LIMIT"):
                owner.run("synthetic", stdin=b"x" * 16385, effect=True)
        spawn.assert_not_called()
        self.assertFalse(owner.uncertain)

    def test_backpressure_is_bounded_and_keeps_uncertainty(self):
        original = subprocess.Popen
        children = []

        def spawn(_argv, **kwargs):
            child = original([sys.executable, "-I", "-c", "import time; time.sleep(30)"], **kwargs)
            children.append(child)
            return child

        owner = runtime()
        before = time.monotonic()
        with patch("subprocess.Popen", side_effect=spawn):
            with self.assertRaises(StartError):
                owner.run("synthetic", stdin=b"x" * 16384, cap=0.15, effect=True)
        self.assertLess(time.monotonic() - before, 2)
        self.assertLess(children[0].returncode, 0)
        self.assertTrue(children[0].stdin.closed)
        self.assertTrue(owner.uncertain)
        self.assertFalse(owner.family_drained)
