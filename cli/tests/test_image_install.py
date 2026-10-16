"""Explicit image install must refuse missing/invalid releases before Docker."""

import json
import os
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.compose import ImageInstallError, install_control_image


class ImageInstallTest(unittest.TestCase):
    def receipt(self, image_id: str = "sha256:" + "b" * 64):
        import omnis_cli.compose as compose

        project = "omnis-local-" + "a" * 32
        return compose.ImageReceipt(
            project,
            "omnis-control-" + "a" * 32 + ":0.1.0",
            image_id,
            "c" * 64,
            "unix:///run/docker.sock",
            "daemon-identity",
        )

    def test_native_install_binds_both_images_to_one_receipt(self):
        import omnis_cli.compose as compose
        from omnis_cli.release import install_release
        from test_install import InstallTest

        fixture = InstallTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        context = fixture.native_bundle()
        install_release(fixture.bundle, fixture.data_home)
        built = {}

        def inspect(tag, bundle, project, manifest_sha, *, host, runtime=False):
            return built.get(tag)

        def command(*args, **kwargs):
            self.assertEqual(args[0], "build")
            tag = args[args.index("-t") + 1]
            if "runtime" in tag:
                staged = Path(args[-1])
                self.assertNotEqual(staged, context)
                self.assertEqual(
                    (staged / "runtime-source/hermes_cli/main.py").read_bytes(), b"management"
                )
                self.assertFalse((staged / "source").exists())
            built[tag] = "sha256:" + ("d" if "runtime" in tag else "c") * 64
            return subprocess.CompletedProcess(args, 0)

        with (
            patch.object(compose, "_preflight", return_value="unix:///owned/docker.sock"),
            patch.object(compose, "_docker_id", return_value="daemon-identity"),
            patch.object(compose, "_base_image"),
            patch.object(compose, "_validate_image", side_effect=inspect),
            patch.object(compose, "_run", side_effect=command),
        ):
            receipt = compose.install_control_image(fixture.data_home, runtime_context=context)
        self.assertEqual(receipt.profile, "p4a-settings-offline")
        self.assertEqual(receipt.runtime_image_id, "sha256:" + "d" * 64)
        self.assertEqual(len(built), 2)
        raw = json.loads((fixture.data_home / "omnis/image.json").read_bytes())
        self.assertEqual(raw["format"], 2)
        self.assertEqual(
            compose._record(
                fixture.data_home / "omnis/image.json", receipt.manifest_sha256, complete=True
            ),
            receipt,
        )
        import time

        from omnis_cli.start_runtime import POSTGRES, ControlRuntime

        images = {
            receipt.image_id: {
                "Id": receipt.image_id,
                "Architecture": "amd64",
                "Os": "linux",
                "Config": {
                    "User": "65532:65532",
                    "Cmd": ["python", "-I", "-m", "omnis.serve"],
                    "Labels": {
                        "org.omnis.project": receipt.project,
                        "org.omnis.bundle_sha256": receipt.manifest_sha256,
                    },
                },
            },
            receipt.runtime_image_id: {
                "Id": receipt.runtime_image_id,
                "Architecture": "amd64",
                "Os": "linux",
                "Config": {
                    "User": "65532:65532",
                    "Cmd": ["/opt/hermes/venv/bin/python", "-I", "-m", "omnis_hermes.runtime_host"],
                    "Labels": {
                        "org.omnis.project": receipt.project,
                        "org.omnis.bundle_sha256": receipt.manifest_sha256,
                        "org.omnis.profile": receipt.profile,
                        "org.omnis.image-role": "runtime",
                    },
                },
            },
            POSTGRES: {
                "Id": "sha256:" + "f" * 64,
                "Architecture": "amd64",
                "Os": "linux",
                "RepoDigests": [POSTGRES.replace(":18.6-bookworm", "")],
            },
        }
        images[receipt.tag] = images[receipt.image_id]
        images[receipt.runtime_tag] = images[receipt.runtime_image_id]
        with (
            patch("omnis_cli.start_runtime._checked_socket", return_value=receipt.docker_host),
            patch.object(ControlRuntime, "check_daemon"),
            patch.object(ControlRuntime, "inspect", side_effect=lambda kind, ident: images[ident]),
            patch.object(
                ControlRuntime, "run", return_value=subprocess.CompletedProcess([], 0, "2.32.4")
            ) as command,
        ):
            runtime = ControlRuntime(fixture.data_home, time.monotonic() + 5)
            self.assertTrue(runtime.native)
            self.assertFalse(any(call.kwargs.get("effect") for call in command.call_args_list))

    def test_native_missing_or_wrong_context_refuses_before_docker(self):
        import omnis_cli.compose as compose
        from omnis_cli.release import install_release
        from test_install import InstallTest

        fixture = InstallTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        context = fixture.native_bundle()
        install_release(fixture.bundle, fixture.data_home)
        with patch.object(compose, "_run") as command:
            with self.assertRaises(ImageInstallError):
                compose.install_control_image(fixture.data_home)
            (context / "runtime-source/hermes_cli/main.py").write_bytes(b"wrong")
            with self.assertRaises(ImageInstallError):
                compose.install_control_image(fixture.data_home, runtime_context=context)
        command.assert_not_called()
        self.assertFalse((fixture.data_home / "omnis/image-installing.json").exists())

    def test_native_image_requires_new_profile_role_and_direct_host(self):
        import omnis_cli.compose as compose

        item = {
            "Id": "sha256:" + "d" * 64,
            "Architecture": "amd64",
            "Os": "linux",
            "Config": {
                "User": "65532:65532",
                "Entrypoint": None,
                "Cmd": ["/opt/hermes/venv/bin/python", "-I", "-m", "omnis_hermes.runtime_host"],
                "Labels": {
                    "org.omnis.project": "fixture",
                    "org.omnis.bundle_sha256": "a" * 64,
                    "org.omnis.profile": "p4a-settings-offline",
                    "org.omnis.image-role": "runtime",
                },
            },
        }
        with patch.object(compose, "_image", return_value=item):
            self.assertEqual(
                compose._validate_image(
                    "tag", Path("/"), "fixture", "a" * 64, host="unix:///fixture", runtime=True
                ),
                item["Id"],
            )
            item["Os"] = "windows"
            with self.assertRaises(ImageInstallError):
                compose._validate_image(
                    "tag", Path("/"), "fixture", "a" * 64, host="unix:///fixture", runtime=True
                )
            item["Os"] = "linux"
            del item["Config"]["Labels"]["org.omnis.profile"]
            with self.assertRaises(ImageInstallError):
                compose._validate_image(
                    "tag", Path("/"), "fixture", "a" * 64, host="unix:///fixture", runtime=True
                )
            item["Config"]["Labels"]["org.omnis.profile"] = "p4a-settings-offline"
            item["Config"]["Entrypoint"] = ["tini", "--"]
            with self.assertRaises(ImageInstallError):
                compose._validate_image(
                    "tag", Path("/"), "fixture", "a" * 64, host="unix:///fixture", runtime=True
                )

    def test_existing_receipt_does_not_require_base_image_for_readback(self):
        import omnis_cli.compose as compose

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            receipt = self.receipt()
            compose._put_record(root / "image.json", receipt, complete=True)
            with (
                patch.object(compose, "_preflight", return_value=receipt.docker_host),
                patch.object(compose, "_docker_id", return_value=receipt.docker_id),
                patch.object(compose, "_validate_image", return_value=receipt.image_id),
                patch.object(compose, "_base_image") as base,
                patch.object(compose, "_run") as command,
            ):
                self.assertEqual(
                    compose._install_locked(root, root, receipt.manifest_sha256), receipt
                )
            base.assert_not_called()
            command.assert_not_called()

    def test_untrusted_socket_symlink_and_docker_override_are_refused(self):
        import omnis_cli.compose as compose

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            scratch = Path(name)
            socket_path = scratch / "docker.sock"
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(str(socket_path))
                link = scratch / "docker-link.sock"
                link.symlink_to(socket_path)
                with self.assertRaises(compose.ImageInstallError):
                    compose._checked_socket(f"unix://{link}")
                with patch.dict(os.environ, {"DOCKER_CONTEXT": "foreign"}):
                    with patch.object(compose, "_run") as command:
                        with self.assertRaises(compose.ImageInstallError):
                            compose._preflight(scratch)
                    command.assert_not_called()

    def test_daemon_identity_changes_after_image_readback_are_refused(self):
        import omnis_cli.compose as compose

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            with (
                patch.object(compose, "_preflight", return_value="unix:///run/docker.sock"),
                patch.object(
                    compose, "_docker_id", side_effect=["daemon-one", "daemon-one", "daemon-two"]
                ),
                patch.object(compose, "_base_image"),
                patch.object(compose, "_validate_image", side_effect=[None, "sha256:" + "b" * 64]),
                patch.object(
                    compose,
                    "_run",
                    return_value=subprocess.CompletedProcess(["docker", "build"], 0),
                ),
            ):
                with self.assertRaises(compose.ImageInstallError):
                    compose._install_locked(root, root, "a" * 64)
            self.assertFalse((root / "image.json").exists())

    def test_retry_requires_directory_sync_of_a_recovered_receipt(self):
        import omnis_cli.compose as compose

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            receipt = self.receipt()
            compose._put_record(root / "image.json", receipt, complete=True)
            with patch.object(compose.os, "fsync", side_effect=OSError("directory sync failed")):
                with self.assertRaises(OSError):
                    compose._record(root / "image.json", receipt.manifest_sha256, complete=True)

    def test_receipt_pins_the_verified_docker_endpoint(self):
        import omnis_cli.compose as compose

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            receipt = self.receipt()
            path = Path(name) / "image.json"
            compose._put_record(path, receipt, complete=True)
            self.assertEqual(compose._record(path, receipt.manifest_sha256, complete=True), receipt)
            self.assertEqual(json.loads(path.read_text())["docker_host"], receipt.docker_host)
            self.assertEqual(json.loads(path.read_text())["docker_id"], receipt.docker_id)
            self.assertEqual(path.stat().st_nlink, 1)

    def test_preflight_canonicalizes_socket_without_base_inspection(self):
        import omnis_cli.compose as compose

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            socket_path = Path(name) / "docker.sock"
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(str(socket_path))
                host = f"unix://{socket_path}"

                def docker(*argv, **_kwargs):
                    if argv[:2] == ("context", "show"):
                        return subprocess.CompletedProcess(argv, 0, stdout="default\n")
                    if argv[:2] == ("context", "inspect"):
                        return subprocess.CompletedProcess(argv, 0, stdout=host + "\n")
                    self.fail("Preflight must not inspect the base or build")

                with patch.object(compose, "_run", side_effect=docker):
                    self.assertEqual(compose._preflight(Path(name)), host)

    def test_docker_command_uses_verified_endpoint_in_argv(self):
        import omnis_cli.compose as compose

        with patch.object(compose.subprocess, "run") as command:
            compose._run(
                "image", "inspect", "sha256:owned", cwd=Path("/"), host="unix:///owned/docker.sock"
            )
        self.assertEqual(
            command.call_args.args[0][:4],
            ["docker", "--host", "unix:///owned/docker.sock", "image"],
        )

    def test_image_build_and_readback_use_the_preflight_endpoint(self):
        import omnis_cli.compose as compose

        endpoint = "unix:///owned/docker.sock"
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            with (
                patch.object(compose, "_preflight", return_value=endpoint),
                patch.object(compose, "_docker_id", return_value="daemon-identity"),
                patch.object(compose, "_base_image"),
                patch.object(
                    compose, "_validate_image", side_effect=[None, "sha256:" + "d" * 64]
                ) as inspect,
                patch.object(
                    compose, "_run", return_value=subprocess.CompletedProcess(["docker"], 0)
                ) as command,
            ):
                receipt = compose._install_locked(root, root, "a" * 64)
            self.assertEqual(receipt.image_id, "sha256:" + "d" * 64)
            self.assertEqual(receipt.docker_id, "daemon-identity")
            self.assertEqual(command.call_args.kwargs.get("host"), endpoint)
            self.assertTrue(
                all(call.kwargs.get("host") == endpoint for call in inspect.call_args_list)
            )

    def test_no_installed_release_never_touches_docker(self):
        with tempfile.TemporaryDirectory(
            prefix="omnis-image-install-", dir=os.environ["TMPDIR"]
        ) as name:
            home = Path(name)
            with patch("omnis_cli.compose.subprocess.run") as command:
                with self.assertRaises(ImageInstallError):
                    install_control_image(home)
            command.assert_not_called()

    def test_failed_build_with_tag_is_not_an_installed_image(self):
        import omnis_cli.compose as compose

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            with (
                patch.object(compose, "_preflight", return_value="unix:///owned/docker.sock"),
                patch.object(compose, "_docker_id", return_value="daemon-identity"),
                patch.object(compose, "_base_image"),
                patch.object(compose, "_validate_image", side_effect=[None, "sha256:" + "b" * 64]),
                patch.object(
                    compose,
                    "_run",
                    return_value=subprocess.CompletedProcess(["docker", "build"], 1),
                ),
            ):
                with self.assertRaises(ImageInstallError):
                    compose._install_locked(root, root, "a" * 64)
            self.assertFalse((root / "image.json").exists())

    def test_preexisting_unconfirmed_tag_requires_recovery(self):
        import omnis_cli.compose as compose

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            receipt = self.receipt(image_id="")
            compose._put_record(root / "image-installing.json", receipt, complete=False)
            with (
                patch.object(compose, "_preflight", return_value=receipt.docker_host),
                patch.object(compose, "_docker_id", return_value=receipt.docker_id),
                patch.object(compose, "_validate_image", return_value="sha256:" + "c" * 64),
                patch.object(compose, "_run") as command,
            ):
                with self.assertRaises(ImageInstallError):
                    compose._install_locked(root, root, receipt.manifest_sha256)
            command.assert_not_called()
            self.assertFalse((root / "image.json").exists())

    def test_interrupted_intent_without_tag_is_not_rebuilt(self):
        import omnis_cli.compose as compose

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            intent = self.receipt(image_id="")
            compose._put_record(root / "image-installing.json", intent, complete=False)
            with (
                patch.object(compose, "_preflight", return_value=intent.docker_host),
                patch.object(compose, "_docker_id", return_value=intent.docker_id),
                patch.object(compose, "_validate_image", return_value=None),
                patch.object(compose, "_base_image") as base,
                patch.object(compose, "_run") as docker,
            ):
                with self.assertRaises(ImageInstallError):
                    compose._install_locked(root, root, intent.manifest_sha256)
            base.assert_not_called()
            docker.assert_not_called()
            self.assertFalse((root / "image.json").exists())

    def test_interrupted_receipt_publication_has_no_partial_final_name(self):
        import omnis_cli.compose as compose

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            record = self.receipt()
            final = root / "image.json"
            with patch.object(
                compose, "publish_directory", side_effect=OSError("interrupted publication")
            ):
                with self.assertRaises(OSError):
                    compose._put_record(final, record, complete=True)
            self.assertFalse(final.exists())
            self.assertEqual(list(root.iterdir()), [], "Owned staging file must be cleaned")
