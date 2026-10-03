"""M03 runtime regressions: real attestor, read-only synthetic I/O, no OCI credit."""

import importlib
import json
import os
import subprocess
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from omnis_cli.lifecycle import StartError, write_record
from omnis_cli.start_runtime import ControlRuntime
from omnis_cli.stop_owner import _View
from runtime_inspect_fixture import ROLES, container_item, image_item

start = importlib.import_module("omnis_cli.start")


class RuntimeCompletenessTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="m03-", dir=os.environ["TMPDIR"])
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.control = self.root / "control"
        self.control.mkdir(mode=0o700)
        write_record(self.root / "startup.json", {"system_id": "12345"})
        (self.root / "db-password").write_text("a" * 48)
        (self.root / "db-password").chmod(0o600)
        self.runtime = ControlRuntime.__new__(ControlRuntime)
        self.runtime.receipt = SimpleNamespace(
            project="omnis-local-" + "b" * 32,
            image_id="sha256:" + "c" * 64,
            docker_id="synthetic-daemon",
        )
        self.runtime.pg_image = "sha256:" + "d" * 64
        self.runtime.attempt = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        self.runtime.deadline = time.monotonic() + 30
        self.runtime.release, self.runtime.digest = self.root, "e" * 64
        self.runtime.host = "unix:///not-contacted"
        self.runtime.uncertain, self.runtime.family_drained = False, True
        self.cid, self.port = "f" * 64, 48765
        self.images = {
            self.runtime.pg_image: image_item(self.runtime, "db"),
            self.runtime.receipt.image_id: image_item(self.runtime, "api"),
        }
        self.network = {
            "Id": "1" * 64,
            "Name": self.runtime.receipt.project + "_control",
            "Labels": {
                "com.docker.compose.project": self.runtime.receipt.project,
                "org.omnis.start-attempt": self.runtime.attempt,
            },
            "Driver": "bridge",
            "Internal": True,
            "Options": {},
            "Containers": {},
        }
        self.items, self.reads, self.effects = {}, [], []
        self.runtime.run = self.read_only
        self.socket_check = patch(
            "omnis_cli.start_runtime._checked_socket", side_effect=lambda v: v
        )
        self.socket_check.start()
        self.addCleanup(self.socket_check.stop)
        for name in ("subprocess.Popen", "subprocess.run", "socket.socket.connect"):
            guard = patch(name, side_effect=AssertionError("external I/O forbidden"))
            guard.start()
            self.addCleanup(guard.stop)

    def read_only(self, *args, **kwargs):
        if kwargs.get("effect"):
            self.effects.append(args)
            raise AssertionError("resource effect forbidden")
        self.reads.append(args)
        if args == ("info", "--format", "{{.ID}}"):
            return subprocess.CompletedProcess(args, 0, self.runtime.receipt.docker_id)
        if args[0] == "ps":
            return subprocess.CompletedProcess(args, 0, "\n".join(self.items))
        if len(args) == 3 and args[1] == "inspect":
            kind, _, ident = args
            if kind == "container":
                value = self.items[ident]
            elif kind == "image":
                value = self.images[ident]
            elif kind == "network":
                self.assertIn(ident, (self.network["Name"], self.network["Id"]))
                value = self.network
            else:
                self.fail("unexpected inspect kind")
            return subprocess.CompletedProcess(args, 0, json.dumps([value]))
        self.fail(f"unexpected command {args}")

    def install(self, role, state="running"):
        item = container_item(
            self.runtime, role, self.cid, self.root, self.control, self.port, state
        )
        self.items = {self.cid: item}
        self.network["Containers"] = {self.cid: {}} if state == "running" else {}
        return item

    def snapshot(self):
        return {
            str(path.relative_to(self.root)): (
                path.read_bytes() if path.is_file() else None,
                path.stat().st_mode,
                path.stat().st_uid,
                path.stat().st_gid,
                path.stat().st_dev,
                path.stat().st_ino,
                path.stat().st_size,
                path.stat().st_mtime_ns,
            )
            for path in [self.root, *self.root.rglob("*")]
        }

    def check(self, role, *, reject=False, consumer=None):
        before = self.snapshot(), deepcopy((self.items, self.images, self.network))
        action = consumer or (
            lambda: self.runtime.attest(self.cid, role, self.root, self.control, self.port)
        )
        try:
            if reject:
                with self.assertRaises(StartError):
                    action()
            else:
                action()
        finally:
            self.assertEqual(self.snapshot(), before[0])
            self.assertEqual((self.items, self.images, self.network), before[1])
            self.assertEqual(self.effects, [])
            self.assertFalse(self.runtime.uncertain)
            self.assertTrue(self.runtime.family_drained)

    def owner(self):
        engine = SimpleNamespace(
            deadline=self.runtime.deadline,
            check_daemon=self.runtime.check_daemon,
            container=lambda cid: deepcopy(self.items[cid]),
            image=lambda ident: deepcopy(self.images[ident]),
            network=lambda ident: deepcopy(self.network),
            networks=lambda project: [deepcopy(self.network)],
            containers=lambda project: list(self.items),
        )
        return _View(self.runtime, engine)

    def test_positive_all_roles_running_created_exited(self):
        for role in ROLES:
            for state in ("running", "created", "exited"):
                with self.subTest(role=role, state=state):
                    self.install(role, state)
                    self.check(role)

    def test_f01_complete_environment_from_image_and_only_role_overrides(self):
        for role in ROLES:
            valid = self.install(role)
            env = valid["Config"]["Env"]
            mutations = [
                [*env, "PGHOST=foreign"],
                [*env, "LD_PRELOAD=/foreign"],
                [*env, env[0]],
                [*env, 7],
                [*env, "MALFORMED"],
                [*env, "=empty-key"],
                None,
            ]
            for index in range(len(env)):
                mutations.extend(
                    [
                        env[:index] + env[index + 1 :],
                        [*env[:index], env[index] + "-drift", *env[index + 1 :]],
                    ]
                )
            for changed in mutations:
                with self.subTest(role=role, env=changed):
                    self.items[self.cid] = deepcopy(valid)
                    self.items[self.cid]["Config"]["Env"] = changed
                    self.check(role, reject=True)

    def test_f01_inheritance_is_read_from_identity_bound_image_not_fixture_pin(self):
        for role in ROLES:
            with self.subTest(role=role):
                item = self.install(role)
                image = self.images[item["Image"]]
                saved = deepcopy(image)
                image["Config"]["Env"].append("NEW_IMAGE_DEFAULT=arbitrary=value")
                self.check(role, reject=True)
                item["Config"]["Env"].append("NEW_IMAGE_DEFAULT=arbitrary=value")
                self.check(role)
                image["Id"] = "sha256:" + "0" * 64
                self.check(role, reject=True)
                self.images[item["Image"]] = saved

    def test_f01_owner_and_service_ids_share_full_environment_attestation(self):
        for role in ROLES:
            for boundary in ("service_ids", "owner"):
                with self.subTest(role=role, boundary=boundary):
                    item = self.install(role)
                    owner = self.owner()
                    consumer = (
                        (
                            lambda: start.service_ids(
                                self.runtime, self.root, self.control, self.port
                            )
                        )
                        if boundary == "service_ids"
                        else (
                            lambda owner=owner, role=role: owner.attest(
                                self.cid, role, self.root, self.control, self.port
                            )
                        )
                    )
                    self.check(role, consumer=consumer)
                    item["Config"]["Env"].append("LD_PRELOAD=/foreign")
                    self.check(role, reject=True, consumer=consumer)

    def test_owner_image_read_is_typed_and_run_stays_forbidden(self):
        owner = self.owner()
        self.assertEqual(
            owner.inspect("image", self.runtime.pg_image), self.images[self.runtime.pg_image]
        )
        with self.assertRaisesRegex(StartError, "STOP_INSPECT_FORBIDDEN"):
            owner.inspect("volume", "foreign")
        with self.assertRaisesRegex(StartError, "STOP_COMMAND_EXECUTION_FORBIDDEN"):
            owner.run("image", "inspect", self.runtime.pg_image)
