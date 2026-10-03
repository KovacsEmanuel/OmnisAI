"""M03: actual preflight, only receipt/inspect/config channels substituted."""

import hashlib
import os
import subprocess
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from omnis_cli.start_runtime import POSTGRES, ControlRuntime


class RuntimePreflightTest(unittest.TestCase):
    def test_supported_control_and_refusal_matrix_have_zero_resource_effects(self):
        with tempfile.TemporaryDirectory(prefix="pf-", dir=os.environ["TMPDIR"]) as name:
            data = Path(name)
            digest = hashlib.sha256(b"{}").hexdigest()
            receipt = SimpleNamespace(
                project="omnis-local-" + "a" * 32,
                image_id="sha256:" + "b" * 64,
                docker_host="unix:///run/docker.sock",
                docker_id="fixture-daemon",
                tag="fixture-tag",
            )
            image = {
                "Id": receipt.image_id,
                "Architecture": "amd64",
                "Os": "linux",
                "Config": {
                    "User": "65532:65532",
                    "Cmd": ["python", "-I", "-m", "omnis.serve"],
                    "Labels": {
                        "org.omnis.project": receipt.project,
                        "org.omnis.bundle_sha256": digest,
                    },
                },
            }
            pg = {
                "Id": "sha256:" + "c" * 64,
                "Architecture": "amd64",
                "RepoDigests": [POSTGRES.replace(":18.6-bookworm", "")],
            }
            for fault in (
                None,
                "platform",
                "architecture",
                "root-uid",
                "root-gid",
                "ambient",
                "socket",
                "daemon",
                "image",
                "image-entrypoint",
                "tag",
                "receipt",
                "compose-v1",
                "compose-missing",
            ):
                effects = []

                def run(owner, *args, mode=fault, history=effects, **kwargs):
                    history.append((args, kwargs.get("effect", False)))
                    if args == ("compose", "version", "--short"):
                        if mode == "compose-missing":
                            raise FileNotFoundError("synthetic missing Compose plugin")
                        return subprocess.CompletedProcess(
                            args, 0, "1.29.2" if mode == "compose-v1" else "2.32.4"
                        )
                    return subprocess.CompletedProcess(
                        args, 0, "wrong-daemon" if mode == "daemon" else receipt.docker_id
                    )

                def inspect(owner, kind, ident, mode=fault):
                    if ident == POSTGRES:
                        return pg
                    if mode == "image-entrypoint" and ident == receipt.image_id:
                        return {**image, "Config": {**image["Config"], "Entrypoint": ["sh"]}}
                    if mode == "image" and ident == receipt.image_id:
                        return {**image, "Architecture": "foreign"}
                    if mode == "tag" and ident == receipt.tag:
                        return {**image, "Id": "sha256:" + "0" * 64}
                    return image

                with self.subTest(fault=fault), ExitStack() as scope:
                    scope.enter_context(
                        patch.dict(
                            os.environ,
                            {
                                "PATH": "/usr/bin:/bin",
                                **({"DOCKER_HOST": "synthetic"} if fault == "ambient" else {}),
                            },
                            clear=True,
                        )
                    )
                    scope.enter_context(patch("omnis_cli.start_runtime.private_dir"))
                    scope.enter_context(
                        patch("omnis_cli.start_runtime._installed_pointer", return_value=True)
                    )
                    scope.enter_context(
                        patch("omnis_cli.start_runtime._manifest", return_value=(b"{}", {}))
                    )
                    scope.enter_context(
                        patch(
                            "omnis_cli.start_runtime._record",
                            return_value=None if fault == "receipt" else receipt,
                        )
                    )
                    scope.enter_context(
                        patch(
                            "omnis_cli.start_runtime._checked_socket",
                            side_effect=OSError("synthetic missing socket")
                            if fault == "socket"
                            else None,
                            return_value=receipt.docker_host,
                        )
                    )
                    scope.enter_context(
                        patch(
                            "omnis_cli.start_runtime.platform.system",
                            return_value="foreign" if fault == "platform" else "Linux",
                        )
                    )
                    scope.enter_context(
                        patch(
                            "omnis_cli.start_runtime.platform.machine",
                            return_value="foreign" if fault == "architecture" else "x86_64",
                        )
                    )
                    if fault in {"root-uid", "root-gid"}:
                        scope.enter_context(
                            patch(
                                "os.getuid" if fault == "root-uid" else "os.getgid", return_value=0
                            )
                        )
                    scope.enter_context(patch.object(ControlRuntime, "run", run))
                    scope.enter_context(patch.object(ControlRuntime, "inspect", inspect))
                    if fault is None:
                        runtime = ControlRuntime(data, time.monotonic() + 3)
                        self.assertIs(runtime.receipt, receipt)
                        self.assertFalse(runtime.uncertain)
                        self.assertTrue(runtime.family_drained)
                    else:
                        with self.assertRaises((ValueError, OSError)):
                            ControlRuntime(data, time.monotonic() + 3)
                self.assertTrue(all(not effect for _, effect in effects))
                self.assertTrue(all(args[0] in {"info", "compose"} for args, _ in effects))
                self.assertEqual(list(data.iterdir()), [])
