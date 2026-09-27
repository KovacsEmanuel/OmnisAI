"""Build and install a real locked control bundle outside the checkout."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]


class ReleaseBundleTest(unittest.TestCase):
    def assert_compose_config(self, installed_root, scratch):
        state = scratch / "state"
        control = scratch / "control"
        state.mkdir(mode=0o700)
        (state / "postgres").mkdir(mode=0o700)
        control.mkdir(mode=0o700)
        password_file = scratch / "db-password"
        password_file.write_text("synthetic-compose-only")
        password_file.chmod(0o600)
        project = f"omnis-p04-config-{uuid4().hex[:12]}"
        image = "sha256:" + "a" * 64  # Config-only placeholder; never run it.
        env = {
            "PATH": os.environ.get("PATH", ""),
            "OMNIS_PROJECT": project,
            "OMNIS_IMAGE_ID": image,
            "OMNIS_UID": str(os.getuid()),
            "OMNIS_GID": str(os.getgid()),
            "OMNIS_HTTP_PORT": "8765",
            "OMNIS_STATE_ROOT": str(state),
            "OMNIS_CONTROL_DIR": str(control),
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
        self.assertEqual(
            services["api"]["ports"],
            [
                {
                    "mode": "ingress",
                    "host_ip": "127.0.0.1",
                    "target": 8765,
                    "published": "8765",
                    "protocol": "tcp",
                }
            ],
        )
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
        self.assertEqual(services["api"]["user"], f"{os.getuid()}:{os.getgid()}")
        self.assertEqual(services["supervisor"]["user"], f"{os.getuid()}:{os.getgid()}")
        self.assertEqual(len(services["db"]["volumes"]), 1)
        self.assertEqual(len(services["api"]["volumes"]), 1)
        self.assertEqual(len(services["supervisor"]["volumes"]), 1)
        self.assertEqual(services["db"]["volumes"][0]["source"], str(state / "postgres"))
        self.assertEqual(services["db"]["volumes"][0]["target"], "/var/lib/postgresql")
        self.assertEqual(services["api"]["volumes"][0]["source"], str(control))
        self.assertEqual(services["supervisor"]["volumes"][0]["source"], str(control))
        self.assertEqual(services["api"]["volumes"][0]["target"], "/run/omnis-control")
        self.assertEqual(services["supervisor"]["volumes"][0]["target"], "/run/omnis-control")
        self.assertTrue(services["api"]["volumes"][0]["read_only"])
        self.assertFalse(services["supervisor"]["volumes"][0].get("read_only", False))
        self.assertTrue(config["networks"]["control"]["internal"])
        self.assertEqual(config["networks"]["control"]["name"], f"{project}_control")

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
        with tempfile.TemporaryDirectory(prefix="omnis-bundle-", dir=os.environ["TMPDIR"]) as name:
            scratch = Path(name)

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
            regressions = [
                (
                    "foreign-port",
                    '      - "127.0.0.1:${OMNIS_HTTP_PORT:?Explicit host loopback port required}:8765"',
                    '      - "127.0.0.1:${OMNIS_HTTP_PORT:?Explicit host loopback port required}:8765"\n'
                    '      - "0.0.0.0:9876:8765"',
                ),
                (
                    "extra-mount",
                    "        read_only: true\n    ports:",
                    "        read_only: true\n      - type: bind\n"
                    "        source: ${OMNIS_CONTROL_DIR:?Explicit private control path required}\n"
                    "        target: /extra-writable\n    ports:",
                ),
                (
                    "wrong-secret",
                    "POSTGRES_PASSWORD_FILE: /run/secrets/db_password",
                    "POSTGRES_PASSWORD_FILE: /other-secret",
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
