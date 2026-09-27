"""Build and install a real locked control bundle outside the checkout."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ReleaseBundleTest(unittest.TestCase):
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
