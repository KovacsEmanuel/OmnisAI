"""Negative controls on the real cold CLI; filesystem real, PG/OCI substituted."""

import contextlib
import io
import os
import tarfile
import unittest
from unittest.mock import patch

import test_cold_backup as fixtures
from omnis_cli.lifecycle import StartError, read_record, write_record
from omnis_cli.main import main
from omnis_cli.start_runtime import ControlRuntime


class ColdControlsTest(unittest.TestCase):
    def test_snapshot_refusals_before_restore_effects(self):
        fixture = fixtures.ColdBackupTest()
        cold = fixture.module()
        for fault in (
            "tamper",
            "symlink",
            "hardlink",
            "extra",
            "manifest-limit",
            "archive-limit",
            "uuid",
            "bool",
            "profile",
        ):
            with self.subTest(fault=fault), fixture.source() as (base, root, old, runtime):
                with (
                    patch.object(cold, "ControlRuntime", return_value=runtime),
                    patch.object(cold, "archive", side_effect=fixture.archive),
                    patch.object(cold, "cold_identity", return_value=old["system_id"]),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    snapshot = base / "snapshot"
                    self.assertEqual(main(["backup", "--output", str(snapshot)]), 0)
                    if fault == "tamper":
                        (snapshot / "db-password").write_bytes(b"tampered")
                    elif fault in {"symlink", "hardlink"}:
                        (snapshot / "db-password").unlink()
                        if fault == "symlink":
                            (snapshot / "db-password").symlink_to(root / "db-password")
                        else:
                            os.link(root / "db-password", snapshot / "db-password")
                    elif fault == "extra":
                        (snapshot / "extra").touch(mode=0o600)
                    elif fault == "manifest-limit":
                        (snapshot / "manifest.json").write_bytes(b" " * 16385)
                    elif fault == "archive-limit":
                        with (snapshot / "postgres.tar").open("r+b") as out:
                            out.truncate(cold.ARCHIVE_LIMIT + 1)
                    else:
                        manifest = read_record(snapshot / "manifest.json")
                        manifest[
                            {"uuid": "instance_id", "bool": "version", "profile": "profile"}[fault]
                        ] = {"uuid": "not-a-uuid", "bool": True, "profile": "other"}[fault]
                        write_record(snapshot / "manifest.json", manifest, replace=True)
                    target = base / "new"
                    target.mkdir(mode=0o700)
                    with (
                        patch.dict(os.environ, {"XDG_STATE_HOME": str(target)}),
                        patch.object(
                            cold, "archive", side_effect=AssertionError("effect before validation")
                        ),
                    ):
                        self.assertEqual(main(["restore", "--backup", str(snapshot)]), 4)
                        self.assertFalse((target / "omnis").exists())

    def test_active_source_and_existing_destination_never_overwritten(self):
        fixture = fixtures.ColdBackupTest()
        cold = fixture.module()
        for fault in ("active", "existing", "symlink"):
            with self.subTest(fault=fault), fixture.source() as (base, root, old, runtime):
                output = base / "snapshot"
                if fault == "active":
                    old["phase"] = "READY"
                    write_record(root / "startup.json", old, replace=True)
                elif fault == "existing":
                    output.mkdir(mode=0o700)
                else:
                    output.symlink_to(root)
                before = (root / "startup.json").read_bytes()
                with (
                    patch.object(cold, "ControlRuntime", return_value=runtime),
                    patch.object(cold, "archive", side_effect=AssertionError("unexpected archive")),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(main(["backup", "--output", str(output)]), 4)
                self.assertEqual((root / "startup.json").read_bytes(), before)

    def test_archive_rejects_links_traversal_special_duplicate_and_expansion(self):
        fixture = fixtures.ColdBackupTest()
        cold = fixture.module()
        for fault in (
            "../escape",
            "/escape",
            "18/../escape",
            "symlink",
            "hardlink",
            "fifo",
            "duplicate",
            "expansion",
        ):
            with self.subTest(fault=fault), fixture.source() as (base, _root, _old, runtime):
                path = base / "bad.tar"
                with tarfile.open(path, "w") as out:
                    entry = tarfile.TarInfo(fault if "/" in fault else "18/bad")
                    entry.type = {
                        "symlink": tarfile.SYMTYPE,
                        "hardlink": tarfile.LNKTYPE,
                        "fifo": tarfile.FIFOTYPE,
                    }.get(fault, tarfile.REGTYPE)
                    entry.linkname = "../../escape" if fault in {"symlink", "hardlink"} else ""
                    if fault == "expansion":
                        entry.size = cold.ARCHIVE_LIMIT + 1
                    if fault == "expansion":
                        out.fileobj.write(entry.tobuf())
                    else:
                        out.addfile(entry)
                    if fault == "duplicate":
                        out.addfile(entry)
                with self.assertRaises((StartError, tarfile.TarError)):
                    cold.validate_tar(path, runtime.deadline)

    def test_restored_marker_identity_or_payload_changes_are_refused(self):
        fixture = fixtures.ColdBackupTest()
        cold = fixture.module()
        for fault in ("identity", "ciphertext", "key", "intent"):
            with self.subTest(fault=fault), fixture.source() as (base, _root, old, runtime):
                with (
                    patch.object(cold, "ControlRuntime", return_value=runtime),
                    patch.object(cold, "archive", side_effect=fixture.archive),
                    patch.object(cold, "cold_identity", return_value=old["system_id"]),
                    contextlib.redirect_stdout(io.StringIO()),
                ):
                    self.assertEqual(main(["backup", "--output", str(base / "snapshot")]), 0)
                    parent = base / "new"
                    parent.mkdir(mode=0o700)
                    with patch.dict(os.environ, {"XDG_STATE_HOME": str(parent)}):
                        self.assertEqual(main(["restore", "--backup", str(base / "snapshot")]), 0)
                    target = parent / "omnis"
                    if fault == "identity":
                        (target / "vault").rename(target / "old-vault")
                        (target / "vault").mkdir(mode=0o700)
                    elif fault == "ciphertext":
                        (target / "vault/vault.json").write_bytes(b"changed")
                    elif fault == "key":
                        (target / "vault-key/master.key").touch(mode=0o600)
                    else:
                        marker = read_record(target / "restore.json")
                        marker["state"] = "STARTING"
                        write_record(target / "restore.json", marker, replace=True)
                    with self.assertRaises((OSError, ValueError)):
                        cold.admit_restore(runtime, target)

    def test_binary_fd_owner_roundtrip_above_text_limit_and_invalid_fd(self):
        fixture = fixtures.ColdBackupTest()
        with fixture.source() as (base, _root, _old, original):
            runtime = ControlRuntime.__new__(ControlRuntime)
            runtime.deadline, runtime.uncertain, runtime.family_drained = (
                original.deadline,
                False,
                True,
            )
            runtime.release, runtime.host = base, "synthetic-host"
            runtime.docker = base / "child"
            runtime.docker.write_text(
                "#!/usr/bin/python3\nimport os\nfor _ in range(80): os.write(1, b'\\x00\\xff' * 32768)\n"
            )
            runtime.docker.chmod(0o700)
            path = base / "binary"
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            try:
                result = runtime.run("synthetic", stdout_fd=fd, effect=True)
                self.assertEqual(result.stdout, "")
                self.assertEqual(os.fstat(fd).st_size, 80 * 65536)
                self.assertEqual(path.read_bytes(), b"\x00\xff" * (40 * 65536))
                self.assertFalse(runtime.uncertain)
                self.assertTrue(runtime.family_drained)
                os.ftruncate(fd, 1024**3 + 1)
                with self.assertRaisesRegex(StartError, "COMMAND_BINARY_FD_INVALID"):
                    runtime.run("must-not-spawn", stdin_fd=fd)
            finally:
                os.close(fd)
