"""AR03/M03: product validators; only inspect/config channels substituted."""

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
from unittest.mock import Mock

from omnis_cli.lifecycle import StartError
from omnis_cli.start_runtime import POSTGRES, ControlRuntime

start = importlib.import_module("omnis_cli.start")


class ProductAttestationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="att-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.control = self.root / "control"
        self.control.mkdir(mode=0o700)
        secret = self.root / "db-password"
        secret.write_text("a" * 48 + "\n")
        secret.chmod(0o600)
        self.runtime = ControlRuntime.__new__(ControlRuntime)
        self.runtime.deadline = time.monotonic() + 3
        self.runtime.attempt = "b" * 32
        self.runtime.receipt = SimpleNamespace(
            project="omnis-local-" + "c" * 32, image_id="sha256:" + "d" * 64
        )
        self.runtime.pg_image = "sha256:" + "e" * 64
        self.runtime.check_daemon = Mock()
        self.runtime.run = Mock(side_effect=AssertionError("No resource effects permitted"))
        self.port = 48765
        self.cid = "f" * 64
        self.env = start.environment(self.runtime, self.root, self.control, self.port)

    def item(self, role):
        command = {
            "db": ["postgres"],
            "api": ["python", "-I", "-m", "omnis.serve"],
            "supervisor": ["python", "-I", "-m", "omnis.supervisor"],
        }[role]
        mounts = [
            {
                "Type": "bind",
                "Source": str(self.control),
                "Destination": "/run/omnis-control",
                "RW": role == "supervisor",
            }
        ]
        if role == "api":
            mounts.append(
                {
                    "Type": "bind",
                    "Source": str(self.root / "http"),
                    "Destination": "/run/omnis-http",
                    "RW": True,
                }
            )
        if role == "db":
            mounts = [
                {
                    "Type": "bind",
                    "Source": str(self.root / "postgres"),
                    "Destination": "/var/lib/postgresql",
                    "RW": True,
                },
                {
                    "Type": "bind",
                    "Source": str(self.root / "db-password"),
                    "Destination": "/run/secrets/db_password",
                    "RW": False,
                },
            ]
        environment = [
            "OMNIS_DATABASE_URL=" + self.env["OMNIS_DATABASE_URL"],
            "OMNIS_WEB_ROOT=/opt/omnis/web",
            "OMNIS_CONTROL_DIR=/run/omnis-control",
        ]
        if role == "api":
            environment += [
                "OMNIS_HTTP_DIR=/run/omnis-http",
                f"OMNIS_HTTP_PORT={self.port}",
            ]
        return {
            "Id": self.cid,
            "Image": self.runtime.pg_image if role == "db" else self.runtime.receipt.image_id,
            "Config": {
                "Cmd": command,
                "User": f"{os.getuid()}:{os.getgid()}",
                "Labels": {
                    "com.docker.compose.project": self.runtime.receipt.project,
                    "com.docker.compose.service": role,
                    "org.omnis.start-attempt": self.runtime.attempt,
                },
                "Env": environment,
            },
            "HostConfig": {
                "Privileged": False,
                "PortBindings": {},
                "NetworkMode": self.runtime.receipt.project + "_control",
                "PidMode": "",
                "IpcMode": "private",
                "CapAdd": [],
                "Devices": [],
                "ReadonlyRootfs": True,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges:true"],
            },
            "NetworkSettings": {
                "Ports": {},
                "Networks": {self.runtime.receipt.project + "_control": {}},
            },
            "State": {"Running": True},
            "Mounts": mounts,
        }

    def test_reconciliation_role_requires_exact_job_confinement_and_stdin(self):
        from omnis_cli.lifecycle import write_record

        write_record(self.root / "startup.json", {"system_id": "12345"})
        base_env = ["PATH=/usr/local/bin:/usr/bin:/bin", "OMNIS_WEB_ROOT=/opt/omnis/web"]
        item = self.item("supervisor")
        item["Mounts"] = []
        item["State"]["Running"] = False  # Must attest the created job BEFORE start.
        item["Config"].update(
            Cmd=["python", "-I", "-m", "omnis.stop_reconcile"],
            Entrypoint=None,
            OpenStdin=True,
            StdinOnce=True,
            Tty=False,
            AttachStdin=True,
            AttachStdout=True,
            AttachStderr=True,
            Env=[
                *base_env,
                "OMNIS_DATABASE_URL=" + self.env["OMNIS_DATABASE_URL"],
                "OMNIS_EXPECTED_SYSTEM_ID=12345",
            ],
        )
        item["Config"]["Labels"]["com.docker.compose.service"] = "reconcile"
        item["HostConfig"]["RestartPolicy"] = {"Name": "no", "MaximumRetryCount": 0}

        def inspect(kind, _ident):
            return {"Config": {"Env": base_env}} if kind == "image" else candidate

        candidate = item
        self.runtime.inspect = Mock(side_effect=inspect)
        self.assertEqual(
            self.runtime.attest(self.cid, "reconcile", self.root, self.control, self.port), item
        )
        changes = (
            ("Cmd", ["python", "-I", "-m", "omnis.migrate"]),
            ("Entrypoint", ["sh"]),
            ("OpenStdin", False),
            ("StdinOnce", False),
            ("Tty", True),
            ("AttachStdin", False),
            ("AttachStdout", False),
            ("AttachStderr", False),
            ("User", "0:0"),
            ("Env", [*item["Config"]["Env"], "PGHOST=foreign"]),
            ("Env", [*item["Config"]["Env"], "LD_PRELOAD=/foreign"]),
            ("Env", [*item["Config"]["Env"], "OMNIS_EXPECTED_SYSTEM_ID=12345"]),
        )
        for field, value in changes:
            with self.subTest(field=field, value=value):
                candidate = deepcopy(item)
                candidate["Config"][field] = value
                with self.assertRaises(StartError):
                    self.runtime.attest(self.cid, "reconcile", self.root, self.control, self.port)
        for section, change in (
            ("HostConfig", {"RestartPolicy": {"Name": "always", "MaximumRetryCount": 0}}),
            ("HostConfig", {"ReadonlyRootfs": False}),
            ("HostConfig", {"CapDrop": []}),
            ("HostConfig", {"SecurityOpt": []}),
            ("HostConfig", {"NetworkMode": "host"}),
            ("HostConfig", {"Binds": ["/var/run/docker.sock:/docker"]}),
            ("HostConfig", {"Tmpfs": {"/tmp": "rw"}}),
            ("NetworkSettings", {"Networks": {"foreign": {}}}),
            (
                "Config",
                {"Labels": {**item["Config"]["Labels"], "org.omnis.start-attempt": "foreign"}},
            ),
        ):
            with self.subTest(section=section, change=change):
                candidate = deepcopy(item)
                candidate[section].update(change)
                with self.assertRaises(StartError):
                    self.runtime.attest(self.cid, "reconcile", self.root, self.control, self.port)
        candidate = deepcopy(item)
        candidate["Image"] = "sha256:" + "0" * 64
        with self.assertRaises(StartError):
            self.runtime.attest(self.cid, "reconcile", self.root, self.control, self.port)
        self.runtime.run.assert_not_called()

    def test_runtime_attestation_valid_and_one_boundary_mutations(self):
        mutations = [
            ("missing-bind", ("Mounts",), lambda x: x.pop()),
            (
                "extra-bind",
                ("Mounts",),
                lambda x: x.append(
                    {
                        "Type": "bind",
                        "Source": "/foreign",
                        "Destination": "/extra",
                        "RW": True,
                    }
                ),
            ),
            ("wrong-bind", ("Mounts", 0), lambda x: x.update(Source="/foreign")),
            ("bind-readonly", ("Mounts", 0), lambda x: x.update(RW=not x["RW"])),
            ("rootfs", ("HostConfig",), lambda x: x.update(ReadonlyRootfs=False)),
            ("caps", ("HostConfig",), lambda x: x.update(CapDrop=[])),
            ("privileges", ("HostConfig",), lambda x: x.update(SecurityOpt=[])),
            ("uid", ("Config",), lambda x: x.update(User="0:0")),
            (
                "published-port",
                ("HostConfig",),
                lambda x: x.update(PortBindings={"8765/tcp": [{"HostPort": "8765"}]}),
            ),
            (
                "network",
                ("NetworkSettings", "Networks"),
                lambda x: x.update(foreign={}),
            ),
            ("image", (), lambda x: x.update(Image="sha256:" + "0" * 64)),
            ("command", ("Config",), lambda x: x.update(Cmd=["sleep", "99"])),
            (
                "attempt",
                ("Config", "Labels"),
                lambda x: x.update({"org.omnis.start-attempt": "foreign"}),
            ),
            (
                "project",
                ("Config", "Labels"),
                lambda x: x.update({"com.docker.compose.project": "foreign"}),
            ),
            ("environment", ("Config", "Env"), lambda x: x.append("OMNIS_HTTP_PORT=1")),
        ]
        for role in ("api", "supervisor", "db"):
            valid = self.item(role)
            self.runtime.inspect = Mock(return_value=valid)
            self.assertEqual(
                self.runtime.attest(self.cid, role, self.root, self.control, self.port),
                valid,
            )
            for name, path, mutate in mutations:
                if role == "db" and name in {
                    "rootfs",
                    "caps",
                    "privileges",
                    "uid",
                    "environment",
                }:
                    continue  # DB entrypoint has a different declared security contract.
                with self.subTest(role=role, boundary=name):
                    bad = deepcopy(valid)
                    target = bad
                    for key in path:
                        target = target[key]
                    mutate(target)
                    self.runtime.inspect = Mock(return_value=bad)
                    with self.assertRaises(StartError):
                        self.runtime.attest(self.cid, role, self.root, self.control, self.port)
        self.runtime.run.assert_not_called()

    def config(self):
        # Shape observed from the installed Compose renderer with no daemon
        # endpoint. Image defaults (API/DB command and WEB_ROOT) are not overrides.
        services = {}
        for role in ("api", "supervisor", "db"):
            item = self.item(role)
            services[role] = {
                "image": POSTGRES if role == "db" else self.runtime.receipt.image_id,
                "pull_policy": "never",
                "platform": "linux/amd64",
                "restart": "no",
                "networks": {"control": None},
                "labels": {"org.omnis.start-attempt": self.runtime.attempt},
                "command": item["Config"]["Cmd"] if role == "supervisor" else None,
                "user": item["Config"]["User"],
                "read_only": True,
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "environment": {
                    key: value
                    for key, value in (v.split("=", 1) for v in item["Config"]["Env"])
                    if key != "OMNIS_WEB_ROOT"
                },
                "volumes": [
                    {
                        "type": m["Type"],
                        "source": m["Source"],
                        "target": m["Destination"],
                        **({"read_only": True} if not m["RW"] else {}),
                    }
                    for m in item["Mounts"]
                    if m["Destination"] != "/run/secrets/db_password"
                ],
            }
            if role == "db":
                for key in ("user", "read_only", "cap_drop", "security_opt"):
                    services[role].pop(key)
                services[role]["environment"] = {
                    "POSTGRES_USER": "omnis",
                    "POSTGRES_DB": "omnis",
                    "POSTGRES_PASSWORD_FILE": "/run/secrets/db_password",
                    "POSTGRES_INITDB_ARGS": "--auth-host=scram-sha-256",
                }
                services[role]["secrets"] = [
                    {"source": "db_password", "target": "/run/secrets/db_password"}
                ]
                services[role]["healthcheck"] = {
                    "test": [
                        "CMD",
                        "pg_isready",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "omnis",
                        "-d",
                        "omnis",
                    ],
                    "timeout": "2s",
                    "interval": "2s",
                    "retries": 30,
                }
            else:
                services[role]["depends_on"] = {
                    "db": {"condition": "service_healthy", "required": True}
                }
                if role == "api":
                    services[role]["stop_grace_period"] = "15s"
        return {
            "name": self.runtime.receipt.project,
            "services": services,
            "secrets": {
                "db_password": {
                    "name": self.runtime.receipt.project + "_db_password",
                    "file": self.env["OMNIS_DB_PASSWORD_FILE"],
                }
            },
            "networks": {
                "control": {
                    "name": self.runtime.receipt.project + "_control",
                    "internal": True,
                    "ipam": {},
                    "labels": {"org.omnis.start-attempt": self.runtime.attempt},
                }
            },
        }

    def test_config_mount_command_environment_and_secret_boundaries(self):
        valid = self.config()
        self.runtime.compose = Mock(
            return_value=subprocess.CompletedProcess([], 0, json.dumps(valid))
        )
        start.validate_config(self.runtime, self.env)
        mutations = [
            ("missing-bind", lambda s: s["volumes"].pop()),
            (
                "extra-bind",
                lambda s: s["volumes"].append(
                    {"type": "bind", "source": "/foreign", "target": "/extra"}
                ),
            ),
            ("foreign-source", lambda s: s["volumes"][0].update(source="/foreign")),
            ("foreign-target", lambda s: s["volumes"][0].update(target="/foreign")),
            (
                "write-mode",
                lambda s: s["volumes"][0].update(
                    read_only=not s["volumes"][0].get("read_only", False)
                ),
            ),
            ("boolean-alias", lambda s: s["volumes"][0].update(read_only=1)),
            (
                "bind-options",
                lambda s: s["volumes"][0].update(bind={"propagation": "rshared"}),
            ),
            ("command", lambda s: s.update(command=["sleep", "90"])),
            (
                "missing-env",
                lambda s: s["environment"].pop(next(iter(s["environment"]))),
            ),
            ("extra-env", lambda s: s["environment"].update(LD_PRELOAD="/foreign")),
            (
                "changed-env",
                lambda s: s["environment"].update({next(iter(s["environment"])): "foreign"}),
            ),
            ("secret-binding", lambda s: s.update(secrets=[{"source": "foreign"}])),
        ]
        for role in ("api", "supervisor", "db"):
            for name, mutate in mutations:
                with self.subTest(role=role, boundary=name):
                    bad = deepcopy(valid)
                    mutate(bad["services"][role])
                    self.runtime.compose.return_value = subprocess.CompletedProcess(
                        [], 0, json.dumps(bad)
                    )
                    with self.assertRaises(StartError):
                        start.validate_config(self.runtime, self.env)
        root_mutations = [
            ("secret-missing", lambda c: c.pop("secrets")),
            (
                "secret-path",
                lambda c: c["secrets"]["db_password"].update(file="/foreign"),
            ),
            (
                "secret-name",
                lambda c: c["secrets"]["db_password"].update(name="foreign"),
            ),
            (
                "secret-extra",
                lambda c: c["secrets"].update(foreign={"file": "/foreign"}),
            ),
            ("named-volume", lambda c: c.update(volumes={"foreign": {}})),
        ]
        for name, mutate in root_mutations:
            with self.subTest(boundary=name):
                bad = deepcopy(valid)
                mutate(bad)
                self.runtime.compose.return_value = subprocess.CompletedProcess(
                    [], 0, json.dumps(bad)
                )
                with self.assertRaises(StartError):
                    start.validate_config(self.runtime, self.env)
        self.runtime.run.assert_not_called()

    def test_config_rejects_alternate_effect_channels_and_changed_lifecycle_commands(
        self,
    ):
        valid = self.config()
        self.runtime.compose = Mock(
            return_value=subprocess.CompletedProcess([], 0, json.dumps(valid))
        )
        start.validate_config(self.runtime, self.env)
        cases = []
        for role in ("api", "supervisor", "db"):
            for field, value in (
                ("volumes_from", ["container:foreign"]),
                ("configs", [{"source": "foreign"}]),
                ("tmpfs", ["/foreign"]),
                ("gpus", "all"),
                ("post_start", [{"command": "sleep 90"}]),
            ):
                cases.append((role, field, value))
        cases.extend(
            [
                (
                    "db",
                    "healthcheck",
                    {
                        **valid["services"]["db"]["healthcheck"],
                        "test": ["CMD", "sleep", "90"],
                    },
                ),
                (
                    "db",
                    "healthcheck",
                    {**valid["services"]["db"]["healthcheck"], "retries": 30.0},
                ),
                ("api", "stop_grace_period", "1s"),
                (
                    "supervisor",
                    "depends_on",
                    {"db": {"condition": "service_started", "required": True}},
                ),
                (
                    "api",
                    "depends_on",
                    {"db": {"condition": "service_healthy", "required": 1}},
                ),
            ]
        )
        for role, field, value in cases:
            with self.subTest(role=role, field=field, value=value):
                bad = deepcopy(valid)
                bad["services"][role][field] = value
                self.runtime.compose.return_value = subprocess.CompletedProcess(
                    [], 0, json.dumps(bad)
                )
                with self.assertRaises(StartError):
                    start.validate_config(self.runtime, self.env)
        self.runtime.run.assert_not_called()

    def test_config_rejects_nondefault_network_attachments(self):
        valid = self.config()
        self.runtime.compose = Mock(
            return_value=subprocess.CompletedProcess([], 0, json.dumps(valid))
        )
        start.validate_config(self.runtime, self.env)
        for role in ("api", "supervisor", "db"):
            for attachment in (
                {"aliases": ["db"]},
                {
                    "driver_opts": {
                        "com.docker.network.endpoint.sysctls": "net.ipv4.conf.IFNAME.forwarding=1"
                    }
                },
                {"mac_address": "02:42:ac:11:00:02"},
                {"ipv4_address": "172.28.0.200"},
                {"unknown": True},
                {},
                [],
                True,
                1,
                "control",
            ):
                with self.subTest(role=role, attachment=attachment):
                    bad = deepcopy(valid)
                    bad["services"][role]["networks"]["control"] = attachment
                    self.runtime.compose.return_value = subprocess.CompletedProcess(
                        [], 0, json.dumps(bad)
                    )
                    with self.assertRaisesRegex(StartError, "COMPOSE_SERVICE_INVALID"):
                        start.validate_config(self.runtime, self.env)
        self.runtime.run.assert_not_called()

    def test_config_requires_exact_internal_boolean(self):
        valid = self.config()
        self.runtime.compose = Mock(
            return_value=subprocess.CompletedProcess([], 0, json.dumps(valid))
        )
        start.validate_config(self.runtime, self.env)
        for value in (1, 1.0, False, "true", None, [], {}):
            with self.subTest(internal=value):
                bad = deepcopy(valid)
                bad["networks"]["control"]["internal"] = value
                self.runtime.compose.return_value = subprocess.CompletedProcess(
                    [], 0, json.dumps(bad)
                )
                with self.assertRaisesRegex(StartError, "COMPOSE_TOPOLOGY_INVALID"):
                    start.validate_config(self.runtime, self.env)
        self.runtime.run.assert_not_called()

    def test_config_validator_valid_and_supported_boundary_mutations(self):
        valid = self.config()
        self.runtime.compose = Mock(
            return_value=subprocess.CompletedProcess([], 0, json.dumps(valid))
        )
        start.validate_config(self.runtime, self.env)
        mutations = [
            ("image", lambda x: x.update(image="foreign")),
            ("network", lambda x: x.update(networks={"foreign": None})),
            ("ports", lambda x: x.update(ports=["8765:8765"])),
            ("uid", lambda x: x.update(user="0:0")),
            ("rootfs", lambda x: x.update(read_only=False)),
            ("caps", lambda x: x.update(cap_drop=[])),
            ("privileges", lambda x: x.update(security_opt=[])),
            (
                "attempt",
                lambda x: x.update(labels={"org.omnis.start-attempt": "foreign"}),
            ),
        ]
        for name, mutate in mutations:
            with self.subTest(boundary=name):
                bad = deepcopy(valid)
                mutate(bad["services"]["api"])
                self.runtime.compose.return_value = subprocess.CompletedProcess(
                    [], 0, json.dumps(bad)
                )
                with self.assertRaises(StartError):
                    start.validate_config(self.runtime, self.env)
        self.runtime.run.assert_not_called()
