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
            environment += ["OMNIS_HTTP_DIR=/run/omnis-http", f"OMNIS_HTTP_PORT={self.port}"]
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

    def test_runtime_attestation_valid_and_one_boundary_mutations(self):
        mutations = [
            ("missing-bind", ("Mounts",), lambda x: x.pop()),
            (
                "extra-bind",
                ("Mounts",),
                lambda x: x.append(
                    {"Type": "bind", "Source": "/foreign", "Destination": "/extra", "RW": True}
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
            ("network", ("NetworkSettings", "Networks"), lambda x: x.update(foreign={})),
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
                self.runtime.attest(self.cid, role, self.root, self.control, self.port), valid
            )
            for name, path, mutate in mutations:
                if role == "db" and name in {"rootfs", "caps", "privileges", "uid", "environment"}:
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
                "command": item["Config"]["Cmd"],
                "user": item["Config"]["User"],
                "read_only": True,
                "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"],
                "environment": dict(v.split("=", 1) for v in item["Config"]["Env"]),
                "volumes": [
                    {
                        "type": m["Type"],
                        "source": m["Source"],
                        "target": m["Destination"],
                        "read_only": not m["RW"],
                        "bind": {"create_host_path": True},
                    }
                    for m in item["Mounts"]
                ],
            }
        return {
            "name": self.runtime.receipt.project,
            "services": services,
            "networks": {
                "control": {
                    "name": self.runtime.receipt.project + "_control",
                    "internal": True,
                    "ipam": {},
                    "labels": {"org.omnis.start-attempt": self.runtime.attempt},
                }
            },
        }

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
            ("attempt", lambda x: x.update(labels={"org.omnis.start-attempt": "foreign"})),
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
