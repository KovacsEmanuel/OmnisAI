"""Explicit image install must refuse missing/invalid releases before Docker."""

import hashlib
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

        def inspect(
            tag,
            bundle,
            project,
            manifest_sha,
            *,
            host,
            runtime=False,
            profile="p4a-settings-offline",
        ):
            if runtime:
                self.assertEqual(profile, "p4a-settings-offline")
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
                for key in ("DOCKER_CONTEXT", "DOCKER_CONFIG"):
                    with patch.dict(os.environ, {key: str(scratch)}):
                        with patch.object(compose, "_run") as command:
                            with self.assertRaisesRegex(
                                compose.ImageInstallError, "Ambient Docker overrides are forbidden"
                            ):
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

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            root = Path(name)
            home = root / "caller-home"
            home.mkdir(mode=0o700)
            for leaf in ("bundle", "native-staged"):
                cwd = root / leaf
                cwd.mkdir(mode=0o700)
                for failure in (None, OSError("spawn"), subprocess.TimeoutExpired("docker", 15)):
                    configs = []

                    def command(argv, *, state=(configs, cwd, failure), **kwargs):
                        configs, cwd, failure = state
                        self.assertEqual(argv[:2], ["docker", "--config"])
                        config = Path(argv[2])
                        configs.append(config)
                        self.assertEqual(config.parent, root)
                        self.assertFalse(config.is_relative_to(cwd))
                        self.assertEqual(config.stat().st_mode & 0o777, 0o700)
                        self.assertEqual((config / "config.json").stat().st_mode & 0o777, 0o600)
                        self.assertEqual(
                            json.loads((config / "config.json").read_bytes()),
                            {"auths": {"https://index.docker.io/v1/": {}}},
                        )
                        self.assertEqual(
                            kwargs["env"],
                            {
                                "PATH": "/usr/bin:/bin",
                                "HOME": str(config),
                                "DOCKER_CONFIG": str(config),
                            },
                        )
                        self.assertEqual(
                            argv[3:],
                            [
                                "--host",
                                "unix:///owned/docker.sock",
                                "image",
                                "inspect",
                                "sha256:owned",
                            ],
                        )
                        self.assertEqual(kwargs["cwd"], cwd)
                        self.assertEqual(kwargs["timeout"], 15)
                        if failure is not None:
                            raise failure
                        return subprocess.CompletedProcess(argv, 0, "[]", "")

                    with (
                        self.subTest(cwd=leaf, failure=type(failure).__name__),
                        patch.dict(
                            os.environ,
                            {
                                "HOME": str(home),
                                "PATH": "/usr/bin:/bin",
                                "HTTPS_PROXY": "synthetic",
                            },
                            clear=True,
                        ),
                        patch.object(compose.subprocess, "run", side_effect=command),
                    ):
                        if failure is None:
                            compose._run(
                                "image",
                                "inspect",
                                "sha256:owned",
                                cwd=cwd,
                                host="unix:///owned/docker.sock",
                            )
                        else:
                            with self.assertRaises(type(failure)):
                                compose._run(
                                    "image",
                                    "inspect",
                                    "sha256:owned",
                                    cwd=cwd,
                                    host="unix:///owned/docker.sock",
                                )
                        self.assertEqual(len(configs), 1)
                        self.assertFalse(configs[0].exists())
                        self.assertEqual(list(cwd.iterdir()), [])
                        self.assertEqual(list(home.iterdir()), [])

    def test_isolated_preflight_refuses_nondefault_context(self):
        import omnis_cli.compose as compose

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            with (
                patch.dict(os.environ, {}, clear=True),
                patch.object(
                    compose, "_run", return_value=subprocess.CompletedProcess([], 0, "rootless\n")
                ) as command,
                patch.object(compose, "_checked_socket", return_value="unix:///synthetic"),
            ):
                with self.assertRaisesRegex(ImageInstallError, "Local Docker context unavailable"):
                    compose._preflight(Path(name))
            self.assertEqual(command.call_count, 1)

    def test_public_native_install_uses_anonymous_client_and_preserves_uncertainty(self):
        """SOURCE only: normal CLI chain, synthetic Engine at subprocess.run."""
        import io

        import omnis_cli.compose as compose
        from omnis_cli.main import main
        from omnis_cli.release import _manifest, install_release
        from test_install import InstallTest

        for timeout in (False, True):
            with self.subTest(timeout=timeout):
                fixture = InstallTest()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                context = fixture.native_bundle()
                bundle = install_release(fixture.bundle, fixture.data_home)
                original = _manifest(bundle)
                configs, calls, built = [], [], {}
                sock = fixture.root / "d.sock"
                host = f"unix://{sock}"

                def engine(argv, *, state=(configs, calls, built, bundle, host, timeout), **kwargs):
                    configs, calls, built, bundle, host, timeout = state
                    self.assertEqual(argv[:2], ["docker", "--config"])
                    config = Path(argv[2])
                    configs.append(config)
                    cwd = kwargs["cwd"]
                    self.assertEqual(config.parent, cwd.parent)
                    self.assertFalse(config.is_relative_to(bundle))
                    self.assertFalse(config.is_relative_to(cwd))
                    self.assertEqual(
                        json.loads((config / "config.json").read_bytes()),
                        {"auths": {"https://index.docker.io/v1/": {}}},
                    )
                    self.assertEqual(
                        kwargs["env"],
                        {
                            "PATH": "/usr/bin:/bin",
                            "HOME": str(config),
                            "DOCKER_CONFIG": str(config),
                        },
                    )
                    args = argv[3:]
                    if args[:1] == ["context"]:
                        calls.append(tuple(args[:2]))
                        output = "default" if args[1] == "show" else host
                    else:
                        self.assertEqual(args[:2], ["--host", host])
                        args = args[2:]
                        calls.append(tuple(args[:2]))
                        if args[0] == "info":
                            output = "daemon-identity"
                        elif args[:2] == ["image", "inspect"]:
                            tag = args[2]
                            if tag == compose._BASE:
                                item = {
                                    "Architecture": "amd64",
                                    "RepoDigests": [
                                        compose._BASE.replace(":3.13.15-slim-bookworm", "")
                                    ],
                                }
                            elif tag in built:
                                item = built[tag]
                            else:
                                return subprocess.CompletedProcess(argv, 1, "", "No such image")
                            output = json.dumps([item])
                        else:
                            self.assertEqual(args[0], "build")
                            self.assertEqual(kwargs["timeout"], 300)
                            if timeout:
                                raise subprocess.TimeoutExpired(argv, 300)
                            tag = args[args.index("-t") + 1]
                            labels = dict(
                                args[i + 1].split("=", 1)
                                for i, arg in enumerate(args)
                                if arg == "--label"
                            )
                            native = "runtime" in tag
                            built[tag] = {
                                "Id": "sha256:" + ("d" if native else "c") * 64,
                                "Architecture": "amd64",
                                "Os": "linux",
                                "Config": {
                                    "User": "65532:65532",
                                    "Labels": labels,
                                    "Cmd": [
                                        "/opt/hermes/venv/bin/python",
                                        "-I",
                                        "-m",
                                        "omnis_hermes.runtime_host",
                                    ]
                                    if native
                                    else [],
                                },
                            }
                            output = ""
                    return subprocess.CompletedProcess(argv, 0, output, "")

                with (
                    socket.socket(socket.AF_UNIX) as listener,
                    patch.dict(
                        os.environ,
                        {
                            "PATH": "/usr/bin:/bin",
                            "HOME": str(fixture.root),
                            "XDG_DATA_HOME": str(fixture.data_home),
                        },
                        clear=True,
                    ),
                    patch.object(compose.subprocess, "run", side_effect=engine),
                    patch("sys.stdout", new=io.StringIO()),
                    patch("sys.stderr", new=io.StringIO()),
                ):
                    listener.bind(str(sock))
                    self.assertEqual(
                        main(["install-image", "--runtime-context", str(context)]),
                        2 if timeout else 0,
                    )
                    if timeout:
                        self.assertTrue(
                            (fixture.data_home / "omnis/image-installing.json").is_file()
                        )
                        self.assertFalse((fixture.data_home / "omnis/image.json").exists())
                        before = calls.count(("build", "--platform"))
                        self.assertEqual(
                            main(["install-image", "--runtime-context", str(context)]), 2
                        )
                        self.assertEqual(calls.count(("build", "--platform")), before)
                    else:
                        receipt = compose._record(
                            fixture.data_home / "omnis/image.json",
                            hashlib.sha256(original[0]).hexdigest(),
                            complete=True,
                        )
                        assert receipt is not None
                        self.assertEqual(receipt.docker_host, host)
                        self.assertEqual(receipt.runtime_image_id, "sha256:" + "d" * 64)
                        self.assertEqual(len(built), 2)
                        self.assertEqual(
                            main(["install-image", "--runtime-context", str(context)]), 0
                        )
                        self.assertEqual(calls.count(("build", "--platform")), 2)
                self.assertEqual(_manifest(bundle), original)
                self.assertTrue(configs)
                self.assertTrue(all(not config.exists() for config in configs))
                self.assertIn(("context", "show"), calls)
                self.assertIn(("context", "inspect"), calls)

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
