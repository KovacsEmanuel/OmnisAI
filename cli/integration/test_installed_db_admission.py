"""M09 observer admission controls: real child, substituted DB, no Docker."""

import json
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import installed_start_failures as failures


class DatabaseAdmissionTest(unittest.TestCase):
    def control(self, missing_pin):
        with tempfile.TemporaryDirectory(prefix="da-", dir=os.environ["TMPDIR"]) as name:
            fixture = Path(name)
            marker = fixture / "executed"
            cli = fixture / "cli"
            cli.write_text(
                f"#!{sys.executable}\n"
                "import json,os,pathlib,time\n"
                f"pathlib.Path({str(marker)!r}).write_text('executed')\n"
                "root=pathlib.Path(os.environ['XDG_STATE_HOME'])/'omnis'\n"
                "root.mkdir(parents=True,exist_ok=True)\n"
                "(root/'postgres').mkdir()\n"
                "(root/'db-password').write_text('synthetic-test-only')\n"
                "record={'phase':'STARTING','attempt':'test-only','containers':{'db':'test-db'}}\n"
                "journal=root/'startup.json'\n"
                "journal.write_text(json.dumps(record))\n"
                "while not (root/'fault').exists(): time.sleep(0.01)\n"
                "record.update(phase='FAILED_CLEANED',failed_phase='STARTING',cleanup=[])\n"
                "journal.write_text(json.dumps(record))\n"
                "print(json.dumps({'reason':'SERVICE_READINESS_FAILED',"
                "'dashboard_ready':False,'assessment_ready':False}))\n"
                "raise SystemExit(3)\n"
            )
            cli.chmod(0o700)
            holder = {}
            real_popen, real_pin = subprocess.Popen, os.pidfd_open

            def popen(argv, **kwargs):
                holder["state"] = Path(kwargs["env"]["HOME"])
                process = real_popen(argv, **kwargs)
                holder["process"] = process
                holder["observer"] = real_pin(process.pid)
                return process

            def product_pin(pid):
                self.assertEqual(pid, holder["process"].pid)
                if missing_pin:
                    raise OSError("synthetic pidfd unavailable")
                return real_pin(pid)

            class Database:
                def __init__(self, *args):
                    pass

                def network(self, allowed):
                    return None

                def inspect(self, *args):
                    return None

                def ids(self):
                    root = holder["state"] / "s/omnis"
                    return [] if (root / "fault").exists() else ["test-db"]

                def attest(self, *args):
                    root = holder["state"] / "s/omnis"
                    return {
                        "State": {
                            "Status": "exited" if (root / "fault").exists() else "running",
                            "Running": not (root / "fault").exists(),
                            "Health": {"Status": "starting"},
                        }
                    }

                def run(self, *args, **kwargs):
                    if args != ("container", "kill", "--signal", "KILL", "test-db"):
                        raise AssertionError("Unexpected resource effect")
                    (holder["state"] / "s/omnis/fault").touch()

            try:
                with (
                    patch.object(failures, "ControlRuntime", Database),
                    patch.object(failures.subprocess, "Popen", popen),
                    patch.object(failures.os, "pidfd_open", product_pin),
                ):
                    if missing_pin:
                        with self.assertRaisesRegex(OSError, "synthetic pidfd unavailable"):
                            failures.run_database_readiness_failure(
                                fixture / "data", {"project": "test-only"}, str(cli)
                            )
                        self.assertTrue(select.select([holder["observer"]], [], [], 0)[0])
                        self.assertIsNotNone(holder["process"].returncode)
                        self.assertFalse(marker.exists(), "CLI executed without observer pin")
                    else:
                        failures.run_database_readiness_failure(
                            fixture / "data", {"project": "test-only"}, str(cli)
                        )
                        self.assertTrue(marker.exists())
                        self.assertEqual(holder["process"].returncode, 3)
                receipt = json.loads((holder["state"] / "probe-receipt.json").read_text())
                self.assertEqual(receipt["probe"], "FAIL" if missing_pin else "PASS")
                self.assertEqual(receipt["cleanup"], "UNCERTAIN" if missing_pin else "VERIFIED")
            finally:
                if "observer" in holder:
                    observer_pin = holder["observer"]
                    try:
                        if not select.select([observer_pin], [], [], 0)[0]:
                            signal.pidfd_send_signal(observer_pin, signal.SIGCONT)
                            signal.pidfd_send_signal(observer_pin, signal.SIGKILL)
                        holder["process"].wait(timeout=5)
                    finally:
                        os.close(observer_pin)
                if "state" in holder:
                    shutil.rmtree(holder["state"])

    def test_missing_pidfd_reaps_unadmitted_child_and_preserves_failure(self):
        self.control(True)

    def test_pinned_child_runs_same_database_failure_channel(self):
        self.control(False)
