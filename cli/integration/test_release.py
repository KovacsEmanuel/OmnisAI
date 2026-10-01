"""Build and install a real locked control bundle outside the checkout."""

import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from omnis_cli.compose import _checked_socket, _docker_id, _record
from omnis_cli.instance import private_dir

ROOT = Path(__file__).resolve().parents[2]


class ReleaseBundleTest(unittest.TestCase):
    def run_cli_scope(self, argv, *, cwd, env, timeout):
        """Own the CLI and its Docker child as one process group on timeout."""
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate(timeout=5)
            raise
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)

    def test_cli_timeout_kills_a_term_resistant_owned_child(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            scratch = Path(name)
            ready = scratch / "ready"
            late = scratch / "late-tag"
            child = (
                "import os,signal,time; from pathlib import Path; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                f"Path({str(ready)!r}).write_text(str(os.getpid())); "
                "time.sleep(2); "
                f"Path({str(late)!r}).write_text('late')"
            )
            parent = scratch / "driver.py"
            parent.write_text(
                "import subprocess,sys,time\n"
                f"subprocess.Popen([sys.executable, '-c', {child!r}], "
                "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
                "time.sleep(10)\n"
            )
            with self.assertRaises(subprocess.TimeoutExpired):
                self.run_cli_scope(
                    [sys.executable, str(parent)],
                    cwd=scratch,
                    env={"PATH": os.environ.get("PATH", "")},
                    timeout=1,
                )
            self.assertTrue(ready.is_file(), "Child must have started before timeout")
            time.sleep(2.2)
            self.assertFalse(late.exists(), "Owned child must not publish after timeout")

    @contextmanager
    def bundle_scratch(self):
        scratch = Path(tempfile.mkdtemp(prefix="omnis-bundle-", dir=os.environ["TMPDIR"]))
        keep = False
        try:
            yield scratch
        except BaseException:
            root = scratch / "data/omnis"
            keep = (root / "image-installing.json").exists() or (root / "image.json").exists()
            if keep:
                print(f"IMAGE_RECOVERY_INTENT retained at {scratch}", file=sys.stderr)
            raise
        finally:
            if not keep:
                shutil.rmtree(scratch)

    def test_uncertain_install_preserves_private_recovery_intent(self):
        scratch = None
        try:
            with self.assertRaisesRegex(RuntimeError, "uncertain"):
                with self.bundle_scratch() as scratch:
                    intent = scratch / "data/omnis/image-installing.json"
                    intent.parent.mkdir(parents=True, mode=0o700)
                    intent.write_text("synthetic-intent")
                    raise RuntimeError("uncertain")
            self.assertIsNotNone(scratch)
            self.assertEqual(intent.read_text(), "synthetic-intent")
        finally:
            if scratch is not None:
                shutil.rmtree(scratch)

    def test_probe_of_installed_image_reaps_its_named_container_on_timeout(self):
        host = "unix:///run/docker.sock"
        receipt = {
            "docker_host": host,
            "project": "omnis-local-" + "a" * 32,
            "image_id": "sha256:" + "b" * 64,
        }
        removed = False
        started = False

        def docker(argv, **_kwargs):
            nonlocal removed, started
            if argv[:5] == ["docker", "--host", host, "container", "inspect"]:
                if removed or not started:
                    return subprocess.CompletedProcess(argv, 1, stderr="No such container")
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    stdout=json.dumps(
                        [
                            {
                                "Image": receipt["image_id"],
                                "Config": {"Labels": {"org.omnis.project": receipt["project"]}},
                            }
                        ]
                    ),
                )
            if argv[:3] == ["docker", "--host", host] and argv[3] == "run":
                started = True
                self.assertIn("none", argv)
                self.assertIn("--read-only", argv)
                self.assertIn(receipt["image_id"], argv)
                raise subprocess.TimeoutExpired(argv, 25)
            if argv[:6] == ["docker", "--host", host, "container", "rm", "-f"]:
                removed = True
                return subprocess.CompletedProcess(argv, 0)
            self.fail("Unexpected Docker operation")

        with patch("subprocess.run", side_effect=docker):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.probe_installed_image(receipt, Path(os.environ["TMPDIR"]))
        self.assertTrue(removed)

    def probe_installed_image(self, receipt, scratch):
        """Execute the exact read-back image ID with no network or writable rootfs."""
        host = receipt["docker_host"]
        name = "omnis-p04-installed-" + receipt["project"].removeprefix("omnis-local-")
        inspect = ["docker", "--host", host, "container", "inspect", name]
        before = subprocess.run(
            inspect, cwd=scratch, capture_output=True, text=True, timeout=15, check=False
        )
        self.assertNotEqual(before.returncode, 0, "Refuse a preexisting container name")
        self.assertIn("No such container", before.stderr, "Container preflight uncertain")
        uid = os.getuid() if os.getuid() not in {0, 65532} else 1001
        command = [
            "docker",
            "--host",
            host,
            "run",
            "--name",
            name,
            "--label",
            f"org.omnis.project={receipt['project']}",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            f"{uid}:{uid}",
            receipt["image_id"],
            "python",
            "-I",
            "-c",
            "import os; from omnis.api import create_app; "
            "from omnis.core.web_assets import WebAssets; assert create_app().routes; "
            "assets=WebAssets(os.environ['OMNIS_WEB_ROOT']).load(); "
            "assert assets and 'index.html' in assets; "
            "print('IMAGE_RUNTIME_OK uid=' + str(os.getuid()))",
        ]
        try:
            result = subprocess.run(
                command, cwd=scratch, capture_output=True, text=True, timeout=25, check=False
            )
            self.assertEqual(result.returncode, 0, "Installed image cannot load API/assets")
            self.assertEqual(result.stdout.strip(), f"IMAGE_RUNTIME_OK uid={uid}")
        finally:
            owned = subprocess.run(
                inspect, cwd=scratch, capture_output=True, text=True, timeout=15, check=False
            )
            if owned.returncode:
                self.assertIn("No such container", owned.stderr, "Container cleanup uncertain")
            else:
                (container,) = json.loads(owned.stdout)
                self.assertEqual(container["Image"], receipt["image_id"])
                self.assertEqual(
                    container["Config"]["Labels"].get("org.omnis.project"), receipt["project"]
                )
                subprocess.run(
                    ["docker", "--host", host, "container", "rm", "-f", name],
                    cwd=scratch,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True,
                )
                absent = subprocess.run(
                    inspect, cwd=scratch, capture_output=True, text=True, timeout=15, check=False
                )
                self.assertNotEqual(absent.returncode, 0, "Installed probe container survived")
                self.assertIn("No such container", absent.stderr)

    def test_image_install_timeout_cleans_recorded_tag(self):
        project = "omnis-local-" + "a" * 32
        tag = "omnis-control-" + "a" * 32 + ":0.1.0"
        removed = False
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            scratch = Path(name)
            data = scratch / "data"
            root = data / "omnis"
            release = root / "releases/0.1.0"
            release.mkdir(parents=True, mode=0o700)
            root.chmod(0o700)
            manifest = b'{"synthetic":"manifest"}'
            (release / "release.json").write_bytes(manifest)
            digest = hashlib.sha256(manifest).hexdigest()
            with socket.socket(socket.AF_UNIX) as listener:
                path = scratch / "docker.sock"
                listener.bind(str(path))
                host = f"unix://{path}"
                intent = root / "image-installing.json"
                intent.write_text(
                    json.dumps(
                        {
                            "format": 1,
                            "release": "0.1.0",
                            "project": project,
                            "tag": tag,
                            "manifest_sha256": digest,
                            "docker_host": host,
                            "docker_id": "daemon-identity",
                        }
                    )
                )
                intent.chmod(0o600)

                def command(argv, **_kwargs):
                    nonlocal removed
                    if argv[:3] == ["docker", "--host", host] and argv[3] == "info":
                        return subprocess.CompletedProcess(argv, 0, stdout="daemon-identity\n")
                    if argv[:3] == ["docker", "--host", host] and argv[3:5] == ["image", "inspect"]:
                        if removed:
                            return subprocess.CompletedProcess(
                                argv, 1, stdout="", stderr="No such image"
                            )
                        return subprocess.CompletedProcess(
                            argv,
                            0,
                            stdout=json.dumps(
                                [
                                    {
                                        "Id": "sha256:" + "b" * 64,
                                        "Config": {
                                            "Labels": {
                                                "org.omnis.project": project,
                                                "org.omnis.bundle_sha256": digest,
                                            }
                                        },
                                    }
                                ]
                            ),
                        )
                    if argv[:3] == ["docker", "--host", host] and argv[3:5] == ["image", "rm"]:
                        removed = True
                        return subprocess.CompletedProcess(argv, 0)
                    raise AssertionError("Unexpected cleanup operation")

                with (
                    patch("subprocess.run", side_effect=command),
                    patch.object(
                        self,
                        "run_cli_scope",
                        side_effect=subprocess.TimeoutExpired(["/synthetic/omnis"], 420),
                    ),
                ):
                    with self.assertRaisesRegex(AssertionError, "uncertain"):
                        self.assert_image_install("/synthetic/omnis", {"PATH": ""}, data, scratch)
        self.assertTrue(removed, "A CLI timeout must clean its owned tagged image")

    def test_timeout_with_late_image_keeps_uncertainty_after_cleanup(self):
        project = "omnis-local-" + "a" * 32
        tag = "omnis-control-" + "a" * 32 + ":0.1.0"
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            scratch = Path(name)
            data = scratch / "data"
            root = data / "omnis"
            release = root / "releases/0.1.0"
            release.mkdir(parents=True, mode=0o700)
            root.chmod(0o700)
            manifest = b'{"synthetic":"manifest"}'
            (release / "release.json").write_bytes(manifest)
            digest = hashlib.sha256(manifest).hexdigest()
            with socket.socket(socket.AF_UNIX) as listener:
                path = scratch / "docker.sock"
                listener.bind(str(path))
                host = f"unix://{path}"
                intent = root / "image-installing.json"
                intent.write_text(
                    json.dumps(
                        {
                            "format": 1,
                            "release": "0.1.0",
                            "project": project,
                            "tag": tag,
                            "manifest_sha256": digest,
                            "docker_host": host,
                            "docker_id": "daemon-identity",
                        }
                    )
                )
                intent.chmod(0o600)
                inspected = 0
                removed = False

                def command(argv, **_kwargs):
                    nonlocal inspected, removed
                    if argv[:3] != ["docker", "--host", host]:
                        self.fail("Unexpected endpoint")
                    if argv[3] == "info":
                        return subprocess.CompletedProcess(argv, 0, stdout="daemon-identity\n")
                    if argv[3:5] == ["image", "inspect"]:
                        inspected += 1
                        if inspected == 1 or removed:
                            return subprocess.CompletedProcess(argv, 1, stderr="No such image")
                        return subprocess.CompletedProcess(
                            argv,
                            0,
                            stdout=json.dumps(
                                [
                                    {
                                        "Id": "sha256:" + "b" * 64,
                                        "Config": {
                                            "Labels": {
                                                "org.omnis.project": project,
                                                "org.omnis.bundle_sha256": digest,
                                            }
                                        },
                                    }
                                ]
                            ),
                        )
                    if argv[3:5] == ["image", "rm"]:
                        removed = True
                        return subprocess.CompletedProcess(argv, 0)
                    self.fail("Unexpected Docker operation")

                with (
                    patch("subprocess.run", side_effect=command),
                    patch.object(
                        self,
                        "run_cli_scope",
                        side_effect=subprocess.TimeoutExpired(["/synthetic/omnis"], 420),
                    ),
                ):
                    with self.assertRaisesRegex(AssertionError, "uncertain"):
                        self.assert_image_install("/synthetic/omnis", {"PATH": ""}, data, scratch)
                self.assertTrue(removed)
                self.assertGreaterEqual(inspected, 3)
                self.assertTrue(intent.exists(), "Recovery identity must survive uncertainty")

    def test_cleanup_rejects_daemon_switch_before_deletion(self):
        project = "omnis-local-" + "a" * 32
        tag = "omnis-control-" + "a" * 32 + ":0.1.0"
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            scratch = Path(name)
            data = scratch / "data"
            root = data / "omnis"
            release = root / "releases/0.1.0"
            release.mkdir(parents=True, mode=0o700)
            root.chmod(0o700)
            manifest = b'{"synthetic":"manifest"}'
            (release / "release.json").write_bytes(manifest)
            digest = hashlib.sha256(manifest).hexdigest()
            with socket.socket(socket.AF_UNIX) as listener:
                path = scratch / "docker.sock"
                listener.bind(str(path))
                host = f"unix://{path}"
                intent = root / "image-installing.json"
                intent.write_text(
                    json.dumps(
                        {
                            "format": 1,
                            "release": "0.1.0",
                            "project": project,
                            "tag": tag,
                            "manifest_sha256": digest,
                            "docker_host": host,
                            "docker_id": "daemon-one",
                        }
                    )
                )
                intent.chmod(0o600)

                def command(argv, **_kwargs):
                    if argv[:3] == ["docker", "--host", host] and argv[3:5] == ["image", "inspect"]:
                        return subprocess.CompletedProcess(
                            argv,
                            0,
                            stdout=json.dumps(
                                [
                                    {
                                        "Id": "sha256:" + "b" * 64,
                                        "Config": {
                                            "Labels": {
                                                "org.omnis.project": project,
                                                "org.omnis.bundle_sha256": digest,
                                            }
                                        },
                                    }
                                ]
                            ),
                        )
                    self.fail("No deletion or other Docker operation after daemon switch")

                with (
                    patch("subprocess.run", side_effect=command),
                    patch("test_release._docker_id", side_effect=["daemon-one", "daemon-two"]),
                ):
                    with self.assertRaisesRegex(AssertionError, "daemon changed"):
                        self.cleanup_image_install(data)
                self.assertTrue(intent.exists())

    def cleanup_image_install(self, data, *, uncertain=False):
        root = data / "omnis"
        if not root.exists():
            return
        private_dir(root)
        manifest_sha = hashlib.sha256(
            (root / "releases/0.1.0/release.json").read_bytes()
        ).hexdigest()
        record = None
        malformed = False
        for path, complete in (
            (root / "image.json", True),
            (root / "image-installing.json", False),
        ):
            try:
                record = _record(path, manifest_sha, complete=complete)
            except (OSError, ValueError):
                malformed = True
                continue
            if record is not None:
                break
        if record is None:
            self.assertFalse(malformed, "Image cleanup uncertain: unreadable intent/receipt")
            self.assertFalse(uncertain, "Image outcome uncertain: no recovery intent")
            return  # The installer writes intent before invoking Docker build.
        self.assertEqual(_checked_socket(record.docker_host), record.docker_host)
        self.assertEqual(
            _docker_id(root, record.docker_host),
            record.docker_id,
            "Image cleanup uncertain: Docker daemon changed",
        )
        args = ["docker", "--host", record.docker_host, "image", "inspect", record.tag]
        owned = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
        if owned.returncode:
            self.assertTrue(
                "No such image" in owned.stderr or "No such object" in owned.stderr,
                "Image cleanup uncertain: Docker unavailable",
            )
            if not uncertain:
                return
            self.assertEqual(
                _docker_id(root, record.docker_host),
                record.docker_id,
                "Image cleanup uncertain: Docker daemon changed",
            )
            time.sleep(0.1)
            owned = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
            if owned.returncode:
                self.assertTrue(
                    "No such image" in owned.stderr or "No such object" in owned.stderr,
                    "Image cleanup uncertain: Docker unavailable",
                )
                raise AssertionError("Image outcome uncertain: late daemon build may publish")
        (image,) = json.loads(owned.stdout)
        self.assertEqual(image["Config"]["Labels"]["org.omnis.project"], record.project)
        self.assertEqual(
            image["Config"]["Labels"]["org.omnis.bundle_sha256"], record.manifest_sha256
        )
        if record.image_id:
            self.assertEqual(image["Id"], record.image_id)
        self.assertEqual(
            _docker_id(root, record.docker_host),
            record.docker_id,
            "Image cleanup uncertain: Docker daemon changed",
        )
        subprocess.run(
            ["docker", "--host", record.docker_host, "image", "rm", record.tag],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        again = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
        self.assertEqual(
            _docker_id(root, record.docker_host),
            record.docker_id,
            "Image cleanup uncertain: Docker daemon changed",
        )
        self.assertNotEqual(again.returncode, 0, "Owned image survived cleanup")
        self.assertIn("No such image", again.stderr)
        if uncertain:
            raise AssertionError("Image outcome uncertain: daemon build may publish later")

    def assert_image_install(self, cli, env, data, scratch):
        uncertain = False
        try:
            result = self.run_cli_scope(
                [cli, "install-image"],
                cwd=scratch,
                env=env,
                timeout=420,
            )
            self.assertEqual(result.returncode, 0, "Installed CLI did not build the local image")
            receipt = data / "omnis/image.json"
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
            state = json.loads(receipt.read_text())
            host = state["docker_host"]
            self.assertEqual(_checked_socket(host), host)
            self.assertEqual(_docker_id(data / "omnis", host), state["docker_id"])
            probe = subprocess.run(
                ["docker", "--host", host, "image", "inspect", state["tag"]],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
            (image,) = json.loads(probe.stdout)
            self.assertEqual(image["Id"], state["image_id"])
            self.assertEqual(image["Config"]["Labels"]["org.omnis.project"], state["project"])
            self.assertEqual(
                image["Config"]["Labels"]["org.omnis.bundle_sha256"], state["manifest_sha256"]
            )
            self.assertEqual(image["Config"]["User"], "65532:65532")
            self.assertEqual(image["Config"]["Cmd"], ["python", "-I", "-m", "omnis.serve"])
            self.probe_installed_image(state, scratch)
            if os.environ.get("OMNIS_INSTALLED_CONTROL_PROBE") == "1":
                from control_topology import run_probe

                run_probe(data, state, scratch, cli)
            if (
                os.environ.get("OMNIS_INSTALLED_START_PROBE") == "1"
                or os.environ.get("OMNIS_INSTALLED_PAIR_OPEN_PROBE") == "1"
            ):
                from installed_start import run_installed_start, run_interrupted_start

                run_installed_start(
                    data,
                    state,
                    scratch,
                    cli,
                    pair_open=os.environ.get("OMNIS_INSTALLED_PAIR_OPEN_PROBE") == "1",
                )
                if os.environ.get("OMNIS_INSTALLED_START_PROBE") == "1":
                    run_interrupted_start(data, state, cli)
                    run_interrupted_start(data, state, cli, phase="FORWARDING")
                    run_interrupted_start(data, state, cli, expire_dashboard=True)
                    from installed_start_failures import (
                        run_database_readiness_failure,
                        run_lock_expiry,
                    )

                    run_database_readiness_failure(data, state, cli)
                    run_lock_expiry(data, state, cli)
            docker_binary = shutil.which("docker")
            self.assertIsNotNone(docker_binary)
            denial = scratch / "deny-image-rebuild"
            denial.mkdir(mode=0o700)
            wrapper = denial / "docker"
            wrapper.write_text(
                "#!/usr/bin/env python3\nimport os,sys\n"
                "if 'build' in sys.argv[1:]: sys.exit(97)\n"
                f"os.execv({docker_binary!r}, [{docker_binary!r}, *sys.argv[1:]])\n"
            )
            wrapper.chmod(0o700)
            denied_build = subprocess.run(
                [str(wrapper), "build"],
                cwd=scratch,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            self.assertEqual(denied_build.returncode, 97, "Negative build control must reject")
            repeat_env = {**env, "PATH": f"{denial}:{env['PATH']}"}
            repeated = subprocess.run(
                [cli, "install-image"],
                cwd=scratch,
                env=repeat_env,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(repeated.returncode, 0, "Same installed image must be idempotent")
            self.assertEqual(json.loads(receipt.read_text()), state)
            self.assertNotIn(
                str(scratch), result.stdout + result.stderr + repeated.stdout + repeated.stderr
            )
        except subprocess.TimeoutExpired:
            uncertain = True
            raise
        finally:
            self.cleanup_image_install(data, uncertain=uncertain)
        print(f"IMAGE_INSTALLED_VERIFIED id={state['image_id']} project={state['project']}")

    def assert_compose_config(self, installed_root, scratch):
        state = scratch / "state"
        control = scratch / "control"
        http = scratch / "http"
        state.mkdir(mode=0o700)
        (state / "postgres").mkdir(mode=0o700)
        control.mkdir(mode=0o700)
        http.mkdir(mode=0o700)
        password_file = scratch / "db-password"
        password_file.write_text("synthetic-compose-only")
        password_file.chmod(0o600)
        project = f"omnis-p04-config-{uuid4().hex[:12]}"
        image = "sha256:" + "a" * 64  # Config-only placeholder; never run it.
        env = {
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_PROJECT": project,
            "OMNIS_START_ATTEMPT": uuid4().hex,
            "OMNIS_IMAGE_ID": image,
            "OMNIS_UID": str(os.getuid()),
            "OMNIS_GID": str(os.getgid()),
            "OMNIS_HTTP_PORT": "8765",
            "OMNIS_STATE_ROOT": str(state),
            "OMNIS_CONTROL_DIR": str(control),
            "OMNIS_HTTP_BIND_DIR": str(http),
            "OMNIS_DB_PASSWORD_FILE": str(password_file),
            "OMNIS_DATABASE_URL": "postgresql+psycopg://omnis:synthetic@db:5432/omnis",
        }
        command = [
            "docker",
            "compose",
            "-f",
            str(installed_root / "ops/compose.yaml"),
            "config",
            "--format",
            "json",
        ]
        denied = subprocess.run(
            command,
            cwd=scratch,
            env={"PATH": env["PATH"]},
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertNotEqual(denied.returncode, 0, "Compose must require explicit identity/paths")
        result = subprocess.run(
            command,
            cwd=scratch,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, "Installed Compose config refused")
        config = json.loads(result.stdout)
        self.assertEqual(config["name"], project)
        self.assertEqual(set(config["services"]), {"db", "supervisor", "api"})
        services = config["services"]
        for service in services.values():
            self.assertEqual(service["pull_policy"], "never")
        self.assertEqual(services["api"]["image"], image)
        self.assertEqual(services["supervisor"]["image"], image)
        self.assertEqual(
            services["db"]["image"],
            "postgres:18.6-bookworm@sha256:3725f4e2499eef5134592b3b4ab79a543ed7f8e533b05b5b637af926630f6650",
        )
        self.assertNotIn("ports", services["db"])
        self.assertNotIn("ports", services["supervisor"])
        self.assertNotIn("ports", services["api"])
        self.assertEqual(set(config["secrets"]), {"db_password"})
        self.assertEqual(config["secrets"]["db_password"]["file"], str(password_file))
        self.assertEqual(
            services["db"]["secrets"],
            [{"source": "db_password", "target": "/run/secrets/db_password"}],
        )
        self.assertNotIn("secrets", services["api"])
        self.assertNotIn("secrets", services["supervisor"])
        self.assertEqual(
            services["db"]["environment"],
            {
                "POSTGRES_USER": "omnis",
                "POSTGRES_DB": "omnis",
                "POSTGRES_PASSWORD_FILE": "/run/secrets/db_password",
                "POSTGRES_INITDB_ARGS": "--auth-host=scram-sha-256",
            },
        )
        self.assertEqual(
            services["api"]["environment"],
            {
                "OMNIS_DATABASE_URL": env["OMNIS_DATABASE_URL"],
                "OMNIS_CONTROL_DIR": "/run/omnis-control",
                "OMNIS_HTTP_DIR": "/run/omnis-http",
                "OMNIS_HTTP_PORT": "8765",
            },
        )
        self.assertEqual(
            services["supervisor"]["environment"],
            {
                "OMNIS_DATABASE_URL": env["OMNIS_DATABASE_URL"],
                "OMNIS_CONTROL_DIR": "/run/omnis-control",
            },
        )
        for service in services.values():
            self.assertNotIn("build", service)
            self.assertNotEqual(service.get("network_mode"), "host")
            self.assertFalse(service.get("privileged", False))
            self.assertNotIn("/var/run/docker.sock", json.dumps(service))
            self.assertEqual(set(service["networks"]), {"control"})
        for name in ("api", "supervisor"):
            self.assertTrue(services[name].get("read_only"))
            self.assertEqual(services[name].get("cap_drop"), ["ALL"])
            self.assertEqual(services[name].get("security_opt"), ["no-new-privileges:true"])
        self.assertEqual(services["api"]["user"], f"{os.getuid()}:{os.getgid()}")
        self.assertEqual(services["supervisor"]["user"], f"{os.getuid()}:{os.getgid()}")
        self.assertEqual(services["api"].get("stop_grace_period"), "15s")
        self.assertEqual(len(services["db"]["volumes"]), 1)
        self.assertEqual(len(services["api"]["volumes"]), 2)
        self.assertEqual(len(services["supervisor"]["volumes"]), 1)
        self.assertEqual(services["db"]["volumes"][0]["source"], str(state / "postgres"))
        self.assertEqual(services["db"]["volumes"][0]["target"], "/var/lib/postgresql")
        self.assertEqual(services["api"]["volumes"][0]["source"], str(control))
        self.assertEqual(services["supervisor"]["volumes"][0]["source"], str(control))
        self.assertEqual(services["api"]["volumes"][0]["target"], "/run/omnis-control")
        self.assertEqual(services["api"]["volumes"][1]["source"], str(http))
        self.assertEqual(services["api"]["volumes"][1]["target"], "/run/omnis-http")
        self.assertFalse(services["api"]["volumes"][1].get("read_only", False))
        self.assertEqual(services["supervisor"]["volumes"][0]["target"], "/run/omnis-control")
        self.assertTrue(services["api"]["volumes"][0]["read_only"])
        self.assertFalse(services["supervisor"]["volumes"][0].get("read_only", False))
        self.assertTrue(config["networks"]["control"]["internal"])
        self.assertEqual(config["networks"]["control"]["name"], f"{project}_control")
        self.assertEqual(set(config["networks"]), {"control"})

    def test_build_timeout_reaps_owned_image(self):
        calls = []
        marker = None
        removed = False

        def docker(argv, **_kwargs):
            nonlocal marker, removed
            calls.append(argv)
            if argv[:3] == ["docker", "image", "inspect"]:
                if marker is None or removed:
                    return subprocess.CompletedProcess(argv, 1, stdout="")
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    stdout=json.dumps([{"Config": {"Labels": {"org.omnis.build-probe": marker}}}]),
                )
            if argv[:3] == ["docker", "container", "inspect"]:
                return subprocess.CompletedProcess(argv, 1, stdout="")
            if argv[:2] == ["docker", "build"]:
                marker = argv[argv.index("--label") + 1].split("=", 1)[1]
                raise subprocess.TimeoutExpired(argv, 300)
            if argv[:3] == ["docker", "image", "rm"]:
                removed = True
                return subprocess.CompletedProcess(argv, 0, stdout="")
            raise AssertionError("Unexpected Docker operation in cleanup test")

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            with patch("subprocess.run", side_effect=docker):
                with self.assertRaises(subprocess.TimeoutExpired):
                    self.probe_image(Path(name), Path(name))
        self.assertTrue(removed, "An image tagged before build timeout must be removed")
        self.assertTrue(any(argv[:3] == ["docker", "image", "rm"] for argv in calls))

    def test_run_timeout_reaps_owned_container_before_image(self):
        marker = None
        container_name = None
        container_removed = False
        image_removed = False

        def docker(argv, **_kwargs):
            nonlocal marker, container_name, container_removed, image_removed
            if argv[:3] == ["docker", "image", "inspect"]:
                if marker is None or image_removed:
                    return subprocess.CompletedProcess(argv, 1, stdout="")
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    stdout=json.dumps(
                        [
                            {
                                "Id": "sha256:owned",
                                "Architecture": "amd64",
                                "Config": {
                                    "User": "65532:65532",
                                    "Cmd": ["python", "-I", "-m", "omnis.serve"],
                                    "Env": ["OMNIS_WEB_ROOT=/opt/omnis/web"],
                                    "Labels": {"org.omnis.build-probe": marker},
                                },
                            }
                        ]
                    ),
                )
            if argv[:3] == ["docker", "container", "inspect"]:
                if container_name is None or container_removed:
                    return subprocess.CompletedProcess(argv, 1, stdout="")
                return subprocess.CompletedProcess(
                    argv,
                    0,
                    stdout=json.dumps(
                        [
                            {
                                "Image": "sha256:owned",
                                "Config": {"Labels": {"org.omnis.build-probe": marker}},
                            }
                        ]
                    ),
                )
            if argv[:2] == ["docker", "build"]:
                marker = argv[argv.index("--label") + 1].split("=", 1)[1]
                return subprocess.CompletedProcess(argv, 0, stderr="")
            if argv[:2] == ["docker", "run"]:
                container_name = argv[argv.index("--name") + 1]
                raise subprocess.TimeoutExpired(argv, 25)
            if argv[:4] == ["docker", "container", "rm", "-f"]:
                container_removed = True
                return subprocess.CompletedProcess(argv, 0)
            if argv[:3] == ["docker", "image", "rm"]:
                self.assertTrue(container_removed, "Remove owned container before image")
                image_removed = True
                return subprocess.CompletedProcess(argv, 0)
            raise AssertionError("Unexpected Docker operation in cleanup test")

        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as name:
            with patch("subprocess.run", side_effect=docker):
                with self.assertRaises(subprocess.TimeoutExpired):
                    self.probe_image(Path(name), Path(name))
        self.assertTrue(container_removed)
        self.assertTrue(image_removed)

    def probe_image(self, bundle, scratch):
        tag = f"omnis-p04-image-probe:{uuid4().hex}"
        marker = uuid4().hex
        before = subprocess.run(["docker", "image", "inspect", tag], capture_output=True)
        self.assertNotEqual(before.returncode, 0, "Refuse to adopt an existing image tag")
        names = (f"omnis-p04-probe-{marker[:16]}-default", f"omnis-p04-probe-{marker[:16]}-mapped")
        for name in names:
            existing = subprocess.run(["docker", "container", "inspect", name], capture_output=True)
            self.assertNotEqual(existing.returncode, 0, "Refuse to adopt an existing container")
        image_id = None
        try:
            result = subprocess.run(
                [
                    "docker",
                    "build",
                    "--platform",
                    "linux/amd64",
                    "--pull=false",
                    "--label",
                    f"org.omnis.build-probe={marker}",
                    "-f",
                    str(bundle / "ops/Dockerfile"),
                    "-t",
                    tag,
                    str(bundle),
                ],
                cwd=scratch,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            probe = subprocess.run(
                ["docker", "image", "inspect", tag],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
            (image,) = json.loads(probe.stdout)
            self.assertEqual(image["Config"]["Labels"]["org.omnis.build-probe"], marker)
            image_id = image["Id"]
            self.assertEqual(image["Config"]["User"], "65532:65532")
            self.assertEqual(image["Config"]["Cmd"], ["python", "-I", "-m", "omnis.serve"])
            self.assertIn("OMNIS_WEB_ROOT=/opt/omnis/web", image["Config"]["Env"])
            self.assertEqual(image["Architecture"], "amd64")
            probe_command = [
                "docker",
                "run",
                "--rm",
                "--name",
                names[0],
                "--label",
                f"org.omnis.build-probe={marker}",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                tag,
                "python",
                "-I",
                "-c",
                "import os; from omnis.api import create_app; "
                "from omnis.core.web_assets import WebAssets; assert create_app().routes; "
                "assets=WebAssets(os.environ['OMNIS_WEB_ROOT']).load(); "
                "assert assets and 'index.html' in assets; "
                "print('IMAGE_PROBE_OK uid=' + str(os.getuid()))",
            ]
            run = subprocess.run(
                probe_command,
                cwd=scratch,
                capture_output=True,
                text=True,
                timeout=25,
                check=False,
            )
            self.assertEqual(run.returncode, 0, run.stderr[-2000:])
            self.assertEqual(run.stdout.strip(), "IMAGE_PROBE_OK uid=65532")
            mapped_uid = os.getuid() if os.getuid() not in {0, 65532} else 1001
            mapped_command = [
                *probe_command[:2],
                "--user",
                f"{mapped_uid}:{mapped_uid}",
                *probe_command[2:],
            ]
            mapped_command[mapped_command.index("--name") + 1] = names[1]
            mapped = subprocess.run(
                mapped_command,
                cwd=scratch,
                capture_output=True,
                text=True,
                timeout=25,
                check=False,
            )
            self.assertEqual(mapped.returncode, 0, mapped.stderr[-2000:])
            self.assertEqual(mapped.stdout.strip(), f"IMAGE_PROBE_OK uid={mapped_uid}")
            self.assertTrue(image["Id"].startswith("sha256:"))
            print(f"IMAGE_BUILD_VERIFIED id={image['Id']} uid=65532/mapped={mapped_uid}")
        finally:
            problems = []
            for name in names:
                try:
                    owned = subprocess.run(
                        ["docker", "container", "inspect", name],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        check=False,
                    )
                    if owned.returncode == 0:
                        (container,) = json.loads(owned.stdout)
                        if (
                            container["Config"]["Labels"].get("org.omnis.build-probe") != marker
                            or image_id is not None
                            and container["Image"] != image_id
                        ):
                            problems.append("container identity mismatch")
                            continue
                        subprocess.run(
                            ["docker", "container", "rm", "-f", name],
                            capture_output=True,
                            text=True,
                            timeout=30,
                            check=True,
                        )
                        again = subprocess.run(
                            ["docker", "container", "inspect", name],
                            capture_output=True,
                            timeout=15,
                            check=False,
                        )
                        if again.returncode == 0:
                            problems.append("owned container survived cleanup")
                except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError):
                    problems.append("owned container cleanup uncertain")
            try:
                owned_image = subprocess.run(
                    ["docker", "image", "inspect", tag],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if owned_image.returncode == 0:
                    (current,) = json.loads(owned_image.stdout)
                    if current["Config"]["Labels"].get("org.omnis.build-probe") != marker:
                        problems.append("image identity mismatch")
                    else:
                        subprocess.run(
                            ["docker", "image", "rm", tag],
                            capture_output=True,
                            text=True,
                            timeout=30,
                            check=True,
                        )
                        again = subprocess.run(
                            ["docker", "image", "inspect", tag],
                            capture_output=True,
                            timeout=15,
                            check=False,
                        )
                        if again.returncode == 0:
                            problems.append("owned image survived cleanup")
                elif image_id is not None:
                    problems.append("image identity unavailable after build")
            except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError):
                problems.append("owned image cleanup uncertain")
            if problems:
                raise AssertionError("Probe cleanup incomplete: " + ", ".join(problems))

    def test_real_api_web_and_cli_bundle_is_checkout_independent(self):
        uv = os.environ["OMNIS_UV"]
        cli = os.environ["OMNIS_CLI_BIN"]
        self.assertTrue((ROOT / "web/dist/omnis-web.json").is_file(), "Build web first")
        with self.bundle_scratch() as scratch:

            def run(argv, *, env=None, expected=0, timeout=120):
                result = subprocess.run(
                    argv,
                    cwd=scratch,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                self.assertEqual(
                    result.returncode, expected, f"{argv[0]} returned {result.returncode}"
                )
                return result

            api_wheels = scratch / "api-wheel"
            cli_wheels = scratch / "cli-wheel"
            run(
                [
                    uv,
                    "build",
                    "--no-config",
                    "--wheel",
                    str(ROOT / "api"),
                    "--out-dir",
                    str(api_wheels),
                ]
            )
            run(
                [
                    uv,
                    "build",
                    "--no-config",
                    "--wheel",
                    str(ROOT / "cli"),
                    "--out-dir",
                    str(cli_wheels),
                ]
            )
            requirements = scratch / "requirements.txt"
            run(
                [
                    uv,
                    "export",
                    "--locked",
                    "--no-config",
                    "--directory",
                    str(ROOT / "api"),
                    "--no-dev",
                    "--no-emit-project",
                    "--no-header",
                    "--no-annotate",
                    "--format",
                    "requirements-txt",
                    "--output-file",
                    str(requirements),
                    "--quiet",
                ]
            )
            (api_wheel,) = api_wheels.glob("*.whl")
            (cli_wheel,) = cli_wheels.glob("*.whl")
            bundle = scratch / "bundle"
            run(
                [
                    str(ROOT / "cli/.venv/bin/python"),
                    "-I",
                    str(ROOT / "ops/build_control_bundle.py"),
                    "--api-wheel",
                    str(api_wheel),
                    "--cli-wheel",
                    str(cli_wheel),
                    "--requirements",
                    str(requirements),
                    "--web-root",
                    str(ROOT / "web/dist"),
                    "--output",
                    str(bundle),
                ]
            )
            manifest = json.loads((bundle / "release.json").read_text())
            self.assertEqual(manifest["release"], "0.1.0")
            self.assertEqual(
                set(manifest["files"]),
                {
                    str(path.relative_to(bundle))
                    for path in bundle.rglob("*")
                    if path.is_file() and path.name != "release.json"
                },
            )
            data = scratch / "data"
            env = {
                "PATH": os.environ.get("PATH", ""),
                "XDG_DATA_HOME": str(data),
                "XDG_STATE_HOME": str(scratch / "absent"),
            }
            installed = run([cli, "install", "--bundle", str(bundle)], env=env)
            self.assertNotIn(str(ROOT), installed.stdout + installed.stderr)
            installed_root = data / "omnis/releases/0.1.0"
            self.assertEqual(
                (installed_root / "web/index.html").read_bytes(),
                (ROOT / "web/dist/index.html").read_bytes(),
            )
            self.assert_compose_config(installed_root, scratch)
            compose_source = (installed_root / "ops/compose.yaml").read_text()
            api_security = (
                "    read_only: true\n    cap_drop: [ALL]\n"
                "    security_opt: [no-new-privileges:true]\n    stop_grace_period: 15s\n"
                '    networks: [control]\n    restart: "no"\nsecrets:'
            )
            regressions = [
                (
                    "foreign-port",
                    "        target: /run/omnis-http\n    depends_on:",
                    "        target: /run/omnis-http\n    ports:\n"
                    '      - "0.0.0.0:9876:8765"\n    depends_on:',
                ),
                (
                    "extra-mount",
                    "        target: /run/omnis-http\n    depends_on:",
                    "        target: /run/omnis-http\n      - type: bind\n"
                    "        source: ${OMNIS_HTTP_BIND_DIR:?Explicit private HTTP socket path required}\n"
                    "        target: /extra-writable\n    depends_on:",
                ),
                (
                    "wrong-secret",
                    "POSTGRES_PASSWORD_FILE: /run/secrets/db_password",
                    "POSTGRES_PASSWORD_FILE: /other-secret",
                ),
                (
                    "writable-api-rootfs",
                    api_security,
                    api_security.replace("read_only: true", "read_only: false", 1),
                ),
                (
                    "retained-api-caps",
                    api_security,
                    api_security.replace("cap_drop: [ALL]", "cap_drop: []", 1),
                ),
                (
                    "api-privilege-escalation",
                    api_security,
                    api_security.replace(
                        "security_opt: [no-new-privileges:true]", "security_opt: []", 1
                    ),
                ),
                (
                    "api-stop-too-short",
                    api_security,
                    api_security.replace("stop_grace_period: 15s", "stop_grace_period: 5s", 1),
                ),
            ]
            for label, original, changed in regressions:
                self.assertEqual(compose_source.count(original), 1)
                mutant = scratch / label
                (mutant / "ops").mkdir(parents=True)
                (mutant / "ops/compose.yaml").write_text(
                    compose_source.replace(original, changed, 1)
                )
                runtime = scratch / f"{label}-runtime"
                runtime.mkdir(mode=0o700)
                with self.assertRaises(AssertionError) as failure:
                    self.assert_compose_config(mutant, runtime)
                self.assertNotIn("Installed Compose config refused", str(failure.exception))
            if os.environ.get("OMNIS_IMAGE_PROBE") == "1":
                self.probe_image(installed_root, scratch)
            if os.environ.get("OMNIS_INSTALL_IMAGE_PROBE") == "1":
                self.assert_image_install(cli, env, data, scratch)
            run([cli, "install", "--bundle", str(bundle)], env=env)
            report = run([cli, "status", "--json"], env=env, expected=3)
            self.assertEqual(json.loads(report.stdout)["state"], "NOT_INSTALLED")
            (bundle / "web/index.html").write_bytes(b"tampered")
            foreign_data = scratch / "other-data"
            env["XDG_DATA_HOME"] = str(foreign_data)
            run([cli, "install", "--bundle", str(bundle)], env=env, expected=2)
            self.assertFalse((foreign_data / "omnis/releases").exists())
            rogue = scratch / "rogue-requirements.txt"
            rogue.write_text("-r ../../outside.txt\n# --hash=sha256:fake\n")
            forged = scratch / "forged-bundle"
            run(
                [
                    str(ROOT / "cli/.venv/bin/python"),
                    "-I",
                    str(ROOT / "ops/build_control_bundle.py"),
                    "--api-wheel",
                    str(api_wheel),
                    "--cli-wheel",
                    str(cli_wheel),
                    "--requirements",
                    str(rogue),
                    "--web-root",
                    str(ROOT / "web/dist"),
                    "--output",
                    str(forged),
                ],
                expected=2,
            )
            self.assertFalse(forged.exists())
            fake_uv = scratch / "wrong-version-uv"
            fake_uv.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "from pathlib import Path\n"
                "if sys.argv[1] == '--version':\n"
                "    print('uv 0.0.0')\n"
                "else:\n"
                f"    sys.stdout.buffer.write(Path({str(requirements)!r}).read_bytes())\n"
            )
            fake_uv.chmod(0o700)
            wrong_uv_env = dict(os.environ, OMNIS_UV=str(fake_uv))
            wrong_uv_bundle = scratch / "wrong-uv-bundle"
            run(
                [
                    str(ROOT / "cli/.venv/bin/python"),
                    "-I",
                    str(ROOT / "ops/build_control_bundle.py"),
                    "--api-wheel",
                    str(api_wheel),
                    "--cli-wheel",
                    str(cli_wheel),
                    "--requirements",
                    str(requirements),
                    "--web-root",
                    str(ROOT / "web/dist"),
                    "--output",
                    str(wrong_uv_bundle),
                ],
                env=wrong_uv_env,
                expected=2,
            )
            self.assertFalse(wrong_uv_bundle.exists())
            fifo = scratch / api_wheel.name
            os.mkfifo(fifo)
            refused = run(
                [
                    str(ROOT / "cli/.venv/bin/python"),
                    "-I",
                    str(ROOT / "ops/build_control_bundle.py"),
                    "--api-wheel",
                    str(fifo),
                    "--cli-wheel",
                    str(cli_wheel),
                    "--requirements",
                    str(requirements),
                    "--web-root",
                    str(ROOT / "web/dist"),
                    "--output",
                    str(scratch / "foreign-bundle"),
                ],
                expected=2,
                timeout=2,
            )
            self.assertEqual(refused.stderr.strip(), "BUNDLE_REFUSED")
