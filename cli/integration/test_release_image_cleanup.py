"""Image lifetime at the real release consumer; no Docker or installed gates run."""

import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from functools import partial
from pathlib import Path
from unittest.mock import patch

import control_topology
import installed_start
import installed_start_failures
import installed_stop
import test_release
from omnis_cli.compose import ImageReceipt, _put_record

GATES = {
    "CONTROL": ["control"],
    "START": ["start", "interrupt", "interrupt-FORWARDING", "interrupt-dashboard", "db", "lock"],
    "PAIR_OPEN": ["start", "non-tty"],
    "STOP": ["stop", "emergency"],
}


class ReleaseImageCleanupTest(unittest.TestCase):
    def exercise(self, enabled, *, fail_at=None, error=None):
        consumer = test_release.ReleaseBundleTest()
        events = []
        removed = False
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name, ExitStack() as stack:
            scratch = Path(name)
            data = scratch / "data"
            root = data / "omnis"
            release = root / "releases/0.1.0"
            release.mkdir(parents=True, mode=0o700)
            root.chmod(0o700)
            manifest = b'{"synthetic":"manifest"}'
            (release / "release.json").write_bytes(manifest)
            receipt = ImageReceipt(
                "omnis-local-" + "a" * 32,
                "omnis-control-" + "a" * 32 + ":0.1.0",
                "sha256:" + "b" * 64,
                hashlib.sha256(manifest).hexdigest(),
                "unix:///synthetic/docker.sock",
                "synthetic-daemon",
            )
            receipt_path = root / "image.json"
            _put_record(receipt_path, receipt, complete=True)
            original = receipt_path.read_bytes()
            image = {
                "Id": receipt.image_id,
                "Config": {
                    "User": "65532:65532",
                    "Cmd": ["python", "-I", "-m", "omnis.serve"],
                    "Labels": {
                        "org.omnis.project": receipt.project,
                        "org.omnis.bundle_sha256": receipt.manifest_sha256,
                    },
                },
            }

            def stage(label, *_args, **kwargs):
                if label == "interrupt":
                    if kwargs.get("expire_dashboard"):
                        label += "-dashboard"
                    elif kwargs.get("phase"):
                        label += "-" + kwargs["phase"]
                if label == "start":
                    self.assertEqual(kwargs["pair_open"], "PAIR_OPEN" in enabled)
                events.append(label)
                if label == fail_at:
                    assert error is not None
                    raise error

            def install(argv, **_kwargs):
                self.assertEqual(argv, ["/synthetic/omnis", "install-image"])
                stage("install")
                return subprocess.CompletedProcess(argv, 0, "", "")

            def command(argv, **_kwargs):
                nonlocal removed
                docker = ["docker", "--host", receipt.docker_host, "image"]
                if argv == [*docker, "inspect", receipt.tag]:
                    if removed:
                        return subprocess.CompletedProcess(argv, 1, "", "No such image")
                    return subprocess.CompletedProcess(argv, 0, json.dumps([image]), "")
                if argv == [*docker, "rm", receipt.tag]:
                    events.append("remove")
                    removed = True
                    return subprocess.CompletedProcess(argv, 0, "", "")
                if argv == [str(scratch / "deny-image-rebuild/docker"), "build"]:
                    stage("deny-build")
                    return subprocess.CompletedProcess(argv, 97, "", "")
                if argv == ["/synthetic/omnis", "install-image"]:
                    stage("repeat")
                    return subprocess.CompletedProcess(argv, 0, "", "")
                self.fail(f"Unexpected subprocess: {argv!r}")

            stack.enter_context(
                patch.dict(
                    os.environ,
                    {
                        f"OMNIS_INSTALLED_{key}_PROBE": "1" if key in enabled else "0"
                        for key in GATES
                    },
                )
            )
            # Substitute every external seam explicitly; an escaped spawn is an error.
            stack.enter_context(patch.object(test_release.subprocess, "run", side_effect=command))
            spawn = stack.enter_context(
                patch.object(subprocess, "Popen", side_effect=AssertionError("Unmocked spawn"))
            )
            stack.enter_context(patch.object(consumer, "run_cli_scope", side_effect=install))
            stack.enter_context(
                patch.object(consumer, "probe_installed_image", side_effect=partial(stage, "image"))
            )
            stack.enter_context(
                patch.object(test_release, "_checked_socket", return_value=receipt.docker_host)
            )
            stack.enter_context(
                patch.object(test_release, "_docker_id", return_value=receipt.docker_id)
            )
            stack.enter_context(
                patch.object(test_release.shutil, "which", return_value="/synthetic/docker")
            )
            for module, function, label in (
                (control_topology, "run_probe", "control"),
                (installed_start, "run_installed_start", "start"),
                (installed_start, "run_installed_non_tty_default", "non-tty"),
                (installed_start, "run_interrupted_start", "interrupt"),
                (installed_start_failures, "run_database_readiness_failure", "db"),
                (installed_start_failures, "run_lock_expiry", "lock"),
                (installed_stop, "run_installed_stop", "stop"),
                (installed_stop, "run_emergency_stop", "emergency"),
            ):
                stack.enter_context(
                    patch.object(module, function, side_effect=partial(stage, label))
                )
            cleanup = stack.enter_context(
                patch.object(
                    consumer, "cleanup_image_install", wraps=consumer.cleanup_image_install
                )
            )
            caught = None
            output = io.StringIO()
            with redirect_stdout(output):
                try:
                    consumer.assert_image_install("/synthetic/omnis", {"PATH": ""}, data, scratch)
                except (AssertionError, subprocess.TimeoutExpired) as exc:
                    caught = exc

            sequence = ["install", "image"]
            if "CONTROL" in enabled:
                sequence += GATES["CONTROL"]
            if "START" in enabled or "PAIR_OPEN" in enabled:
                sequence += ["start"]
                if "PAIR_OPEN" in enabled:
                    sequence += ["non-tty"]
                if "START" in enabled:
                    sequence += GATES["START"][1:]
            if "STOP" in enabled:
                sequence += GATES["STOP"]
            sequence += ["deny-build", "repeat"]
            expected = sequence if fail_at is None else sequence[: sequence.index(fail_at) + 1]
            # Prove the fault was reached, not masked by a broken pre-probe fixture.
            self.assertEqual([event for event in events if event != "remove"], expected)
            spawn.assert_not_called()
            self.assertEqual(receipt_path.read_bytes(), original)
            self.assertEqual((release / "release.json").read_bytes(), manifest)
            if fail_at not in {None, "install", "image", "deny-build", "repeat"}:
                cleanup.assert_not_called()
                self.assertFalse(removed, "Unreconciled runtime still needs its exact image")
            else:
                cleanup.assert_called_once_with(data, uncertain=False)
                self.assertTrue(removed)
            self.assertIs(caught, error, "Preserve the original failure, never promote it to PASS")
            if error is not None:
                self.assertEqual(output.getvalue(), "")
            else:
                self.assertEqual(
                    output.getvalue(),
                    f"IMAGE_INSTALLED_VERIFIED id={receipt.image_id} project={receipt.project}\n",
                )

    def test_runtime_assertion_retains_image(self):
        for gate, stages in GATES.items():
            for stage in stages:
                with self.subTest(gate=gate, stage=stage):
                    self.exercise(
                        [gate], fail_at=stage, error=AssertionError("runtime unreconciled")
                    )

    def test_runtime_timeout_retains_image(self):
        for gate, stages in GATES.items():
            for stage in stages:
                with self.subTest(gate=gate, stage=stage):
                    self.exercise(
                        [gate], fail_at=stage, error=subprocess.TimeoutExpired([stage], 1)
                    )

    def test_verified_runtime_and_image_only_still_cleanup(self):
        for enabled in [[], *([gate] for gate in GATES), list(GATES)]:
            with self.subTest(enabled=enabled):
                self.exercise(enabled)

    def test_failures_outside_runtime_still_cleanup(self):
        for stage in ["install", "image", "deny-build", "repeat"]:
            with self.subTest(stage=stage):
                self.exercise(list(GATES), fail_at=stage, error=AssertionError("outside runtime"))
