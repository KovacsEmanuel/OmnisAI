"""M03 runtime regressions: real attestor, read-only synthetic I/O, no OCI credit."""

import importlib
import json
import os
import subprocess
import tempfile
import time
import unittest
from contextlib import ExitStack
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
                self.assertIn(
                    ident, (self.runtime.receipt.project + "_control", self.network["Id"])
                )
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
        root = getattr(self, "snapshot_root", self.root)
        return {
            str(path.relative_to(root)): (
                path.read_bytes() if path.is_file() else None,
                path.stat().st_mode,
                path.stat().st_uid,
                path.stat().st_gid,
                path.stat().st_dev,
                path.stat().st_ino,
                path.stat().st_size,
                path.stat().st_mtime_ns,
            )
            for path in [root, *root.rglob("*")]
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

    def test_f02_exact_entrypoint_for_each_role(self):
        for role in ROLES:
            for entrypoint in (["sh", "-c", "exit 0"], "", {}, False, ["python"]):
                with self.subTest(role=role, entrypoint=entrypoint):
                    item = self.install(role)
                    item["Config"]["Entrypoint"] = entrypoint
                    self.check(role, reject=True)
            if role == "db":
                for entrypoint in (None, []):
                    with self.subTest(role=role, entrypoint=entrypoint):
                        self.install(role)["Config"]["Entrypoint"] = entrypoint
                        self.check(role, reject=True)
            else:
                for entrypoint in (None, []):
                    self.install(role)["Config"]["Entrypoint"] = entrypoint
                    self.check(role)

    def test_f03_no_publish_all_or_nested_port_bindings_before_start(self):
        for role in ROLES:
            for state in ("created", "running", "exited"):
                for section, field, bad in (
                    ("HostConfig", "PublishAllPorts", True),
                    ("HostConfig", "PublishAllPorts", 0),
                    ("HostConfig", "PublishAllPorts", None),
                    ("HostConfig", "PortBindings", []),
                    ("HostConfig", "PortBindings", ""),
                    ("HostConfig", "PortBindings", False),
                    ("HostConfig", "PortBindings", {"5432/tcp": [{"HostPort": "1234"}]}),
                    ("NetworkSettings", "Ports", {"5432/tcp": [{"HostPort": "1234"}]}),
                    ("NetworkSettings", "Ports", {"5432/tcp": {}}),
                    ("NetworkSettings", "Ports", {"5432/tcp": False}),
                    ("NetworkSettings", "Ports", {"5432/tcp": ""}),
                ):
                    with self.subTest(role=role, state=state, field=field, bad=bad):
                        item = self.install(role, state)
                        item["Config"]["ExposedPorts"] = {"5432/tcp": {}}
                        item[section][field] = bad
                        self.check(role, reject=True)
            for bindings in (None, {}):
                for ports in (None, {}, {"5432/tcp": None}, {"5432/tcp": []}):
                    item = self.install(role, "created")
                    item["Config"]["ExposedPorts"] = {"5432/tcp": {}}
                    item["HostConfig"]["PortBindings"] = bindings
                    item["NetworkSettings"]["Ports"] = ports
                    self.check(role)

    def test_f04_fixed_host_confinement_all_roles(self):
        mutations = [
            ("RestartPolicy", {"Name": "always", "MaximumRetryCount": 0}),
            ("RestartPolicy", {"Name": "no", "MaximumRetryCount": False}),
            ("RestartPolicy", {"Name": "no", "MaximumRetryCount": 0.0}),
            ("RestartPolicy", {"Name": "no", "MaximumRetryCount": 1}),
            ("RestartPolicy", None),
            ("Tmpfs", {"/extra": "rw"}),
            ("Tmpfs", []),
            ("Tmpfs", False),
            ("IpcMode", "container:" + "0" * 64),
            ("IpcMode", "host"),
            ("IpcMode", "shareable"),
            ("IpcMode", None),
        ]
        for field in ("DeviceRequests", "DeviceCgroupRules", "Devices", "CapAdd"):
            mutations.extend((field, v) for v in (["foreign"], {}, "", False, 0))
        for role in ROLES:
            for field, bad in mutations:
                with self.subTest(role=role, field=field, bad=bad):
                    item = self.install(role)
                    item["HostConfig"][field] = bad
                    self.check(role, reject=True)
            for value in (None, []):
                item = self.install(role)
                for field in ("DeviceRequests", "DeviceCgroupRules", "Devices", "CapAdd"):
                    item["HostConfig"][field] = value
                for tmpfs in (None, {}):
                    item["HostConfig"]["Tmpfs"] = tmpfs
                    self.check(role)

    def test_f04_bind_propagation_and_exact_rw_type(self):
        for role in ROLES[:3]:
            for index in range(len(self.install(role)["Mounts"])):
                for field, bad in (
                    ("Propagation", "rshared"),
                    ("Propagation", "rslave"),
                    ("Propagation", ""),
                    ("Propagation", None),
                    ("RW", 0),
                    ("RW", 1),
                    ("RW", 1.0),
                    ("Source", []),
                    ("Destination", {}),
                ):
                    with self.subTest(role=role, index=index, field=field, bad=bad):
                        self.install(role)["Mounts"][index][field] = bad
                        self.check(role, reject=True)

    def test_f04_empty_job_binds_and_volumes_are_typed(self):
        for role in ROLES[3:]:
            for section, field, valid, invalid in (
                ("HostConfig", "Binds", (None, []), ({}, "", False, ["/extra:/extra"])),
                ("Config", "Volumes", (None, {}), ([], "", False, {"/extra": {}})),
            ):
                for value in (*valid, *invalid):
                    with self.subTest(role=role, field=field, value=value):
                        self.install(role)[section][field] = value
                        self.check(role, reject=value in invalid)

    def test_f05_created_attachments_and_nested_bindings_all_roles(self):
        for role in ROLES:
            for state in ("created", "running", "exited"):
                for change in ("extra", "foreign", "id", "alias", "dns", "driver", "ipam", "links"):
                    with self.subTest(role=role, state=state, change=change):
                        item = self.install(role, state)
                        nets = item["NetworkSettings"]["Networks"]
                        endpoint = nets[self.network["Name"]]
                        if change == "extra":
                            nets["foreign"] = deepcopy(endpoint)
                        elif change == "foreign":
                            nets["foreign"] = nets.pop(self.network["Name"])
                        else:
                            field, value = {
                                "id": ("NetworkID", "0" * 64),
                                "alias": ("Aliases", ["foreign"]),
                                "dns": ("DNSNames", ["foreign"]),
                                "driver": ("DriverOpts", {"foreign": "true"}),
                                "ipam": ("IPAMConfig", {"IPv4Address": "192.0.2.1"}),
                                "links": ("Links", ["foreign"]),
                            }[change]
                            endpoint[field] = value
                        self.check(role, reject=True)

    def test_f05_generated_aliases_and_unallocated_endpoints(self):
        for role in ROLES:
            for state in ("created", "running", "exited"):
                item = self.install(role, state)
                endpoint = item["NetworkSettings"]["Networks"][self.network["Name"]]
                for names in (None, [], [item["Name"][1:], self.cid, self.cid[:12]]):
                    endpoint["Aliases"] = names
                    endpoint["DNSNames"] = names
                    self.check(role)
                for field, values in (
                    ("Aliases", (False, {}, "", [7])),
                    ("DNSNames", (False, {}, "", [7])),
                    ("DriverOpts", (False, [], "")),
                    ("IPAMConfig", (False, [], "")),
                    ("Links", (False, {}, "")),
                ):
                    original = endpoint[field]
                    for value in values:
                        with self.subTest(role=role, state=state, field=field, value=value):
                            endpoint[field] = value
                            self.check(role, reject=True)
                    endpoint[field] = original
                endpoint["NetworkID"] = ""
                self.check(role, reject=state == "running")
                endpoint["NetworkID"] = None
                self.check(role, reject=True)
            item = self.install(role, "exited")
            item["NetworkSettings"]["Networks"] = {}
            self.check(role)
            for state in ("created", "running"):
                item["State"].update(Status=state, Running=state == "running")
                self.check(role, reject=True)

    def test_f05_network_object_policy_is_shared_with_owner(self):
        self.install("db")
        valid = deepcopy(self.network)
        for boundary in (self.runtime, self.owner()):

            def consumer(boundary=boundary):
                return boundary.network({self.cid})

            for options in (None, {}):
                self.network["Options"] = options
                self.check("db", consumer=consumer)
            for field, value in (
                ("Options", {"com.docker.network.bridge.enable_icc": "false"}),
                ("Options", []),
                ("Options", False),
                ("Options", ""),
                ("Name", "foreign"),
                ("Internal", 1),
                ("Driver", "host"),
                ("Id", "not-an-id"),
                ("Containers", {"0" * 64: {}}),
            ):
                with self.subTest(boundary=type(boundary).__name__, field=field, value=value):
                    self.network = deepcopy(valid)
                    self.network[field] = value
                    self.check("db", reject=True, consumer=consumer)
            self.network = deepcopy(valid)
            # allowed is a maximum: created/exited containers need not be members.
            self.network["Containers"] = {}
            self.check("db", consumer=consumer)

    def test_f06_database_uses_its_image_user_and_docker_defaults_not_api_policy(self):
        for section, field, bad in (
            ("Config", "User", "999:999"),
            ("Config", "User", "0:999"),
            ("Config", "User", None),
            ("HostConfig", "ReadonlyRootfs", True),
            ("HostConfig", "ReadonlyRootfs", 0),
            ("HostConfig", "CapDrop", ["ALL"]),
            ("HostConfig", "CapDrop", {}),
            ("HostConfig", "CapDrop", False),
            ("HostConfig", "SecurityOpt", ["seccomp=unconfined"]),
            ("HostConfig", "SecurityOpt", ["no-new-privileges:true"]),
            ("HostConfig", "SecurityOpt", {}),
            ("HostConfig", "SecurityOpt", False),
        ):
            with self.subTest(field=field, bad=bad):
                self.install("db")[section][field] = bad
                self.check("db", reject=True)
        for value in (None, []):
            item = self.install("db")
            item["HostConfig"].update(CapDrop=value, SecurityOpt=value)
            self.check("db")
        # Inheritance is tied to actual metadata, not a copied user from this fixture.
        self.images[self.runtime.pg_image]["Config"]["User"] = "postgres"
        self.check("db", reject=True)
        item["Config"]["User"] = "postgres"
        self.check("db")

    def test_service_inventory_and_owner_propagate_each_runtime_category(self):
        faults = (
            ("Config", "Env", lambda item: [*item["Config"]["Env"], "PGHOST=foreign"]),
            ("Config", "Entrypoint", lambda item: ["sh"]),
            ("HostConfig", "PublishAllPorts", lambda item: True),
            ("HostConfig", "DeviceRequests", lambda item: [{"Count": -1}]),
            ("NetworkSettings", "Networks", lambda item: {"foreign": {}}),
            ("HostConfig", "ReadonlyRootfs", lambda item: not item["HostConfig"]["ReadonlyRootfs"]),
        )
        for role in ROLES:
            for state in ("created", "running", "exited"):
                for boundary in ("service_ids", "owner"):
                    self.install(role, state)
                    owner = self.owner()

                    def consume(role=role, boundary=boundary, owner=owner):
                        if boundary == "service_ids":
                            return start.service_ids(
                                self.runtime, self.root, self.control, self.port
                            )
                        return owner.attest(self.cid, role, self.root, self.control, self.port)

                    self.check(role, consumer=consume)
                    for section, field, change in faults:
                        with self.subTest(role=role, state=state, boundary=boundary, field=field):
                            item = self.install(role, state)
                            item[section][field] = change(item)
                            self.check(role, reject=True, consumer=consume)

    def test_start_reuse_and_stop_inventories_refuse_drift_without_effects(self):
        from test_stop import private_stop_fixture

        stop = importlib.import_module("omnis_cli.stop")
        with private_stop_fixture() as (base, root, _foreign, control, stopped, _unused):
            self.root, self.control, self.port = root, control, stopped["port"]
            self.snapshot_root = base
            control.mkdir(mode=0o700)
            (root / "http").mkdir(mode=0o700)
            (root / "db-password").write_text("a" * 48)
            for path in (root / "lifecycle.lock", base / "d/omnis/lifecycle.lock"):
                path.touch(mode=0o600)
            runtime = self.runtime
            runtime.receipt = SimpleNamespace(
                project=stopped["project"],
                image_id=stopped["image_id"],
                docker_id=stopped["docker_id"],
            )
            runtime.attempt, runtime.digest = stopped["attempt"], stopped["release_digest"]
            runtime.host, runtime.files = stopped["docker_host"], {}
            self.images = {
                runtime.pg_image: image_item(runtime, "db"),
                runtime.receipt.image_id: image_item(runtime, "api"),
            }
            self.network.update(
                Name=runtime.receipt.project + "_control",
                Labels={
                    "com.docker.compose.project": runtime.receipt.project,
                    "org.omnis.start-attempt": runtime.attempt,
                },
                Containers={cid: {} for cid in stopped["containers"].values()},
            )
            ready = {key: value for key, value in stopped.items() if key in start.READY_FIELDS}
            ready["phase"] = "READY"
            stopping = {
                **stopped,
                "phase": "STOPPING",
                "teardown_completed": [],
                "finalized_generation": None,
            }
            status = {
                "instance_id": ready["instance_id"],
                "assessment_ready": False,
                "admission_open": True,
                "generation": 1,
                "supervisor_epoch": 1,
            }
            # Real journal/PGDATA/instance checks and real shared attestation;
            # substitute only unrelated DB/HTTP/process/socket observations.
            with ExitStack() as scope:
                scope.enter_context(patch.dict(os.environ, {"XDG_DATA_HOME": str(base / "d")}))
                scope.enter_context(patch.object(start, "ControlRuntime", return_value=runtime))
                scope.enter_context(patch.object(start, "state_dir", return_value=root))
                scope.enter_context(patch.object(start, "control_dir", return_value=control))
                scope.enter_context(patch.object(start, "api_process", return_value=42))
                scope.enter_context(patch.object(start, "dashboard", return_value=status))
                scope.enter_context(patch.object(stop, "request", return_value=status))
                for module in (start, stop):
                    scope.enter_context(
                        patch.object(
                            module,
                            "database_identity",
                            return_value=("12345", ready["instance_id"]),
                        )
                    )
                    scope.enter_context(patch.object(module, "listener_owned"))
                    scope.enter_context(
                        patch.object(
                            module,
                            "socket_identity",
                            side_effect=lambda path: (
                                ready["api_socket"]
                                if path.name == "api.sock"
                                else ready["control_socket"]
                            ),
                        )
                    )
                for boundary in ("start-reuse", "reuse", "stop", "emergency"):
                    record = stopping if boundary == "stop" else ready
                    write_record(
                        root / "startup.json", record, replace=(root / "startup.json").exists()
                    )

                    def consume(boundary=boundary, record=record):
                        if boundary == "start-reuse":
                            return start.start_instance(self.port)
                        if boundary == "reuse":
                            return start.verify_running(runtime, root, control, record, self.port)
                        if boundary == "stop":
                            return stop._running_for_stop(runtime, root, control, record)
                        return stop._emergency_inventory(runtime, root, control, record)

                    for role in ROLES[:3]:
                        valid = {
                            cid: container_item(runtime, service, cid, root, control, self.port)
                            for service, cid in stopped["containers"].items()
                        }
                        self.items = deepcopy(valid)
                        self.check(role, consumer=consume)
                        for section, field, value in (
                            ("Config", "Entrypoint", ["sh"]),
                            ("HostConfig", "PublishAllPorts", True),
                            ("HostConfig", "DeviceCgroupRules", ["a *:* rwm"]),
                            ("NetworkSettings", "Networks", {"foreign": {}}),
                            ("HostConfig", "ReadonlyRootfs", role == "db"),
                        ):
                            with self.subTest(boundary=boundary, role=role, field=field):
                                self.items = deepcopy(valid)
                                self.items[stopped["containers"][role]][section][field] = value
                                self.check(role, reject=True, consumer=consume)
                        self.items = deepcopy(valid)
                        self.items[stopped["containers"][role]]["Config"]["Env"].append(
                            "PGHOST=foreign"
                        )
                        self.check(role, reject=True, consumer=consume)

    def test_real_job_create_producers_feed_the_shared_attestor(self):
        """Execute producer Python, not Docker: materialize only its recorded argv/env."""
        import hashlib

        from omnis_cli import restart

        base, runtime = self.root, self.runtime
        for role in ("migrate", "reconcile"):
            self.root = base / role
            self.control = self.root / "runtime-ipc"
            data = base / (role + "-data")
            (data / "omnis").mkdir(parents=True, mode=0o700)
            captured = []

            def capture(*args, captured=captured, **kwargs):
                if args[0] == "create":
                    captured.append((args, kwargs["env"]))
                    raise StartError("SYNTHETIC_CREATE_CAPTURE", 3)
                self.assertEqual(args, ("start", "2" * 64))
                return subprocess.CompletedProcess(args, 0, "", "")

            if role == "migrate":
                # Only advance the unrelated DB/bootstrap boundaries. The create
                # argv below is emitted by start_instance itself, not this test.
                with (
                    patch.dict(os.environ, {"XDG_DATA_HOME": str(data)}),
                    patch.object(start, "state_dir", return_value=self.root),
                    patch.object(start, "control_dir", return_value=self.control),
                    patch.object(start, "ControlRuntime", return_value=runtime),
                    patch.object(start, "preflight_port"),
                    patch.object(start, "validate_config"),
                    patch.object(start, "service_ids", return_value={"db": "2" * 64}),
                    patch.object(start, "cleanup_attempt", return_value=[]),
                    patch.object(runtime, "ids", return_value=[]),
                    patch.object(runtime, "inspect", return_value=None),
                    patch.object(runtime, "attest", return_value={}),
                    patch.object(runtime, "wait_container", return_value={}),
                    patch.object(runtime, "psql", return_value="12345"),
                    patch.object(
                        runtime, "compose", return_value=subprocess.CompletedProcess([], 0, "")
                    ),
                    patch.object(runtime, "run", side_effect=capture),
                    self.assertRaisesRegex(StartError, "SYNTHETIC_CREATE_CAPTURE"),
                ):
                    start.start_instance(self.port)
            else:
                self.root.mkdir(mode=0o700)
                self.control.mkdir(mode=0o700)
                (self.root / "db-password").write_text("a" * 48)
                (self.root / "db-password").chmod(0o600)
                write_record(self.root / "startup.json", {"system_id": "12345"})
                command = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
                for stem in ("stop", "stopped"):
                    write_record(self.root / f"{stem}-{command}.json", {})
                digest = hashlib.sha256(
                    (self.root / f"stop-{command}.json").read_bytes()
                ).hexdigest()
                record = {
                    "attempt": runtime.attempt,
                    "system_id": "12345",
                    "containers": {"db": "2" * 64},
                    "port": self.port,
                }
                intent = {
                    "state": "PREPARED",
                    "new_attempt": runtime.attempt,
                    "old_stop_command": command,
                    "stopped_sha256": digest,
                    "request": {"system_identifier": "12345", "completion_sha256": digest},
                }
                write_record(self.root / f"restart-{command}.json", intent)
                with (
                    patch.object(runtime, "ids", return_value=["2" * 64]),
                    patch.object(runtime, "network", return_value="1" * 64),
                    patch.object(runtime, "run", side_effect=capture),
                    self.assertRaisesRegex(StartError, "SYNTHETIC_CREATE_CAPTURE"),
                ):
                    restart.reconcile_database(
                        runtime,
                        self.root,
                        self.control,
                        record,
                        intent,
                        {
                            "OMNIS_DATABASE_URL": "postgresql+psycopg://omnis:"
                            + "a" * 48
                            + "@db:5432/omnis"
                        },
                    )
            self.assertEqual(len(captured), 1)
            args, environment = captured[0]
            item = self.install(role, "created")
            self.network["Labels"]["org.omnis.start-attempt"] = runtime.attempt
            image = self.images[runtime.receipt.image_id]
            emitted_env = dict(value.split("=", 1) for value in image["Config"]["Env"])
            labels, options, flags, index = {}, {}, set(), 1
            while args[index] != runtime.receipt.image_id:
                option = args[index]
                if option in ("--read-only", "--interactive"):
                    flags.add(option)
                    index += 1
                    continue
                self.assertIn(
                    option,
                    {
                        "--name",
                        "--label",
                        "--network",
                        "--cap-drop",
                        "--security-opt",
                        "--user",
                        "--env",
                        "--pull",
                        "--platform",
                        "--restart",
                        "--attach",
                    },
                )
                value = args[index + 1]
                if option == "--env":
                    emitted_env[value] = environment[value]
                elif option == "--label":
                    key, setting = value.split("=", 1)
                    labels[key] = setting
                else:
                    options[option] = value
                index += 2
            item["Name"] = "/" + options["--name"]
            item["Config"].update(
                Cmd=list(args[index + 1 :]),
                User=options["--user"],
                Labels=labels,
                Env=[f"{key}={value}" for key, value in emitted_env.items()],
            )
            item["HostConfig"].update(
                NetworkMode=options["--network"],
                ReadonlyRootfs="--read-only" in flags,
                CapDrop=[options["--cap-drop"]],
                SecurityOpt=[options["--security-opt"]],
                RestartPolicy={"Name": options.get("--restart", "no"), "MaximumRetryCount": 0},
            )
            self.check(role)
            item["Config"]["Env"].append("LD_PRELOAD=/foreign")
            self.check(role, reject=True)

    def test_owner_image_read_is_typed_and_run_stays_forbidden(self):
        owner = self.owner()
        self.assertEqual(
            owner.inspect("image", self.runtime.pg_image), self.images[self.runtime.pg_image]
        )
        with self.assertRaisesRegex(StartError, "STOP_INSPECT_FORBIDDEN"):
            owner.inspect("volume", "foreign")
        with self.assertRaisesRegex(StartError, "STOP_COMMAND_EXECUTION_FORBIDDEN"):
            owner.run("image", "inspect", self.runtime.pg_image)
