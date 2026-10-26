"""Explicit local bundle install must be atomic and independent of the checkout."""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.release import ReleaseError, install_release


class InstallTest(unittest.TestCase):
    def test_install_syncs_published_tree_and_pointer_before_ack(self):
        import omnis_cli.release as release

        with patch.object(release, "_sync_dir", wraps=release._sync_dir) as synced:
            installed = install_release(self.bundle, self.data_home)
        paths = [call.args[0] for call in synced.call_args_list]
        self.assertIn(installed / "web/assets", paths)
        self.assertIn(installed, paths)
        self.assertIn(installed.parent, paths)
        self.assertIn(self.data_home, paths)
        self.assertIn(self.data_home / "omnis", paths)

    def test_repeat_install_refuses_unsynced_recovered_pointer(self):
        import omnis_cli.release as release

        install_release(self.bundle, self.data_home)
        root = self.data_home / "omnis"
        original = release._sync_dir

        def fail_root(path):
            if path == root:
                raise OSError("directory sync failed")
            return original(path)

        with patch.object(release, "_sync_dir", side_effect=fail_root):
            with self.assertRaises(ReleaseError):
                install_release(self.bundle, self.data_home)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="omnis-install-", dir=os.environ["TMPDIR"])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir(mode=0o700)
        self.data_home = self.root / "data"
        self.data_home.mkdir(mode=0o700)
        self.payloads = {
            "api/omnis_api-0.1.0-py3-none-any.whl": b"synthetic api wheel bytes",
            "cli/omnis_cli-0.1.0-py3-none-any.whl": b"synthetic cli wheel bytes",
            "api/requirements.txt": b"# synthetic locked input\n",
            "ops/Dockerfile": b"FROM pinned-synthetic-base\n",
            "ops/compose.yaml": b"name: synthetic-owned-project\nservices: {}\n",
            "web/omnis-web.json": b'{"version":1,"files":{"index.html":"synthetic"}}',
            "web/index.html": b"synthetic index",
            "web/assets/index-1.js": b"synthetic asset",
        }
        self.manifest = {
            "format": 1,
            "release": "0.1.0",
            "schema": "0016_provider_models",
            "platform": "linux/amd64",
            "files": {},
        }
        for name, content in self.payloads.items():
            target = self.bundle / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            self.manifest["files"][name] = hashlib.sha256(content).hexdigest()
        self.write_manifest()

    def write_manifest(self):
        (self.bundle / "release.json").write_text(json.dumps(self.manifest, sort_keys=True))

    def native_bundle(self):
        """Small SOURCE producer-schema fixture, not real native provenance."""
        requirements = (
            b"fixture==1 --hash=sha256:" + hashlib.sha256(b"wheel").hexdigest().encode() + b"\n"
        )
        source_files = {"hermes_cli/main.py": hashlib.sha256(b"management").hexdigest()}
        pin = {"python": "3.13.15", "license_sha256": hashlib.sha256(b"license").hexdigest()}
        deps = {"files": {"requirements-native.txt": hashlib.sha256(requirements).hexdigest()}}
        source = {
            "schema_version": 1,
            "pin": pin,
            "original_files": source_files,
            "patched_files": {},
            "managed_patched_files": {},
            "management_patched_files": {},
            "dependency_override": deps,
            "native_started": False,
            "provider_calls": "NOT_RUN",
            "assessment_ready": False,
        }
        adapter = {
            "name": "omnis_hermes-0.1.0-py3-none-any.whl",
            "sha256": hashlib.sha256(b"adapter").hexdigest(),
        }
        build = {
            "schema_version": 1,
            "python": "3.13.15",
            "dependency_wheels": [
                {
                    "url": "https://files.pythonhosted.org/packages/fixture-1-py3-none-any.whl",
                    "hash": "sha256:" + hashlib.sha256(b"wheel").hexdigest(),
                    "size": 5,
                    "upload-time": "2026-01-01T00:00:00Z",
                }
            ],
            "native_source_files": source_files,
            "native_distribution": "supported source layout (not a Nix wheel)",
            "dependency_override": deps,
            "native_started": False,
            "adapter_injected": True,
            "adapter_wheel": adapter,
        }
        metadata = {
            "source-manifest.json": json.dumps(source).encode(),
            "build-manifest.json": json.dumps(build).encode(),
            "requirements-native.txt": requirements,
            "requirements-artifacts.txt": (
                "# Separate Omnis adapter input required for OCI.\n"
                + adapter["name"]
                + " --hash=sha256:"
                + adapter["sha256"]
                + "\n"
            ).encode(),
        }
        context = self.root / "prepared"
        context.mkdir(mode=0o700)
        for name, body in {
            **metadata,
            "LICENSE.hermes": b"license",
            "runtime-source/hermes_cli/main.py": b"management",
            "wheelhouse/fixture-1-py3-none-any.whl": b"wheel",
            "wheelhouse/" + adapter["name"]: b"adapter",
        }.items():
            path = context / name
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.write_bytes(body)
        self.manifest.update(format=2, profile="p4a-settings-offline")
        for name, body in {
            **{"native/" + n: b for n, b in metadata.items()},
            "ops/Dockerfile.hermes": b"FROM sealed-fixture\n",
        }.items():
            path = self.bundle / name
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            path.write_bytes(body)
            self.manifest["files"][name] = hashlib.sha256(body).hexdigest()
        self.write_manifest()
        return context

    def test_native_profile_installs_exact_sealed_metadata(self):
        self.native_bundle()
        installed = install_release(self.bundle, self.data_home)
        self.assertEqual(
            (installed / "native/build-manifest.json").read_bytes(),
            (self.bundle / "native/build-manifest.json").read_bytes(),
        )
        self.assertEqual(json.loads((installed / "release.json").read_bytes())["format"], 2)
        self.assertFalse((self.data_home / "omnis/image.json").exists())

    def test_bundle_producer_refuses_nonobject_native_metadata(self):
        import io
        import runpy
        import subprocess
        import sys
        import zipfile

        context = self.native_bundle()
        (context / "source-manifest.json").write_bytes(b"[]")
        namespace = runpy.run_path(
            str(Path(__file__).resolve().parents[2] / "ops/build_control_bundle.py")
        )
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as wheel:
            wheel.writestr("fixture", "SOURCE fixture, not installable provenance")
        api = self.bundle / "api/omnis_api-0.1.0-py3-none-any.whl"
        cli = self.bundle / "cli/omnis_cli-0.1.0-py3-none-any.whl"
        api.write_bytes(archive.getvalue())
        cli.write_bytes(archive.getvalue())
        requirements = b"fixture==1 --hash=sha256:" + b"a" * 64 + b"\n"
        req = self.bundle / "api/requirements.txt"
        req.write_bytes(requirements)
        web = self.bundle / "web"
        (web / "omnis-web.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "files": {
                        name: hashlib.sha256((web / name).read_bytes()).hexdigest()
                        for name in ("index.html", "assets/index-1.js")
                    },
                }
            )
        )
        with (
            patch.dict(os.environ, {"OMNIS_UV": str(Path(sys.executable).resolve())}),
            patch.object(
                namespace["subprocess"],
                "run",
                side_effect=[
                    subprocess.CompletedProcess([], 0, b"uv 0.12.19 (x86_64-unknown-linux-gnu)"),
                    subprocess.CompletedProcess([], 0, requirements),
                ],
            ),
        ):
            with self.assertRaises(ValueError):
                namespace["build_bundle"](
                    api, cli, req, web, self.root / "output", runtime_metadata=context
                )
        self.assertFalse((self.root / "output").exists())

    def test_native_release_keeps_file_and_aggregate_caps(self):
        from omnis_cli.release import _manifest

        self.native_bundle()
        path = self.bundle / "ops/Dockerfile.hermes"
        for size in (2 * 1024 * 1024, 2 * 1024 * 1024 + 1):
            body = b"x" * size
            path.write_bytes(body)
            self.manifest["files"]["ops/Dockerfile.hermes"] = hashlib.sha256(body).hexdigest()
            self.write_manifest()
            if size == 2 * 1024 * 1024:
                _manifest(self.bundle)
            else:
                with self.assertRaises(ReleaseError):
                    _manifest(self.bundle)
        path.write_bytes(b"fixture")
        self.manifest["files"]["ops/Dockerfile.hermes"] = hashlib.sha256(b"fixture").hexdigest()
        remaining = 8 * 1024 * 1024 - sum(
            (self.bundle / name).stat().st_size for name in self.manifest["files"]
        )
        index = 0
        while remaining:
            name = f"web/assets/budget-{index}.txt"
            body = b"x" * min(remaining, 2 * 1024 * 1024)
            (self.bundle / name).write_bytes(body)
            self.manifest["files"][name] = hashlib.sha256(body).hexdigest()
            remaining -= len(body)
            index += 1
        self.write_manifest()
        _manifest(self.bundle)
        name = "web/assets/overflow.txt"
        (self.bundle / name).write_bytes(b"x")
        self.manifest["files"][name] = hashlib.sha256(b"x").hexdigest()
        self.write_manifest()
        with self.assertRaises(ReleaseError):
            _manifest(self.bundle)

    def test_native_context_exact_closure_and_link_extra_hash_denials(self):
        from omnis_cli import native_artifacts
        from omnis_cli.release import _manifest

        context = self.native_bundle()
        _, payloads = _manifest(self.bundle)
        native_artifacts.validate_context(context, payloads)
        stage = self.root / "stage"
        native_artifacts.stage_context(context, payloads, stage)
        self.assertEqual((stage / "runtime-source/hermes_cli/main.py").read_bytes(), b"management")
        target = context / "runtime-source/hermes_cli/main.py"
        for cut in ("hash", "extra", "symlink", "hardlink", "metadata", "traversal"):
            with self.subTest(cut=cut):
                backup = target.read_bytes()
                original = (context / "build-manifest.json").read_bytes()
                if cut == "hash":
                    target.write_bytes(b"wrong")
                elif cut == "extra":
                    (context / "runtime-source/extra.py").write_bytes(b"unexpected")
                elif cut == "symlink":
                    target.unlink()
                    target.symlink_to(context / "LICENSE.hermes")
                elif cut == "hardlink":
                    os.link(target, context / "foreign-link")
                elif cut == "metadata":
                    (context / "build-manifest.json").write_bytes(b"{}")
                elif cut == "traversal":
                    forged = json.loads(payloads["native/build-manifest.json"])
                    forged["native_source_files"]["../outside.py"] = "a" * 64
                    payloads["native/build-manifest.json"] = json.dumps(forged).encode()
                with self.assertRaises(ValueError):
                    native_artifacts.validate_context(context, payloads)
                target.unlink()
                target.write_bytes(backup)
                (context / "runtime-source/extra.py").unlink(missing_ok=True)
                (context / "foreign-link").unlink(missing_ok=True)
                (context / "build-manifest.json").write_bytes(original)
                payloads["native/build-manifest.json"] = original
        native_artifacts.validate_context(context, payloads)

    def test_local_install_is_idempotent_and_does_not_create_an_instance(self):
        result = install_release(self.bundle, self.data_home)
        self.assertEqual(result, self.data_home / "omnis/releases/0.1.0")
        self.assertEqual((result / "web/index.html").read_bytes(), b"synthetic index")
        self.assertEqual((self.data_home / "omnis/installed.json").stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / "instance.json").exists())
        self.assertEqual(install_release(self.bundle, self.data_home), result)

    def test_settings_schema_bundle_is_admitted_and_old_heads_are_refused(self):
        self.manifest["schema"] = "0016_provider_models"
        self.write_manifest()
        installed = install_release(self.bundle, self.data_home)
        self.assertEqual(
            json.loads((installed / "release.json").read_text())["schema"],
            "0016_provider_models",
        )
        before = (installed / "release.json").read_bytes()
        for previous in (
            "0015_model_test_v2",
            "0014_provider_settings",
            "0013_mission_revisions",
            "0012_contract_methods",
            "0009_catalog_candidates",
        ):
            with self.subTest(schema=previous):
                self.manifest["schema"] = previous
                self.write_manifest()
                with self.assertRaises(ReleaseError):
                    install_release(self.bundle, self.root / "legacy-data")
                self.assertFalse((self.root / "legacy-data").exists())
                self.assertEqual((installed / "release.json").read_bytes(), before)

    def test_pre_p1_schema_bundle_is_refused_before_install(self):
        self.manifest["schema"] = "0006_stop_reconciliation"
        self.write_manifest()
        with self.assertRaises(ReleaseError):
            install_release(self.bundle, self.data_home)
        self.assertFalse((self.data_home / "omnis/installed.json").exists())

    def test_changed_payload_refused_without_partial_install(self):
        (self.bundle / "web/index.html").write_bytes(b"different")
        with self.assertRaises(ReleaseError):
            install_release(self.bundle, self.data_home)
        self.assertFalse((self.data_home / "omnis/releases/0.1.0").exists())

    def test_symlink_and_unlisted_file_refused(self):
        (self.bundle / "web/index.html").unlink()
        (self.bundle / "web/index.html").symlink_to(self.bundle / "web/assets/index-1.js")
        with self.assertRaises(ReleaseError):
            install_release(self.bundle, self.data_home)
        (self.bundle / "web/index.html").unlink()
        (self.bundle / "web/index.html").write_bytes(self.payloads["web/index.html"])
        (self.bundle / ".env").write_text("not an asset")
        with self.assertRaises(ReleaseError):
            install_release(self.bundle, self.data_home)
        self.assertFalse((self.data_home / "omnis/releases/0.1.0").exists())

    def test_installed_release_cannot_be_replaced_implicitly(self):
        first = install_release(self.bundle, self.data_home)
        (self.bundle / "web/index.html").write_bytes(b"different")
        self.manifest["files"]["web/index.html"] = hashlib.sha256(b"different").hexdigest()
        self.write_manifest()
        with self.assertRaises(ReleaseError):
            install_release(self.bundle, self.data_home)
        self.assertEqual((first / "web/index.html").read_bytes(), b"synthetic index")

    def test_fresh_data_home_is_created_privately(self):
        fresh = self.root / "fresh" / "share"
        result = install_release(self.bundle, fresh)
        self.assertEqual(result, fresh / "omnis/releases/0.1.0")
        self.assertEqual(fresh.stat().st_mode & 0o777, 0o700)

    def test_overlapping_bundle_and_data_home_refused_before_writing(self):
        with self.assertRaises(ReleaseError):
            install_release(self.bundle, self.bundle)
        self.assertFalse((self.bundle / "omnis").exists())

    def test_competing_installed_pointer_is_not_overwritten(self):
        import omnis_cli.release as release

        original = release.tempfile.mkstemp
        pointer = self.data_home / "omnis/installed.json"

        def compete(*args, **kwargs):
            fd, name = original(*args, **kwargs)
            if kwargs.get("prefix") == ".installed-":
                pointer.write_text('{"format":1,"release":"different"}')
                pointer.chmod(0o600)
            return fd, name

        with patch.object(release.tempfile, "mkstemp", side_effect=compete):
            with self.assertRaises(ReleaseError):
                install_release(self.bundle, self.data_home)
        self.assertEqual(json.loads(pointer.read_text())["release"], "different")

    def test_empty_competing_directory_is_not_replaced(self):
        from omnis_cli.release import publish_directory

        stage = self.root / "stage"
        target = self.root / "target"
        stage.mkdir()
        target.mkdir()
        (stage / "marker").write_text("ours")
        with self.assertRaises(FileExistsError):
            publish_directory(stage, target)
        self.assertFalse((target / "marker").exists())

    def test_disappearing_competing_pointer_is_not_success(self):
        import omnis_cli.release as release

        with patch.object(release.os, "link", side_effect=FileExistsError):
            with self.assertRaises(ReleaseError):
                install_release(self.bundle, self.data_home)
        self.assertFalse((self.data_home / "omnis/installed.json").exists())
