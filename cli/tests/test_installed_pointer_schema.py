"""AR02: private installed-pointer files, real consumers and strict manifest controls.

Fixtures are checksum-bound synthetic bundles, not runnable API releases.
No Docker/DB call is allowed; image preflight is intercepted explicitly.
"""

import contextlib
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.compose import ImageInstallError
from omnis_cli.main import main
from omnis_cli.release import ReleaseError, _installed_pointer, _manifest, install_release


class InstalledPointerSchemaTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ar2-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir(mode=0o700)
        self.data = self.root / "data"
        self.data.mkdir(mode=0o700)
        self.cwd = self.root / "external-cwd"
        self.cwd.mkdir(mode=0o700)
        self.payloads = {
            "api/omnis_api-0.1.0-py3-none-any.whl": b"synthetic api wheel",
            "cli/omnis_cli-0.1.0-py3-none-any.whl": b"synthetic cli wheel",
            "api/requirements.txt": b"# synthetic locked requirements\n",
            "ops/Dockerfile": b"FROM synthetic-pinned-base\n",
            "ops/compose.yaml": b"name: synthetic-project\nservices: {}\n",
            "web/omnis-web.json": b'{"version":1,"files":{}}',
            "web/index.html": b"synthetic index",
            "web/assets/app-1.js": b"synthetic asset",
        }
        self.manifest = {
            "format": 1,
            "release": "0.1.0",
            "schema": "0005_stop_fence",
            "platform": "linux/amd64",
            "files": {
                name: hashlib.sha256(content).hexdigest() for name, content in self.payloads.items()
            },
        }
        for name, content in self.payloads.items():
            target = self.bundle / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            target.write_bytes(content)
            target.chmod(0o600)
        (self.bundle / "release.json").write_text(json.dumps(self.manifest))
        self.release = install_release(self.bundle, self.data)
        self.pointer = self.data / "omnis/installed.json"
        self.valid = {"format": 1, "release": "0.1.0"}
        self.env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.root / "home"),
            "XDG_DATA_HOME": str(self.data),
            "XDG_STATE_HOME": str(self.root / "state"),
            "XDG_RUNTIME_DIR": str(self.root / "runtime"),
        }

    def invalid_pointers(self):
        for value in (True, 1.0, False, 2, "ar02-secret-marker", None):
            yield (
                f"format-{type(value).__name__}-{value}",
                json.dumps({**self.valid, "format": value}).encode(),
            )
        for field in self.valid:
            yield (
                f"missing-{field}",
                json.dumps(
                    {key: value for key, value in self.valid.items() if key != field}
                ).encode(),
            )
        yield "extra", json.dumps({**self.valid, "extra": "ar02-secret-marker"}).encode()
        for field in self.valid:
            yield (
                f"duplicate-{field}",
                (
                    json.dumps(self.valid).removesuffix("}")
                    + f',"{field}":{json.dumps(self.valid[field])}}}'
                ).encode(),
            )
        for value in (True, 1, 1.0, None, "ar02-secret-marker"):
            yield f"release-{value}", json.dumps({**self.valid, "release": value}).encode()
        for value in ([], None, True, 1, "ar02-secret-marker"):
            yield f"top-level-{value}", json.dumps(value).encode()

    def write_pointer(self, content):
        self.pointer.write_bytes(content)
        self.pointer.chmod(0o600)

    def snapshot(self):
        result = {}
        for path in self.root.rglob("*"):
            info = path.lstat()
            result[str(path.relative_to(self.root))] = (
                info.st_ino,
                info.st_uid,
                stat.S_IMODE(info.st_mode),
                info.st_nlink,
                path.read_bytes() if path.is_file() else None,
            )
        return result

    def console(self, *args):
        return subprocess.run(
            [str(Path(sys.executable).with_name("omnis")), *args],
            cwd=self.cwd,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def assert_start_refusal(self, result, reason):
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "state": "REFUSED",
                "reason": reason,
                "dashboard_ready": False,
                "assessment_ready": False,
                "browser_opened": False,
            },
        )
        self.assertEqual(result.stderr, "")
        self.assertNotIn("ar02-secret-marker", result.stdout)
        self.assertNotIn("Traceback", result.stdout)
        self.assertFalse((self.root / "state").exists())
        self.assertFalse((self.root / "runtime").exists())

    def test_exact_int_control_and_absent_pointer_semantics(self):
        self.assertTrue(_installed_pointer(self.pointer))
        self.assertEqual(_manifest(self.release)[1], self.payloads)
        self.assertEqual(install_release(self.bundle, self.data), self.release)
        before = self.snapshot()
        self.assert_start_refusal(self.console("start", "--no-open", "--json"), "IMAGE_REQUIRED")
        self.assertEqual(self.snapshot(), before)
        self.pointer.unlink()
        self.assertFalse(_installed_pointer(self.pointer))

    def test_real_private_pointer_rejects_noninteger_and_nonexact_schema(self):
        for case, content in self.invalid_pointers():
            with self.subTest(case=case):
                self.write_pointer(content)
                with self.assertRaises(ValueError):
                    _installed_pointer(self.pointer)
                self.assertEqual(self.pointer.read_bytes(), content)
                self.assertEqual(stat.S_IMODE(self.pointer.stat().st_mode), 0o600)

    def test_start_console_refuses_pointer_before_effects_without_payload_or_traceback(self):
        for case, content in self.invalid_pointers():
            with self.subTest(case=case):
                self.write_pointer(content)
                before = self.snapshot()
                self.assert_start_refusal(
                    self.console("start", "--no-open", "--json"), "RELEASE_OR_IMAGE_INVALID"
                )
                self.assertEqual(self.snapshot(), before)

    def test_install_console_refuses_pointer_without_replacing_installed_bytes(self):
        for case, content in self.invalid_pointers():
            with self.subTest(case=case):
                self.write_pointer(content)
                before = self.snapshot()
                result = self.console("install", "--bundle", str(self.bundle))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertEqual(
                    result.stderr,
                    "RELEASE_INSTALL_REFUSED: verificați bundleul și directorul XDG privat.\n",
                )
                self.assertNotIn("ar02-secret-marker", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(self.snapshot(), before)

    def test_image_consumer_refuses_before_preflight_and_preserves_files(self):
        # A positive control proves the real consumer reaches this seam with
        # int1; the seam refuses without invoking a Docker client on RED too.
        with (
            patch.dict(os.environ, self.env, clear=True),
            patch(
                "omnis_cli.compose._preflight",
                side_effect=ImageInstallError("synthetic stop before Docker"),
            ) as preflight,
            contextlib.redirect_stdout(io.StringIO()) as output,
            contextlib.redirect_stderr(io.StringIO()) as errors,
        ):
            self.assertEqual(main(["install-image"]), 2)
            preflight.assert_called_once_with(self.release)
            self.assertEqual(output.getvalue(), "")
            self.assertEqual(
                errors.getvalue(), "IMAGE_INSTALL_REFUSED: verificați releaseul și Docker local.\n"
            )
        for case, content in self.invalid_pointers():
            with (
                self.subTest(case=case),
                patch.dict(os.environ, self.env, clear=True),
                patch(
                    "omnis_cli.compose._preflight",
                    side_effect=ImageInstallError("synthetic stop before Docker"),
                ) as preflight,
                contextlib.redirect_stdout(io.StringIO()) as output,
                contextlib.redirect_stderr(io.StringIO()) as errors,
            ):
                self.write_pointer(content)
                before = self.snapshot()
                self.assertEqual(main(["install-image"]), 2)
                preflight.assert_not_called()
                self.assertEqual(output.getvalue(), "")
                self.assertEqual(
                    errors.getvalue(),
                    "IMAGE_INSTALL_REFUSED: verificați releaseul și Docker local.\n",
                )
                self.assertEqual(self.snapshot(), before)

    def test_pointer_file_mode_linkcount_nofollow_and_byte_cap_are_preserved(self):
        self.pointer.chmod(0o644)
        with self.assertRaises(ReleaseError):
            _installed_pointer(self.pointer)
        self.pointer.chmod(0o600)
        alias = self.root / "hardlink"
        os.link(self.pointer, alias)
        with self.assertRaises(ReleaseError):
            _installed_pointer(self.pointer)
        alias.unlink()
        content = self.pointer.read_bytes()
        self.pointer.unlink()
        alias.write_bytes(content)
        alias.chmod(0o600)
        self.pointer.symlink_to(alias)
        with self.assertRaises(ReleaseError):
            _installed_pointer(self.pointer)
        self.assertEqual(alias.read_bytes(), content)
        self.pointer.unlink()
        self.write_pointer(content + b" " * (1024 - len(content)))
        self.assertTrue(_installed_pointer(self.pointer))
        self.write_pointer(content + b" " * (1025 - len(content)))
        with self.assertRaises(ReleaseError):
            _installed_pointer(self.pointer)

    def test_manifest_retains_exact_format_fields_release_and_checksums(self):
        self.assertEqual(_manifest(self.release)[1], self.payloads)
        manifest_path = self.release / "release.json"
        for value in (True, 1.0, False, 2, "1", None):
            with self.subTest(format=value):
                manifest_path.write_text(json.dumps({**self.manifest, "format": value}))
                with self.assertRaises(ReleaseError):
                    _manifest(self.release)
        for field in self.manifest:
            with self.subTest(missing=field):
                manifest_path.write_text(
                    json.dumps({key: value for key, value in self.manifest.items() if key != field})
                )
                with self.assertRaises(ReleaseError):
                    _manifest(self.release)
        for field, value in (
            ("extra", "ar02-secret-marker"),
            ("release", "other"),
            ("schema", "other"),
            ("platform", "other"),
        ):
            with self.subTest(field=field):
                manifest_path.write_text(json.dumps({**self.manifest, field: value}))
                with self.assertRaises(ReleaseError):
                    _manifest(self.release)
        manifest_path.write_text(json.dumps(self.manifest))
        (self.release / "web/index.html").write_bytes(b"altered")
        with self.assertRaisesRegex(ReleaseError, "checksum mismatch"):
            _manifest(self.release)
