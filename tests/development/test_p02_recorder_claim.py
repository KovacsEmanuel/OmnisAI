"""P02 one-shot SOURCE regression: no-effect owner, real retained-file claim."""

import importlib.util
import json
import os
import signal
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
RECORDER = ROOT / "documents/verification/p2-integration-p02-recorder.py"


class RecorderClaim(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(
            prefix="p02-claim-unit-", dir=os.environ["TMPDIR"]
        )
        self.addCleanup(self.directory.cleanup)
        spec = importlib.util.spec_from_file_location("p02_claim_recorder", RECORDER)
        assert spec is not None and spec.loader is not None
        self.rec = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.rec)
        self.rec.ATTEMPT = Path(self.directory.name) / "attempt"
        self.rec.INTEGRATION = Path(self.directory.name) / "registry"
        self.rec.ATTEMPT.mkdir(mode=0o700)
        self.rec.INTEGRATION.mkdir(mode=0o700)
        self.artifact = self.rec.ATTEMPT / "source-only-artifact"
        self.artifact.write_bytes(b"not installed; no effects")
        manifest = self.rec.INTEGRATION / "inputs.json"
        manifest.write_text(
            json.dumps(
                {"inputs": {str(RECORDER.relative_to(ROOT)): self.rec.sha(RECORDER.read_bytes())}}
            )
        )
        self.rec.write_registry(
            {
                "attempts": [
                    {
                        "id": "p02",
                        "intent_nonce": self.rec.NONCE,
                        "state": "COPY_INSTALLED_ATTESTED_READY_FOR_SINGLE_GATE",
                        "input_manifest": str(manifest),
                        "input_manifest_sha256": self.rec.sha(manifest.read_bytes()),
                        "artifact_hashes": {
                            str(self.artifact): self.rec.sha(self.artifact.read_bytes())
                        },
                    }
                ]
            }
        )
        env = patch.dict(
            os.environ,
            {"HOME": str(self.rec.ATTEMPT / "home"), "TMPDIR": str(self.rec.ATTEMPT / "tmp")},
        )
        env.start()
        self.addCleanup(env.stop)
        self.calls = []
        owner = {
            "calls": self.calls,
            "write_fixture_manifest": lambda *args: None,
            "_request_stop": lambda *args: None,
        }
        exec(
            "def prove_private_fixture(target, uv, seconds):\n    calls.append((target, seconds))\n    return 0\n",
            owner,
        )
        for change in (
            patch.object(self.rec.runpy, "run_path", return_value=owner),
            patch.object(signal, "signal", return_value=None),
            patch.object(self.rec, "require_grant", self.rec.registry),
        ):
            change.start()
            self.addCleanup(change.stop)

    def test_single_positive_and_sequential_replay_refusal(self):
        self.assertEqual(self.rec.main(), 0)
        with self.assertRaises(ValueError):
            self.rec.main()
        self.assertEqual(self.calls, [(self.rec.TARGET, 900)])

    def test_two_valid_ready_readers_only_one_owner_entry(self):
        barrier = threading.Barrier(2, timeout=3)
        lock = threading.Lock()
        write = self.rec.write_registry
        errors = []

        def require():
            value = self.rec.registry()
            barrier.wait()
            return value

        def serial_write(value):
            with lock:
                write(value)

        def invoke():
            try:
                self.rec.main()
            except Exception as error:
                errors.append(type(error).__name__)

        with (
            patch.object(self.rec, "require_grant", require),
            patch.object(self.rec, "write_registry", serial_write),
        ):
            threads = [threading.Thread(target=invoke) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)
            self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(self.calls, [(self.rec.TARGET, 900)])
        self.assertEqual(errors, ["FileExistsError"])
        marker = self.rec.ATTEMPT / ("consumed-" + self.rec.NONCE + ".json")
        self.assertEqual(json.loads(marker.read_bytes())["intent_nonce"], self.rec.NONCE)

    def test_registry_failure_after_claim_never_rearms_ready(self):
        with patch.object(
            self.rec, "write_registry", side_effect=OSError("synthetic metadata failure")
        ):
            with self.assertRaises(OSError):
                self.rec.main()
        self.assertEqual(
            self.rec.registry()[1]["state"], "COPY_INSTALLED_ATTESTED_READY_FOR_SINGLE_GATE"
        )
        with self.assertRaises(FileExistsError):
            self.rec.main()
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
