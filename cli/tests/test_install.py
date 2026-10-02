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
            "schema": "0005_stop_fence",
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

    def test_local_install_is_idempotent_and_does_not_create_an_instance(self):
        result = install_release(self.bundle, self.data_home)
        self.assertEqual(result, self.data_home / "omnis/releases/0.1.0")
        self.assertEqual((result / "web/index.html").read_bytes(), b"synthetic index")
        self.assertEqual((self.data_home / "omnis/installed.json").stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / "instance.json").exists())
        self.assertEqual(install_release(self.bundle, self.data_home), result)

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
