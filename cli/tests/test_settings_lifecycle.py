"""Four-role SOURCE topology; synthetic inspect, no Docker/native execution."""

import json
import os
import subprocess
from copy import deepcopy
from unittest.mock import Mock

from omnis_cli.lifecycle import StartError, write_record
from omnis_cli.start import validate_config
from omnis_cli.start_runtime import ControlRuntime
from test_start_attestation import ProductAttestationTest


class SettingsTopologyTest(ProductAttestationTest):
    def native(self):
        self.runtime.receipt.profile = "p4a-settings-offline"
        self.runtime.receipt.runtime_image_id = "sha256:" + "2" * 64
        self.runtime.release = self.root / "release"
        for name in ("native-ipc", "provider"):
            (self.root / name).mkdir(mode=0o700)
        info = (self.root / "provider").stat()
        ipc = (self.root / "native-ipc").stat()
        write_record(self.root / "startup.json", {
            "format": 3,
            "provider_identity": [info.st_dev, info.st_ino, info.st_uid, info.st_gid, 0o700],
            "runtime_dir_identity": [ipc.st_dev, ipc.st_ino, ipc.st_uid, ipc.st_gid, 0o700],
        })

    def test_sealed_native_compose_and_full_attestation(self):
        self.native()
        from omnis_cli.start import environment
        self.env = environment(self.runtime, self.root, self.control, self.port)
        self.runtime.run = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
        ControlRuntime.compose(self.runtime, self.env, "config", "--format", "json")
        call = self.runtime.run.call_args
        self.assertIn("-", call.args)
        overlay = json.loads(call.kwargs["stdin"])
        config = self.config()
        config["services"]["supervisor"]["environment"].update(
            overlay["services"]["supervisor"]["environment"])
        config["services"]["supervisor"]["volumes"].extend(
            overlay["services"]["supervisor"]["volumes"])
        config["services"]["runtime"] = overlay["services"]["runtime"]
        self.runtime.compose = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps(config), ""))
        validate_config(self.runtime, self.env)
        for mutation in ("network_mode", "init", "image", "volumes", "environment"):
            bad = deepcopy(config)
            bad["services"]["runtime"][mutation] = {
                "network_mode": "host", "init": True, "image": self.runtime.receipt.image_id,
                "volumes": [], "environment": {"OMNIS_DATABASE_URL": "forbidden"},
            }[mutation]
            self.runtime.compose.return_value.stdout = json.dumps(bad)
            with self.assertRaises(StartError):
                validate_config(self.runtime, self.env)
        item = self.item("supervisor")
        item["Config"]["Env"].append("OMNIS_RUNTIME_DIR=/runtime")
        item["Mounts"].append({"Type": "bind", "Source": str(self.root / "native-ipc"),
                              "Destination": "/runtime", "RW": True, "Propagation": "rprivate"})
        native = deepcopy(item)
        native["Config"]["Labels"]["com.docker.compose.service"] = "runtime"
        native["Config"]["Cmd"] = ["/opt/hermes/venv/bin/python", "-I", "-m", "omnis_hermes.runtime_host"]
        native["Config"]["Env"] = ["PATH=/synthetic/image/bin", "OMNIS_RUNTIME_DIR=/runtime"]
        native["Image"] = self.runtime.receipt.runtime_image_id
        native["HostConfig"]["NetworkMode"] = "none"
        native["NetworkSettings"]["Networks"] = {"none": {"NetworkID": "3" * 64}}
        native["Mounts"] = [item["Mounts"][-1], {"Type": "bind", "Source": str(self.root / "provider"),
            "Destination": "/state/provider", "RW": True, "Propagation": "rprivate"}]
        self.runtime.inspect = Mock(side_effect=lambda kind, ident: (
            {"Id": self.runtime.receipt.runtime_image_id, "Config": {"Env": ["PATH=/synthetic/image/bin"]}}
            if kind == "image" else self.network if kind == "network" else native))
        self.assertEqual(self.runtime.attest(self.cid, "runtime", self.root, self.control, self.port), native)
        (self.root / "provider").rename(self.root / "old-provider")
        (self.root / "provider").mkdir(mode=0o700)
        with self.assertRaises(StartError):
            self.runtime.attest(self.cid, "runtime", self.root, self.control, self.port)
