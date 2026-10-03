"""Cgroup readback races: real owned pidfds, ordinary private cgroup-shaped files."""

import contextlib
import importlib
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from omnis_cli.lifecycle import StartError

owner = importlib.import_module("omnis_cli.stop_owner")


@contextlib.contextmanager
def family_fixture(*, live=False):
    with tempfile.TemporaryDirectory(prefix="cg-", dir=os.environ["TMPDIR"]) as directory:
        path = Path(directory) / "group"
        path.mkdir()
        events = path / "cgroup.events"
        events.write_text("populated 0\nfrozen 0\n")
        info = path.stat()
        reader, writer = os.pipe()
        child = None
        pidfd = -1
        try:
            child = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    "import os,sys; os.read(int(sys.argv[1]),1)",
                    str(reader),
                ],
                pass_fds=(reader,),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            os.close(reader)
            reader = -1
            pidfd = os.pidfd_open(child.pid)
            if not live:
                os.close(writer)
                writer = -1
                assert child.wait(timeout=3) == 0
            family = owner._ContainerFamily.__new__(owner._ContainerFamily)
            family.fd = pidfd
            family.path = path
            family.identity = (info.st_dev, info.st_ino)
            yield family, events
        finally:
            for fd in (reader, writer):
                if fd >= 0:
                    os.close(fd)
            try:
                if child is not None:
                    try:
                        child.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        if pidfd >= 0:
                            signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                        child.wait(timeout=3)
            finally:
                if pidfd >= 0:
                    os.close(pidfd)


class CgroupDrainTest(unittest.TestCase):
    def test_exited_leader_accepts_empty_or_already_removed_group(self):
        with family_fixture() as (family, events):
            family.drained()
            events.unlink()
            family.path.rmdir()
            family.drained()

    def removal_at(self, cut):
        with family_fixture() as (family, events):
            real_stat, real_read = Path.stat, Path.read_text
            seen = []

            def removed():
                seen.append(cut)
                events.unlink()
                family.path.rmdir()

            def statting(path, *args, **kwargs):
                if path == family.path and cut == "stat" and not seen:
                    removed()
                return real_stat(path, *args, **kwargs)

            def reading(path, *args, **kwargs):
                if path == events and cut == "events" and not seen:
                    removed()
                return real_read(path, *args, **kwargs)

            with patch.object(Path, "stat", statting), patch.object(Path, "read_text", reading):
                family.drained()
            self.assertEqual(seen, [cut])
            self.assertFalse(os.path.lexists(family.path))

    def test_group_removal_during_stat_or_events_is_read_back_as_absent(self):
        for cut in ("stat", "events"):
            with self.subTest(cut=cut):
                self.removal_at(cut)

    def test_missing_events_with_group_present_is_not_drain(self):
        with family_fixture() as (family, events):
            events.unlink()
            with self.assertRaises((StartError, FileNotFoundError)):
                family.drained()
            self.assertTrue(family.path.is_dir())

    def test_live_leader_populated_group_and_replacement_are_refused(self):
        with family_fixture(live=True) as (family, events):
            events.unlink()
            family.path.rmdir()
            with self.assertRaisesRegex(StartError, "STOP_CONTAINER_FAMILY_LIVE"):
                family.drained()
        with family_fixture() as (family, events):
            events.write_text("populated 1\nfrozen 0\n")
            with self.assertRaisesRegex(StartError, "STOP_CONTAINER_FAMILY_LIVE"):
                family.drained()
        with family_fixture() as (family, _events):
            family.path.rename(family.path.with_name("original"))
            family.path.mkdir()
            (family.path / "cgroup.events").write_text("populated 0\nfrozen 0\n")
            with self.assertRaisesRegex(StartError, "STOP_CONTAINER_FAMILY_UNVERIFIED"):
                family.drained()

    def test_access_error_is_not_absence(self):
        with family_fixture() as (family, events):
            original = Path.read_text

            def reading(path, *args, **kwargs):
                if path == events:
                    raise PermissionError("synthetic access denial")
                return original(path, *args, **kwargs)

            with patch.object(Path, "read_text", reading), self.assertRaises(PermissionError):
                family.drained()

    def refused_readback(self, failure):
        with family_fixture() as (family, events):
            original_read, original_lstat = Path.read_text, Path.lstat
            seen = []

            def reading(path, *args, **kwargs):
                if path == events:
                    seen.append("events-missing")
                    if failure == "replacement":
                        family.path.rename(family.path.with_name("original"))
                        family.path.mkdir()
                    raise FileNotFoundError("synthetic concurrent disappearance")
                return original_read(path, *args, **kwargs)

            def lstating(path, *args, **kwargs):
                if path == family.path and seen and failure == "access":
                    raise PermissionError("synthetic readback denial")
                return original_lstat(path, *args, **kwargs)

            with (
                patch.object(Path, "read_text", reading),
                patch.object(Path, "lstat", lstating),
                self.assertRaises((StartError, OSError)),
            ):
                family.drained()
            self.assertEqual(seen, ["events-missing"])

    def test_absence_readback_does_not_hide_access_error_or_replacement(self):
        for failure in ("access", "replacement", "missing-events"):
            with self.subTest(failure=failure):
                self.refused_readback(failure)


if __name__ == "__main__":
    unittest.main()
